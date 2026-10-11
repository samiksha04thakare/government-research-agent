"""Tests for Step 6: Scheduled Government Data Updates."""
import hashlib
import threading
import time
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.sources.config import UPDATE_INTERVAL_HOURS
from app.sources.pipeline import (
    _run_lock,
    compute_content_hash,
    ensure_metadata_compliance,
    generate_chunk_ids,
    ingest_all_registered_sources,
    ingest_source,
    is_ingestion_running,
)
from app.sources.scheduler import GovernmentDataScheduler
from app.sources.source_registry import SourceConfig


def test_scheduler_configuration_and_intervals():
    """Verify scheduler initialization, default 24h interval, and dynamic adjustments."""
    sched = GovernmentDataScheduler(interval_hours=24.0)
    assert sched.interval_hours == 24.0
    assert sched.interval_seconds == 24.0 * 3600.0
    assert not sched.is_running()

    # Dynamic interval reconfiguration
    sched.set_interval_hours(12.0)
    assert sched.interval_hours == 12.0
    assert sched.interval_seconds == 12.0 * 3600.0

    st = sched.get_status()
    assert st["interval_hours"] == 12.0
    assert st["running"] is False
    assert st["run_count"] == 0


def test_scheduler_controlled_lifecycle():
    """Verify clean start and stop without infinite execution."""
    sched = GovernmentDataScheduler(interval_hours=1.0)
    assert not sched.is_running()

    # Start background worker without immediate run
    started = sched.start(run_immediately=False)
    assert started is True
    assert sched.is_running() is True

    # Starting again should safely return False
    assert sched.start(run_immediately=False) is False

    # Stop background worker cleanly
    stopped = sched.stop(timeout=2.0)
    assert stopped is True
    assert sched.is_running() is False


def test_overlapping_run_protection():
    """Verify run lock blocks concurrent or overlapping ingestion executions."""
    # Simulate an active run by acquiring the lock
    acquired = _run_lock.acquire(blocking=False)
    assert acquired is True, "Failed to acquire lock for test"
    try:
        # A second run attempt must detect active run and skip cleanly
        res = ingest_all_registered_sources()
        assert res["status"] == "skipped"
        assert res["reason"] == "run_in_progress"
        assert "another run is currently in progress" in res["message"]
    finally:
        _run_lock.release()


def test_duplicate_prevention_chunk_ids():
    """Verify deterministic chunk IDs prevent ID collisions and duplicate chunks."""
    source_url = "https://pmkisan.gov.in/guidelines"
    ids1 = generate_chunk_ids(source_url, 4)
    ids2 = generate_chunk_ids(source_url, 4)

    # Identical source produces identical deterministic IDs
    assert ids1 == ids2
    assert len(ids1) == 4
    assert ids1[0].startswith("gov_")
    assert ids1[0].endswith("_0")
    assert ids1[3].endswith("_3")

    # Different source produces different IDs
    ids3 = generate_chunk_ids("https://icar.org.in/advisory", 4)
    assert ids1 != ids3


def test_unchanged_document_skips_embedding():
    """Verify identical SHA-256 hash skips chunking and embedding, avoiding costs."""
    sample_text = "Standard Official Guidelines for Farmer Support."
    content_hash = compute_content_hash(sample_text)

    test_src = SourceConfig(
        source_name="Test Soil Portal",
        source_url="https://soilhealth.dac.gov.in/test",
        source_type="website",
        department="Department of Agriculture",
        category="fertilizers",
        title="Soil Testing Protocol",
    )

    doc = Document(page_content=sample_text, metadata={"title": test_src.title})

    mock_store = MagicMock()
    # Simulate ChromaDB already having chunks with the exact same hash
    mock_store.get.return_value = {
        "ids": ["gov_test_0", "gov_test_1"],
        "metadatas": [{"content_hash": content_hash}],
    }

    with patch("app.sources.pipeline.collect_source_with_retries", return_value=("SUCCESS", [doc], "")):
        with patch("app.sources.pipeline.get_store", return_value=mock_store):
            res = ingest_source(test_src, dry_run=False)

            assert res["status"] == "UNCHANGED"
            assert res["chunks_added"] == 0
            assert res["content_hash"] == content_hash
            # ChromaDB add_documents must NOT be called when content is unchanged
            mock_store.add_documents.assert_not_called()
            mock_store.delete.assert_not_called()


