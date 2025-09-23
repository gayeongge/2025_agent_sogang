"""Collector for Jira issue creation events."""

from __future__ import annotations

from typing import Any, Dict

from ..models import JiraIssueEvent
from .base import AlertCollector, CollectorResponse


class JiraIssueEventCollector(AlertCollector):
    """Consumes Jira webhook payloads for issue creation events."""

    source = "jira_issue_created"

    def collect(
        self,
        payload: Dict[str, Any],
        *,
        execute: bool = False,
        **_: Any,
    ) -> CollectorResponse:
        issue = self._parse_issue(payload)
        metadata = {
            "issue_event": issue,
            "note": "Jira issue creation event ingested; persistence pipeline TBD.",
        }
        # No remediation plans to build here; returning metadata only.
        return CollectorResponse(plans=[], execution_results=[], metadata=metadata)

    def _parse_issue(self, payload: Dict[str, Any]) -> JiraIssueEvent:
        issue_data = payload.get("issue", {})
        fields = issue_data.get("fields", {})
        issue_key = issue_data.get("key", "UNKNOWN")
        project = fields.get("project", {})
        reporter = fields.get("reporter", {})
        priority = fields.get("priority", {})

        return JiraIssueEvent(
            issue_key=issue_key,
            project_key=project.get("key", "UNKNOWN"),
            summary=fields.get("summary", ""),
            reporter=reporter.get("displayName") if isinstance(reporter, dict) else None,
            priority=priority.get("name") if isinstance(priority, dict) else None,
            url=self._issue_url(payload),
            raw=payload,
        )

    def _issue_url(self, payload: Dict[str, Any]) -> str | None:
        issue = payload.get("issue", {})
        if isinstance(issue, dict):
            return issue.get("self")
        return None
