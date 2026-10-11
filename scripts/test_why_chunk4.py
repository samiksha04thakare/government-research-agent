import sys
from pathlib import Path
sys.path.insert(0, ".")

from app.tools.document_search import vector_search
from app.utils.citations import filter_supported_evidence
from app.config import RELEVANCE_THRESHOLD

q = "What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?"
aq = "Kisan Credit Card KCC helpline kisan call centre 1800-180-1551 taluka agriculture officer grievance"

raw = vector_search(aq, k=4)
print(f"Results for aq: count={len(raw)}")
for r in raw:
    meta = r.get("metadata", {})
    print(f"chunk_id={meta.get('chunk_id')} | score={r['similarity_score']} | title={meta.get('title')}")

supp, rej = filter_supported_evidence(q, raw, category="government_schemes")
print(f"Supported count={len(supp)} | Rejected count={len(rej)}")
for s in supp:
    meta = s.get("metadata", {})
    print(f"Supported chunk_id={meta.get('chunk_id')}")
for rj in rej:
    meta = rj.get("metadata", {})
    print(f"Rejected chunk_id={meta.get('chunk_id')} reason={rj.get('rejection_reason')}")
