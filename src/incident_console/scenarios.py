"""알람 시나리오 시드 데이터."""

from typing import List

from .models import AlertScenario


def load_default_scenarios() -> List[AlertScenario]:
    """order.md MVP 시나리오와 일치하는 샘플 데이터를 반환한다."""
    return [
        AlertScenario(
            code="http_5xx_surge",
            title="Nginx 5xx surge on checkout API",
            source="Prometheus http_error_rate",
            description="http_error_rate exceeded threshold triggering Slack notification",
            hypotheses=[
                "Recent deploy introduced regression in request validation",
                "Upstream payment provider timeout cascading to gateway",
                "Auto-scaling group missing warm instances causing cold start failures",
            ],
            evidences=[
                "http_error_rate > 12% over 5m",
                "Deployment build #20250925.3 rolled out 5 min before alert",
                "Gateway pods restarted 3 times within 10m",
            ],
            actions=[
                "Roll back checkout-service to build #20250925.2 via MCP",
                "Scale gateway pool to 2× to absorb traffic spike",
                "Notify product manager in #ops-incident",
            ],
        ),
        AlertScenario(
            code="cpu_spike_core",
            title="Edge node CPU spike",
            source="Prometheus cpu_usage",
            description="cpu_usage exceeded 90% triggering Jira incident",
            hypotheses=[
                "Ashburn edge node receiving concentrated traffic burst",
                "New Prometheus scrape job running hot due to misconfigured interval",
                "Background batch job pinned to shared core",
            ],
            evidences=[
                "cpu_usage >= 92% for 10 mins on edge-node-03",
                "Load balancer sticky sessions skewed toward node",
                "No matching deployment in the change log",
            ],
            actions=[
                "Rebalance traffic by updating load balancer weights",
                "Throttle scrape interval for experimental dashboard",
                "Open Jira outage ticket for visibility",
            ],
        ),
    ]
