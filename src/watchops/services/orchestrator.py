"""Service layer orchestrating alert ingestion and workflows."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

from ..alarm_sources.prometheus import PrometheusAlertParser
from ..analytics import CorrelationAnalyzer, PrometheusCorrelationAnalyzer
from ..diagnostics.engine import DiagnosticsEngine
from ..verification import PlanVerificationEngine, ActionCoverageVerifier, SimulationVerifier
from ..monitoring import PostMonitoringGenerator, PrometheusPostMonitoringGenerator
from ..reporting import ActionEffectReporter, PrometheusEffectReporter
from ..ai import HypothesisGenerator, RuleBasedHypothesisGenerator
from ..models import ActionEffectReport, ActionResult, Alert, RemediationPlan
from ..workflows.base import Workflow
from ..actions import ActionClient, ActionExecutor, ActionRegistry, SafetyGuard, DefaultSafetyGuard


class WatchOpsOrchestrator:
    """Central coordinator that maps alerts to remediation workflows."""

    def __init__(
        self,
        *,
        workflows: Sequence[Workflow],
        action_clients: Iterable[ActionClient],
        parser: PrometheusAlertParser | None = None,
        diagnostics: DiagnosticsEngine | None = None,
        hypothesis_generator: HypothesisGenerator | None = None,
        correlation_analyzer: CorrelationAnalyzer | None = None,
        safety_guard: SafetyGuard | None = None,
        verification_engine: PlanVerificationEngine | None = None,
        post_monitoring_generator: PostMonitoringGenerator | None = None,
        action_reporter: ActionEffectReporter | None = None,
    ) -> None:
        self._workflows = list(workflows)
        self._parser = parser or PrometheusAlertParser()
        self._diagnostics = diagnostics or DiagnosticsEngine(checks=[])
        self._hypothesis_generator = hypothesis_generator or RuleBasedHypothesisGenerator()
        self._correlation_analyzer = correlation_analyzer or PrometheusCorrelationAnalyzer()
        self._post_monitoring_generator = (
            post_monitoring_generator or PrometheusPostMonitoringGenerator()
        )
        self._action_reporter = action_reporter or PrometheusEffectReporter()

        registry = ActionRegistry(action_clients)
        guard = safety_guard or DefaultSafetyGuard()
        self._action_executor = ActionExecutor(registry, guard)

        if verification_engine is None:
            verification_engine = PlanVerificationEngine(
                [ActionCoverageVerifier(), SimulationVerifier()]
            )
        self._verification_engine = verification_engine

    def register_workflow(self, workflow: Workflow) -> None:
        self._workflows.append(workflow)

    def register_action_client(self, client: ActionClient) -> None:
        self._action_executor.register(client)

    def plan_prometheus_alert(
        self,
        payload: Dict[str, object],
        *,
        top_k_hypotheses: int = 3,
        user_notes: Iterable[str] | None = None,
    ) -> List[RemediationPlan]:
        alerts = self._parser.parse(payload)
        plans: List[RemediationPlan] = []
        for alert in alerts:
            workflow = self._match_workflow(alert)
            if not workflow:
                continue
            plan = workflow.build_plan(alert)

            findings = self._diagnostics.run(alert)
            if findings:
                plan.diagnostics.extend(findings)

            hypotheses = self._hypothesis_generator.generate(
                alert, top_k=top_k_hypotheses, user_notes=user_notes
            )
            if hypotheses:
                plan.hypotheses.extend(hypotheses)

            correlations = self._correlation_analyzer.analyze(alert)
            if correlations:
                plan.correlations.extend(correlations)

            monitoring_tasks = self._post_monitoring_generator.generate(alert)
            if monitoring_tasks:
                plan.post_monitoring.extend(monitoring_tasks)

            verification_issues = self._verification_engine.verify(plan)
            if verification_issues:
                plan.verifications.extend(verification_issues)

            plans.append(plan)
        return plans

    def execute_plans(self, plans: Iterable[RemediationPlan]) -> List[ActionResult]:
        return self._action_executor.execute_plans(plans)

    def build_reports(
        self,
        plans: Iterable[RemediationPlan],
        action_results: Iterable[ActionResult],
    ) -> List[ActionEffectReport]:
        results_by_scenario: Dict[str, List[ActionResult]] = {}
        for result in action_results:
            scenario = result.metadata.get("plan_scenario", "unknown")
            results_by_scenario.setdefault(scenario, []).append(result)

        reports: List[ActionEffectReport] = []
        for plan in plans:
            results = results_by_scenario.get(plan.scenario, [])
            report = self._action_reporter.build_report(
                plan,
                results,
                plan.post_monitoring,
            )
            plan.reports.append(report)
            reports.append(report)
        return reports

    def process_prometheus_alert(
        self,
        payload: Dict[str, object],
        *,
        execute: bool = False,
        top_k_hypotheses: int = 3,
        user_notes: Iterable[str] | None = None,
    ):
        plans = self.plan_prometheus_alert(
            payload,
            top_k_hypotheses=top_k_hypotheses,
            user_notes=user_notes,
        )
        if not execute:
            return plans
        results = self.execute_plans(plans)
        self.build_reports(plans, results)
        return results

    def _match_workflow(self, alert: Alert) -> Workflow | None:
        for workflow in self._workflows:
            if workflow.matches(alert):
                return workflow
        return None
