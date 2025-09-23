"""Metric/log correlation analyzers."""

from __future__ import annotations

from typing import Iterable, List

from ..models import Alert, CorrelationInsight


class CorrelationAnalyzer:
    """Interface for producing metric/log correlations per alert source."""

    def analyze(self, alert: Alert) -> List[CorrelationInsight]:
        raise NotImplementedError


class PrometheusCorrelationAnalyzer(CorrelationAnalyzer):
    """Heuristic analyzer linking Prometheus metrics to log sources."""

    def __init__(self, metric_templates: Iterable[str] | None = None) -> None:
        self._metric_templates = list(metric_templates or [
            "rate({service}:http_requests_total{{status=~\"5..\"}}[5m])",
            "histogram_quantile(0.99, sum(rate({service}:latency_bucket[5m])) by (le))",
            "rate(node_cpu_seconds_total{{instance=\"{instance}\",mode=\"system\"}}[5m])",
        ])

    def analyze(self, alert: Alert) -> List[CorrelationInsight]:
        service = alert.labels.get("service", alert.labels.get("job", "generic"))
        instance = alert.labels.get("instance", "*")
        source = alert.source or "prometheus"
        insights: List[CorrelationInsight] = []

        for template in self._metric_templates:
            metric_ref = template.format(service=service, instance=instance)
            log_ref = self._guess_log_reference(alert, service=service, instance=instance)
            insights.append(
                CorrelationInsight(
                    source=source,
                    metric_reference=metric_ref,
                    log_reference=log_ref,
                    confidence=0.6,
                    summary="메트릭/로그를 조합하여 원인 파악을 위한 교차 검증을 수행하세요.",
                )
            )
        return insights

    def _guess_log_reference(self, alert: Alert, *, service: str, instance: str) -> str:
        if "nginx" in service.lower():
            return f"/var/log/nginx/{service}.log"
        if "cpu" in alert.labels.get("alertname", "").lower():
            return f"/var/log/syslog?host={instance}"
        return f"/var/log/{service}/application.log"
