"""Remote action clients for API or MCP integrations."""

from __future__ import annotations

from typing import Any, Dict

from ..models import ActionRecommendation, ActionResult
from .base import ActionClient


class HttpActionClient(ActionClient):
    """Sends remediation requests to an HTTP API endpoint."""

    action_type = "api"

    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def execute(self, recommendation: ActionRecommendation) -> ActionResult:
        endpoint = recommendation.payload.get("endpoint", "/remediations")
        url = f"{self._base_url}{endpoint}"
        detail = (
            "Simulated HTTP API call; replace with real request implementation "
            "(e.g., requests or httpx)."
        )
        metadata: Dict[str, Any] = {
            "url": url,
            "payload": recommendation.payload,
        }
        return ActionResult(
            action_type=self.action_type,
            status="simulated",
            detail=detail,
            metadata=metadata,
        )


class MCPActionClient(ActionClient):
    """Invokes actions through a hypothetical MCP (Management Control Plane)."""

    action_type = "mcp"

    def __init__(self, *, endpoint: str) -> None:
        self._endpoint = endpoint

    def execute(self, recommendation: ActionRecommendation) -> ActionResult:
        command = recommendation.payload.get("command", "noop")
        detail = "Simulated MCP command dispatch; integrate with MCP SDK when ready."
        metadata: Dict[str, Any] = {
            "endpoint": self._endpoint,
            "command": command,
            "parameters": recommendation.payload.get("parameters", {}),
        }
        return ActionResult(
            action_type=self.action_type,
            status="simulated",
            detail=detail,
            metadata=metadata,
        )
