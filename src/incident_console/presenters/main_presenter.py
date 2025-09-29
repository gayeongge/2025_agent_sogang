"""Incident console 메인 Presenter."""

from __future__ import annotations

from typing import Optional

from ..async_tasks import AsyncExecutor
from ..integrations.jira import JiraIntegration
from ..integrations.prometheus import PrometheusClient
from ..integrations.slack import SlackIntegration
from ..views.main_view import IncidentConsoleView
from .alert_presenter import AlertPresenter
from .jira_presenter import JiraPresenter
from .prometheus_presenter import PrometheusPresenter
from .slack_presenter import SlackPresenter
from .state import PresenterState
from .utils import timestamp


class IncidentConsolePresenter:
    def __init__(
        self,
        view: IncidentConsoleView,
        *,
        slack_client: Optional[SlackIntegration] = None,
        jira_client: Optional[JiraIntegration] = None,
        prom_client: Optional[PrometheusClient] = None,
        executor: Optional[AsyncExecutor] = None,
    ) -> None:
        self._view = view
        self._executor = executor or AsyncExecutor()
        self._state = PresenterState()

        self._slack = SlackPresenter(
            view,
            self._state,
            slack_client,
            self._executor,
            self._handle_error,
        )
        self._jira = JiraPresenter(
            view,
            self._state,
            jira_client,
            self._executor,
            self._handle_error,
        )
        self._prometheus = PrometheusPresenter(
            view,
            self._state,
            prom_client,
            self._executor,
            self._handle_error,
        )
        self._alerts = AlertPresenter(
            view,
            self._state,
            self._slack,
            self._jira,
            view.append_feed,
            view.set_verify_enabled,
        )

        self._connect_signals()

    # region Signal 연결
    def _connect_signals(self) -> None:
        self._view.trigger_alert_requested.connect(self._on_trigger_alert)
        self._view.verify_recovery_requested.connect(self._prometheus.verify_recovery)

        self._view.slack_test_requested.connect(self._slack.handle_test)
        self._view.slack_save_requested.connect(self._slack.handle_save)

        self._view.jira_test_requested.connect(self._jira.handle_test)
        self._view.jira_save_requested.connect(self._jira.handle_save)

        self._view.prometheus_test_requested.connect(self._prometheus.handle_test)
        self._view.prometheus_save_requested.connect(self._prometheus.handle_save)

    # endregion

    def _on_trigger_alert(self) -> None:
        self._alerts.handle_trigger()

    def _handle_error(self, title: str, error: Exception) -> None:
        message = str(error) or error.__class__.__name__
        self._view.show_error(title, message)
        self._view.append_feed(f"[{timestamp()}] ERROR {title}: {message}")
