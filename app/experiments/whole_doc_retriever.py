"""Whole-Document Retrieval Experiment (No-Chunking Architecture).

This module implements a clean, isolated whole-document retrieval experiment
without touching, altering, or deleting the production chunk-based pipeline.

Key Characteristics:
1. Separate Persistence: 'vectorstore_whole_doc/' (keeps 'vectorstore/' untouched).
2. Separate ChromaDB Collection: 'gov_docs_whole_doc'.
3. Unchunked Documents: Full document text is preserved as a single entity.
4. Complete Metadata: Preserves title, source_url, authority, department, category,
   publication_date, updated_date, last_checked, document_type, year.
5. Explicit Token Audit: Audits against embedding model max_seq_length (256 tokens)
   and explicitly reports truncation extent and information loss ratio.
6. Context Size Guard: Checks total token footprint against LLM context budget
   before answer generation.
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from langchain_chroma import Chroma
from langchain_core.documents import Document
from pypdf import PdfReader

from app.rag.embeddings import get_embeddings
from app.rag.loader import _extract_year, _infer_category
from app.tools.source_validator import validate_source

log = logging.getLogger("whole_doc_experiment")

WHOLE_DOC_CHROMA_DIR = "vectorstore_whole_doc"
WHOLE_DOC_COLLECTION = "gov_docs_whole_doc"
MAX_EMBEDDING_TOKENS = 256  # sentence-transformers/all-MiniLM-L6-v2 limit


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_document_text(text: str) -> str:
    """Clean whitespace and formatting while preserving complete text content."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def count_tokens(text: str) -> int:
    """Calculate token count using the embedding model's active tokenizer."""
    emb = get_embeddings()
    tokenizer = getattr(emb._client, "tokenizer", None)
    if tokenizer:
        return len(tokenizer.encode(text, truncation=False))
    # Fallback approximation: 1 token ~= 4 characters / 0.75 words
    return int(len(text.split()) * 1.3)


