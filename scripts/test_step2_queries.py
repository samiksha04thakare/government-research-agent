import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

queries = [
    {
        "domain": "Government",
        "question": "How can a farmer apply for Kisan Credit Card?",
        "expected_status": "completed",
        "should_have_chunks": True,
    },
    {
        "domain": "Agriculture",
        "question": "What is the recommended method for managing pests in cotton?",
        "expected_status": "completed",
        "should_have_chunks": True,
    },
    {
        "domain": "Random",
        "question": "Tell me a joke",
        "expected_status": "out_of_scope",
        "should_have_chunks": False,
    },
    {
        "domain": "Random",
        "question": "What is 2 + 2?",
        "expected_status": "out_of_scope",
        "should_have_chunks": False,
    },
    {
        "domain": "Programming",
        "question": "Write a Python calculator",
        "expected_status": "out_of_scope",
        "should_have_chunks": False,
    },
]

print("==================================================================")
print("RUNNING STEP 2 QUERY CLASSIFICATION TESTS VIA LIVE API ENDPOINT")
print("==================================================================")

client = httpx.Client(timeout=60.0)

all_passed = True
for tc in queries:
    q = tc["question"]
    domain = tc["domain"]
    resp = client.post(f"{BASE_URL}/research", json={"question": q})
    assert resp.status_code == 200, f"HTTP Error {resp.status_code}: {resp.text}"
    data = resp.json()

    status = data.get("status")
    answer = data.get("answer", "")
    retrieved_chunks = data.get("retrieved_chunks", [])
    chunks_count = len(retrieved_chunks)

    print(f"\n[{domain}] Query: \"{q}\"")
    print(f"  Status: {status}")
    print(f"  Retrieved Chunks: {chunks_count}")
    print(f"  Answer Snippet: {answer[:130]}...")

    # Verification
    if tc["should_have_chunks"]:
        if status != "completed" or chunks_count == 0:
            print("  [FAIL]: Expected completed status with retrieved chunks!")
            all_passed = False
        else:
            print("  [PASS]: In-scope query successfully searched and retrieved official documents.")
    else:
        if status != "out_of_scope" or chunks_count > 0:
            print("  [FAIL]: Expected out_of_scope with 0 chunks!")
            all_passed = False
        else:
            print("  [PASS]: Out-of-scope query successfully rejected WITHOUT searching ChromaDB.")

print("\n==================================================================")
if all_passed:
    print("ALL 5 REQUIRED STEP 2 TEST QUERIES PASSED WITH 100% SUCCESS!")
else:
    print("SOME TESTS FAILED.")
print("==================================================================")
