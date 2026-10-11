import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

test_cases = [
    {
        "id": "A",
        "name": "KCC Application (Government Schemes)",
        "question": "How can a farmer apply for Kisan Credit Card?",
        "expected_decision": "ACCEPTED",
        "expected_min_accepted": 1,
    },
    {
        "id": "B",
        "name": "Cotton Pest Management (Pest Management)",
        "question": "What is the recommended method for managing pests in cotton?",
        "expected_decision": "ACCEPTED",
        "expected_min_accepted": 1,
    },
    {
        "id": "C",
        "name": "Fertilizer based on Soil Health (Fertilizers)",
        "question": "What fertilizer is recommended based on soil health?",
        "expected_decision": "ACCEPTED",
        "expected_min_accepted": 1,
    },
    {
        "id": "D",
        "name": "Tell me a joke (Out of Scope)",
        "question": "Tell me a joke",
        "expected_decision": "OUT_OF_SCOPE",
        "expected_min_accepted": 0,
    },
    {
        "id": "E",
        "name": "Unindexed Government Query (LTC Reimbursement)",
        "question": "How can a government employee claim LTC tour reimbursement?",
        "expected_decision": "REJECTED_LOW_RELEVANCE",
        "expected_min_accepted": 0,
    },
]

print("==================================================================")
print("RUNNING STEP 4 TESTS: STRICT RELEVANCE / SIMILARITY FILTERING")
print("==================================================================")

client = httpx.Client(timeout=60.0)

all_passed = True
for tc in test_cases:
    cid = tc["id"]
    name = tc["name"]
    q = tc["question"]

    print(f"\n--- Case {cid}: {name} ---")
    print(f"Query: \"{q}\"")

    resp = client.post(f"{BASE_URL}/research", json={"question": q})
    assert resp.status_code == 200, f"HTTP Error {resp.status_code}: {resp.text}"
    data = resp.json()

    category = data.get("category")
    scope = data.get("scope")
    status = data.get("status")
    answer = data.get("answer", "")
    retrieved_chunks = data.get("retrieved_chunks", [])
    accepted_count = len(retrieved_chunks)
    scores = [c.get("similarity_score") for c in retrieved_chunks]

    if status == "out_of_scope":
        decision = "OUT_OF_SCOPE"
    elif status == "insufficient_evidence":
        decision = "REJECTED_LOW_RELEVANCE"
    elif status == "completed":
        decision = "ACCEPTED"
    else:
        decision = status

    print(f"  Detected Category:  {category}")
    print(f"  Detected Scope:     {scope}")
    print(f"  Decision:           {decision}")
    print(f"  Accepted Chunks:    {accepted_count}")
    print(f"  Accepted Scores:    {scores}")
    print(f"  Final Answer:\n    {answer[:140]}...")

    # Verification
    if decision != tc["expected_decision"]:
        print(f"  [FAIL]: Expected decision {tc['expected_decision']}, got {decision}")
        all_passed = False
    elif tc["expected_min_accepted"] > 0 and accepted_count == 0:
        print(f"  [FAIL]: Expected accepted chunks >= {tc['expected_min_accepted']}, got 0")
        all_passed = False
    elif tc["expected_min_accepted"] == 0 and accepted_count > 0:
        print(f"  [FAIL]: Expected 0 accepted chunks, got {accepted_count}")
        all_passed = False
    else:
        print("  [PASS]: Case passed all criteria successfully!")

print("\n==================================================================")
if all_passed:
    print("ALL 5 REQUIRED STEP 4 TEST CASES PASSED WITH 100% SUCCESS!")
else:
    print("SOME STEP 4 TESTS FAILED.")
print("==================================================================")
