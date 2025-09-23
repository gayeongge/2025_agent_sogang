"""Alert ingestion module base definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Protocol

from ..models import ActionResult, RemediationPlan


@dataclass
class CollectorResponse:
    """Summary of processing performed by a collector."""

    plans: List[RemediationPlan]
    execution_results: List[ActionResult]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_plans(cls, plans: List[RemediationPlan]) -> "CollectorResponse":
        return cls(plans=plans, execution_results=[], metadata={})


class AlertCollector(Protocol):
    """Interface for alert ingestion adapters."""

    source: str

    def collect(
        self,
        payload: Dict[str, Any],
        *,
        execute: bool = False,
        **options: Any,
    ) -> CollectorResponse:
        """Ingest a raw payload and optionally execute remediation."""


class CompositeCollector:
    """Routes ingestion to the correct collector based on source name."""

    def __init__(self, collectors: Iterable[AlertCollector]) -> None:
        self._collectors = {collector.source: collector for collector in collectors}

    def collect(
        self,
        source: str,
        payload: Dict[str, Any],
        *,
        execute: bool = False,
        **options: Any,
    ) -> CollectorResponse:
        collector = self._collectors.get(source)
        if not collector:
            raise KeyError(f"No collector registered for source '{source}'")
        return collector.collect(payload, execute=execute, **options)
