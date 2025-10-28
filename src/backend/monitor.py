"""Background Prometheus monitor that auto-dispatches incident reports."""

from __future__ import annotations

import threading
import time
import uuid
from typing import List, Tuple

from src.backend.actions import ActionExecutionService
from src.backend.analysis import generate_incident_analysis
from src.backend.services import AlertService, JiraService, PrometheusService, SlackService
from src.backend.state import STATE, STATE_LOCK, IncidentReport, MetricSample, make_sample
from src.incident_console.errors import IntegrationError
from src.incident_console.models import AlertScenario
from src.incident_console.utils import timestamp

_WINDOW_SIZE = 5
_POLL_INTERVAL_SECONDS = 5.0


class PrometheusMonitor:
    """Continuously polls Prometheus and notifies when thresholds are breached."""

    def __init__(
        self,
        prom_service: PrometheusService,
        alert_service: AlertService,
        slack_service: SlackService,
        jira_service: JiraService,
        action_service: ActionExecutionService,
    ) -> None:
        self._prom_service = prom_service
        self._alert_service = alert_service
        self._slack_service = slack_service
        self._jira_service = jira_service
        self._action_service = action_service
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(_POLL_INTERVAL_SECONDS)
            try:
                http_val, cpu_val, http_threshold, cpu_threshold = self._prom_service.fetch_metrics()
            except ValueError:
                # Prometheus settings are incomplete; skip quietly.
                continue
            except IntegrationError as exc:
                self._record_monitor_failure(f"Prometheus query failed: {exc}")
                continue

            sample = make_sample(http_val, http_threshold, cpu_val, cpu_threshold)
            with STATE_LOCK:
                STATE.monitor_samples.append(sample)
                samples_snapshot = list(STATE.monitor_samples)
                incident_active = STATE.incident_active

            if len(samples_snapshot) < _WINDOW_SIZE:
                continue

            exceeded = any(s.any_exceeded for s in samples_snapshot)
            if exceeded and not incident_active:
                self._handle_incident(samples_snapshot[-1])
                with STATE_LOCK:
                    STATE.incident_active = True
            elif not exceeded and incident_active:
                with STATE_LOCK:
                    STATE.incident_active = False

    def _handle_incident(self, sample: MetricSample) -> None:
        scenario = self._select_scenario(sample)
        if scenario is None:
            self._record_monitor_failure("No scenarios available to build incident report")
            return

        analysis = generate_incident_analysis(scenario, sample)
        report_body = analysis["report_text"]
        report = IncidentReport(
            id=str(uuid.uuid4()),
            scenario_code=scenario.code,
            title=scenario.title,
            created_at=sample.timestamp,
            report_body=report_body,
            metrics=sample,
            summary=analysis.get("summary", ""),
            root_cause=analysis.get("root_cause", ""),
            impact=analysis.get("impact", ""),
            action_items=list(analysis.get("action_plan", [])) or list(scenario.actions),
            follow_up=list(analysis.get("follow_up", [])),
        )

        self._action_service.queue_from_report(report)

        recipients_sent, recipients_missing = self._deliver_report(scenario, report_body)
        report.recipients_sent = recipients_sent
        report.recipients_missing = recipients_missing

        feed_message = self._build_feed_message(sample, recipients_sent, recipients_missing)
        self._alert_service.record_incident(scenario, report, feed_message)

        with STATE_LOCK:
            if recipients_missing:
                STATE.pending_reports.append(report)
                # cap queue size to avoid unbounded growth
                if len(STATE.pending_reports) > 20:
                    STATE.pending_reports.pop(0)

    def _deliver_report(
        self,
        scenario: AlertScenario,
        report_body: str,
    ) -> Tuple[List[str], List[str]]:
        recipients_sent: List[str] = []
        recipients_missing: List[str] = []

        with STATE_LOCK:
            preferences = STATE.preferences
            slack_settings = STATE.slack
            jira_settings = STATE.jira

        if preferences.slack:
            if slack_settings.token:
                try:
                    self._slack_service.dispatch(scenario, report_body=report_body)
                    recipients_sent.append("slack")
                except (IntegrationError, ValueError) as exc:
                    recipients_missing.append(f"Slack 전송 실패: {exc}")
            else:
                recipients_missing.append("Slack 설정이 필요합니다")

        if preferences.jira:
            if all([jira_settings.site, jira_settings.project, jira_settings.email, jira_settings.token]):
                try:
                    self._jira_service.create_issue(scenario, report_body=report_body)
                    recipients_sent.append("jira")
                except (IntegrationError, ValueError) as exc:
                    recipients_missing.append(f"Jira 전송 실패: {exc}")
            else:
                recipients_missing.append("Jira 설정이 필요합니다")

        return recipients_sent, recipients_missing

    def _select_scenario(self, sample: MetricSample) -> AlertScenario | None:
        primary_code = "http_5xx_surge"
        secondary_code = "cpu_spike_core"

        http_delta = sample.http - sample.http_threshold
        cpu_delta = sample.cpu - sample.cpu_threshold

        if sample.http_exceeded and not sample.cpu_exceeded:
            code = primary_code
        elif sample.cpu_exceeded and not sample.http_exceeded:
            code = secondary_code
        elif sample.http_exceeded and sample.cpu_exceeded:
            code = primary_code if http_delta >= cpu_delta else secondary_code
        else:
            code = primary_code if http_delta >= cpu_delta else secondary_code

        scenario = self._alert_service.get_scenario_by_code(code)
        if scenario is None and STATE.scenarios:
            scenario = STATE.scenarios[0]
        return scenario

    @staticmethod
    def _build_feed_message(
        sample: MetricSample,
        recipients_sent: List[str],
        recipients_missing: List[str],
    ) -> str:
        delivered = ", ".join(recipients_sent) if recipients_sent else "none"
        missing = ", ".join(recipients_missing) if recipients_missing else "none"
        return (
            "Auto-detected anomaly (http={http:.4f}/{http_thr:.4f}, "
            "cpu={cpu:.4f}/{cpu_thr:.4f}) -> delivered=[{sent}] missing=[{missing}]"
        ).format(
            http=sample.http,
            http_thr=sample.http_threshold,
            cpu=sample.cpu,
            cpu_thr=sample.cpu_threshold,
            sent=delivered,
            missing=missing,
        )

    def _record_monitor_failure(self, message: str) -> None:
        with STATE_LOCK:
            STATE.append_feed(f"[{timestamp()}] {message}")
