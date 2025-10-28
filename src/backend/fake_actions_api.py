"""In-process FastAPI app that simulates action execution results."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from src.incident_console.utils import utcnow_iso

fake_actions_app = FastAPI(title="Action Simulator", version="1.0.0")


class SimulatedActionPayload(BaseModel):
    execution_id: str
    action: str


@fake_actions_app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@fake_actions_app.post("/execute")
def execute_action(payload: SimulatedActionPayload) -> dict[str, str]:
    """Pretend to perform an action and return a deterministic response."""

    executed_at = utcnow_iso()
    detail = f"Simulated run completed for '{payload.action}'."
    return {
        "execution_id": payload.execution_id,
        "status": "success",
        "detail": detail,
        "executed_at": executed_at,
    }
