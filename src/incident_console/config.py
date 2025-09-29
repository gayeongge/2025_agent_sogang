"""환경 변수 및 .env 설정 로더."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _PROJECT_ROOT / ".env"

# .env가 있으면 우선 로드 (없어도 조용히 무시)
load_dotenv(_ENV_PATH, override=False)


@lru_cache(maxsize=1)
def get_openai_api_key() -> str | None:
    """OPENAI_API_KEY 값을 반환한다 (.env → 환경 변수 순).

    Returns:
        str | None: 설정된 API 키. 없으면 None.
    """
    return os.getenv("OPENAI_API_KEY")
