import sys
from pathlib import Path
sys.path.insert(0, ".")

from app.rag.retriever import search_with_scores, get_store
from app.utils.citations import inspect_document_support, filter_supported_evidence
from app.config import RELEVANCE_THRESHOLD

from app.tools.document_search import vector_search

focused_queries = [
    "Kisan Credit Card application procedure documents required land records 7/12 RoR Aadhaar passbook",
    "Kisan Credit Card helpline kisan call centre 1800-180-1551 taluka agriculture officer",
]

for q in focused_queries:
    print(f"\n=== Query: {q} ===")
    results = vector_search(q, k=4)
    for r in results:
        meta = r.get("metadata", {})
        cid = meta.get("chunk_id")
        title = meta.get("title", "")
        if "agricultural-credit" in meta.get("source_url", ""):
            print(f"chunk_id={cid} | score={r['similarity_score']:.4f} | Pass={r['similarity_score'] >= RELEVANCE_THRESHOLD}")
            print(f"text: {r['text'][:120]}...\n")
