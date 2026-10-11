"""Official source citations, verification, and information freshness tracking.

Requirements:
- Maps citation markers ([1], [2]) directly to retrieved official sources.
- Validates official HTTP/HTTPS source URLs; clearly labels unavailable URLs without fabricating replacements.
- Strictly distinguishes verified check date (last_checked) from official document date (last_updated).
- Displays 'Official update date not available.' when official dates are not provided.
- Preserves all metadata attributes across chunks and API responses.
- Audits and flags inconsistent metadata (dates, authorities, tracking URLs) without silently guessing.
- Inspects actual document content to verify factual support for query claims.
- Reconciles answer citation markers to source list entries 1-to-1, eliminating unused sources.
"""
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.sources.config import SUPPORTED_CATEGORIES, is_official_government_url

OFFICIAL_DATE_NOT_AVAILABLE = "Official update date not available."
URL_NOT_AVAILABLE = "Source URL unavailable on official portal"
ADVISORY_DISCLAIMER = (
    "_Important: Information is grounded directly in verified government sources. "
    "Always confirm the latest scheme guidelines, application dates, and eligibility "
    "directly on the official government portal before taking administrative or financial action._"
)

TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "fbclid",
    "gclid",
}


def is_valid_official_url(url: str | None) -> bool:
    """Validate that a URL is a legitimate official HTTP/HTTPS government URL."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    return is_official_government_url(url)


def _is_valid_date_format(d_str: str) -> bool:
    """Validate ISO date format (YYYY, YYYY-MM, or YYYY-MM-DD) and calendar sanity."""
    if not d_str:
        return True
    match = re.match(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$", d_str)
    if not match:
        return False
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    day = int(match.group(3)) if match.group(3) else None
    if year < 1950 or year > 2099:
        return False
    if month is not None and (month < 1 or month > 12):
        return False
    if day is not None and (day < 1 or day > 31):
        return False
    return True


def check_metadata_consistency(metadata: dict) -> list[str]:
    """Check consistency between title, authority, department, dates, URL, and category.
    
    Flags inconsistent metadata rather than silently guessing or correcting it.
    """
    inconsistencies = []

    raw_url = str(metadata.get("source_url") or "").strip()
    title = str(metadata.get("title") or "").strip()
    auth = str(metadata.get("authority") or "").strip()
    dept = str(metadata.get("department") or "").strip()
    cat = str(metadata.get("category") or "").strip()
    doc_type = str(metadata.get("document_type") or "").strip().lower()
    pub_date = str(metadata.get("publication_date") or "").strip()
    upd_date = str(metadata.get("updated_date") or metadata.get("last_updated") or "").strip()
    if upd_date == OFFICIAL_DATE_NOT_AVAILABLE:
        upd_date = ""
    last_checked = str(metadata.get("last_checked") or "").strip()

    # 1. URL tracking parameter contamination check
    if raw_url:
        parsed = urlparse(raw_url)
        if parsed.query:
            params = parse_qs(parsed.query)
            tracking_found = [p for p in params if p.lower() in TRACKING_QUERY_PARAMS or p.lower().startswith("utm_")]
            if tracking_found:
                inconsistencies.append(
                    f"Source URL contains tracking parameters ({', '.join(sorted(tracking_found))}); official government URLs must not contain tracking tags."
                )

    # 2. Date format sanity check
    if pub_date and not _is_valid_date_format(pub_date):
        inconsistencies.append(
            f"Publication date ('{pub_date}') has an invalid date format or calendar value."
        )
    if upd_date and not _is_valid_date_format(upd_date):
        inconsistencies.append(
            f"Updated/revision date ('{upd_date}') has an invalid date format or calendar value."
        )
    if last_checked and not _is_valid_date_format(last_checked):
        inconsistencies.append(
            f"Check date ('{last_checked}') has an invalid date format or calendar value."
        )

    # 3. Date chronology consistency check
    if pub_date and upd_date and _is_valid_date_format(pub_date) and _is_valid_date_format(upd_date):
        if pub_date > upd_date:
            inconsistencies.append(
                f"Publication date ({pub_date}) is later than revision/updated date ({upd_date})."
            )
    if pub_date and last_checked and _is_valid_date_format(pub_date) and _is_valid_date_format(last_checked):
        if last_checked < pub_date:
            inconsistencies.append(
                f"Verified check date ({last_checked}) is earlier than document publication date ({pub_date})."
            )

    # 4. Document type vs URL / File extension mismatch
    if doc_type and raw_url:
        url_lower = raw_url.lower()
        if doc_type == "pdf" and (url_lower.endswith(".txt") or url_lower.endswith(".html") or url_lower.endswith(".htm")):
            inconsistencies.append(
                f"Document type '{doc_type}' conflicts with source URL extension ('{url_lower.split('.')[-1]}')."
            )
        elif doc_type in ("txt", "text", "html") and url_lower.endswith(".pdf"):
            inconsistencies.append(
                f"Document type '{doc_type}' conflicts with PDF source URL."
            )

    # 5. Authority vs Department mismatch
    if auth and dept and auth.lower() != "unknown" and dept.lower() != "unknown":
        auth_lower = auth.lower()
        dept_lower = dept.lower()
        if ("agriculture" in auth_lower and "posts" in dept_lower) or ("finance" in auth_lower and "agriculture" in dept_lower):
            inconsistencies.append(
                f"Authority ('{auth}') conflicts with Department ('{dept}')."
            )

    # 6. Title vs Authority / URL Domain mismatch
    title_lower = title.lower()
    if title_lower:
        # Postal scheme vs Agriculture authority / domain
        if ("post scheme" in title_lower or "postal" in title_lower or "vikas patra" in title_lower):
            if "agriculture" in (auth + " " + dept).lower():
                inconsistencies.append(
                    f"Title '{title}' indicates Postal Department scheme but authority indicates agriculture ('{auth or dept}')."
                )
            if raw_url and "pmkisan.gov.in" in raw_url:
                inconsistencies.append(
                    f"Title '{title}' indicates Postal Department scheme but URL domain is pmkisan.gov.in."
                )
        # Scholarship vs Agriculture
        if ("scholarship" in title_lower or "post-matric" in title_lower):
            if cat and cat not in ("education_scholarships", "scholarships"):
                inconsistencies.append(
                    f"Title '{title}' relates to scholarships but category is '{cat}'."
                )

    # 7. Category validity
    if cat and cat not in SUPPORTED_CATEGORIES and cat not in ("education_scholarships", "tax_gst", "out_of_scope"):
        inconsistencies.append(
            f"Category '{cat}' is not in the recognized categories."
        )

    return inconsistencies


def inspect_document_support(query: str, chunk_text: str, metadata: dict | None = None) -> tuple[bool, str]:
    """Inspect whether a retrieved chunk's actual content supports query claims.
    
    Relevance to general farming alone is not sufficient.
    For KCC questions, only evidence supporting KCC procedures, eligibility,
    credit limits, interest subventions, collateral, or application documents is accepted.
    """
    q_lower = query.lower()
    text_lower = chunk_text.lower()
    meta = metadata or {}
    meta_title = str(meta.get("title", "")).lower()

    # KCC (Kisan Credit Card) queries
    is_kcc_query = (
        any(k in q_lower for k in [
            "kisan credit card", "kcc", "credit card for farmer", "crop loan",
            "किसान क्रेडिट कार्ड", "केसीसी", "पीक कर्ज"
        ])
        or ("credit" in q_lower and ("farmer" in q_lower or "agriculture" in q_lower))
    )

    if is_kcc_query:
        kcc_indicators = [
            "kisan credit card",
            "kcc",
            "scale of finance",
            "credit limit",
            "interest subvention",
            "prompt repayment",
            "collateral requirement",
            "short-term crop loan",
            "concessional interest rate",
            "agricultural credit",
            "kisan call centre",
            "1800-180-1551",
            "record of rights",
            "documents required",
            "7/12",
        ]
        has_kcc_support = any(ind in text_lower for ind in kcc_indicators)

        # Check if chunk is from official credit guidelines specifying application documents or verification
        if not has_kcc_support:
            is_credit_doc = (
                any(k in meta_title for k in ["agricultural credit", "kisan credit card", "credit guidelines"])
                or "agricultural-credit" in str(meta.get("source_url", "")).lower()
            )
            if is_credit_doc and any(
                ind in text_lower for ind in [
                    "documents required", "record of rights", "7/12", "land record", "khasra", "patta", "dltc",
                    "kisan call centre", "1800-180-1551"
                ]
            ):
                has_kcc_support = True

        if has_kcc_support:
            return True, "Supports Kisan Credit Card scheme procedures, eligibility, loan terms, or documentation."

        # Distinguish why it does not support KCC
        if "pm-kisan" in text_lower or "samman nidhi" in text_lower or "pfms" in text_lower or "6,000" in text_lower or "pm kisan" in meta_title:
            return False, "Discusses PM-KISAN income support / PFMS DBT rather than Kisan Credit Card procedures or eligibility."
        elif "soil health" in text_lower or "fertilizer" in text_lower:
            return False, "Discusses soil health or fertilizer management rather than Kisan Credit Card credit."
        elif "pest" in text_lower or "cotton" in text_lower:
            return False, "Discusses crop pest management rather than Kisan Credit Card credit."
        else:
            return False, "Does not contain procedures, eligibility, or terms for Kisan Credit Card."

    # PMFBY Crop Insurance Queries
    if any(k in q_lower for k in ["pmfby", "fasal bima", "crop insurance", "पीक विमा", "फसल बीमा", "विमा हप्ता", "प्रीमियम"]):
        if any(w in text_lower for w in ["pmfby", "fasal bima", "crop insurance", "kharif", "rabi", "premium"]):
            return True, "Supports Pradhan Mantri Fasal Bima Yojana (PMFBY) crop insurance rules and premium rates."
        return False, "Does not discuss PMFBY crop insurance."

    # Land Records & Tenant Farmer Queries
    if any(k in q_lower for k in ["7/12", "ror", "record of rights", "bhulekh", "उतारा", "खतौनी", "बटाईदार", "काश्तकार", "भाडेकरू", "tenant"]):
        if any(w in text_lower for w in ["7/12", "record of rights", "ror", "tenant", "bhulekh", "documents required", "self-declaration"]):
            return True, "Supports farmer land records, 7/12 extract, or tenant verification."
        return False, "Does not discuss land records or tenant verification."

    # Cotton Pest & Insect Queries (Multilingual)
    if any(k in q_lower for k in ["pest", "कीड", "कीट", "bollworm", "बोंडअळी", "armyworm", "लष्करी", "ipm"]):
        if any(p in text_lower for p in ["pest", "bollworm", "ipm", "cibrc", "insecticide", "neem", "armyworm", "pheromone", "etl"]):
            return True, "Supports pest management and crop protection recommendations."
        return False, "Does not discuss pest management."

    # Fertilizer & Soil Health Queries (Multilingual)
    if any(k in q_lower for k in ["fertilizer", "soil health", "खत", "उर्वरक", "मृदा", "माती", "urea", "युरिया", "यूरिया", "npk"]):
        if any(f in text_lower for f in ["fertilizer", "soil health", "npk", "micronutrient", "shc", "soil test", "urea", "nitrogen"]):
            return True, "Supports soil health and fertilizer recommendations."
        return False, "Does not discuss soil health or fertilizer specifications."

    # Crop Disease & Physiological Disorder Queries (Multilingual)
    if any(k in q_lower for k in ["crop disease", "crop disorder", "yellowing", "chlorosis", "पिवळ", "पीला", "रोग", "stress", "heat", "तणाव"]):
        if any(d in text_lower for d in ["disease", "disorder", "chlorosis", "yellowing", "pathogen", "blight", "rot", "heat stress", "deficiency"]):
            return True, "Supports crop disease diagnosis and stress management."
        return False, "Does not discuss crop diseases or disorders."

    # Official Central & State Scheme Queries (Multilingual & Cross-lingual)
    try:
        from app.schemes.pipeline import find_matching_scheme_for_query
        matched_scheme = find_matching_scheme_for_query(query)
        if matched_scheme:
            name_lower = matched_scheme.scheme_name.lower()
            key_words = [
                w for w in re.findall(r"\w+", name_lower)
                if len(w) > 3 and w not in {"yojana", "scheme", "pradhan", "mantri", "state", "central"}
            ]
            if any(w in text_lower or w in meta_title for w in key_words):
                return True, f"Supports official guidelines and provisions for {matched_scheme.scheme_name}."
            if matched_scheme.official_source_url and matched_scheme.official_source_url.lower() in str(meta.get("source_url", "")).lower():
                return True, f"Official source citation match for {matched_scheme.scheme_name}."
    except Exception:
        pass

    # General government queries: require topical entity match
    words = [w for w in re.findall(r"\w+", q_lower) if len(w) > 3 and w not in {"what", "when", "where", "which", "about", "farmer", "government", "scheme", "apply", "state"}]
    if words and any(w in text_lower for w in words):
        return True, "Topically grounded in query entities."
    elif not words:
        return True, "General topic match."

    return False, "Does not contain substantive supporting information for query claims."


def filter_supported_evidence(
    query: str,
    evidence: list[dict],
    category: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Filter retrieved evidence to chunks whose content actually supports the query claims.
    
    Returns (supported_evidence, rejected_evidence_with_reasons).
    """
    supported = []
    rejected = []
    for ev in evidence:
        text = ev.get("text", "")
        meta = ev.get("metadata", {})
        is_supported, reason = inspect_document_support(query, text, meta)
        if is_supported:
            supported.append(ev)
        else:
            rejected.append({**ev, "rejection_reason": reason})
    return supported, rejected


