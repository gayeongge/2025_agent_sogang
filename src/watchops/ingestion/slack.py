"""Collector for Slack channel alarm events."""

from __future__ import annotations

from typing import Any, Dict

from ..models import SlackChannelEvent
from .base import AlertCollector, CollectorResponse


class SlackChannelEventCollector(AlertCollector):
    """Consumes Slack Events API payloads for channel alarm notifications."""

    source = "slack_channel_event"

    def collect(
        self,
        payload: Dict[str, Any],
        *,
        execute: bool = False,
        **_: Any,
    ) -> CollectorResponse:
        event = self._parse_event(payload)
        metadata = {
            "slack_event": event,
            "note": "Slack channel alarm event ingested; notify routing TBD.",
        }
        return CollectorResponse(plans=[], execution_results=[], metadata=metadata)

    def _parse_event(self, payload: Dict[str, Any]) -> SlackChannelEvent:
        event = payload.get("event", {})
        channel = event.get("channel", "UNKNOWN")
        text = event.get("text", "")
        user = event.get("user")
        ts = event.get("ts", "")
        event_type = event.get("type", payload.get("type", "event_callback"))
        return SlackChannelEvent(
            channel=channel,
            user=user,
            text=text,
            ts=ts,
            event_type=event_type,
            raw=payload,
        )
