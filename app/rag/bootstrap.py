"""Automatic baseline government document bootstrapper.

Ensures that upon fresh deployment (e.g., Render, Docker, cloud environments),
official agricultural and government policy guideline documents are automatically
registered and indexed into the Chroma vectorstore if the database is unpopulated.
"""
from pathlib import Path

from app.database.db import Document, SessionLocal
from app.rag.loader import load_file
from app.rag.retriever import index_documents
from app.utils.logging import get_logger

log = get_logger("rag_bootstrap")

BASELINE_DOCUMENTS = [
    {
        "file": "data/raw/farmer_welfare_and_credit.txt",
        "title": "Farmer Welfare, Land Records & Agricultural Credit Guidelines",
        "authority": "Ministry of Agriculture and Farmers Welfare, Govt of India",
        "source_url": "https://agricoop.nic.in/en/divisiontype/agricultural-credit",
        "publication_date": "2025-01-15",
    },
    {
        "file": "data/raw/crop_production_and_disorders.txt",
        "title": "Crop Production Practices, Stress Management & Physiological Disorders Advisory",
        "authority": "Indian Council of Agricultural Research (ICAR)",
        "source_url": "https://icar.org.in/crop-production-advisories",
        "publication_date": "2025-02-10",
    },
    {
        "file": "data/raw/integrated_pest_management_cibrc.txt",
        "title": "Integrated Pest Management (IPM) & CIBRC Approved Control Measures",
        "authority": "Central Insecticides Board & Registration Committee (CIBRC)",
        "source_url": "https://cibrc.gov.in/approved-crop-pest-recommendations",
        "publication_date": "2025-01-20",
    },
    {
        "file": "data/raw/soil_health_and_fertilizer_management.txt",
        "title": "Soil Health Card Parameters, Fertilizer Dosage & Subsidy Norms",
        "authority": "Department of Fertilizers & Ministry of Agriculture and Farmers Welfare",
        "source_url": "https://soilhealth.dac.gov.in/guidelines",
        "publication_date": "2025-01-10",
    },
    {
        "file": "data/raw/agriculture_government_schemes.txt",
        "title": "Central Agricultural Schemes Compendium (PM-KISAN, PMFBY, PM-KUSUM, SMAM)",
        "authority": "Ministry of Agriculture and Farmers Welfare & MNRE",
        "source_url": "https://myscheme.gov.in/schemes",
        "publication_date": "2025-01-01",
    },
    {
        "file": "data/raw/maharashtra_agriculture_active_schemes_2026_2027.txt",
        "title": "Maharashtra Active Agricultural Schemes & Budget Outlay Compendium (2026-2027)",
        "authority": "Department of Agriculture, Government of Maharashtra",
        "source_url": "https://krishi.maharashtra.gov.in/bds",
        "publication_date": "2026-10-07",
    },
    {
        "file": "data/raw/maharashtra_women_child_schemes.txt",
        "title": "Maharashtra Women and Child Development Department Schemes Compendium",
        "authority": "Women and Child Development Department, Govt of Maharashtra",
        "source_url": "https://womenchild.maharashtra.gov.in",
        "publication_date": "2025-01-15",
    },
    {
        "file": "data/raw/maharashtra_scholarships.txt",
        "title": "MahaDBT Agriculture & Higher Education Scholarships Guidelines",
        "authority": "Higher & Technical Education Department, Govt of Maharashtra",
        "source_url": "https://mahadbt.maharashtra.gov.in",
        "publication_date": "2025-01-10",
    },
    {
        "file": "data/raw/entrepreneurship_mudra_loan_guidelines.txt",
        "title": "Pradhan Mantri MUDRA Yojana (PMMY) Operational Guidelines & Loan Application Manual",
        "authority": "Department of Financial Services, Ministry of Finance, Govt of India & MUDRA Ltd.",
        "source_url": "https://www.mudra.org.in",
        "publication_date": "2025-01-20",
    },
]


def bootstrap_baseline_documents(db=None) -> int:
    """Index baseline government documents into ChromaDB and SQLite/PostgreSQL."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    indexed_count = 0
    try:
        for m in BASELINE_DOCUMENTS:
            p = Path(m["file"])
            if not p.is_file():
                continue

            existing = db.query(Document).filter(Document.title == m["title"]).first()
            if not existing:
                doc = Document(
                    title=m["title"],
                    authority=m["authority"],
                    source_url=m["source_url"],
                    document_type="txt",
                    publication_date=m["publication_date"],
                    updated_date="2025-07-01",
                    version="1.0",
                    file_path=m["file"],
                    indexed=False,
                )
                db.add(doc)
                db.commit()
            else:
                doc = existing

            if not doc.indexed:
                meta = {
                    c: getattr(doc, c)
                    for c in (
                        "title",
                        "authority",
                        "source_url",
                        "document_type",
                        "publication_date",
                        "updated_date",
                        "version",
                    )
                }
                pages = load_file(doc.file_path, meta)
                chunks = index_documents(pages)
                doc.content_hash = pages[0].metadata.get("content_hash", "") if pages else ""
                doc.indexed = True
                db.commit()
                indexed_count += 1
                log.info("Bootstrapped document '%s' with %d chunks", doc.title, chunks)
    except Exception as exc:
        log.warning("Baseline documents bootstrap error (non-fatal): %s", exc)
    finally:
        if close_db:
            db.close()

    return indexed_count
