"""Incident analysis generator using OpenAI (with deterministic fallback)."""

from __future__ import annotations

import json
import logging
from textwrap import dedent
from typing import Dict

from src.incident_console.config import get_openai_api_key
from src.incident_console.models import AlertScenario
from src.backend.state import MetricSample

logger = logging.getLogger("incident.analysis")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[incident.analysis] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

try:
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional dependency
    AgentExecutor = None  # type: ignore
    create_openai_functions_agent = None  # type: ignore
    ChatOpenAI = None  # type: ignore
    ChatPromptTemplate = None  # type: ignore
    MessagesPlaceholder = None  # type: ignore

SYSTEM_PROMPT = (
    "당신은 SRE 사고 분석가입니다. 제공된 모니터링 결과를 바탕으로 사고의 원인, 영향 범위, "
    "즉시 수행할 조치와 후속 조치를 정리하는 분석 보고서를 작성하세요.\n\n"
    "필수 포함 사항:\n"
    "1. Summary: 사고 상황과 임계치 초과 사실을 2~3문장으로 요약\n"
    "2. Root Cause: 가능한 근본 원인을 구체적으로 설명 (가설이면 추정을 명시)\n"
    "3. Impact: 고객/서비스에 미치는 영향\n"
    "4. Action Plan: 수행 가능한 조치 항목 목록 (각 항목에 \"사유\"를 붙여주세요)\n"
    "5. Follow-up: 추후 점검해야 할 항목 1~2개\n"
    "응답 형식은 아래 JSON 스키마를 따르세요.\n"
    "{\n"
    "  \"summary\": \"...\",\n"
    "  \"root_cause\": \"...\",\n"
    "  \"impact\": \"...\",\n"
    "  \"action_plan\": [\"...\"],\n"
    "  \"follow_up\": [\"...\"]\n"
    "}\n\n"
    "반드시 한국어로 작성하세요."
)


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
    if not api_key:
        return None
    if not all(
        dependency is not None
        for dependency in (
            ChatOpenAI,
            create_openai_functions_agent,
            ChatPromptTemplate,
            MessagesPlaceholder,
        )
    ):
        return None

    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=900,
            openai_api_key=api_key,
        )

        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )
        agent = create_openai_functions_agent(llm, [], prompt_template)
        executor = AgentExecutor(agent=agent, tools=[], verbose=False)

        logger.info("AI한테 질의했다: %s", prompt)
        result = executor.invoke({"input": prompt, "chat_history": []})
        logger.info("LangChain raw result: %r", result)

        output = ""
        if isinstance(result, dict):
            candidate = result.get("output")
            if not candidate and isinstance(result.get("return_values"), dict):
                candidate = result["return_values"].get("output")
            if candidate:
                output = str(candidate).strip()
        elif result is not None:
            output = str(result).strip()

        if not output and isinstance(result, dict):
            # 일부 LangChain 버전은 intermediate_steps에 최종 응답을 포함함
            steps = result.get("intermediate_steps")
            if isinstance(steps, list) and steps:
                output = str(steps[-1]).strip()

        logger.info("AI raw output string (pre-parse): %s", output)

        if not output:
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 문자열에서 JSON만 추출 시도
            start = output.find('{')
            end = output.rfind('}')
            if start != -1 and end != -1 and start < end:
                fragment = output[start : end + 1]
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    logger.info("AI 응답 JSON 파싱 실패: %s", output)
                    return None
            logger.info("AI 응답 JSON 파싱 실패: %s", output)
            return None
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("LangChain 에이전트 호출 실패")
        return None


def _fallback_analysis(scenario: AlertScenario, sample: MetricSample) -> Dict[str, object]:
    summary = (
        f"{sample.timestamp} UTC 기준으로 '{scenario.title}' 경로에서 HTTP 오류율이 "
        f"임계값 {sample.http_threshold:.2f}를 초과했고, CPU 사용률도 {sample.cpu:.2f}까지 상승했습니다."
    )
    root_cause = (
        scenario.hypotheses[0]
        if scenario.hypotheses
        else "추가 조사가 필요합니다."
    )
    impact = "지속될 경우 사용자 응답 지연과 서비스 장애로 번질 위험이 있습니다."
    action_plan = [
        scenario.actions[0] if scenario.actions else "비상 대응 절차를 수립하세요.",
        "Prometheus 지표와 애플리케이션 로그를 점검해 추가 이상 징후를 확인하세요.",
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
        logger.info("AI 연결 실패, 기본 템플릿으로 대체합니다.")
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