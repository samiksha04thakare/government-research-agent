import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

test_queries = [
    {
        "name": "Query 1 (Government Schemes)",
        "question": "How can a farmer apply for Kisan Credit Card?",
        "expected_category": "government_schemes",
        "expected_scope": "government_related",
        "expected_min_chunks": 1,
    },
    {
        "name": "Query 2 (Pest Management)",
        "question": "What is the recommended method for managing pests in cotton?",
        "expected_category": "pest_management",
        "expected_scope": "agriculture_related",
        "expected_min_chunks": 1,
    },
    {
        "name": "Query 3 (Fertilizers)",
        "question": "What fertilizer is recommended based on soil health?",
        "expected_category": "fertilizers",
        "expected_scope": "agriculture_related",
        "expected_min_chunks": 1,
    },
    {
        "name": "Query 4 (Crop Problems)",
        "question": "Tell me about crop diseases in cotton.",
        "expected_category": "crop_problems",
        "expected_scope": "agriculture_related",
        "expected_min_chunks": 1,
    },
    {
        "name": "Query 5 (Out of Scope)",
        "question": "Tell me a joke",
        "expected_category": "out_of_scope",
        "expected_scope": "out_of_scope",
        "expected_min_chunks": 0,
    },
    {
        "name": "Query 6 (Category with No Documents)",
        "question": "How do I file my income tax return or pay GST?",
        "expected_category": "tax_gst",
        "expected_scope": "government_related",
        "expected_min_chunks": 0,
    },
]

print("==================================================================")
print("RUNNING STEP 3 TESTS: CATEGORY CLASSIFICATION & SOURCE ROUTING")
print("==================================================================")

client = httpx.Client(timeout=60.0)

all_passed = True
for tc in test_queries:
    q = tc["question"]
    name = tc["name"]
    print(f"\n--- {name} ---")
    print(f"Question: \"{q}\"")

    resp = client.post(f"{BASE_URL}/research", json={"question": q})
    assert resp.status_code == 200, f"HTTP Error {resp.status_code}: {resp.text}"
    data = resp.json()

    detected_category = data.get("category")
    detected_scope = data.get("scope")
    retrieved_chunks = data.get("retrieved_chunks", [])
    chunks_count = len(retrieved_chunks)
    answer = data.get("answer", "")
    status = data.get("status")

    # Determine selected source / category filter
    if retrieved_chunks:
        selected_sources = list(set(c.get("source", "Unknown") for c in retrieved_chunks))
    else:
        selected_sources = ["None (Bypassed / Not retrieved)"]

    print(f"  Detected Scope:     {detected_scope}")
    print(f"  Detected Category:  {detected_category}")
    print(f"  Selected Source:    {', '.join(selected_sources[:2])}")
    print(f"  Chunks Retrieved:   {chunks_count}")
    print(f"  Status:             {status}")
    print(f"  Final Result Snippet:\n    {answer[:160]}...")

    # Validations
    if tc["expected_category"] != detected_category:
        print(f"  [FAIL]: Category mismatch. Expected {tc['expected_category']}, got {detected_category}")
        all_passed = False
    elif tc["expected_scope"] != detected_scope:
        print(f"  [FAIL]: Scope mismatch. Expected {tc['expected_scope']}, got {detected_scope}")
        all_passed = False
    elif tc["expected_min_chunks"] > 0 and chunks_count == 0:
        print(f"  [FAIL]: Expected at least {tc['expected_min_chunks']} chunks, got {chunks_count}")
        all_passed = False
    elif tc["expected_min_chunks"] == 0 and chunks_count > 0:
        print(f"  [FAIL]: Expected 0 chunks for out-of-scope/unindexed, got {chunks_count}")
        all_passed = False
    else:
        print("  [PASS]: All assertions satisfied!")

print("\n==================================================================")
if all_passed:
    print("ALL STEP 3 TESTS PASSED PERFECTLY!")
else:
    print("SOME TESTS FAILED.")
print("==================================================================")
