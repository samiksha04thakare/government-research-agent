import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.classifier import classify
from app.graph.workflow import build_graph

test_cases = [
    ("Government", "How can a farmer apply for Kisan Credit Card?"),
    ("Agriculture", "What is the recommended method for managing pests in cotton?"),
    ("Random", "Tell me a joke"),
    ("Random", "What is 2 + 2?"),
    ("Programming", "Write a Python calculator"),
    ("Random", "What is the weather today?"),
    ("Random", "Who is Virat Kohli?"),
]

print("==================================================")
print("1. TESTING QUERY CLASSIFIER DIRECTLY")
print("==================================================")
for label, q in test_cases:
    res = classify(q)
    print(f"[{label}] '{q}'")
    print(f"  -> Category: {res.get('category')} | Reason: {res.get('reasoning')}")

print("\n==================================================")
print("2. TESTING LANGGRAPH WORKFLOW ROUTING FOR OUT-OF-SCOPE")
print("==================================================")
graph = build_graph()
out_of_scope_cases = [
    "Tell me a joke",
    "What is 2 + 2?",
    "Write a Python calculator"
]
for q in out_of_scope_cases:
    state = graph.invoke({"question": q})
    print(f"\nQuery: '{q}'")
    print(f"  Status: {state.get('status')}")
    print(f"  Final Answer: {state.get('final_answer')}")
    print(f"  Evidence chunks count: {len(state.get('evidence', []))}")
    print(f"  Citations count: {len(state.get('citations', []))}")
    assert state.get("status") == "out_of_scope", f"Expected out_of_scope, got {state.get('status')}"
    assert len(state.get("evidence", [])) == 0, f"Expected 0 evidence chunks, got {len(state.get('evidence', []))}"
    print("  => PASS: No ChromaDB search performed, returned out-of-scope response directly!")
