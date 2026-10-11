"""Run comprehensive whole-document vs chunk-based RAG evaluation experiment.

Compares:
1. Ingestion & token truncation metrics
2. Retrieval relevance scores
3. Specific claim / step coverage
4. Context token consumption
5. Latency & failure cases
"""
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.db import SessionLocal, Document as DbDocument
from app.rag.loader import load_file
from app.tools.document_search import vector_search
from app.utils.citations import build_citations, filter_supported_evidence
from app.experiments.whole_doc_retriever import (
    WHOLE_DOC_CHROMA_DIR,
    WHOLE_DOC_COLLECTION,
    audit_context_limit,
    index_whole_documents,
    load_whole_document,
    search_whole_documents,
)

RAW_DIR = Path("data/raw")

TEST_QUERIES = [
    {
        "id": "Q1_KCC_CREDIT",
        "category": "farmer_questions",
        "question": "What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?",
        "critical_facts": [
            "4% concessional interest rate (7% minus 3% prompt repayment incentive)",
            "Kisan Call Centre 1800-180-1551",
            "7/12 extract or RoR land records",
        ],
        "expected_source": "farmer_welfare_and_credit.txt",
    },
    {
        "id": "Q2_CROP_YELLOWING",
        "category": "crop_problems",
        "question": "How to distinguish between Nitrogen deficiency, waterlogging, and Iron chlorosis when crop leaves turn yellow?",
        "critical_facts": [
            "Nitrogen deficiency older bottom leaves first",
            "Iron chlorosis younger top leaves interveinal",
            "Waterlogging root asphyxiation",
        ],
        "expected_source": "crop_production_and_disorders.txt",
    },
    {
        "id": "Q3_FAW_IPM",
        "category": "pest_management",
        "question": "What is the Integrated Pest Management (IPM) schedule and ETL for Fall Armyworm (FAW) in maize?",
        "critical_facts": [
            "Fall Armyworm",
            "ETL or pheromone traps",
            "CIBRC bio-pesticides or recommended spray",
        ],
        "expected_source": "integrated_pest_management_cibrc.txt",
    },
    {
        "id": "Q4_SOIL_HEALTH",
        "category": "fertilizers",
        "question": "How to interpret Soil Health Card parameters (pH, EC, Organic Carbon, and NPK benchmarks)?",
        "critical_facts": [
            "Soil Health Card",
            "Organic Carbon",
            "NPK benchmarks",
        ],
        "expected_source": "soil_health_and_fertilizer_management.txt",
    },
    {
        "id": "Q5_PM_KISAN",
        "category": "government_schemes",
        "question": "What are the mandatory e-KYC and land-seeding rules to receive Rs 6,000 yearly under PM-KISAN?",
        "critical_facts": [
            "Rs 6,000 yearly in 3 instalments",
            "e-KYC mandatory",
            "Aadhaar linked bank account",
        ],
        "expected_source": "agriculture_government_schemes.txt",
    },
    {
        "id": "Q6_MAHA_NAMO_SHETAKARI",
        "category": "government_schemes",
        "question": "What is the 2026-27 proposed budget outlay and allocation for Namo Shetakari Mahasanmaan Nidhi Yojana?",
        "critical_facts": [
            "Namo Shetakari Mahasanmaan Nidhi Yojana",
            "Proposed outlay",
            "Scheme Code 2401A511",
        ],
        "expected_source": "maharashtra_agriculture_active_schemes_2026_2027.txt",
    },
    {
        "id": "Q7_MAHA_KRUSHI_SAMRUDHI",
        "category": "government_schemes",
        "question": "What are the details and fund utilization of the new Krushi Samrudhi Yojana in Maharashtra?",
        "critical_facts": [
            "Krushi Samrudhi Yojana",
            "Proposed outlay or BDS release",
        ],
        "expected_source": "maharashtra_agriculture_active_schemes_2026_2027.txt",
    },
]


def ingest_raw_documents_into_whole_doc_store():
    print("\n" + "=" * 80)
    print("STEP 1: INGESTING WHOLE DOCUMENTS (NO CHUNKING) INTO SEPARATE CHROMA STORE")
    print(f"Directory: {WHOLE_DOC_CHROMA_DIR} | Collection: {WHOLE_DOC_COLLECTION}")
    print("=" * 80)

    # Gather metadata from SQLite or defaults
    doc_metadata_map = {}
    with SessionLocal() as db:
        for d in db.query(DbDocument).all():
            doc_metadata_map[Path(d.file_path).name] = {
                "title": d.title,
                "authority": d.authority,
                "department": d.authority,
                "source_url": d.source_url,
                "publication_date": d.publication_date,
                "updated_date": d.updated_date,
                "version": d.version,
                "document_type": d.document_type,
            }

    whole_docs = []
    ingestion_stats = []

    for path in sorted(RAW_DIR.glob("*")):
        if path.suffix.lower() not in [".txt", ".pdf", ".html"]:
            continue

        meta = doc_metadata_map.get(path.name, {})
        doc = load_whole_document(path, meta)
        whole_docs.append(doc)

        stat = {
            "file_name": path.name,
            "title": doc.metadata["title"],
            "department": doc.metadata["department"],
            "total_chars": doc.metadata["total_characters"],
            "total_words": doc.metadata["total_words"],
            "total_tokens": doc.metadata["total_tokens"],
            "embedding_limit": doc.metadata["max_embedding_tokens"],
            "is_truncated": doc.metadata["embedding_truncated"],
            "loss_pct": doc.metadata["estimated_token_loss_pct"],
        }
        ingestion_stats.append(stat)
        status = f"TRUNCATED ({stat['loss_pct']}% lost)" if stat["is_truncated"] else "OK"
        print(f"Loaded: {path.name[:35]:35s} | Tokens: {stat['total_tokens']:5d} | Limit: 256 | {status}")

    indexed = index_whole_documents(whole_docs, force=True)
    print(f"\nIndexed {indexed} whole documents into experimental store.")
    return ingestion_stats


