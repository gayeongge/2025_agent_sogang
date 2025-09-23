"""Workflow for handling general HTTP error rate spikes."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from ..models import ActionRecommendation, Alert, RemediationPlan
from .base import Workflow


class HttpErrorRateWorkflow(Workflow):
    scenario = "http_error_rate_threshold"

    ERROR_KEYWORDS = ("http_error_rate", "5xx", "http 5xx", "http-errors")

    def matches(self, alert: Alert) -> bool:
        labels = {k.lower(): v.lower() for k, v in alert.labels.items()}
        alertname = labels.get("alertname", "")
        metric = labels.get("metric", labels.get("metric_name", ""))
        if any(keyword in alertname for keyword in self.ERROR_KEYWORDS):
            return True
        if any(keyword in metric for keyword in self.ERROR_KEYWORDS):
            return True
        summary = (alert.annotations.get("summary") or "").lower()
        description = (alert.annotations.get("description") or "").lower()
        return any(keyword in summary or keyword in description for keyword in self.ERROR_KEYWORDS)

    def build_plan(self, alert: Alert) -> RemediationPlan:
        start_ts = (
            alert.starts_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(alert.starts_at, datetime) else "unknown"
        )
        service = alert.labels.get("service", alert.labels.get("job", "unknown"))
        summary = "HTTP 오류율이 임계치를 초과했습니다. 라우팅 및 백엔드 상태 점검이 필요합니다."
        context: Dict[str, str] = {
            "service": service,
            "env": alert.labels.get("env", "unknown"),
            "starts_at": start_ts,
            "alertname": alert.labels.get("alertname", ""),
        }

        slack_rec = ActionRecommendation(
            action_type="slack",
            description="운영 채널에 HTTP 오류율 경보 공유",
            payload={
                "text": (
                    "[WatchOps] HTTP 오류율 임계치 초과 감지\n"
                    f"서비스: {context['service']}\n"
                    f"환경: {context['env']}\n"
                    f"시작: {context['starts_at']}\n"
                    f"상세: {alert.annotations.get('description', 'n/a')}"
                )
            },
        )

        return RemediationPlan(
            scenario=self.scenario,
            summary=summary,
            recommendations=[slack_rec],
        )
