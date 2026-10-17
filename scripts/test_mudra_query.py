import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

q = "मुद्रा लोन के लिए आवेदन कैसे करें?"
req_data = json.dumps({"question": q, "language": "hi"}).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8000/research",
    data=req_data,
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print("=== RESULT ===")
        print(f"Status: {result.get('status')}")
        print(f"Category: {result.get('category')}")
        print(f"Scope: {result.get('scope')}")
        print(f"Language: {result.get('language')}")
        matched = result.get('matched_scheme')
        if matched:
            print(f"Matched Scheme: {matched.get('hindi_name')} ({matched.get('scheme_name')})")
            print(f"Authority: {matched.get('authority')}")
            print(f"Portal: {matched.get('official_source_url')}")
            print(f"Eligibility: {matched.get('eligibility')}")
            print(f"Benefits: {matched.get('benefits')}")
            print(f"Documents: {matched.get('documents')}")
        print(f"Sources Count: {len(result.get('sources', []))}")
        for s in result.get('sources', []):
            print(f"- {s.get('citation_number', '')} {s.get('source_title', '')} ({s.get('authority', '')})")
        print("\n=== ANSWER ===")
        print(result.get('answer'))
except Exception as e:
    print("Error:", e)
