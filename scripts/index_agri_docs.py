import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.db import SessionLocal, Document
from app.rag.loader import load_file
from app.rag.retriever import index_documents

docs_meta = [
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
    }
]

def main():
    with SessionLocal() as db:
        for m in docs_meta:
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
                print(f"Added to database: {m['title']}")
            else:
                print(f"Already in database: {m['title']}")

        unindexed = db.query(Document).filter(Document.indexed.is_(False)).all()
        print(f"Documents to index: {len(unindexed)}")
        total_chunks = 0
        for doc in unindexed:
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
            total_chunks += chunks
            doc.content_hash = pages[0].metadata["content_hash"] if pages else ""
            doc.indexed = True
            print(f"Indexed '{doc.title}': {chunks} chunks")
        db.commit()
        print(f"All done! Added {total_chunks} chunks.")

if __name__ == "__main__":
    main()
