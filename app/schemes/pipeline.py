"""Text Extraction, Cleaning & Normalization, and Structured Scheme Ingestion Pipeline.

Pipeline Architecture:
Official Government Sources
          ↓
Hindi / English Documents
          ↓
Text Extraction
          ↓
Cleaning & Normalization
          ↓
Structured Scheme Data
          ↓
PostgreSQL / Relational DB
          │
          ├── Scheme name
          ├── Hindi name
          ├── Category
          ├── Beneficiary
          ├── Eligibility
          ├── Benefits
          ├── Documents
          ├── State/District
          └── Status
"""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import or_

from app.database.db import Scheme, SessionLocal
from app.schemes.data import OFFICIAL_SCHEMES_SEED
from app.utils.logging import get_logger

log = get_logger("schemes_pipeline")


# Devanagari numerals to ASCII map
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def normalize_text(text: str) -> str:
    """Clean and normalize raw Hindi / English text extracted from government sources.
    
    1. Unicode NFKC normalization (fixes composite Devanagari ligatures and accents)
    2. Normalize non-standard whitespace, tabs, zero-width joiners, and linebreaks
    3. Standardize rupee signs (Rs., Rs, INR, रू -> ₹)
    4. Normalize Devanagari numbering
    5. Clean OCR artifact lines and stray bullets
    """
    if not text:
        return ""

    # Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # Standardize currency notations
    normalized = re.sub(r"\b(?:Rs\.?|INR|रू\.?)\s*", "₹", normalized, flags=re.IGNORECASE)

    # Convert non-breaking spaces and zero-width characters
    normalized = normalized.replace("\u200b", "").replace("\ufeff", "").replace("\u00a0", " ")

    # Normalize double dashes, fancy quotes
    normalized = normalized.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("—", "-").replace("–", "-")

    # Clean multiple spaces while preserving paragraphs
    lines = []
    for line in normalized.splitlines():
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        if cleaned_line:
            lines.append(cleaned_line)

    return "\n".join(lines)


