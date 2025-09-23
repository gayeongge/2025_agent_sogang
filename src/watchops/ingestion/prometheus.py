"""Prometheus Alertmanager collector implementation."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from ..services.orchestrator import WatchOpsOrchestrator
from ..models import RemediationPlan, ActionResult
from .base import AlertCollector, CollectorResponse


class PrometheusWebhookCollector(AlertCollector):
    """Ingests Alertmanager webhook payloads via the WatchOps orchestrator."""

    source = "prometheus"

    def __init__(self, orchestrator: WatchOpsOrchestrator) -> None:
        self._orchestrator = orchestrator

    def collect(
        self,
        payload: Dict[str, Any],
        *,
        execute: bool = False,
        top_k_hypotheses: int = 3,
        user_notes: Iterable[str] | None = None,
    ) -> CollectorResponse:
        plans = self._orchestrator.plan_prometheus_alert(
            payload,
            top_k_hypotheses=top_k_hypotheses,
            user_notes=user_notes,
        )
        if not execute:
            return CollectorResponse.from_plans(plans)
        results = self._orchestrator.execute_plans(plans)
        return CollectorResponse(plans=plans, execution_results=results)
