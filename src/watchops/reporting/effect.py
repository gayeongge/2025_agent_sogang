"""Action effect report generation."""

from __future__ import annotations

from typing import Iterable, List

from ..models import ActionEffectReport, ActionResult, PostMonitoringTask, RemediationPlan


class ActionEffectReporter:
    """Interface for generating post-action effect summaries."""

    def build_report(
        self,
        plan: RemediationPlan,
        action_results: Iterable[ActionResult],
        post_monitoring: Iterable[PostMonitoringTask],
    ) -> ActionEffectReport:
        raise NotImplementedError


class PrometheusEffectReporter(ActionEffectReporter):
    """Creates effect reports using action outcomes and monitoring tasks."""

    def build_report(
        self,
        plan: RemediationPlan,
        action_results: Iterable[ActionResult],
        post_monitoring: Iterable[PostMonitoringTask],
    ) -> ActionEffectReport:
        results_list = list(action_results)
        monitoring_list = list(post_monitoring)

        normalized = self._evaluate_normalization(results_list)
        summary = self._summarize(plan, results_list, normalized)
        metrics = self._collect_metrics(results_list, monitoring_list)
        recommendations = self._next_steps(normalized)

        return ActionEffectReport(
            plan_scenario=plan.scenario,
            normalized=normalized,
            summary=summary,
            metrics=metrics,
            recommendations=recommendations,
        )

    def _evaluate_normalization(self, results: List[ActionResult]) -> bool:
        # simple heuristic: all actions succeeded or simulated
        return all(result.status in {"simulated", "success"} for result in results)

    def _summarize(
        self,
        plan: RemediationPlan,
        results: List[ActionResult],
        normalized: bool,
    ) -> str:
        status = "정상화" if normalized else "추가 확인 필요"
        return f"시나리오 '{plan.scenario}' 조치 결과: {status}."

    def _collect_metrics(
        self,
        results: List[ActionResult],
        monitoring: List[PostMonitoringTask],
    ) -> dict:
        return {
            "actions": [
                {
                    "action_type": res.action_type,
                    "status": res.status,
                    "guard_mode": res.metadata.get("guard", {}).get("mode"),
                }
                for res in results
            ],
            "monitoring_tasks": [
                {
                    "query": task.metric_query,
                    "duration": task.duration,
                    "success": task.success_criteria,
                }
                for task in monitoring
            ],
        }

    def _next_steps(self, normalized: bool) -> List[str]:
        if normalized:
            return [
                "향후 30분간 Prometheus 대시보드 상태 확인",
                "사후 RCA 문서화 진행",
            ]
        return [
            "추가 알람 발생 여부 확인 후 역량 동원",
            "SRE 온콜과 협력하여 수동 점검 수행",
        ]
