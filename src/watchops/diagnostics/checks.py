"""Built-in diagnostic checks for WatchOps MVP."""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import Alert, DiagnosticFinding
from .base import DiagnosticCheck


class SeveritySanityCheck(DiagnosticCheck):
    name = "severity_sanity"

    def applies(self, alert: Alert) -> bool:
        return True

    def run(self, alert: Alert) -> DiagnosticFinding:
        severity = alert.severity or alert.labels.get("severity", "unknown")
        detail = f"Alert reported severity '{severity}'."
        return DiagnosticFinding(name=self.name, status="info", detail=detail, metadata={"severity": severity})


class RecentStartTimeCheck(DiagnosticCheck):
    name = "recent_start_time"

    def applies(self, alert: Alert) -> bool:
        return alert.starts_at is not None

    def run(self, alert: Alert) -> DiagnosticFinding:
        assert alert.starts_at is not None
        now = datetime.now(timezone.utc)
        delta = now - alert.starts_at
        minutes = int(delta.total_seconds() // 60)
        status = "warning" if minutes > 30 else "info"
        detail = f"Alert has been firing for approximately {minutes} minutes."
        return DiagnosticFinding(name=self.name, status=status, detail=detail, metadata={"minutes_active": minutes})


class Http5xxContextCheck(DiagnosticCheck):
    name = "http_5xx_context"

    def applies(self, alert: Alert) -> bool:
        labels = {k.lower(): v.lower() for k, v in alert.labels.items()}
        return "5xx" in labels.get("alertname", "") or "5xx" in labels.get("metric_name", "")

    def run(self, alert: Alert) -> DiagnosticFinding:
        description = alert.annotations.get("description", "N/A")
        detail = "Analysed 5xx alert context; inspect upstream dependencies."
        return DiagnosticFinding(
            name=self.name,
            status="info",
            detail=detail,
            metadata={"description": description},
        )


class CpuSpikeContextCheck(DiagnosticCheck):
    name = "cpu_spike_context"

    def applies(self, alert: Alert) -> bool:
        labels = {k.lower(): v.lower() for k, v in alert.labels.items()}
        keyword_sources = [labels.get("alertname", ""), labels.get("metric_name", ""), labels.get("service", "")]
        return any("cpu" in value for value in keyword_sources if value)

    def run(self, alert: Alert) -> DiagnosticFinding:
        host = alert.labels.get("instance", alert.labels.get("host", "unknown"))
        detail = f"CPU spike detected on host {host}; check pod/node resource allocations."
        return DiagnosticFinding(
            name=self.name,
            status="info",
            detail=detail,
            metadata={"host": host},
        )
