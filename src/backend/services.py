"""Business logic used by the FastAPI backend."""

from __future__ import annotations

import logging
import os
import random
import re
import smtplib
from dataclasses import asdict
from email.message import EmailMessage
from typing import Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from src.backend.state import (
    STATE,
    STATE_LOCK,
    ActionExecution,
    ActionExecutionResult,
    IncidentReport,
    MetricSample,
    EmailRecipient,
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
from src.incident_console.utils import parse_threshold, timestamp, utcnow_iso


logger = logging.getLogger("incident.email")


class SlackService:
    def __init__(self, integration: Optional[SlackIntegration] = None) -> None:
        self._integration = integration or SlackIntegration()

    def test(self, token: str) -> Dict[str, object]:
        return self._integration.test_connection(token)

    def save(self, settings: SlackSettings) -> str:
        with STATE_LOCK:
            STATE.slack = settings
            message = f"Slack 설정을 저장했습니다 ({settings.workspace or 'workspace'})"
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
            message = f"Prometheus 설정을 저장했습니다 ({settings.url or '(unset)'})"
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
                "email_recipients": [
                    serialize_email_recipient(rec)
                    for rec in STATE.email_recipients
                ],
                "feed": list(STATE.feed),
                "alert_history": list(STATE.alert_history),
                "last_alert": serialize_scenario(STATE.last_alert) if STATE.last_alert else None,
                "scenarios": [
                    {
                        "code": scenario.code,
                        "title": scenario.title,
                        "source": scenario.source,
                        "description": scenario.description,
                    }
                    for scenario in STATE.scenarios
                ],
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
                "OpenAI API Key가 설정되었습니다."
                if updated_value
                else "OpenAI API Key가 제거되었습니다."
            )
            STATE.append_feed(_feed_line(message))
        set_openai_api_key(updated_value)
        if self._on_change:
            self._on_change()
        return message


class EmailRegistryService:
    """In-memory registry for email recipients used for MCP notifications."""

    _EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)

    def list_recipients(self) -> List[EmailRecipient]:
        with STATE_LOCK:
            return list(STATE.email_recipients)

    def add_recipient(self, email: str) -> EmailRecipient:
        normalized = self._normalize(email)
        if not normalized:
            raise ValueError("유효한 이메일 주소를 입력하세요.")

        with STATE_LOCK:
            if any(rec.email.lower() == normalized for rec in STATE.email_recipients):
                raise ValueError("이미 등록된 이메일입니다.")

            recipient = EmailRecipient(
                id=str(uuid4()),
                email=normalized,
                created_at=utcnow_iso(),
            )
            STATE.email_recipients.append(recipient)
            STATE.append_feed(_feed_line(f"Email recipient added: {normalized}"))
            return recipient

    def remove_recipient(self, recipient_id: str) -> None:
        if not recipient_id:
            raise ValueError("삭제할 대상을 선택하세요.")

        with STATE_LOCK:
            for index, recipient in enumerate(STATE.email_recipients):
                if recipient.id == recipient_id:
                    removed = STATE.email_recipients.pop(index)
                    STATE.append_feed(_feed_line(f"Email recipient removed: {removed.email}"))
                    return

        raise ValueError("대상을 찾을 수 없습니다.")

    def _normalize(self, email: str) -> str:
        value = (email or "").strip().lower()
        if value and self._EMAIL_PATTERN.match(value):
            return value
        return ""


class EmailDeliveryService:
    """Lightweight SMTP sender for action-status notifications."""

    def __init__(self, registry: Optional[EmailRegistryService] = None) -> None:
        self._registry = registry or EmailRegistryService()

    def send_action_status(self, execution: ActionExecution, status: str) -> None:
        recipients = self._registry.list_recipients()
        if not recipients:
            logger.info("Skipping email notification (no recipients configured).")
            return

        addresses = [recipient.email for recipient in recipients if recipient.email]
        if not addresses:
            logger.info("Skipping email notification (recipients invalid).")
            return

        status_label = status.capitalize()
        subject = f"[Incident] {execution.scenario_title} - {status_label}"
        body = self._build_action_email_body(execution, status_label)
        if self._deliver(addresses, subject, body):
            with STATE_LOCK:
                STATE.append_feed(
                    _feed_line(
                        f"Action status emailed to {len(addresses)} recipient(s)"
                    )
                )

    def _deliver(self, recipients: List[str], subject: str, body: str) -> bool:
        settings = self._smtp_settings()
        if not settings["host"]:
            logger.info("Email SMTP host missing; notification skipped.")
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings["sender"]
        message["To"] = ", ".join(recipients)
        message.set_content(body)

        try:
            with smtplib.SMTP(settings["host"], settings["port"], timeout=10) as server:
                if settings["use_tls"]:
                    server.starttls()
                if settings["username"]:
                    server.login(settings["username"], settings["password"])
                server.send_message(message)
            return True
        except Exception:
            logger.exception("Failed to send email notification.")
            return False

    def _smtp_settings(self) -> Dict[str, object]:
        host = os.getenv("INCIDENT_EMAIL_SMTP_HOST", "").strip()
        port = int(os.getenv("INCIDENT_EMAIL_SMTP_PORT", "587") or "587")
        username = os.getenv("INCIDENT_EMAIL_SMTP_USER", "").strip()
        password = os.getenv("INCIDENT_EMAIL_SMTP_PASSWORD", "")
        sender = os.getenv("INCIDENT_EMAIL_FROM", username or "incident-console@example.com").strip()
        use_tls = os.getenv("INCIDENT_EMAIL_SMTP_TLS", "1") != "0"
        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "sender": sender,
            "use_tls": use_tls,
        }

    def _build_action_email_body(
        self,
        execution: ActionExecution,
        status_label: str,
    ) -> str:
        lines = [
            "Incident Action Update",
            "",
            f"Scenario: {execution.scenario_title} ({execution.scenario_code})",
            f"Status: {status_label}",
            f"Requested: {execution.created_at}",
        ]
        if execution.executed_at:
            lines.append(f"Updated: {execution.executed_at}")
        lines.append("")
        lines.append("Actions:")
        for action in execution.actions:
            lines.append(f"- {action}")

        if execution.results:
            lines.append("")
            lines.append("Results:")
            for result in execution.results:
                detail = f" ({result.detail})" if result.detail else ""
                lines.append(f"- {result.action}: {result.status}{detail}")

        lines.append("")
        lines.append("Sent via Incident Response Console MCP notifications.")
        return "\n".join(lines)


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
        "node": sample.node,
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


def serialize_email_recipient(recipient: EmailRecipient) -> Dict[str, object]:
    return {
        "id": recipient.id,
        "email": recipient.email,
        "created_at": recipient.created_at,
    }


def _enumerate_lines(lines: List[str]) -> List[str]:
    return [f"{idx + 1}. {line}" for idx, line in enumerate(lines)]


def _feed_line(message: str) -> str:
    return f"[{timestamp()}] {message}"
