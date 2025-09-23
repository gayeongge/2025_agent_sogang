"""Action execution utilities for WatchOps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List

from ..models import ActionRecommendation, ActionResult, RemediationPlan
from .base import ActionClient
from .guard import DefaultSafetyGuard, SafetyGuard


class ActionRegistry:
    """Manages action clients keyed by their action type."""

    def __init__(self, clients: Iterable[ActionClient] | None = None) -> None:
        self._clients: Dict[str, ActionClient] = {}
        if clients:
            for client in clients:
                self.register(client)

    def register(self, client: ActionClient) -> None:
        self._clients[client.action_type] = client

    def get(self, action_type: str) -> ActionClient | None:
        return self._clients.get(action_type)

    def iter_clients(self) -> Iterator[ActionClient]:
        return iter(self._clients.values())


@dataclass
class ActionExecutionContext:
    """Contextual data captured during execution of recommendations."""

    plan: RemediationPlan
    recommendation: ActionRecommendation


class ActionExecutor:
    """Executes remediation recommendations via registered clients."""

    def __init__(
        self,
        registry: ActionRegistry | None = None,
        guard: SafetyGuard | None = None,
    ) -> None:
        self._registry = registry or ActionRegistry()
        self._guard = guard or DefaultSafetyGuard()

    @property
    def registry(self) -> ActionRegistry:
        return self._registry

    def register(self, client: ActionClient) -> None:
        self._registry.register(client)

    def execute_recommendation(
        self,
        recommendation: ActionRecommendation,
        *,
        context: RemediationPlan,
    ) -> ActionResult:
        decision = self._guard.authorize(plan=context, recommendation=recommendation)
        if not decision.allowed:
            return ActionResult(
                action_type=recommendation.action_type,
                status="blocked",
                detail=decision.reason,
                metadata={
                    "guard": decision.metadata,
                    "payload": recommendation.payload,
                },
            )
        if decision.simulate_only:
            return self._guard.simulate(
                plan=context,
                recommendation=recommendation,
                decision=decision,
            )

        client = self._registry.get(recommendation.action_type)
        if not client:
            return ActionResult(
                action_type=recommendation.action_type,
                status="skipped",
                detail="No action client registered; manual follow-up required.",
                metadata={"payload": recommendation.payload},
            )
        result = client.execute(recommendation)
        if decision.metadata:
            result.metadata.setdefault("guard", decision.metadata)
        result.metadata.setdefault("payload", recommendation.payload)
        result.metadata.setdefault("plan_scenario", context.scenario)
        return result

    def execute_plan(self, plan: RemediationPlan) -> List[ActionResult]:
        results: List[ActionResult] = []
        for recommendation in plan.recommendations:
            results.append(self.execute_recommendation(recommendation, context=plan))
        return results

    def execute_plans(self, plans: Iterable[RemediationPlan]) -> List[ActionResult]:
        results: List[ActionResult] = []
        for plan in plans:
            results.extend(self.execute_plan(plan))
        return results
