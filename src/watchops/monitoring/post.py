"""Post-remediation monitoring generators."""

from __future__ import annotations

from typing import Iterable, List

from ..models import Alert, PostMonitoringTask


class PostMonitoringGenerator:
    """Interface for generating post-remediation monitoring tasks."""

    def generate(self, alert: Alert) -> List[PostMonitoringTask]:
        raise NotImplementedError


class PrometheusPostMonitoringGenerator(PostMonitoringGenerator):
    """Creates follow-up Prometheus metric checks after remediation."""

    def __init__(self, default_duration: str = "15m") -> None:
        self._default_duration = default_duration

    def generate(self, alert: Alert) -> List[PostMonitoringTask]:
        service = alert.labels.get("service", alert.labels.get("job", "app"))
        env = alert.labels.get("env", "unknown")
        alertname = alert.labels.get("alertname", "Alert")
        tasks: List[PostMonitoringTask] = []

        # Primary KPI recovery check
        kpi_query = self._build_recovery_query(alert, service)
        tasks.append(
            PostMonitoringTask(
                metric_query=kpi_query,
                duration=self._default_duration,
                success_criteria="해당 지표가 SLA 임계치 이하로 유지",
                notes={
                    "alertname": alertname,
                    "service": service,
                    "env": env,
                },
            )
        )

        # Error budget or latency guardrail
        latency_query = f"histogram_quantile(0.95, sum(rate({service}:latency_bucket[5m])) by (le))"
        tasks.append(
            PostMonitoringTask(
                metric_query=latency_query,
                duration="30m",
                success_criteria="p95 latency가 평소 대비 10% 이내",
                notes={"service": service, "env": env},
            )
        )

        return tasks

    def _build_recovery_query(self, alert: Alert, service: str) -> str:
        if "cpu" in (alert.labels.get("alertname", "") or "").lower():
            instance = alert.labels.get("instance", "*")
            return (
                "1 - avg(rate(node_cpu_seconds_total{instance=\"%s\",mode=\"idle\"}[5m]))" % instance
            )
        if "5xx" in alert.labels.get("alertname", ""):  # HTTP errors
            return f"rate({service}:http_requests_total{{status=~\"5..\"}}[5m])"
        return f"avg_over_time({service}:availability[5m])"