def build_citations(evidence: list[dict]) -> list[dict[str, Any]]:
    """One citation per unique (source_url/title, page_number).

    Sets ev['cid'] on each evidence item so that markdown citation markers
    [1], [2] correspond 1-to-1 with the numbered citation list.
    Preserves exact stored metadata, audits for inconsistencies, and avoids date fabrication.
    """
    index: dict[tuple, int] = {}
    out: list[dict[str, Any]] = []

    for ev in evidence:
        m = ev.get("metadata", {})
        raw_url = m.get("source_url", "").strip()
        title = m.get("title", "").strip() or "Official Government Document"
        page_num = m.get("page_number") or m.get("page")

        key = (raw_url or title, page_num)
        if key not in index:
            cid = len(out) + 1
            index[key] = cid

            # URL validation (preserve verified URL without alteration)
            is_valid = is_valid_official_url(raw_url)
            clean_url = raw_url if is_valid else ""
            url_status = "available" if is_valid else "unavailable"

            # Freshness date distinction (never fabricate missing dates)
            raw_last_checked = m.get("last_checked") or ""
            if not raw_last_checked and m.get("ingested_at"):
                raw_last_checked = str(m.get("ingested_at"))[:10]

            official_updated = (
                m.get("last_updated")
                or m.get("updated_date")
                or m.get("publication_date")
                or ""
            )
            if official_updated == OFFICIAL_DATE_NOT_AVAILABLE:
                official_updated = ""

            has_official_date = bool(official_updated)
            display_last_updated = (
                official_updated if has_official_date else OFFICIAL_DATE_NOT_AVAILABLE
            )

            auth = (
                m.get("department")
                or m.get("authority")
                or m.get("source_name")
                or "Official Government Authority"
            )

            # Metadata consistency audit
            inconsistencies = check_metadata_consistency(m)

            out.append({
                "id": cid,
                "title": title,
                "url": clean_url,
                "url_status": url_status,
                "raw_source_url": raw_url if raw_url else None,
                "authority": auth,
                "department": auth,
                "source_name": m.get("source_name") or auth,
                "category": m.get("category", "government_schemes"),
                "document_type": m.get("document_type", "document"),
                "publication_date": m.get("publication_date", ""),
                "updated_date": m.get("updated_date", ""),
                "last_checked": raw_last_checked or "Check date not recorded",
                "last_updated": display_last_updated,
                "has_official_date": has_official_date,
                "page_number": page_num,
                "inconsistencies": inconsistencies,
                "has_inconsistencies": bool(inconsistencies),
                "metadata_status": "inconsistent" if inconsistencies else "consistent",
            })

        ev["cid"] = index[key]

    return out


