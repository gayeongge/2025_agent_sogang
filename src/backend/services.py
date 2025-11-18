"""Business logic used by the FastAPI backend."""

from __future__ import annotations

import random
from dataclasses import asdict
from typing import Callable, Dict, List, Optional, Tuple

from src.backend.state import (
    STATE,
    STATE_LOCK,
    ActionExecution,
    ActionExecutionResult,
    IncidentReport,
    MetricSample,
    make_sample,
)
from src.incident_console.config import set_openai_api_key
from src.incident_console.integrations.prometheus import PrometheusClient
from src.incident_console.integrations.slack import SlackIntegration
from src.incident_console.models import (
    AISettings,
    AlertScenario,
    PrometheusSettings,
    SlackSettings,
)
from src.incident_console.utils import parse_threshold, timestamp


class SlackService:
    def __init__(self, integration: Optional[SlackIntegration] = None) -> None:
        self._integration = integration or SlackIntegration()

    def test(self, token: str) -> Dict[str, object]:
        return self._integration.test_connection(token)

    def save(self, settings: SlackSettings) -> str:
        with STATE_LOCK:
            STATE.slack = settings
            message = f"Slack settings saved for {settings.workspace or 'workspace'}"
            STATE.append_feed(_feed_line(message))
        return message

    def dispatch(
        self,
        scenario: AlertScenario,
        channel: Optional[str] = None,
        report_body: Optional[str] = None,
    ) -> Dict[str, object]:
        with STATE_LOCK:
            preferences_enabled = STATE.preferences.slack
            settings = STATE.slack
            token = settings.token
            workspace = settings.workspace or "workspace"
            channel_to_use = channel or settings.channel or "#ops-incident"

        if not preferences_enabled:
            raise ValueError("Slack auto notifications are disabled. Enable the checkbox to send messages.")
        if not token:
            raise ValueError("Slack token is not configured")

        message = self._build_message(scenario, report_body)
        result = self._integration.post_message(token, channel_to_use, message)
        with STATE_LOCK:
            STATE.append_feed(
                _feed_line(
                    f"Slack incident dispatched to {channel_to_use} ({workspace})"
                )
            )
        return result

    @staticmethod
    def _build_message(scenario: AlertScenario, report_body: Optional[str]) -> str:
        if report_body:
            return report_body

        lines = [
            f":rotating_light: {scenario.title}",
            f"Source: {scenario.source}",
            "Top hypotheses:",
        ]
        lines.extend(f"{idx + 1}. {item}" for idx, item in enumerate(scenario.hypotheses))
        lines.append("Recommended next step:")
        lines.append(scenario.actions[0])
        return "\n".join(lines)


class PrometheusService:
    def __init__(self, client: Optional[PrometheusClient] = None) -> None:
        self._client = client or PrometheusClient()

    def test(self, settings: PrometheusSettings) -> Dict[str, float]:
        http_val = self._client.instant_value(settings.url, settings.http_query)
        cpu_val = self._client.instant_value(settings.url, settings.cpu_query)
        return {"http": http_val, "cpu": cpu_val}

    def save(self, settings: PrometheusSettings) -> str:
        parse_threshold(settings.http_threshold, default=0.05)
        parse_threshold(settings.cpu_threshold, default=0.80)
        with STATE_LOCK:
            STATE.prometheus = settings
            message = f"Prometheus settings saved for {settings.url or '(unset)'}"
            STATE.append_feed(_feed_line(message))
        return message

    def fetch_metrics(self) -> Tuple[float, float, float, float]:
        with STATE_LOCK:
            settings = STATE.prometheus
            url = settings.url
            http_query = settings.http_query
            cpu_query = settings.cpu_query
            http_threshold = parse_threshold(settings.http_threshold, default=0.05)
            cpu_threshold = parse_threshold(settings.cpu_threshold, default=0.80)

        if not url:
            raise ValueError("Prometheus base URL is not configured")
        if not http_query or not cpu_query:
            raise ValueError("Prometheus HTTP and CPU queries must be configured")

        http_val = self._client.instant_value(url, http_query)
        cpu_val = self._client.instant_value(url, cpu_query)
        return http_val, cpu_val, http_threshold, cpu_threshold

    def verify(self) -> Dict[str, object]:
        http_val, cpu_val, http_threshold, cpu_threshold = self.fetch_metrics()
        http_ok = http_val <= http_threshold
        cpu_ok = cpu_val <= cpu_threshold

        with STATE_LOCK:
            STATE.append_feed(
                _feed_line(
                    (
                        f"Verification http={http_val:.4f} (threshold {http_threshold:.4f}), "
                        f"cpu={cpu_val:.4f} (threshold {cpu_threshold:.4f})"
                    )
                )
            )
            verify_status = "recovered" if http_ok and cpu_ok else "pending"

        return {
            "http": http_val,
            "cpu": cpu_val,
            "http_threshold": http_threshold,
            "cpu_threshold": cpu_threshold,
            "status": verify_status,
        }


