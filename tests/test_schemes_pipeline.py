"""Unit and Integration Tests for Structured Scheme Ingestion, Normalization, PostgreSQL/SQLite storage, and Hindi Answer Synthesis."""
# pyrefly: ignore[missing-import]
from fastapi.testclient import TestClient

from app.database.db import Scheme, SessionLocal
from app.main import app
from app.schemes.pipeline import (
    extract_structured_scheme,
    extract_text_from_file,
    find_matching_scheme_for_query,
    normalize_text,
    search_schemes_in_db,
    seed_official_schemes,
)

client = TestClient(app)


def test_text_normalization():
    raw_sample = "योजना   का नाम :  \tप्रधानमंत्री  किसान  सम्मान  निधि\n\n\u200bराशि: Rs. 6,000 / वर्ष"
    normalized = normalize_text(raw_sample)
    assert "₹6,000" in normalized
    assert "प्रधानमंत्री किसान सम्मान निधि" in normalized
    assert "\u200b" not in normalized


def test_extract_structured_scheme_from_text():
    sample_text = """
    # Pradhan Mantri Matsya Sampada Yojana
    Hindi Name: प्रधानमंत्री मत्स्य संपदा योजना
    Category: Fisheries & Animal Husbandry
    Beneficiary: Traditional fishers, fish farmers, and SHGs
    Eligibility: Active fishers registered with State Fisheries Department
    Benefits: Subsidized financial assistance of up to 40% to 60% for cage aquaculture and boats
    Documents Required: Aadhaar Card, Fisher Registration Certificate, Bank Passbook
    State/District: Central / All India
    Status: Active
    """
    extracted = extract_structured_scheme(sample_text)
    assert extracted["scheme_name"] == "Pradhan Mantri Matsya Sampada Yojana"
    assert "मत्स्य संपदा" in extracted["hindi_name"]
    assert extracted["category"] == "Fisheries & Animal Husbandry"
    assert "Aadhaar Card" in extracted["documents"]
    assert extracted["status"] == "Active"


def test_schemes_db_and_api():
    # Verify DB has seeded schemes
    seed_official_schemes()
    with SessionLocal() as db:
        count = db.query(Scheme).count()
        assert count >= 12

    # Verify GET /schemes endpoint returns 9-field schema
    res = client.get("/schemes")
    assert res.status_code == 200
    schemes = res.json()
    assert len(schemes) >= 12

    first = schemes[0]
    expected_fields = [
        "scheme_name",
        "hindi_name",
        "category",
        "beneficiary",
        "eligibility",
        "benefits",
        "documents",
        "state_district",
        "status",
    ]
    for f in expected_fields:
        assert f in first, f"Field '{f}' missing from structured scheme"


def test_scheme_search_and_alias_matching():
    # Search in English
    res_en = client.get("/schemes?q=kisan")
    assert res_en.status_code == 200
    assert len(res_en.json()) >= 1

    # Search in Hindi
    res_hi = client.get("/schemes?q=प्रधानमंत्री")
    assert res_hi.status_code == 200
    assert len(res_hi.json()) >= 1

    # Test alias finder
    scheme = find_matching_scheme_for_query("पीएम किसान")
    assert scheme is not None
    assert "PM-KISAN" in scheme.scheme_name or "Kisan" in scheme.scheme_name


def test_research_hindi_output():
    payload = {
        "question": "पीएम किसान योजना में क्या लाभ और दस्तावेज लगते हैं?",
        "language": "hi",
    }
    res = client.post("/research", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("completed", "insufficient_evidence")
    if data["status"] == "completed":
        assert data.get("matched_scheme") is not None
        assert "पीएम-किसान" in data["matched_scheme"]["hindi_name"] or "PM-KISAN" in data["matched_scheme"]["scheme_name"]
        # Hindi answer should contain official scheme overview
        assert ("किसान" in data["answer"] or "पात्रता" in data["answer"] or "दस्तावेज़" in data["answer"])
