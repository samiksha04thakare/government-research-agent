import urllib.request
import json
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def main():
    url = "http://127.0.0.1:8000/research"
    payload = {
        "question": "What is the 25% Capital Investment Subsidy Scheme in Lakshadweep and what benefits does it provide?"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        formatted = json.dumps(res_data, indent=2, ensure_ascii=False)
        with open("data/query_response.json", "w", encoding="utf-8") as f:
            f.write(formatted)
        print(formatted)

if __name__ == "__main__":
    main()
