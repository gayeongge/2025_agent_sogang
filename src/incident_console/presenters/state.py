"""Presenter에서 공유하는 상태."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..config import get_openai_api_key
from ..models import AlertScenario, JiraSettings, PrometheusSettings, SlackSettings
from ..scenarios import load_default_scenarios


@dataclass
class PresenterState:
    slack: SlackSettings = field(default_factory=SlackSettings)
    jira: JiraSettings = field(default_factory=JiraSettings)
    prometheus: PrometheusSettings = field(default_factory=PrometheusSettings)
    scenarios: List[AlertScenario] = field(default_factory=load_default_scenarios)
    openai_api_key: str = field(default_factory=lambda: get_openai_api_key() or "")
