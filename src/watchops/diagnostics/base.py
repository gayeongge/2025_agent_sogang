"""Diagnostic base definitions for WatchOps."""

from __future__ import annotations

from typing import Protocol

from ..models import Alert, DiagnosticFinding


class DiagnosticCheck(Protocol):
    """Interface for diagnostic routines executed against alerts."""

    name: str

    def applies(self, alert: Alert) -> bool:
        """Return True if this diagnostic should run for the given alert."""

    def run(self, alert: Alert) -> DiagnosticFinding:
        """Produce a diagnostic finding for the alert."""


class AlwaysRunCheck(DiagnosticCheck):
    """Utility diagnostic that always runs with a static outcome."""

    def __init__(self, name: str, detail: str, status: str = "info") -> None:
        self.name = name
        self._detail = detail
        self._status = status

    def applies(self, alert: Alert) -> bool:
        return True

    def run(self, alert: Alert) -> DiagnosticFinding:
        return DiagnosticFinding(name=self.name, status=self._status, detail=self._detail)