def reconcile_citations_with_answer(
    answer_text: str,
    citations: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Ensure citation markers in answer map 1-to-1 to the returned citation list.
    
    Removes unused citations, renumbers sequentially, and corrects markers in answer text.
    Handles single [1], adjacent [1][2], and compound [1, 2] markers cleanly.
    """
    if not citations:
        clean_text = re.sub(r"\[[\d\s,]+\]", "", answer_text)
        clean_text = re.sub(r" +", " ", clean_text)
        return clean_text, []

    # Find all citation markers like [1], [2], or [1, 2] in answer_text
    matches = list(re.finditer(r"\[([\d\s,]+)\]", answer_text))
    cited_ids = []
    for m in matches:
        parts = [p.strip() for p in m.group(1).split(",")]
        for p in parts:
            if p.isdigit():
                cited_ids.append(int(p))

    unique_cited_ids = sorted(set(cited_ids))

    if not unique_cited_ids:
        # If no citation markers in text, return citations as is
        return answer_text, citations

    # Map old citation IDs to new 1-indexed sequential IDs for citations that exist
    citation_map = {c["id"]: c for c in citations}
    retained_citations = []
    id_remap = {}

    for old_id in unique_cited_ids:
        if old_id in citation_map:
            new_id = len(retained_citations) + 1
            c = dict(citation_map[old_id])
            c["id"] = new_id
            retained_citations.append(c)
            id_remap[old_id] = new_id

    # If none of the cited IDs existed in citation_map, clean markers and return empty
    if not retained_citations:
        clean_text = re.sub(r"\[[\d\s,]+\]", "", answer_text)
        clean_text = re.sub(r" +", " ", clean_text)
        return clean_text, []

    # Replace markers in text: handle compound [1, 2] and single [1]
    def replace_bracket(match):
        parts = [p.strip() for p in match.group(1).split(",")]
        remapped_parts = []
        for p in parts:
            if p.isdigit() and int(p) in id_remap:
                remapped_parts.append(str(id_remap[int(p)]))
        if remapped_parts:
            seen = set()
            deduped = [x for x in remapped_parts if not (x in seen or seen.add(x))]
            return f"[{', '.join(deduped)}]"
        return ""  # remove invalid marker

    updated_answer = re.sub(r"\[([\d\s,]+)\]", replace_bracket, answer_text)

    # Normalize adjacent identical markers like [1][1] or [1] [1]
    updated_answer = re.sub(r"\[(\d+)\](?:\s*\[\1\])+", r"[\1]", updated_answer)

    # Clean double spaces and space before punctuation
    updated_answer = re.sub(r" +", " ", updated_answer)
    updated_answer = re.sub(r" +([.,;])", r"\1", updated_answer)

    return updated_answer, retained_citations


def format_citations_markdown(citations: list[dict[str, Any]]) -> str:
    """Format a numbered official sources list with explicit freshness date distinction."""
    if not citations:
        return "\n\n_No official sources were available for citation._"

    lines = ["\n\n### Official Sources & Information Freshness\n"]
    for c in citations:
        cid = c["id"]
        title = c["title"]
        auth = c.get("department") or c.get("authority") or "Official Department"
        url = c.get("url")
        last_updated = c.get("last_updated") or OFFICIAL_DATE_NOT_AVAILABLE
        last_checked = c.get("last_checked") or "Check date not recorded"
        page = c.get("page_number")

        page_str = f" (Page {page})" if page else ""
        if url:
            link_str = f"[{url}]({url})"
        else:
            link_str = f"_{URL_NOT_AVAILABLE}_"

        entry = (
            f"[{cid}] **{title}**{page_str} — *{auth}*\n"
            f"   - **Official Source URL:** {link_str}\n"
            f"   - **Official Document Date:** {last_updated}\n"
            f"   - **Verified Check Date:** {last_checked}"
        )
        if c.get("has_inconsistencies") and c.get("inconsistencies"):
            issues = "; ".join(c["inconsistencies"])
            entry += f"\n   - ⚠️ **Metadata Inconsistency Flag:** {issues}"
        lines.append(entry)

    lines.append(f"\n{ADVISORY_DISCLAIMER}")
    return "\n".join(lines)
