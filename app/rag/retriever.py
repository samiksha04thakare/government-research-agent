import chromadb
from functools import lru_cache
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import CHROMA_DIR
from app.rag.chunker import chunk_documents
from app.rag.embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=CHROMA_DIR)


@lru_cache(maxsize=1)
def get_store() -> Chroma:
    return Chroma(
        client=get_chroma_client(),
        collection_name="gov_docs",
        embedding_function=get_embeddings(),
    )


def index_documents(docs: list[Document], force: bool = False) -> int:
    """Chunk + embed + store. Skips content already indexed unless force=True."""
    store = get_store()
    if docs:
        content_hash = docs[0].metadata.get("content_hash", "")
        if content_hash:
            existing = store.get(where={"content_hash": content_hash})
            if existing["ids"]:
                if not force:
                    return 0
                store.delete(ids=existing["ids"])
    chunks = chunk_documents(docs)
    store.add_documents(chunks)
    return len(chunks)


def search(query: str, k: int = 5, filters: dict | None = None) -> list[Document]:
    return get_store().similarity_search(query, k=k, filter=filters or None)


def search_with_scores(query: str, k: int = 5, filters: dict | None = None) -> list[tuple[Document, float]]:
    """Retrieve chunks along with their similarity relevance scores, clamped between 0.0 and 1.0."""
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Relevance scores must be between 0 and 1")
        results = get_store().similarity_search_with_relevance_scores(query, k=k, filter=filters or None)
        return [(doc, max(0.0, min(1.0, float(score)))) for doc, score in results]


def get_retriever(k: int = 5, filters: dict | None = None):
    """Instantiate standard retriever with search_kwargs (k=5, filter)."""
    search_kwargs = {"k": k}
    if filters:
        search_kwargs["filter"] = filters
    return get_store().as_retriever(search_kwargs=search_kwargs)
