"""Slack action client (simulated for MVP)."""

from __future__ import annotations

from typing import Any, Dict

from ..config import SlackConfig
from ..models import ActionRecommendation, ActionResult
from .base import ActionClient


class SlackActionClient(ActionClient):
    """Formats Slack messages for operational responders."""

    action_type = "slack"

    def __init__(self, config: SlackConfig) -> None:
        self._config = config

    def execute(self, recommendation: ActionRecommendation) -> ActionResult:
        detail = "Simulated Slack message delivery; replace with webhook call."
        metadata: Dict[str, Any] = {
            "channel": self._config.channel,
            "payload": recommendation.payload,
        }
        return ActionResult(
            action_type=self.action_type,
            status="simulated",
            detail=detail,
            metadata=metadata,
        )
