"""Lightweight RAG helper backed by FAISS and OpenAI embeddings."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
from threading import Lock
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

from src.incident_console.config import get_openai_api_key
from src.incident_console.models import AlertScenario
from src.incident_console.utils import utcnow_iso
from src.backend.text_utils import normalize_legacy_payload, normalize_legacy_text

try:  # Optional dependencies are resolved at runtime
    from langchain_core.documents import Document
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
except ImportError:  # pragma: no cover - fallback when dependencies missing
    Document = None  # type: ignore[assignment]
    FAISS = None  # type: ignore[assignment]
    OpenAIEmbeddings = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from src.backend.state import ActionExecution, IncidentReport

logger = logging.getLogger("incident.rag")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[incident.rag] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class RAGService:
    """Persisted FAISS-backed document store tailored for incident actions."""

    def __init__(
        self,
        index_dir: Path,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self._index_dir = index_dir
        self._embedding_model = embedding_model
        self._lock = Lock()
        self._index_dir.mkdir(parents=True, exist_ok=True)

        self._metadata_path = self._index_dir / "documents.json"
        self._documents_by_key: Dict[str, Dict[str, object]] = {}

        self._embeddings: Optional[OpenAIEmbeddings] = None  # type: ignore[assignment]
        self._vectorstore: Optional[FAISS] = None  # type: ignore[assignment]

        self._load_documents()
        # Try to eagerly load the FAISS index; falls back to lazy rebuild.
        self._ensure_vectorstore(load_only=True)

    # ------------------------------------------------------------------ #
    # Lifecycle helpers
    # ------------------------------------------------------------------ #

    def _load_documents(self) -> None:
        if not self._metadata_path.exists():
            self._documents_by_key = {}
            return

        changed = False
        try:
            raw = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for entry in raw:
                    key = entry.get("doc_key")
                    if isinstance(key, str):
                        normalized = normalize_legacy_payload(entry)
                        if normalized != entry:
                            changed = True
                        self._documents_by_key[key] = normalized
        except Exception:  # pragma: no cover - corrupted metadata guard
            logger.exception("Failed to load persisted RAG metadata; starting empty.")
            self._documents_by_key = {}
            return

        if changed:
            self._persist_documents()

    def _persist_documents(self) -> None:
        data = list(self._documents_by_key.values())
        try:
            self._metadata_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Failed to persist RAG metadata to %s", self._metadata_path)

    def _get_embeddings(self) -> Optional[OpenAIEmbeddings]:  # type: ignore[override]
        if OpenAIEmbeddings is None:
            return None
        if self._embeddings is not None:
            return self._embeddings

        api_key = get_openai_api_key()
        if not api_key:
            logger.info("Skipping RAG embeddings setup (OPENAI_API_KEY missing).")
            return None

        try:
            self._embeddings = OpenAIEmbeddings(
                model=self._embedding_model,
                openai_api_key=api_key,
            )
        except Exception:  # pragma: no cover - API/SDK failure guard
            logger.exception("Failed to initialise OpenAI embeddings for RAG.")
            self._embeddings = None
        return self._embeddings

    def _ensure_vectorstore(self, load_only: bool = False) -> Optional[FAISS]:  # type: ignore[override]
        if FAISS is None:
            return None

        if self._vectorstore is not None:
            return self._vectorstore

        embeddings = self._get_embeddings()
        if embeddings is None:
            return None

        index_file = self._index_dir / "index.faiss"
        if index_file.exists():
            try:
                self._vectorstore = FAISS.load_local(
                    str(self._index_dir),
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
                logger.info("Loaded existing RAG FAISS index from %s", self._index_dir)
            except Exception:  # pragma: no cover - corrupted index guard
                logger.exception("Failed to load FAISS index, rebuilding from metadata.")
                self._vectorstore = None

        if self._vectorstore is None and not load_only:
            documents = [
                self._to_document(entry)
                for entry in self._documents_by_key.values()
                if self._to_document(entry) is not None
            ]
            if documents:
                self._vectorstore = FAISS.from_documents(documents, embeddings)
                self._save_vectorstore()
                logger.info("Rebuilt RAG FAISS index with %d document(s).", len(documents))

        return self._vectorstore

    def _save_vectorstore(self) -> None:
        if self._vectorstore is None:
            return
        try:
            self._vectorstore.save_local(str(self._index_dir))
        except Exception:  # pragma: no cover - persistence guard
            logger.exception("Failed to persist FAISS index to %s", self._index_dir)

    # ------------------------------------------------------------------ #
    # Document utilities
    # ------------------------------------------------------------------ #

    def _to_document(self, entry: Dict[str, object]) -> Optional[Document]:  # type: ignore[override]
        if Document is None:
            return None

        content = entry.get("content")
        metadata = entry.get("metadata")
        if not isinstance(content, str) or not isinstance(metadata, dict):
            return None
        return Document(page_content=content, metadata=metadata)

    def _format_summary(self, values: Iterable[str]) -> str:
        non_empty = [value.strip() for value in values if value and value.strip()]
        return ", ".join(non_empty[:4])

    def _add_document(self, *, doc_key: str, content: str, metadata: Dict[str, object]) -> bool:
        created_at = metadata.get("created_at")
        if not isinstance(created_at, str):
            created_at = utcnow_iso()
            metadata["created_at"] = created_at

        content = normalize_legacy_text(content)
        metadata = normalize_legacy_payload(metadata)

        with self._lock:
            if doc_key in self._documents_by_key:
                return False

            clean_metadata = dict(metadata)
            clean_metadata["doc_key"] = doc_key

            doc_entry: Dict[str, object] = {
                "doc_key": doc_key,
                "content": content,
                "created_at": created_at,
                "title": metadata.get("title", ""),
                "summary": metadata.get("summary", ""),
                "scenario_code": metadata.get("scenario_code", ""),
                "status": metadata.get("status", ""),
                "type": metadata.get("type", ""),
                "metadata": clean_metadata,
            }
            self._documents_by_key[doc_key] = normalize_legacy_payload(doc_entry)
            self._persist_documents()

            vectorstore = self._ensure_vectorstore()
            if vectorstore is None:
                return True

            document = self._to_document(doc_entry)
            if document is None:
                return True

            try:
                vectorstore.add_documents([document])
                self._save_vectorstore()
            except Exception:  # pragma: no cover - index append guard
                logger.exception("Failed to append document %s to FAISS index.", doc_key)
            return True

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def bootstrap_scenarios(self, scenarios: Iterable[AlertScenario]) -> None:
        for scenario in scenarios:
            summary = self._format_summary(scenario.actions)
            content_lines = [
                f"시나리오: {scenario.title} ({scenario.code})",
                f"원인 지표: {scenario.source}",
                f"설명: {scenario.description}",
                "우선 가설:",
            ]
            content_lines.extend(f"- {item}" for item in scenario.hypotheses)
            content_lines.append("추천 조치:")
            content_lines.extend(f"- {item}" for item in scenario.actions)
            content_lines.append("관련 증거:")
            content_lines.extend(f"- {item}" for item in scenario.evidences)

            self._add_document(
                doc_key=f"scenario:{scenario.code}",
                content="\n".join(content_lines),
                metadata={
                    "type": "scenario",
                    "scenario_code": scenario.code,
                    "status": "reference",
                    "title": scenario.title,
                    "summary": summary or scenario.description,
                },
            )

    def record_action_execution(
        self,
        execution: ActionExecution,
        *,
        recovery_status: str = "pending",
    ) -> None:
        summary = self._format_summary(execution.actions)
        executed_at = execution.executed_at or utcnow_iso()
        results = execution.results or []

        content_lines = [
            f"승인된 조치 실행 기록 ({execution.scenario_title})",
            f"시나리오 코드: {execution.scenario_code}",
            f"결과 상태: executed",
            f"실행 시각(UTC): {executed_at}",
            f"Recovery status: {recovery_status}",
            "조치 목록:",
        ]
        for result in results:
            detail = getattr(result, "detail", "")
            status = getattr(result, "status", "unknown")
            action_text = getattr(result, "action", "")
            executed_ts = getattr(result, "executed_at", "")
            content_lines.append(
                f"- {action_text} -> status={status}, 실행시각={executed_ts}, 비고={detail}"
            )
        if not results:
            for action in execution.actions:
                content_lines.append(f"- {action}")

        self._add_document(
            doc_key=f"action_execution:{execution.id}:executed",
            content="\n".join(content_lines),
            metadata={
                "type": "action_execution",
                "scenario_code": execution.scenario_code,
                "status": "executed",
                "recovery_status": recovery_status,
                "title": f"{execution.scenario_title} 승인된 조치",
                "summary": f"승인된 조치: {summary}",
                "actions": execution.actions,
                "created_at": executed_at,
            },
        )

    def record_action_deferred(
        self,
        execution: ActionExecution,
        *,
        recovery_status: str = "not_executed",
    ) -> None:
        summary = self._format_summary(execution.actions)
        recorded_at = utcnow_iso()

        content_lines = [
            f"보류된 조치 계획 ({execution.scenario_title})",
            f"시나리오 코드: {execution.scenario_code}",
            "결과 상태: deferred",
            f"보류 시각(UTC): {recorded_at}",
            f"Recovery status: {recovery_status}",
            "검토 필요 조치:",
        ]
        for action in execution.actions:
            content_lines.append(f"- {action}")

        self._add_document(
            doc_key=f"action_execution:{execution.id}:deferred",
            content="\n".join(content_lines),
            metadata={
                "type": "action_execution",
                "scenario_code": execution.scenario_code,
                "status": "deferred",
                "recovery_status": recovery_status,
                "title": f"{execution.scenario_title} 보류된 조치",
                "summary": f"보류된 조치: {summary}",
                "actions": execution.actions,
                "created_at": recorded_at,
            },
        )

    def mark_action_recovery(
        self,
        execution_id: str,
        status: str,
        *,
        resolved_at: Optional[str] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> bool:
        doc_key = f"action_execution:{execution_id}:executed"
        resolved_at = resolved_at or utcnow_iso()

        with self._lock:
            entry = self._documents_by_key.get(doc_key)
            if not entry:
                return False
            metadata = entry.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}

            metadata["recovery_status"] = status
            metadata["recovered_at"] = resolved_at
            if metrics:
                metadata["recovery_metrics"] = metrics
            entry["metadata"] = normalize_legacy_payload(metadata)
            self._documents_by_key[doc_key] = normalize_legacy_payload(entry)
            self._persist_documents()
            self._vectorstore = None

        # Lazy rebuild (if embeddings configured) to keep FAISS metadata consistent.
        self._ensure_vectorstore(load_only=False)
        return True

    def record_incident_report(self, report: "IncidentReport") -> None:
        content_lines = [
            f"Incident report snapshot: {report.title}",
            f"시나리오 코드: {report.scenario_code}",
            f"작성 시각(UTC): {report.created_at}",
            "",
            "요약:",
            report.summary or "(요약 없음)",
            "",
            "근본 원인:",
            report.root_cause or "(근본 원인 없음)",
            "",
            "영향 범위:",
            report.impact or "(영향 정보 없음)",
            "",
            "조치 항목:",
        ]
        if report.action_items:
            content_lines.extend(f"- {item}" for item in report.action_items)
        else:
            content_lines.append("- (등록된 조치 항목 없음)")
        content_lines.append("")
        content_lines.append("후속 조치:")
        if report.follow_up:
            content_lines.extend(f"- {item}" for item in report.follow_up)
        else:
            content_lines.append("- (등록된 후속 조치 없음)")

        self._add_document(
            doc_key=f"incident_report:{report.id}",
            content="\n".join(content_lines),
            metadata={
                "type": "incident_report",
                "scenario_code": report.scenario_code,
                "status": "report",
                "recovery_status": "not_applicable",
                "title": report.title,
                "summary": report.summary or report.title,
                "actions": report.action_items,
                "created_at": report.created_at,
            },
        )

    def list_documents(self) -> List[Dict[str, object]]:
        with self._lock:
            items = list(self._documents_by_key.values())
        items.sort(
            key=lambda entry: entry.get("created_at") or "",
            reverse=True,
        )
        return items

    def recent_actions(
        self,
        scenario_code: str,
        *,
        status: str = "executed",
        limit: int = 5,
    ) -> List[str]:
        with self._lock:
            entries = list(self._documents_by_key.values())

        filtered: List[str] = []
        entries.sort(key=lambda entry: entry.get("created_at") or "", reverse=True)
        for entry in entries:
            metadata = entry.get("metadata")
            if not isinstance(metadata, dict):
                continue
            if metadata.get("scenario_code") != scenario_code:
                continue
            if metadata.get("status") != status:
                continue
            actions = metadata.get("actions")
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, str):
                        filtered.append(action)
                        if len(filtered) >= limit:
                            return filtered
        return filtered[:limit]

    def search(
        self,
        query: str,
        *,
        limit: int = 4,
        metadata_filter: Optional[Dict[str, object]] = None,
    ) -> List[Document]:  # type: ignore[override]
        with self._lock:
            filter_dict = metadata_filter or {}

            vectorstore = self._ensure_vectorstore()
            if vectorstore is not None:
                try:
                    return vectorstore.similarity_search(
                        query,
                        k=limit,
                        filter=filter_dict,
                    )
                except Exception:  # pragma: no cover - defensive guard
                    logger.exception("RAG similarity search failed; falling back to metadata scan.")

            # Fallback: metadata-only filtering ordered by recency.
            matches: List[Document] = []
            for entry in self._documents_by_key.values():
                metadata = entry.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                include = True
                for key, value in filter_dict.items():
                    if metadata.get(key) != value:
                        include = False
                        break
                if include:
                    document = self._to_document(entry)
                    if document:
                        matches.append(document)

            matches.sort(
                key=lambda doc: doc.metadata.get("created_at") or "",
                reverse=True,
            )
            return matches[:limit]

    def build_context_for_scenario(
        self,
        scenario: AlertScenario,
        *,
        limit: int = 4,
    ) -> str:
        query = " ".join(
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
        approved_docs = self.search(
            query,
            limit=limit,
            metadata_filter={"scenario_code": scenario.code, "status": "executed"},
        )

        documents = approved_docs
        prefix = "Previously approved actions:"
        if not documents:
            documents = self.search(
                query,
                limit=limit,
                metadata_filter={"scenario_code": scenario.code},
            )
            prefix = "Related history:" if documents else ""

        if documents:
            lines = [prefix] if prefix else []
            for document in documents:
                meta = document.metadata
                title = meta.get("title") or scenario.title
                status = meta.get("status") or "reference"
                created_at = meta.get("created_at") or ""
                summary = meta.get("summary") or document.page_content.replace("\n", " ")[:200]
                lines.append(f"- [{status}] {title} ({created_at})")
                lines.append(f"  {summary}")
            return "\n".join(lines)

        fallback_entries = [
            entry
            for entry in self.list_documents()
            if isinstance(entry.get("metadata"), dict)
            and entry["metadata"].get("scenario_code") == scenario.code
        ]
        if fallback_entries:
            lines = ["Related history:"]
            for entry in fallback_entries[:limit]:
                metadata = entry.get("metadata", {})
                title = metadata.get("title") or entry.get("title") or scenario.title
                status = metadata.get("status") or entry.get("status") or "reference"
                created_at = metadata.get("created_at") or entry.get("created_at") or ""
                summary = metadata.get("summary") or entry.get("summary") or ""
                lines.append(f"- [{status}] {title} ({created_at})")
                if summary:
                    lines.append(f"  {summary}")
            return "\n".join(lines)

        approved_actions = self.recent_actions(
            scenario.code,
            status="executed",
            limit=limit,
        )
        if approved_actions:
            lines = ["Previously approved actions:"]
            lines.extend(f"- {item}" for item in approved_actions)
            return "\n".join(lines)
        return ""


# Shared singleton used throughout the backend.
rag_data_dir = Path(__file__).resolve().parents[2] / "rag_data"
rag_service = RAGService(rag_data_dir)
