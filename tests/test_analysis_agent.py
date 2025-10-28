import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend import analysis
from src.backend.state import MetricSample
from src.incident_console.models import AlertScenario


@pytest.mark.integration
def test_generate_incident_analysis_real_agent(caplog):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is required for this integration test")

    caplog.set_level("INFO", logger=analysis.logger.name)

    scenario = AlertScenario(
        code="SREAL",
        title="실제 에이전트 테스트",
        source="http_error_rate",
        description="통합 테스트용 시나리오",
        hypotheses=["최근 배포로 인한 오류 가능"],
        evidences=["에러율 급증"],
        actions=["롤백 검토", "오토스케일 조정"],
    )
    sample = MetricSample(
        timestamp="2025-01-01T00:00:00Z",
        http=0.18,
        http_threshold=0.05,
        cpu=0.83,
        cpu_threshold=0.80,
    )

    result = analysis.generate_incident_analysis(scenario, sample)

    assert isinstance(result, dict)
    for key in ("summary", "root_cause", "impact", "action_plan", "follow_up", "report_text"):
        assert key in result
        assert result[key]

    assert isinstance(result["action_plan"], list)
    assert isinstance(result["follow_up"], list)

    combined_logs = " ".join(entry.message for entry in caplog.records)
    assert "AI한테 질의했다" in combined_logs
    assert "LangChain raw result" in combined_logs
    assert "AI raw output string" in combined_logs


