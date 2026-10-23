import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import GROQ_BASE_URL, GROQ_MODEL
from app.llm.model import (
    get_llm,
    mask_api_key,
    normalize_groq_base_url,
    parse_groq_exception,
    test_groq_connection as check_groq_connection,
)
from app.main import app


def test_groq_configuration_defaults():
    assert GROQ_BASE_URL == "https://api.groq.com/openai/v1"
    assert GROQ_MODEL == "llama-3.3-70b-versatile"
    assert normalize_groq_base_url("https://api.groq.com/openai/v1") == "https://api.groq.com"
    assert normalize_groq_base_url("https://api.groq.com/openai/v1/") == "https://api.groq.com"
    assert normalize_groq_base_url("https://api.groq.com") == "https://api.groq.com"
    assert normalize_groq_base_url(None) == "https://api.groq.com"


def test_groq_key_masking():
    assert mask_api_key("") == ""
    assert mask_api_key(None) == ""
    assert mask_api_key("short") == "gsk_***"
    masked = mask_api_key("gsk_1234567890abcdef1234567890")
    assert masked.startswith("gsk_")
    assert masked.endswith("7890")
    assert "abcdef" not in masked


def test_parse_groq_exceptions():
    err_auth = parse_groq_exception(Exception("Error code: 401 - Invalid API Key"))
    assert err_auth["error_type"] == "authentication_error"
    assert err_auth["status_code"] == 401

    err_rate = parse_groq_exception(Exception("Error code: 429 - Rate limit reached"))
    assert err_rate["error_type"] == "rate_limit_error"
    assert err_rate["status_code"] == 429

    err_timeout = parse_groq_exception(Exception("Request timed out after 30 seconds"))
    assert err_timeout["error_type"] == "timeout_error"
    assert err_timeout["status_code"] == 504

    err_conn = parse_groq_exception(Exception("Failed to establish a connection"))
    assert err_conn["error_type"] == "connection_error"
    assert err_conn["status_code"] == 502


def test_groq_connection_missing_key():
    diag = check_groq_connection(api_key="gsk_your_groq_key_here")
    assert diag["success"] is False
    assert diag["error_type"] == "missing_api_key"
    assert "No valid GROQ_API_KEY configured" in diag["message"]
    # Verify no secret leaked
    assert "gsk_your_groq_key_here" not in str(diag)


def test_groq_connection_invalid_key():
    diag = check_groq_connection(api_key="gsk_invalid_test_key_0987654321")
    assert diag["success"] is False
    assert diag["error_type"] in ("authentication_error", "connection_error")
    # Verify masked key
    assert "masked_key" in diag
    assert diag["masked_key"] == "gsk_...4321"
    assert "0987654321" not in diag["masked_key"]


def test_health_endpoint_reports_groq_config():
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "llm_model" in data
    assert "llm_provider" in data
    assert data["groq_base_url"] == "https://api.groq.com/openai/v1"
    # Ensure no API keys exist anywhere in payload
    assert "gsk_" not in str(data)
    assert "api_key" not in data


def test_test_llm_endpoint():
    client = TestClient(app)
    res = client.get("/config/test-llm")
    assert res.status_code == 200
    data = res.json()
    assert "success" in data
    assert "provider" in data
    assert data["provider"] == "groq"
    assert data["model"] == "llama-3.3-70b-versatile"
    assert data["base_url"] == "https://api.groq.com/openai/v1"
    # Never expose unmasked secrets
    for val in data.values():
        if isinstance(val, str) and len(val) > 10:
            assert not (val.startswith("gsk_") and "..." not in val)


def test_groq_llm_synthesis_integration():
    from app.agents.research_agent import synthesize_answer
    
    mock_llm = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "## 📌 Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) [1]\nBeneficiaries receive ₹6,000 per year."
    mock_llm.invoke.return_value = mock_msg

    with patch("app.agents.research_agent.get_llm", return_value=mock_llm):
        evidence = [{
            "text": "PM-KISAN provides ₹6,000 per year to eligible farmers.",
            "metadata": {"title": "PM-KISAN Guidelines", "source_url": "https://pmkisan.gov.in"},
            "cid": 1,
        }]
        matched = {
            "scheme_name": "Pradhan Mantri Kisan Samman Nidhi",
            "hindi_name": "प्रधानमंत्री किसान सम्मान निधि",
            "category": "Agriculture & Farmer Welfare",
            "beneficiary": "Small & Marginal Farmers",
            "eligibility": "Landholding farmer families",
            "benefits": "₹6,000 per year in 3 installments of ₹2,000",
            "documents": "Aadhaar Card, Land Records, Bank Account",
            "official_source_url": "https://pmkisan.gov.in",
            "status": "Active",
            "state_district": "Central / All India",
            "authority": "Ministry of Agriculture",
        }
        answer = synthesize_answer("What is the benefit under PM-KISAN?", evidence=evidence, matched_scheme=matched, language="en")
        assert "₹6,000" in answer
        assert "[1]" in answer
        assert mock_llm.invoke.called
