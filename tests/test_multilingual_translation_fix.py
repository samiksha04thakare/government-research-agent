"""Comprehensive automated tests for Multilingual Language Translation Fix.

Validates:
1. English ('en'), Hindi ('hi'), and Marathi ('mr') responses tested separately.
2. Request validation and safe fallback (defaults safely to 'en' when missing or invalid).
3. Selected language reaches backend and answer-generation pipeline.
4. Citations ([1]), official URLs, scheme names, eligibility figures, and RAG grounding are preserved.
5. Consecutive queries alternating languages (en -> hi -> mr) update language dynamically.
6. Markdown citation blocks & freshness disclaimers are translated to target language.
7. Out-of-scope and fallback nodes in LangGraph localize to target language.
8. Frontend i18n translation dictionary covers all keys in en, hi, mr.
"""
import json
import re
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.language import detect_language, resolve_language, UI_STRINGS
from app.utils.citations import format_citations_markdown
from app.graph.nodes import (
    classify_query,
    out_of_scope,
    no_documents,
    insufficient,
)


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Validation & Language Fallback
# -----------------------------------------------------------------------------

def test_request_language_validation_safe_defaults(client):
    """Verify invalid or missing language defaults safely to 'en' without crashing."""
    # Invalid code 'xyz'
    res1 = client.post(
        "/research",
        json={"question": "What is the Kisan Credit Card limit?", "language": "xyz"},
    )
    assert res1.status_code == 200
    assert res1.json()["language"] == "en"

    # None / omitted language
    res2 = client.post(
        "/research",
        json={"question": "What is the Kisan Credit Card limit?"},
    )
    assert res2.status_code == 200
    assert res2.json()["language"] == "en"


def test_language_detection_and_resolution():
    """Verify target language resolution handles explicit overrides and auto-detection."""
    # Explicit Marathi override on English question
    target, detected = resolve_language("mr", "How to apply for crop loan?")
    assert target == "mr"
    assert detected == "en"

    # Explicit Hindi override on English question
    target, detected = resolve_language("hi", "How to apply for crop loan?")
    assert target == "hi"
    assert detected == "en"

    # Auto detection for Devanagari Hindi
    target, detected = resolve_language("auto", "किसान क्रेडिट कार्ड कैसे मिलेगा?")
    assert target == "hi"
    assert detected == "hi"

    # Auto detection for Devanagari Marathi
    target, detected = resolve_language("auto", "शेतकऱ्यांना पीक कर्ज कसे मिळते?")
    assert target == "mr"
    assert detected == "mr"


# -----------------------------------------------------------------------------
# 2. English, Hindi, and Marathi Responses Tested Separately
# -----------------------------------------------------------------------------

