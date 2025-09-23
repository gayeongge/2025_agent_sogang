"""Safety guard implementations for action execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Protocol

from ..models import ActionRecommendation, ActionResult, RemediationPlan


@dataclass
class GuardDecision:
    """Outcome of safety guard authorization."""

    allowed: bool
    reason: str = ""
    simulate_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class SafetyGuard(Protocol):
    """Defines a contract for safeguarding action execution."""

    def authorize(
        self,
        *,
        plan: RemediationPlan,
        recommendation: ActionRecommendation,
    ) -> GuardDecision:
        """Determine whether the recommendation may be executed."""

    def simulate(
        self,
        *,
        plan: RemediationPlan,
        recommendation: ActionRecommendation,
        decision: GuardDecision,
    ) -> ActionResult:
        """Produce a simulated result when execution is disallowed or deferred."""


class DefaultSafetyGuard(SafetyGuard):
    """Basic guard enforcing allowlists and simulation for sensitive actions."""

    def __init__(
        self,
        *,
        allowed_actions: Iterable[str] | None = None,
        simulate_actions: Iterable[str] | None = None,
    ) -> None:
        self._allowed_actions = set(allowed_actions or {"slack", "jira", "api", "mcp", "email"})
        self._simulate_actions = set(simulate_actions or {"api", "mcp"})

    def authorize(
        self,
        *,
        plan: RemediationPlan,
        recommendation: ActionRecommendation,
    ) -> GuardDecision:
        action_type = recommendation.action_type
        metadata = {
            "scenario": plan.scenario,
            "action_type": action_type,
        }
        if action_type not in self._allowed_actions:
            return GuardDecision(
                allowed=False,
                reason=f"Action type '{action_type}' is not permitted by safety policy.",
                simulate_only=False,
                metadata=metadata,
            )
        simulate_only = action_type in self._simulate_actions
        if simulate_only:
            metadata["mode"] = "simulation"
        else:
            metadata["mode"] = "execution"
        return GuardDecision(
            allowed=True,
            reason="Authorized",
            simulate_only=simulate_only,
            metadata=metadata,
        )

    def simulate(
        self,
        *,
        plan: RemediationPlan,
        recommendation: ActionRecommendation,
        decision: GuardDecision,
    ) -> ActionResult:
        detail = (
            "Safety guard simulation executed; real command requires elevated approval."
        )
        metadata = {
            "guard": decision.metadata,
            "payload": recommendation.payload,
        }
        return ActionResult(
            action_type=recommendation.action_type,
            status="simulated",
            detail=detail,
            metadata=metadata,
        )
