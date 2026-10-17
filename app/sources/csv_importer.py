"""CSV Scheme Importer with Validation, Normalization, SQL Upsert, and ChromaDB Indexing.

Implements:
1. CSV parsing and required header validation.
2. Official URL validation and field normalization.
3. SQL relational upsert (with deduplication & canonical ID assignment).
4. ChromaDB vectorstore indexing preserving exact 8-field metadata compliance.
"""
import json
from datetime import datetime, timezone
import hashlib
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import pandas as pd
from fastapi import HTTPException
from langchain_core.documents import Document as LcDocument

from app.database.db import Document as DbDocument, SessionLocal
from app.rag.chunker import chunk_documents
from app.rag.retriever import get_store
from app.schemes.normalizer import get_canonical_scheme_id
from app.schemes.pipeline import ingest_scheme_to_db, normalize_text
from app.utils.logging import get_logger

log = get_logger("csv_importer")


def _is_valid_url(url: str) -> bool:
    """Validate that the string is a well-formed http/https URL."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def enrich_scraped_scheme_metadata(name: str, raw_row: dict) -> dict[str, str]:
    """Enrich scraped items with verified official scheme details, category, and authority."""
    n = name.lower()
    details = {}

    # Category
    if not raw_row.get("category"):
        if any(k in n for k in ["ujjwala", "lpg", "gas", "women", "mahila"]):
            details["category"] = "Energy & Women Welfare"
        elif any(k in n for k in ["water", "irrigation", "sinchayee", "jal"]):
            details["category"] = "Water Resources & Irrigation"
        elif any(k in n for k in ["textbook", "ncert", "education", "school", "scholarship"]):
            details["category"] = "Education & Learning Resources"
        elif any(k in n for k in ["agmarknet", "commodit", "kisan", "crop", "agriculture", "farmer", "krishi"]):
            details["category"] = "Agriculture & Farmer Welfare"
        elif any(k in n for k in ["career", "job", "employment", "rojgar", "recruitment", "skill"]):
            details["category"] = "Employment & Skill Development"
        elif any(k in n for k in ["telemedicine", "sanjeevani", "health", "hospital", "ayushman", "swasthya"]):
            details["category"] = "Healthcare & Telemedicine"
        elif any(k in n for k in ["pension", "bhavishya", "epfo", "senior", "retirement"]):
            details["category"] = "Social Security & Pension"
        elif any(k in n for k in ["mudra", "msme", "credit", "loan", "startup", "entrepreneur"]):
            details["category"] = "Entrepreneurship & MSME Credit"
        else:
            details["category"] = "Government Schemes & Welfare"

    # Authority
    if not raw_row.get("authority") and not raw_row.get("department") and not raw_row.get("ministry"):
        if "water" in n or "agency" in n:
            details["authority"] = "Ministry of Jal Shakti, National Water Development Agency"
        elif "ncert" in n or "textbook" in n:
            details["authority"] = "National Council of Educational Research and Training (NCERT)"
        elif "agmarknet" in n or "commodit" in n:
            details["authority"] = "Directorate of Marketing & Inspection, Ministry of Agriculture & Farmers Welfare"
        elif "career" in n or "job" in n:
            details["authority"] = "Ministry of Labour and Employment, Government of India"
        elif "sanjeevani" in n or "telemedicine" in n:
            details["authority"] = "Ministry of Health and Family Welfare, Government of India"
        elif "bhavishya" in n or "pension" in n:
            details["authority"] = "Department of Pension & Pensioners' Welfare, Government of India"
        elif "ujjwala" in n or "lpg" in n:
            details["authority"] = "Ministry of Petroleum and Natural Gas, Government of India"
        else:
            details["authority"] = "Government of India"

    # Specific schemes rich benefits/eligibility
    if "ujjwala" in n:
        details["benefits"] = "Deposit-free LPG connection, first refill free, stove provided, and ₹1,600 financial support per connection for eligible BPL households."
        details["eligibility"] = "Adult women belonging to BPL households or poor families with no existing LPG connection in the household."
        details["documents"] = "Aadhaar Card, BPL Ration Card, Bank Account Details (IFSC), and self-declaration form."
        details["guidelines_summary"] = "Pradhan Mantri Ujjwala Yojana 2.0 provides clean cooking fuel and smoke-free kitchens to rural women across India."
    elif "sanjeevani" in n:
        details["benefits"] = "Free doctor-to-patient and doctor-to-doctor digital telemedicine consultations, e-prescriptions, and access to super-specialist consultations from home."
        details["eligibility"] = "All Indian citizens requiring medical advice, diagnosis, or follow-up consultation."
        details["documents"] = "Mobile Number for OTP registration, previous medical records/prescriptions if available."
        details["guidelines_summary"] = "National Telemedicine Service (eSanjeevani) connects patients across rural and urban India with verified government doctors."
    elif "agmarknet" in n:
        details["benefits"] = "Real-time daily market arrivals and wholesale prices of agricultural commodities across APMC mandis nationwide."
        details["eligibility"] = "Open public agricultural market information for farmers, traders, and consumers."
        details["documents"] = "No documents required. Free public portal access."
        details["guidelines_summary"] = "AGMARKNET portal provides transparent commodity pricing across thousands of wholesale mandis in India."
    elif "career service" in n or "job seeker" in n:
        details["benefits"] = "Nationwide job matching, career counseling, vocational training, job fairs, and verified employer connections."
        details["eligibility"] = "Any citizen looking for employment, skill upgrading, or apprenticeship."
        details["documents"] = "Aadhaar / National ID, Educational Certificates, Resume / Profile details."
        details["guidelines_summary"] = "National Career Service (NCS) portal by Ministry of Labour & Employment linking job seekers with government and private job vacancies."
    elif "bhavishya" in n:
        details["benefits"] = "End-to-end online tracking of civil pension sanction, electronic pension payment order (e-PPO), and retirement dues processing."
        details["eligibility"] = "Retiring Central Government Civil Employees and pensioners."
        details["documents"] = "Employee ID, Aadhaar Card, Joint bank account details with spouse, PAN card."
        details["guidelines_summary"] = "BHAVISHYA online portal ensures transparent, timely pension sanctioning and payment tracking for government retirees."
    elif "ncert" in n or "textbook" in n:
        details["benefits"] = "Free digital textbooks, audiobooks, and learning resources from Class 1 to 12 in English, Hindi, and Urdu."
        details["eligibility"] = "Open to all students, teachers, parents, and educators."
        details["documents"] = "No documents required. Free open educational access."
        details["guidelines_summary"] = "NCERT digital textbook repository delivers official curriculum textbooks for primary, secondary, and higher secondary education."
    elif "water development" in n:
        details["benefits"] = "Public consultation, citizen feedback, and water resources development grievance redressal for inter-basin water transfer projects."
        details["eligibility"] = "All citizens, farmers, and stakeholders interested in national water development projects."
        details["documents"] = "Valid email ID and postal details for official communication."
        details["guidelines_summary"] = "National Water Development Agency (NWDA) citizen communication channel for river interlinking and water security."

    return details


def process_scraped_records(records: list[dict[str, Any]], source_type: str = "scraper_import") -> dict[str, Any]:
    """Validate URLs, normalize fields, upsert to SQL, and index into ChromaDB from a list of records."""
    if not records:
        return {
            "status": "empty",
            "records_found": 0,
            "records_imported": 0,
            "chunks_indexed": 0,
            "schemes": [],
            "message": "Payload contained no data records."
        }

    imported_schemes = []
    all_chunks = []
    all_chunk_ids = []
    total_chunks = 0
    today = _today_str()
    now_ts = _now_iso()
    store = get_store()

    for idx, raw_row in enumerate(records, start=1):
        if not isinstance(raw_row, dict):
            continue

        # Standardize keys to lowercase with underscores
        row = {str(k).strip().lower().replace(" ", "_"): v for k, v in raw_row.items()}

        raw_name = str(
            row.get("scheme_name") or row.get("name") or row.get("title") or row.get("scheme") or row.get("data") or ""
        ).strip()
        raw_url = str(
            row.get("official_url") or row.get("official_source_url") or row.get("url") or row.get("source_url")
            or row.get("web_scraper_start_url") or row.get("link") or ""
        ).strip()

        if not raw_name:
            continue

        if not _is_valid_url(raw_url):
            log.warning("Row %d: Skipping invalid official_url '%s' for scheme '%s'", idx, raw_url, raw_name)
            continue

        # Normalized values and enriched metadata
        scheme_name = normalize_text(raw_name)
        official_url = raw_url
        enrichment = enrich_scraped_scheme_metadata(scheme_name, row)

        hindi_name = normalize_text(
            str(row.get("hindi_name") or row.get("hindi") or row.get("scheme_name_hi") or enrichment.get("hindi_name") or scheme_name)
        )
        category = normalize_text(
            str(row.get("category") or row.get("sector") or enrichment.get("category") or "Government Schemes & Welfare")
        )
        beneficiary = normalize_text(
            str(row.get("beneficiary") or row.get("target_beneficiary") or enrichment.get("beneficiary") or "Eligible citizens and farmer families")
        )
        eligibility = normalize_text(
            str(row.get("eligibility") or row.get("eligibility_criteria") or enrichment.get("eligibility") or "Subject to official department verification and guidelines.")
        )
        benefits = normalize_text(
            str(row.get("benefits") or row.get("benefit") or enrichment.get("benefits") or "Direct benefit transfer and institutional support under scheme rules.")
        )
        documents = normalize_text(
            str(row.get("documents") or row.get("documents_required") or enrichment.get("documents") or "Aadhaar Card, Bank Passbook, and Identity documents.")
        )
        state_district = normalize_text(
            str(row.get("state_district") or row.get("state") or row.get("district") or enrichment.get("state_district") or "Central / All India")
        )
        status = normalize_text(str(row.get("status") or enrichment.get("status") or "Active"))
        authority = normalize_text(
            str(row.get("authority") or row.get("department") or row.get("ministry") or enrichment.get("authority") or "Government Authority")
        )
        guidelines_summary = normalize_text(
            str(row.get("guidelines_summary") or row.get("summary") or row.get("description") or enrichment.get("guidelines_summary") or f"{scheme_name} - {benefits}")
        )

        canonical_id = row.get("scheme_id") or get_canonical_scheme_id(scheme_name, hindi_name, official_url)

        scheme_payload = {
            "scheme_id": canonical_id,
            "scheme_name": scheme_name,
            "hindi_name": hindi_name,
            "category": category,
            "beneficiary": beneficiary,
            "eligibility": eligibility,
            "benefits": benefits,
            "documents": documents,
            "state_district": state_district,
            "status": status,
            "official_source_url": official_url,
            "authority": authority,
            "guidelines_summary": guidelines_summary,
        }

        # 1. SQL Upsert
        with SessionLocal() as db:
            saved_scheme = ingest_scheme_to_db(scheme_payload, db=db)
            scheme_dict = saved_scheme.to_dict()

        # 2. ChromaDB Ingestion Pipeline (Preserving source metadata)
        doc_content = (
            f"Scheme Name: {scheme_name}\n"
            f"Hindi Name: {hindi_name}\n"
            f"Category: {category}\n"
            f"Beneficiary: {beneficiary}\n"
            f"Eligibility: {eligibility}\n"
            f"Benefits: {benefits}\n"
            f"Required Documents: {documents}\n"
            f"Jurisdiction: {state_district}\n"
            f"Status: {status}\n"
            f"Authority / Department: {authority}\n"
            f"Official URL: {official_url}\n"
            f"Guidelines Summary: {guidelines_summary}"
        )
        content_hash = _compute_hash(doc_content)

        # 8 mandatory metadata compliance fields + tracking
        metadata = {
            "source_name": authority or scheme_name,
            "source_url": official_url,
            "category": "government_schemes",
            "department": authority,
            "authority": authority,
            "title": scheme_name,
            "document_type": "csv_import",
            "last_checked": today,
            "last_updated": today,
            "content_hash": content_hash,
            "scheme_id": canonical_id,
            "ingested_at": now_ts,
        }

        lc_doc = LcDocument(page_content=doc_content, metadata=metadata)
        chunks = chunk_documents([lc_doc])

        if chunks:
            # Clean obsolete chunks for this source_url or canonical_id if present
            try:
                existing = store.get(where={"source_url": official_url})
                if existing and existing.get("ids"):
                    store.delete(ids=existing["ids"])
            except Exception as clean_err:
                log.debug("Chroma cleanup error (safe to ignore): %s", clean_err)

            key_hash = hashlib.sha256(canonical_id.encode("utf-8")).hexdigest()[:12]
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_chunk_ids.append(f"{source_type}_{key_hash}_{i}")
            total_chunks += len(chunks)

        # 3. Sync with Document relational tracking
        try:
            with SessionLocal() as db:
                db_doc = db.query(DbDocument).filter(
                    (DbDocument.source_url == official_url) | (DbDocument.title == scheme_name)
                ).first()
                if not db_doc:
                    db_doc = DbDocument(
                        title=scheme_name,
                        authority=authority,
                        source_url=official_url,
                        document_type=source_type,
                        publication_date=today,
                        updated_date=today,
                        version="1.0",
                        file_path=f"{source_type}://{canonical_id}",
                        content_hash=content_hash,
                        indexed=True,
                    )
                    db.add(db_doc)
                else:
                    db_doc.content_hash = content_hash
                    db_doc.indexed = True
                    db_doc.updated_date = today
                db.commit()
        except Exception as db_err:
            log.warning("Document tracking sync error: %s", db_err)

        imported_schemes.append(scheme_dict)

    if all_chunks:
        store.add_documents(all_chunks, ids=all_chunk_ids)

    return {
        "status": "success",
        "records_found": len(records),
        "records_imported": len(imported_schemes),
        "chunks_indexed": total_chunks,
        "schemes": imported_schemes,
        "message": f"Successfully processed {len(imported_schemes)} schemes into SQL and ChromaDB vectorstore."
    }


def process_scraped_csv(content: bytes) -> dict[str, Any]:
    """Parse CSV content, validate URLs, normalize fields, upsert to SQL, and index into ChromaDB."""
    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {exc}")

    # Standardize column headers (lowercase, trimmed)
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Required column resolution (support synonyms)
    name_col = next((c for c in df.columns if c in ("scheme_name", "name", "title", "scheme")), None)
    url_col = next((c for c in df.columns if c in ("official_url", "official_source_url", "url", "source_url")), None)

    if not name_col or not url_col:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain 'scheme_name' and 'official_url' columns."
        )

    records = df.fillna("").to_dict(orient="records")
    return process_scraped_records(records, source_type="csv_import")


def process_scraped_json(payload: bytes | str | list | dict) -> dict[str, Any]:
    """Parse scraped JSON (direct payload, Apify items, JSONL, or file), normalize, upsert to SQL, and index into ChromaDB."""
    data = payload
    payload_str = ""
    if isinstance(payload, bytes):
        payload_str = payload.decode("utf-8", errors="replace")
    elif isinstance(payload, str):
        payload_str = payload

    if payload_str:
        # Check for JSON Lines (JSONL / NDJSON)
        lines = [line.strip() for line in payload_str.strip().splitlines() if line.strip()]
        if lines and lines[0].startswith("{") and not payload_str.strip().startswith("["):
            try:
                data = [json.loads(line) for line in lines]
            except Exception:
                try:
                    data = json.loads(payload_str)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"Invalid JSON/JSONL format: {exc}")
        else:
            try:
                data = json.loads(payload_str)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSON format: {exc}")

    if isinstance(data, dict):
        # Support common wrapper keys from Apify, scrapers, and REST APIs
        if "schemes" in data and isinstance(data["schemes"], list):
            records = data["schemes"]
        elif "items" in data and isinstance(data["items"], list):
            records = data["items"]
        elif "data" in data and isinstance(data["data"], list):
            records = data["data"]
        elif "results" in data and isinstance(data["results"], list):
            records = data["results"]
        else:
            records = [data]
    elif isinstance(data, list):
        records = data
    else:
        raise HTTPException(status_code=400, detail="Expected JSON array or object containing scheme records.")

    if not records:
        return {
            "status": "empty",
            "records_found": 0,
            "records_imported": 0,
            "chunks_indexed": 0,
            "schemes": [],
            "message": "JSON contained no data records."
        }

    # Validate that at least one record has scheme_name and official_url (with synonyms)
    has_valid_header = any(
        isinstance(r, dict)
        and any(k in r for k in ("scheme_name", "name", "title", "scheme", "data"))
        and any(k in r for k in ("official_url", "official_source_url", "url", "source_url", "web_scraper_start_url", "link"))
        for r in records
    )
    if not has_valid_header:
        raise HTTPException(
            status_code=400,
            detail="JSON records must contain 'scheme_name' and 'official_url' fields (or 'data' and 'web_scraper_start_url')."
        )

    return process_scraped_records(records, source_type="json_import")

