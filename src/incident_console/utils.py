"""Shared utility helpers for incident console services."""

from __future__ import annotations

from datetime import datetime, timezone


def timestamp() -> str:
    """Return the current UTC time formatted as HH:MM:SS."""
    return datetime.utcnow().strftime("%H:%M:%S")


def parse_threshold(value: str, *, default: float) -> float:
    """Parse a numeric threshold string, falling back to the provided default."""
    stripped = value.strip()
    if not stripped:
        return default
    parsed = float(stripped)
    if parsed < 0:
        raise ValueError("Threshold must be zero or greater.")
    return parsed


def utcnow_iso() -> str:
    """Return the current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
