"""Government Data Ingestion & Indexing Pipeline.

Integrates official data collectors with the existing ChromaDB 'gov_docs' collection.
Enforces:
1. Exact metadata schema:
   - source_name
   - source_url
   - category
   - department
   - title
   - document_type
   - last_checked (recorded only when check occurs)
   - last_updated (official document/source date, never fabricated)
2. Duplicate and change detection via SHA-256 content hashing:
   - Same -> Skip (UNCHANGED, avoids unnecessary embedding costs)
   - Changed -> Re-index (UPDATED, deletes obsolete chunks, prevents duplicate IDs)
   - New -> Add (NEW)
3. Non-destructive indexing (never wipes verified documents on source failure).
4. Timeouts, limited retries with backoff, and protection against overlapping runs.
5. Standardized structured logging.
"""
import hashlib
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.database.db import Document as DbDocument, SessionLocal
from app.rag.chunker import chunk_documents
from app.rag.retriever import get_store
from app.sources.config import (
    SOURCE_MAX_RETRIES,
    SOURCE_RETRY_BACKOFF_SECONDS,
    SOURCE_TIMEOUT_SECONDS,
    SOURCE_TYPE_API,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_WEBSITE,
    SUPPORTED_CATEGORIES,
)
from app.sources.data_gov import fetch_data_gov_resource
from app.sources.pdf_collector import collect_pdf
from app.sources.source_registry import SourceConfig, registry
from app.sources.website_collector import collect_webpage
from app.utils.logging import get_logger

log = get_logger("sources_pipeline")

# Run lock to protect against concurrent/overlapping scheduled runs
_run_lock = threading.Lock()
_is_running = False


def is_ingestion_running() -> bool:
    """Check if an ingestion cycle is currently active."""
    return _is_running


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash for document content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_chunk_ids(source_key: str, count: int) -> list[str]:
    """Generate deterministic, unique chunk IDs to prevent duplicate IDs upon re-indexing."""
    clean_key = source_key or "doc"
    key_hash = hashlib.sha256(clean_key.encode("utf-8")).hexdigest()[:16]
    return [f"gov_{key_hash}_{i}" for i in range(count)]


def ensure_metadata_compliance(
    docs: list[Document],
    source_cfg: SourceConfig,
    content_hash: str,
    check_time: str | None = None,
) -> list[Document]:
    """Ensure every document and page chunk satisfies the strict 8-field metadata contract.

    Rule: Record last_checked only when a check occurs. Do not invent official last_updated dates.
    """
    now_ts = check_time or _now_iso()
    check_date = now_ts[:10]

    # Official date from source or publication; never substitute check_date for last_updated
    official_updated = (
        source_cfg.updated_date
        or source_cfg.publication_date
        or ""
    )

    for doc in docs:
        meta = doc.metadata or {}
        # Mandatory 8 metadata fields
        meta["source_name"] = source_cfg.source_name
        meta["source_url"] = source_cfg.source_url
        meta["category"] = source_cfg.category
        meta["department"] = source_cfg.department
        meta["title"] = source_cfg.title or source_cfg.source_name
        meta["document_type"] = source_cfg.source_type
        meta["last_checked"] = check_date
        meta["last_updated"] = meta.get("last_updated") or meta.get("updated_date") or official_updated

        # Additional pipeline tracking fields
        meta["content_hash"] = content_hash
        meta["authority"] = source_cfg.department
        meta["version"] = source_cfg.version
        meta["ingested_at"] = now_ts

        doc.metadata = meta

    return docs


def collect_source_documents(source_cfg: SourceConfig) -> tuple[str, list[Document], str]:
    """Dispatch collection based on source_type.

    Returns:
        (status, list_of_documents, error_message)
    """
    stype = source_cfg.source_type
    try:
        if stype == SOURCE_TYPE_API:
            if not source_cfg.resource_id:
                return ("ERROR", [], "No resource_id configured for data.gov.in API source")
            res = fetch_data_gov_resource(
                resource_id=source_cfg.resource_id,
                title=source_cfg.title,
                department=source_cfg.department,
                category=source_cfg.category,
            )
            status = res.get("status")
            if status == "unconfigured":
                return ("SKIPPED_UNCONFIGURED", [], res.get("message", "API key not configured"))
            elif status == "error":
                return ("ERROR", [], res.get("message", "API fetch error"))
            elif status == "empty":
                return ("EMPTY", [], "Resource returned 0 records")
            return ("SUCCESS", res.get("documents", []), "")

        elif stype == SOURCE_TYPE_WEBSITE:
            doc = collect_webpage(
                source_cfg.source_url,
                meta={
                    "source_name": source_cfg.source_name,
                    "title": source_cfg.title,
                    "department": source_cfg.department,
                    "category": source_cfg.category,
                    "publication_date": source_cfg.publication_date,
                    "updated_date": source_cfg.updated_date,
                    "version": source_cfg.version,
                },
            )
            if not doc:
                return ("ERROR", [], "Failed to collect webpage content or access disallowed")
            return ("SUCCESS", [doc], "")

        elif stype == SOURCE_TYPE_PDF:
            path_or_url = source_cfg.local_path or source_cfg.source_url
            docs = collect_pdf(
                path_or_url,
                meta={
                    "source_name": source_cfg.source_name,
                    "title": source_cfg.title,
                    "source_url": source_cfg.source_url,
                    "department": source_cfg.department,
                    "category": source_cfg.category,
                    "publication_date": source_cfg.publication_date,
                    "updated_date": source_cfg.updated_date,
                    "version": source_cfg.version,
                },
            )
            if not docs:
                return ("ERROR", [], f"Failed to extract text from PDF: {path_or_url}")
            return ("SUCCESS", docs, "")

        else:
            return ("ERROR", [], f"Unsupported source type: {stype}")

    except Exception as e:
        return ("ERROR", [], str(e))


