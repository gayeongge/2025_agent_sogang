"""Domain models for WatchOps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Alert:
    """Normalized alert representation coming from monitoring systems."""

    source: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    severity: str = "unknown"
    fingerprint: Optional[str] = None


@dataclass
class ActionRecommendation:
    """Recommendation for a downstream tool (e.g., Slack, Jira)."""

    action_type: str
    description: str
    payload: Dict[str, Any]


@dataclass
class DiagnosticFinding:
    """Represents a single diagnostic conclusion about an alert."""

    name: str
    status: str
    detail: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Hypothesis:
    """AI- or user-informed remediation hypothesis."""

    title: str
    confidence: float
    rationale: str
    signals: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorrelationInsight:
    """Metric/log linkage insight for a given alert source."""

    source: str
    metric_reference: str
    log_reference: str
    confidence: float
    summary: str


@dataclass
class PostMonitoringTask:
    """Defines a follow-up monitoring task after remediation."""

    metric_query: str
    duration: str
    success_criteria: str
    notes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationIssue:
    """Represents a verification warning or error on a remediation plan."""

    level: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionEffectReport:
    """Summarizes action execution outcomes and normalization state."""

    plan_scenario: str
    normalized: bool
    summary: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class RemediationPlan:
    """Aggregates recommended actions to respond to an alert."""

    scenario: str
    summary: str
    recommendations: List[ActionRecommendation] = field(default_factory=list)
    diagnostics: List[DiagnosticFinding] = field(default_factory=list)
    hypotheses: List[Hypothesis] = field(default_factory=list)
    correlations: List[CorrelationInsight] = field(default_factory=list)
    post_monitoring: List[PostMonitoringTask] = field(default_factory=list)
    verifications: List[VerificationIssue] = field(default_factory=list)
    reports: List[ActionEffectReport] = field(default_factory=list)


@dataclass
class ActionResult:
    """Result of executing a recommended action."""

    action_type: str
    status: str
    detail: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JiraIssueEvent:
    """Represents a Jira issue creation event received from webhooks/API."""

    issue_key: str
    project_key: str
    summary: str
    reporter: Optional[str]
    priority: Optional[str]
    url: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SlackChannelEvent:
    """Captures Slack channel alarm messages received via Events API."""

    channel: str
    user: Optional[str]
    text: str
    ts: str
    event_type: str
    raw: Dict[str, Any] = field(default_factory=dict)
