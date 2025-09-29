"""Qt 비동기 작업 유틸리티."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class IntegrationError(RuntimeError):
    """외부 연동 실패를 표현하는 예외."""


class WorkerSignals(QObject):
    finished = Signal(object, object)


class AsyncTask(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self._fn()
            self.signals.finished.emit(result, None)
        except Exception as exc:  # noqa: BLE001 - UI 레이어에서 처리
            self.signals.finished.emit(None, exc)


class AsyncExecutor:
    """QThreadPool을 감싼 비동기 실행 도우미."""

    def __init__(self, pool: QThreadPool | None = None) -> None:
        self._pool = pool or QThreadPool.globalInstance()

    def submit(self, fn: Callable[[], Any], callback: Callable[[Any | None, Exception | None], None]) -> None:
        task = AsyncTask(fn)
        task.signals.finished.connect(callback)
        self._pool.start(task)
