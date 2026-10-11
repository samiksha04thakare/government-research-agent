import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.db import SessionLocal, Document
from app.rag.loader import load_file
from app.rag.retriever import index_documents

doc_meta = {
    "file": "data/raw/maharashtra_agriculture_active_schemes_2026_2027.txt",
    "title": "Maharashtra Active Agricultural Schemes & Budget Outlay Compendium (2026-2027)",
    "authority": "Department of Agriculture, Government of Maharashtra",
    "source_url": "https://krishi.maharashtra.gov.in/bds",
    "publication_date": "2026-10-07",
    "updated_date": "2026-10-08",
    "version": "1.0",
    "document_type": "txt",
}

def main():
    with SessionLocal() as db:
        existing = db.query(Document).filter(Document.title == doc_meta["title"]).first()
        if not existing:
            doc = Document(
                title=doc_meta["title"],
                authority=doc_meta["authority"],
                source_url=doc_meta["source_url"],
                document_type=doc_meta["document_type"],
                publication_date=doc_meta["publication_date"],
                updated_date=doc_meta["updated_date"],
                version=doc_meta["version"],
                file_path=doc_meta["file"],
                indexed=False,
            )
            db.add(doc)
            db.commit()
            print(f"Added to database: {doc_meta['title']}")
        else:
            doc = existing
            print(f"Already in database: {doc_meta['title']}")

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
        print(f"Successfully indexed '{doc.title}': {chunks} chunks added to ChromaDB!")

if __name__ == "__main__":
    main()
