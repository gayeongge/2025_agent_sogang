"""Incident analysis generator using OpenAI (with deterministic fallback)."""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Dict, List

from src.incident_console.config import get_openai_api_key
from src.incident_console.models import AlertScenario
from src.backend.state import MetricSample

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

SYSTEM_PROMPT = """
당신은 SRE 팀의 사고 분석가입니다. 제공된 모니터링 결과를 바탕으로 사고의 원인, 영향을 받은 영역,
즉시 실행할 조치와 후속 조치를 논리적으로 분석해서 상세 보고서를 작성하세요.

필수 포함 사항:
1. Summary: 사고 상황과 임계값 초과 사실을 2~3문장으로 요약
2. Root Cause: 가능한 근본 원인을 구체적으로 설명 (가설이라면 추정임을 명시)
3. Impact: 고객/시스템에 미치는 영향
4. Action Plan: 실행 가능한 조치 항목 목록 (각 항목에 "이유"를 덧붙일 것)
5. Follow-up: 추가로 검토해야 할 항목 1~2개

응답 형식은 아래 JSON 스키마를 따르세요.
{
  "summary": "...",
  "root_cause": "...",
  "impact": "...",
  "action_plan": ["..."],
  "follow_up": ["..."]
}

한국어로 작성하세요.
"""


def _build_user_prompt(scenario: AlertScenario, sample: MetricSample) -> str:
    hypotheses = "\n".join(f"- {item}" for item in scenario.hypotheses)
    evidences = "\n".join(f"- {item}" for item in scenario.evidences)
    actions = "\n".join(f"- {item}" for item in scenario.actions)
    return dedent(
        f"""
        Incident Title: {scenario.title}
        Source Metric: {scenario.source}
        Detected At (UTC): {sample.timestamp}
        HTTP Error Rate: {sample.http:.4f} (threshold {sample.http_threshold:.4f})
        CPU Usage: {sample.cpu:.4f} (threshold {sample.cpu_threshold:.4f})

        Hypotheses:\n{hypotheses or '- (none)'}

        Evidence:\n{evidences or '- (none)'}

        Recommended Actions (playbook):\n{actions or '- (none)'}
        """
    ).strip()


def _call_openai(prompt: str) -> Dict[str, object] | None:
    api_key = get_openai_api_key()
    if not api_key or OpenAI is None:
        return None

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-4o-mini",
        temperature=0.3,
        max_output_tokens=900,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    text = response.output_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _fallback_analysis(scenario: AlertScenario, sample: MetricSample) -> Dict[str, object]:
    summary = (
        f"{sample.timestamp} UTC 기준으로 '{scenario.title}' 경로에서 HTTP 오류율이 "
        f"임계값 {sample.http_threshold:.2f}을 초과했고, CPU 사용률도 {sample.cpu:.2f}까지 상승했습니다."
    )
    root_cause = (
        scenario.hypotheses[0]
        if scenario.hypotheses
        else "수집된 가설이 없어 추가 조사가 필요합니다."
    )
    impact = "지속될 경우 사용자 응답 지연 및 장애로 번질 위험이 있습니다."
    action_plan = [
        scenario.actions[0] if scenario.actions else "대응 절차를 수립하십시오.",
        "Prometheus 대시보드와 서비스 로그를 확인해 추가 지표 이상 여부를 점검하십시오.",
    ]
    follow_up = ["배포/인프라 변경 이력을 검토해 관련성이 있는지 확인"]
    return {
        "summary": summary,
        "root_cause": root_cause,
        "impact": impact,
        "action_plan": action_plan,
        "follow_up": follow_up,
    }


def _build_report_text(analysis: Dict[str, object], scenario: AlertScenario, sample: MetricSample) -> str:
    action_lines = analysis.get("action_plan") or []
    follow_lines = analysis.get("follow_up") or []
    actions_text = "\n".join(f"- {item}" for item in action_lines) if action_lines else "- (미정)"
    follow_text = "\n".join(f"- {item}" for item in follow_lines) if follow_lines else "- (미정)"
    return dedent(
        f"""
        Incident: {scenario.title}
        Detected (UTC): {sample.timestamp}
        Metrics: HTTP {sample.http:.4f}/{sample.http_threshold:.4f}, CPU {sample.cpu:.4f}/{sample.cpu_threshold:.4f}

        Summary:
        {analysis.get('summary', '요약 정보가 준비되지 않았습니다.')}

        Root Cause:
        {analysis.get('root_cause', '근본 원인 분석이 필요합니다.')}

        Impact:
        {analysis.get('impact', '영향 범위를 파악 중입니다.')}

        Action Plan:
        {actions_text}

        Follow-up:
        {follow_text}
        """
    ).strip()


def generate_incident_analysis(
    scenario: AlertScenario, sample: MetricSample
) -> Dict[str, object]:
    prompt = _build_user_prompt(scenario, sample)
    analysis = _call_openai(prompt)
    if not analysis:
        analysis = _fallback_analysis(scenario, sample)

    action_plan = analysis.get("action_plan") or []
    follow_up = analysis.get("follow_up") or []
    if isinstance(action_plan, str):
        action_plan = [action_plan]
    if isinstance(follow_up, str):
        follow_up = [follow_up]

    normalized = {
        "summary": analysis.get("summary", ""),
        "root_cause": analysis.get("root_cause", ""),
        "impact": analysis.get("impact", ""),
        "action_plan": action_plan,
        "follow_up": follow_up,
    }
    report_text = _build_report_text(normalized, scenario, sample)
    return {
        **normalized,
        "report_text": report_text,
    }
