"""Regression and safety test suite for Step 8: Farmer-Friendly Answers and Multilingual Support.

Covers:
1. English, Hindi, and Marathi response preferences.
2. Language auto-detection fallback (Devanagari Hindi vs Marathi vs English).
3. Preservation of citation markers ([1]) after translation and localization.
4. Unsupported application procedures and explicit missing document notices.
5. Follow-up clarifying question generation (asking when critical details are needed, silent when answered).
6. Preservation of relevance threshold (0.25) and evidence safeguards.
7. Existing out-of-scope rejection in multilingual contexts.
8. Devanagari category routing across farmer, fertilizers, and pests.
9. Agricultural advisory safety: distinguishing general guidance, zero invented chemical dosages.
"""
import pytest
from fastapi.testclient import TestClient

from app.config import RELEVANCE_THRESHOLD
from app.main import app
from app.utils.language import detect_language, resolve_language, UI_STRINGS
from app.agents.farmer_explainer import (
    format_farmer_kcc_answer,
    format_farmer_general_answer,
    get_clarifying_question,
)
from app.agents.classifier import heuristic_classify


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Language Detection & Resolution
# -----------------------------------------------------------------------------

def test_language_detection():
    """Verify accurate detection of English, Hindi, and Marathi."""
    en_query = "What is the procedure for obtaining a Kisan Credit Card?"
    hi_query = "किसान क्रेडिट कार्ड के लिए आवेदन कैसे करें और ब्याज दर क्या है?"
    mr_query = "किसान क्रेडिट कार्डसाठी अर्ज कसा करावा आणि व्याजदर काय आहे?"

    assert detect_language(en_query) == "en"
    assert detect_language(hi_query) == "hi"
    assert detect_language(mr_query) == "mr"

    # Marathi distinctive characters and markers
    assert detect_language("शेतकऱ्यांना पीक कर्जासाठी 7/12 उतारा कसा मिळेल?") == "mr"
    assert detect_language("पिकांचे नुकसान झाल्यावर मदत कशी मिळते?") == "mr"

    # Hindi distinctive markers
    assert detect_language("किसानों को फसल ऋण पर कितनी छूट मिलेगी?") == "hi"
    assert detect_language("खाद की सब्सिडी कैसे प्राप्त होगी?") == "hi"


def test_language_resolution_preferences():
    """Verify preference override and auto-detection fallback."""
    mr_query = "किसान क्रेडिट कार्डसाठी अर्ज कसा करावा?"

    # Explicit override to English
    target, detected = resolve_language("en", mr_query)
    assert target == "en"
    assert detected == "mr"

    # Explicit override to Hindi
    target, detected = resolve_language("hi", mr_query)
    assert target == "hi"
    assert detected == "mr"

    # Auto detect
    target, detected = resolve_language("auto", mr_query)
    assert target == "mr"
    assert detected == "mr"


# -----------------------------------------------------------------------------
# 2. English, Hindi, and Marathi API Responses
# -----------------------------------------------------------------------------

