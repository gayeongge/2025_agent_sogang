"""Service layer for orchestrating action execution with user approval."""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import ClassVar, List, Optional

import requests
import uvicorn

from src.backend.fake_actions_api import fake_actions_app
from src.backend.state import (
    STATE,
    STATE_LOCK,
    ActionExecution,
    ActionExecutionResult,
    IncidentReport,
)
from src.incident_console.utils import timestamp, utcnow_iso


_SIM_HOST = os.environ.get("INCIDENT_ACTION_SIM_HOST", "127.0.0.1")
_SIM_PORT = int(os.environ.get("INCIDENT_ACTION_SIM_PORT", "8765"))
_SIM_BASE_URL = f"http://{_SIM_HOST}:{_SIM_PORT}"
_SIM_EXECUTE_URL = f"{_SIM_BASE_URL}/execute"
_SIM_HEALTH_URL = f"{_SIM_BASE_URL}/health"


def _feed_line(message: str) -> str:
    return f"[{timestamp()}] {message}"


def _run_simulator_server() -> None:
    """Run the FastAPI simulator using uvicorn in a background thread."""

    config = uvicorn.Config(
        fake_actions_app,
        host=_SIM_HOST,
        port=_SIM_PORT,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    server.run()


class ActionExecutionService:
    """Queues action plans and executes them through the simulator."""

    _sim_lock: ClassVar[threading.Lock] = threading.Lock()
    _sim_started: ClassVar[bool] = False
    _sim_thread: ClassVar[threading.Thread | None] = None

    def __init__(self) -> None:
        self._ensure_simulator()
        self._session = requests.Session()

    def _ensure_simulator(self) -> None:
        if self.__class__._sim_started:
            return

        with self._sim_lock:
            if self.__class__._sim_started:
                return

            # First try to detect an already running simulator (reuse on reload).
            if self._probe_simulator():
                self.__class__._sim_started = True
                return

            thread = threading.Thread(
                target=_run_simulator_server,
                name="ActionSimulatorServer",
                daemon=True,
            )
            thread.start()
            self.__class__._sim_thread = thread

        # Wait for the server to report healthy.
        if not self._wait_for_simulator():
            raise RuntimeError("Failed to start action simulator service")
        self.__class__._sim_started = True

    @staticmethod
    def _probe_simulator(timeout: float = 0.5) -> bool:
        try:
            response = requests.get(_SIM_HEALTH_URL, timeout=timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False

    @staticmethod
    def _wait_for_simulator(retries: int = 20, delay: float = 0.25) -> bool:
        for _ in range(retries):
            if ActionExecutionService._probe_simulator(timeout=0.5):
                return True
            time.sleep(delay)
        return False

    def queue_from_report(self, report: IncidentReport) -> Optional[ActionExecution]:
        actions = [action.strip() for action in report.action_items if action.strip()]
        if not actions:
            return None

        execution = ActionExecution(
            id=str(uuid.uuid4()),
            report_id=report.id,
            scenario_code=report.scenario_code,
            scenario_title=report.title,
            created_at=report.created_at,
            actions=actions,
        )

        with STATE_LOCK:
            STATE.action_executions.append(execution)
            # keep history bounded
            if len(STATE.action_executions) > 30:
                STATE.action_executions.pop(0)
            STATE.append_feed(
                _feed_line(
                    f"Action plan ready for approval ({execution.scenario_title})"
                )
            )
        return execution

    def execute_pending(self, execution_id: str) -> ActionExecution:
        execution = self._require_execution(execution_id)
        if execution.status == "executed":
            return execution

        results: List[ActionExecutionResult] = []
        for action in execution.actions:
            try:
                response = self._session.post(
                    _SIM_EXECUTE_URL,
                    json={"execution_id": execution_id, "action": action},
                    timeout=5.0,
                )
            except requests.RequestException as exc:
                raise ValueError("Action simulator request failed") from exc
            if response.status_code >= 400:
                raise ValueError(
                    f"Action simulator failed with HTTP {response.status_code}"
                )
            payload = response.json()
            result = ActionExecutionResult(
                action=action,
                status=str(payload.get("status", "unknown")),
                detail=str(payload.get("detail", "")),
                executed_at=str(payload.get("executed_at") or utcnow_iso()),
            )
            results.append(result)

        with STATE_LOCK:
            execution.status = "executed"
            execution.executed_at = utcnow_iso()
            execution.results = results
            STATE.append_feed(
                _feed_line(
                    f"Executed {len(results)} action(s) for {execution.scenario_title}"
                )
            )
        return execution

    def defer_execution(self, execution_id: str) -> ActionExecution:
        execution = self._require_execution(execution_id)
        if execution.status == "executed":
            return execution
        with STATE_LOCK:
            execution.status = "deferred"
            execution.executed_at = None
            execution.results = []
            STATE.append_feed(
                _feed_line(
                    f"Stored action plan for manual review ({execution.scenario_title})"
                )
            )
        return execution

    def _require_execution(self, execution_id: str) -> ActionExecution:
        with STATE_LOCK:
            execution = next(
                (item for item in STATE.action_executions if item.id == execution_id),
                None,
            )
        if execution is None:
            raise ValueError("Unknown action execution request")
        return execution