def extract_text_from_file(file_path: str | Path) -> str:
    """Extract raw text from PDF, HTML, TXT, JSON, or CSV official government documents."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    ext = path.suffix.lower()

    if ext == ".pdf":
        reader = PdfReader(str(path))
        extracted_pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_pages.append(f"--- Page {i + 1} ---\n{page_text}")
        raw = "\n\n".join(extracted_pages)
        return normalize_text(raw)

    elif ext in (".html", ".htm"):
        raw_html = path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return normalize_text(soup.get_text(separator="\n"))

    elif ext in (".txt", ".md", ".csv"):
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        return normalize_text(raw_text)

    elif ext == ".json":
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return normalize_text(json.dumps(data, ensure_ascii=False, indent=2))

    else:
        raise ValueError(f"Unsupported file format for text extraction: {ext}")


def extract_structured_scheme(raw_text: str, default_meta: dict | None = None) -> dict[str, Any]:
    """Parse cleaned & normalized text into structured scheme schema."""
    cleaned = normalize_text(raw_text)
    meta = default_meta or {}

    # Heuristic pattern extractors
    def _find_field(patterns: list[str], fallback: str = "") -> str:
        for pat in patterns:
            m = re.search(pat, cleaned, re.IGNORECASE | re.MULTILINE)
            if m:
                return m.group(1).strip()
        return fallback

    scheme_name = meta.get("scheme_name") or _find_field([
        r"(?:Scheme Name|योजना का नाम|Scheme Title|Name of Scheme)\s*[:\-]\s*([^\n]+)",
        r"^#\s*([^\n]+)",
    ], fallback=meta.get("title", "Government Scheme"))

    hindi_name = meta.get("hindi_name") or _find_field([
        r"(?:Hindi Name|हिन्दी नाम|योजना का नाम)\s*[:\-]\s*([^\n]+)",
        r"\(([\u0900-\u097F\s\-]+(?:योजना|अभियान|निधि|कार्ड|मिशन)[^\)]*)\)",
    ], fallback=scheme_name)

    category = meta.get("category") or _find_field([
        r"(?:Category|श्रेणी|विभाग)\s*[:\-]\s*([^\n]+)",
        r"(?:Sector|क्षेत्र)\s*[:\-]\s*([^\n]+)",
    ], fallback="Government Schemes & Welfare")

    beneficiary = meta.get("beneficiary") or _find_field([
        r"(?:Beneficiary|लाभार्थी|Target Beneficiary|पात्र वर्ग)\s*[:\-]\s*([^\n]+(?:\n[ \t]*[•\-\*][^\n]+)*)",
    ], fallback="Eligible citizens and farmer families")

    eligibility = meta.get("eligibility") or _find_field([
        r"(?:Eligibility(?: Criteria)?|पात्रता|पात्रता शर्तें)\s*[:\-]\s*([^\n]+(?:\n[ \t]*[•\-\*0-9][^\n]+)*)",
    ], fallback="Subject to official department verification and guidelines.")

    benefits = meta.get("benefits") or _find_field([
        r"(?:Benefits|लाभ|Financial Assistance|सहायता राशि|Benefit Structure)\s*[:\-]\s*([^\n]+(?:\n[ \t]*[•\-\*0-9][^\n]+)*)",
    ], fallback="Direct benefit transfer and institutional support under scheme rules.")

    documents = meta.get("documents") or _find_field([
        r"(?:Documents Required|आवश्यक दस्तावेज़|Required Documents|कागदपत्रे)\s*[:\-]\s*([^\n]+(?:\n[ \t]*[•\-\*0-9][^\n]+)*)",
    ], fallback="Aadhaar Card, Bank Passbook, and Identity/Land documents.")

    state_district = meta.get("state_district") or meta.get("state") or _find_field([
        r"(?:State/District|राज्य/जिला|State|Jurisdiction)\s*[:\-]\s*([^\n]+)",
    ], fallback="Central / All India")

    status = meta.get("status") or _find_field([
        r"(?:Status|स्थिति)\s*[:\-]\s*([^\n]+)",
    ], fallback="Active")

    return {
        "scheme_name": scheme_name,
        "hindi_name": hindi_name,
        "category": category,
        "beneficiary": beneficiary,
        "eligibility": eligibility,
        "benefits": benefits,
        "documents": documents,
        "state_district": state_district,
        "status": status,
        "official_source_url": meta.get("source_url") or meta.get("official_source_url", ""),
        "authority": meta.get("authority", ""),
        "guidelines_summary": cleaned[:500] if len(cleaned) > 500 else cleaned,
    }


from app.schemes.normalizer import (
    get_canonical_scheme_id,
    are_schemes_equivalent,
    normalize_scheme_name,
)


def _record_completeness(s: Scheme) -> int:
    """Calculate completeness score for a scheme record to pick best record when deduplicating."""
    score = 0
    if s.official_source_url:
        score += 20
    if s.eligibility and len(s.eligibility) > 15:
        score += len(s.eligibility)
    if s.benefits and len(s.benefits) > 15:
        score += len(s.benefits)
    if s.documents and len(s.documents) > 15:
        score += len(s.documents)
    if s.guidelines_summary:
        score += 10
    return score


def ingest_scheme_to_db(scheme_data: dict[str, Any], db=None) -> Scheme:
    """Upsert a structured scheme into the PostgreSQL / SQLite database with strict deduplication."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        s_name = scheme_data["scheme_name"].strip()
        h_name = scheme_data.get("hindi_name", "").strip()
        source_url = scheme_data.get("official_source_url") or scheme_data.get("source_url", "")
        canonical_id = scheme_data.get("scheme_id") or get_canonical_scheme_id(s_name, h_name, source_url)

        # Look up existing scheme by canonical scheme_id first
        existing = db.query(Scheme).filter(Scheme.scheme_id == canonical_id).first()

        # If not matched by scheme_id, check by exact or normalized name
        if not existing:
            conds = [Scheme.scheme_name.ilike(s_name)]
            if h_name:
                conds.append(Scheme.hindi_name.ilike(h_name))
            existing = db.query(Scheme).filter(or_(*conds)).first()

        # If still not found, check canonical equivalence across all existing records
        if not existing:
            all_schemes = db.query(Scheme).all()
            for cand in all_schemes:
                if are_schemes_equivalent(cand, {"scheme_id": canonical_id, "scheme_name": s_name, "hindi_name": h_name}):
                    existing = cand
                    break

        from app.database.db import get_scheme_dataset_section_info
        sec_name = scheme_data.get("dataset_section")
        sec_grp = scheme_data.get("section_group")
        if not sec_name or not sec_grp:
            d_sec, d_grp = get_scheme_dataset_section_info(canonical_id, s_name, scheme_data.get("category", "General"))
            sec_name = sec_name or d_sec
            sec_grp = sec_grp or d_grp

        if existing:
            # Update fields and ensure scheme_id and sections are set
            existing.scheme_id = canonical_id
            existing.dataset_section = sec_name
            existing.section_group = sec_grp
            for key, val in scheme_data.items():
                if hasattr(existing, key) and val is not None and key not in ("id", "created_at"):
                    setattr(existing, key, val)
            db.commit()
            db.refresh(existing)
            log.info("Updated existing scheme id=%d [%s]: %s", existing.id, existing.scheme_id, existing.scheme_name)
            return existing
        else:
            new_scheme = Scheme(
                scheme_id=canonical_id,
                scheme_name=s_name,
                hindi_name=h_name or s_name,
                category=scheme_data.get("category", "General"),
                beneficiary=scheme_data.get("beneficiary", "Eligible Citizens"),
                eligibility=scheme_data.get("eligibility", "N/A"),
                benefits=scheme_data.get("benefits", "N/A"),
                documents=scheme_data.get("documents", "Aadhaar Card, Bank Passbook"),
                state_district=scheme_data.get("state_district", "Central / All India"),
                status=scheme_data.get("status", "Active"),
                official_source_url=source_url,
                authority=scheme_data.get("authority", ""),
                guidelines_summary=scheme_data.get("guidelines_summary", ""),
                application_process=scheme_data.get("application_process", ""),
                dataset_section=sec_name,
                section_group=sec_grp,
            )
            db.add(new_scheme)
            db.commit()
            db.refresh(new_scheme)
            log.info("Created new scheme id=%d [%s]: %s", new_scheme.id, new_scheme.scheme_id, new_scheme.scheme_name)
            return new_scheme
    finally:
        if should_close:
            db.close()


