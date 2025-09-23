"""Architecture skeleton definitions for WatchOps MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Component:
    """Represents a logical component in the WatchOps architecture."""

    name: str
    responsibility: str
    interfaces: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DataFlow:
    """Captures a directional integration between two components."""

    source: str
    target: str
    contract: str


@dataclass(frozen=True)
class ArchitectureSkeleton:
    """High-level blueprint describing major WatchOps building blocks."""

    components: List[Component]
    flows: List[DataFlow]


ARCHITECTURE_SKELETON = ArchitectureSkeleton(
    components=[
        Component(
            name="Prometheus Alert Ingress",
            responsibility="수집된 Alertmanager 웹훅 페이로드를 수신하고 정규화",
            interfaces=["HTTP Webhook", "PrometheusAlertParser", "PrometheusWebhookCollector"],
        ),
        Component(
            name="Collaboration Event Ingress",
            responsibility="Jira/Slack 등 협업 도구의 이벤트를 수집하여 상태 동기화",
            interfaces=["JiraIssueEventCollector", "SlackChannelEventCollector"],
        ),
        Component(
            name="Diagnostics Engine",
            responsibility="알람 별 진단 체크를 수행하여 Remediation Plan 에 컨텍스트 추가",
            interfaces=["DiagnosticsEngine", "DiagnosticChecks"],
        ),
        Component(
            name="Verification Engine",
            responsibility="조치 실행 전 계획 유효성 및 위험 검증",
            interfaces=["PlanVerificationEngine", "ActionCoverageVerifier", "SimulationVerifier"],
        ),
        Component(
            name="Post Monitoring",
            responsibility="조치 후 Prometheus 지표 기반 모니터링 작업 생성",
            interfaces=["PrometheusPostMonitoringGenerator"],
        ),
        Component(
            name="Alert Orchestrator",
            responsibility="정규화된 알람을 워크플로우와 매핑하고 실행 단계로 전달",
            interfaces=["WatchOpsOrchestrator"],
        ),
        Component(
            name="Safety Guard",
            responsibility="권한 검증 및 실행 전 시뮬레이션 수행",
            interfaces=["SafetyGuard", "DefaultSafetyGuard"],
        ),
        Component(
            name="Action Execution",
            responsibility="조치 추천을 실행하고 결과를 집계",
            interfaces=["ActionExecutor", "ActionRegistry", "SlackActionClient", "JiraActionClient", "HttpActionClient", "MCPActionClient"],
        ),
        Component(
            name="Workflow Catalog",
            responsibility="시나리오별 진단 및 대응 전략 정의",
            interfaces=["Nginx5xxWorkflow", "HttpErrorRateWorkflow", "CpuSpikeWorkflow"],
        ),
        Component(
            name="Observability Data Lake",
            responsibility="후속 분석을 위한 알람/조치/이벤트 메타데이터 보관 (MVP에서는 생략)",
            interfaces=["TBD"],
        ),
    ],
    flows=[
        DataFlow(
            source="Prometheus Alert Ingress",
            target="Alert Orchestrator",
            contract="Normalized Alert objects (watchops.models.Alert)",
        ),
        DataFlow(
            source="Alert Orchestrator",
            target="Diagnostics Engine",
            contract="Alert 전달 및 DiagnosticFinding 생성 요청",
        ),
        DataFlow(
            source="Diagnostics Engine",
            target="Alert Orchestrator",
            contract="DiagnosticFinding 리스트",
        ),
        DataFlow(
            source="Alert Orchestrator",
            target="Verification Engine",
            contract="RemediationPlan 검증 요청",
        ),
        DataFlow(
            source="Verification Engine",
            target="Alert Orchestrator",
            contract="VerificationIssue 리스트",
        ),
        DataFlow(
            source="Alert Orchestrator",
            target="Post Monitoring",
            contract="사후 모니터링 Task 생성 요청",
        ),
        DataFlow(
            source="Post Monitoring",
            target="Alert Orchestrator",
            contract="PostMonitoringTask 리스트",
        ),
        DataFlow(
            source="Alert Orchestrator",
            target="Workflow Catalog",
            contract="Workflow.matches/Workflow.build_plan 호출",
        ),
        DataFlow(
            source="Workflow Catalog",
            target="Alert Orchestrator",
            contract="RemediationPlan 반환",
        ),
        DataFlow(
            source="Alert Orchestrator",
            target="Safety Guard",
            contract="ActionRecommendation 권한 검증 요청",
        ),
        DataFlow(
            source="Safety Guard",
            target="Action Execution",
            contract="허가/시뮬레이션 결과",
        ),
        DataFlow(
            source="Action Execution",
            target="Observability Data Lake",
            contract="ActionResult 저장 (MVP 이후 확장)",
        ),
        DataFlow(
            source="Collaboration Event Ingress",
            target="Observability Data Lake",
            contract="JiraIssueEvent/SlackChannelEvent 메타데이터 적재",
        ),
    ],
)