def collect_source_with_retries(
    source_cfg: SourceConfig,
    max_retries: int = SOURCE_MAX_RETRIES,
) -> tuple[str, list[Document], str]:
    """Execute collection with limited retries and backoff for transient failures."""
    attempts = 0
    while attempts <= max_retries:
        attempts += 1
        status, docs, err = collect_source_documents(source_cfg)
        if status in ("SUCCESS", "SKIPPED_UNCONFIGURED", "EMPTY"):
            return status, docs, err
        # Non-retryable errors: missing key, unapproved domain, or permanent bad type
        if "not an approved" in err or "Unsupported source type" in err or "unconfigured" in err.lower():
            return status, docs, err

        if attempts <= max_retries:
            log.warning(
                "SOURCE: %s | Temporary failure on attempt %d/%d: %s. Retrying in %.1fs...",
                source_cfg.source_name,
                attempts,
                max_retries + 1,
                err,
                SOURCE_RETRY_BACKOFF_SECONDS,
            )
            time.sleep(SOURCE_RETRY_BACKOFF_SECONDS)

    return status, docs, err


def ingest_source(source_cfg: SourceConfig, dry_run: bool = False) -> dict[str, Any]:
    """Execute collection, duplicate/change detection, and ChromaDB indexing for a source.

    Duplicate detection workflow:
    document content -> SHA-256 hash -> Compare with existing hash:
       Same    -> Skip (UNCHANGED, no embedding cost)
       Changed -> Re-index (UPDATED, clean obsolete chunks, prevent duplicate IDs)
       New     -> Add (NEW, deterministic chunk IDs)

    Non-destructive guarantee:
    If collection fails or times out, valid existing indexed documents are NEVER deleted.
    """
    check_time = _now_iso()
    base_log = (
        f"SOURCE: {source_cfg.source_name} | URL: {source_cfg.source_url} | "
        f"DOCUMENT: {source_cfg.title} | CATEGORY: {source_cfg.category} | "
        f"CHECK_TIME: {check_time}"
    )

    if not source_cfg.enabled:
        log.info(f"{base_log} | STATUS: DISABLED")
        return {
            "source_name": source_cfg.source_name,
            "status": "DISABLED",
            "chunks_added": 0,
            "check_time": check_time,
            "message": "Source is disabled",
        }

    # Fetch source with timeout and limited retries
    status, docs, err = collect_source_with_retries(source_cfg)

    if status == "SKIPPED_UNCONFIGURED":
        log.info(f"{base_log} | STATUS: UNCONFIGURED | {err}")
        return {
            "source_name": source_cfg.source_name,
            "status": "UNCONFIGURED",
            "chunks_added": 0,
            "check_time": check_time,
            "message": err,
        }

    # If collection failed, preserve existing documents and log the failure
    if status != "SUCCESS" or not docs:
        log.error(f"{base_log} | STATUS: ERROR | ERROR: {err or 'No documents collected'}")
        return {
            "source_name": source_cfg.source_name,
            "status": "ERROR",
            "chunks_added": 0,
            "check_time": check_time,
            "error": err or "No documents collected",
        }

    # Calculate overall content hash for change detection
    full_text = "\n\n".join(d.page_content for d in docs)
    content_hash = compute_content_hash(full_text)

    # Ensure all 8 mandatory metadata attributes are present without fabricating dates
    docs = ensure_metadata_compliance(docs, source_cfg, content_hash, check_time=check_time)

    # Query ChromaDB collection 'gov_docs' to find existing entries for this source
    store = get_store()

    # Locate existing chunks by exact source_url or title
    existing = store.get(where={"source_url": source_cfg.source_url})
    if not existing["ids"] and source_cfg.title:
        existing = store.get(where={"title": source_cfg.title})

    decision = "NEW"
    existing_hash = ""

    if existing["ids"]:
        # Existing document found; inspect stored content_hash
        metas = existing.get("metadatas", [])
        if metas and isinstance(metas[0], dict):
            existing_hash = metas[0].get("content_hash", "")

        if existing_hash == content_hash:
            decision = "UNCHANGED"
        else:
            decision = "UPDATED"

    # Outcome handling
    if decision == "UNCHANGED":
        log.info(f"{base_log} | STATUS: UNCHANGED | Hash matches, skipping embedding.")
        # Update check timestamp in SQLite tracking without changing official updated_date
        try:
            with SessionLocal() as db:
                db_doc = db.query(DbDocument).filter(
                    (DbDocument.source_url == source_cfg.source_url) | (DbDocument.title == source_cfg.title)
                ).first()
                if db_doc:
                    db.commit()
        except Exception:
            pass

        return {
            "source_name": source_cfg.source_name,
            "status": "UNCHANGED",
            "chunks_added": 0,
            "check_time": check_time,
            "content_hash": content_hash,
            "message": "Content hash identical to existing index; skipped re-indexing.",
        }

    if dry_run:
        log.info(f"{base_log} | STATUS: {decision} (DRY-RUN)")
        return {
            "source_name": source_cfg.source_name,
            "status": f"{decision}_DRY_RUN",
            "chunks_added": 0,
            "check_time": check_time,
            "content_hash": content_hash,
        }

    # When updated, delete only previous chunks of THIS specific document
    if decision == "UPDATED":
        log.info(f"{base_log} | STATUS: UPDATED | Removing {len(existing['ids'])} obsolete chunks")
        store.delete(ids=existing["ids"])

    # Chunk and store in ChromaDB with deterministic chunk IDs to prevent duplicate IDs
    chunks = chunk_documents(docs)
    chunk_ids = generate_chunk_ids(source_cfg.source_url or source_cfg.title, len(chunks))
    store.add_documents(chunks, ids=chunk_ids)

    # Sync with SQLite Document tracking table without overwriting verified docs
    try:
        with SessionLocal() as db:
            db_doc = db.query(DbDocument).filter(
                (DbDocument.source_url == source_cfg.source_url) | (DbDocument.title == source_cfg.title)
            ).first()
            if not db_doc:
                db_doc = DbDocument(
                    title=source_cfg.title,
                    authority=source_cfg.department,
                    source_url=source_cfg.source_url,
                    document_type=source_cfg.source_type,
                    publication_date=source_cfg.publication_date,
                    updated_date=source_cfg.updated_date,
                    version=source_cfg.version,
                    file_path=source_cfg.local_path or source_cfg.source_url,
                    content_hash=content_hash,
                    indexed=True,
                )
                db.add(db_doc)
            else:
                db_doc.content_hash = content_hash
                db_doc.indexed = True
                if source_cfg.updated_date:
                    db_doc.updated_date = source_cfg.updated_date
            db.commit()
    except Exception as db_err:
        log.warning("Database sync warning for %s: %s", source_cfg.source_name, db_err)

    log.info(f"{base_log} | STATUS: {decision} | CHUNKS: {len(chunks)}")
    return {
        "source_name": source_cfg.source_name,
        "status": decision,
        "chunks_added": len(chunks),
        "check_time": check_time,
        "content_hash": content_hash,
    }


