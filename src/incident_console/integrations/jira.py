"""Jira 연동 모듈."""

from __future__ import annotations

from typing import Dict, Optional

import requests
from requests.auth import HTTPBasicAuth

from ..async_tasks import IntegrationError


class JiraIntegration:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session or requests.Session()

    def test_connection(self, site: str, email: str, token: str, project: str) -> Dict[str, object]:
        url = f"{site.rstrip('/')}/rest/api/3/project/{project}"
        try:
            response = self._session.get(url, auth=HTTPBasicAuth(email, token), timeout=10)
        except requests.RequestException as exc:  # pragma: no cover - 네트워크 예외 처리
            raise IntegrationError(f"Jira project lookup failed: {exc}") from exc

        if response.status_code == 401:
            raise IntegrationError("Jira credentials rejected (401)")
        if response.status_code == 404:
            raise IntegrationError(f"Jira project {project} not found or inaccessible")
        if not response.ok:
            raise IntegrationError(f"Jira test failed: HTTP {response.status_code}")

        try:
            return response.json()
        except ValueError as exc:
            raise IntegrationError("Jira project lookup returned invalid JSON") from exc

    def create_incident_issue(
        self,
        site: str,
        email: str,
        token: str,
        project: str,
        summary: str,
        description: str,
    ) -> Dict[str, object]:
        url = f"{site.rstrip('/')}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": project},
                "summary": summary,
                "description": description,
                "issuetype": {"name": "Task"},
            }
        }
        try:
            response = self._session.post(
                url,
                auth=HTTPBasicAuth(email, token),
                json=payload,
                timeout=15,
            )
        except requests.RequestException as exc:  # pragma: no cover - 네트워크 예외 처리
            raise IntegrationError(f"Jira issue creation failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise IntegrationError("Jira rejected credentials or permissions for issue create")
        if response.status_code == 404:
            raise IntegrationError("Jira issue endpoint not found; check site URL")
        if response.status_code not in {200, 201}:
            raise IntegrationError(f"Jira issue create failed: HTTP {response.status_code}")

        try:
            return response.json()
        except ValueError as exc:
            raise IntegrationError("Jira issue create returned invalid JSON") from exc
