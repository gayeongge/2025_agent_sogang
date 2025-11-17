import json

from src.backend.app import _ingest_rag_upload
from src.backend.rag import RAGService


def _collect_doc(service: RAGService, doc_key: str) -> dict[str, object]:
    for doc in service.list_documents():
        if doc.get("doc_key") == doc_key:
            return doc
    raise AssertionError(f"Document {doc_key} not found")


def test_add_uploaded_document_persists_defaults(tmp_path):
    service = RAGService(tmp_path)

    doc_key = service.add_uploaded_document(
        title="Custom incident log",
        content="Line one\nLine two\nLine three",
        metadata={"scenario_code": "custom_s1"},
    )

    stored = _collect_doc(service, doc_key)
    metadata = stored["metadata"]
    assert stored["title"] == "Custom incident log"
    assert metadata["scenario_code"] == "custom_s1"
    assert metadata["type"] == "uploaded"
    assert metadata["status"] == "reference"
    assert metadata["summary"]


def test_ingest_rag_upload_accepts_text(tmp_path):
    service = RAGService(tmp_path)

    doc_keys = _ingest_rag_upload(
        "notes.txt",
        ".txt",
        "Temporary runbook for outage\nStep 1: reboot node",
        service=service,
    )

    assert len(doc_keys) == 1
    stored = _collect_doc(service, doc_keys[0])
    assert stored["title"] == "notes"
    assert "reboot node" in stored["content"]


def test_ingest_rag_upload_accepts_json(tmp_path):
    service = RAGService(tmp_path)
    payload = [
        {
            "title": "Fallback procedure",
            "content": "Use cached config and recycle deployment.",
            "scenario_code": "fallback_01",
            "status": "reference",
        },
        {
            "metadata": {"title": "Report recap", "scenario_code": "report_x"},
            "content": "Incident resolved after failover.",
        },
    ]

    doc_keys = _ingest_rag_upload(
        "docs.json",
        ".json",
        json.dumps(payload, ensure_ascii=False),
        service=service,
    )

    assert len(doc_keys) == 2
    titles = { _collect_doc(service, key)["title"] for key in doc_keys }
    assert titles == {"Fallback procedure", "Report recap"}
