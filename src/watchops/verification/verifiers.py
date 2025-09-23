"""Built-in verification rules for WatchOps."""

from __future__ import annotations

from ..models import RemediationPlan, VerificationIssue
from .base import PlanVerifier


class ActionCoverageVerifier(PlanVerifier):
    """Ensures each plan contains at least one action recommendation."""

    def verify(self, plan: RemediationPlan) -> list[VerificationIssue]:
        if plan.recommendations:
            return []
        return [
            VerificationIssue(
                level="error",
                message="Remediation plan contains no action recommendations.",
                metadata={"scenario": plan.scenario},
            )
        ]


class SimulationVerifier(PlanVerifier):
    """Flags plans where all actions are forced to simulation mode."""

    def __init__(self, simulated_actions: set[str] | None = None) -> None:
        self._simulated_actions = simulated_actions or {"mcp", "api"}

    def verify(self, plan: RemediationPlan) -> list[VerificationIssue]:
        if not plan.recommendations:
            return []
        types = {rec.action_type for rec in plan.recommendations}
        if types.issubset(self._simulated_actions):
            return [
                VerificationIssue(
                    level="warning",
                    message="All actions require simulation/approval before execution.",
                    metadata={"scenario": plan.scenario, "actions": sorted(types)},
                )
            ]
        return []
