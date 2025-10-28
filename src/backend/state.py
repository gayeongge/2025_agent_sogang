"""Shared application state for the FastAPI backend."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque, List, Optional

from src.incident_console.models import (
    AlertScenario,
    JiraSettings,
    PrometheusSettings,
    SlackSettings,
)
from src.incident_console.scenarios import load_default_scenarios
from src.incident_console.utils import utcnow_iso


@dataclass
class MetricSample:
    """Single Prometheus observation with threshold comparisons."""

    timestamp: str
    http: float
    http_threshold: float
    cpu: float
    cpu_threshold: float

    @property
    def http_exceeded(self) -> bool:
        return self.http > self.http_threshold

    @property
    def cpu_exceeded(self) -> bool:
        return self.cpu > self.cpu_threshold

    @property
    def any_exceeded(self) -> bool:
        return self.http_exceeded or self.cpu_exceeded


@dataclass
class NotificationPreferences:
    slack: bool = True
    jira: bool = True


@dataclass
class IncidentReport:
    """Structured summary of an incident notification."""

    id: str
    scenario_code: str
    title: str
    created_at: str
    report_body: str
    metrics: MetricSample
    summary: str
    root_cause: str
    impact: str
    action_items: List[str]
    follow_up: List[str]
    recipients_sent: List[str] = field(default_factory=list)
    recipients_missing: List[str] = field(default_factory=list)


@dataclass
class ActionExecutionResult:
    """Outcome returned by the fake action executor."""

    action: str
    status: str
    detail: str
    executed_at: str


@dataclass
class ActionExecution:
    """Pending or completed execution request for report action items."""

    id: str
    report_id: str
    scenario_code: str
    scenario_title: str
    created_at: str
    actions: List[str]
    status: str = "pending"
    executed_at: Optional[str] = None
    results: List[ActionExecutionResult] = field(default_factory=list)


@dataclass
class AppState:
    """Mutable state shared across API requests."""

    slack: SlackSettings = field(default_factory=SlackSettings)
    jira: JiraSettings = field(default_factory=JiraSettings)
    prometheus: PrometheusSettings = field(default_factory=PrometheusSettings)
    scenarios: List[AlertScenario] = field(default_factory=load_default_scenarios)
    feed: List[str] = field(default_factory=list)
    alert_history: List[str] = field(default_factory=list)
    last_alert: Optional[AlertScenario] = None
    monitor_samples: Deque[MetricSample] = field(
        default_factory=lambda: deque(maxlen=5)
    )
    incident_active: bool = False
    preferences: NotificationPreferences = field(
        default_factory=NotificationPreferences
    )
    last_report: Optional[IncidentReport] = None
    pending_reports: List[IncidentReport] = field(default_factory=list)
    action_executions: List[ActionExecution] = field(default_factory=list)

    def append_feed(self, message: str) -> None:
        self.feed.append(message)

    def record_alert(self, label: str, scenario: AlertScenario) -> None:
        self.alert_history.insert(0, label)
        self.last_alert = scenario


STATE = AppState()
STATE_LOCK = Lock()


def make_sample(http: float, http_threshold: float, cpu: float, cpu_threshold: float) -> MetricSample:
    """Factory helper to build a timestamped metric sample."""

    return MetricSample(
        timestamp=utcnow_iso(),
        http=http,
        http_threshold=http_threshold,
        cpu=cpu,
        cpu_threshold=cpu_threshold,
    )
