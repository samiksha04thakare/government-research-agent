"""Comprehensive Tests for Government Scheme Deduplication, Pagination, and Search Integrity.

Tests all required scenarios:
1. Duplicate scheme records in the database (with different IDs and name variations).
2. Similar scheme names that genuinely belong to different schemes (e.g. PMAY-G vs PMAY-U, KUSUM-A vs KUSUM-B).
3. Multiple pages of search results (disjoint items, non-overlapping scheme IDs across pages).
4. Empty search results (no false positive items, correct 0 counts).
5. Search filters combined with pagination (category / state filters + page offsets).
6. Total result counts accurately reflect unique schemes after deduplication.
7. Existing government scheme search and RAG functionality integration.
"""
import pytest
from fastapi.testclient import TestClient

from app.database.db import Scheme, SessionLocal, init_db
from app.main import app
from app.schemes.normalizer import (
    get_canonical_scheme_id,
    are_schemes_equivalent,
    normalize_scheme_name,
)
from app.schemes.pipeline import (
    find_matching_scheme_for_query,
    ingest_scheme_to_db,
    search_schemes_in_db,
    seed_official_schemes,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db_seeded():
    """Ensure DB has base official schemes and valid schema."""
    init_db()
    with SessionLocal() as db:
        if db.query(Scheme).count() < 12:
            seed_official_schemes(db=db)
    yield


# ==============================================================================
# 1. DUPLICATE SCHEME RECORDS IN THE DATABASE
# ==============================================================================
def test_duplicate_records_with_different_ids_are_deduplicated():
    """Test that multiple records representing the same scheme with different IDs are deduplicated."""
    with SessionLocal() as db:
        initial_unique = len(search_schemes_in_db(db=db))
        initial_raw = db.query(Scheme).count()

        # Inject 2 duplicate variants of PM-KISAN with different IDs and slight name variations
        dup1 = Scheme(
            scheme_id="PM-KISAN",
            scheme_name="Pradhan Mantri Kisan Samman Nidhi",  # Missing (PM-KISAN) suffix
            hindi_name="प्रधानमंत्री किसान सम्मान निधि",
            category="Agriculture & Farmer Welfare",
            beneficiary="Farmers",
            eligibility="Landholders",
            benefits="Rs 6,000",
            documents="Aadhaar",
            state_district="Central / All India",
            status="Active",
        )
        dup2 = Scheme(
            scheme_id=None,  # Null scheme_id to test dynamic resolution
            scheme_name="PM-KISAN Scheme",
            hindi_name="पीएम-किसान योजना",
            category="Agriculture & Farmer Welfare",
            beneficiary="Farmers",
            eligibility="Landholders",
            benefits="Rs 6000 DBT",
            documents="Aadhaar, Land records",
            state_district="Central / All India",
            status="Active",
        )
        db.add_all([dup1, dup2])
        db.commit()

        try:
            assert db.query(Scheme).count() == initial_raw + 2

            # Search without query
            results = search_schemes_in_db(db=db)
            pm_kisan_instances = [s for s in results if s.scheme_id == "PM-KISAN" or "PM-KISAN" in s.scheme_name]
            assert len(pm_kisan_instances) == 1, "Duplicate PM-KISAN records leaked into search results"
            assert len(results) == initial_unique, "Unique scheme count increased despite duplicate injection"

            # Search with specific query
            query_results = search_schemes_in_db(query="kisan samman", db=db)
            pm_matches = [s for s in query_results if s.scheme_id == "PM-KISAN" or "PM-KISAN" in s.scheme_name]
            assert len(pm_matches) == 1, "Duplicate PM-KISAN records returned for search query"
        finally:
            db.delete(dup1)
            db.delete(dup2)
            db.commit()


def test_ingestion_upsert_prevents_duplicate_insertion():
    """Test that ingest_scheme_to_db updates existing schemes instead of inserting duplicates."""
    with SessionLocal() as db:
        initial_count = db.query(Scheme).count()

        # Attempt to ingest an existing scheme with slightly different name
        updated = ingest_scheme_to_db({
            "scheme_name": "Kisan Credit Card (KCC)",
            "hindi_name": "किसान क्रेडिट कार्ड",
            "category": "Agricultural Credit & Finance",
            "beneficiary": "All Farmers",
            "eligibility": "Cultivators and tenant farmers",
            "benefits": "Short-term production credit up to ₹3,00,000 at 4%",
            "documents": "Aadhaar Card, 7/12 RoR",
            "state_district": "Central / All India",
            "status": "Active",
            "official_source_url": "https://agricoop.nic.in",
        }, db=db)

        # Count should remain the same
        assert db.query(Scheme).count() == initial_count
        assert updated.scheme_id == "KCC"


# ==============================================================================
# 2. SIMILAR SCHEME NAMES THAT BELONG TO DIFFERENT SCHEMES
# ==============================================================================
def test_genuinely_different_schemes_with_similar_names_are_preserved():
    """Verify that schemes with similar names (e.g., PMAY-G vs PMAY-U) are NOT accidentally deduplicated."""
    with SessionLocal() as db:
        pmay_u = Scheme(
            scheme_id="PMAY-U",
            scheme_name="Pradhan Mantri Awas Yojana - Urban (PMAY-U)",
            hindi_name="प्रधानमंत्री आवास योजना - शहरी (पीएमएवाई-यू)",
            category="Housing & Urban Affairs",
            beneficiary="Urban economically weaker sections and low-income groups",
            eligibility="Urban families without pucca house across all statutory towns",
            benefits="Interest subsidy up to ₹2.67 lakh under Credit Linked Subsidy Scheme",
            documents="Aadhaar Card, Bank Account, Urban Domicile",
            state_district="Central / All India",
            status="Active",
        )
        db.add(pmay_u)
        db.commit()

        try:
            results = search_schemes_in_db(query="Awas Yojana", db=db)
            scheme_ids = [s.scheme_id for s in results]
            assert "PMAY-G" in scheme_ids, "PMAY-G was missing from search results"
            assert "PMAY-U" in scheme_ids, "PMAY-U was erroneously removed or conflated with PMAY-G"
        finally:
            db.delete(pmay_u)
            db.commit()


def test_women_and_child_schemes_remain_distinct():
    """Verify Mukhyamantri Majhi Ladki Bahin and Lek Ladki Yojana are not conflated."""
    with SessionLocal() as db:
        results = search_schemes_in_db(category="Women", db=db)
        ids = [s.scheme_id for s in results]
        assert "MH-WOM-01" in ids, "Majhi Ladki Bahin (MH-WOM-01) missing"
        assert "MH-WOM-02" in ids, "Lek Ladki (MH-WOM-02) missing"


# ==============================================================================
# 3. MULTIPLE PAGES OF SEARCH RESULTS (PAGINATION)
# ==============================================================================
def test_pagination_disjoint_pages_and_no_duplicates():
    """Verify schemes do not reappear across pages and page counts are consistent."""
    res_p1 = client.get("/schemes?page=1&page_size=5")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["page"] == 1
    assert data_p1["page_size"] == 5
    assert len(data_p1["items"]) == 5

    res_p2 = client.get("/schemes?page=2&page_size=5")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert data_p2["page"] == 2
    assert len(data_p2["items"]) == 5

    res_p3 = client.get("/schemes?page=3&page_size=5")
    assert res_p3.status_code == 200
    data_p3 = res_p3.json()
    assert data_p3["page"] == 3

    # Check for zero overlap across pages
    set_p1 = {s["scheme_id"] for s in data_p1["items"]}
    set_p2 = {s["scheme_id"] for s in data_p2["items"]}
    set_p3 = {s["scheme_id"] for s in data_p3["items"]}

    assert len(set_p1.intersection(set_p2)) == 0, "Schemes overlap between page 1 and page 2"
    assert len(set_p1.intersection(set_p3)) == 0, "Schemes overlap between page 1 and page 3"
    assert len(set_p2.intersection(set_p3)) == 0, "Schemes overlap between page 2 and page 3"


def test_pagination_headers_present():
    """Verify HTTP response headers include accurate unique total counts and pages."""
    res = client.get("/schemes?page=1&page_size=10")
    assert res.status_code == 200
    assert "X-Total-Count" in res.headers
    assert "X-Total-Pages" in res.headers
    assert "X-Page" in res.headers
    assert "X-Page-Size" in res.headers

    total_count = int(res.headers["X-Total-Count"])
    total_pages = int(res.headers["X-Total-Pages"])
    assert total_count >= 12
    assert total_pages == (total_count + 10 - 1) // 10


# ==============================================================================
# 4. EMPTY SEARCH RESULTS
# ==============================================================================
def test_empty_search_results_with_pagination():
    """Verify searching for non-existent query returns empty items with accurate pagination."""
    res = client.get("/schemes?q=nonexistentqueryxyz999&page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total_count"] == 0
    assert data["total_pages"] == 1
    assert data["has_next"] is False
    assert data["has_prev"] is False


def test_unpaginated_empty_search():
    """Verify unpaginated empty search returns empty list."""
    res = client.get("/schemes?q=nonexistentqueryxyz999")
    assert res.status_code == 200
    assert res.json() == []


# ==============================================================================
# 5. SEARCH FILTERS COMBINED WITH PAGINATION
# ==============================================================================
def test_category_filter_with_pagination():
    """Verify combining category filters with pagination yields deduplicated, filtered items."""
    res = client.get("/schemes?category=Women&page=1&page_size=4")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 10
    assert len(data["items"]) == 4

    # Every item on the page must belong to Women & Child schemes
    for s in data["items"]:
        cat_lower = s["category"].lower()
        assert s["scheme_id"].startswith("MH-WOM") or any(
            k in cat_lower for k in [
                "women", "child", "girl", "maternity", "shg", "shelter", "nutrition",
                "empowerment", "trafficking", "livelihood", "grievance", "anganwadi", "poshan", "nari", "mahila"
            ]
        )


# ==============================================================================
# 6. TOTAL RESULT COUNTS AFTER DEDUPLICATION
# ==============================================================================
def test_total_result_counts_reflect_unique_schemes():
    """Verify total_count strictly counts unique schemes even if duplicate rows exist."""
    with SessionLocal() as db:
        initial_unique = len(search_schemes_in_db(db=db))

        # Add 3 duplicate rows of KCC
        dups = [
            Scheme(
                scheme_id="KCC",
                scheme_name=f"KCC Loan Variant {i}",
                hindi_name="केसीसी ऋण",
                category="Credit",
                beneficiary="Farmers",
                eligibility="Landholders",
                benefits="4%",
                documents="Aadhaar",
                state_district="Central",
                status="Active",
            )
            for i in range(1, 4)
        ]
        db.add_all(dups)
        db.commit()

        try:
            # Check via API
            res = client.get("/schemes?page=1&page_size=50")
            assert res.status_code == 200
            data = res.json()
            assert data["total_count"] == initial_unique, (
                f"total_count should be {initial_unique} but was {data['total_count']}"
            )
        finally:
            for d in dups:
                db.delete(d)
            db.commit()


# ==============================================================================
# 7. EXISTING SEARCH AND RAG FUNCTIONALITY INTEGRATION
# ==============================================================================
def test_find_matching_scheme_for_query_returns_canonical():
    """Verify research query matching returns the deduplicated canonical scheme."""
    scheme_en = find_matching_scheme_for_query("What is the interest rate for Kisan Credit Card (KCC)?")
    assert scheme_en is not None
    assert scheme_en.scheme_id == "KCC"

    scheme_hi = find_matching_scheme_for_query("पीएम किसान सम्मान निधि में कितने पैसे मिलते हैं?")
    assert scheme_hi is not None
    assert scheme_hi.scheme_id == "PM-KISAN"

    scheme_mr = find_matching_scheme_for_query("माझी लाडकी बहीण योजनेसाठी काय पात्रता आहे?")
    assert scheme_mr is not None
    assert scheme_mr.scheme_id == "MH-WOM-01"


def test_research_endpoint_with_matched_scheme_and_citations():
    """Verify POST /research returns unique matched_scheme with valid citations and no chunk loss."""
    payload = {
        "question": "What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?",
        "language": "en",
    }
    res = client.post("/research", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["matched_scheme"] is not None
    assert data["matched_scheme"]["scheme_id"] == "KCC"
    assert len(data["sources"]) > 0
    assert len(data["retrieved_chunks"]) > 0

    # Ensure citations have no duplicates by ID
    cids = [s["id"] for s in data["sources"]]
    assert len(cids) == len(set(cids)), "Duplicate citation IDs found in sources"
