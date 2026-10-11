import sys
from pathlib import Path
sys.path.insert(0, ".")

from app.rag.retriever import get_store
store = get_store()
res = store.get(where={"source_url": "https://agricoop.nic.in/en/divisiontype/agricultural-credit"})
print(f"Total chunks found: {len(res['ids'])}")
for i in range(len(res["ids"])):
    meta = res["metadatas"][i]
    doc = res["documents"][i]
    print(f"\n--- Chunk {i} (chunk_id={meta.get('chunk_id')}) ---")
    print(f"Metadata: {meta}")
    print(f"Text:\n{doc}\n")
