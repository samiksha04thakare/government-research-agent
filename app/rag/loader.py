"""Load PDF / HTML documents and attach metadata (doc section 11)."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from langchain_core.documents import Document
from pypdf import PdfReader

import re

ALLOWED_EXT = {".pdf", ".html", ".htm", ".txt"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_year(text: str) -> str:
    m = re.search(r"\b(20\d{2}[-–/]\d{2,4})\b", text)
    if m:
        return m.group(1).replace("–", "-")
    m_single = re.search(r"\b(20\d{2})\b", text)
    return m_single.group(1) if m_single else "2025-26"


def _infer_category(title: str, dept: str = "") -> str:
    t = f"{title} {dept}".lower()
    if any(k in t for k in ["pest", "ipm", "cibrc", "insecticide", "pesticide"]):
        return "pest_management"
    if any(k in t for k in ["fertilizer", "soil health", "urea", "nutrient"]):
        return "fertilizers"
    if any(k in t for k in ["crop", "disorder", "icar", "production practices"]):
        return "crop_problems"
    if any(k in t for k in ["scholarship", "matric", "education"]):
        return "education_scholarships"
    if any(k in t for k in ["scheme", "myscheme", "credit", "kisan", "pmfby", "kusum", "bds", "budget"]):
        return "government_schemes"
    if any(k in t for k in ["farmer"]):
        return "farmer_questions"
    return "other_government"


def load_file(path: str | Path, meta: dict | None = None) -> list[Document]:
    path = Path(path)
    if path.suffix.lower() not in ALLOWED_EXT:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    meta = meta or {}
    
    dept = meta.get("department") or meta.get("authority", "unknown")
    doc_year = meta.get("year") or _extract_year(f"{meta.get('publication_date', '')} {meta.get('title', '')}")
    doc_type = meta.get("document_type") or path.suffix.lstrip(".").upper()
    source_name = meta.get("source_name") or meta.get("source") or meta.get("title", path.name)
    category = meta.get("category") or _infer_category(meta.get("title", path.stem), dept)
    last_checked = meta.get("last_checked") or meta.get("updated_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    base = {
        "source_name": source_name,
        "source": source_name,
        "source_url": meta.get("source_url", ""),
        "category": category,
        "department": dept,
        "authority": dept,
        "title": meta.get("title", path.stem),
        "document_type": doc_type,
        "last_checked": last_checked,
        "year": doc_year,
        "publication_date": meta.get("publication_date", ""),
        "updated_date": meta.get("updated_date", ""),
        "version": meta.get("version", ""),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    docs: list[Document] = []
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                docs.append(Document(page_content=text, metadata={**base, "page": i, "page_number": i}))
    else:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = raw if path.suffix.lower() == ".txt" else BeautifulSoup(raw, "html.parser").get_text("\n")
        docs.append(Document(page_content=text.strip(), metadata={**base, "page": 1, "page_number": 1}))

    content_hash = _hash("".join(d.page_content for d in docs))
    for d in docs:
        d.metadata["content_hash"] = content_hash
    return docs