def test_kcc_response_in_english(client):
    """Verify KCC response with English language preference."""
    res = client.post(
        "/research",
        json={"question": "How can a farmer apply for Kisan Credit Card?", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "en"
    assert "[1]" in data["answer"]
    # Check financial accuracy preserved
    assert "₹3,00,000" in data["answer"] or "3,00,000" in data["answer"]
    assert "4%" in data["answer"]
    assert "7%" in data["answer"]
    assert len(data["practical_steps"]) >= 2


def test_kcc_response_in_hindi(client):
    """Verify KCC response with Hindi language preference."""
    res = client.post(
        "/research",
        json={"question": "How can a farmer apply for Kisan Credit Card?", "language": "hi"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "hi"
    assert "[1]" in data["answer"]
    # Hindi farmer-friendly headings
    assert "किसान क्रेडिट कार्ड" in data["answer"]
    assert "ब्याज" in data["answer"]
    # Check financial figures strictly preserved
    assert "₹3,00,000" in data["answer"] or "3,00,000" in data["answer"]
    assert "4%" in data["answer"]
    assert "7%" in data["answer"]
    assert len(data["practical_steps"]) >= 2


def test_kcc_response_in_marathi(client):
    """Verify KCC response with Marathi language preference."""
    res = client.post(
        "/research",
        json={"question": "What is the procedure to obtain Kisan Credit Card?", "language": "mr"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "mr"
    assert "[1]" in data["answer"]
    # Marathi farmer-friendly headings
    assert "शेतकऱ्यांसाठी" in data["answer"]
    assert "किसान क्रेडिट कार्ड" in data["answer"]
    assert "व्याजदर" in data["answer"] or "व्याज" in data["answer"]
    # Exact financial terms preserved
    assert "₹3,00,000" in data["answer"] or "3,00,000" in data["answer"]
    assert "4%" in data["answer"]
    assert "7%" in data["answer"]
    assert len(data["practical_steps"]) >= 2


# -----------------------------------------------------------------------------
# 3. Language Auto-Detection via API
# -----------------------------------------------------------------------------

def test_auto_detection_hindi_query(client):
    """Verify Hindi question is auto-detected when language='auto'."""
    res = client.post(
        "/research",
        json={"question": "किसान क्रेडिट कार्ड योजना क्या है और इसमें कितना ब्याज लगता है?", "language": "auto"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "hi"
    assert data["detected_language"] == "hi"
    assert "[1]" in data["answer"]


def test_auto_detection_marathi_query(client):
    """Verify Marathi question is auto-detected when language='auto'."""
    res = client.post(
        "/research",
        json={"question": "किसान क्रेडिट कार्डचे व्याजदर काय आहे आणि किती कर्ज मिळते?", "language": "auto"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "completed"
    assert data["language"] == "mr"
    assert data["detected_language"] == "mr"
    assert "[1]" in data["answer"]


# -----------------------------------------------------------------------------
# 4. Citation Marker Preservation Across Translations
# -----------------------------------------------------------------------------

def test_citation_marker_preservation_across_all_languages():
    """Verify citation markers ([1]) remain attached to factual claims across EN, HI, MR."""
    mock_supported = [
        {
            "cid": 1,
            "text": "Kisan Credit Card short term crop loan limit up to Rs 3,00,000 at 7% per annum. Prompt repayment incentive is 3%, resulting in effective interest rate of 4% per annum.",
            "title": "KCC Guidelines",
            "url": "https://agricoop.nic.in/kcc",
            "similarity_score": 0.85,
        }
    ]

    for lang in ("en", "hi", "mr"):
        ans, steps, clarify, missing_docs = format_farmer_kcc_answer(
            question="What is the interest rate?",
            supported_results=mock_supported,
            language=lang,
        )
        assert "[1]" in ans, f"Citation [1] missing in {lang} response"
        assert "[2]" not in ans, f"Spurious citation [2] found in {lang} response"
        assert "4%" in ans
        assert "7%" in ans


# -----------------------------------------------------------------------------
# 5. Missing Evidence & Unsupported Application Procedures Safeguards
# -----------------------------------------------------------------------------

def test_missing_application_procedure_explicit_warning():
    """Verify that when application steps are missing from evidence, a clear warning is provided."""
    # Chunk containing ONLY interest rate terms, without application form or documents
    mock_limited_chunk = [
        {
            "cid": 1,
            "text": "Base interest rate is 7% per annum with 1.5% interest subvention. Collateral free limit is Rs 1,60,000.",
            "title": "Interest Subvention Order",
            "url": "https://agricoop.nic.in/subvention",
            "similarity_score": 0.72,
        }
    ]

    ans_en, steps_en, _, missing_docs_en = format_farmer_kcc_answer(
        question="How to apply for KCC?",
        supported_results=mock_limited_chunk,
        language="en",
    )
    assert missing_docs_en is True
    assert "Application Documents Unavailable" in ans_en
    assert "application documents unavailable" in ans_en.lower() or "not provided in current verified records" in ans_en.lower()

    ans_mr, _, _, missing_docs_mr = format_farmer_kcc_answer(
        question="केसीसीसाठी कसा अर्ज करावा?",
        supported_results=mock_limited_chunk,
        language="mr",
    )
    assert missing_docs_mr is True
    assert "नोंदींमध्ये उपलब्ध नाहीत" in ans_mr or "उपलब्ध नाही" in ans_mr


# -----------------------------------------------------------------------------
# 6. Follow-Up Clarifying Questions
# -----------------------------------------------------------------------------

def test_clarifying_question_behavior():
    """Verify clarifying question is generated only when critical information is missing."""
    # Short vague KCC query missing tenure
    q_short = "How to get KCC loan?"
    clarify_en = get_clarifying_question(q_short, "farmer", "en")
    assert clarify_en is not None
    assert "owner cultivator or tenant farmer" in clarify_en.lower()

    clarify_hi = get_clarifying_question(q_short, "farmer", "hi")
    assert clarify_hi is not None
    assert "बटाईदार" in clarify_hi or "भूमि" in clarify_hi

    clarify_mr = get_clarifying_question(q_short, "farmer", "mr")
    assert clarify_mr is not None
    assert "भाडेकरू" in clarify_mr or "जमिनीवर" in clarify_mr

    # Specific KCC query that ALREADY specifies land tenure: should NOT ask unnecessary clarification
    q_complete = "How can a tenant farmer apply for Kisan Credit Card with self-declaration?"
    assert get_clarifying_question(q_complete, "farmer", "en") is None

    # Pest query missing crop name
    q_pest = "How to control stem borer?"
    clarify_pest = get_clarifying_question(q_pest, "pest_management", "en")
    assert clarify_pest is not None
    assert "which crop" in clarify_pest.lower()

    # Pest query WITH crop name specified
    q_pest_complete = "How to control stem borer in paddy crop using pheromone traps?"
    assert get_clarifying_question(q_pest_complete, "pest_management", "en") is None


# -----------------------------------------------------------------------------
# 7. Preservation of Relevance Threshold (0.25)
# -----------------------------------------------------------------------------

def test_relevance_threshold_is_strictly_preserved():
    """Verify that retrieval relevance threshold remains 0.25 in configuration."""
    assert RELEVANCE_THRESHOLD == 0.25


def test_insufficient_evidence_when_similarity_below_threshold(client):
    """Verify that completely ungrounded query returns insufficient_evidence."""
    res = client.post(
        "/research",
        json={"question": "What is the policy for deep sea geothermal space mining subsidies?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("insufficient_evidence", "out_of_scope")


# -----------------------------------------------------------------------------
# 8. Out-of-Scope Rejection in Multilingual Context
# -----------------------------------------------------------------------------

def test_multilingual_out_of_scope_rejection(client):
    """Verify out-of-scope rejection for non-agricultural/non-government queries."""
    # English
    res_en = client.post("/research", json={"question": "Write a python script for sorting binary trees"})
    assert res_en.status_code == 200
    assert res_en.json()["status"] == "out_of_scope"

    # Hindi out of scope
    res_hi = client.post("/research", json={"question": "क्रिकेट विश्व कप 2023 किसने जीता?"})
    assert res_hi.status_code == 200
    assert res_hi.json()["status"] == "out_of_scope"

    # Marathi out of scope
    res_mr = client.post("/research", json={"question": "चित्रपटाचे तिकीट कसे बुक करावे?"})
    assert res_mr.status_code == 200
    assert res_mr.json()["status"] == "out_of_scope"


# -----------------------------------------------------------------------------
# 9. Devanagari Category Routing
# -----------------------------------------------------------------------------

def test_devanagari_category_routing():
    """Verify heuristic classification routes Devanagari queries to proper categories."""
    assert heuristic_classify("7/12 उतारा आणि जमिनीचा दाखला").category == "farmer_questions"
    assert heuristic_classify("युरिया आणि डीएपी खतांचा वापर").category == "fertilizers"
    assert heuristic_classify("कपाशीवरील बोंडअळी नियंत्रण").category == "pest_management"
    assert heuristic_classify("गव्हावरील पिवळेपणा कसा रोखावा").category == "crop_problems"
    assert heuristic_classify("नमो शेतकरी महासन्मान निधी योजना हप्ता").category == "government_schemes"


# -----------------------------------------------------------------------------
# 10. Agricultural Advisory Safety & Caution
# -----------------------------------------------------------------------------

def test_agricultural_general_answer_safety():
    """Verify general agricultural answers include advisory disclaimers and do not fabricate chemical dosages."""
    mock_results = [
        {
            "cid": 1,
            "text": "For Fall Armyworm in maize, install pheromone traps at 5 per acre. Avoid indiscriminate chemical spraying.",
            "title": "FAW Advisory ICAR",
            "url": "https://icar.org.in/faw",
            "similarity_score": 0.78,
        }
    ]

    ans_en, steps_en, _, _ = format_farmer_general_answer(
        question="How to control armyworm?",
        category="pest_management",
        supported_results=mock_results,
        language="en",
    )
    # Must contain official advisory warning
    assert "Agricultural Advisory & Diagnosis Guidance" in ans_en
    assert "Taluka Agriculture Officer" in ans_en
    assert "Krishi Vigyan Kendra" in ans_en
    # Must not contain unverified toxic chemical concentrations
    assert "500ml per acre monocrotophos" not in ans_en.lower()


# -----------------------------------------------------------------------------
# 11. Application Procedure & Helpline Verification
# -----------------------------------------------------------------------------

def test_kcc_includes_application_procedure_and_helpline(client):
    """Verify that KCC answers across English, Hindi, and Marathi include application steps, documents, and helpline."""
    # English test
    res_en = client.post(
        "/research",
        json={"question": "What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?", "language": "en"},
    )
    assert res_en.status_code == 200
    data_en = res_en.json()
    assert data_en["status"] == "completed"
    assert "Application Procedure & Required Documents" in data_en["answer"]
    assert "Aadhaar Card" in data_en["answer"]
    assert "7/12 extract" in data_en["answer"] or "Record of Rights" in data_en["answer"]
    assert "Commercial Banks, Regional Rural Banks (RRBs), or District Central Cooperative Banks" in data_en["answer"]
    assert "1800-180-1551" in data_en["answer"]
    assert "Where to Get Help & Who to Contact" in data_en["answer"]
    assert data_en["missing_evidence_warning"] is False
    assert any("1800-180-1551" in s for s in data_en["practical_steps"])

    # Hindi test
    res_hi = client.post(
        "/research",
        json={"question": "किसान क्रेडिट कार्ड (KCC) प्राप्त करने की प्रक्रिया क्या है और रियायती ब्याज दर कितनी है?", "language": "hi"},
    )
    assert res_hi.status_code == 200
    data_hi = res_hi.json()
    assert data_hi["status"] == "completed"
    assert "आवेदन की प्रक्रिया और आवश्यक दस्तावेज" in data_hi["answer"]
    assert "आधार कार्ड" in data_hi["answer"]
    assert "7/12" in data_hi["answer"] or "खतौनी" in data_hi["answer"]
    assert "1800-180-1551" in data_hi["answer"]
    assert "कहाँ से मदद लें और किससे संपर्क करें" in data_hi["answer"]
    assert data_hi["missing_evidence_warning"] is False

    # Marathi test
    res_mr = client.post(
        "/research",
        json={"question": "किसान क्रेडिट कार्ड (KCC) मिळविण्याची पद्धत काय आहे आणि सवलतीचा व्याजदर किती आहे?", "language": "mr"},
    )
    assert res_mr.status_code == 200
    data_mr = res_mr.json()
    assert data_mr["status"] == "completed"
    assert "अर्ज कसा करावा आणि लागणारी कागदपत्रे" in data_mr["answer"]
    assert "आधार कार्ड" in data_mr["answer"]
    assert "7/12 उतारा" in data_mr["answer"]
    assert "1800-180-1551" in data_mr["answer"]
    assert "मदत आणि संपर्कासाठी माहिती" in data_mr["answer"]
    assert data_mr["missing_evidence_warning"] is False

