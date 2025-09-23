"""Workflow for handling Nginx/Web 5xx error spikes."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from ..models import ActionRecommendation, Alert, RemediationPlan
from .base import Workflow


class Nginx5xxWorkflow(Workflow):
    scenario = "nginx_high_5xx_rate"

    def matches(self, alert: Alert) -> bool:
        service = alert.labels.get("service") or alert.labels.get("job")
        if service and "nginx" in service.lower():
            return True
        alert_name = alert.labels.get("alertname", "").lower()
        annotation_summary = (alert.annotations.get("summary") or "").lower()
        return "5xx" in alert_name or "5xx" in annotation_summary

    def build_plan(self, alert: Alert) -> RemediationPlan:
        start_ts = (
            alert.starts_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(alert.starts_at, datetime) else "unknown"
        )
        summary = (
            "Nginx 서비스에서 5xx 오류 비율이 급증했습니다. 로그 분석과 다운스트림 영향 확인이 필요합니다."
        )
        context: Dict[str, str] = {
            "service": alert.labels.get("service", alert.labels.get("job", "unknown")),
            "env": alert.labels.get("env", "unknown"),
            "starts_at": start_ts,
            "alertname": alert.labels.get("alertname", ""),
        }

        slack_rec = ActionRecommendation(
            action_type="slack",
            description="운영 채널에 알람 상황 공유",
            payload={
                "text": (
                    "[WatchOps] Nginx 5xx 오류 급증 감지\n"
                    f"서비스: {context['service']}\n"
                    f"환경: {context['env']}\n"
                    f"시작: {context['starts_at']}\n"
                    f"상세: {alert.annotations.get('description', 'n/a')}"
                )
            },
        )

        jira_rec = ActionRecommendation(
            action_type="jira",
            description="Jira 인시던트 티켓 생성",
            payload={
                "summary": f"[WatchOps] {context['service']} 5xx 오류 급증",
                "description": (
                    "자동 생성된 인시던트입니다.\n\n"
                    f"Alert: {context['alertname']}\n"
                    f"시작 시간: {context['starts_at']}\n"
                    f"환경: {context['env']}\n"
                    f"알람 세부정보: {alert.annotations.get('description', 'n/a')}"
                ),
                "labels": ["watchops", "nginx", "5xx"],
            },
        )

        mcp_rec = ActionRecommendation(
            action_type="mcp",
            description="MCP를 통해 Nginx upstream 재시작 명령 전송",
            payload={
                "command": "service.restart",
                "parameters": {
                    "service": context["service"],
                    "env": context["env"],
                    "scope": "upstream",
                },
            },
        )

        return RemediationPlan(
            scenario=self.scenario,
            summary=summary,
            recommendations=[slack_rec, jira_rec, mcp_rec],
        )
