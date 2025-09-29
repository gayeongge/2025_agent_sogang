"""Prometheus 관련 Presenter 로직."""

from __future__ import annotations

from typing import Callable, Optional

from ..async_tasks import AsyncExecutor
from ..integrations.prometheus import PrometheusClient
from ..views.main_view import IncidentConsoleView
from .state import PresenterState
from .utils import parse_threshold, timestamp


class PrometheusPresenter:
    def __init__(
        self,
        view: IncidentConsoleView,
        state: PresenterState,
        client: Optional[PrometheusClient],
        executor: AsyncExecutor,
        error_handler: Callable[[str, Exception], None],
    ) -> None:
        self._view = view
        self._state = state
        self._client = client or PrometheusClient()
        self._executor = executor
        self._handle_error = error_handler

    # region 이벤트 핸들러
    def handle_test(self) -> None:
        form = self._view.get_prometheus_form()
        if not all([form.url, form.http_query, form.cpu_query]):
            self._view.show_warning(
                "Prometheus Test",
                "Base URL과 두 가지 쿼리를 모두 입력하세요.",
            )
            return

        self._view.set_prom_test_busy(True)

        def job() -> dict[str, float]:
            http_val = self._client.instant_value(form.url, form.http_query)
            cpu_val = self._client.instant_value(form.url, form.cpu_query)
            return {"http": http_val, "cpu": cpu_val}

        def done(result: dict[str, float] | None, error: Exception | None) -> None:
            self._view.set_prom_test_busy(False)
            if error:
                self._handle_error("Prometheus Test", error)
                return

            self._view.append_feed(
                f"Prometheus test http={result['http']:.4f}, cpu={result['cpu']:.4f}"
            )
            self._view.show_information(
                "Prometheus Test",
                (
                    f"HTTP query value: {result['http']:.4f}\n"
                    f"CPU query value: {result['cpu']:.4f}"
                ),
            )

        self._executor.submit(job, done)

    def handle_save(self) -> None:
        form = self._view.get_prometheus_form()
        if not all([form.url, form.http_query, form.cpu_query]):
            self._view.show_warning(
                "Prometheus",
                "Base URL과 두 가지 쿼리를 모두 입력하세요.",
            )
            return

        try:
            parse_threshold(form.http_threshold, default=0.05)
            parse_threshold(form.cpu_threshold, default=0.80)
        except ValueError as exc:
            self._view.show_warning("Prometheus", f"임계값 오류: {exc}")
            return

        self._state.prometheus = form
        self._view.append_feed(f"Prometheus settings saved for {form.url}")
        self._view.show_information("Prometheus", "설정을 저장했습니다.")

    # endregion

    # region 검증 흐름
    def verify_recovery(self) -> None:
        settings = self._state.prometheus
        if not settings.url:
            self._view.show_warning("Prometheus", "Prometheus 설정을 먼저 저장하세요.")
            return
        if not settings.http_query or not settings.cpu_query:
            self._view.show_warning("Prometheus", "HTTP/CPU 쿼리를 모두 입력해야 합니다.")
            return

        try:
            http_threshold = parse_threshold(settings.http_threshold, default=0.05)
            cpu_threshold = parse_threshold(settings.cpu_threshold, default=0.80)
        except ValueError as exc:
            self._view.show_warning("Prometheus", f"임계값 오류: {exc}")
            return

        self._view.set_verify_busy(True)

        def job() -> dict[str, float]:
            http_val = self._client.instant_value(settings.url, settings.http_query)
            cpu_val = self._client.instant_value(settings.url, settings.cpu_query)
            return {
                "http": http_val,
                "cpu": cpu_val,
                "http_threshold": http_threshold,
                "cpu_threshold": cpu_threshold,
            }

        def done(result: dict[str, float] | None, error: Exception | None) -> None:
            self._view.set_verify_busy(False)
            if error:
                self._handle_error("Recovery Verification", error)
                return

            http_val = result["http"]
            cpu_val = result["cpu"]
            http_ok = http_val <= result["http_threshold"]
            cpu_ok = cpu_val <= result["cpu_threshold"]

            self._view.append_feed(
                f"[{timestamp()}] Verification http={http_val:.4f} (≤ {result['http_threshold']:.4f}), "
                f"cpu={cpu_val:.4f} (≤ {result['cpu_threshold']:.4f})"
            )

            details = (
                f"HTTP error rate {http_val:.4f} vs {result['http_threshold']:.4f}\n"
                f"CPU usage {cpu_val:.4f} vs {result['cpu_threshold']:.4f}"
            )
            if http_ok and cpu_ok:
                self._view.show_information(
                    "Recovery Verified",
                    f"Prometheus 지표 기준으로 서비스가 정상화되었습니다.\n\n{details}",
                )
                self._view.set_verify_enabled(False)
            else:
                self._view.show_warning(
                    "Recovery Pending",
                    f"임계값을 아직 충족하지 못했습니다.\n\n{details}",
                )

        self._executor.submit(job, done)

    # endregion
