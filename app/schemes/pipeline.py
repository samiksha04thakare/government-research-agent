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

        if existing:
            # Update fields and ensure scheme_id is set
            existing.scheme_id = canonical_id
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
            )
            db.add(new_scheme)
            db.commit()
            db.refresh(new_scheme)
            log.info("Created new scheme id=%d [%s]: %s", new_scheme.id, new_scheme.scheme_id, new_scheme.scheme_name)
            return new_scheme
    finally:
        if should_close:
            db.close()


def seed_official_schemes(db=None) -> int:
    """Seed official Central & State government schemes into the database."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    count = 0
    try:
        for item in OFFICIAL_SCHEMES_SEED:
            ingest_scheme_to_db(item, db=db)
            count += 1
        log.info("Successfully seeded %d official government schemes into database", count)
        return count
    finally:
        if should_close:
            db.close()


def search_schemes_in_db(
    query: str = "",
    category: str | None = None,
    state: str | None = None,
    status: str | None = None,
    limit: int = 50,
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

                # Exact phrase matches in name get top priority
                if q_clean in name_lower or q_clean in hindi_lower:
                    score += 100
                elif q_clean in cid_lower:
                    score += 80

                for t in terms:
                    if t in name_lower:
                        score += 25
                    if t in hindi_lower:
                        score += 25
                    if t in cid_lower:
                        score += 20
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
            end_idx = start_idx + limit
            paged_items = processed_schemes[start_idx:end_idx]
            total_pages = max(1, (total_unique + limit - 1) // limit) if total_unique > 0 else 1

        if return_total or page is not None:
            return paged_items, total_unique, total_pages
        return paged_items
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
]


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
            "related", "releated", "about", "details", "info", "information"
        }
        terms = [t for t in q_clean.split() if t not in stop_words and len(t) > 1]
        if not terms:
            return None

        best_score = 0
        best_scheme = None
        for s in all_schemes:
            score = 0
            name_lower = (s.scheme_name or "").lower()
            hindi_lower = (s.hindi_name or "").lower()
            cid_lower = (s.scheme_id or "").lower()
            cat_lower = (s.category or "").lower()
            ben_lower = (s.beneficiary or "").lower()

            for t in terms:
                if t in name_lower:
                    score += 20
                if t in hindi_lower:
                    score += 20
                if t in cid_lower:
                    score += 20
                if (t in cat_lower) or (t in ("farming", "farmer") and ("kisan" in name_lower or "sheti" in name_lower)):
                    score += 15
                if t in ben_lower:
                    score += 10

            if score > best_score:
                best_score = score
                best_scheme = s

        return best_scheme if best_score >= 15 else None
    finally:
        if should_close:
            db.close()

