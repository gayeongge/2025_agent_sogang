"""알람 시나리오 관련 Presenter 로직."""

from __future__ import annotations

import random
from typing import Callable

from ..models import AlertScenario
from ..views.main_view import IncidentConsoleView
from .jira_presenter import JiraPresenter
from .slack_presenter import SlackPresenter
from .state import PresenterState
from .utils import timestamp


class AlertPresenter:
    def __init__(
        self,
        view: IncidentConsoleView,
        state: PresenterState,
        slack_presenter: SlackPresenter,
        jira_presenter: JiraPresenter,
        feed_callback: Callable[[str], None],
        verify_toggle: Callable[[bool], None],
    ) -> None:
        self._view = view
        self._state = state
        self._slack = slack_presenter
        self._jira = jira_presenter
        self._append_feed = feed_callback
        self._toggle_verify = verify_toggle

    def handle_trigger(self) -> AlertScenario:
        scenario = random.choice(self._state.scenarios)
        self._render_scenario(scenario)
        self._append_feed(
            f"Prometheus Alertmanager fired {scenario.code} → Slack {self._state.slack.channel}"
        )
        self._handle_follow_up_actions(scenario)
        return scenario

    def _render_scenario(self, scenario: AlertScenario) -> None:
        self._view.prepend_alert_entry(f"[{timestamp()}] {scenario.title}")
        self._view.display_hypotheses(
            [f"{idx + 1}. {text}" for idx, text in enumerate(scenario.hypotheses)]
        )
        evidence_lines = [f"• {line}" for line in scenario.evidences]
        evidence_lines.append("• Linked metrics: http_error_rate, cpu_usage")
        self._view.display_evidence(evidence_lines)
        action_lines = [f"{idx + 1}. {step}" for idx, step in enumerate(scenario.actions)]
        action_lines.append("4. Post action: verify Prometheus metrics (http_error_rate, cpu_usage)")
        self._view.display_actions(action_lines)
        self._toggle_verify(True)

    def _handle_follow_up_actions(self, scenario: AlertScenario) -> None:
        def continue_to_jira() -> None:
            self._maybe_dispatch_jira_issue(scenario)

        if scenario.code == "http_5xx_surge" and self._state.slack.token:
            channel = self._state.slack.channel or "#ops-incident"
            if self._view.ask_yes_no(
                "Send Slack Alert?",
                f"Slack 채널 {channel}에 인시던트 알림을 보낼까요?",
            ):
                self._slack.dispatch_alert(
                    scenario,
                    channel,
                    on_finished=continue_to_jira,
                )
                return
        continue_to_jira()

    def _maybe_dispatch_jira_issue(self, scenario: AlertScenario) -> None:
        if scenario.code != "cpu_spike_core" or not self._state.jira.token:
            return

        project = self._state.jira.project or "(unset)"
        if not self._view.ask_yes_no(
            "Create Jira Issue?",
            f"Jira 프로젝트 {project}에 자동 이슈를 생성할까요?",
        ):
            return

        self._jira.dispatch_issue(scenario)
