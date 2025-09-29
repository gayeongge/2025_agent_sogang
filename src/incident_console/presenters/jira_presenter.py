"""Jira 관련 Presenter 로직."""

from __future__ import annotations

from typing import Callable, Optional

from ..async_tasks import AsyncExecutor
from ..integrations.jira import JiraIntegration
from ..models import AlertScenario
from ..views.main_view import IncidentConsoleView
from .state import PresenterState
from .utils import timestamp


class JiraPresenter:
    def __init__(
        self,
        view: IncidentConsoleView,
        state: PresenterState,
        client: Optional[JiraIntegration],
        executor: AsyncExecutor,
        error_handler: Callable[[str, Exception], None],
    ) -> None:
        self._view = view
        self._state = state
        self._client = client or JiraIntegration()
        self._executor = executor
        self._handle_error = error_handler

    # region 이벤트 핸들러
    def handle_test(self) -> None:
        form = self._view.get_jira_form()
        if not all([form.site, form.project, form.email, form.token]):
            self._view.show_warning(
                "Jira Test",
                "Site URL, Project Key, Email, API Token을 모두 입력하세요.",
            )
            return

        self._view.set_jira_test_busy(True)

        def job() -> dict[str, object]:
            return self._client.test_connection(form.site, form.email, form.token, form.project)

        def done(result: dict[str, object] | None, error: Exception | None) -> None:
            self._view.set_jira_test_busy(False)
            if error:
                self._handle_error("Jira Test", error)
                return

            project_name = result.get("name", form.project)
            self._view.append_feed(
                f"Jira project {project_name} accessible for automation"
            )
            self._view.show_information(
                "Jira Test",
                f"프로젝트 {project_name} ({form.project})에 연결했습니다.",
            )

        self._executor.submit(job, done)

    def handle_save(self) -> None:
        form = self._view.get_jira_form()
        if not all([form.site, form.project, form.email, form.token]):
            self._view.show_warning(
                "Jira",
                "Site URL, Project Key, Email, API Token을 모두 입력하세요.",
            )
            return

        self._state.jira = form
        self._view.append_feed(
            f"Jira settings saved for project {form.project}"
        )
        self._view.show_information("Jira", "설정을 저장했습니다.")

    # endregion

    # region 이슈 생성
    def dispatch_issue(self, scenario: AlertScenario) -> None:
        settings = self._state.jira
        if not all([settings.site, settings.project, settings.email, settings.token]):
            self._view.show_warning("Jira", "Jira 설정이 완전하지 않습니다.")
            return

        summary = f"[Auto] {scenario.title}"
        description = self._build_issue_description(scenario)
        self._view.set_trigger_busy(True)

        def job() -> dict[str, object]:
            return self._client.create_incident_issue(
                settings.site,
                settings.email,
                settings.token,
                settings.project,
                summary,
                description,
            )

        def done(result: dict[str, object] | None, error: Exception | None) -> None:
            self._view.set_trigger_busy(False)
            if error:
                self._handle_error("Jira Issue", error)
                return

            key = result.get("key", "<unknown>")
            self._view.append_feed(
                f"[{timestamp()}] Jira issue {key} created for {settings.project}"
            )
            self._view.show_information(
                "Jira Issue",
                f"Jira 티켓 {key}를 생성했습니다.",
            )

        self._executor.submit(job, done)

    @staticmethod
    def _build_issue_description(scenario: AlertScenario) -> str:
        lines = [scenario.description, "", "Hypotheses:"]
        lines.extend(f"- {item}" for item in scenario.hypotheses)
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"- {item}" for item in scenario.evidences)
        lines.append("")
        lines.append("Recommended actions:")
        lines.extend(f"- {item}" for item in scenario.actions)
        return "\n".join(lines)

    # endregion
