"""Script to ingest, normalize, and connect gov_myscheme_data.csv into SQLite and ChromaDB.

Executes:
1. Locates gov_myscheme_data.csv in data/ or user-supplied path.
2. Normalizes fields: scheme name, slug/ID, ministry/state authority, eligibility,
   benefits, documents required, application process, and official links.
3. Performs high-performance bulk upsert to SQLite relational database (research.db).
4. Creates structured search documents and indexes them in ChromaDB vectorstore.
5. Verifies database integrity and runs sample queries to ensure readiness.
"""
import sys
import os
import time
import re
import hashlib
from pathlib import Path

# Configure UTF-8 encoding for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from langchain_core.documents import Document as LcDocument

from app.database.db import Document as DbDocument, Scheme, SessionLocal, init_db
from app.rag.chunker import chunk_documents
from app.rag.retriever import get_store, search_with_scores
from app.schemes.normalizer import get_canonical_scheme_id
from app.schemes.pipeline import normalize_text, search_schemes_in_db
from app.sources.csv_importer import _compute_hash, _is_valid_url, _now_iso, _today_str, enrich_scraped_scheme_metadata
from app.utils.logging import get_logger

log = get_logger("connect_myscheme")


def locate_csv_file(custom_path: str | None = None) -> Path:
    """Find the gov_myscheme_data.csv file."""
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified CSV file not found: {custom_path}")

    candidates = [
        ROOT_DIR / "data" / "gov_myscheme_data.csv",
        ROOT_DIR.parent / "gov_myscheme_data.csv",
        Path("data/gov_myscheme_data.csv"),
        Path("gov_myscheme_data.csv"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()

    raise FileNotFoundError(
        "Could not find gov_myscheme_data.csv in ./data/ or parent directory. "
        "Please provide the absolute path as an argument."
    )


def connect_myscheme_dataset(
    csv_path: str | None = None,
    batch_size: int = 100,
    index_vectorstore: bool = True,
    limit: int | None = None,
) -> dict:
    file_path = locate_csv_file(csv_path)
    print(f"\n[INFO] Loading dataset from: {file_path}", flush=True)
    t0 = time.time()

    df = pd.read_csv(file_path)
    if limit:
        df = df.head(limit)
    total_records = len(df)
    print(f"[INFO] Total scheme records found: {total_records:,}", flush=True)

    # Initialize SQL DB
    init_db()

    today = _today_str()
    now_ts = _now_iso()

    # Normalize DataFrame column keys
    col_map = {}
    for c in df.columns:
        k_clean = str(c).strip().lower()
        k_norm = re.sub(r"[^a-z0-9]+", "_", k_clean).strip("_")
        col_map[c] = k_norm
    df_norm = df.rename(columns=col_map).fillna("")

    # Cache existing schemes in memory for O(1) deduplication
    print("[CACHE] Caching existing schemes in SQLite for fast deduplication...", flush=True)
    with SessionLocal() as db:
        existing_schemes = db.query(Scheme).all()
        id_to_scheme = {s.scheme_id: s for s in existing_schemes if s.scheme_id}
        name_to_scheme = {s.scheme_name.lower(): s for s in existing_schemes if s.scheme_name}

    print(f"        Found {len(existing_schemes)} schemes currently in database.", flush=True)

    imported_count = 0
    updated_count = 0
    all_chunks: list[LcDocument] = []
    all_chunk_ids: list[str] = []

    print("\n[SQL] Synchronizing records into SQLite relational database...", flush=True)
    db = SessionLocal()

    try:
        for idx, row in df_norm.iterrows():
            raw_name = str(row.get("scheme_name") or row.get("name") or row.get("title") or "").strip()
            if not raw_name:
                continue

            raw_url = str(
                row.get("official_link") or row.get("official_url") or row.get("myscheme_url") or row.get("source_url") or ""
            ).strip()

            if not _is_valid_url(raw_url):
                fallback_url = str(row.get("myscheme_url") or "").strip()
                if _is_valid_url(fallback_url):
                    raw_url = fallback_url
                else:
                    raw_url = f"https://www.myscheme.gov.in/schemes/{row.get('scheme_slug', 'scheme')}"

            scheme_name = normalize_text(raw_name)
            official_url = raw_url
            slug = str(row.get("scheme_slug", "")).strip()

            enrichment = enrich_scraped_scheme_metadata(scheme_name, row.to_dict())

            hindi_name = normalize_text(
                str(row.get("hindi_name") or row.get("scheme_name_hi") or enrichment.get("hindi_name") or scheme_name)
            )

            canonical_id = slug or row.get("scheme_id") or get_canonical_scheme_id(scheme_name, hindi_name, official_url)

            # Category
            raw_tags = str(row.get("tags_categories") or row.get("category") or "").strip()
            if raw_tags:
                first_tag = [t.strip() for t in raw_tags.split(",") if t.strip()]
                category = ", ".join(first_tag[:3])
            else:
                category = enrichment.get("category", "Government Schemes & Welfare")
            category = normalize_text(category)

            # Beneficiary
            beneficiary = normalize_text(
                str(row.get("beneficiary") or enrichment.get("beneficiary") or "Eligible citizens, youths, and families")
            )

            # Eligibility & Exclusions
            raw_elig = str(row.get("eligibility_criteria") or row.get("eligibility_general") or row.get("eligibility") or "").strip()
            raw_excl = str(row.get("exclusions_ineligibility") or "").strip()
            if raw_excl and raw_excl not in raw_elig:
                eligibility = normalize_text(f"{raw_elig}\nExclusions: {raw_excl}" if raw_elig else f"Exclusions: {raw_excl}")
            else:
                eligibility = normalize_text(raw_elig or "Subject to official department verification and guidelines.")

            # Benefits
            raw_benefits = str(row.get("benefits") or enrichment.get("benefits") or "").strip()
            benefits = normalize_text(raw_benefits or "Financial assistance and institutional support under scheme rules.")

            # Documents
            raw_docs = str(row.get("documents_required") or row.get("documents") or "").strip()
            documents = normalize_text(raw_docs or "Aadhaar Card, Bank Passbook, Identity & Residence proof.")

            # Authority & Jurisdiction
            level = str(row.get("level", "")).strip()
            state_ut = str(row.get("state_ut_ministry", "")).strip()

            if level.lower() == "central":
                state_district = "Central / All India"
                authority = state_ut or "Government of India"
            else:
                state_district = state_ut or "State / UT"
                authority = f"{state_ut} Administration / State Department"

            authority = normalize_text(authority)
            state_district = normalize_text(state_district)

            # Description / Guidelines Summary
            raw_desc = str(row.get("description") or row.get("summary") or "").strip()
            raw_mode = str(row.get("application_mode") or "").strip()
            raw_proc = str(row.get("application_process") or "").strip()
            raw_faqs = str(row.get("frequently_asked_questions_faqs") or "").strip()

            desc_parts = [raw_desc] if raw_desc else [f"{scheme_name} - {benefits}"]
            if raw_mode:
                desc_parts.append(f"Application Mode: {raw_mode}")
            if raw_proc and raw_proc not in raw_desc:
                desc_parts.append(f"Application Process:\n{raw_proc}")
            if raw_faqs and len(raw_faqs) > 30:
                desc_parts.append(f"FAQs:\n{raw_faqs[:1000]}")

            guidelines_summary = normalize_text("\n\n".join(desc_parts))

            # Deduplication lookup in memory
            existing_s = id_to_scheme.get(canonical_id) or name_to_scheme.get(scheme_name.lower())

            if existing_s:
                existing_s.scheme_id = canonical_id
                existing_s.category = category
                existing_s.beneficiary = beneficiary
                existing_s.eligibility = eligibility
                existing_s.benefits = benefits
                existing_s.documents = documents
                existing_s.state_district = state_district
                existing_s.official_source_url = official_url
                existing_s.authority = authority
                existing_s.guidelines_summary = guidelines_summary
                updated_count += 1
            else:
                new_s = Scheme(
                    scheme_id=canonical_id,
                    scheme_name=scheme_name,
                    hindi_name=hindi_name,
                    category=category,
                    beneficiary=beneficiary,
                    eligibility=eligibility,
                    benefits=benefits,
                    documents=documents,
                    state_district=state_district,
                    status="Active",
                    official_source_url=official_url,
                    authority=authority,
                    guidelines_summary=guidelines_summary,
                )
                db.add(new_s)
                id_to_scheme[canonical_id] = new_s
                name_to_scheme[scheme_name.lower()] = new_s
                imported_count += 1

            # Prepare high-density document text for ChromaDB vectorstore
            if index_vectorstore:
                doc_content = (
                    f"Scheme Name: {scheme_name}\n"
                    f"Hindi Name: {hindi_name}\n"
                    f"Scheme ID: {canonical_id}\n"
                    f"Category: {category}\n"
                    f"Level: {level}\n"
                    f"Authority: {authority}\n"
                    f"Jurisdiction: {state_district}\n"
                    f"Beneficiary: {beneficiary}\n"
                    f"Eligibility Criteria: {eligibility[:450]}\n"
                    f"Benefits: {benefits[:450]}\n"
                    f"Required Documents: {documents[:350]}\n"
                    f"Official URL: {official_url}\n"
                    f"Guidelines & Overview: {raw_desc[:500]}"
                )
                content_hash = _compute_hash(doc_content)

                metadata = {
                    "source_name": authority or scheme_name,
                    "source_url": official_url,
                    "category": "government_schemes",
                    "department": authority,
                    "authority": authority,
                    "title": scheme_name,
                    "document_type": "myscheme_csv",
                    "last_checked": today,
                    "last_updated": today,
                    "content_hash": content_hash,
                    "scheme_id": canonical_id,
                    "ingested_at": now_ts,
                }

                lc_doc = LcDocument(page_content=doc_content, metadata=metadata)
                chunks = chunk_documents([lc_doc], size=1400, overlap=100)
                key_hash = hashlib.sha256(canonical_id.encode("utf-8")).hexdigest()[:10]
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    all_chunk_ids.append(f"myscheme_{key_hash}_{i}")

                # Sync with Document table
                db_doc = db.query(DbDocument).filter(
                    (DbDocument.source_url == official_url) | (DbDocument.title == scheme_name)
                ).first()
                if not db_doc:
                    db_doc = DbDocument(
                        title=scheme_name,
                        authority=authority,
                        source_url=official_url,
                        document_type="myscheme_csv",
                        publication_date=today,
                        updated_date=today,
                        version="1.0",
                        file_path=f"myscheme://{canonical_id}",
                        content_hash=content_hash,
                        indexed=True,
                    )
                    db.add(db_doc)
                else:
                    db_doc.content_hash = content_hash
                    db_doc.indexed = True
                    db_doc.updated_date = today

            # Commit periodically to SQL
            if (idx + 1) % 500 == 0 or (idx + 1) == total_records:
                db.commit()
                print(f"   [{idx + 1:,} / {total_records:,}] Schemes synchronized with SQL...", flush=True)

        db.commit()
    finally:
        db.close()

    print(f"[SQL DONE] {imported_count:,} new schemes inserted, {updated_count:,} schemes updated.", flush=True)

    # 4. ChromaDB Vectorstore Ingestion
    chunks_indexed = 0
    if index_vectorstore and all_chunks:
        print(f"\n[CHROMA] Indexing {len(all_chunks):,} chunks into ChromaDB vectorstore...", flush=True)
        store = get_store()

        total_chunks = len(all_chunks)
        for b_start in range(0, total_chunks, batch_size):
            b_chunks = all_chunks[b_start : b_start + batch_size]
            b_ids = all_chunk_ids[b_start : b_start + batch_size]
            store.add_documents(b_chunks, ids=b_ids)
            chunks_indexed += len(b_chunks)
            pct = int((chunks_indexed / total_chunks) * 100)
            print(f"   [{chunks_indexed:,} / {total_chunks:,}] ({pct}%) Chunks embedded and indexed in ChromaDB...", flush=True)

        print(f"[CHROMA DONE] {chunks_indexed:,} chunks indexed.", flush=True)

    elapsed = round(time.time() - t0, 2)
    print(f"\n[SUCCESS] Connected gov_myscheme_data in {elapsed}s!", flush=True)

    # 5. Verification Check
    print("\n[VERIFY] Checking connected data integrity...", flush=True)
    with SessionLocal() as db_check:
        total_schemes_in_db = db_check.query(Scheme).count()
        print(f"   - Total schemes in SQLite DB: {total_schemes_in_db:,}", flush=True)

        # Test search query
        sample_results, sample_total, _ = search_schemes_in_db(
            query="Lakshadweep Capital Investment", db=db_check, page=1, page_size=3, return_total=True
        )
        print(f"   - Test SQL Search ('Lakshadweep Capital Investment'): Found {sample_total} matching schemes.", flush=True)
        for s in sample_results[:2]:
            print(f"     * [{s.scheme_id}] {s.scheme_name} | {s.state_district} | {s.official_source_url}", flush=True)

    if index_vectorstore:
        try:
            vec_res = search_with_scores("subsidy for micro enterprises in islands", k=2)
            print(f"   - Test Chroma Vector Search: Retrieved {len(vec_res)} chunks successfully.", flush=True)
            for doc, score in vec_res:
                print(f"     * Similarity: {score:.3f} | Title: {doc.metadata.get('title')} | URL: {doc.metadata.get('source_url')}", flush=True)
        except Exception as v_err:
            print(f"   - Vector search test warning: {v_err}", flush=True)

    return {
        "status": "success",
        "csv_path": str(file_path),
        "total_records_in_csv": total_records,
        "new_schemes_inserted": imported_count,
        "schemes_updated": updated_count,
        "total_chunks_indexed": chunks_indexed,
        "elapsed_seconds": elapsed,
    }


if __name__ == "__main__":
    custom_arg = sys.argv[1] if len(sys.argv) > 1 else None
    connect_myscheme_dataset(csv_path=custom_arg)
