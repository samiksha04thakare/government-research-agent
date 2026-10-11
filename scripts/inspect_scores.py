import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.retriever import get_store

queries_to_test = [
    ("KCC Query", "How can a farmer apply for Kisan Credit Card?", {"category": "government_schemes"}),
    ("Pest Query", "What is the recommended method for managing pests in cotton?", {"category": "pest_management"}),
    ("Fertilizer Query", "What fertilizer is recommended based on soil health?", {"category": "fertilizers"}),
    ("Crop Disease Query", "Tell me about crop diseases in cotton.", {"category": "crop_problems"}),
    ("Unrelated Govt Scheme", "What is the application process for Startup India seed fund scheme?", {"category": "government_schemes"}),
    ("Unrelated Govt Scheme 2", "How can a government employee claim LTC tour reimbursement?", {"category": "government_schemes"}),
    ("Unrelated Pest", "How to fix a puncture in bicycle tire?", {"category": "pest_management"}),
]

store = get_store()

print("==================================================")
print("INSPECTING CHROMADB SIMILARITY RELEVANCE SCORES")
print("==================================================")

for label, q, f in queries_to_test:
    res = store.similarity_search_with_relevance_scores(q, k=3, filter=f)
    print(f"\n[{label}] Query: \"{q}\" (Filter: {f})")
    for i, (doc, score) in enumerate(res, 1):
        print(f"  {i}. Score: {score:.4f} | Title: {doc.metadata.get('title')}")
        snippet = doc.page_content.replace("\n", " ")[:90]
        print(f"     Snippet: {snippet}...")
