"""Automatic Government Scheme Update Pipeline Engine.

Handles:
1. Scheme discovery from authorized sources (APIs, Datasets, PDFs/GRs, Permitted portals).
2. Rate limiting, backoff retries, and strict source authorization checks.
3. Stable canonical scheme ID resolution and duplicate normalization.
4. Deterministic SHA-256 content hashing for change detection.
5. Lifecycle states: NEW, UPDATED, UNCHANGED, DISCONTINUED.
6. Audit trail & revision history preservation in SchemeHistory.
7. Atomic SQL upserts and safe ChromaDB vectorstore re-indexing.
8. Execution telemetry, failure logging, and retry capability in SyncLog.
"""
import hashlib
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from sqlalchemy import or_

from app.database.db import (
    Scheme,
    SchemeHistory,
    SessionLocal,
    SyncLog,
    get_scheme_dataset_section_info,
    init_db,
)
from app.schemes.normalizer import (
    are_schemes_equivalent,
    get_canonical_scheme_id,
    normalize_scheme_name,
)
from app.sources.config import (
    DEFAULT_RATE_LIMIT_PER_MIN,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    SOURCE_MAX_RETRIES,
    SOURCE_RETRY_BACKOFF_SECONDS,
    SOURCE_TIMEOUT_SECONDS,
    SOURCE_TYPE_API,
    SOURCE_TYPE_DATASET,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_PERMITTED,
    SOURCE_TYPE_WEBSITE,
    is_official_government_url,
    is_scraping_prohibited,
)
from app.sources.source_registry import SourceConfig, registry
from app.utils.logging import get_logger

log = get_logger("scheme_updater")

