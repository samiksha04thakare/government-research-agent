"""Regression test suite for Step 7 citation accuracy audit and fixes.

Covers:
1. One-to-one citation marker mapping and elimination of unused sources.
2. Prevention of duplicate or incorrect citation numbering.
3. Preservation of verified source URLs without invented tracking parameters.
4. Flagging inconsistent metadata (dates, authorities, tracking URLs) rather than guessing.
5. Content inspection ensuring actual claims support beyond general farming relevance.
6. KCC grounding: citing only evidence supporting KCC procedures and terms.
7. Strict separation between last_checked and official dates with zero date fabrication.
8. Detection and rejection of unrelated documents and unsupported factual claims.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app, local_grounded_research
from app.utils.citations import (
    OFFICIAL_DATE_NOT_AVAILABLE,
    URL_NOT_AVAILABLE,
    build_citations,
    check_metadata_consistency,
    filter_supported_evidence,
    format_citations_markdown,
    inspect_document_support,
    is_valid_official_url,
    reconcile_citations_with_answer,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_citation_mapping_one_to_one_and_unused_removal():
    """Verify that unused citations are eliminated and markers map 1-to-1."""
    citations = [
        {"id": 1, "title": "Doc A", "url": "https://agricoop.nic.in/a"},
        {"id": 2, "title": "Doc B", "url": "https://agricoop.nic.in/b"},
        {"id": 3, "title": "Doc C", "url": "https://agricoop.nic.in/c"},
    ]
    # Answer only cites source [2]
    answer_text = "Farmers are eligible for concessional credit under guidelines [2]."

    reconciled_text, reconciled_cites = reconcile_citations_with_answer(answer_text, citations)

    # Citation [2] must be renumbered to [1], and Doc A and Doc C must be removed
    assert len(reconciled_cites) == 1
    assert reconciled_cites[0]["id"] == 1
    assert reconciled_cites[0]["title"] == "Doc B"
    assert reconciled_text == "Farmers are eligible for concessional credit under guidelines [1]."


def test_prevent_duplicate_and_incorrect_numbering():
    """Verify non-contiguous markers [1] and [3] are renumbered sequentially to [1] and [2]."""
    citations = [
        {"id": 1, "title": "Doc 1", "url": "https://agricoop.nic.in/1"},
        {"id": 2, "title": "Doc 2", "url": "https://agricoop.nic.in/2"},
        {"id": 3, "title": "Doc 3", "url": "https://agricoop.nic.in/3"},
    ]
    answer_text = "Claim one is grounded in [1]. Claim two is grounded in [3]."

    reconciled_text, reconciled_cites = reconcile_citations_with_answer(answer_text, citations)

    assert len(reconciled_cites) == 2
    assert [c["id"] for c in reconciled_cites] == [1, 2]
    assert reconciled_cites[0]["title"] == "Doc 1"
    assert reconciled_cites[1]["title"] == "Doc 3"
    assert "[1]" in reconciled_text
    assert "[2]" in reconciled_text
    assert "[3]" not in reconciled_text
    assert reconciled_text == "Claim one is grounded in [1]. Claim two is grounded in [2]."


def test_flag_modified_urls_and_tracking_parameters():
    """Verify that URLs with tracking parameters (?utm_source=...) are flagged."""
    meta_dirty = {
        "title": "kisan post scheme",
        "authority": "ministry of agriculture",
        "source_url": "https://pmkisan.gov.in/?utm_source=chatgpt.com",
        "publication_date": "2026-09-15",
    }
    inconsistencies = check_metadata_consistency(meta_dirty)
    assert any("tracking parameters" in inc for inc in inconsistencies)
    assert any("utm_source" in inc for inc in inconsistencies)

    # Clean official URL must not trigger tracking flags
    meta_clean = {
        "title": "PM-KISAN Guidelines",
        "authority": "Ministry of Agriculture",
        "source_url": "https://pmkisan.gov.in/Documents/PM-Kisan_Guidelines.pdf",
        "publication_date": "2020-03-29",
    }
    assert not any("tracking parameters" in inc for inc in check_metadata_consistency(meta_clean))


def test_preserve_source_urls_without_tampering():
    """Verify that build_citations preserves exact verified URLs without adding parameters."""
    evidence = [
        {
            "text": "Guideline text.",
            "metadata": {
                "title": "Credit Guidelines",
                "source_url": "https://agricoop.nic.in/en/divisiontype/agricultural-credit",
                "department": "Ministry of Agriculture",
                "page_number": 1,
            },
        }
    ]
    citations = build_citations(evidence)
    assert len(citations) == 1
    assert citations[0]["url"] == "https://agricoop.nic.in/en/divisiontype/agricultural-credit"
    assert "utm_" not in citations[0]["url"]


def test_flag_inconsistent_dates_publication_later_than_updated():
    """Verify that publication_date later than updated_date is flagged."""
    meta = {
        "title": "Sample Doc",
        "authority": "Ministry of Agriculture",
        "source_url": "https://agricoop.nic.in/doc",
        "publication_date": "2026-09-15",
        "updated_date": "2025-07-01",
    }
    inconsistencies = check_metadata_consistency(meta)
    assert any("later than revision/updated date" in inc for inc in inconsistencies)


def test_strict_separation_of_last_checked_and_no_date_fabrication():
    """Verify that last_checked is never fabricated into an official publication date."""
    evidence = [
        {
            "text": "Procedural text.",
            "metadata": {
                "title": "Advisory Note",
                "source_url": "https://icar.org.in/note",
                "department": "ICAR",
                "last_checked": "2026-10-09",
                # official dates missing
            },
        }
    ]
    citations = build_citations(evidence)
    c = citations[0]

    assert c["has_official_date"] is False
    assert c["last_updated"] == OFFICIAL_DATE_NOT_AVAILABLE
    assert c["publication_date"] == ""
    assert c["last_checked"] == "2026-10-09"
    assert c["last_updated"] != c["last_checked"]


def test_flag_mismatched_authority_and_title():
    """Verify metadata check flags mismatch between Postal Scheme title and Agriculture authority."""
    meta = {
        "title": "kisan post scheme",
        "authority": "ministry of agriculture",
        "department": "ministry of agriculture",
        "source_url": "https://pmkisan.gov.in/?utm_source=chatgpt.com",
    }
    inconsistencies = check_metadata_consistency(meta)
    assert any("Postal Department scheme but authority" in inc for inc in inconsistencies)
    assert any("Postal Department scheme but URL domain" in inc for inc in inconsistencies)


def test_content_inspection_rejects_unrelated_farming_documents_for_kcc():
    """Verify that general farming or PM-KISAN chunks are rejected for KCC queries."""
    query = "How can a farmer apply for Kisan Credit Card?"

    # 1. Authentic KCC Chunk
    kcc_text = (
        "## Section 1: Kisan Credit Card (KCC) Scheme\n"
        "1. Objective: Provide adequate and timely credit support from the banking system.\n"
        "2. Eligibility: All farmers - individuals/joint borrowers who are owner cultivators."
    )
    is_supported, reason = inspect_document_support(query, kcc_text)
    assert is_supported is True
    assert "Supports Kisan Credit Card" in reason

    # 2. PM-KISAN Chunk (relevance to farming alone is not sufficient)
    pmkisan_text = (
        "ii) Timely assistance to the farmers in farm operation\n"
        "iii) A unified e-platform for transferring of cash benefits into farmer's bank account through PFMS integration."
    )
    is_supported, reason = inspect_document_support(query, pmkisan_text)
    assert is_supported is False
    assert "PM-KISAN" in reason

    # 3. Fertilizer / Soil Health Chunk
    soil_text = "Soil Health Card 12 Parameters test N, P, K, and micronutrients."
    is_supported, reason = inspect_document_support(query, soil_text)
    assert is_supported is False

    # 4. Cotton Pest Chunk
    pest_text = "Pink Bollworm in Bt Cotton symptoms and neem spray recommendations."
    is_supported, reason = inspect_document_support(query, pest_text)
    assert is_supported is False


def test_kcc_query_cites_only_evidence_supporting_kcc(client):
    """End-to-end verification: KCC question cites ONLY authentic KCC guidelines with 1-to-1 mapping."""
    response = client.post(
        "/research",
        json={"question": "How can a farmer apply for Kisan Credit Card?"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    # Must only cite the authentic KCC guidelines, rejecting PM-KISAN and contaminated post scheme
    assert len(data["sources"]) == 1

    kcc_source = data["sources"][0]
    assert kcc_source["id"] == 1
    assert kcc_source["title"] == "Farmer Welfare, Land Records & Agricultural Credit Guidelines"
    assert kcc_source["url"] == "https://agricoop.nic.in/en/divisiontype/agricultural-credit"
    assert "utm_" not in kcc_source["url"]
    assert kcc_source["has_official_date"] is True
    assert kcc_source["publication_date"] == "2025-01-15"
    assert kcc_source["last_updated"] == "2025-07-01"

    # Answer must include marker [1] and NO [2]
    assert "[1]" in data["answer"]
    assert "[2]" not in data["answer"]
    assert "kisan post scheme" not in data["answer"].lower()
    assert "Kisan Credit Card (KCC) Scheme Overview" in data["answer"]
    assert "Effective Interest Rate" in data["answer"]


def test_kcc_insufficient_evidence_when_no_kcc_documents_support():
    """When only unrelated farming documents are retrieved, return insufficient evidence."""
    unrelated_evidence = [
        {
            "text": "PM-KISAN cash transfer of Rs 6,000 per year via PFMS integration.",
            "similarity_score": 0.45,
            "metadata": {
                "title": "PM-KISAN Guidelines",
                "source_url": "https://pmkisan.gov.in",
                "department": "Ministry of Agriculture",
            },
        },
        {
            "text": "Cotton pink bollworm pest spray with neem 10000 ppm.",
            "similarity_score": 0.35,
            "metadata": {
                "title": "IPM Guidelines",
                "source_url": "https://cibrc.gov.in",
                "department": "CIBRC",
            },
        },
    ]

    supported, rejected = filter_supported_evidence(
        "What is the interest subvention rate for Kisan Credit Card?",
        unrelated_evidence,
    )
    assert len(supported) == 0
    assert len(rejected) == 2


def test_unsupported_factual_claims_detected():
    """Verify that factual claims not grounded in sources are flagged."""
    from app.graph.nodes import cite

    state = {
        "question": "Does KCC provide free agricultural tractors?",
        "draft_answer": "Under KCC, farmers receive credit support for seasonal crop operations [1].",
        "citations": [
            {
                "id": 1,
                "title": "KCC Guidelines",
                "department": "MoA&FW",
                "url": "https://agricoop.nic.in/kcc",
                "last_updated": "2025-01-15",
                "last_checked": "2026-10-09",
            }
        ],
        "conflicts": [],
        "unsupported": [
            "Free agricultural tractors are not provided under KCC guidelines."
        ],
    }

    result = cite(state)
    assert "**Could not be verified from the retrieved sources:**" in result["final_answer"]
    assert "Free agricultural tractors are not provided" in result["final_answer"]


def test_compound_and_adjacent_citation_marker_reconciliation():
    """Verify compound markers [1, 3] and adjacent duplicates [1][1] are cleanly remapped and normalized."""
    citations = [
        {"id": 1, "title": "Doc 1", "url": "https://agricoop.nic.in/1"},
        {"id": 2, "title": "Doc 2", "url": "https://agricoop.nic.in/2"},
        {"id": 3, "title": "Doc 3", "url": "https://agricoop.nic.in/3"},
    ]
    # Doc 2 is unused. Doc 1 and Doc 3 are cited in compound [1, 3] and adjacent [1][1]
    raw_text = "Eligibility is established [1, 3]. Credit guidelines confirm terms [1][1]."

    reconciled_text, reconciled_cites = reconcile_citations_with_answer(raw_text, citations)

    assert len(reconciled_cites) == 2
    assert [c["id"] for c in reconciled_cites] == [1, 2]
    assert reconciled_cites[0]["title"] == "Doc 1"
    assert reconciled_cites[1]["title"] == "Doc 3"
    assert "[1, 2]" in reconciled_text
    assert "[1]" in reconciled_text
    assert "[1][1]" not in reconciled_text


def test_unmapped_citation_marker_cleanup():
    """Verify that markers pointing to non-existent source IDs are stripped cleanly."""
    citations = [
        {"id": 1, "title": "Doc 1", "url": "https://agricoop.nic.in/1"},
    ]
    raw_text = "Valid claim grounded here [1]. Hallucinated citation marker [99] must be removed."

    reconciled_text, reconciled_cites = reconcile_citations_with_answer(raw_text, citations)

    assert len(reconciled_cites) == 1
    assert "[1]" in reconciled_text
    assert "[99]" not in reconciled_text
    assert "Hallucinated citation marker must be removed." in reconciled_text


def test_flag_invalid_date_formats():
    """Verify metadata checker flags non-ISO and calendar-invalid date strings."""
    meta_bad_month = {
        "title": "Bad Month Doc",
        "authority": "MoA&FW",
        "source_url": "https://agricoop.nic.in/doc",
        "publication_date": "2025-99-01",
    }
    inconsistencies = check_metadata_consistency(meta_bad_month)
    assert any("invalid date format or calendar value" in inc for inc in inconsistencies)

    meta_bad_format = {
        "title": "Bad Format Doc",
        "authority": "MoA&FW",
        "source_url": "https://agricoop.nic.in/doc",
        "updated_date": "not-a-date",
    }
    assert any("invalid date format or calendar value" in inc for inc in check_metadata_consistency(meta_bad_format))


def test_flag_document_type_extension_mismatch():
    """Verify that metadata checker flags mismatched document types and URL extensions."""
    meta = {
        "title": "Guidelines",
        "authority": "MoA&FW",
        "source_url": "https://agricoop.nic.in/guidelines.txt",
        "document_type": "pdf",
    }
    inconsistencies = check_metadata_consistency(meta)
    assert any("Document type 'pdf' conflicts with source URL extension" in inc for inc in inconsistencies)


def test_flag_checked_date_earlier_than_publication():
    """Verify that a check date earlier than publication date is flagged as inconsistent."""
    meta = {
        "title": "Future Guideline",
        "authority": "MoA&FW",
        "source_url": "https://agricoop.nic.in/doc",
        "publication_date": "2025-06-01",
        "last_checked": "2024-01-15",
    }
    inconsistencies = check_metadata_consistency(meta)
    assert any("earlier than document publication date" in inc for inc in inconsistencies)


def test_exact_chunk_tracing_for_all_kcc_answer_claims(client):
    """Verify that every section in the KCC answer can be traced back to text in retrieved_chunks."""
    response = client.post(
        "/research",
        json={"question": "How can a farmer apply for Kisan Credit Card?"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert len(data["sources"]) == 1
    assert len(data["retrieved_chunks"]) >= 1

    combined_chunk_text = "\n".join(c["text"] for c in data["retrieved_chunks"]).lower()

    # If the answer claims eligibility, it must exist in retrieved chunks
    if "Eligibility Criteria" in data["answer"]:
        assert "owner cultivators" in combined_chunk_text

    # If the answer claims interest rate terms, it must exist in retrieved chunks
    if "Interest Rates" in data["answer"]:
        assert "7%" in combined_chunk_text
        assert "subvention" in combined_chunk_text

    # If the answer claims application documents, it must exist in retrieved chunks
    if "Application Procedure" in data["answer"]:
        assert "documents required" in combined_chunk_text or "record of rights" in combined_chunk_text

    # Verify no ungrounded claims about tractors or free diesel appear
    assert "tractor" not in data["answer"].lower()
    assert "diesel" not in data["answer"].lower()


def test_reject_unrelated_farming_documents_even_with_high_scores():
    """Verify that unrelated agricultural chunks (fertilizer, pests, PM-KISAN) are rejected for KCC."""
    evidence = [
        {
            "text": "Fertilizer subsidy per bag under NBS policy for DAP and Urea.",
            "similarity_score": 0.48,
            "metadata": {"title": "Fertilizer Guidelines", "department": "Department of Fertilizers"},
        },
        {
            "text": "Bt cotton bollworm IPM chemical spray advisory.",
            "similarity_score": 0.42,
            "metadata": {"title": "CIBRC Advisory", "department": "CIBRC"},
        },
        {
            "text": "PM-KISAN direct cash transfer of Rs 2000 per installment.",
            "similarity_score": 0.45,
            "metadata": {"title": "PM-KISAN Guidelines", "department": "MoA&FW"},
        },
    ]

    supported, rejected = filter_supported_evidence(
        "What are the eligibility norms for Kisan Credit Card?",
        evidence,
        category="government_schemes",
    )
    assert len(supported) == 0
    assert len(rejected) == 3
    reasons = [r["rejection_reason"] for r in rejected]
    assert any("fertilizer" in r.lower() for r in reasons)
    assert any("crop pest" in r.lower() for r in reasons)
    assert any("pm-kisan" in r.lower() for r in reasons)

