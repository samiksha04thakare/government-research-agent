"""Scheme Name Normalization, Canonical Scheme ID Resolution, and Equivalence Matching.

Prevents duplicate schemes while strictly preserving genuinely different schemes
(e.g., distinguishing PMAY-G from PMAY-U, PM-KUSUM Component A from Component B,
and Mukhyamantri Majhi Ladki Bahin from Lek Ladki).
"""
import re
import unicodedata
from typing import Any


# Known official scheme identifier mapping with high-confidence trigger patterns
CANONICAL_SCHEME_TRIGGERS: list[tuple[str, list[str]]] = [
    # Women and Child Development (MH-WOM-01 to MH-WOM-11)
    ("MH-WOM-01", ["ladki bahin", "ladakibahin", "लाडकी बहीण", "लाडकी बहिण", "लाड़की बहिन", "माझी लाडकी", "majhi ladki"]),
    ("MH-WOM-02", ["lek ladki", "लेक लाडकी", "lek-ladki"]),
    ("MH-WOM-03", ["pmmvy", "matru vandana", "मातृ वंदना", "मातृवंदना"]),
    ("MH-WOM-04", ["one stop centre", "one stop center", "वन स्टॉप", "sakhi centre", "sakhi center", "सखी केंद्र", "sakhi"]),
    ("MH-WOM-05", ["women helpline", "महिला हेल्पलाइन", "महिला हेल्पलाईन", "helpline 181"]),
    ("MH-WOM-06", ["nari adalat", "नारी अदालत"]),
    ("MH-WOM-07", ["ujjawala", "उज्ज्वला"]),
    ("MH-WOM-08", ["shakti sadan", "शक्ति सदन"]),
    ("MH-WOM-09", ["hub for empowerment", "महिला सक्षमीकरण", "hew"]),
    ("MH-WOM-10", ["mavim", "माविम", "mahila arthik vikas", "bachat gat", "बचत गट", "बचतगट"]),
    ("MH-WOM-11", ["saksham anganwadi", "poshan 2.0", "poshan", "पोषण २.०", "पोषण 2.0", "अंगणवाडी"]),

    # Central and State Agriculture & Welfare Schemes
    ("PM-KISAN", ["pm-kisan", "pm kisan", "pmkisan", "किसान सम्मान निधि", "kisan samman nidhi"]),
    ("KCC", ["kisan credit card", "kcc", "केसीसी", "किसान क्रेडिट"]),
    ("PMFBY", ["pmfby", "fasal bima", "पीएमएफबीवाई", "फसल बीमा", "पीक विमा"]),
    ("PM-KUSUM-B", ["kusum component b", "kusum घटक ब", "pm-kusum component b", "stand-alone solar agriculture pumps"]),
    ("PM-KUSUM-A", ["kusum component a", "kusum घटक अ", "pm-kusum component a"]),
    ("PM-KUSUM-C", ["kusum component c", "kusum घटक क", "pm-kusum component c"]),
    ("PM-KUSUM", ["pm-kusum", "pm kusum", "kusum", "कुसुम"]),
    ("NAMO-SHETAKARI", ["namo shetakari", "namo shetkari", "नमो शेतकरी"]),
    ("SHAASHWAT-SINCHAN", ["shaashwat", "shet tale", "शाश्वत", "शेततळे", "shaashwat sheti"]),
    ("MAHA-POST-MATRIC-SCHOLARSHIP", ["post-matric scholarship", "पोस्ट-मॅट्रिक", "मैट्रिकोत्तर छात्रवृत्ति", "mahadbt scholarship", "post matric scholarship"]),
    ("SMAM", ["smam", "mechanization", "यांत्रिकीकरण", "agrimachinery", "agricultural mechanization"]),
    ("SOIL-HEALTH-CARD", ["soil health card", "मृदा स्वास्थ्य कार्ड", "मृदा कार्ड", "माती आरोग्य पत्रिका"]),
    ("PM-JAY", ["ayushman bharat", "pm-jay", "pmjay", "आयुष्मान भारत"]),
    ("PMAY-G", ["pmay-g", "pmay gramin", "ग्रामीण आवास", "awas yojana gramin"]),
    ("PMAY-U", ["pmay-u", "pmay urban", "शहरी आवास", "awas yojana urban"]),
]


