"""Action clients for WatchOps."""

from .jira import JiraActionClient
from .slack import SlackActionClient
from .remote import HttpActionClient, MCPActionClient
from .base import SimulatedActionClient, ActionClient
from .executor import ActionExecutor, ActionRegistry
from .guard import SafetyGuard, DefaultSafetyGuard, GuardDecision

__all__ = [
    "JiraActionClient",
    "SlackActionClient",
    "HttpActionClient",
    "MCPActionClient",
    "SimulatedActionClient",
    "ActionClient",
    "ActionExecutor",
    "ActionRegistry",
    "SafetyGuard",
    "DefaultSafetyGuard",
    "GuardDecision",
]
