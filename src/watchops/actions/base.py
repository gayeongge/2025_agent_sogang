"""Abstract base classes for WatchOps action executors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from ..models import ActionRecommendation, ActionResult


class ActionClient(Protocol):
    """Interface for downstream action executors (Slack, Jira, etc.)."""

    action_type: str

    def execute(self, recommendation: ActionRecommendation) -> ActionResult:
        """Execute an action recommendation."""


@dataclass
class SimulatedActionClient:
    """Fallback client used during MVP prototyping with no external calls."""

    action_type: str

    def execute(self, recommendation: ActionRecommendation) -> ActionResult:
        detail = "Simulated action execution; integrate real client when ready."
        metadata: Dict[str, Any] = {"payload": recommendation.payload}
        return ActionResult(
            action_type=self.action_type,
            status="simulated",
            detail=detail,
            metadata=metadata,
        )
