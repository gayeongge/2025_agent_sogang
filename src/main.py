"""Entry point demonstrating the WatchOps MVP pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone, timedelta

from watchops.actions import (
    HttpActionClient,
    JiraActionClient,
    MCPActionClient,
    SimulatedActionClient,
    SlackActionClient,
)
from watchops.config import JiraConfig, SlackConfig, WatchOpsConfig, PrometheusConfig
from watchops.diagnostics import (
    DiagnosticsEngine,
    SeveritySanityCheck,
    RecentStartTimeCheck,
    Http5xxContextCheck,
    CpuSpikeContextCheck,
)
from watchops.services.orchestrator import WatchOpsOrchestrator
from watchops.workflows.nginx_5xx import Nginx5xxWorkflow
from watchops.workflows.http_error_rate import HttpErrorRateWorkflow
from watchops.workflows.cpu_spike import CpuSpikeWorkflow
from watchops.architecture import ARCHITECTURE_SKELETON
from watchops.ingestion import (
    PrometheusWebhookCollector,
    CompositeCollector,
    JiraIssueEventCollector,
    SlackChannelEventCollector,
)


def build_demo_config() -> WatchOpsConfig:
    return WatchOpsConfig(
        prometheus=PrometheusConfig(endpoint="https://prometheus.example/api"),
        jira=JiraConfig(base_url="https://jira.example", project_key="OPS"),
        slack=SlackConfig(webhook_url="https://hooks.slack.example/T000/B000/XXX", channel="#watchops"),
    )


def build_demo_diagnostics() -> DiagnosticsEngine:
    checks = [
        SeveritySanityCheck(),
        RecentStartTimeCheck(),
        Http5xxContextCheck(),
        CpuSpikeContextCheck(),
    ]
    return DiagnosticsEngine(checks)


def build_demo_orchestrator(config: WatchOpsConfig) -> WatchOpsOrchestrator:
    workflows = [
        Nginx5xxWorkflow(),
        HttpErrorRateWorkflow(),
        CpuSpikeWorkflow(),
    ]
    action_clients = [
        SlackActionClient(config.slack),
        JiraActionClient(config.jira),
        HttpActionClient(base_url="https://remediation-api.example"),
        MCPActionClient(endpoint="mcp://control-plane/watchops"),
        SimulatedActionClient(action_type="email"),
    ]
    diagnostics = build_demo_diagnostics()
    return WatchOpsOrchestrator(
        workflows=workflows,
        action_clients=action_clients,
        diagnostics=diagnostics,
    )


def build_demo_collectors(orchestrator: WatchOpsOrchestrator) -> CompositeCollector:
    return CompositeCollector([
        PrometheusWebhookCollector(orchestrator),
        JiraIssueEventCollector(),
        SlackChannelEventCollector(),
    ])


def load_demo_prometheus_payload() -> dict:
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(minutes=3)
    return {
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "NginxHigh5xxRate",
                    "service": "frontend-nginx",
                    "env": "prod",
                    "severity": "critical",
                },
                "annotations": {
                    "summary": "5xx error rate is above threshold",
                    "description": "Frontend nginx is returning 12% 5xx responses over the last 5 minutes.",
                },
                "startsAt": now.isoformat(),
                "endsAt": "",
                "fingerprint": "abc123",
            },
            {
                "status": "firing",
                "labels": {
                    "alertname": "HttpErrorRateThresholdExceeded",
                    "service": "checkout-api",
                    "env": "prod",
                    "metric_name": "http_error_rate",
                    "severity": "warning",
                },
                "annotations": {
                    "summary": "HTTP error rate exceeded threshold",
                    "description": "Checkout API reported >7% HTTP 5xx responses.",
                },
                "startsAt": earlier.isoformat(),
                "endsAt": "",
                "fingerprint": "def456",
            },
            {
                "status": "firing",
                "labels": {
                    "alertname": "NodeHighCpu",
                    "instance": "ip-10-0-0-12",
                    "service": "order-processing",
                    "env": "staging",
                    "severity": "critical",
                },
                "annotations": {
                    "summary": "CPU usage above 95%",
                    "description": "Node ip-10-0-0-12 sustained >95% CPU for 10 minutes.",
                },
                "startsAt": earlier.isoformat(),
                "endsAt": "",
                "fingerprint": "ghi789",
            },
        ]
    }


def load_demo_jira_event() -> dict:
    return {
        "webhookEvent": "jira:issue_created",
        "issue": {
            "id": "10001",
            "key": "OPS-1234",
            "self": "https://jira.example/rest/api/3/issue/OPS-1234",
            "fields": {
                "summary": "[WatchOps] frontend-nginx 5xx spike",
                "project": {"key": "OPS"},
                "reporter": {"displayName": "WatchOps Bot"},
                "priority": {"name": "High"},
            },
        },
    }


def load_demo_slack_event() -> dict:
    return {
        "token": "demo-token",
        "team_id": "T0001",
        "api_app_id": "A111",
        "type": "event_callback",
        "event": {
            "type": "message",
            "channel": "COPS",
            "user": "U12345",
            "text": "[WatchOps] CPU spike detected on ip-10-0-0-12 (staging)",
            "ts": "1737573157.000200",
        },
    }


def print_architecture_skeleton() -> None:
    print("=== Architecture Skeleton ===")
    for component in ARCHITECTURE_SKELETON.components:
        print(f"- {component.name}: {component.responsibility}")
    print("\nFlows:")
    for flow in ARCHITECTURE_SKELETON.flows:
        print(f"  {flow.source} -> {flow.target}: {flow.contract}")


def print_prometheus_plans(plans) -> None:
    print("\n=== Remediation Plans ===")
    print(json.dumps([plan.summary for plan in plans], ensure_ascii=False, indent=2))

    print("\n=== Dry-run Recommendations ===")
    for plan in plans:
        for rec in plan.recommendations:
            print(f"- {plan.scenario} -> {rec.action_type}: {rec.description}")

    for plan in plans:
        if plan.diagnostics:
            print(f"\nDiagnostics for {plan.scenario}:")
            for finding in plan.diagnostics:
                print(f"  - {finding.name} [{finding.status}]: {finding.detail}")
        if plan.hypotheses:
            print(f"\nHypotheses for {plan.scenario} (top {len(plan.hypotheses)}):")
            for hyp in plan.hypotheses:
                print(
                    f"  - {hyp.title} (confidence {hyp.confidence:.2f}): {hyp.rationale}"
                )
        if plan.correlations:
            print(f"\nCorrelation Insights for {plan.scenario}:")
            for corr in plan.correlations:
                print(
                    "  - {summary} (confidence {conf:.2f})\n"
                    "    metric: {metric}\n"
                    "    log: {log}".format(
                        summary=corr.summary,
                        conf=corr.confidence,
                        metric=corr.metric_reference,
                        log=corr.log_reference,
                    )
                )
        if plan.post_monitoring:
            print(f"\nPost-Monitoring Tasks for {plan.scenario}:")
            for task in plan.post_monitoring:
                notes = json.dumps(task.notes, ensure_ascii=False)
                print(
                    "  - query={query}, duration={duration}, success={success}\n"
                    "    notes={notes}".format(
                        query=task.metric_query,
                        duration=task.duration,
                        success=task.success_criteria,
                        notes=notes,
                    )
                )
        if plan.verifications:
            print(f"\nVerification Issues for {plan.scenario}:")
            for issue in plan.verifications:
                print(
                    f"  - {issue.level.upper()}: {issue.message}"
                )
        if plan.reports:
            print(f"\nAction Effect Reports for {plan.scenario}:")
            for report in plan.reports:
                recommendations = json.dumps(report.recommendations, ensure_ascii=False)
                metrics = json.dumps(report.metrics, ensure_ascii=False)
                print(
                    "  - normalized={normalized}, summary={summary}\n"
                    "    metrics={metrics}\n"
                    "    next_steps={next_steps}".format(
                        normalized=report.normalized,
                        summary=report.summary,
                        metrics=metrics,
                        next_steps=recommendations,
                    )
                )


def print_results(results) -> None:
    print("\n=== Executing Actions (simulated) ===")
    for result in results:
        detail = f"{result.detail}"
        meta = json.dumps(result.metadata, ensure_ascii=False)
        print(f"- {result.action_type} -> {result.status}: {detail}\n  metadata={meta}")


def print_jira_event(metadata: dict) -> None:
    issue = metadata.get("issue_event")
    print("\n=== Jira Issue Event ===")
    if issue is None:
        print("No issue event captured.")
        return
    issue_dict = asdict(issue)
    print(json.dumps(issue_dict, ensure_ascii=False, indent=2))
    if note := metadata.get("note"):
        print(f"Note: {note}")


def print_slack_event(metadata: dict) -> None:
    event = metadata.get("slack_event")
    print("\n=== Slack Channel Event ===")
    if event is None:
        print("No slack event captured.")
        return
    event_dict = asdict(event)
    print(json.dumps(event_dict, ensure_ascii=False, indent=2))
    if note := metadata.get("note"):
        print(f"Note: {note}")


def main() -> None:
    print_architecture_skeleton()

    config = build_demo_config()
    orchestrator = build_demo_orchestrator(config)
    collectors = build_demo_collectors(orchestrator)

    user_notes = ["30분 전 신규 버전 롤아웃", "APM에서 checkout API 오류율 증가 확인"]

    prometheus_payload = load_demo_prometheus_payload()
    response = collectors.collect(
        "prometheus",
        prometheus_payload,
        execute=False,
        top_k_hypotheses=3,
        user_notes=user_notes,
    )
    print_prometheus_plans(response.plans)

    exec_response = collectors.collect(
        "prometheus",
        prometheus_payload,
        execute=True,
        top_k_hypotheses=3,
        user_notes=user_notes,
    )
    print_results(exec_response.execution_results)

    # Build reports using the orchestrator with the plans and results
    orchestrator.build_reports(response.plans, exec_response.execution_results)
    print_prometheus_plans(response.plans)

    jira_payload = load_demo_jira_event()
    jira_response = collectors.collect("jira_issue_created", jira_payload, execute=False)
    print_jira_event(jira_response.metadata)

    slack_payload = load_demo_slack_event()
    slack_response = collectors.collect("slack_channel_event", slack_payload, execute=False)
    print_slack_event(slack_response.metadata)


if __name__ == "__main__":
    main()
