"""Interfaces and implementations for hypothesis generation."""

from __future__ import annotations

from typing import Iterable, List, Optional

from ..models import Alert, Hypothesis


class HypothesisGenerator:
    """Generate remediation hypotheses using AI models or heuristics."""

    def generate(
        self,
        alert: Alert,
        *,
        top_k: int = 3,
        user_notes: Optional[Iterable[str]] = None,
    ) -> List[Hypothesis]:
        raise NotImplementedError


class RuleBasedHypothesisGenerator(HypothesisGenerator):
    """Placeholder generator using heuristic signals until AI integration is ready."""

    def generate(
        self,
        alert: Alert,
        *,
        top_k: int = 3,
        user_notes: Optional[Iterable[str]] = None,
    ) -> List[Hypothesis]:
        notes = list(user_notes or [])
        base_hypotheses: List[Hypothesis] = []

        service = alert.labels.get("service") or alert.labels.get("job") or "unknown-service"
        env = alert.labels.get("env", "unknown")
        severity = alert.labels.get("severity", alert.severity)
        summary = alert.annotations.get("summary", "")
        description = alert.annotations.get("description", "")

        # Hypothesis 1: roll-out or deployment issues
        base_hypotheses.append(
            Hypothesis(
                title=f"최근 배포 이상으로 인한 {service} 서비스 장애",
                confidence=0.6 if severity == "critical" else 0.4,
                rationale=(
                    "서비스 라벨과 심각도를 기반으로 최근 배포/설정 변경 여부 확인이 필요합니다."
                ),
                signals={
                    "service": service,
                    "env": env,
                    "severity": severity,
                    "summary": summary,
                },
            )
        )

        # Hypothesis 2: downstream dependency saturation
        base_hypotheses.append(
            Hypothesis(
                title="다운스트림 의존성 혹은 외부 API 응답 지연",
                confidence=0.5,
                rationale="HTTP 오류율/CPU 스파이크는 외부 의존성 문제와 연관될 수 있습니다.",
                signals={
                    "description": description,
                    "notes": notes,
                },
            )
        )

        # Hypothesis 3: 인프라 자원 문제
        base_hypotheses.append(
            Hypothesis(
                title="인프라 자원 (CPU/메모리) 부족으로 인한 성능 저하",
                confidence=0.55 if "cpu" in service.lower() or "cpu" in description.lower() else 0.35,
                rationale="CPU/메모리 지표 점검 및 오토스케일링 정책 확인 필요",
                signals={
                    "service": service,
                    "user_notes": notes,
                },
            )
        )

        # Blend in user-provided insights to adjust confidence
        if notes:
            for hyp in base_hypotheses:
                hyp.signals.setdefault("user_notes", notes)
                hyp.confidence = min(0.95, hyp.confidence + 0.05)

        return base_hypotheses[:top_k]
