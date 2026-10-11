import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.db import SessionLocal, Document
from app.rag.loader import load_file
from app.rag.retriever import index_documents, get_store

# Document metadata configurations preserving authentic sources and adding category
DOC_METADATA_CONFIGS = {
    "myScheme Guidelines": {
        "source_name": "myScheme National Platform",
        "source_url": "https://www.myscheme.gov.in",
        "category": "government_schemes",
        "department": "Ministry of Electronics and IT (MeitY)",
        "document_type": "Official Guideline",
        "last_checked": "2026-10-08",
    },
    "Maharashtra State Post-Matric Scholarship Scheme Guidelines": {
        "source_name": "MahaDBT Portal",
        "source_url": "https://mahadbt.maharashtra.gov.in",
        "category": "education_scholarships",
        "department": "Higher and Technical Education Department, Govt of Maharashtra",
        "document_type": "Official Guideline",
        "last_checked": "2026-10-08",
    },
    "Farmer Welfare, Land Records & Agricultural Credit Guidelines": {
        "source_name": "Department of Agriculture and Farmers Welfare (DA&FW)",
        "source_url": "https://agricoop.nic.in/en/divisiontype/agricultural-credit",
        "category": "government_schemes",
        "department": "Ministry of Agriculture and Farmers Welfare, Govt of India",
        "document_type": "Official Guideline / Manual",
        "last_checked": "2026-10-08",
    },
    "Crop Production Practices, Stress Management & Physiological Disorders Advisory": {
        "source_name": "ICAR Advisory Portal",
        "source_url": "https://icar.org.in/crop-production-advisories",
        "category": "crop_problems",
        "department": "Indian Council of Agricultural Research (ICAR)",
        "document_type": "Advisory / Technical Bulletin",
        "last_checked": "2026-10-08",
    },
    "Integrated Pest Management (IPM) & CIBRC Approved Control Measures": {
        "source_name": "CIBRC Pest Recommendations",
        "source_url": "https://cibrc.gov.in/approved-crop-pest-recommendations",
        "category": "pest_management",
        "department": "Central Insecticides Board & Registration Committee (CIBRC)",
        "document_type": "Regulatory Standard / IPM Advisory",
        "last_checked": "2026-10-08",
    },
    "Soil Health Card Parameters, Fertilizer Dosage & Subsidy Norms": {
        "source_name": "Soil Health Card Portal",
        "source_url": "https://soilhealth.dac.gov.in/guidelines",
        "category": "fertilizers",
        "department": "Department of Fertilizers & Ministry of Agriculture and Farmers Welfare",
        "document_type": "Technical Manual / Standards",
        "last_checked": "2026-10-08",
    },
    "Central Agricultural Schemes Compendium (PM-KISAN, PMFBY, PM-KUSUM, SMAM)": {
        "source_name": "myScheme Central Schemes",
        "source_url": "https://myscheme.gov.in/schemes",
        "category": "government_schemes",
        "department": "Ministry of Agriculture and Farmers Welfare & MNRE",
        "document_type": "Compendium / Scheme Guidelines",
        "last_checked": "2026-10-08",
    },
    "pm kisan guideline": {
        "source_name": "PM-KISAN Guidelines",
        "source_url": "https://myscheme.gov.in",
        "category": "government_schemes",
        "department": "Ministry of Agriculture",
        "document_type": "Official Guideline",
        "last_checked": "2026-10-08",
    },
    "kisan post scheme": {
        "source_name": "Kisan Post Scheme",
        "source_url": "https://pmkisan.gov.in",
        "category": "government_schemes",
        "department": "Ministry of Agriculture",
        "document_type": "Official Guideline",
        "last_checked": "2026-10-08",
    },
    "Maharashtra Active Agricultural Schemes & Budget Outlay Compendium (2026-2027)": {
        "source_name": "Krishi Maharashtra BDS Portal",
        "source_url": "https://krishi.maharashtra.gov.in/bds",
        "category": "government_schemes",
        "department": "Department of Agriculture, Government of Maharashtra",
        "document_type": "Budget & Scheme Compendium",
        "last_checked": "2026-10-08",
    },
}


def main():
    print("==================================================")
    print("UPDATING DOCUMENT INDEXING METADATA IN CHROMADB")
    print("==================================================")
    with SessionLocal() as db:
        docs = db.query(Document).all()
        print(f"Total documents found in database: {len(docs)}")

        total_chunks = 0
        for doc in docs:
            cfg = DOC_METADATA_CONFIGS.get(doc.title, {})
            meta = {
                "title": doc.title,
                "authority": doc.authority or cfg.get("department", "Government Authority"),
                "department": doc.authority or cfg.get("department", "Government Authority"),
                "source_url": doc.source_url or cfg.get("source_url", ""),
                "source_name": cfg.get("source_name", doc.title),
                "category": cfg.get("category", "other_government"),
                "document_type": doc.document_type or cfg.get("document_type", "Document"),
                "last_checked": cfg.get("last_checked", "2026-10-08"),
                "publication_date": doc.publication_date or "2025-01-01",
                "updated_date": doc.updated_date or "2025-07-01",
                "version": doc.version or "1.0",
            }

            pages = load_file(doc.file_path, meta)
            chunks = index_documents(pages, force=True)
            doc.content_hash = pages[0].metadata.get("content_hash", "") if pages else ""
            doc.indexed = True
            total_chunks += chunks
            print(f"Updated '{doc.title}': {chunks} chunks | category: {meta['category']}")

        db.commit()
        print(f"\nSuccessfully updated {len(docs)} documents ({total_chunks} chunks) in ChromaDB collection 'gov_docs'!")

        # Verify a sample from ChromaDB
        store = get_store()
        sample = store.get(limit=3)
        print("\nVerification sample from ChromaDB:")
        for m in sample["metadatas"]:
            print(f"- Title: {m.get('title')} | Category: {m.get('category')} | Source: {m.get('source_name')} | Last Checked: {m.get('last_checked')}")


if __name__ == "__main__":
    main()
