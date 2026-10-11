"""Tests for Step 5: Official Government Data Source Integration."""
import hashlib
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.sources.config import (
    OFFICIAL_GOVERNMENT_DOMAINS,
    SUPPORTED_CATEGORIES,
    is_official_government_url,
)
from app.sources.data_gov import check_api_key, fetch_data_gov_resource
from app.sources.pdf_collector import clean_pdf_text, collect_pdf, extract_pdf_from_bytes
from app.sources.pipeline import (
    compute_content_hash,
    ensure_metadata_compliance,
    ingest_source,
)
from app.sources.source_registry import SourceConfig, registry
from app.sources.website_collector import clean_html_content, collect_webpage


def test_source_config_supported_categories():
    """Verify strictly supported initial categories and exclusion of unindexed categories."""
    expected = [
        "government_schemes",
        "agriculture",
        "crop_problems",
        "pest_management",
        "fertilizers",
        "farmer_questions",
    ]
    assert set(SUPPORTED_CATEGORIES) == set(expected)
    assert "jobs" not in SUPPORTED_CATEGORIES
    assert "health" not in SUPPORTED_CATEGORIES
    assert "tax" not in SUPPORTED_CATEGORIES
    assert "passport" not in SUPPORTED_CATEGORIES


def test_is_official_government_url():
    """Verify that only approved official government domains are permitted."""
    assert is_official_government_url("https://data.gov.in/resource/123")
    assert is_official_government_url("https://api.data.gov.in/resource/456")
    assert is_official_government_url("https://india.gov.in/topics/agriculture")
    assert is_official_government_url("https://services.india.gov.in/service/detail")
    assert is_official_government_url("https://pmkisan.gov.in/guidelines.aspx")
    assert is_official_government_url("https://agricoop.nic.in/en")
    assert is_official_government_url("https://soilhealth.dac.gov.in/")
    assert is_official_government_url("https://icar.org.in/node/100")
    assert is_official_government_url("https://cibrc.gov.in/approved")

    # Non-government and deceptive domains must be rejected
    assert not is_official_government_url("https://google.com")
    assert not is_official_government_url("https://attacker-gov.in.com")
    assert not is_official_government_url("https://data.gov.in.attacker.org")
    assert not is_official_government_url("https://192.168.1.1")
    assert not is_official_government_url("")


def test_data_gov_unconfigured_api_key():
    """Verify that when DATA_GOV_API_KEY is missing, no fake data is generated."""
    with patch("app.sources.data_gov.get_api_key", return_value=""):
        has_key, msg = check_api_key()
        assert not has_key
        assert "DATA_GOV_API_KEY is not configured" in msg

        res = fetch_data_gov_resource(
            resource_id="sample-resource-123",
            title="Sample Catalog",
            department="Department of Agriculture",
            category="agriculture",
        )
        assert res["status"] == "unconfigured"
        assert res["documents"] == []
        assert "DATA_GOV_API_KEY is not configured" in res["message"]