def load_whole_document(path: str | Path, meta: dict | None = None) -> Document:
    """Extract complete document text and attach complete metadata without chunking."""
    path = Path(path)
    meta = meta or {}

    dept = meta.get("department") or meta.get("authority", "unknown")
    doc_year = meta.get("year") or _extract_year(f"{meta.get('publication_date', '')} {meta.get('title', '')}")
    doc_type = meta.get("document_type") or path.suffix.lstrip(".").upper()
    source_name = meta.get("source_name") or meta.get("source") or meta.get("title", path.stem)
    category = meta.get("category") or _infer_category(meta.get("title", path.stem), dept)
    last_checked = meta.get("last_checked") or meta.get("updated_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    page_count = 1
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        page_texts = []
        for i, page in enumerate(reader.pages, start=1):
            extracted = (page.extract_text() or "").strip()
            if extracted:
                page_texts.append(f"--- Page {i} ---\n{extracted}")
        full_text = "\n\n".join(page_texts)
    elif path.suffix.lower() == ".txt":
        full_text = path.read_text(encoding="utf-8", errors="ignore")
    elif path.suffix.lower() in [".html", ".htm"]:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        full_text = BeautifulSoup(raw, "html.parser").get_text("\n")
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    cleaned = clean_document_text(full_text)
    total_tokens = count_tokens(cleaned)
    is_truncated = total_tokens > MAX_EMBEDDING_TOKENS
    loss_ratio = round(((total_tokens - MAX_EMBEDDING_TOKENS) / total_tokens) * 100, 2) if is_truncated else 0.0

    metadata = {
        "title": meta.get("title", path.stem),
        "source_name": source_name,
        "source": source_name,
        "source_url": meta.get("source_url", ""),
        "department": dept,
        "authority": dept,
        "category": category,
        "document_type": doc_type,
        "publication_date": meta.get("publication_date", ""),
        "updated_date": meta.get("updated_date", ""),
        "last_checked": last_checked,
        "year": doc_year,
        "version": meta.get("version", "1.0"),
        "page_count": page_count,
        "file_path": str(path),
        "content_hash": _hash_text(cleaned),
        "total_characters": len(cleaned),
        "total_words": len(cleaned.split()),
        "total_tokens": total_tokens,
        "max_embedding_tokens": MAX_EMBEDDING_TOKENS,
        "embedding_truncated": is_truncated,
        "estimated_token_loss_pct": loss_ratio,
        "is_whole_document": True,
    }

    if is_truncated:
        log.warning(
            "WHOLE-DOC EMBEDDING TRUNCATION: Document '%s' has %d tokens. Model max sequence length is %d. "
            "%.1f%% of document content will NOT be captured in the vector representation!",
            metadata["title"],
            total_tokens,
            MAX_EMBEDDING_TOKENS,
            loss_ratio,
        )

    return Document(page_content=cleaned, metadata=metadata)


def get_whole_doc_store() -> Chroma:
    """Return the isolated ChromaDB store for whole documents."""
    return Chroma(
        collection_name=WHOLE_DOC_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=WHOLE_DOC_CHROMA_DIR,
    )


def index_whole_documents(docs: list[Document], force: bool = False) -> int:
    """Index whole documents directly into the experimental collection."""
    store = get_whole_doc_store()
    indexed_count = 0

    for doc in docs:
        content_hash = doc.metadata.get("content_hash", "")
        if content_hash and not force:
            existing = store.get(where={"content_hash": content_hash})
            if existing and existing["ids"]:
                log.info("Document '%s' already indexed in whole-doc store, skipping.", doc.metadata.get("title"))
                continue

        # Use deterministic doc ID based on title / content hash
        doc_id = f"wholedoc_{content_hash[:16]}"
        store.add_documents([doc], ids=[doc_id])
        indexed_count += 1
        log.info(
            "Indexed whole document '%s' (Tokens: %d, Truncated: %s)",
            doc.metadata.get("title"),
            doc.metadata.get("total_tokens", 0),
            doc.metadata.get("embedding_truncated", False),
        )

    return indexed_count


def search_whole_documents(
    query: str,
    k: int = 5,
    filters: dict | None = None,
    min_score: float | None = None,
) -> list[dict[str, Any]]:
    """Retrieve whole documents along with clamped relevance scores."""
    import warnings

    store = get_whole_doc_store()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Relevance scores must be between 0 and 1")
        results = store.similarity_search_with_relevance_scores(query, k=k, filter=filters or None)

    items = []
    for doc, score in results:
        clamped_score = max(0.0, min(1.0, float(score)))
        items.append({
            "text": doc.page_content,
            "metadata": doc.metadata,
            "similarity_score": round(clamped_score, 4),
            "validation": validate_source(doc.metadata),
            "total_tokens": doc.metadata.get("total_tokens", 0),
            "embedding_truncated": doc.metadata.get("embedding_truncated", False),
            "estimated_token_loss_pct": doc.metadata.get("estimated_token_loss_pct", 0.0),
        })

    if min_score is not None:
        items = [item for item in items if item["similarity_score"] >= min_score]

    return items


def audit_context_limit(retrieved_docs: list[dict[str, Any]], max_context_budget: int = 12000) -> dict[str, Any]:
    """Audit whether retrieved whole documents fit inside the LLM context window limit.
    
    If the combined text exceeds the budget, reports that limitation explicitly
    instead of silently truncating critical evidence.
    """
    total_tokens = sum(doc.get("total_tokens", count_tokens(doc.get("text", ""))) for doc in retrieved_docs)
    exceeds = total_tokens > max_context_budget

    return {
        "total_retrieved_tokens": total_tokens,
        "max_context_budget": max_context_budget,
        "exceeds_context_limit": exceeds,
        "document_breakdown": [
            {
                "title": doc.get("metadata", {}).get("title", "Unknown"),
                "tokens": doc.get("total_tokens", 0),
                "words": len(doc.get("text", "").split()),
            }
            for doc in retrieved_docs
        ],
        "warning": (
            f"CONTEXT LIMIT RISK: Total retrieved text is {total_tokens} tokens, exceeding budget of {max_context_budget} tokens. "
            "In whole-document retrieval, full texts consume excessive prompt context."
            if exceeds else None
        ),
    }
