"""Slack 연동 모듈."""

from __future__ import annotations

from typing import Dict, Optional

import requests

from ..async_tasks import IntegrationError


class SlackIntegration:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session or requests.Session()

    def test_connection(self, token: str) -> Dict[str, object]:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = self._session.post(
                "https://slack.com/api/auth.test",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:  # pragma: no cover - 네트워크 예외 처리
            raise IntegrationError(f"Slack auth request failed: {exc}") from exc
        except ValueError as exc:
            raise IntegrationError("Slack auth returned invalid JSON") from exc

        if not data.get("ok"):
            raise IntegrationError(f"Slack auth error: {data.get('error', 'unknown error')}")
        return data

    def post_message(self, token: str, channel: str, text: str) -> Dict[str, object]:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"channel": channel, "text": text}
        try:
            response = self._session.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:  # pragma: no cover - 네트워크 예외 처리
            raise IntegrationError(f"Slack message failed: {exc}") from exc
        except ValueError as exc:
            raise IntegrationError("Slack message returned invalid JSON") from exc

        if not data.get("ok"):
            raise IntegrationError(f"Slack message error: {data.get('error', 'unknown error')}")
        return data