def get_scheme_by_id_or_code(identifier: str | int, db=None) -> Scheme | None:
    """Fetch exact scheme using canonical scheme_id, integer PK id, or exact title."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        ident_str = str(identifier).strip()
        if not ident_str:
            return None

        # 1. Exact canonical scheme_id
        scheme = db.query(Scheme).filter(Scheme.scheme_id == ident_str).first()
        if scheme:
            return scheme

        # 2. Integer ID
        if ident_str.isdigit():
            scheme = db.get(Scheme, int(ident_str))
            if scheme:
                return scheme

        # 3. Case-insensitive scheme_id
        scheme = db.query(Scheme).filter(Scheme.scheme_id.ilike(ident_str)).first()
        if scheme:
            return scheme

        # 4. Exact scheme_name or hindi_name
        scheme = db.query(Scheme).filter(
            or_(
                Scheme.scheme_name.ilike(ident_str),
                Scheme.hindi_name.ilike(ident_str),
            )
        ).first()
        if scheme:
            return scheme

        # 5. Canonical equivalence
        for s in db.query(Scheme).all():
            if are_schemes_equivalent(s, {"scheme_id": ident_str, "scheme_name": ident_str, "hindi_name": ident_str}):
                return s

        return None
    finally:
        if should_close:
            db.close()


def index_scheme_to_vectorstore(scheme: Scheme, force: bool = False) -> int:
    """Index an authoritative structured scheme document chunk into ChromaDB with metadata['scheme_id']."""
    import hashlib
    from langchain_core.documents import Document as LcDocument
    from app.rag.retriever import get_store
    from app.rag.chunker import chunk_documents

    canonical_id = scheme.scheme_id or get_canonical_scheme_id(
        scheme.scheme_name, scheme.hindi_name, scheme.official_source_url
    )
    store = get_store()

    # Check if chunks with this scheme_id already exist
    if not force:
        try:
            existing = store.get(where={"scheme_id": canonical_id})
            if existing and existing.get("ids"):
                return 0
        except Exception:
            pass

    content = (
        f"Scheme Name: {scheme.scheme_name}\n"
        f"Hindi Name: {scheme.hindi_name}\n"
        f"Scheme Identifier: {canonical_id}\n"
        f"Category: {scheme.category}\n"
        f"Beneficiary: {scheme.beneficiary}\n"
        f"Eligibility Criteria: {scheme.eligibility}\n"
        f"Benefits & Financial Assistance: {scheme.benefits}\n"
        f"Required Documents: {scheme.documents}\n"
        f"Application Procedure: {scheme.application_process or 'Official application guidelines are provided on the official portal.'}\n"
        f"Jurisdiction / State: {scheme.state_district}\n"
        f"Status: {scheme.status}\n"
        f"Authority / Department: {scheme.authority}\n"
        f"Official Portal URL: {scheme.official_source_url}\n"
        f"Guidelines Summary: {scheme.guidelines_summary}"
    )
    content_hash = getattr(scheme, "content_hash", None) or hashlib.sha256(content.encode("utf-8")).hexdigest()

    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last_chk = (
        scheme.last_checked.strftime("%Y-%m-%d")
        if getattr(scheme, "last_checked", None)
        else now_date
    )
    last_ver = (
        scheme.last_verified.strftime("%Y-%m-%d")
        if getattr(scheme, "last_verified", None)
        else (scheme.updated_at.strftime("%Y-%m-%d") if scheme.updated_at else now_date)
    )

    metadata = {
        "scheme_id": canonical_id,
        "title": scheme.scheme_name,
        "source_name": scheme.authority or scheme.department or scheme.scheme_name,
        "source_url": scheme.official_source_url or scheme.application_url or "https://india.gov.in",
        "category": "government_schemes",
        "department": scheme.department or scheme.authority or "Government Authority",
        "authority": scheme.authority or scheme.department or "Government Authority",
        "document_type": "official_scheme_record",
        "status": scheme.status,
        "is_discontinued": bool(getattr(scheme, "is_discontinued", False)),
        "state": scheme.state_district,
        "content_hash": content_hash,
        "last_checked": last_chk,
        "last_updated": last_ver,
    }

    doc = LcDocument(page_content=content, metadata=metadata)
    chunks = chunk_documents([doc], size=750, overlap=100)

    # Deterministic chunk IDs
    new_chunk_ids = [f"scheme_{canonical_id}_{i}" for i in range(len(chunks))]

    # Get existing chunk IDs for this scheme_id
    existing_ids = set()
    try:
        existing = store.get(where={"scheme_id": canonical_id})
        if existing and existing.get("ids"):
            existing_ids = set(existing["ids"])
    except Exception:
        pass

    # Safe atomic replacement: add new chunks FIRST
    try:
        store.add_documents(chunks, ids=new_chunk_ids)
    except Exception as emb_err:
        log.error("Failed to add scheme chunks to ChromaDB for %s: %s", canonical_id, emb_err)
        raise

    # Only after successful addition, delete obsolete chunks that are no longer part of the scheme
    obsolete_ids = list(existing_ids - set(new_chunk_ids))
    if obsolete_ids:
        try:
            store.delete(ids=obsolete_ids)
        except Exception as del_err:
            log.warning("Could not delete obsolete chunks for scheme %s: %s", canonical_id, del_err)

    return len(chunks)


def _index_wcd_compendium_sections(wcd_file: Path, store, force: bool = False):
    """Index sections of Maharashtra Women & Child Compendium with explicit scheme_ids (MH-WOM-01 to 11)."""
    import hashlib
    from langchain_core.documents import Document as LcDocument
    from app.rag.chunker import chunk_documents

    raw_text = wcd_file.read_text(encoding="utf-8", errors="replace")
    sections = re.split(r"(?=## Section \d+:)", raw_text)

    for sec in sections:
        sec = sec.strip()
        if not sec.startswith("## Section"):
            continue
        code_match = re.search(r"\(Code:\s*(MH-WOM-\d{2})\)", sec, re.IGNORECASE)
        if not code_match:
            continue
        scheme_id = code_match.group(1).upper()

        if not force:
            try:
                existing = store.get(where={"scheme_id": scheme_id})
                if existing and len(existing.get("ids", [])) > 2:
                    continue
            except Exception:
                pass

        title_m = re.search(r"## Section \d+:\s*([^\n\(]+)", sec)
        title = title_m.group(1).strip() if title_m else f"Women Scheme {scheme_id}"
        portal_m = re.search(r"Portal:\s*([^\n]+)", sec)
        portal = portal_m.group(1).strip() if portal_m else "https://womenchild.maharashtra.gov.in"

        sec_hash = hashlib.sha256(sec.encode("utf-8")).hexdigest()
        meta = {
            "scheme_id": scheme_id,
            "title": title,
            "source_name": "Department of Women and Child Development, Maharashtra",
            "source_url": portal,
            "category": "government_schemes",
            "department": "Department of Women and Child Development, Government of Maharashtra",
            "authority": "Department of Women and Child Development, Government of Maharashtra",
            "document_type": "official_guideline_section",
            "content_hash": sec_hash,
            "last_checked": "2026-10-21",
            "last_updated": "2026-10-21",
        }
        doc = LcDocument(page_content=sec, metadata=meta)
        chunks = chunk_documents([doc], size=700, overlap=100)
        chunk_ids = [f"wcd_sec_{scheme_id}_{i}" for i in range(len(chunks))]
        store.add_documents(chunks, ids=chunk_ids)


def sync_all_schemes_to_vectorstore(db=None, force: bool = False) -> dict[str, int]:
    """Ensure every scheme in SQL has its chunks indexed into ChromaDB with metadata['scheme_id']."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        from app.rag.retriever import get_store
        store = get_store()

        if not force:
            try:
                # Fast check: If canonical scheme MH-WOM-01 is already indexed, skip slow full-table metadata load
                test_hit = store.get(where={"scheme_id": "MH-WOM-01"}, limit=1)
                if test_hit and test_hit.get("ids"):
                    log.info("ChromaDB already populated with scheme_id metadata; skipping redundant full sync")
                    return {"schemes_indexed": 0, "chunks_added": 0}
            except Exception:
                pass

        all_schemes = db.query(Scheme).all()

        existing_sids = set()
        try:
            sample = store.get(include=["metadatas"])
            for m in sample.get("metadatas", []):
                sid = m.get("scheme_id")
                if sid:
                    existing_sids.add(sid)
        except Exception as e:
            log.warning("Could not pre-fetch existing scheme_ids: %s", e)

        indexed_count = 0
        chunks_count = 0
        for s in all_schemes:
            cid = s.scheme_id or get_canonical_scheme_id(s.scheme_name, s.hindi_name, s.official_source_url)
            if force or cid not in existing_sids:
                ch = index_scheme_to_vectorstore(s, force=force)
                if ch > 0:
                    indexed_count += 1
                    chunks_count += ch
                    existing_sids.add(cid)

        # Index section-specific text for Maharashtra Women & Child Compendium
        wcd_file = Path("data/raw/maharashtra_women_child_schemes.txt")
        if wcd_file.exists():
            _index_wcd_compendium_sections(wcd_file, store, force=force)

        log.info("Synced schemes to ChromaDB: %d schemes indexed (%d chunks)", indexed_count, chunks_count)
        return {"schemes_indexed": indexed_count, "chunks_added": chunks_count}
    finally:
        if should_close:
            db.close()


