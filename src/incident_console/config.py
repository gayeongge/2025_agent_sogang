"""환경 변수/.env 설정 로더."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _PROJECT_ROOT / ".env"

# .env가 존재하면 우선 로드 (없어도 조용히 무시)
load_dotenv(_ENV_PATH, override=False)

_OPENAI_API_KEY_OVERRIDE: str | None = None


@lru_cache(maxsize=1)
def _load_env_openai_api_key() -> str | None:
    """Read the OpenAI key from the environment only once."""

    return os.getenv("OPENAI_API_KEY")


def get_openai_api_key() -> str | None:
    """Return OPENAI_API_KEY from runtime override or environment."""

    if _OPENAI_API_KEY_OVERRIDE:
        return _OPENAI_API_KEY_OVERRIDE
    return _load_env_openai_api_key()


def set_openai_api_key(value: str | None) -> None:
    """Override the OpenAI API key at runtime (empty clears override)."""

    global _OPENAI_API_KEY_OVERRIDE
    sanitized = (value or "").strip()
    _OPENAI_API_KEY_OVERRIDE = sanitized or None
