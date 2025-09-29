"""Slack 관련 Presenter 로직."""

from __future__ import annotations

from typing import Callable, Optional

from ..async_tasks import AsyncExecutor
from ..integrations.slack import SlackIntegration
from ..models import AlertScenario, SlackSettings
from ..views.main_view import IncidentConsoleView
from .state import PresenterState
from .utils import timestamp


class SlackPresenter:
    def __init__(
        self,
        view: IncidentConsoleView,
        state: PresenterState,
        client: Optional[SlackIntegration],
        executor: AsyncExecutor,
        error_handler: Callable[[str, Exception], None],
    ) -> None:
        self._view = view
        self._state = state
        self._client = client or SlackIntegration()
        self._executor = executor
        self._handle_error = error_handler

    # region 이벤트 핸들러
    def handle_test(self) -> None:
        form = self._view.get_slack_form()
        if not form.token:
            self._view.show_warning("Slack Test", "Bot 토큰을 입력하세요.")
            return

        self._view.set_slack_test_busy(True)

        def job() -> dict[str, object]:
            return self._client.test_connection(form.token)

        def done(result: dict[str, object] | None, error: Exception | None) -> None:
            self._view.set_slack_test_busy(False)
            if error:
                self._handle_error("Slack Test", error)
                return

            team = result.get("team")
            domain = result.get("team_domain")
            workspace_match = True
            if form.workspace and domain:
                workspace_match = form.workspace in {domain, f"{domain}.slack.com"}

            info_lines = [f"Team: {team} ({domain})", f"User: {result.get('user')}"]
            if form.workspace and not workspace_match:
                info_lines.append(
                    f"주의: 입력한 워크스페이스 '{form.workspace}'와 Slack 도메인 '{domain}'가 다릅니다."
                )

            self._view.append_feed(f"Slack auth test succeeded for {domain or 'workspace'}")
            self._view.show_information("Slack Test", "\n".join(info_lines))

        self._executor.submit(job, done)

    def handle_save(self) -> None:
        form = self._view.get_slack_form()
        if not form.token:
            self._view.show_warning("Slack", "Bot 토큰은 필수입니다.")
            return

        self._state.slack = form
        self._view.append_feed(
            f"Slack settings saved for {form.workspace or 'workspace'}"
        )
        self._view.show_information("Slack", "설정을 저장했습니다.")

    # endregion

    # region 후속 액션
    def dispatch_alert(
        self,
        scenario: AlertScenario,
        channel: str,
        *,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        token = self._state.slack.token
        workspace = self._state.slack.workspace
        if not token or not channel:
            self._view.show_warning("Slack", "Slack 설정이 완전하지 않습니다.")
            if on_finished:
                on_finished()
            return

        message = self._build_incident_message(scenario)
        self._view.set_trigger_busy(True)

        def job() -> dict[str, object]:
            return self._client.post_message(token, channel, message)

        def done(result: dict[str, object] | None, error: Exception | None) -> None:
            self._view.set_trigger_busy(False)
            if error:
                self._handle_error("Slack Alert", error)
            else:
                self._view.append_feed(
                    f"[{timestamp()}] Slack incident dispatched to {channel} ({workspace or 'workspace'})"
                )
                self._view.show_information("Slack Alert", "Slack에 알림을 발송했습니다.")
            if on_finished:
                on_finished()

        self._executor.submit(job, done)

    # endregion

    # region 내부 함수
    @staticmethod
    def _build_incident_message(scenario: AlertScenario) -> str:
        body_lines = [
            f":rotating_light: {scenario.title}",
            f"Source: {scenario.source}",
            "Top hypotheses:",
        ]
        body_lines.extend(
            f"{idx + 1}. {text}" for idx, text in enumerate(scenario.hypotheses)
        )
        body_lines.append("Recommended next step:")
        body_lines.append(scenario.actions[0])
        return "\n".join(body_lines)

    # endregion