def seed_official_schemes(db=None, force_update: bool = False) -> int:
    """Seed official Central & State government schemes into the database and vectorstore."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    count = 0
    try:
        for item in OFFICIAL_SCHEMES_SEED:
            saved = ingest_scheme_to_db(item, db=db)
            index_scheme_to_vectorstore(saved, force=force_update)
            count += 1
        log.info("Successfully seeded %d official government schemes into database and vectorstore", count)
        return count
    finally:
        if should_close:
            db.close()


def search_schemes_in_db(
    query: str = "",
    category: str | None = None,
    state: str | None = None,
    status: str | None = None,
    section_group: str | None = None,
    section: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    page: int | None = None,
    page_size: int | None = None,
    return_total: bool = False,
    db=None,
) -> tuple[list[Scheme], int, int] | list[Scheme]:
    """Search, filter, deduplicate, and deterministically paginate structured schemes.
    
    Guarantees:
    1. Deduplication BEFORE pagination (each unique scheme appears exactly once).
    2. Uses stable canonical scheme_id / name equivalence.
    3. Deterministic sorting with unique tie-breaker (score, scheme_name, id).
    4. Calculates accurate unique scheme counts, total pages, and non-overlapping pages.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Base SQL query with deterministic order by ID
        q = db.query(Scheme).order_by(Scheme.id.asc())
        if section_group and section_group != "all":
            from app.database.db import SECTION_GROUP_MAP
            target_group = SECTION_GROUP_MAP.get(section_group.lower(), section_group)
            conds = [
                Scheme.section_group.ilike(f"%{section_group}%"),
                Scheme.section_group.ilike(f"%{target_group}%"),
            ]
            terms = [t for t in target_group.replace("(", " ").replace(")", " ").split() if len(t) > 3 and t.lower() not in ("with", "from", "plan", "development", "sections")]
            for t in terms:
                conds.append(Scheme.section_group.ilike(f"%{t}%"))
            q = q.filter(or_(*conds))
        if section and section != "all":
            q = q.filter(Scheme.dataset_section.ilike(f"%{section}%"))

        if category and category != "all":
            cat_l = category.strip().lower()
            if cat_l in ("women", "women & child", "women and child"):
                q = q.filter(
                    or_(
                        Scheme.category.ilike("%Women%"),
                        Scheme.category.ilike("%Child%"),
                        Scheme.category.ilike("%Maternity%"),
                        Scheme.category.ilike("%Girl%"),
                        Scheme.category.ilike("%Nari%"),
                        Scheme.category.ilike("%Mahila%"),
                        Scheme.category.ilike("%Shelter%"),
                        Scheme.category.ilike("%Anganwadi%"),
                        Scheme.category.ilike("%Poshan%"),
                        Scheme.category.ilike("%Trafficking%"),
                        Scheme.category.ilike("%Empowerment%"),
                        Scheme.category.ilike("%Livelihood%"),
                    )
                )
            elif cat_l in ("agriculture", "agri", "farmer", "farmers"):
                q = q.filter(
                    or_(
                        Scheme.category.ilike("%Agriculture%"),
                        Scheme.category.ilike("%Farmer%"),
                        Scheme.category.ilike("%Credit%"),
                        Scheme.category.ilike("%Crop%"),
                        Scheme.category.ilike("%Soil%"),
                        Scheme.category.ilike("%Mechanization%"),
                        Scheme.category.ilike("%Irrigation%"),
                    )
                )
            else:
                q = q.filter(Scheme.category.ilike(f"%{category}%"))
        if state and state != "all":
            q = q.filter(Scheme.state_district.ilike(f"%{state}%"))
        if status and status != "all":
            q = q.filter(Scheme.status.ilike(f"%{status}%"))

        raw_candidates = q.all()

        # Step 1: Pre-pagination deduplication by canonical scheme identifier
        unique_map: dict[str, Scheme] = {}
        for s in raw_candidates:
            canon_id = s.scheme_id or get_canonical_scheme_id(
                s.scheme_name, s.hindi_name, s.official_source_url
            )
            if canon_id not in unique_map:
                unique_map[canon_id] = s
            else:
                # Merge / retain the record with higher content completeness or lower primary key
                existing_s = unique_map[canon_id]
                if _record_completeness(s) > _record_completeness(existing_s):
                    unique_map[canon_id] = s

        unique_schemes = list(unique_map.values())

        # Step 2: Scoring and deterministic ranking
        q_clean = (query or "").strip().lower()
        if q_clean:
            terms = [t for t in q_clean.split() if len(t) > 1]
            scored: list[tuple[int, Scheme]] = []

            for s in unique_schemes:
                score = 0
                name_lower = (s.scheme_name or "").lower()
                hindi_lower = (s.hindi_name or "").lower()
                cat_lower = (s.category or "").lower()
                elig_lower = (s.eligibility or "").lower()
                ben_lower = (s.benefits or "").lower()
                cid_lower = (s.scheme_id or "").lower()
                dept_lower = (getattr(s, "department", None) or s.authority or "").lower()

                # Exact phrase matches in name get top priority
                if q_clean in name_lower or q_clean in hindi_lower:
                    score += 100
                elif q_clean in cid_lower:
                    score += 80
                elif q_clean in dept_lower:
                    score += 60

                for t in terms:
                    if t in name_lower:
                        score += 25
                    if t in hindi_lower:
                        score += 25
                    if t in cid_lower:
                        score += 20
                    if t in dept_lower:
                        score += 15
                    if t in cat_lower:
                        score += 10
                    if t in elig_lower:
                        score += 5
                    if t in ben_lower:
                        score += 5

                if score > 0:
                    scored.append((score, s))

            # Deterministic sort with unique tie-breaker: (-score, name_lower, id)
            scored.sort(key=lambda x: (-x[0], (x[1].scheme_name or "").lower(), x[1].id))
            processed_schemes = [item[1] for item in scored]
        else:
            # Deterministic sort with unique tie-breaker when no search query
            processed_schemes = sorted(
                unique_schemes,
                key=lambda s: ((s.scheme_name or "").lower(), s.id)
            )

        # Step 3: Deduplicated pagination calculation
        total_unique = len(processed_schemes)

        if page is not None:
            p_size = max(1, page_size or limit or 10)
            p_num = max(1, page)
            start_idx = (p_num - 1) * p_size
            end_idx = start_idx + p_size
            paged_items = processed_schemes[start_idx:end_idx]
            total_pages = max(1, (total_unique + p_size - 1) // p_size) if total_unique > 0 else 1
        else:
            start_idx = max(0, offset)
            end_idx = (start_idx + limit) if limit is not None else None
            paged_items = processed_schemes[start_idx:end_idx]
            total_pages = max(1, (total_unique + limit - 1) // limit) if (limit and total_unique > 0) else 1

        if return_total or page is not None:
            return paged_items, total_unique, total_pages
        return paged_items
    finally:
        if should_close:
            db.close()


def get_dataset_sections_summary(db=None) -> list[dict]:
    """Return organized section groups and individual dataset sections according to official datasets."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        from app.database.db import get_scheme_dataset_section_info

        schemes = db.query(Scheme).order_by(Scheme.id.asc()).all()
        groups_meta = [
            {
                "id": "women_child",
                "name": "Women & Child Development (Sections 1-11)",
                "label_hi": "महिला व बाल विकास कंपेंडियम (सेक्शन १-११)",
                "label_mr": "महिला व बाल विकास कंपेंडियम (कलम १-११)",
                "authority": "Department of Women & Child Development, Maharashtra & Ministry of WCD, GoI",
                "source_file": "maharashtra_women_child_schemes.txt",
                "icon": "👩",
            },
            {
                "id": "central_farmer",
                "name": "Central Agriculture & Farmer Welfare",
                "label_hi": "केंद्रीय कृषि एवं किसान कल्याण फ्लैगशिप योजनाएँ",
                "label_mr": "केंद्रीय कृषी व शेतकरी कल्याण प्रमुख योजना",
                "authority": "Ministry of Agriculture & Farmers Welfare, Government of India",
                "source_file": "farmer_welfare_and_credit.txt / pmkisan.gov.in",
                "icon": "🌾",
            },
            {
                "id": "maharashtra_agri",
                "name": "Maharashtra Agriculture Budget (2026-2027)",
                "label_hi": "महाराष्ट्र कृषि बजेट व सक्रिय योजनाएं (BDS २०२६-२७)",
                "label_mr": "महाराष्ट्र कृषी अर्थसंकल्प व थेट योजना (BDS २०२६-२७)",
                "authority": "Department of Agriculture, Government of Maharashtra",
                "source_file": "maharashtra_agriculture_schemes_2026_2027.json",
                "icon": "🚜",
            },
            {
                "id": "education_scholarship",
                "name": "Education & Scholarships",
                "label_hi": "शिक्षा एवं उच्च शिक्षा छात्रवृत्ति योजनाएँ",
                "label_mr": "शिक्षण व शिष्यवृत्ती योजना (MahaDBT)",
                "authority": "Department of Higher & Technical Education / Social Justice, Maharashtra",
                "source_file": "maharashtra_scholarships.txt",
                "icon": "🎓",
            },
            {
                "id": "credit_enterprise",
                "name": "Credit & Entrepreneurship",
                "label_hi": "उद्यमिता, मुद्रा लोन एवं सूक्ष्म वित्त योजनाएँ",
                "label_mr": "उद्योजकता व मुद्रा कर्ज योजना (PMMY)",
                "authority": "Ministry of Micro, Small and Medium Enterprises & DFS",
                "source_file": "entrepreneurship_mudra_loan_guidelines.txt",
                "icon": "💼",
            },
            {
                "id": "healthcare_housing",
                "name": "Healthcare & Social Protection",
                "label_hi": "स्वास्थ्य सुरक्षा एवं ग्रामीण आवास योजनाएँ",
                "label_mr": "आरोग्य व ग्रामीण गृहनिर्माण योजना",
                "authority": "National Health Authority & Ministry of Rural Development",
                "source_file": "pmjay.gov.in / pmayg.nic.in",
                "icon": "🏥",
            },
        ]

        result = []
        for g in groups_meta:
            g_name = g["name"]
            matched_schemes = []
            for s in schemes:
                s_sec, s_grp = get_scheme_dataset_section_info(s.scheme_id, s.scheme_name, s.category)
                eff_grp = s.section_group or s_grp
                if g_name.lower() in eff_grp.lower() or eff_grp.lower() in g_name.lower():
                    matched_schemes.append(s)

            unique_matched: dict[str, Scheme] = {}
            for ms in matched_schemes:
                cid = ms.scheme_id or ms.scheme_name
                if cid not in unique_matched or _record_completeness(ms) > _record_completeness(unique_matched[cid]):
                    unique_matched[cid] = ms

            final_schemes = list(unique_matched.values())
            distinct_sections = []
            seen_secs = set()
            for fs in final_schemes:
                sec_val = fs.dataset_section or get_scheme_dataset_section_info(fs.scheme_id, fs.scheme_name, fs.category)[0]
                if sec_val and sec_val not in seen_secs:
                    seen_secs.add(sec_val)
                    distinct_sections.append({
                        "section_name": sec_val,
                        "scheme_id": fs.scheme_id,
                        "scheme_name": fs.scheme_name,
                        "hindi_name": fs.hindi_name,
                    })

            result.append({
                "group_id": g["id"],
                "group_name": g["name"],
                "label_hi": g["label_hi"],
                "label_mr": g["label_mr"],
                "authority": g["authority"],
                "source_file": g["source_file"],
                "icon": g["icon"],
                "count": len(final_schemes),
                "sections": distinct_sections,
                "distinct_sections": distinct_sections,
                "schemes": [
                    {
                        "id": fs.id,
                        "scheme_id": fs.scheme_id,
                        "scheme_name": fs.scheme_name,
                        "hindi_name": fs.hindi_name,
                        "category": fs.category,
                        "dataset_section": fs.dataset_section or get_scheme_dataset_section_info(fs.scheme_id, fs.scheme_name, fs.category)[0],
                        "benefits": fs.benefits,
                        "state_district": fs.state_district,
                        "status": fs.status,
                    }
                    for fs in final_schemes[:20]
                ],
            })

        return result
    finally:
        if should_close:
            db.close()



SCHEME_IDENTIFIER_MAP = [
    # Women and Child Development (MH-WOM-01 to MH-WOM-11)
    ("MH-WOM-02", ["lek ladki", "लेक लाडकी", "lek-ladki"]),
    ("MH-WOM-01", ["ladki bahin", "ladakibahin", "लाडकी बहीण", "लाडकी बहिण", "लाड़की बहिन", "माझी लाडकी", "majhi ladki"]),
    ("MH-WOM-03", ["pmmvy", "matru vandana", "मातृ वंदना", "मातृवंदना", "matru-vandana"]),
    ("MH-WOM-04", ["one stop centre", "one stop center", "वन स्टॉप", "sakhi centre", "sakhi center", "सखी केंद्र", "sakhi"]),
    ("MH-WOM-05", ["women helpline", "महिला हेल्पलाइन", "महिला हेल्पलाईन", "181"]),
    ("MH-WOM-06", ["nari adalat", "नारी अदालत"]),
    ("MH-WOM-07", ["ujjawala", "उज्ज्वला"]),
    ("MH-WOM-08", ["shakti sadan", "शक्ति सदन"]),
    ("MH-WOM-09", ["hub for empowerment", "महिला सक्षमीकरण", "hew"]),
    ("MH-WOM-10", ["mavim", "माविम", "mahila arthik vikas", "bachat gat", "बचत गट", "बचतगट"]),
    ("MH-WOM-11", ["saksham anganwadi", "poshan 2.0", "poshan", "पोषण", "अंगणवाडी", "अंगनवाड़ी"]),
    # Central and Maharashtra Schemes
    ("PM-KISAN", ["pm kisan", "pm-kisan", "pmkisan", "पीएम किसान", "पीएम-किसान", "किसान सम्मान निधि"]),
    ("KCC", ["kisan credit card", "kcc", "केसीसी", "किसान क्रेडिट"]),
    ("PMFBY", ["pmfby", "fasal bima", "पीएमएफबीवाई", "फसल बीमा", "पीक विमा"]),
    ("PM-KUSUM", ["pm-kusum", "kusum", "कुसुम", "solar pump", "सोलर पंप", "सौर पंप"]),
    ("Namo Shetakari", ["namo shetakari", "namo shetkari", "नमो शेतकरी"]),
    ("Shaashwat", ["shaashwat", "shet tale", "शाश्वत", "शेततळे", "कृषि सिंचाई"]),
    ("Scholarship", ["post-matric", "scholarship", "महाडीबीटी", "छात्रवृत्ति", "शिष्यवृत्ती"]),
    ("SMAM", ["smam", "mechanization", "यांत्रिकीकरण", "agrimachinery"]),
    ("Soil Health", ["soil health", "मृदा स्वास्थ्य", "मृदा कार्ड", "माती परीक्षण"]),
    ("PM-JAY", ["ayushman", "pm-jay", "pmjay", "आयुष्मान"]),
    ("PMAY-G", ["pmay", "awas yojana", "ग्रामीण आवास", "आवास योजना"]),
    ("MUDRA", ["mudra", "मुद्रा", "pmmy", "udyamimitra", "udyami mitra", "shishu", "kishore", "tarun"]),
    ("MSRTC", ["msrtc", "st bus", "st-bus", "एसटी बस", "एसटी", "half ticket", "half-ticket", "हाफ तिकीट", "महिला सन्मान", "mahila sanman", "तिकीट सवलत"]),
    ("MAHAPOCRA", ["mahapocra", "pocra", "पोकरा", "कृषी संजीवनी", "कृषि संजीवनी", "dbt.mahapocra"]),
]


def find_explicit_scheme_in_query(query: str, db=None) -> Scheme | None:
    """Find a scheme that is explicitly named or triggered in the user's query.
    Unlike fuzzy keyword scoring, this strictly requires a scheme keyword trigger, canonical ID,
    or distinctive scheme name keyword, preventing generic questions (e.g. 'What are the eligibility
    criteria and required documents?') from falsely matching an unrelated scheme.
    """
    if not query:
        return None
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        q_lower = query.lower()
        # 1. Check deterministic keyword triggers from SCHEME_IDENTIFIER_MAP
        for identifier, triggers in SCHEME_IDENTIFIER_MAP:
            for trigger in triggers:
                trig_l = trigger.lower()
                matched = False
                if trig_l.isascii():
                    pattern = rf"(?<!\w){re.escape(trig_l)}(?!\w)"
                    matched = bool(re.search(pattern, q_lower))
                else:
                    matched = trig_l in q_lower
                if matched:
                    s = (
                        db.query(Scheme)
                        .filter(
                            or_(
                                Scheme.scheme_id == identifier,
                                Scheme.scheme_id.ilike(f"%{identifier}%"),
                                Scheme.scheme_name.ilike(f"%{identifier}%"),
                                Scheme.hindi_name.ilike(f"%{identifier}%"),
                            )
                        )
                        .first()
                    )
                    if s:
                        return s

        # 2. Check canonical scheme_id exact occurrences in query
        all_schemes = db.query(Scheme).all()
        for s in all_schemes:
            if s.scheme_id and len(s.scheme_id) >= 3:
                pattern = rf"(?<!\w){re.escape(s.scheme_id.lower())}(?!\w)"
                if re.search(pattern, q_lower):
                    return s

        # 3. Check for distinctive scheme name (excluding generic words like scheme, yojana, govt, etc.)
        for s in all_schemes:
            name_lower = (s.scheme_name or "").lower()
            clean_name = re.sub(
                r"\b(pradhan|mantri|yojana|scheme|maharashtra|government|shasan|state|central|department|mission|abhiyan)\b",
                "",
                name_lower,
            ).strip()
            if len(clean_name) >= 6 and clean_name in q_lower:
                return s
            if s.hindi_name:
                h_clean = re.sub(r"(प्रधानमंत्री|योजना|शासन|महाराष्ट्र|मिशन|अभियान)", "", s.hindi_name).strip()
                if len(h_clean) >= 5 and h_clean in query:
                    return s

        return None
    finally:
        if should_close:
            db.close()


def find_matching_scheme_for_query(query: str, db=None) -> Scheme | None:
    """Find a specific scheme matching the user's research query (English or Hindi), using deduplicated records."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        q_lower = query.lower()
        # Deduplicate schemes by canonical identifier to ensure single best record match
        unique_map: dict[str, Scheme] = {}
        for s in db.query(Scheme).order_by(Scheme.id.asc()).all():
            cid = s.scheme_id or get_canonical_scheme_id(s.scheme_name, s.hindi_name, s.official_source_url)
            if cid not in unique_map or _record_completeness(s) > _record_completeness(unique_map[cid]):
                unique_map[cid] = s

        all_schemes = list(unique_map.values())
        if not all_schemes:
            return None

        # 1. Match against deterministic keyword triggers
        for identifier, triggers in SCHEME_IDENTIFIER_MAP:
            for trigger in triggers:
                if trigger in q_lower:
                    # Find scheme matching identifier or canonical scheme_id
                    for s in all_schemes:
                        if (s.scheme_id and identifier.lower() == s.scheme_id.lower()) or identifier.lower() in s.scheme_name.lower():
                            return s

        # 2. Score against all schemes by title & hindi name
        q_clean = q_lower.strip()
        stop_words = {
            "what", "is", "the", "are", "of", "and", "for", "to", "in", "a", "an",
            "scheme", "schemes", "schema", "yojana", "योजना", "योजनेची", "बारे", "में", "क्या", "की", "का",
            "hi", "hiii", "hiiii", "hello", "hey", "give", "me", "some", "tell", "show", "list",
            "related", "releated", "about", "details", "info", "information", "policy",
            "it", "its", "do", "does", "did", "can", "could", "will", "would", "should", "provide", "provides", "get", "apply"
        }
        terms = [t.strip(".,;:?!'\"()[]{}") for t in q_clean.split()]
        terms = [t for t in terms if t not in stop_words and len(t) > 1]
        if not terms:
            return None

        def _matches(term: str, target: str | None) -> bool:
            if not target or not term:
                return False
            if term.isascii():
                pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
                return bool(re.search(pattern, target, re.IGNORECASE))
            return term in target

        best_score = 0
        best_scheme = None
        for s in all_schemes:
            score = 0
            name_lower = (s.scheme_name or "").lower()
            hindi_lower = (s.hindi_name or "").lower()
            cid_lower = (s.scheme_id or "").lower()
            cat_lower = (s.category or "").lower()
            ben_lower = (s.beneficiary or "").lower()
            state_lower = (s.state_district or "").lower()
            auth_lower = (s.authority or "").lower()

            # Exact title in query bonus
            if len(name_lower) > 5 and name_lower in q_lower:
                score += 100

            for t in terms:
                if _matches(t, name_lower):
                    score += 20
                if _matches(t, hindi_lower):
                    score += 20
                if _matches(t, cid_lower):
                    score += 20
                if _matches(t, cat_lower) or (t in ("farming", "farmer") and ("kisan" in name_lower or "sheti" in name_lower)):
                    score += 15
                if _matches(t, ben_lower):
                    score += 10
                if _matches(t, state_lower):
                    score += 35
                if _matches(t, auth_lower):
                    score += 25

            if score > best_score:
                best_score = score
                best_scheme = s

        return best_scheme if best_score >= 15 else None
    finally:
        if should_close:
            db.close()

