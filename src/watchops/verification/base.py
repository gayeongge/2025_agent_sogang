"""Verification base classes."""

from __future__ import annotations

from typing import Protocol

from ..models import RemediationPlan, VerificationIssue


class PlanVerifier(Protocol):
    """Contract for remediation plan verification rules."""

    def verify(self, plan: RemediationPlan) -> list[VerificationIssue]:
        """Return issues detected on the plan."""


class NoOpVerifier(PlanVerifier):
    """Verifier that always passes."""

    def verify(self, plan: RemediationPlan) -> list[VerificationIssue]:
        return []
