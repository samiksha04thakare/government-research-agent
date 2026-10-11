"""Official Government PDF Collector.

Workflow:
Official PDF -> PDF Text Extraction -> Clean Text -> Metadata Attachment -> [Ready for Chunking & ChromaDB]

Supports both local official PDF files and approved official government PDF URLs.
"""
import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from langchain_core.documents import Document
from pypdf import PdfReader

from app.sources.config import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    MAX_PDF_DOWNLOAD_BYTES,
    is_official_government_url,
)
from app.sources.website_collector import check_robots_allowed
from app.utils.logging import get_logger

log = get_logger("pdf_collector")


def clean_pdf_text(text: str) -> str:
    """Normalize whitespace and remove unreadable control characters from extracted PDF text."""
    if not text:
        return ""
    # Strip null bytes and non-printable characters except newlines/tabs
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", text)
    # Collapse horizontal spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_pdf_from_bytes(
    pdf_bytes: bytes,
    meta: dict[str, Any],
) -> list[Document]:
    """Extract and clean text from raw PDF bytes page-by-page with complete metadata."""
    stream = io.BytesIO(pdf_bytes)
    reader = PdfReader(stream)

    raw_pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        cleaned = clean_pdf_text(extracted)
        if cleaned:
            raw_pages.append((idx, cleaned))

    if not raw_pages:
        return []

    combined_text = "\n\n".join(text for _, text in raw_pages)
    content_hash = _compute_hash(combined_text)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    source_name = meta.get("source_name") or meta.get("title", "Official PDF Document")
    source_url = meta.get("source_url", "")
    category = meta.get("category") or "government_schemes"
    department = meta.get("department") or meta.get("authority", "Official Government Authority")
    title = meta.get("title") or "Official PDF Document"
    last_updated = meta.get("updated_date") or meta.get("publication_date") or now_str

    documents: list[Document] = []
    for page_num, page_text in raw_pages:
        doc_metadata = {
            "source_name": source_name,
            "source_url": source_url,
            "category": category,
            "department": department,
            "title": title,
            "document_type": "pdf",
            "last_checked": now_str,
            "last_updated": last_updated,
            "publication_date": meta.get("publication_date", ""),
            "updated_date": meta.get("updated_date", ""),
            "version": meta.get("version", "1.0"),
            "page": page_num,
            "page_number": page_num,
            "content_hash": content_hash,
        }
        documents.append(Document(page_content=page_text, metadata=doc_metadata))

    return documents


def collect_pdf(
    source_path_or_url: str,
    meta: dict[str, Any] | None = None,
) -> list[Document]:
    """Collect an official PDF from a local path or approved official government URL."""
    meta = meta or {}
    source_name = meta.get("source_name") or source_path_or_url
    category = meta.get("category") or "government_schemes"
    title = meta.get("title") or Path(source_path_or_url).stem

    # Check if local file exists
    local_path = Path(source_path_or_url)
    if local_path.is_file():
        try:
            pdf_bytes = local_path.read_bytes()
            meta_copy = dict(meta)
            meta_copy.setdefault("title", title)
            meta_copy.setdefault("source_url", meta.get("source_url") or str(local_path))
            docs = extract_pdf_from_bytes(pdf_bytes, meta_copy)
            log.info(
                "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: EXTRACTED | PAGES: %d",
                source_name,
                meta_copy["source_url"],
                title,
                category,
                len(docs),
            )
            return docs
        except Exception as e:
            err = f"Failed to extract local PDF: {str(e)}"
            log.error(
                "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
                source_name,
                source_path_or_url,
                title,
                category,
                err,
            )
            return []

    # If it is a URL, validate official government domain and robots.txt
    if source_path_or_url.startswith(("http://", "https://")):
        url = source_path_or_url
        if not is_official_government_url(url):
            err = f"PDF URL '{url}' is not an approved official government domain."
            log.error(
                "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
                source_name,
                url,
                title,
                category,
                err,
            )
            return []

        allowed, robot_reason = check_robots_allowed(url)
        if not allowed:
            log.warning(
                "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
                source_name,
                url,
                title,
                category,
                robot_reason,
            )
            return []

        try:
            with httpx.Client(
                timeout=DEFAULT_REQUEST_TIMEOUT * 2,
                follow_redirects=True,
                headers={"User-Agent": DEFAULT_USER_AGENT},
            ) as client:
                resp = client.get(url)
                resp.raise_for_status()
                pdf_bytes = resp.content

            if len(pdf_bytes) > MAX_PDF_DOWNLOAD_BYTES:
                err = f"PDF file size exceeds maximum allowed ({len(pdf_bytes)} > {MAX_PDF_DOWNLOAD_BYTES})"
                log.error(
                    "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
                    source_name,
                    url,
                    title,
                    category,
                    err,
                )
                return []

            meta_copy = dict(meta)
            meta_copy.setdefault("title", title)
            meta_copy["source_url"] = url
            docs = extract_pdf_from_bytes(pdf_bytes, meta_copy)
            log.info(
                "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: DOWNLOADED_AND_EXTRACTED | PAGES: %d",
                source_name,
                url,
                title,
                category,
                len(docs),
            )
            return docs
        except Exception as e:
            err = f"Failed to download/extract remote PDF: {str(e)}"
            log.error(
                "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
                source_name,
                url,
                title,
                category,
                err,
            )
            return []

    err = f"Path '{source_path_or_url}' does not exist and is not a valid URL."
    log.error(
        "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
        source_name,
        source_path_or_url,
        title,
        category,
        err,
    )
    return []
