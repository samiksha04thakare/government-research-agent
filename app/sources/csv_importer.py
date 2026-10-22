"""CSV Scheme Importer with Validation, Normalization, SQL Upsert, and ChromaDB Indexing.

Implements:
1. CSV parsing and required header validation.
2. Official URL validation and field normalization.
3. SQL relational upsert (with deduplication & canonical ID assignment).
4. ChromaDB vectorstore indexing preserving exact 8-field metadata compliance.
"""
import json
import re
from datetime import datetime, timezone
import hashlib
import io
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
    url_str = str(
        raw_row.get("official_url") or raw_row.get("official_source_url") or raw_row.get("url")
        or raw_row.get("web_scraper_start_url") or raw_row.get("link") or ""
    ).lower()
    details = {}

    # Check Maharashtra PoCRA (Nanaji Deshmukh Krishi Sanjivani Prakalp)
    if "mahapocra" in url_str or "pocra" in n:
        details["category"] = "Agriculture & Farmer Welfare"
        details["authority"] = "Department of Agriculture, Government of Maharashtra (Nanaji Deshmukh Krishi Sanjivani Prakalp / PoCRA)"
        details["state_district"] = "Maharashtra"
        details["official_url"] = "https://dbt.mahapocra.gov.in/"
        details["beneficiary"] = "Farmers, village communities, and Farmer Producer Organizations (FPOs/SHGs) in Maharashtra"
        if "communit" in n:
            details["hindi_name"] = "नानाजी देशमुख कृषी संजीवनी प्रकल्प - समुदाय डीबीटी (PoCRA Communities DBT)"
            details["benefits"] = "Financial assistance to execute community natural resource management works as per Village Development Plans (VDP)."
            details["eligibility"] = "Village Climate Change Adaptation Committees (VCCMC) and Gram Panchayats in PoCRA project villages."
            details["documents"] = "Gram Sabha resolution, approved Village Development Plan (VDP), VCCMC bank account details."
            details["guidelines_summary"] = "MahaPoCRA Communities DBT provides financial assistance to village-level institutions for community water, soil, and natural resource conservation."
        elif "fpo" in n or "self help" in n or "shg" in n:
            details["hindi_name"] = "नानाजी देशमुख कृषी संजीवनी प्रकल्प - एफपीओ व बचत गट डीबीटी (PoCRA FPO & SHG DBT)"
            details["benefits"] = "Financial grants and matching assistance for FPOs, FPCs, and Women SHGs for post-harvest processing, seed supply chain, and Custom Hiring Centres (CHC)."
            details["eligibility"] = "Registered Farmer Producer Companies (FPCs/FPOs) and active Women SHGs in PoCRA project districts."
            details["documents"] = "FPO/SHG registration certificate, audited balance sheets, business plan project report, bank account details."
            details["guidelines_summary"] = "MahaPoCRA FPO & Self Help Groups DBT supports farmer collectives and women SHGs in establishing agribusiness value chain infrastructure."
        else:
            details["hindi_name"] = "नानाजी देशमुख कृषी संजीवनी प्रकल्प - शेतकरी डीबीटी (PoCRA Farmers DBT)"
            details["benefits"] = "Direct benefit transfer (DBT) financial assistance and subsidies for climate-resilient farming, micro-irrigation, individual farm ponds, and horticulture under PoCRA."
            details["eligibility"] = "Small and marginal farmers residing in notified climate-vulnerable project villages across Maharashtra."
            details["documents"] = "7/12 extract (Satbara), 8-A land holding certificate, Aadhaar card, bank account linked with NPCI."
            details["guidelines_summary"] = "MahaPoCRA Farmers DBT enables registered farmers in 15 project districts of Maharashtra to apply directly for climate-resilient agricultural subsidies and financial assistance."
        return details

    # Check Maharashtra MSRTC 50% Concession for Women (Mahila Sanman Yojana)
    if "st-bus" in url_str or "msrtc" in url_str or "half-ticket" in url_str or "msrtc" in n or "half ticket" in n or "mahila sanman" in n or "concession on bus fare" in n:
        details["category"] = "Transport & Women Welfare"
        details["authority"] = "Maharashtra State Road Transport Corporation (MSRTC), Government of Maharashtra"
        details["state_district"] = "Maharashtra"
        details["official_url"] = "https://msrtc.maharashtra.gov.in/"
        details["hindi_name"] = "एसटी बस महिला सन्मान योजना (५०% प्रवास सवलत)"
        details["beneficiary"] = "All women and female passengers traveling in Maharashtra"
        details["benefits"] = "50% concession on passenger bus ticket fare across all MSRTC State Transport bus services (Ordinary, Semi-luxury, Shivshahi, Shivneri AC) within Maharashtra for all women passengers."
        details["eligibility"] = "All women and female citizens of any age group traveling within Maharashtra (no age limit applies)."
        details["documents"] = "Aadhaar Card or Government Photo ID for verification if requested."
        details["guidelines_summary"] = (
            "MSRTC Mahila Sanman Yojana provides a 50% concession on bus fares to all women passengers traveling on Maharashtra State Road Transport Corporation buses across Maharashtra. "
            "Applicable on all MSRTC services including Ordinary (साधी बस), Semi-Luxury (निमआराम), Shivshahi, and Shivneri AC buses. "
            "Does not apply to municipal city buses (PMC, PCMC, NMMT, BEST). Available for online booking and on-spot bus conductor ticketing."
        )
        return details

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