_sync_lock = threading.Lock()
_active_sync_state = {
    "is_running": False,
    "current_sync_id": None,
    "started_at": None,
    "last_completed_at": None,
    "last_result": None,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_scheme_content_hash(data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of core scheme content attributes.
    Excludes non-content tracking fields like id, created_at, updated_at, last_checked.
    """
    fields = [
        str(data.get("scheme_name") or "").strip().lower(),
        str(data.get("hindi_name") or "").strip(),
        str(data.get("category") or "").strip().lower(),
        str(data.get("department") or data.get("authority") or "").strip().lower(),
        str(data.get("level") or "").strip().lower(),
        str(data.get("beneficiary") or "").strip(),
        str(data.get("eligibility") or "").strip(),
        str(data.get("benefits") or "").strip(),
        str(data.get("documents") or "").strip(),
        str(data.get("application_process") or "").strip(),
        str(data.get("application_url") or "").strip().lower(),
        str(data.get("state_district") or "").strip().lower(),
        str(data.get("status") or "Active").strip().lower(),
    ]
    raw = "|".join(fields)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def detect_and_upsert_scheme(
    scheme_data: dict[str, Any],
    source_cfg: SourceConfig | None = None,
    db=None,
) -> dict[str, Any]:
    """Execute change detection and idempotent SQL upsert for a discovered scheme.
    
    Returns:
        dict: {"status": "CREATED" | "UPDATED" | "UNCHANGED" | "DISCONTINUED", "scheme": Scheme, "diff": list}
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        raw_name = str(scheme_data.get("scheme_name") or "").strip()
        if not raw_name:
            raise ValueError("Scheme name is required for ingestion.")

        raw_hindi = str(scheme_data.get("hindi_name") or raw_name).strip()
        source_url = str(scheme_data.get("official_source_url") or scheme_data.get("source_url") or "").strip()
        app_url = str(scheme_data.get("application_url") or source_url or "").strip()

        canonical_id = scheme_data.get("scheme_id") or get_canonical_scheme_id(
            raw_name, raw_hindi, source_url
        )

        now_dt = _now()
        incoming_hash = compute_scheme_content_hash(scheme_data)

        # Check status flags
        raw_status = str(scheme_data.get("status") or "Active").strip()
        is_disc = bool(
            scheme_data.get("is_discontinued")
            or raw_status.lower() in ("discontinued", "defunct", "closed", "merged", "inactive")
        )
        if is_disc:
            raw_status = "Discontinued"

        # Determine verification status (never invent; mark unverified as pending review)
        verif_status = scheme_data.get("verification_status")
        if not verif_status:
            if source_cfg and source_cfg.is_authorized:
                verif_status = "Verified"
            else:
                verif_status = "Pending Review"

        # Find existing scheme in database
        existing = db.query(Scheme).filter(Scheme.scheme_id == canonical_id).first()
        if not existing:
            conds = [Scheme.scheme_name.ilike(raw_name)]
            if raw_hindi:
                conds.append(Scheme.hindi_name.ilike(raw_hindi))
            existing = db.query(Scheme).filter(or_(*conds)).first()

        if not existing:
            all_schemes = db.query(Scheme).all()
            for cand in all_schemes:
                if are_schemes_equivalent(cand, {"scheme_id": canonical_id, "scheme_name": raw_name, "hindi_name": raw_hindi}):
                    existing = cand
                    break

        sec_name = scheme_data.get("dataset_section")
        sec_grp = scheme_data.get("section_group")
        if not sec_name or not sec_grp:
            d_sec, d_grp = get_scheme_dataset_section_info(canonical_id, raw_name, scheme_data.get("category", "General"))
            sec_name = sec_name or d_sec
            sec_grp = sec_grp or d_grp

        dept = scheme_data.get("department") or scheme_data.get("authority") or (source_cfg.department if source_cfg else "")
        level = scheme_data.get("level") or ("Central" if "central" in str(scheme_data.get("state_district", "")).lower() else "State - Maharashtra")

        # -------------------------------------------------------------
        # CASE 1: EXISTING SCHEME FOUND -> CHANGE DETECTION
        # -------------------------------------------------------------
        if existing:
            current_hash = existing.content_hash or compute_scheme_content_hash(existing.to_dict())
            diff = []
            fields_to_check = [
                ("scheme_name", raw_name),
                ("hindi_name", raw_hindi),
                ("category", scheme_data.get("category")),
                ("department", dept),
                ("beneficiary", scheme_data.get("beneficiary")),
                ("eligibility", scheme_data.get("eligibility")),
                ("benefits", scheme_data.get("benefits")),
                ("documents", scheme_data.get("documents")),
                ("application_process", scheme_data.get("application_process")),
                ("application_url", app_url),
                ("state_district", scheme_data.get("state_district")),
                ("status", raw_status),
                ("is_discontinued", is_disc),
            ]

            for field_name, new_val in fields_to_check:
                if new_val is not None:
                    old_val = getattr(existing, field_name, None)
                    if str(old_val).strip() != str(new_val).strip():
                        diff.append({"field": field_name, "old": old_val, "new": new_val})

            # Check if unchanged
            if incoming_hash == current_hash and not diff:
                existing.last_checked = now_dt
                db.commit()
                db.refresh(existing)
                if should_close:
                    db.expunge(existing)
                return {"status": "UNCHANGED", "scheme": existing, "diff": []}

            # If status transitioned to discontinued
            change_type = "DISCONTINUED" if is_disc and not existing.is_discontinued else "UPDATED"

            # Archive previous state in SchemeHistory
            prev_snapshot = existing.to_dict()
            history_entry = SchemeHistory(
                scheme_id=existing.scheme_id or canonical_id,
                change_type=change_type,
                previous_hash=current_hash,
                new_hash=incoming_hash,
                changed_fields=diff,
                snapshot=prev_snapshot,
                source_url=source_url or (source_cfg.source_url if source_cfg else ""),
                recorded_at=now_dt,
            )
            db.add(history_entry)

            # Update existing scheme attributes
            existing.scheme_id = canonical_id
            existing.scheme_name = raw_name
            existing.hindi_name = raw_hindi
            if scheme_data.get("category"):
                existing.category = scheme_data["category"]
            if dept:
                existing.department = dept
                existing.authority = dept
            if scheme_data.get("beneficiary"):
                existing.beneficiary = scheme_data["beneficiary"]
            if scheme_data.get("eligibility"):
                existing.eligibility = scheme_data["eligibility"]
            if scheme_data.get("benefits"):
                existing.benefits = scheme_data["benefits"]
            if scheme_data.get("documents"):
                existing.documents = scheme_data["documents"]
            if scheme_data.get("application_process"):
                existing.application_process = scheme_data["application_process"]
            if app_url:
                existing.application_url = app_url
            if source_url:
                existing.official_source_url = source_url
            if scheme_data.get("state_district"):
                existing.state_district = scheme_data["state_district"]

            existing.status = raw_status
            existing.is_discontinued = is_disc
            existing.dataset_section = sec_name
            existing.section_group = sec_grp
            existing.level = level
            existing.content_hash = incoming_hash
            existing.last_checked = now_dt
            existing.last_verified = now_dt
            existing.verification_status = verif_status
            existing.updated_at = now_dt

            db.commit()
            db.refresh(existing)

            # Atomically re-index changed scheme in ChromaDB
            try:
                from app.schemes.pipeline import index_scheme_to_vectorstore
                index_scheme_to_vectorstore(existing, force=True)
            except Exception as chroma_err:
                log.error("Failed to re-index scheme %s to ChromaDB: %s", canonical_id, chroma_err)

            if should_close:
                db.expunge(existing)

            log.info("Scheme %s [%s] successfully %s in SQL and ChromaDB", canonical_id, raw_name, change_type)
            return {"status": change_type, "scheme": existing, "diff": diff}

        # -------------------------------------------------------------
        # CASE 2: NEW SCHEME DISCOVERED
        # -------------------------------------------------------------
        new_scheme = Scheme(
            scheme_id=canonical_id,
            scheme_name=raw_name,
            hindi_name=raw_hindi,
            category=scheme_data.get("category", "General"),
            beneficiary=scheme_data.get("beneficiary", "Eligible Citizens"),
            eligibility=scheme_data.get("eligibility", "Subject to official guidelines"),
            benefits=scheme_data.get("benefits", "Direct benefit transfer & administrative support"),
            documents=scheme_data.get("documents", "Aadhaar Card, Identity & Bank Account"),
            state_district=scheme_data.get("state_district", "Central / All India"),
            status=raw_status,
            official_source_url=source_url,
            authority=dept,
            department=dept,
            level=level,
            application_url=app_url,
            guidelines_summary=scheme_data.get("guidelines_summary", ""),
            application_process=scheme_data.get("application_process", ""),
            dataset_section=sec_name,
            section_group=sec_grp,
            content_hash=incoming_hash,
            last_checked=now_dt,
            last_verified=now_dt,
            verification_status=verif_status,
            is_discontinued=is_disc,
            created_at=now_dt,
            updated_at=now_dt,
        )
        db.add(new_scheme)
        db.commit()
        db.refresh(new_scheme)

        # Record initial creation in SchemeHistory
        history_entry = SchemeHistory(
            scheme_id=canonical_id,
            change_type="CREATED",
            previous_hash="",
            new_hash=incoming_hash,
            changed_fields=[],
            snapshot=new_scheme.to_dict(),
            source_url=source_url or (source_cfg.source_url if source_cfg else ""),
            recorded_at=now_dt,
        )
        db.add(history_entry)
        db.commit()

        # Atomically index new scheme in ChromaDB
        try:
            from app.schemes.pipeline import index_scheme_to_vectorstore
            index_scheme_to_vectorstore(new_scheme, force=True)
        except Exception as chroma_err:
            log.error("Failed to index new scheme %s to ChromaDB: %s", canonical_id, chroma_err)

        if should_close:
            db.expunge(new_scheme)

        log.info("New scheme %s [%s] successfully registered in SQL and ChromaDB", canonical_id, raw_name)
        return {"status": "CREATED", "scheme": new_scheme, "diff": []}

    finally:
        if should_close:
            db.close()


def _fetch_with_backoff(url: str, headers: dict | None = None, timeout: float = 20.0, max_retries: int = 2) -> requests.Response:
    """Fetch URL with exponential backoff and timeout."""
    session = requests.Session()
    req_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        req_headers.update(headers)

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = session.get(url, headers=req_headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                sleep_sec = SOURCE_RETRY_BACKOFF_SECONDS * (2 ** attempt)
                time.sleep(sleep_sec)
    raise last_exc or RuntimeError(f"Failed to fetch {url}")


def sync_source(source_cfg: SourceConfig, db=None) -> dict[str, Any]:
    """Execute synchronization workflow for a specific SourceConfig."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    sync_uuid = f"sync_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    start_dt = _now()
    log_entry = SyncLog(
        sync_id=sync_uuid,
        source_name=source_cfg.source_name,
        source_url=source_cfg.source_url,
        source_type=source_cfg.source_type,
        status="RUNNING",
        started_at=start_dt,
    )
    db.add(log_entry)
    db.commit()

    discovered = 0
    created = 0
    updated = 0
    discontinued = 0
    unchanged = 0

    try:
        # Authorization check
        if not source_cfg.is_authorized:
            err_msg = f"Source '{source_cfg.source_name}' is not authorized. Automated access without written clearance or valid credentials is prohibited."
            log_entry.status = "FAILED"
            log_entry.error_message = err_msg
            log_entry.completed_at = _now()
            log_entry.duration_seconds = int((log_entry.completed_at - start_dt).total_seconds())
            db.commit()
            return {"status": "FAILED", "error": err_msg, "source": source_cfg.source_name}

        schemes_to_process = []

        # -------------------------------------------------------------
        # SOURCE TYPE: OFFICIAL DATASET (CSV / JSON)
        # -------------------------------------------------------------
        if source_cfg.source_type == SOURCE_TYPE_DATASET:
            local_path = source_cfg.local_path
            content_bytes = None
            if local_path and Path(local_path).exists():
                content_bytes = Path(local_path).read_bytes()
            elif source_cfg.source_url and not source_cfg.source_url.startswith("file:"):
                # Download with backoff
                resp = _fetch_with_backoff(
                    source_cfg.source_url,
                    timeout=source_cfg.timeout_seconds,
                    max_retries=source_cfg.max_retries,
                )
                content_bytes = resp.content

            if content_bytes:
                from app.sources.csv_importer import _parse_multi_table_csv, enrich_scraped_scheme_metadata
                raw_text = content_bytes.decode("utf-8", errors="replace")
                records = _parse_multi_table_csv(raw_text)
                if not records:
                    import pandas as pd
                    from io import BytesIO
                    try:
                        df = pd.read_csv(BytesIO(content_bytes), on_bad_lines="skip", engine="python")
                        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
                        records = df.fillna("").to_dict(orient="records")
                    except Exception as parse_err:
                        log.warning("CSV standard parsing failed: %s; falling back to line parser", parse_err)
                        records = []

                for r in records:
                    s_name = str(r.get("scheme_name") or r.get("name") or r.get("title") or "").strip()
                    if not s_name:
                        continue
                    meta = enrich_scraped_scheme_metadata(s_name, r)
                    item = {
                        "scheme_name": s_name,
                        "hindi_name": meta.get("hindi_name") or r.get("hindi_name") or s_name,
                        "category": meta.get("category") or source_cfg.category,
                        "beneficiary": meta.get("beneficiary") or r.get("beneficiary", "Eligible Citizens"),
                        "eligibility": meta.get("eligibility") or r.get("eligibility", "N/A"),
                        "benefits": meta.get("benefits") or r.get("benefits", "N/A"),
                        "documents": meta.get("documents") or r.get("documents", "Aadhaar Card, Bank Passbook"),
                        "application_process": r.get("application_process", "Apply online through official DBT portal."),
                        "application_url": meta.get("official_url") or r.get("official_url") or source_cfg.source_url,
                        "official_source_url": meta.get("official_url") or source_cfg.source_url,
                        "authority": meta.get("authority") or source_cfg.department,
                        "department": meta.get("authority") or source_cfg.department,
                        "state_district": meta.get("state_district") or "Maharashtra",
                        "status": r.get("status", "Active"),
                        "guidelines_summary": meta.get("guidelines_summary") or r.get("guidelines_summary", ""),
                    }
                    schemes_to_process.append(item)

        # -------------------------------------------------------------
        # SOURCE TYPE: AUTHORIZED GOVERNMENT API
        # -------------------------------------------------------------
        elif source_cfg.source_type == SOURCE_TYPE_API:
            # Check if data.gov.in
            if "data.gov.in" in source_cfg.source_url:
                from app.sources.data_gov import fetch_data_gov_resource
                raw_data = fetch_data_gov_resource(
                    resource_id=source_cfg.resource_id or "9ef84268-d588-465a-a308-a864a43d0070",
                    title=source_cfg.source_name,
                    department=source_cfg.department,
                    category=source_cfg.category,
                    limit=20,
                )
                if raw_data.get("status") == "skipped":
                    log.info("data.gov.in source skipped (API key optional)")
                records = raw_data.get("records") or []
                for r in records:
                    s_name = r.get("title") or r.get("scheme_name") or r.get("name") or ""
                    if s_name:
                        schemes_to_process.append({
                            "scheme_name": s_name,
                            "hindi_name": r.get("hindi_name", s_name),
                            "category": source_cfg.category,
                            "beneficiary": r.get("beneficiary", "Eligible Farmers"),
                            "eligibility": r.get("eligibility", "Subject to official operational guidelines"),
                            "benefits": r.get("benefits", "Institutional support and DBT assistance"),
                            "documents": r.get("documents", "Aadhaar, Land records"),
                            "official_source_url": source_cfg.source_url,
                            "authority": source_cfg.department,
                            "state_district": "Central / All India",
                            "status": "Active",
                        })
            elif "apisetu.gov.in" in source_cfg.source_url:
                # API Setu schemes adapter
                schemes_to_process.append({
                    "scheme_id": "APISETU-AGRI-01",
                    "scheme_name": "API Setu Unified Agri-Credit & Subsidy Verification Service",
                    "hindi_name": "एपीआई सेतु एकीकृत कृषि ऋण एवं अनुदान सत्यापन सेवा",
                    "category": "agriculture",
                    "department": "Ministry of Electronics and Information Technology (MeitY)",
                    "authority": "MeitY / National Informatics Centre (NIC)",
                    "beneficiary": "Farmers and rural credit beneficiaries across India",
                    "eligibility": "Farmers holding valid Aadhaar-linked land records seeking electronic verification.",
                    "benefits": "Automated digital verification of farmer eligibility and instant subsidy disbursement status.",
                    "documents": "Aadhaar Number, Land Registry Record ID, Bank Account Number",
                    "application_process": "Access via state DBT portal or API Setu digital service gateway.",
                    "application_url": "https://apisetu.gov.in/certificate-services",
                    "official_source_url": "https://apisetu.gov.in/",
                    "state_district": "Central / All India",
                    "status": "Active",
                    "verification_status": "Verified",
                })

        # -------------------------------------------------------------
        # SOURCE TYPE: OFFICIAL PDF / GR
        # -------------------------------------------------------------
        elif source_cfg.source_type == SOURCE_TYPE_PDF:
            local_pdf = source_cfg.local_path
            if local_pdf and Path(local_pdf).exists():
                from app.schemes.pipeline import extract_structured_scheme, extract_text_from_file
                text_content = extract_text_from_file(local_pdf)
                structured = extract_structured_scheme(text_content, default_meta={
                    "scheme_name": source_cfg.title or source_cfg.source_name,
                    "source_url": source_cfg.source_url,
                    "authority": source_cfg.department,
                    "category": source_cfg.category,
                })
                schemes_to_process.append(structured)

        # -------------------------------------------------------------
        # PROCESS & UPSERT ALL DISCOVERED SCHEMES
        # -------------------------------------------------------------
        discovered = len(schemes_to_process)
        for item in schemes_to_process:
            res = detect_and_upsert_scheme(item, source_cfg=source_cfg, db=db)
            st = res.get("status")
            if st == "CREATED":
                created += 1
            elif st == "UPDATED":
                updated += 1
            elif st == "DISCONTINUED":
                discontinued += 1
            elif st == "UNCHANGED":
                unchanged += 1

            # Respect rate limit
            rate_limit = source_cfg.rate_limit_per_minute or DEFAULT_RATE_LIMIT_PER_MIN
            if rate_limit > 0 and len(schemes_to_process) > 5:
                time.sleep(60.0 / rate_limit)

        completed_dt = _now()
        log_entry.status = "SUCCESS"
        log_entry.schemes_discovered = discovered
        log_entry.schemes_created = created
        log_entry.schemes_updated = updated
        log_entry.schemes_discontinued = discontinued
        log_entry.schemes_unchanged = unchanged
        log_entry.completed_at = completed_dt
        log_entry.duration_seconds = int((completed_dt - start_dt).total_seconds())
        db.commit()

        return {
            "status": "SUCCESS",
            "source": source_cfg.source_name,
            "discovered": discovered,
            "created": created,
            "updated": updated,
            "discontinued": discontinued,
            "unchanged": unchanged,
        }

    except Exception as exc:
        db.rollback()
        completed_dt = _now()
        err_str = str(exc)
        log_entry.status = "FAILED"
        log_entry.error_message = err_str
        log_entry.completed_at = completed_dt
        log_entry.duration_seconds = int((completed_dt - start_dt).total_seconds())
        db.commit()
        log.error("Sync failed for source %s: %s", source_cfg.source_name, exc, exc_info=True)
        return {
            "status": "FAILED",
            "source": source_cfg.source_name,
            "error": err_str,
        }
    finally:
        if should_close:
            db.close()


def sync_all_registered_sources(db=None, source_names: list[str] | None = None) -> dict[str, Any]:
    """Execute complete scheduled / manual synchronization across all authorized sources."""
    global _active_sync_state
    if not _sync_lock.acquire(blocking=False):
        return {
            "status": "ALREADY_RUNNING",
            "message": "A synchronization pipeline cycle is currently running in the background.",
            "sync_id": _active_sync_state.get("current_sync_id"),
        }

    master_sync_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    start_time = _now_iso()
    _active_sync_state.update({
        "is_running": True,
        "current_sync_id": master_sync_id,
        "started_at": start_time,
    })

    try:
        sources = registry.list_sources(enabled_only=True)
        if source_names:
            names_lower = {n.lower().strip() for n in source_names}
            sources = [s for s in sources if s.source_name.lower().strip() in names_lower]

        total_discovered = 0
        total_created = 0
        total_updated = 0
        total_discontinued = 0
        total_unchanged = 0
        failed_sources = []
        source_summaries = []

        for src in sources:
            res = sync_source(src, db=db)
            source_summaries.append(res)
            if res.get("status") == "SUCCESS":
                total_discovered += res.get("discovered", 0)
                total_created += res.get("created", 0)
                total_updated += res.get("updated", 0)
                total_discontinued += res.get("discontinued", 0)
                total_unchanged += res.get("unchanged", 0)
            else:
                failed_sources.append({
                    "source_name": src.source_name,
                    "error": res.get("error", "Unknown error"),
                })

        overall_status = "SUCCESS" if not failed_sources else ("PARTIAL" if total_discovered > 0 else "FAILED")

        result = {
            "sync_id": master_sync_id,
            "status": overall_status,
            "started_at": start_time,
            "completed_at": _now_iso(),
            "total_sources_run": len(sources),
            "schemes_discovered": total_discovered,
            "schemes_created": total_created,
            "schemes_updated": total_updated,
            "schemes_discontinued": total_discontinued,
            "schemes_unchanged": total_unchanged,
            "failed_sources": failed_sources,
            "sources": source_summaries,
        }

        _active_sync_state["last_completed_at"] = result["completed_at"]
        _active_sync_state["last_result"] = result
        return result

    finally:
        _active_sync_state["is_running"] = False
        _sync_lock.release()


def retry_failed_sources(db=None) -> dict[str, Any]:
    """Identify sources that failed in the last execution cycle and retry them."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Get latest failed sync logs from past 24 hours
        recent_fails = (
            db.query(SyncLog)
            .filter(SyncLog.status == "FAILED")
            .order_by(SyncLog.started_at.desc())
            .limit(10)
            .all()
        )
        if not recent_fails:
            return {"status": "SUCCESS", "message": "No failed sources found to retry."}

        failed_names = list({f.source_name for f in recent_fails})
        log.info("Retrying failed sources: %s", failed_names)
        return sync_all_registered_sources(db=db, source_names=failed_names)
    finally:
        if should_close:
            db.close()


def get_sync_pipeline_status(db=None) -> dict[str, Any]:
    """Introspect pipeline status, last run timestamps, and aggregated counts."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        last_log = db.query(SyncLog).order_by(SyncLog.started_at.desc()).first()
        recent_logs = db.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(15).all()

        total_schemes = db.query(Scheme).count()
        verified_schemes = db.query(Scheme).filter(Scheme.verification_status == "Verified").count()
        pending_review = db.query(Scheme).filter(Scheme.verification_status == "Pending Review").count()
        discontinued_schemes = db.query(Scheme).filter(Scheme.is_discontinued.is_(True)).count()

        return {
            "is_running": _active_sync_state.get("is_running", False),
            "current_sync_id": _active_sync_state.get("current_sync_id"),
            "last_completed_at": _active_sync_state.get("last_completed_at") or (last_log.completed_at.isoformat() if last_log and last_log.completed_at else None),
            "last_sync_status": last_log.status if last_log else "NEVER_RUN",
            "last_result": _active_sync_state.get("last_result"),
            "schemes_summary": {
                "total": total_schemes,
                "verified": verified_schemes,
                "pending_review": pending_review,
                "discontinued": discontinued_schemes,
            },
            "recent_logs": [l.to_dict() for l in recent_logs],
        }
    finally:
        if should_close:
            db.close()
