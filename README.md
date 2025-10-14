﻿# Incident Response Console

Electron desktop UI backed by a Python FastAPI service that simulates the first-responder workflow for Prometheus alerts. The app keeps the MVP features from `order.md` (F1-F4): firing a runbook scenario, inspecting hypotheses/evidence, dispatching Slack notifications, opening Jira issues, and verifying recovery with Prometheus queries.

## Architecture

```
src/
  main.py                         # python -m src.main -> launches FastAPI backend
  backend/
    app.py                        # FastAPI routes (alerts, Slack, Jira, Prometheus)
    services.py                   # Business logic & shared state helpers
    state.py                      # In-memory state used by the API
    main.py                       # uvicorn runner (reads INCIDENT_BACKEND_* env vars)
  incident_console/
    models.py | scenarios.py      # Core domain models & sample incident scenarios
    integrations/                 # Slack/Jira/Prometheus HTTP clients (requests based)
    errors.py                     # Shared IntegrationError type
    utils.py                      # Shared helpers (time format, threshold parsing)
electron/
  package.json                    # npm metadata (Electron runtime)
  main.js | preload.js            # Desktop shell + Python backend bootstrapper
  renderer/                       # HTML/CSS/JS front-end that talks to the API
prometheus/
  README.md                       # Local Prometheus setup & sample metrics feeder
  sample_metrics_service.py       # Generates deterministic threshold breaches
scripts/
  setup_env.py                    # Creates venv and installs Python dependencies
```

## Operator Guides

- See `SETUP.md` for platform-specific setup, launch, and UI guidance.

## Prerequisites

- Python 3.10+
- Node.js 18+ (Electron runtime)
- Slack/Jira/Prometheus credentials if you want to hit real APIs
- (Optional) OpenAI API key (OPENAI_API_KEY) to enable AI 기반 사고 분석 보고서를 생성합니다

## Backend setup

```bash
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt  # Windows
# or
source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
```

Configuration values (e.g. `OPENAI_API_KEY`, integration tokens) can still be stored in `.env` at the project root.

## Electron UI setup

```bash
cd electron
npm install
npm run start  # spawns python -m src.backend.main and opens the desktop window
```

The Electron launcher automatically starts the FastAPI backend (default `http://127.0.0.1:8000`). When you close the desktop window the Python process is stopped as well.

### Running services independently

You can also run each layer by hand:

```bash
# Terminal 1 - backend only
python -m src.backend.main
# Server answers on http://127.0.0.1:8000

# Terminal 2 - just open the renderer without auto-spawning python
cd electron
INCIDENT_BACKEND_HOST=127.0.0.1 INCIDENT_BACKEND_PORT=8000 npm start
```

## Key API routes

| Method | Route               | Purpose                              |
| ------ | ------------------- | ------------------------------------ |
| POST   | `/alerts/trigger`   | Pick one of the demo scenarios and populate the feed/hypotheses/actions |
| POST   | `/alerts/verify`    | Run Prometheus instant queries with stored thresholds |
| POST   | `/slack/test`       | `auth.test` connectivity check       |
| POST   | `/slack/save`       | Persist Slack defaults in memory     |
| POST   | `/slack/dispatch`   | Send the most recent scenario to Slack |
| POST   | `/jira/test`        | Fetch project metadata using REST API |
| POST   | `/jira/save`        | Persist Jira settings                |
| POST   | `/jira/create`      | Create a Task issue for last alert   |
| POST   | `/prometheus/test`  | Run HTTP + CPU queries once          |
| POST   | `/prometheus/save`  | Persist Prometheus settings          |
| GET    | `/state`            | Dump current in-memory settings, feed, and last alert |
| GET    | `/health`           | Liveness probe used by Electron boot |

All responses are JSON; errors use FastAPI Problem Details with `detail` explaining the failure (`IntegrationError` from the original code path is preserved).

## Current behaviour

- Alert triggers still choose from `scenarios.py` and prefill hypotheses/evidence/actions.
- Slack/Jira/Prometheus operations reuse the original `requests` clients, so you can point them at live services.
- The feed persists in memory while the backend is running; restart clears state.
- The Electron renderer is now the sole UI surface, featuring a bright monotone-inspired layout tuned for quick operator scans.
- A background Prometheus monitor samples metrics every few seconds, detects anomalies when at least one of the latest five samples breaches a threshold, and auto-generates incident reports.
- Notification targets (Slack/Jira) can be toggled via checkboxes; 설정이 비어 있으면 전체 보고서를 팝업으로 보여 주어 사용자가 수동으로 조치할 수 있습니다.

- OpenAI API가 설정돼 있으면 Prometheus 임계값을 초과한 시점에 AI가 원인·영향·조치 계획을 분석해 보고서 형태로 Slack/Jira 및 UI 모달에 제공합니다 (없으면 기본 규칙 기반 보고서를 사용합니다).

## Next steps

- Persist state to disk (e.g. sqlite or JSON) so settings survive restarts.
- Replace global state with dependency-injected stores to ease testing.
- Add mocked integrations/tests so CI can validate without real credentials.
- Package the Electron app (electron-builder) once distribution requirements are clear.






