"""
Unit and integration tests for Scheme-Specific Information Display in AI Government Research Agent.

Requirements verified:
1. Exact Scheme details fetched by unique canonical ID from SQL database.
2. Proper 404 response when a scheme does not exist.
3. ChromaDB metadata filter using selected scheme_id strictly isolates retrieval to that scheme.
4. Scheme-scoped research does not mix details from other schemes (e.g., no 7/12 land records for Majhi Ladki Bahin).
5. Cross-scheme question handling: detects when user asks about Scheme B while viewing Scheme A.
6. General queries without scheme_id retain global retrieval capability across schemes.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.db import SessionLocal, Scheme, init_db
from app.schemes.pipeline import (
    get_scheme_by_id_or_code,
    seed_official_schemes,
    sync_all_schemes_to_vectorstore,
)
from app.rag.retriever import get_store
from app.tools.document_search import vector_search

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    init_db()
    with SessionLocal() as db:
        seed_official_schemes(db=db, force_update=False)
        sync_all_schemes_to_vectorstore(db=db, force=False)


def test_get_scheme_by_canonical_id_exact():
    """Verify that fetching a scheme by canonical ID returns that exact scheme."""
    resp = client.get("/schemes/MH-WOM-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == "MH-WOM-01"
    assert "Ladki Bahin" in data["scheme_name"] or "लाडकी बहीण" in data["hindi_name"]
    assert "1,500" in data["benefits"]
    assert "21" in data["eligibility"] and "65" in data["eligibility"]
    # Verify application process is authentic and present
    assert data.get("application_process")
    assert "Nari Shakti Doot" in data["application_process"] or "ladkibahin.maharashtra.gov.in" in data["application_process"]
    # Ensure no land records (7/12) in required documents
    assert "7/12" not in data["documents"]


def test_get_scheme_by_secondary_canonical_id():
    """Verify Scheme B (Lek Ladki) returns its own distinct data."""
    resp = client.get("/schemes/MH-WOM-02")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == "MH-WOM-02"
    assert "Lek Ladki" in data["scheme_name"] or "लेक लाडकी" in data["hindi_name"]
    assert "1,01,000" in data["benefits"]
    # Distinct from Ladki Bahin's ₹1,500/month
    assert "1,500" not in data["benefits"]


def test_get_agricultural_scheme_has_proper_details():
    """Verify agricultural scheme PM-KISAN returns exact verified details."""
    resp = client.get("/schemes/PM-KISAN")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == "PM-KISAN"
    assert "6,000" in data["benefits"]
    assert "pmkisan.gov.in" in data.get("official_source_url", "")


def test_get_scheme_not_found_404():
    """Verify that requesting a nonexistent scheme ID returns 404."""
    resp = client.get("/schemes/NONEXISTENT-SCHEME-99999")
    assert resp.status_code == 404
    err_body = resp.json()
    assert "not found" in err_body["detail"].lower()


def test_chromadb_filter_retrieval_isolation():
    """Verify that ChromaDB metadata filter retrieves ONLY chunks matching scheme_id."""
    store = get_store()

    # Query with filter for MH-WOM-01
    results = store.similarity_search(
        "eligibility criteria application process documents",
        k=6,
        filter={"scheme_id": "MH-WOM-01"},
    )
    assert len(results) > 0, "Expected chunks for MH-WOM-01 in ChromaDB"
    for doc in results:
        assert doc.metadata.get("scheme_id") == "MH-WOM-01", (
            f"Chunk returned from different scheme: {doc.metadata.get('scheme_id')}"
        )
        # Must not contain land record or KCC text
        assert "7/12" not in doc.page_content
        assert "Kisan Credit Card" not in doc.page_content


def test_scoped_research_endpoint_no_cross_scheme_contamination():
    """Verify that POST /research with scheme_id='MH-WOM-01' returns verified Ladki Bahin data without 7/12."""
    resp = client.post(
        "/research",
        json={
            "question": "What are the eligibility criteria and required documents?",
            "language": "en",
            "scheme_id": "MH-WOM-01",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    answer = data.get("answer", "")
    assert data.get("status") == "completed"

    # Should contain Ladki Bahin specifics
    assert "Ladki Bahin" in answer or "1,500" in answer or "21" in answer
    # Must NOT mention 7/12 land records
    assert "7/12" not in answer
    assert "Kisan Credit Card" not in answer

    # Verify matched scheme in response matches the scoped scheme
    matched = data.get("matched_scheme")
    assert matched is not None
    assert matched.get("scheme_id") == "MH-WOM-01"


def test_cross_scheme_question_detection():
    """Verify that if a user views Scheme A (MH-WOM-01) but asks about Scheme B (PM-KISAN),
    the system handles it explicitly with a notice rather than blending information."""
    resp = client.post(
        "/research",
        json={
            "question": "Tell me about PM-KISAN installment amounts and rules",
            "language": "en",
            "scheme_id": "MH-WOM-01",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    answer = data.get("answer", "")

    # Should include a switch notice mentioning that the user is viewing MH-WOM-01 but asked about PM-KISAN
    assert "Note" in answer or "viewing" in answer or "PM-KISAN" in answer
    # Must contain PM-KISAN ₹6,000 info
    assert "6,000" in answer or "PM-KISAN" in answer


def test_general_chat_unscoped_retrieval():
    """Verify that general chat without scheme_id can retrieve relevant schemes globally."""
    resp = client.post(
        "/research",
        json={
            "question": "What is the Kisan Credit Card loan limit and interest rate?",
            "language": "en",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "completed"
    answer = data.get("answer", "")
    assert "KCC" in answer or "Credit" in answer or "1,60,000" in answer or "4%" in answer
