"""Plan verification engine."""

from __future__ import annotations

from typing import Iterable

from ..models import RemediationPlan, VerificationIssue
from .base import PlanVerifier


class PlanVerificationEngine:
    """Runs registered verifiers against remediation plans."""

    def __init__(self, verifiers: Iterable[PlanVerifier] | None = None) -> None:
        self._verifiers = list(verifiers or [])

    def register(self, verifier: PlanVerifier) -> None:
        self._verifiers.append(verifier)

    def verify(self, plan: RemediationPlan) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        for verifier in self._verifiers:
            issues.extend(verifier.verify(plan))
        return issues