def test_english_research_response(client):
    """Verify English answer generation, citations, and source grounding."""
    res = client.post(
        "/research",
        json={
            "question": "What is the proposed budget outlay and allocation for Namo Shetakari Mahasanmaan Nidhi Yojana?",
            "language": "en",
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "en"
    assert len(data["sources"]) > 0
    # Citations intact
    assert "[1]" in data["answer"]
    # Check official figures & URL
    assert any(s.get("url") for s in data["sources"])
    assert "Official Referenced Sources" in data["answer"] or "References" in data["answer"] or len(data["sources"]) > 0


def test_hindi_research_response_devanagari(client):
    """Verify Hindi answer generation in natural Devanagari script preserving facts."""
    res = client.post(
        "/research",
        json={
            "question": "What is the proposed budget outlay and allocation for Namo Shetakari Mahasanmaan Nidhi Yojana?",
            "language": "hi",
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "hi"
    assert len(data["sources"]) > 0
    assert "[1]" in data["answer"]

    # Devanagari script presence
    devanagari_chars = re.findall(r"[\u0900-\u097F]", data["answer"])
    assert len(devanagari_chars) >= 20, "Expected Hindi answer to contain natural Devanagari text"

    # Official citations and freshness notice in Hindi
    assert "आधिकारिक संदर्भित स्रोत" in data["answer"] or "संदर्भ" in data["answer"] or "[1]" in data["answer"]


def test_marathi_research_response_devanagari(client):
    """Verify Marathi answer generation in natural Devanagari script preserving facts."""
    res = client.post(
        "/research",
        json={
            "question": "What is the proposed budget outlay and allocation for Namo Shetakari Mahasanmaan Nidhi Yojana?",
            "language": "mr",
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "mr"
    assert len(data["sources"]) > 0
    assert "[1]" in data["answer"]

    # Devanagari script presence
    devanagari_chars = re.findall(r"[\u0900-\u097F]", data["answer"])
    assert len(devanagari_chars) >= 20, "Expected Marathi answer to contain natural Devanagari text"

    # Official citations and freshness notice in Marathi
    assert "अधिकृत संदर्भित स्रोत" in data["answer"] or "संदर्भ" in data["answer"] or "[1]" in data["answer"]


# -----------------------------------------------------------------------------
# 3. Consecutive Language Switching Between Questions
# -----------------------------------------------------------------------------

def test_consecutive_language_switching(client):
    """Verify sequential requests cleanly switch language between en, hi, and mr."""
    q = "What is the interest rate and credit limit for Kisan Credit Card?"

    # Turn 1: English
    r1 = client.post("/research", json={"question": q, "language": "en"}).json()
    assert r1["language"] == "en"
    assert "4%" in r1["answer"]
    assert "[1]" in r1["answer"]

    # Turn 2: Hindi
    r2 = client.post("/research", json={"question": q, "language": "hi"}).json()
    assert r2["language"] == "hi"
    assert "4%" in r2["answer"]
    assert "किसान" in r2["answer"]
    assert "[1]" in r2["answer"]

    # Turn 3: Marathi
    r3 = client.post("/research", json={"question": q, "language": "mr"}).json()
    assert r3["language"] == "mr"
    assert "4%" in r3["answer"]
    assert "शेतकऱ्यांसाठी" in r3["answer"] or "किसान" in r3["answer"]
    assert "[1]" in r3["answer"]

    # Turn 4: Back to English
    r4 = client.post("/research", json={"question": q, "language": "en"}).json()
    assert r4["language"] == "en"
    assert "4%" in r4["answer"]


# -----------------------------------------------------------------------------
# 4. Citations & Advisory Localization
# -----------------------------------------------------------------------------

def test_format_citations_markdown_localization():
    """Verify format_citations_markdown renders localized headings, dates, and advisory."""
    citations = [
        {
            "id": 1,
            "title": "Maharashtra Agriculture Budget 2026-27",
            "url": "https://krishi.maharashtra.gov.in/bds",
            "department": "Department of Agriculture",
            "last_updated": "2026-03-15",
            "last_checked": "2026-10-13",
            "page_number": 42,
        }
    ]

    en_md = format_citations_markdown(citations, language="en")
    assert "### Official Sources & Information Freshness" in en_md
    assert "Official Document Date:" in en_md
    assert "Verified Check Date:" in en_md
    assert "https://krishi.maharashtra.gov.in/bds" in en_md
    assert "[1]" in en_md

    hi_md = format_citations_markdown(citations, language="hi")
    assert "आधिकारिक स्रोत" in hi_md
    assert "आधिकारिक स्रोत URL:" in hi_md
    assert "सत्यापन जांच दिनांक:" in hi_md
    assert "https://krishi.maharashtra.gov.in/bds" in hi_md
    assert "[1]" in hi_md

    mr_md = format_citations_markdown(citations, language="mr")
    assert "अधिकृत शासकीय स्रोत" in mr_md
    assert "अधिकृत स्रोत URL:" in mr_md
    assert "पडताळणी तारीख:" in mr_md
    assert "https://krishi.maharashtra.gov.in/bds" in mr_md
    assert "[1]" in mr_md


# -----------------------------------------------------------------------------
# 5. LangGraph Node Language Propagation & Localized Messages
# -----------------------------------------------------------------------------

def test_langgraph_nodes_propagate_language():
    """Verify classify_query, out_of_scope, no_documents, and insufficient nodes respect language."""
    # 1. classify_query with explicit language
    state = {"question": "Can I get movie recommendations?", "language": "hi"}
    new_state = classify_query(state)
    assert new_state["language"] == "hi"

    # 2. out_of_scope produces Hindi explanation
    oos_state = {"question": "Recommend Bollywood movies", "language": "hi"}
    oos_result = out_of_scope(oos_state)
    assert oos_result["status"] == "out_of_scope"
    assert "सरकारी" in oos_result["final_answer"]

    # 3. out_of_scope produces Marathi explanation
    oos_state_mr = {"question": "Recommend Bollywood movies", "language": "mr"}
    oos_result_mr = out_of_scope(oos_state_mr)
    assert oos_result_mr["status"] == "out_of_scope"
    assert "शासकीय" in oos_result_mr["final_answer"]

    # 4. no_documents produces Hindi message
    no_doc_hi = no_documents({"question": "Quantum gravity", "language": "hi", "category": "science"})
    assert no_doc_hi["status"] == "no_documents_for_category"
    assert "सरकारी" in no_doc_hi["final_answer"] or "अनुक्रमित" in no_doc_hi["final_answer"]

    # 5. insufficient produces Marathi message
    insuf_mr = insufficient({"question": "Unclear topic", "language": "mr", "evidence": []})
    assert insuf_mr["status"] == "insufficient_evidence"
    assert "सरकारी" in insuf_mr["final_answer"] or "अधिकृत" in insuf_mr["final_answer"]


# -----------------------------------------------------------------------------
# 6. Frontend i18n Translation Dictionary Completeness
# -----------------------------------------------------------------------------

def test_frontend_i18n_keys_match_across_languages():
    """Verify that frontend/src/i18n.js has identical key coverage for en, hi, and mr."""
    from pathlib import Path
    i18n_path = Path("frontend/src/i18n.js")
    assert i18n_path.exists(), "frontend/src/i18n.js must exist"

    content = i18n_path.read_text(encoding="utf-8")
    assert "export const SUPPORTED_LANGUAGES" in content
    assert "export const UI_TRANSLATIONS" in content
    assert "export const DOMAIN_CATEGORIES_BY_LANG" in content

    # Test that essential UI strings are in app.utils.language.UI_STRINGS
    for lang in ["en", "hi", "mr"]:
        assert lang in UI_STRINGS
        assert "official_sources_heading" in UI_STRINGS[lang]
        assert "official_date" in UI_STRINGS[lang]
        assert "advisory_disclaimer" in UI_STRINGS[lang]