def test_data_gov_configured_response_mock():
    """Verify data.gov.in formatting and metadata attachment when API key is provided."""
    mock_json = {
        "records": [
            {"scheme": "PM-KISAN", "state": "All India", "installment": "Rs. 2000"},
            {"scheme": "PMFBY", "state": "All India", "coverage": "Crop Insurance"},
        ],
        "updated_date": "2026-01-10",
    }
    with patch("app.sources.data_gov.get_api_key", return_value="real-test-api-key"):
        with patch("httpx.Client.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_json
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            res = fetch_data_gov_resource(
                resource_id="sample-resource-123",
                title="Agricultural Schemes Summary",
                department="Ministry of Agriculture & Farmers Welfare",
                category="government_schemes",
            )
            assert res["status"] == "success"
            assert len(res["documents"]) == 1
            doc = res["documents"][0]
            assert "PM-KISAN" in doc.page_content
            assert "PMFBY" in doc.page_content

            # Check 8 required metadata attributes
            meta = doc.metadata
            assert meta["source_name"] == "data.gov.in"
            assert "https://data.gov.in/resource/sample-resource-123" in meta["source_url"]
            assert meta["category"] == "government_schemes"
            assert meta["department"] == "Ministry of Agriculture & Farmers Welfare"
            assert meta["title"] == "Agricultural Schemes Summary"
            assert meta["document_type"] == "api"
            assert "last_checked" in meta
            assert "last_updated" in meta
            assert "content_hash" in meta


def test_website_collector_html_cleaning():
    """Verify HTML cleaning strips navigation/footers and preserves core text."""
    sample_html = """
    <!DOCTYPE html>
    <html>
      <head><title>Pradhan Mantri Fasal Bima Yojana - Official Guidelines</title></head>
      <body>
        <nav><a href="/home">Home</a><a href="/login">Login</a></nav>
        <header><h1>Header Banner</h1></header>
        <main>
          <h2>Scheme Overview</h2>
          <p>PMFBY provides comprehensive crop insurance against non-preventable natural risks.</p>
          <p>Premium rate for Kharif crops is 2%, for Rabi crops is 1.5%.</p>
        </main>
        <aside>Related Links</aside>
        <footer>Copyright 2026 Ministry of Agriculture. All rights reserved.</footer>
        <script>console.log('tracking');</script>
      </body>
    </html>
    """
    title, clean_text = clean_html_content(sample_html)
    assert title == "Pradhan Mantri Fasal Bima Yojana - Official Guidelines"
    assert "Scheme Overview" in clean_text
    assert "PMFBY provides comprehensive crop insurance" in clean_text
    assert "Premium rate for Kharif crops is 2%" in clean_text

    # Unwanted noise must be completely absent
    assert "Home" not in clean_text
    assert "Login" not in clean_text
    assert "Header Banner" not in clean_text
    assert "Related Links" not in clean_text
    assert "All rights reserved" not in clean_text
    assert "tracking" not in clean_text


def test_website_collector_domain_rejection():
    """Verify website collector rejects unauthorized non-government domains."""
    doc = collect_webpage(
        "https://random-commercial-blog.com/schemes",
        meta={"title": "Unauthorized"},
    )
    assert doc is None


def test_pdf_collector_clean_text():
    """Verify PDF cleaner removes excessive whitespace and control characters."""
    raw = "Pradhan  Mantri\x00\x0c  Kisan\n\n\n\nSamman   Nidhi"
    cleaned = clean_pdf_text(raw)
    assert cleaned == "Pradhan Mantri Kisan\n\nSamman Nidhi"


def test_pdf_collector_local_file():
    """Verify PDF extraction on local official guideline PDF."""
    local_pdf = "data/raw/1ed42b58950974e5.pdf"
    docs = collect_pdf(
        local_pdf,
        meta={
            "source_name": "PM-KISAN Guidelines",
            "title": "PM-KISAN Operational Guidelines",
            "department": "Ministry of Agriculture & Farmers Welfare",
            "category": "government_schemes",
            "publication_date": "2020-03-29",
            "updated_date": "2025-01-15",
        },
    )
    assert len(docs) > 0
    assert "PM-KISAN" in docs[0].page_content or "PRADHAN MANTRI" in docs[0].page_content

    first_meta = docs[0].metadata
    # Check all 8 required metadata attributes
    assert first_meta["source_name"] == "PM-KISAN Guidelines"
    assert "source_url" in first_meta
    assert first_meta["category"] == "government_schemes"
    assert first_meta["department"] == "Ministry of Agriculture & Farmers Welfare"
    assert first_meta["title"] == "PM-KISAN Operational Guidelines"
    assert first_meta["document_type"] == "pdf"
    assert "last_checked" in first_meta
    assert "last_updated" in first_meta
    assert "content_hash" in first_meta
    assert len(first_meta["content_hash"]) == 64  # SHA-256


def test_source_registry_validation():
    """Verify SourceRegistry configuration and category validation."""
    sources = registry.list_sources()
    assert len(sources) >= 5

    # Check each registered source has valid categories and attributes
    for s in sources:
        assert s.category in SUPPORTED_CATEGORIES
        assert s.source_type in {"api", "website", "pdf"}
        assert s.source_name
        assert s.source_url
        assert s.department

    # Invalid category must raise ValueError
    try:
        SourceConfig(
            source_name="Invalid Source",
            source_url="https://passport.gov.in",
            source_type="website",
            department="CPV Division",
            category="passport",  # Not in supported 6 categories
        )
        assert False, "Should have raised ValueError for unsupported category"
    except ValueError:
        pass


def test_pipeline_metadata_compliance():
    """Verify that ensure_metadata_compliance guarantees all 8 mandatory fields."""
    src = SourceConfig(
        source_name="Test Source",
        source_url="https://agricoop.nic.in/test",
        source_type="website",
        department="Ministry of Agriculture",
        category="agriculture",
        title="Test Agricultural Advisory",
        publication_date="2025-01-15",
    )
    sample_doc = Document(page_content="Sample advisory text content.")
    content_hash = compute_content_hash(sample_doc.page_content)

    compliant_docs = ensure_metadata_compliance([sample_doc], src, content_hash)
    meta = compliant_docs[0].metadata

    required_fields = [
        "source_name",
        "source_url",
        "category",
        "department",
        "title",
        "document_type",
        "last_checked",
        "last_updated",
    ]
    for rf in required_fields:
        assert rf in meta, f"Missing required metadata field: {rf}"
        assert meta[rf], f"Field {rf} must not be empty"


def test_duplicate_change_detection_logic():
    """Verify SHA-256 hash detection: Same -> Skip, Changed -> Re-index, New -> Add."""
    text1 = "Official Scheme Guidelines version 1.0"
    text2 = "Official Scheme Guidelines version 1.0"
    text3 = "Official Scheme Guidelines version 2.0 (Updated Budget Allocations)"

    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    hash3 = compute_content_hash(text3)

    assert hash1 == hash2  # Same content -> hash matches -> UNCHANGED
    assert hash1 != hash3  # Changed content -> hash differs -> UPDATED
    assert len(hash1) == 64
