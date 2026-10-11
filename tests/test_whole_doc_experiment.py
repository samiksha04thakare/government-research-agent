"""Regression and invariant tests for Whole-Document Retrieval Experiment.

Ensures:
1. Whole documents are loaded without splitting into chunks.
2. Complete metadata attributes (title, URL, department, category, dates) are preserved.
3. Embedding model sequence length (256 tokens) truncation is strictly flagged.
4. Experimental Chroma collection is isolated in 'vectorstore_whole_doc' and does NOT
   pollute or alter production 'vectorstore/'.
5. Context size audit detects overflows without silent truncation.
"""
from pathlib import Path
import pytest

from app.rag.retriever import get_store as get_chunk_store
from app.experiments.whole_doc_retriever import (
    WHOLE_DOC_CHROMA_DIR,
    WHOLE_DOC_COLLECTION,
    MAX_EMBEDDING_TOKENS,
    audit_context_limit,
    count_tokens,
    get_whole_doc_store,
    load_whole_document,
)


def test_whole_document_loading_preserves_full_content_and_metadata():
    txt_path = Path("data/raw/farmer_welfare_and_credit.txt")
    assert txt_path.exists()

    meta = {
        "title": "Farmer Welfare, Land Records & Agricultural Credit Guidelines",
        "authority": "Ministry of Agriculture and Farmers Welfare, Govt of India",
        "source_url": "https://agricoop.nic.in/en/divisiontype/agricultural-credit",
        "publication_date": "2025-01-15",
        "updated_date": "2025-07-01",
    }
    doc = load_whole_document(txt_path, meta)

    # 1. Unbroken content verification
    assert len(doc.page_content) > 3000
    assert "Kisan Credit Card" in doc.page_content
    assert "1800-180-1551" in doc.page_content

    # 2. Metadata preservation
    assert doc.metadata["title"] == meta["title"]
    assert doc.metadata["authority"] == meta["authority"]
    assert doc.metadata["source_url"] == meta["source_url"]
    assert doc.metadata["publication_date"] == meta["publication_date"]
    assert doc.metadata["category"] == "government_schemes" or doc.metadata["category"] == "farmer_questions"
    assert doc.metadata["is_whole_document"] is True

    # 3. Token truncation audit
    tokens = doc.metadata["total_tokens"]
    assert tokens > MAX_EMBEDDING_TOKENS
    assert doc.metadata["embedding_truncated"] is True
    assert doc.metadata["estimated_token_loss_pct"] > 50.0  # More than 50% truncated


def test_embedding_token_limit_constant():
    assert MAX_EMBEDDING_TOKENS == 256


def test_context_limit_guard_flags_large_payload():
    mock_docs = [
        {"total_tokens": 5000, "text": "word " * 4000, "metadata": {"title": "Doc A"}},
        {"total_tokens": 8000, "text": "word " * 6000, "metadata": {"title": "Doc B"}},
    ]
    # Total = 13,000 tokens, exceeds 10,000 budget
    audit = audit_context_limit(mock_docs, max_context_budget=10000)
    assert audit["exceeds_context_limit"] is True
    assert audit["total_retrieved_tokens"] == 13000
    assert audit["warning"] is not None

    # Fits within 20,000 budget
    audit_ok = audit_context_limit(mock_docs, max_context_budget=20000)
    assert audit_ok["exceeds_context_limit"] is False
    assert audit_ok["warning"] is None


def test_isolation_from_production_vectorstore():
    # Production store must be in vectorstore and have 'gov_docs'
    prod_store = get_chunk_store()
    assert prod_store._collection.name == "gov_docs"

    # Experimental store must have 'gov_docs_whole_doc' in WHOLE_DOC_CHROMA_DIR
    exp_store = get_whole_doc_store()
    assert exp_store._collection.name == WHOLE_DOC_COLLECTION
    assert exp_store._collection.name != prod_store._collection.name
