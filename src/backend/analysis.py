"""Incident analysis generator using OpenAI (with deterministic fallback)."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
import sys
from textwrap import dedent
from typing import Dict, List

from src.backend.rag import rag_service
from src.backend.state import MetricSample
from src.backend.text_utils import normalize_legacy_payload
from src.incident_console.config import get_openai_api_key
from src.incident_console.models import AlertScenario

logger = logging.getLogger("incident.analysis")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[incident.analysis] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

try:
    from langchain_core.tools import Tool
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional dependency
    Tool = None  # type: ignore
    ChatOpenAI = None  # type: ignore

try:
    from langgraph.prebuilt import create_react_agent as langgraph_create_react_agent
except ImportError:  # pragma: no cover - optional dependency
    langgraph_create_react_agent = None  # type: ignore

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

def _build_user_prompt(
    scenario: AlertScenario,
    sample: MetricSample,
    rag_context: str | None = None,
) -> str:
    hypotheses = "\n".join(f"- {item}" for item in scenario.hypotheses)
    evidences = "\n".join(f"- {item}" for item in scenario.evidences)
    actions = "\n".join(f"- {item}" for item in scenario.actions)
    context_block = (
        f"\n\nRAG_CONTEXT:\n{rag_context.strip()}"
        if rag_context and rag_context.strip()
        else ""
    )
    return (
        dedent(
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
        + context_block
    )


def _prioritize_actions(
    preferred: Sequence[str] | None,
    existing: Sequence[str] | None,
) -> List[str]:
    ordered: List[str] = []
    seen: set[str] = set()

    for source in (preferred or []), (existing or []):
        for action in source:
            if not isinstance(action, str):
                continue
            stripped = action.strip()
            if not stripped:
                continue
            if stripped not in seen:
                ordered.append(stripped)
                seen.add(stripped)
    return ordered

def _build_rag_tool(scenario: AlertScenario) -> Tool | None:
    if Tool is None:
        return None

    def _search(query: str) -> str:
        base_query = (query or "").strip() or " ".join(
            filter(
                None,
                [
                    scenario.title,
                    scenario.description,
                    scenario.source,
                    " ".join(scenario.actions),
                ],
            )
        )
        documents = rag_service.search(
            base_query,
            limit=4,
            metadata_filter={"scenario_code": scenario.code},
        )
        if not documents:
            documents = rag_service.search(base_query, limit=4)

        if not documents:
            recent = rag_service.recent_actions(scenario.code, status="executed", limit=4)
            if recent:
                lines = ["최근 승인된 조치:"]
                lines.extend(f"- {item}" for item in recent)
                return "\n".join(lines)
            return "관련된 RAG 조치 이력을 찾지 못했습니다."

        lines = ["과거 RAG 조치 요약:"]
        for doc in documents:
            metadata = getattr(doc, "metadata", {}) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            title = metadata.get("title") or scenario.title
            status = metadata.get("status") or metadata.get("type") or "reference"
            created_at = metadata.get("created_at") or ""
            summary = metadata.get("summary") or getattr(doc, "page_content", "").replace("\n", " ")[:200]
            header = f"- [{status}] {title}"
            if created_at:
                header += f" ({created_at})"
            lines.append(header)
            actions = metadata.get("actions")
            added = False
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, str) and action.strip():
                        lines.append(f"    · {action.strip()}")
                        added = True
            if not added and summary:
                lines.append(f"    · {summary}")
        return "\n".join(lines)

    return Tool(
        name="incident_rag_lookup",
        func=_search,
        description=(
            "현재 시나리오와 유사한 과거 보고/승인 조치를 RAG 데이터베이스에서 조회합니다. "
            "필요한 조치 힌트를 얻고 싶을 때 한국어로 질문하세요."
        ),
    )



class _LangGraphAgentExecutor:
    """Shim so LangGraph runnables mimic the AgentExecutor API."""

    def __init__(self, runnable) -> None:
        self._runnable = runnable

    def invoke(self, payload: Dict[str, object]) -> Dict[str, object]:
        if isinstance(payload, dict) and "messages" in payload:
            return self._runnable.invoke(payload)

        query = ""
        if isinstance(payload, dict):
            raw = payload.get("input") or payload.get("prompt") or ""
            query = str(raw)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        return self._runnable.invoke({"messages": messages})


def _build_agent_executor(llm: ChatOpenAI, tools: List[Tool]):
    if langgraph_create_react_agent is None:
        return None

    graph_agent = langgraph_create_react_agent(llm, tools)
    return _LangGraphAgentExecutor(graph_agent)


def _extract_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if hasattr(value, "content"):
        return _extract_text(getattr(value, "content"))
    if isinstance(value, dict):
        for key in ("content", "text", "observation", "output"):
            if key in value:
                return _extract_text(value[key])
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            chunk = _extract_text(item)
            if chunk:
                parts.append(chunk)
        return "\n".join(parts).strip()
    if isinstance(value, tuple):
        if len(value) >= 2:
            return _extract_text(value[1])
        return _extract_text(value[0])
    return str(value).strip()


def _call_openai(scenario: AlertScenario, prompt: str) -> Dict[str, object] | None:
    api_key = get_openai_api_key()
    if not api_key:
        return None
    if ChatOpenAI is None or Tool is None:
        logger.info("Missing LangChain/LangGraph dependencies.")
        return None
    
    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=900,
            openai_api_key=api_key,
        )

        tools: List[Tool] = []
        rag_tool = _build_rag_tool(scenario)
        if rag_tool:
            tools.append(rag_tool)

        agent_executor = _build_agent_executor(llm, tools)
        if agent_executor is None:
            logger.info("Missing LangChain/LangGraph dependencies.")
            return None

        logger.info("AI prompt submitted: %s", prompt)
        result = agent_executor.invoke(
            {
                "input": f"{SYSTEM_PROMPT}\n\n{prompt}",
                "chat_history": [],
            }
        )
        logger.info("Agent raw result: %r", result)

        output = ""
        if isinstance(result, dict):
            candidate = result.get("output")
            if not candidate and isinstance(result.get("return_values"), dict):
                candidate = result["return_values"].get("output")
            if not candidate:
                messages = result.get("messages")
                if isinstance(messages, list) and messages:
                    candidate = _extract_text(messages[-1])
            if candidate:
                output = _extract_text(candidate)
        elif result is not None:
            output = _extract_text(result)

        if not output and isinstance(result, dict):
            # Some LangGraph executors only return text via intermediate_steps
            steps = result.get("intermediate_steps")
            if isinstance(steps, list) and steps:
                for step in reversed(steps):
                    candidate = _extract_text(step)
                    if candidate:
                        output = candidate
                        break

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
                    logger.info("AI JSON parsing failed: %s", output)
                    return None
            logger.info("AI JSON parsing failed: %s", output)
            return None
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("Agent invocation failed")
        return None


def _fallback_analysis(
    scenario: AlertScenario,
    sample: MetricSample,
    preferred_actions: Sequence[str] | None = None,
) -> Dict[str, object]:
    summary = (
        f"{sample.timestamp} UTC에 '{scenario.title}' 시나리오가 감지되었습니다. "
        f"HTTP 오류율이 임계값 {sample.http_threshold:.2f}을(를) 초과했고 "
        f"CPU 사용률이 {sample.cpu:.2f}까지 상승했습니다."
    )
    root_cause = (
        scenario.hypotheses[0]
        if scenario.hypotheses
        else "가능한 근본 원인을 아직 특정하지 못했습니다."
    )
    impact = "이번 장애로 인해 주요 요청 실패와 지연이 발생했을 가능성이 있습니다."

    prioritized_actions: List[str] = []
    seen = set()
    for action in preferred_actions or []:
        stripped = action.strip()
        if stripped and stripped not in seen:
            prioritized_actions.append(stripped)
            seen.add(stripped)
    for action in scenario.actions:
        stripped = action.strip()
        if stripped and stripped not in seen:
            prioritized_actions.append(stripped)
            seen.add(stripped)
    final_action = "Prometheus 대시보드에서 최근 배포와 메트릭 변화를 교차 확인하세요."
    if not prioritized_actions:
        prioritized_actions = [
            "조치 플레이북의 초기 점검 절차를 수행하세요.",
            final_action,
        ]
    elif final_action not in prioritized_actions:
        prioritized_actions.append(final_action)

    follow_up = ["사후 분석 회의를 열고 근본 원인과 재발 방지 대책을 문서화하세요."]
    return normalize_legacy_payload(
        {
            "summary": summary,
            "root_cause": root_cause,
            "impact": impact,
            "action_plan": prioritized_actions,
            "follow_up": follow_up,
        }
    )



def _build_report_text(analysis: Dict[str, object], scenario: AlertScenario, sample: MetricSample) -> str:
    action_lines = analysis.get("action_plan") or []
    follow_lines = analysis.get("follow_up") or []
    if isinstance(action_lines, str):
        action_lines = [action_lines]
    if isinstance(follow_lines, str):
        follow_lines = [follow_lines]
    actions_text = "\n".join(f"- {item}" for item in action_lines) if action_lines else "- (추가 실행 계획 없음)"
    follow_text = "\n".join(f"- {item}" for item in follow_lines) if follow_lines else "- (추가 후속 조치 없음)"
    return dedent(
        f"""
        Incident: {scenario.title}
        Detected (UTC): {sample.timestamp}
        Metrics: HTTP {sample.http:.4f}/{sample.http_threshold:.4f}, CPU {sample.cpu:.4f}/{sample.cpu_threshold:.4f}

        Summary:
        {analysis.get('summary', '요약 정보를 생성하지 못했습니다.')}

        Root Cause:
        {analysis.get('root_cause', '근본 원인을 추정하지 못했습니다.')}

        Impact:
        {analysis.get('impact', '영향 범위를 파악하지 못했습니다.')}

        Action Plan:
        {actions_text}

        Follow-up:
        {follow_text}
        """
    ).strip()

def generate_incident_analysis(
    scenario: AlertScenario, sample: MetricSample
) -> Dict[str, object]:
    approved_actions = rag_service.recent_actions(scenario.code)
    rag_context = rag_service.build_context_for_scenario(scenario)
    prompt = _build_user_prompt(scenario, sample, rag_context)
    analysis = _call_openai(scenario, prompt)
    logger.info("AI analysis result: %r", analysis)
    analysis = normalize_legacy_payload(analysis) if analysis else analysis
    if not analysis:
        logger.info("AI call unavailable; using deterministic fallback.")
        analysis = _fallback_analysis(
            scenario,
            sample,
            preferred_actions=approved_actions,
        )
    else:
        candidate_actions = analysis.get("action_plan") or []
        if isinstance(candidate_actions, str):
            candidate_actions = [candidate_actions]
        prioritized = _prioritize_actions(
            approved_actions,
            candidate_actions if isinstance(candidate_actions, Sequence) else [],
        )
        if prioritized:
            analysis["action_plan"] = prioritized

    action_plan = analysis.get("action_plan") or []
    follow_up = analysis.get("follow_up") or []
    if isinstance(action_plan, str):
        action_plan = [action_plan]
    if isinstance(follow_up, str):
        follow_up = [follow_up]

    prioritized_plan = _prioritize_actions(
        approved_actions,
        action_plan if isinstance(action_plan, Sequence) else [],
    )
    if not prioritized_plan:
        prioritized_plan = list(scenario.actions)
    action_plan = prioritized_plan
    analysis["action_plan"] = action_plan

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




