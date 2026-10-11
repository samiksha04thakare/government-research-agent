import json
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

with open("evaluation_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Metrics:")
print(json.dumps(data.get("metrics"), indent=2))

failed = [q for q in data["query_results"] if not q["passed"]]
print(f"\nTotal failed queries: {len(failed)}")
for q in failed:
    print(f"\nID {q['id']} ({q['type']} - {q['language']}): {q['question']}")
    print(f"  Detected: {q['detected_category']} (expected {q['expected_category']}) -> routing_pass={q['routing_pass']}")
    print(f"  Status: {q['status']} (expected {q['expected_status']}) -> status_pass={q['status_pass']}")
    print(f"  Factual pass: {q['factual_pass']}, Citation pass: {q['citation_pass']}")
    if q.get('missing_claims'):
        print(f"  Missing claims: {q['missing_claims']}")