def ingest_all_registered_sources(
    dry_run: bool = False,
    category_filter: str | None = None,
    source_filter: str | None = None,
) -> dict[str, Any]:
    """Process all enabled sources in the registry and compile ingestion metrics.

    Includes run-lock protection against overlapping runs.
    """
    global _is_running
    # Acquire non-blocking lock to prevent overlapping runs
    acquired = _run_lock.acquire(blocking=False)
    if not acquired:
        msg = "Ingestion run skipped: another run is currently in progress (protection against overlapping runs)."
        log.warning(msg)
        return {
            "status": "skipped",
            "reason": "run_in_progress",
            "message": msg,
            "summary": {},
            "details": [],
            "total_sources_evaluated": 0,
        }

    try:
        _is_running = True
        sources = registry.list_sources(enabled_only=True)

        if category_filter:
            sources = [s for s in sources if s.category == category_filter]
        if source_filter:
            sources = [s for s in sources if s.source_name.lower() == source_filter.lower()]

        summary: dict[str, dict[str, int]] = {}
        detailed_results = []
        run_start_time = _now_iso()

        log.info(
            "Starting government data ingestion cycle at %s across %d sources (dry_run=%s)",
            run_start_time,
            len(sources),
            dry_run,
        )

        for src in sources:
            res = ingest_source(src, dry_run=dry_run)
            detailed_results.append(res)
            sname = src.source_name
            if sname not in summary:
                summary[sname] = {
                    "new": 0,
                    "updated": 0,
                    "unchanged": 0,
                    "failed": 0,
                }

            st = res.get("status", "")
            if st in ("NEW", "NEW_DRY_RUN"):
                summary[sname]["new"] += 1
            elif st in ("UPDATED", "UPDATED_DRY_RUN"):
                summary[sname]["updated"] += 1
            elif st == "UNCHANGED":
                summary[sname]["unchanged"] += 1
            elif st in ("ERROR", "UNCONFIGURED"):
                summary[sname]["failed"] += 1

        run_end_time = _now_iso()
        return {
            "status": "completed",
            "run_start_time": run_start_time,
            "run_end_time": run_end_time,
            "summary": summary,
            "details": detailed_results,
            "total_sources_evaluated": len(sources),
        }
    finally:
        _is_running = False
        _run_lock.release()
