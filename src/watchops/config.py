"""Configuration objects for WatchOps integrations."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PrometheusConfig:
    endpoint: str
    auth_token: Optional[str] = None


@dataclass
class JiraConfig:
    base_url: str
    project_key: str
    auth_user: Optional[str] = None
    auth_token: Optional[str] = None


@dataclass
class SlackConfig:
    webhook_url: str
    channel: Optional[str] = None


@dataclass
class WatchOpsConfig:
    prometheus: PrometheusConfig
    jira: JiraConfig
    slack: SlackConfig
