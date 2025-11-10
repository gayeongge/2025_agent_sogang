"""도메인 모델 정의."""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class AlertScenario:
    code: str
    title: str
    source: str
    description: str
    hypotheses: List[str]
    evidences: List[str]
    actions: List[str]


@dataclass
class SlackSettings:
    token: str = ""
    channel: str = "#ops-incident"
    workspace: str = ""


@dataclass
class PrometheusSettings:
    url: str = ""
    http_query: str = ""
    http_threshold: str = "0.05"
    cpu_query: str = ""
    cpu_threshold: str = "0.80"
