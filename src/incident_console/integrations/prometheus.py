"""Prometheus 연동 모듈."""

from __future__ import annotations

from typing import Optional

import requests

from ..async_tasks import IntegrationError


class PrometheusClient:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session or requests.Session()

    def instant_value(self, base_url: str, query: str) -> float:
        endpoint = f"{base_url.rstrip('/')}/api/v1/query"
        try:
            response = self._session.get(endpoint, params={"query": query}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:  # pragma: no cover - 네트워크 예외 처리
            raise IntegrationError(f"Prometheus query failed: {exc}") from exc
        except ValueError as exc:
            raise IntegrationError("Prometheus response returned invalid JSON") from exc

        if data.get("status") != "success":
            raise IntegrationError(
                f"Prometheus query unsuccessful: {data.get('error', 'unknown error')}"
            )

        result = data.get("data", {}).get("result", [])
        if not result:
            raise IntegrationError("Prometheus query returned no samples")

        try:
            return float(result[0]["value"][1])
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationError("Prometheus sample missing numeric value") from exc
