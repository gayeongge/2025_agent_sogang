"""Presenter 공용 유틸리티."""

from __future__ import annotations

from datetime import datetime


def timestamp() -> str:
    """UTC 시각을 HH:MM:SS 형태로 반환."""
    return datetime.utcnow().strftime("%H:%M:%S")


def parse_threshold(value: str, *, default: float) -> float:
    stripped = value.strip()
    if not stripped:
        return default
    parsed = float(stripped)
    if parsed < 0:
        raise ValueError("임계값은 0 이상이어야 합니다.")
    return parsed
