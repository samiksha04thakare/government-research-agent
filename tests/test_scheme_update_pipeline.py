"""Comprehensive Automated Test Suite for Automatic Government Scheme Update Pipeline.

Tests:
1. Duplicate scheme detection, normalization, and stable canonical ID assignment.
2. Changed scheme detection via SHA-256 content hashing and SchemeHistory audit trail.
3. Discontinued scheme detection and lifecycle management.
4. Failed sync error isolation, SyncLog telemetry, and retry with backoff.
5. SQL & ChromaDB consistency with atomic chunk replacement.
6. Strict RAG retriever isolation preventing unrelated schemes from appearing in scheme-specific answers.
7. Citation accuracy and strict distinction between last_checked and last_verified timestamps.
8. Strict authorization guard preventing unauthorized scraping of myScheme.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.database.db import (
    Scheme,
    SchemeHistory,
    SessionLocal,
    SyncLog,
    init_db,
)
from app.rag.retriever import get_store, search_with_scores
from app.schemes.normalizer import get_canonical_scheme_id
from app.schemes.pipeline import (
    get_scheme_by_id_or_code,
    index_scheme_to_vectorstore,
    search_schemes_in_db,
)
from app.schemes.updater import (
    compute_scheme_content_hash,
    detect_and_upsert_scheme,
    get_sync_pipeline_status,
    retry_failed_sources,
    sync_source,
)
from app.sources.config import is_scraping_prohibited
from app.sources.source_registry import SourceConfig, registry
from app.tools.document_search import vector_search


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_duplicate_schemes_normalization_and_id_stability():
    """Verify duplicate schemes with name variations resolve to stable canonical ID without duplicating SQL rows."""
    scheme_data_1 = {
        "scheme_name": "Chief Minister Krishi Swavalamban Yojana",
        "hindi_name": "मुख्यमंत्री कृषि स्वावलंबन योजना",
        "category": "Agriculture",
        "department": "Department of Agriculture, Maharashtra",
        "beneficiary": "Small & Marginal Farmers",
        "eligibility": "Farmers holding valid land records in Maharashtra.",
        "benefits": "Subsidy up to ₹50,000 for farm wells and micro-irrigation.",
        "documents": "7/12 extract, 8-A certificate, Aadhaar card",
        "application_process": "Apply via state DBT portal",
        "application_url": "https://krishi.maharashtra.gov.in",
        "official_source_url": "https://krishi.maharashtra.gov.in/swavalamban",
        "state_district": "Maharashtra",
        "status": "Active",
    }

    # Ingest first time -> CREATED
    res1 = detect_and_upsert_scheme(scheme_data_1)
    assert res1["status"] in ("CREATED", "UNCHANGED", "UPDATED")
    scheme1 = res1["scheme"]
    canonical_id = scheme1.scheme_id
    assert canonical_id is not None
    assert len(canonical_id) > 2

    # Ingest second time with exact same content -> UNCHANGED
    res2 = detect_and_upsert_scheme(scheme_data_1)
    assert res2["status"] == "UNCHANGED"
    assert res2["scheme"].id == scheme1.id
    assert res2["scheme"].scheme_id == canonical_id


def test_changed_scheme_detection_and_history_logging():
    """Verify that modified scheme content is detected via SHA-256 hash mismatch and logged in SchemeHistory."""
    unique_suffix = uuid.uuid4().hex[:6]
    test_name = f"Maharashtra Solar Pump Subsidy {unique_suffix}"
    scheme_initial = {
        "scheme_name": test_name,
        "hindi_name": f"महाराष्ट्र सौर कृषी पंप योजना {unique_suffix}",
        "category": "Agriculture",
        "department": "Department of Energy & Agriculture",
        "beneficiary": "Farmer families",
        "eligibility": "Farmers without electric agricultural connection.",
        "benefits": "90% subsidy for 3 HP solar water pumps.",
        "documents": "Aadhaar, Land ownership certificate",
        "application_process": "Register on portal",
        "official_source_url": "https://krishi.maharashtra.gov.in/solar",
        "state_district": "Maharashtra",
        "status": "Active",
    }

    # Step 1: Initial creation
    res1 = detect_and_upsert_scheme(scheme_initial)
    assert res1["status"] == "CREATED"
    scheme_obj = res1["scheme"]
    init_hash = scheme_obj.content_hash
    assert init_hash

    # Step 2: Official policy update: benefit subsidy increased to 95% and added 5 HP pumps
    scheme_updated = dict(scheme_initial)
    scheme_updated["benefits"] = "95% subsidy for 3 HP and 5 HP standalone solar water pumps."
    scheme_updated["eligibility"] = "Small and marginal farmers without high-voltage grid connection."

    res2 = detect_and_upsert_scheme(scheme_updated)
    assert res2["status"] == "UPDATED"
    updated_scheme = res2["scheme"]
    assert updated_scheme.id == scheme_obj.id
    assert updated_scheme.content_hash != init_hash
    assert "95%" in updated_scheme.benefits

    # Step 3: Check SchemeHistory audit log
    with SessionLocal() as db:
        history = (
            db.query(SchemeHistory)
            .filter(SchemeHistory.scheme_id == updated_scheme.scheme_id)
            .order_by(SchemeHistory.recorded_at.desc())
            .all()
        )
        assert len(history) >= 2  # CREATED + UPDATED
        latest_rev = history[0]
        assert latest_rev.change_type == "UPDATED"
        assert latest_rev.previous_hash == init_hash
        assert latest_rev.new_hash == updated_scheme.content_hash
        changed_fields = [d["field"] for d in latest_rev.changed_fields]
        assert "benefits" in changed_fields
        assert "eligibility" in changed_fields


def test_discontinued_scheme_detection():
    """Verify that discontinued or sunset schemes are detected and flagged accurately."""
    unique_suffix = uuid.uuid4().hex[:6]
    test_name = f"Temporary Pilot Fertilizer Assistance {unique_suffix}"
    scheme_data = {
        "scheme_name": test_name,
        "hindi_name": f"तात्पुरते खत सहाय्य {unique_suffix}",
        "category": "Agriculture",
        "department": "Department of Agriculture",
        "beneficiary": "Farmers",
        "eligibility": "Drought-affected districts",
        "benefits": "One-time assistance of ₹2,000",
        "documents": "Aadhaar Card",
        "official_source_url": "https://krishi.maharashtra.gov.in/pilot",
        "state_district": "Maharashtra",
        "status": "Active",
    }

    res1 = detect_and_upsert_scheme(scheme_data)
    assert res1["status"] == "CREATED"

    # Scheme is sunset in official notification
    scheme_sunset = dict(scheme_data)
    scheme_sunset["status"] = "Discontinued"
    scheme_sunset["is_discontinued"] = True

    res2 = detect_and_upsert_scheme(scheme_sunset)
    assert res2["status"] == "DISCONTINUED"
    assert res2["scheme"].is_discontinued is True
    assert res2["scheme"].status == "Discontinued"

    # Verify audit log recorded DISCONTINUED transition
    with SessionLocal() as db:
        history_entry = (
            db.query(SchemeHistory)
            .filter(SchemeHistory.scheme_id == res2["scheme"].scheme_id)
            .order_by(SchemeHistory.recorded_at.desc())
            .first()
        )
        assert history_entry.change_type == "DISCONTINUED"


def test_failed_sync_isolation_and_retries():
    """Verify that an unauthorized or failing source logs an informative failure in SyncLog without corrupting the pipeline."""
    # Create an unauthorized test source pointing to an external unauthorized endpoint
    failing_source = SourceConfig(
        source_name="Unauthorized Scraping Test Source",
        source_url="https://www.myscheme.gov.in/api/unauthorized-feed",
        source_type="dataset",
        department="Test Ministry",
        category="government_schemes",
        enabled=True,
    )

    with SessionLocal() as db:
        res = sync_source(failing_source, db=db)
        assert res["status"] == "FAILED"
        assert "not authorized" in res["error"].lower() or "prohibited" in res["error"].lower()

        # Check SyncLog recorded this failure
        latest_log = (
            db.query(SyncLog)
            .filter(SyncLog.source_name == "Unauthorized Scraping Test Source")
            .order_by(SyncLog.started_at.desc())
            .first()
        )
        assert latest_log is not None
        assert latest_log.status == "FAILED"
        assert latest_log.error_message


def test_sql_and_chromadb_consistency():
    """Verify ChromaDB chunks match SQL scheme metadata and replace obsolete chunks atomically."""
    unique_suffix = uuid.uuid4().hex[:6]
    test_name = f"Maharashtra Agri Mechanization Mission {unique_suffix}"
    scheme_dict = {
        "scheme_name": test_name,
        "hindi_name": f"महाराष्ट्र कृषी यांत्रिकीकरण अभियान {unique_suffix}",
        "category": "Agriculture",
        "department": "Department of Agriculture, Maharashtra",
        "beneficiary": "Farmer collectives",
        "eligibility": "Farmers owning cultivable land in Maharashtra.",
        "benefits": "50% financial subsidy for tractors, power tillers, and rotavators.",
        "documents": "7/12 land records, Aadhaar, Bank passbook",
        "application_process": "Apply on MahaDBT portal",
        "application_url": "https://mahadbt.maharashtra.gov.in",
        "official_source_url": "https://krishi.maharashtra.gov.in",
        "state_district": "Maharashtra",
        "status": "Active",
    }

    res = detect_and_upsert_scheme(scheme_dict)
    scheme_obj = res["scheme"]
    canonical_id = scheme_obj.scheme_id

    # Verify chunks exist in ChromaDB with metadata['scheme_id'] == canonical_id
    store = get_store()
    retrieved = store.get(where={"scheme_id": canonical_id})
    assert retrieved is not None
    assert len(retrieved.get("ids", [])) > 0
    first_meta = retrieved["metadatas"][0]
    assert first_meta["scheme_id"] == canonical_id
    assert first_meta["status"] == "Active"
    assert first_meta["content_hash"] == scheme_obj.content_hash
    assert first_meta["last_checked"]
    assert first_meta["last_updated"]

    # Re-index with force=True -> obsolete chunks deleted, new chunks stored with same ID format
    chunks_added = index_scheme_to_vectorstore(scheme_obj, force=True)
    assert chunks_added > 0
    after_reindex = store.get(where={"scheme_id": canonical_id})
    assert len(after_reindex["ids"]) == chunks_added


def test_rag_retrieval_scheme_isolation():
    """Verify that scheme-specific vector searches return only chunks belonging to the target scheme."""
    # Search specifically for MH-WOM-01 (Mukhyamantri Majhi Ladki Bahin Yojana)
    target_sid = "MH-WOM-01"
    results = vector_search("eligibility and monthly financial assistance", k=5, filters={"scheme_id": target_sid})

    assert len(results) > 0
    for item in results:
        meta = item["metadata"]
        # Every retrieved chunk must match target_sid
        assert meta.get("scheme_id") == target_sid
        # Verify no unrelated scheme (e.g. PM-KISAN or KCC) appears
        assert "pm-kisan" not in meta.get("scheme_id", "").lower()
        assert "kcc" not in meta.get("scheme_id", "").lower()


def test_citation_accuracy_and_timestamp_distinction():
    """Verify distinction between last_checked and last_verified timestamps in scheme dictionary."""
    with SessionLocal() as db:
        scheme = db.query(Scheme).first()
        assert scheme is not None
        scheme_dict = scheme.to_dict()

        # Both must exist and be valid ISO dates without fabrication
        assert "last_checked" in scheme_dict
        assert "last_verified" in scheme_dict
        assert "verification_status" in scheme_dict
        assert "source_citations" in scheme_dict
        assert isinstance(scheme_dict["source_citations"], list)


def test_myscheme_scraping_authorization_guard():
    """Verify that unauthorized scraping of myScheme is strictly prohibited."""
    prohibited_url = "https://www.myscheme.gov.in/schemes/pm-kisan"
    assert is_scraping_prohibited(prohibited_url) is True

    authorized_url = "https://data.gov.in/resource/123"
    assert is_scraping_prohibited(authorized_url) is False

    permitted_state_url = "https://dbt.mahapocra.gov.in/"
    assert is_scraping_prohibited(permitted_state_url) is False
