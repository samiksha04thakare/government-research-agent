"""Tests for Section-Wise Dataset Scheme Integration, Compendium Groupings, and Filtering."""
import pytest
from fastapi.testclient import TestClient

from app.database.db import Scheme, SessionLocal
from app.main import app

client = TestClient(app)


def test_dataset_sections_summary_endpoint():
    """Verify GET /schemes/sections returns structured official compendium sections."""
    res = client.get("/schemes/sections")
    assert res.status_code == 200
    sections = res.json()
    assert isinstance(sections, list)
    assert len(sections) >= 3

    group_ids = [s["group_id"] for s in sections]
    assert "women_child" in group_ids
    assert "maharashtra_agri" in group_ids

    # Validate structure of each section group
    for s in sections:
        assert "group_id" in s
        assert "group_name" in s
        assert "authority" in s
        assert "count" in s
        assert "distinct_sections" in s
        assert s["count"] >= 0
        assert isinstance(s["distinct_sections"], list)


def test_women_child_dataset_sections():
    """Verify Women & Child schemes have official numbered sections (Section 1 to 11)."""
    res = client.get("/schemes?section_group=women_child&limit=100")
    assert res.status_code == 200
    schemes = res.json()
    assert len(schemes) >= 11

    # Check for specific compendium sections
    section_names = [s.get("dataset_section", "") for s in schemes]
    has_sec_1 = any("Section 1" in sec for sec in section_names)
    has_sec_2 = any("Section 2" in sec for sec in section_names)
    assert has_sec_1, "Expected Section 1 (Majhi Ladki Bahin Yojana) in Women & Child compendium"
    assert has_sec_2, "Expected Section 2 (Lek Ladki Yojana) in Women & Child compendium"

    # Check Ladki Bahin scheme specifically
    ladki_bahin = next((s for s in schemes if "MH-WOM-01" in s.get("scheme_id", "") or "Ladki Bahin" in s.get("scheme_name", "")), None)
    assert ladki_bahin is not None
    assert "Section 1" in ladki_bahin.get("dataset_section", "")
    assert ladki_bahin.get("section_group_id") == "women_child"
    assert "Women & Child" in ladki_bahin.get("section_group", "")


def test_maharashtra_agriculture_bds_sections():
    """Verify Maharashtra Agriculture schemes have proper BDS Plan sections (General, SCCS, TCS)."""
    res = client.get("/schemes?section_group=maharashtra_agri&limit=200")
    assert res.status_code == 200
    schemes = res.json()
    assert len(schemes) >= 100

    sections = {s.get("dataset_section", "") for s in schemes}
    assert any("General" in sec or "Plan" in sec or "BDS" in sec or "Agriculture" in sec for sec in sections)


def test_scheme_detail_includes_dataset_section_info():
    """Verify GET /schemes/{sid} returns dataset_section and section_group in JSON."""
    res = client.get("/schemes/MH-WOM-01")
    assert res.status_code == 200
    data = res.json()
    assert data["scheme_id"] == "MH-WOM-01"
    assert "dataset_section" in data
    assert "Section 1" in data["dataset_section"]
    assert data.get("section_group_id") == "women_child"
    assert "Women & Child" in data.get("section_group", "")
