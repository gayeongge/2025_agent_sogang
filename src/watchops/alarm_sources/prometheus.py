"""Adapters for Prometheus Alertmanager webhooks."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List

from ..models import Alert


class PrometheusAlertParser:
    """Parses Prometheus Alertmanager webhook payloads into Alert objects."""

    def parse(self, payload: Dict[str, object]) -> List[Alert]:
        raw_alerts = payload.get("alerts") or []
        parsed: List[Alert] = []
        for raw in raw_alerts:  # type: ignore[assignment]
            alert = Alert(
                source="prometheus",
                labels=self._coerce_str_dict(raw.get("labels", {})),
                annotations=self._coerce_str_dict(raw.get("annotations", {})),
                starts_at=self._parse_datetime(raw.get("startsAt")),
                ends_at=self._parse_datetime(raw.get("endsAt")),
                severity=self._infer_severity(raw),
                fingerprint=raw.get("fingerprint"),
            )
            parsed.append(alert)
        return parsed

    def _coerce_str_dict(self, value: object) -> Dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {str(k): str(v) for k, v in value.items() if k is not None and v is not None}

    def _parse_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        clean = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(clean)
        except ValueError:
            return None

    def _infer_severity(self, raw: Dict[str, object]) -> str:
        labels = raw.get("labels")
        if isinstance(labels, dict):
            severity = labels.get("severity")
            if isinstance(severity, str):
                return severity
        return "unknown"