def evaluate_comparative_retrieval(ingestion_stats):
    print("\n" + "=" * 80)
    print("STEP 2: RUNNING COMPARATIVE RETRIEVAL BENCHMARKS ON SAME QUERY SUITE")
    print("=" * 80)

    results = []

    for tcase in TEST_QUERIES:
        qid = tcase["id"]
        q = tcase["question"]
        cat = tcase["category"]
        crit_facts = tcase["critical_facts"]

        print(f"\nEvaluating {qid}: \"{q[:60]}...\"")

        # ----------------- PIPELINE A: CHUNK-BASED (CURRENT) -----------------
        t0 = time.perf_counter()
        chunk_raw = vector_search(q, k=5)
        t_chunk = round((time.perf_counter() - t0) * 1000, 2)

        chunk_top_score = chunk_raw[0]["similarity_score"] if chunk_raw else 0.0
        chunk_avg_score = round(sum(r["similarity_score"] for r in chunk_raw) / len(chunk_raw), 4) if chunk_raw else 0.0
        chunk_total_words = sum(len(r["text"].split()) for r in chunk_raw)
        chunk_total_tokens = sum(len(r["text"].split()) * 1.3 for r in chunk_raw)

        # Fact coverage in chunk retrieved text
        chunk_combined_text = " ".join(r["text"].lower() for r in chunk_raw)
        chunk_facts_found = [fact for fact in crit_facts if any(k.lower() in chunk_combined_text for k in fact.split() if len(k) > 4)]

        # ----------------- PIPELINE B: WHOLE-DOCUMENT (EXPERIMENTAL) ---------
        t0 = time.perf_counter()
        whole_raw = search_whole_documents(q, k=5)
        t_whole = round((time.perf_counter() - t0) * 1000, 2)

        whole_top_score = whole_raw[0]["similarity_score"] if whole_raw else 0.0
        whole_avg_score = round(sum(r["similarity_score"] for r in whole_raw) / len(whole_raw), 4) if whole_raw else 0.0
        whole_context_audit = audit_context_limit(whole_raw, max_context_budget=12000)
        whole_total_tokens = whole_context_audit["total_retrieved_tokens"]

        # Fact coverage in whole document retrieved text
        whole_combined_text = " ".join(r["text"].lower() for r in whole_raw)
        whole_facts_found = [fact for fact in crit_facts if any(k.lower() in whole_combined_text for k in fact.split() if len(k) > 4)]

        # Truncation risk analysis: did the matching document suffer embedding truncation?
        top_doc_truncated = whole_raw[0]["embedding_truncated"] if whole_raw else False
        top_doc_loss_pct = whole_raw[0]["estimated_token_loss_pct"] if whole_raw else 0.0

        query_res = {
            "query_id": qid,
            "question": q,
            "category": cat,
            "chunk_pipeline": {
                "top_similarity_score": chunk_top_score,
                "avg_similarity_score": chunk_avg_score,
                "retrieved_count": len(chunk_raw),
                "total_words": chunk_total_words,
                "approx_tokens": int(chunk_total_tokens),
                "latency_ms": t_chunk,
                "facts_found_ratio": f"{len(chunk_facts_found)}/{len(crit_facts)}",
                "top_source": chunk_raw[0]["metadata"].get("title", "") if chunk_raw else "",
            },
            "whole_doc_pipeline": {
                "top_similarity_score": whole_top_score,
                "avg_similarity_score": whole_avg_score,
                "retrieved_count": len(whole_raw),
                "total_tokens": whole_total_tokens,
                "exceeds_context_limit": whole_context_audit["exceeds_context_limit"],
                "latency_ms": t_whole,
                "facts_found_ratio": f"{len(whole_facts_found)}/{len(crit_facts)}",
                "top_source": whole_raw[0]["metadata"].get("title", "") if whole_raw else "",
                "top_doc_truncated": top_doc_truncated,
                "top_doc_token_loss_pct": top_doc_loss_pct,
            },
        }
        results.append(query_res)

        print(f"  Chunk RAG     -> Score: {chunk_top_score:.4f} | Tokens: ~{int(chunk_total_tokens)} | Latency: {t_chunk}ms | Facts: {len(chunk_facts_found)}/{len(crit_facts)}")
        print(f"  Whole-Doc RAG -> Score: {whole_top_score:.4f} | Tokens: {whole_total_tokens} | Latency: {t_whole}ms | Facts: {len(whole_facts_found)}/{len(crit_facts)} | Top Doc Loss: {top_doc_loss_pct}%")

    return results


def main():
    ingestion_stats = ingest_raw_documents_into_whole_doc_store()
    comparative_results = evaluate_comparative_retrieval(ingestion_stats)

    output = {
        "summary": "Evaluation of Removing Chunking vs Chunk-Based RAG",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_max_tokens": 256,
        "ingestion_statistics": ingestion_stats,
        "query_comparisons": comparative_results,
    }

    out_path = Path("evaluation_whole_doc_vs_chunk.json")
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nSaved full comparative evaluation results to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