def test_changed_document_updates_without_duplicates():
    """Verify changed document deletes old chunks and re-indexes with new deterministic IDs."""
    old_text = "Scheme Guidelines Version 1.0"
    new_text = "Scheme Guidelines Version 2.0 with Revised Outlay"
    old_hash = compute_content_hash(old_text)
    new_hash = compute_content_hash(new_text)

    test_src = SourceConfig(
        source_name="Dynamic Scheme Portal",
        source_url="https://myscheme.gov.in/updated_scheme",
        source_type="website",
        department="Ministry of Agriculture",
        category="government_schemes",
        title="Dynamic Scheme Guidelines",
        updated_date="2026-02-01",
    )

    new_doc = Document(page_content=new_text, metadata={"title": test_src.title})

    mock_store = MagicMock()
    # Simulate ChromaDB holding the old chunks
    mock_store.get.return_value = {
        "ids": ["gov_old_0", "gov_old_1"],
        "metadatas": [{"content_hash": old_hash}],
    }

    with patch("app.sources.pipeline.collect_source_with_retries", return_value=("SUCCESS", [new_doc], "")):
        with patch("app.sources.pipeline.get_store", return_value=mock_store):
            res = ingest_source(test_src, dry_run=False)

            assert res["status"] == "UPDATED"
            assert res["chunks_added"] > 0
            assert res["content_hash"] == new_hash

            # Obsolete chunks must be deleted
            mock_store.delete.assert_called_once_with(ids=["gov_old_0", "gov_old_1"])
            # New chunks must be added
            mock_store.add_documents.assert_called_once()
            call_kwargs = mock_store.add_documents.call_args[1]
            assert "ids" in call_kwargs
            assert len(call_kwargs["ids"]) == res["chunks_added"]


def test_source_failure_never_deletes_valid_documents():
    """Verify network error or source timeout preserves all existing indexed documents."""
    test_src = SourceConfig(
        source_name="Failing Portal",
        source_url="https://agricoop.nic.in/unreachable",
        source_type="website",
        department="Ministry of Agriculture",
        category="farmer_questions",
        title="Unreachable Advisory",
    )

    mock_store = MagicMock()
    mock_store.get.return_value = {
        "ids": ["gov_valid_doc_0", "gov_valid_doc_1"],
        "metadatas": [{"content_hash": "existing-valid-hash"}],
    }

    # Simulate connection timeout error
    with patch(
        "app.sources.pipeline.collect_source_with_retries",
        return_value=("ERROR", [], "Connection timed out after 20.0s"),
    ):
        with patch("app.sources.pipeline.get_store", return_value=mock_store):
            res = ingest_source(test_src, dry_run=False)

            assert res["status"] == "ERROR"
            assert "Connection timed out" in res["error"]
            # ChromaDB must NEVER be asked to delete existing documents on failure
            mock_store.delete.assert_not_called()
            mock_store.add_documents.assert_not_called()


def test_missing_api_key_reporting():
    """Verify missing DATA_GOV_API_KEY reports UNCONFIGURED without generating fake data."""
    test_src = SourceConfig(
        source_name="data.gov.in",
        source_url="https://data.gov.in/resource/catalog-01",
        source_type="api",
        department="Ministry of Agriculture",
        category="agriculture",
        title="OGD Catalog Resource",
        resource_id="catalog-01",
    )

    with patch("app.sources.data_gov.get_api_key", return_value=""):
        res = ingest_source(test_src, dry_run=False)
        assert res["status"] == "UNCONFIGURED"
        assert res["chunks_added"] == 0
        assert "DATA_GOV_API_KEY is not configured" in res["message"]


def test_dry_run_mode_does_not_mutate_index():
    """Verify --dry-run identifies new/changed documents without touching ChromaDB."""
    sample_text = "Brand New Government Scheme Content"
    test_src = SourceConfig(
        source_name="New Scheme Source",
        source_url="https://myscheme.gov.in/new_scheme",
        source_type="website",
        department="Ministry of Agriculture",
        category="government_schemes",
        title="New Scheme Guidelines",
    )

    doc = Document(page_content=sample_text, metadata={"title": test_src.title})

    mock_store = MagicMock()
    mock_store.get.return_value = {"ids": [], "metadatas": []}

    with patch("app.sources.pipeline.collect_source_with_retries", return_value=("SUCCESS", [doc], "")):
        with patch("app.sources.pipeline.get_store", return_value=mock_store):
            res = ingest_source(test_src, dry_run=True)

            assert res["status"] == "NEW_DRY_RUN"
            assert res["chunks_added"] == 0
            # Under dry run, store must not be modified
            mock_store.add_documents.assert_not_called()
            mock_store.delete.assert_not_called()


def test_strict_date_handling():
    """Verify last_checked is recorded only on check, and last_updated is not fabricated."""
    test_src = SourceConfig(
        source_name="Dated Portal",
        source_url="https://icar.org.in/dated",
        source_type="website",
        department="ICAR",
        category="crop_problems",
        title="Official Crop Directive",
        publication_date="2025-03-15",
        updated_date="",  # Unknown updated date
    )
    doc = Document(page_content="Crop Directive Text", metadata={})
    content_hash = compute_content_hash(doc.page_content)

    compliant = ensure_metadata_compliance([doc], test_src, content_hash, check_time="2026-10-09T11:00:00Z")
    meta = compliant[0].metadata

    # last_checked records the check timestamp
    assert meta["last_checked"] == "2026-10-09"
    # last_updated must be the official date (2025-03-15) and NOT today's date!
    assert meta["last_updated"] == "2025-03-15"
    assert meta["last_updated"] != "2026-10-09"
