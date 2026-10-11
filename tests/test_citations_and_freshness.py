"""Tests for Step 7: Official Citations, Source Links, and Information Freshness.

Verifies:
1. Citation markers ([1], [2]) mapping directly to official source lists.
2. Metadata fidelity: citations use real metadata; never fabricate titles or URLs.
3. Strict distinction between verified check date (last_checked) and official date (last_updated).
4. Missing date handling: explicitly displays 'Official update date not available.' (no date fabrication).
5. Missing / unapproved URL handling: labeled as 'Source URL unavailable on official portal'.
6. Security: rejects arbitrary / spoofed domains; allows only approved official government domains.
7. Conflicting sources & unsupported claims reporting.
8. Insufficient evidence rejection preservation (no hallucinated answers or fake citations).
9. Advisory disclaimer included for official action guidance.
10. API response compatibility with all structured source fields.
"""
import pytest
from fastapi.testclient import TestClient

from app.config import RELEVANCE_THRESHOLD
from app.graph.nodes import cite, insufficient
from app.main import app, local_grounded_research
from app.utils.citations import (
    ADVISORY_DISCLAIMER,
    OFFICIAL_DATE_NOT_AVAILABLE,
    URL_NOT_AVAILABLE,
    build_citations,
    format_citations_markdown,
    is_valid_official_url,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_citation_markers_and_mapping():
    """Verify that evidence items are assigned [cid] markers mapping 1-to-1 to citations."""
    evidence = [
        {
            "text": "PM-KISAN provides Rs 6,000 per year in three installments.",
            "metadata": {
                "title": "PM-KISAN Guidelines",
                "source_url": "https://pmkisan.gov.in/guidelines.aspx",
                "department": "Ministry of Agriculture",
                "page_number": 2,
                "publication_date": "2020-03-29",
                "last_checked": "2026-10-09",
            },
        },
        {
            "text": "Beneficiaries must complete e-KYC and land seeding.",
            "metadata": {
                "title": "PM-KISAN Guidelines",
                "source_url": "https://pmkisan.gov.in/guidelines.aspx",
                "department": "Ministry of Agriculture",
                "page_number": 2,
                "publication_date": "2020-03-29",
                "last_checked": "2026-10-09",
            },
        },
        {
            "text": "Soil Health Card scheme tests 12 parameters.",
            "metadata": {
                "title": "Soil Health Guidelines",
                "source_url": "https://soilhealth.dac.gov.in/guidelines.pdf",
                "department": "Department of Agriculture & Cooperation",
                "page_number": 5,
                "publication_date": "2021-06-15",
                "last_checked": "2026-10-09",
            },
        },
    ]

    citations = build_citations(evidence)

    # First two items share source and page, so they map to [1]; third item maps to [2]
    assert len(citations) == 2
    assert citations[0]["id"] == 1
    assert citations[1]["id"] == 2
    assert evidence[0]["cid"] == 1
    assert evidence[1]["cid"] == 1
    assert evidence[2]["cid"] == 2

    # Formatted markdown must present [1] and [2]
    md = format_citations_markdown(citations)
    assert "[1] **PM-KISAN Guidelines**" in md
    assert "[2] **Soil Health Guidelines**" in md
    assert "(Page 2)" in md
    assert "(Page 5)" in md


def test_metadata_fidelity_no_fabrication():
    """Retrieved metadata must remain intact without fabricated titles, departments, or dates."""
    evidence = [
        {
            "text": "Kisan Credit Card interest subvention is 3% for prompt repayment.",
            "metadata": {
                "title": "Master Circular - Kisan Credit Card (KCC) Scheme",
                "source_url": "https://agricoop.nic.in/kcc-circular.pdf",
                "department": "Reserve Bank of India / MoA&FW",
                "source_name": "RBI KCC Master Circular",
                "category": "government_schemes",
                "document_type": "circular",
                "page_number": 4,
                "publication_date": "2023-04-01",
                "last_checked": "2026-10-08",
            },
        }
    ]

    citations = build_citations(evidence)
    assert len(citations) == 1
    c = citations[0]

    assert c["title"] == "Master Circular - Kisan Credit Card (KCC) Scheme"
    assert c["department"] == "Reserve Bank of India / MoA&FW"
    assert c["url"] == "https://agricoop.nic.in/kcc-circular.pdf"
    assert c["category"] == "government_schemes"
    assert c["document_type"] == "circular"
    assert c["page_number"] == 4
    assert c["last_updated"] == "2023-04-01"
    assert c["last_checked"] == "2026-10-08"
    assert c["has_official_date"] is True


def test_date_distinction_checked_vs_updated():
    """Must strictly distinguish verified check date from official publication/update date."""
    evidence = [
        {
            "text": "SDRF assistance norms for agricultural input subsidy.",
            "metadata": {
                "title": "MHA SDRF Guidelines",
                "source_url": "https://ndmindia.mha.gov.in/sdrf",
                "department": "Ministry of Home Affairs",
                "publication_date": "2015-04-08",  # Historical official publication date
                "last_checked": "2026-10-09",     # Current verification date
            },
        }
    ]

    citations = build_citations(evidence)
    c = citations[0]

    # Verify dates are clearly distinguished
    assert c["last_updated"] == "2015-04-08"
    assert c["last_checked"] == "2026-10-09"
    assert c["last_updated"] != c["last_checked"]

    # Verify formatted markdown reflects both distinctly
    md = format_citations_markdown(citations)
    assert "Official Document Date:** 2015-04-08" in md
    assert "Verified Check Date:** 2026-10-09" in md


def test_missing_official_update_date():
    """When official document date is not provided, must display 'Official update date not available.'"""
    evidence = [
        {
            "text": "Fertilizer control order specifications.",
            "metadata": {
                "title": "Fertilizer (Inorganic, Organic or Mixed) Control Order",
                "source_url": "https://agricoop.nic.in/fco",
                "department": "Department of Agriculture & Farmers Welfare",
                "last_checked": "2026-10-09",
                # publication_date and updated_date intentionally omitted
            },
        }
    ]

    citations = build_citations(evidence)
    c = citations[0]

    assert c["has_official_date"] is False
    assert c["last_updated"] == OFFICIAL_DATE_NOT_AVAILABLE
    assert OFFICIAL_DATE_NOT_AVAILABLE == "Official update date not available."

    md = format_citations_markdown(citations)
    assert "Official Document Date:** Official update date not available." in md


def test_missing_and_invalid_urls():
    """Missing or invalid URLs must be clearly labeled as unavailable without inventing fake URLs."""
    evidence = [
        {
            "text": "Local state circular text.",
            "metadata": {
                "title": "District Crop Advisory Notice",
                "source_url": "",  # Empty URL
                "department": "District Agriculture Office",
                "publication_date": "2025-05-10",
                "last_checked": "2026-10-09",
            },
        },
        {
            "text": "Unverified blog reference.",
            "metadata": {
                "title": "Informal Blog Article",
                "source_url": "https://random-blog.com/schemes",  # Non-government URL
                "department": "Unknown",
                "publication_date": "2025-01-01",
            },
        },
    ]

    citations = build_citations(evidence)
    assert len(citations) == 2

    # First: empty URL
    assert citations[0]["url"] == ""
    assert citations[0]["url_status"] == "unavailable"

    # Second: non-approved URL must be stripped
    assert citations[1]["url"] == ""
    assert citations[1]["url_status"] == "unavailable"

    md = format_citations_markdown(citations)
    assert URL_NOT_AVAILABLE in md
    assert "random-blog.com" not in md  # Never render unverified URLs as trusted links


def test_official_url_security_validation():
    """Verify official URL validator allows valid domains and rejects spoofed / untrusted domains."""
    # Approved official domains
    assert is_valid_official_url("https://data.gov.in/resource/123")
    assert is_valid_official_url("https://pmkisan.gov.in/default.aspx")
    assert is_valid_official_url("https://myscheme.gov.in/schemes/kcc")
    assert is_valid_official_url("https://agricoop.nic.in/guidelines")
    assert is_valid_official_url("https://icar.org.in/node/10")

    # Rejected / spoofed domains
    assert not is_valid_official_url("https://pmkisan.gov.in.attacker.com")
    assert not is_valid_official_url("http://spoofed-nic.in.xyz")
    assert not is_valid_official_url("ftp://data.gov.in")
    assert not is_valid_official_url("javascript:alert(1)")
    assert not is_valid_official_url("not_a_url")
    assert not is_valid_official_url(None)


def test_conflicting_sources_handling():
    """Verify that conflicting sources between retrieved documents are reported clearly."""
    state = {
        "question": "What is the maximum subsidy under Krushi Samrudhi?",
        "draft_answer": "Under Krushi Samrudhi, the maximum subsidy varies according to source.",
        "citations": [
            {
                "id": 1,
                "title": "Krushi Samrudhi Yojana GR 2025",
                "department": "Govt of Maharashtra",
                "url": "https://krishi.maharashtra.gov.in/gr1",
                "last_updated": "2025-03-01",
                "last_checked": "2026-10-09",
            },
            {
                "id": 2,
                "title": "Krushi Samrudhi Yojana Revised Notification 2026",
                "department": "Govt of Maharashtra",
                "url": "https://krishi.maharashtra.gov.in/gr2",
                "last_updated": "2026-02-15",
                "last_checked": "2026-10-09",
            },
        ],
        "conflicts": [
            {
                "topic": "Subsidy Ceiling Limit",
                "source_ids": [1, 2],
                "explanation": "Source [1] states Rs 50,000 whereas newer notification [2] increases limit to Rs 75,000.",
            }
        ],
        "unsupported": [],
    }

    result = cite(state)
    answer = result["final_answer"]

    assert "**Conflicting information found:**" in answer
    assert "Subsidy Ceiling Limit (sources [1, 2]):" in answer
    assert "Source [1] states Rs 50,000" in answer
    assert "[1] **Krushi Samrudhi Yojana GR 2025**" in answer
    assert "[2] **Krushi Samrudhi Yojana Revised Notification 2026**" in answer


def test_unsupported_claims_reporting():
    """Verify that claims that cannot be grounded in retrieved sources are explicitly flagged."""
    state = {
        "question": "Can farmers get free diesel under PM-KISAN?",
        "draft_answer": "PM-KISAN provides income support of Rs 6,000 per year [1].",
        "citations": [
            {
                "id": 1,
                "title": "PM-KISAN Guidelines",
                "department": "MoA&FW",
                "url": "https://pmkisan.gov.in",
                "last_updated": "2024-01-01",
                "last_checked": "2026-10-09",
            }
        ],
        "conflicts": [],
        "unsupported": [
            "Free diesel is not covered under PM-KISAN guidelines and has no verified documentation."
        ],
    }

    result = cite(state)
    answer = result["final_answer"]

    assert "**Could not be verified from the retrieved sources:**" in answer
    assert "Free diesel is not covered under PM-KISAN" in answer


def test_insufficient_evidence_preserves_rejection():
    """Verify strict rejection when evidence is insufficient or below relevance threshold."""
    res = insufficient({"question": "Arbitrary question"})
    assert res["status"] == "insufficient_evidence"
    assert res["citations"] == []
    assert "No sufficiently relevant official information" in res["final_answer"]


def test_advisory_disclaimer_preservation():
    """Verify that official advisory disclaimer is included in formatted citations."""
    citations = [
        {
            "id": 1,
            "title": "Crop Advisory",
            "department": "ICAR",
            "url": "https://icar.org.in",
            "last_updated": "2025-06-01",
            "last_checked": "2026-10-09",
        }
    ]
    md = format_citations_markdown(citations)
    assert ADVISORY_DISCLAIMER in md
    assert "Always confirm the latest scheme guidelines" in md


def test_api_research_endpoint_structured_sources(client):
    """Verify the /research endpoint returns full structured source records with freshness info."""
    response = client.post(
        "/research",
        json={"question": "How can a farmer apply for Kisan Credit Card?"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert len(data["sources"]) > 0
    assert len(data["retrieved_chunks"]) > 0

    first_source = data["sources"][0]
    # Check all structured fields
    assert "id" in first_source
    assert "title" in first_source
    assert "url" in first_source
    assert "url_status" in first_source
    assert "authority" in first_source
    assert "department" in first_source
    assert "last_checked" in first_source
    assert "last_updated" in first_source
    assert "has_official_date" in first_source

    # Citation markers [1], [2] should appear in answer
    assert "[1]" in data["answer"]
    assert "### Official Sources & Information Freshness" in data["answer"]
    assert "Official Document Date:" in data["answer"]
    assert "Verified Check Date:" in data["answer"]
