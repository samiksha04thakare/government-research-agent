from langchain_core.documents import Document

from app.rag.chunker import chunk_documents
from app.tools.source_validator import is_approved, validate_source
from app.utils.citations import build_citations


def test_approved_domains():
    assert is_approved("https://www.myscheme.gov.in/schemes/x")
    assert is_approved("https://data.gov.in/")
    assert not is_approved("https://evil-gov.in.example.com/")
    assert not is_approved("https://twitter.com/somebody")


def test_validate_source():
    v = validate_source({"source_url": "https://india.gov.in", "publication_date": "2026-01-01", "authority": "MeitY"})
    assert v == {"approved_domain": True, "has_date": True, "has_authority": True}


def test_chunking_keeps_metadata():
    doc = Document(page_content="word " * 1000, metadata={"title": "T", "page_number": 3})
    chunks = chunk_documents([doc])
    assert len(chunks) > 1
    assert all(c.metadata["title"] == "T" and c.metadata["page_number"] == 3 for c in chunks)


def test_citations_dedupe_and_cid():
    ev = [
        {"text": "a", "metadata": {"title": "A", "source_url": "u1", "page_number": 1}},
        {"text": "b", "metadata": {"title": "A", "source_url": "u1", "page_number": 1}},
        {"text": "c", "metadata": {"title": "B", "source_url": "u2", "page_number": 2}},
    ]
    cites = build_citations(ev)
    assert [c["id"] for c in cites] == [1, 2]
    assert [e["cid"] for e in ev] == [1, 1, 2]
