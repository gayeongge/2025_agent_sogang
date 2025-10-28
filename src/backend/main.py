"""CLI entrypoint for launching the FastAPI backend."""

from __future__ import annotations

import os
from typing import Any

import uvicorn


def run() -> None:
    host = os.getenv("INCIDENT_BACKEND_HOST", "127.0.0.1")
    # Electron 앱과 포트를 다르게 하기 위해 기본값을 8001로 사용한다.
    port = int(os.getenv("INCIDENT_BACKEND_PORT", "8001"))
    reload = os.getenv("INCIDENT_BACKEND_RELOAD", "0") == "1"
    uvicorn.run(
        "src.backend.app:app",
        host=host,
        port=port,
        reload=reload,
        factory=False,
        log_level=os.getenv("INCIDENT_BACKEND_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    run()