class AlertService:
    def trigger(self) -> Dict[str, object]:
        with STATE_LOCK:
            scenario = random.choice(STATE.scenarios)
            slack_channel = STATE.slack.channel or "#ops-incident"

        alert_label = f"[{timestamp()}] {scenario.title}"
        prom_feed = (
            f"Prometheus Alertmanager fired {scenario.code} -> Slack {slack_channel}"
        )

        with STATE_LOCK:
            STATE.record_alert(alert_label, scenario)
            STATE.append_feed(_feed_line(prom_feed))

        return {
            "scenario": serialize_scenario(scenario),
            "alert_entry": alert_label,
            "feed_message": prom_feed,
            "hypotheses": _enumerate_lines(scenario.hypotheses),
            "evidence": [f"- {line}" for line in scenario.evidences]
            + ["- Linked metrics: http_error_rate, cpu_usage"],
            "actions": _enumerate_lines(
                scenario.actions
                + ["Post action: verify Prometheus metrics (http_error_rate, cpu_usage)"]
            ),
        }

    def get_scenario_by_code(self, code: str) -> Optional[AlertScenario]:
        with STATE_LOCK:
            for scenario in STATE.scenarios:
                if scenario.code == code:
                    return scenario
        return None

    def record_incident(
        self,
        scenario: AlertScenario,
        report: IncidentReport,
        feed_message: str,
    ) -> None:
        label = f"[{timestamp()}] {scenario.title}"
        with STATE_LOCK:
            STATE.record_alert(label, scenario)
            STATE.append_feed(_feed_line(feed_message))
            STATE.last_report = report

    def get_state(self) -> Dict[str, object]:
        with STATE_LOCK:
            state_copy = {
                "slack": asdict(STATE.slack),
                "prometheus": asdict(STATE.prometheus),
                "ai": {
                    "configured": bool(STATE.ai.api_key),
                },
                "feed": list(STATE.feed),
                "alert_history": list(STATE.alert_history),
                "last_alert": serialize_scenario(STATE.last_alert) if STATE.last_alert else None,
                "monitor": {
                    "samples": [serialize_sample(sample) for sample in STATE.monitor_samples],
                    "incident_active": bool(STATE.active_incidents),
                    "active_incidents": sorted(STATE.active_incidents),
                },
                "preferences": asdict(STATE.preferences),
                "last_report": serialize_report(STATE.last_report),
                "pending_reports": [
                    serialize_report(report) for report in STATE.pending_reports
                ],
                "action_executions": [
                    serialize_action_execution(execution)
                    for execution in STATE.action_executions
                ],
            }
        return state_copy

    def require_last_alert(self) -> AlertScenario:
        with STATE_LOCK:
            if STATE.last_alert is None:
                raise ValueError("No alert has been triggered yet")
            return STATE.last_alert


class AIService:
    def __init__(self, *, on_change: Optional[Callable[[], None]] = None) -> None:
        self._on_change = on_change

    def save(self, settings: AISettings) -> str:
        updated_value = (settings.api_key or "").strip()
        with STATE_LOCK:
            STATE.ai.api_key = updated_value
            message = (
                "OpenAI API key configured."
                if updated_value
                else "OpenAI API key cleared."
            )
            STATE.append_feed(_feed_line(message))
        set_openai_api_key(updated_value)
        if self._on_change:
            self._on_change()
        return message


def serialize_scenario(scenario: Optional[AlertScenario]) -> Optional[Dict[str, object]]:
    if scenario is None:
        return None
    return {
        "code": scenario.code,
        "title": scenario.title,
        "source": scenario.source,
        "description": scenario.description,
        "hypotheses": list(scenario.hypotheses),
        "evidences": list(scenario.evidences),
        "actions": list(scenario.actions),
    }


def serialize_sample(sample: MetricSample) -> Dict[str, object]:
    return {
        "timestamp": sample.timestamp,
        "http": sample.http,
        "http_threshold": sample.http_threshold,
        "http_exceeded": sample.http_exceeded,
        "cpu": sample.cpu,
        "cpu_threshold": sample.cpu_threshold,
        "cpu_exceeded": sample.cpu_exceeded,
    }


def serialize_report(report: Optional[IncidentReport]) -> Optional[Dict[str, object]]:
    if report is None:
        return None

    return {
        "id": report.id,
        "scenario_code": report.scenario_code,
        "title": report.title,
        "created_at": report.created_at,
        "report_body": report.report_body,
        "metrics": serialize_sample(report.metrics),
        "summary": report.summary,
        "root_cause": report.root_cause,
        "impact": report.impact,
        "action_items": list(report.action_items),
        "follow_up": list(report.follow_up),
        "recipients_sent": list(report.recipients_sent),
        "recipients_missing": list(report.recipients_missing),
    }


def serialize_action_result(result: ActionExecutionResult) -> Dict[str, object]:
    return {
        "action": result.action,
        "status": result.status,
        "detail": result.detail,
        "executed_at": result.executed_at,
    }


def serialize_action_execution(
    execution: Optional[ActionExecution],
) -> Optional[Dict[str, object]]:
    if execution is None:
        return None
    return {
        "id": execution.id,
        "report_id": execution.report_id,
        "scenario_code": execution.scenario_code,
        "scenario_title": execution.scenario_title,
        "created_at": execution.created_at,
        "actions": list(execution.actions),
        "status": execution.status,
        "executed_at": execution.executed_at,
        "results": [serialize_action_result(result) for result in execution.results],
    }


def _enumerate_lines(lines: List[str]) -> List[str]:
    return [f"{idx + 1}. {line}" for idx, line in enumerate(lines)]


def _feed_line(message: str) -> str:
    return f"[{timestamp()}] {message}"
