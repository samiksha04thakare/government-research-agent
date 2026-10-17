import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database.db import SessionLocal, Scheme

client = TestClient(app)


def test_import_csv_invalid_file_extension():
    response = client.post(
        "/scraper/import-csv",
        files={"file": ("test.txt", b"not a csv", "text/plain")},
    )
    assert response.status_code == 400
    assert "Please upload a CSV file" in response.json()["detail"]


def test_import_csv_missing_required_columns():
    csv_content = b"random_col,another_col\nvalue1,value2\n"
    response = client.post(
        "/scraper/import-csv",
        files={"file": ("data.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 400
    assert "scheme_name" in response.json()["detail"]


def test_import_csv_success_pipeline():
    csv_content = (
        "scheme_name,official_url,category,beneficiary,eligibility,benefits\n"
        "Kisan Drone Subsidy,https://agricoop.nic.in/kisan-drone,Agriculture,Small & Marginal Farmers,Farmers with verified land records,Up to Rs. 500000 subsidy for drone purchase\n"
    ).encode("utf-8")

    response = client.post(
        "/scraper/import-csv",
        files={"file": ("schemes.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["records_found"] == 1
    assert data["records_imported"] == 1
    assert data["chunks_indexed"] >= 1

    # Verify SQL upsert
    with SessionLocal() as db:
        scheme = db.query(Scheme).filter(Scheme.scheme_name.ilike("%Kisan Drone%")).first()
        assert scheme is not None
        assert scheme.official_source_url == "https://agricoop.nic.in/kisan-drone"
        assert "₹" in scheme.benefits  # Verify currency normalization (Rs. -> ₹)


def test_import_json_file_success():
    import json
    json_data = [
        {
            "scheme_name": "PM Krishi Sinchayee Yojana - Micro Irrigation",
            "official_url": "https://pmksy.gov.in/microirrigation",
            "category": "Agriculture & Irrigation",
            "beneficiary": "All farming categories, small & marginal farmers given preference",
            "eligibility": "Farmers having landholding with available water source",
            "benefits": "Subsidy up to 55% for small/marginal farmers and 45% for other farmers for drip and sprinkler systems.",
            "authority": "Department of Agriculture and Farmers Welfare, Govt of India"
        }
    ]
    file_bytes = json.dumps(json_data).encode("utf-8")

    response = client.post(
        "/scraper/import-json",
        files={"file": ("pmksy.json", file_bytes, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["records_found"] == 1
    assert data["records_imported"] == 1
    assert data["chunks_indexed"] >= 1

    with SessionLocal() as db:
        scheme = db.query(Scheme).filter(Scheme.scheme_name.ilike("%Sinchayee%")).first()
        assert scheme is not None
        assert scheme.official_source_url == "https://pmksy.gov.in/microirrigation"


def test_scraper_ingest_direct_json_payload():
    """Simulate Apify / Webhook / Scraper direct POST ingestion."""
    payload = {
        "items": [
            {
                "name": "Mahatma Jyotirao Phule Shetkari Karjmukti Yojana",
                "official_source_url": "https://mjpsky.maharashtra.gov.in",
                "category": "Debt Relief & Credit",
                "beneficiary": "Distressed farmers with crop loan arrears",
                "eligibility": "Farmers with overdue crop loans up to ₹2,00,000",
                "benefits": "Direct debt write-off credit up to Rs. 200000 deposited in bank account",
                "authority": "Department of Co-operation and Marketing, Govt of Maharashtra"
            }
        ]
    }

    response = client.post(
        "/scraper/ingest",
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["records_found"] == 1
    assert data["records_imported"] == 1
    assert data["chunks_indexed"] >= 1

    with SessionLocal() as db:
        scheme = db.query(Scheme).filter(Scheme.scheme_name.ilike("%Jyotirao%")).first()
        assert scheme is not None
        assert "₹" in scheme.benefits


def test_import_web_scraper_jsonl_payload():
    """Verify ingestion of Web Scraper JSONL records from india.gov.in."""
    jsonl_content = (
        '{"web_scraper_order":"1792218108-1","web_scraper_start_url":"https://www.india.gov.in/my-government/schemes","data":"Write to National Water Development Agency","image":"https://static2.india.gov.in/npiprod/uploads/water_e055dd1642.jpg"}\n'
        '{"web_scraper_order":"1792218108-2","web_scraper_start_url":"https://www.india.gov.in/my-government/schemes","data":"Online textbooks of National Council of Educational Research and Training","image":"https://static2.india.gov.in/npiprod/uploads/NCERT_b7c03d904c.jpg"}\n'
        '{"web_scraper_order":"1792218108-3","web_scraper_start_url":"https://www.india.gov.in/my-government/schemes","data":"Check prices and arrivals of agricultural commodities","image":"https://static2.india.gov.in/npiprod/uploads/agmarknet_a46d292c72.jpg"}\n'
        '{"web_scraper_order":"1792218108-5","web_scraper_start_url":"https://www.india.gov.in/my-government/schemes","data":"National Career Service for Job Seekers and Employers","image":"https://static2.india.gov.in/npiprod/uploads/job_seekers_8bb287414e.jpg"}\n'
        '{"web_scraper_order":"1792218108-6","web_scraper_start_url":"https://www.india.gov.in/my-government/schemes","data":"eSanjeevani - National Telemedicine Service","image":"https://static2.india.gov.in/npiprod/uploads/e_sanjeevani_626f9eef48.jpg"}\n'
        '{"web_scraper_order":"1792218108-7","web_scraper_start_url":"https://www.india.gov.in/my-government/schemes","data":"BHAVISHYA - Pension Sanction and Payment Tracking System","image":"https://static2.india.gov.in/npiprod/uploads/Bhavisya_6a3973f00b.jpg"}\n'
        '{"web_scraper_order":"1792218108-8","web_scraper_start_url":"https://www.india.gov.in/my-government/schemes","data":"Apply for New Ujjwala 2.0 Connection","image":"https://static2.india.gov.in/npiprod/uploads/ujjwala_77aade7ab0.jpg"}\n'
    ).encode("utf-8")

    response = client.post(
        "/scraper/import-json",
        files={"file": ("india_gov_scraped.json", jsonl_content, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["records_found"] == 7
    assert data["records_imported"] == 7
    assert data["chunks_indexed"] >= 7

    with SessionLocal() as db:
        ujjwala = db.query(Scheme).filter(Scheme.scheme_name.ilike("%Ujjwala%")).first()
        assert ujjwala is not None
        assert "LPG" in ujjwala.benefits

        sanjeevani = db.query(Scheme).filter(Scheme.scheme_name.ilike("%eSanjeevani%")).first()
        assert sanjeevani is not None
        assert "telemedicine" in sanjeevani.category.lower() or "health" in sanjeevani.category.lower()