def _parse_multi_table_csv(content_str: str) -> list[dict[str, Any]]:
    """Parse CSV text containing single or concatenated tables with multi-line quoted fields."""
    import csv
    f = io.StringIO(content_str)
    reader = csv.reader(f)
    current_headers = None
    records = []

    for row in reader:
        if not row:
            continue
        first_col = str(row[0]).strip().lstrip('\ufeff').lower()
        if first_col in ("web_scraper_order", "scheme_name", "name", "title", "scheme", "data"):
            current_headers = [str(c).strip().lstrip('\ufeff').lower().replace(" ", "_") for c in row]
            continue
        if current_headers:
            row_dict = {}
            for idx, val in enumerate(row):
                if idx < len(current_headers):
                    col_name = current_headers[idx]
                    row_dict[col_name] = val
                else:
                    row_dict[f"extra_col_{idx}"] = val
            records.append(row_dict)

    return records


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

    # Pre-processing: Identify comment/FAQ rows and associate them by start_url
    qa_by_url: dict[str, list[tuple[str, str, str]]] = {}
    main_records: list[dict[str, Any]] = []

    for r in records:
        if not isinstance(r, dict):
            continue
        creator = str(r.get("creator") or r.get("creator2") or "").strip().lower()
        d_val = str(r.get("data") or r.get("scheme_name") or r.get("name") or "").strip()
        d2_val = str(r.get("data2") or "").strip()
        d3_val = str(r.get("data3") or "").strip()
        u_val = str(r.get("web_scraper_start_url") or r.get("official_url") or r.get("url") or "").strip()

        is_qa = False
        if creator and ("says" in creator or "comment" in creator):
            # Check for questions first
            if "?" in d_val or "लागू" in d_val or "आहे" in d_val or any(w in d_val.lower() for w in ["kiti", "where", "when", "how", "allowed", "booking"]):
                is_qa = True
            elif any(term in d_val.lower() for term in ["concession", "scheme", "yojana", "dbt", "kisan", "subsid"]):
                is_qa = False
            elif d2_val and not d_val.lower().startswith("msrtc"):
                is_qa = True

        if is_qa and u_val:
            qa_by_url.setdefault(u_val, []).append((d_val, d2_val, d3_val))
        else:
            main_records.append(r)

    imported_schemes = []
    all_chunks = []
    all_chunk_ids = []
    total_chunks = 0
    today = _today_str()
    now_ts = _now_iso()
    store = get_store()

    for idx, raw_row in enumerate(main_records, start=1):
        if not isinstance(raw_row, dict):
            continue

        # Standardize keys to lowercase with underscores and alphanumeric variants
        row = {}
        for k, v in raw_row.items():
            k_clean = str(k).strip().lower()
            row[k_clean] = v
            row[k_clean.replace(" ", "_")] = v
            k_alphanum = re.sub(r"[^a-z0-9]+", "_", k_clean).strip("_")
            row[k_alphanum] = v

        raw_name = str(
            row.get("scheme_name") or row.get("name") or row.get("title") or row.get("scheme") or row.get("data") or ""
        ).strip()
        raw_url = str(
            row.get("official_url") or row.get("official_source_url") or row.get("official_link")
            or row.get("myscheme_url") or row.get("url") or row.get("source_url")
            or row.get("web_scraper_start_url") or row.get("link") or ""
        ).strip()

        # If primary URL is invalid, try fallback to myscheme_url or official_link
        if not _is_valid_url(raw_url):
            fallback_url = str(row.get("myscheme_url") or row.get("official_link") or "").strip()
            if _is_valid_url(fallback_url):
                raw_url = fallback_url

        if not raw_name:
            continue

        if not _is_valid_url(raw_url):
            log.warning("Row %d: Skipping invalid official_url '%s' for scheme '%s'", idx, raw_url, raw_name)
            continue

        # Normalized values and enriched metadata
        scheme_name = normalize_text(raw_name)
        if "msrtc" in scheme_name.lower() and "mahila sanman" not in scheme_name.lower():
            scheme_name = f"{scheme_name} (Mahila Sanman Yojana)"
        elif "mahapocra" in raw_url.lower() and "pocra" not in scheme_name.lower():
            scheme_name = f"MahaPoCRA - {scheme_name}"

        enrichment = enrich_scraped_scheme_metadata(scheme_name, row)
        official_url = enrichment.get("official_url") or raw_url

        raw_data2 = str(row.get("data2") or "").strip()

        hindi_name = normalize_text(
            str(row.get("hindi_name") or row.get("hindi") or row.get("scheme_name_hi") or enrichment.get("hindi_name") or scheme_name)
        )
        category = normalize_text(
            str(row.get("category") or row.get("tags_categories") or row.get("tags__categories") or row.get("sector") or enrichment.get("category") or "Government Schemes & Welfare")
        )
        beneficiary = normalize_text(
            str(row.get("beneficiary") or row.get("target_beneficiary") or enrichment.get("beneficiary") or "Eligible citizens and farmer families")
        )

        raw_elig = str(row.get("eligibility") or row.get("eligibility_criteria") or row.get("eligibility_general") or enrichment.get("eligibility") or "").strip()
        raw_excl = str(row.get("exclusions_ineligibility") or row.get("exclusions__ineligibility") or row.get("exclusions") or "").strip()
        if raw_excl and raw_excl not in raw_elig:
            eligibility = normalize_text(f"{raw_elig}\nExclusions: {raw_excl}" if raw_elig else f"Exclusions: {raw_excl}")
        else:
            eligibility = normalize_text(raw_elig or "Subject to official department verification and guidelines.")

        benefits_val = str(row.get("benefits") or row.get("benefit") or enrichment.get("benefits") or "")
        if not benefits_val and raw_data2 and not raw_data2.lower().startswith("says") and len(raw_data2) > 10:
            benefits_val = raw_data2
        benefits = normalize_text(benefits_val or "Direct benefit transfer and institutional support under scheme rules.")

        documents = normalize_text(
            str(row.get("documents") or row.get("documents_required") or enrichment.get("documents") or "Aadhaar Card, Bank Passbook, and Identity documents.")
        )
        state_district = normalize_text(
            str(row.get("state_district") or row.get("state") or row.get("district")
                or (row.get("state_ut_ministry") or row.get("state__ut__ministry") if str(row.get("level", "")).lower() != "central" else "")
                or enrichment.get("state_district") or "Central / All India")
        )
        status = normalize_text(str(row.get("status") or enrichment.get("status") or "Active"))
        authority = normalize_text(
            str(row.get("authority") or row.get("department") or row.get("ministry")
                or row.get("state_ut_ministry") or row.get("state__ut__ministry")
                or enrichment.get("authority") or "Government Authority")
        )

        raw_desc = str(row.get("guidelines_summary") or row.get("summary") or row.get("description") or enrichment.get("guidelines_summary") or "").strip()
        if not raw_desc and raw_data2 and not raw_data2.lower().startswith("says"):
            raw_desc = raw_data2

        raw_proc = str(row.get("application_process") or "").strip()
        raw_mode = str(row.get("application_mode") or "").strip()
        desc_parts = [raw_desc] if raw_desc else [f"{scheme_name} - {benefits}"]
        if raw_mode:
            desc_parts.append(f"Application Mode: {raw_mode}")
        if raw_proc and raw_proc not in raw_desc:
            desc_parts.append(f"Application Process: {raw_proc}")

        # Attach citizen Q&A / FAQs if available for this URL
        matching_qas = qa_by_url.get(raw_url) or qa_by_url.get(official_url)
        if matching_qas:
            faq_parts = ["\n--- Verified Citizen Q&A & FAQs ---"]
            for q_text, a_text, _ in matching_qas:
                clean_q = normalize_text(q_text)
                clean_a = normalize_text(a_text)
                if clean_a:
                    faq_parts.append(f"• Question: {clean_q}\n  Answer / Clarification: {clean_a}")
                else:
                    faq_parts.append(f"• Citizen Query: {clean_q}")
            desc_parts.append("\n".join(faq_parts))

        guidelines_summary = normalize_text("\n\n".join(desc_parts))

        canonical_id = row.get("scheme_id") or row.get("scheme_slug") or get_canonical_scheme_id(scheme_name, hindi_name, official_url)

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
            # Clean obsolete chunks for this scheme_id if present
            try:
                existing = store.get(where={"scheme_id": canonical_id})
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
        BATCH_SIZE = 100
        for b_start in range(0, len(all_chunks), BATCH_SIZE):
            store.add_documents(
                all_chunks[b_start : b_start + BATCH_SIZE],
                ids=all_chunk_ids[b_start : b_start + BATCH_SIZE],
            )

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
    content_str = content.decode("utf-8", errors="replace").strip()
    if not content_str:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    records = _parse_multi_table_csv(content_str)

    if not records:
        # Fallback to standard pandas read_csv
        try:
            df = pd.read_csv(BytesIO(content))
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            records = df.fillna("").to_dict(orient="records")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {exc}")

    # Required column resolution (support synonyms)
    has_valid_header = any(
        isinstance(r, dict)
        and any(k in r for k in ("scheme_name", "name", "title", "scheme", "data"))
        and any(k in r for k in ("official_url", "official_source_url", "url", "source_url", "official_link", "myscheme_url", "web_scraper_start_url", "link"))
        for r in records
    )

    if not has_valid_header:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain 'scheme_name' and 'official_url' columns (or 'data' and 'web_scraper_start_url')."
        )

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
        and any(k in r for k in ("official_url", "official_source_url", "url", "source_url", "official_link", "myscheme_url", "web_scraper_start_url", "link"))
        for r in records
    )
    if not has_valid_header:
        raise HTTPException(
            status_code=400,
            detail="JSON records must contain 'scheme_name' and 'official_url' fields (or 'data' and 'web_scraper_start_url')."
        )

    return process_scraped_records(records, source_type="json_import")

