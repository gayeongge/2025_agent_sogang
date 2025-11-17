"""FastAPI application exposing the incident console backend."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.backend.actions import ActionExecutionService
from src.backend.fake_actions_api import fake_actions_app
from src.backend.monitor import PrometheusMonitor
from src.backend.rag import RAGService, rag_service
from src.backend.services import (
    AlertService,
    PrometheusService,
    SlackService,
    serialize_action_execution,
)
from src.backend.state import STATE, STATE_LOCK
from src.incident_console.errors import IntegrationError
from src.incident_console.models import PrometheusSettings, SlackSettings

slack_service = SlackService()
prom_service = PrometheusService()
alert_service = AlertService()
action_service = ActionExecutionService()
monitor = PrometheusMonitor(
    prom_service,
    alert_service,
    slack_service,
    action_service,
)
rag_service.bootstrap_scenarios(STATE.scenarios)


class SlackSettingsPayload(BaseModel):
    token: str = Field(..., description="Bot token with chat:write scope")
    channel: str = Field("#ops-incident", description="Default Slack channel")
    workspace: str = Field("", description="Expected Slack workspace domain")


class SlackDispatchPayload(BaseModel):
    channel: str | None = Field(None, description="Override Slack channel")


class PrometheusSettingsPayload(BaseModel):
    url: str = Field(..., description="Base URL to the Prometheus instance")
    http_query: str = Field(..., description="Query for HTTP error rate")
    http_threshold: str = Field("0.05", description="Max allowed http error rate")
    cpu_query: str = Field(..., description="Query for CPU usage")
    cpu_threshold: str = Field("0.80", description="Max allowed CPU usage")


class PrometheusTestPayload(BaseModel):
    url: str
    http_query: str
    cpu_query: str


class NotificationPreferencePayload(BaseModel):
    slack: bool = True


ALLOWED_RAG_UPLOAD_SUFFIXES = {".json", ".txt"}


app = FastAPI(title="Incident Response Console Backend", version="0.2.0")
app.mount("/action-simulator", fake_actions_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _handle_errors(fn):
    try:
        return fn()
    except IntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _parse_uploaded_json_documents(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        documents = payload
    elif isinstance(payload, dict):
        doc_list = payload.get("documents")
        if isinstance(doc_list, list):
            documents = doc_list
        else:
            documents = [payload]
    else:
        raise ValueError("Uploaded JSON must be an object or an array of objects.")

    normalized: list[dict[str, object]] = []
    for entry in documents:
        if not isinstance(entry, dict):
            raise ValueError("Uploaded JSON documents must contain objects.")
        normalized.append(entry)

    if not normalized:
        raise ValueError("Uploaded JSON file does not contain any documents.")
    return normalized


def _normalize_uploaded_entry(
    entry: dict[str, object],
    *,
    fallback_title: str,
    filename: str,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    entry_metadata = entry.get("metadata")
    if isinstance(entry_metadata, dict):
        metadata.update(entry_metadata)

    for key in (
        "title",
        "summary",
        "scenario_code",
        "status",
        "type",
        "recovery_status",
        "actions",
        "created_at",
    ):
        value = entry.get(key)
        if value is not None and key not in metadata:
            metadata[key] = value

    metadata["source_filename"] = filename
    title_value = metadata.get("title")
    if not isinstance(title_value, str) or not title_value.strip():
        metadata["title"] = fallback_title or "Uploaded RAG reference"

    content: str | None = None
    for field in ("content", "text", "body"):
        candidate = entry.get(field)
        if isinstance(candidate, str) and candidate.strip():
            content = candidate
            break

    if not content:
        raise ValueError("JSON document must include a 'content' or 'text' field.")

    return {
        "title": metadata["title"],
        "content": content,
        "metadata": metadata,
    }


def _ingest_rag_upload(
    filename: str,
    suffix: str,
    text: str,
    *,
    service: RAGService | None = None,
) -> list[str]:
    target = service or rag_service
    base_title = Path(filename).stem or "Uploaded RAG reference"
    if suffix == ".txt":
        if not text.strip():
            raise ValueError("Uploaded document is empty.")
        doc_key = target.add_uploaded_document(
            title=base_title,
            content=text,
            metadata={"source_filename": filename},
        )
        return [doc_key]

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Uploaded JSON file is not valid.") from exc

    documents = _parse_uploaded_json_documents(payload)
    doc_keys: list[str] = []
    for entry in documents:
        normalized = _normalize_uploaded_entry(
            entry,
            fallback_title=base_title,
            filename=filename,
        )
        doc_key = target.add_uploaded_document(
            title=normalized["title"],
            content=normalized["content"],
            metadata=normalized["metadata"],
        )
        doc_keys.append(doc_key)
    return doc_keys


@app.on_event("startup")
async def _startup() -> None:
    monitor.start()


@app.on_event("shutdown")
async def _shutdown() -> None:
    monitor.stop()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/state")
def get_state() -> dict[str, object]:
    return alert_service.get_state()


@app.get("/rag/documents")
def get_rag_documents() -> dict[str, object]:
    return {"documents": rag_service.list_documents()}


@app.post("/rag/upload")
async def upload_rag_document(file: UploadFile = File(...)) -> dict[str, object]:
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_RAG_UPLOAD_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only .json or .txt files are supported.")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Uploaded file must be UTF-8 encoded.") from exc

    try:
        doc_keys = _ingest_rag_upload(filename, suffix, decoded)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "message": f"Uploaded {len(doc_keys)} RAG document(s).",
        "documents": doc_keys,
    }


@app.post("/alerts/trigger")
def trigger_alert() -> dict[str, object]:
    payload = alert_service.trigger()
    payload["verify_enabled"] = True
    return payload


@app.post("/alerts/verify")
def verify_recovery() -> dict[str, object]:
    return _handle_errors(prom_service.verify)


@app.post("/slack/test")
def slack_test(payload: SlackSettingsPayload) -> dict[str, object]:
    return _handle_errors(lambda: slack_service.test(payload.token))


@app.post("/slack/save")
def slack_save(payload: SlackSettingsPayload) -> dict[str, str]:
    settings = SlackSettings(
        token=payload.token.strip(),
        channel=payload.channel.strip() or "#ops-incident",
        workspace=payload.workspace.strip(),
    )
    message = slack_service.save(settings)
    return {"message": message}


@app.post("/slack/dispatch")
def slack_dispatch(payload: SlackDispatchPayload) -> dict[str, object]:
    scenario = alert_service.require_last_alert()
    return _handle_errors(lambda: slack_service.dispatch(scenario, payload.channel))


@app.post("/prometheus/test")
def prometheus_test(payload: PrometheusTestPayload) -> dict[str, float]:
    settings = PrometheusSettings(
        url=payload.url.strip(),
        http_query=payload.http_query.strip(),
        http_threshold="0.05",
        cpu_query=payload.cpu_query.strip(),
        cpu_threshold="0.80",
    )
    return _handle_errors(lambda: prom_service.test(settings))


@app.post("/prometheus/save")
def prometheus_save(payload: PrometheusSettingsPayload) -> dict[str, str]:
    settings = PrometheusSettings(
        url=payload.url.strip(),
        http_query=payload.http_query.strip(),
        http_threshold=payload.http_threshold.strip() or "0.05",
        cpu_query=payload.cpu_query.strip(),
        cpu_threshold=payload.cpu_threshold.strip() or "0.80",
    )
    message = _handle_errors(lambda: prom_service.save(settings))
    return {"message": message}


@app.post("/notifications/preferences")
def update_notification_preferences(
    payload: NotificationPreferencePayload,
) -> dict[str, bool]:
    with STATE_LOCK:
        STATE.preferences.slack = payload.slack
        current = {
            "slack": STATE.preferences.slack,
        }
    return current


@app.post("/actions/{execution_id}/execute")
def execute_action_plan(execution_id: str) -> dict[str, object]:
    execution = _handle_errors(lambda: action_service.execute_pending(execution_id))
    return {"execution": serialize_action_execution(execution)}


@app.post("/actions/{execution_id}/defer")
def defer_action_plan(execution_id: str) -> dict[str, object]:
    execution = _handle_errors(lambda: action_service.defer_execution(execution_id))
    return {"execution": serialize_action_execution(execution)}


@app.post("/notifications/pending/{report_id}/ack")
def acknowledge_pending_report(report_id: str) -> dict[str, str]:
    with STATE_LOCK:
        STATE.pending_reports = [
            report for report in STATE.pending_reports if report.id != report_id
        ]
    return {"status": "acknowledged", "report_id": report_id}
