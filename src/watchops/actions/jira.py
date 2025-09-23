"""Jira action client (simulated for MVP)."""

from __future__ import annotations

from typing import Any, Dict

from ..config import JiraConfig
from ..models import ActionRecommendation, ActionResult
from .base import ActionClient


class JiraActionClient(ActionClient):
    """Prepares Jira tickets based on remediation recommendations."""

    action_type = "jira"

    def __init__(self, config: JiraConfig) -> None:
        self._config = config

    def execute(self, recommendation: ActionRecommendation) -> ActionResult:
        detail = (
            "Simulated Jira issue creation; replace with REST call against Jira API."
        )
        metadata: Dict[str, Any] = {
            "project": self._config.project_key,
            "payload": recommendation.payload,
        }
        return ActionResult(
            action_type=self.action_type,
            status="simulated",
            detail=detail,
            metadata=metadata,
        )
