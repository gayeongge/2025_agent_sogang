"""Diagnostics engine coordinating checks for alerts."""

from __future__ import annotations

from typing import Iterable, List

from ..models import Alert, DiagnosticFinding
from .base import DiagnosticCheck


class DiagnosticsEngine:
    """Runs registered diagnostic checks and aggregates findings."""

    def __init__(self, checks: Iterable[DiagnosticCheck]) -> None:
        self._checks = list(checks)

    def register(self, check: DiagnosticCheck) -> None:
        self._checks.append(check)

    def run(self, alert: Alert) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        for check in self._checks:
            if not check.applies(alert):
                continue
            finding = check.run(alert)
            findings.append(finding)
        return findings
