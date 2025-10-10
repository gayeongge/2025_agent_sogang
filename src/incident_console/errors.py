"""Shared exception types for the incident console."""

from __future__ import annotations


class IntegrationError(RuntimeError):
    """Raised when an upstream integration call fails."""

