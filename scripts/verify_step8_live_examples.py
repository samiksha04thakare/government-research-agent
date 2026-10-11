"""Generate and verify actual grounded examples in English, Hindi, and Marathi.
Uses the live FastAPI client / local_grounded_research to extract authentic responses.
"""
import json
import sys
from pathlib import Path

# Ensure root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

# Ensure utf-8 stdout on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

client = TestClient(app)

queries = [
    {
        "lang_code": "en",
        "label": "English Query (Explicit Preference)",
        "question": "What is the procedure for obtaining a Kisan Credit Card (KCC) and what is the concessional interest rate?",
        "lang_param": "en",
    },
    {
        "lang_code": "hi",
        "label": "Hindi Query (Auto-Detected / Preference)",
        "question": "किसान क्रेडिट कार्ड (KCC) प्राप्त करने की प्रक्रिया क्या है और रियायती ब्याज दर कितनी है?",
        "lang_param": "hi",
    },
    {
        "lang_code": "mr",
        "label": "Marathi Query (Auto-Detected / Preference)",
        "question": "किसान क्रेडिट कार्ड (KCC) मिळविण्याची पद्धत काय आहे आणि सवलतीचा व्याजदर किती आहे?",
        "lang_param": "mr",
    },
]

results = []
for q in queries:
    print(f"\n=======================================================")
    print(f"Executing: {q['label']}")
    print(f"Question: {q['question']}")
    print(f"=======================================================")
    
    resp = client.post("/research", json={"question": q["question"], "language": q["lang_param"]})
    assert resp.status_code == 200, f"Error: {resp.status_code}"
    data = resp.json()
    
    item = {
        "language": data.get("language"),
        "detected_language": data.get("detected_language"),
        "status": data.get("status"),
        "question": q["question"],
        "answer": data.get("answer"),
        "sources": data.get("sources"),
        "practical_steps": data.get("practical_steps"),
        "clarifying_question": data.get("clarifying_question"),
        "missing_evidence_warning": data.get("missing_evidence_warning"),
    }
    results.append(item)
    print(f"Target Language: {item['language']}")
    print(f"Detected Language: {item['detected_language']}")
    print(f"Sources Count: {len(item['sources'])}")
    print(f"Practical Steps Count: {len(item['practical_steps'])}")
    print(f"Answer Preview:\n{item['answer'][:350]}...\n")

with open("step8_example_responses.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nSuccessfully saved all 3 language responses to step8_example_responses.json!")
