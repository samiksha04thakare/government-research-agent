from app.rag.retriever import search_with_scores
from app.tools.source_validator import validate_source


def vector_search(query: str, k: int = 5, filters: dict | None = None, min_score: float | None = None) -> list[dict]:
    results = search_with_scores(query, k=k, filters=filters)
    items = [
        {
            "text": doc.page_content,
            "metadata": doc.metadata,
            "similarity_score": round(float(score), 4),
            "validation": validate_source(doc.metadata),
        }
        for doc, score in results
    ]
    if min_score is not None:
        items = [item for item in items if item["similarity_score"] >= min_score]
    return items
