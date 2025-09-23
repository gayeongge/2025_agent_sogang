"""Workflow for handling CPU spike alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..models import ActionRecommendation, Alert, RemediationPlan
from .base import Workflow


class CpuSpikeWorkflow(Workflow):
    scenario = "cpu_spike"

    KEYWORDS = ("cpu", "processor", "host_cpu_usage")

    def matches(self, alert: Alert) -> bool:
        labels = {k.lower(): v.lower() for k, v in alert.labels.items()}
        alertname = labels.get("alertname", "")
        metric = labels.get("metric", labels.get("metric_name", ""))
        if any(keyword in alertname for keyword in self.KEYWORDS):
            return True
        if any(keyword in metric for keyword in self.KEYWORDS):
            return True
        summary = (alert.annotations.get("summary") or "").lower()
        description = (alert.annotations.get("description") or "").lower()
        return any(keyword in summary or keyword in description for keyword in self.KEYWORDS)

    def build_plan(self, alert: Alert) -> RemediationPlan:
        start_ts = (
            alert.starts_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(alert.starts_at, datetime) else "unknown"
        )
        host = alert.labels.get("instance", alert.labels.get("host", "unknown"))
        service = alert.labels.get("service", alert.labels.get("job", "unknown"))
        env = alert.labels.get("env", "unknown")
        summary = "CPU 사용률이 지속적으로 높습니다. 리소스 쿼터와 워크로드 상태를 점검하세요."
        context: Dict[str, str] = {
            "host": host,
            "service": service,
            "env": env,
            "starts_at": start_ts,
            "alertname": alert.labels.get("alertname", ""),
        }

        recommendations: List[ActionRecommendation] = []

        recommendations.append(
            ActionRecommendation(
                action_type="slack",
                description="운영 채널에 CPU 스파이크 상황 공유",
                payload={
                    "text": (
                        "[WatchOps] CPU 스파이크 감지\n"
                        f"호스트: {context['host']}\n"
                        f"서비스: {context['service']}\n"
                        f"환경: {context['env']}\n"
                        f"시작: {context['starts_at']}\n"
                        f"상세: {alert.annotations.get('description', 'n/a')}"
                    )
                },
            )
        )

        recommendations.append(
            ActionRecommendation(
                action_type="jira",
                description="자동 생성된 장애 이슈 기록",
                payload={
                    "summary": f"[WatchOps] {context['host']} CPU 스파이크",
                    "description": (
                        "자동 생성된 장애 티켓입니다.\n\n"
                        f"Alert: {context['alertname']}\n"
                        f"서비스: {context['service']}\n"
                        f"환경: {context['env']}\n"
                        f"시작 시간: {context['starts_at']}\n"
                        f"상세: {alert.annotations.get('description', 'n/a')}"
                    ),
                    "labels": ["watchops", "cpu", "spike"],
                },
            )
        )

        recommendations.append(
            ActionRecommendation(
                action_type="api",
                description="오토스케일러 API 호출로 CPU 쿨다운 트리거",
                payload={
                    "endpoint": "/autoscaler/cooldown",
                    "service": context["service"],
                    "host": context["host"],
                    "env": context["env"],
                },
            )
        )

        return RemediationPlan(
            scenario=self.scenario,
            summary=summary,
            recommendations=recommendations,
        )
