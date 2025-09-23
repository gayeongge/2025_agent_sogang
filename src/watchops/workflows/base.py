"""Workflow base definitions for WatchOps."""

from __future__ import annotations

from typing import Protocol

from ..models import Alert, RemediationPlan


class Workflow(Protocol):
    """Defines common interface for remediation workflows."""

    scenario: str

    def matches(self, alert: Alert) -> bool:
        """Return True if the workflow can handle the given alert."""

    def build_plan(self, alert: Alert) -> RemediationPlan:
        """Construct a remediation plan for the alert."""