def extract_official_code(text: str) -> str | None:
    """Extract official scheme code if explicitly present in brackets or text."""
    if not text:
        return None

    # 1. Official State / Central Codes like MH-WOM-01, MH-AGR-02
    m = re.search(r"\b([A-Z]{2,4}-[A-Z]{2,5}-\d{1,4})\b", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # 2. BDS Budget Scheme Code format (e.g., 2401A511, 1101100034)
    m = re.search(r"\b([0-9]{4}[A-Z][0-9]{3}|[0-9]{8,12})\b", text)
    if m:
        return m.group(1)

    # 3. Known official acronyms in parentheses: (PM-KISAN), (KCC), (PMFBY), (SMAM), (PM-JAY), (PMAY-G), (PMAY-U), (PMMVY)
    m = re.search(r"\(([A-Z0-9]+(?:-[A-Z0-9]+)*)\)", text)
    if m:
        cand = m.group(1).upper()
        if len(cand) >= 3 and cand not in {"SCHEME", "YOJANA", "GOVT", "INDIA", "CENTRAL", "STATE"}:
            return cand

    return None


def normalize_scheme_name(name: str) -> str:
    """Normalize a scheme name into a clean, canonical comparable representation."""
    if not name:
        return ""

    # Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", name).strip()

    # Remove content in parentheses if it's an acronym or translation already captured
    cleaned = re.sub(r"\([^)]*\)", "", normalized)

    # Remove noise characters and punctuation
    cleaned = re.sub(r"[\.,\-—_:;!?'\"/\\#]", " ", cleaned)

    # Convert to lowercase
    cleaned = cleaned.lower()

    # Remove generic scheme stopwords that cause duplicate variations
    stopwords = {
        "scheme", "yojana", "yojna", "yojanechi", "yojanecha",
        "mission", "abhayan", "abhiyan", "initiative", "program", "programme",
        "guidelines", "operational", "details", "overview",
        "योजना", "अभियान", "मिशन", "उपक्रम", "मार्गदर्शक",
    }
    tokens = [t for t in cleaned.split() if t not in stopwords and len(t) > 1]
    return " ".join(tokens)


def get_canonical_scheme_id(
    scheme_name: str,
    hindi_name: str = "",
    official_source_url: str = "",
) -> str:
    """Derive a stable, deterministic unique identifier (scheme_id) for any scheme.
    
    1. Extracts explicit official codes (e.g. MH-WOM-01, PMAY-G, PM-KISAN)
    2. Matches deterministic trigger keywords in name or hindi_name
    3. Falls back to a deterministic normalized slug that preserves differentiating tokens
    """
    combined_text = f"{scheme_name or ''} {hindi_name or ''}"

    # 1. Check for explicit code in parentheses or text
    extracted_code = extract_official_code(scheme_name) or extract_official_code(hindi_name)
    if extracted_code:
        # Normalize component variations (e.g., KUSUM Component B -> PM-KUSUM-B)
        lower_comb = combined_text.lower()
        if "kusum" in lower_comb:
            if "component b" in lower_comb or "घटक ब" in lower_comb:
                return "PM-KUSUM-B"
            elif "component a" in lower_comb or "घटक अ" in lower_comb:
                return "PM-KUSUM-A"
            elif "component c" in lower_comb or "घटक क" in lower_comb:
                return "PM-KUSUM-C"
        return extracted_code

    # 2. Check canonical trigger patterns
    lower_comb = combined_text.lower()
    for canonical_id, triggers in CANONICAL_SCHEME_TRIGGERS:
        for trig in triggers:
            if trig.lower() in lower_comb:
                return canonical_id

    # 3. Fallback: generate a deterministic canonical slug
    normalized = normalize_scheme_name(scheme_name)
    if not normalized and hindi_name:
        normalized = normalize_scheme_name(hindi_name)

    if not normalized:
        return "SCHEME-UNKNOWN"

    # Replace spaces with hyphens and convert to uppercase
    slug = re.sub(r"\s+", "-", normalized).upper()
    return slug[:50]


def are_schemes_equivalent(scheme_a: Any, scheme_b: Any) -> bool:
    """Determine whether two scheme records or dictionaries represent the same scheme."""
    def _extract_attrs(obj):
        if isinstance(obj, dict):
            return (
                obj.get("scheme_id") or "",
                obj.get("scheme_name") or "",
                obj.get("hindi_name") or "",
                obj.get("official_source_url") or "",
            )
        return (
            getattr(obj, "scheme_id", "") or "",
            getattr(obj, "scheme_name", "") or "",
            getattr(obj, "hindi_name", "") or "",
            getattr(obj, "official_source_url", "") or "",
        )

    id_a, name_a, hi_a, url_a = _extract_attrs(scheme_a)
    id_b, name_b, hi_b, url_b = _extract_attrs(scheme_b)

    # 1. Exact scheme_id match if provided
    canon_a = id_a or get_canonical_scheme_id(name_a, hi_a, url_a)
    canon_b = id_b or get_canonical_scheme_id(name_b, hi_b, url_b)

    if canon_a and canon_b and canon_a == canon_b:
        return True

    # 2. Normalized name match
    norm_a = normalize_scheme_name(name_a)
    norm_b = normalize_scheme_name(name_b)
    if norm_a and norm_b and norm_a == norm_b:
        return True

    return False
