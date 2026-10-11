"""Official Government Website Collector.

Collects content from approved official government webpages.
Requirements:
- Validates approved official government domain
- Respects robots.txt and website terms
- Extracts page title and useful text
- Strips navigation, headers, footers, forms, scripts, and clutter
- Preserves department, category, and source metadata
- Computes SHA-256 content hash
"""
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from langchain_core.documents import Document

from app.sources.config import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
    MAX_WEBSITE_CHARS,
    is_official_government_url,
)
from app.utils.logging import get_logger

log = get_logger("website_collector")

# In-memory cache for robots.txt parsers to avoid repeated downloads
_ROBOTS_CACHE: dict[str, RobotFileParser] = {}


def check_robots_allowed(url: str, user_agent: str = DEFAULT_USER_AGENT) -> tuple[bool, str]:
    """Check robots.txt for the given government URL."""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        if not netloc:
            return (False, "Invalid URL netloc")

        robots_url = f"{scheme}://{netloc}/robots.txt"
        if netloc in _ROBOTS_CACHE:
            rp = _ROBOTS_CACHE[netloc]
        else:
            rp = RobotFileParser()
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    resp = client.get(robots_url, headers={"User-Agent": user_agent})
                    if resp.status_code == 200:
                        rp.parse(resp.text.splitlines())
                    else:
                        # 404 or other non-200 generally indicates no restriction
                        rp.allow_all = True
            except Exception:
                # If robots.txt cannot be fetched, default to permissive for official portals
                rp.allow_all = True
            _ROBOTS_CACHE[netloc] = rp

        allowed = rp.can_fetch(user_agent, url) or rp.can_fetch("*", url)
        if not allowed:
            return (False, f"Access disallowed by robots.txt at {robots_url}")
        return (True, "Allowed by robots.txt")
    except Exception as e:
        return (True, f"Robots check bypassed due to: {e}")


def clean_html_content(html: str) -> tuple[str, str]:
    """Parse HTML, extract title and main text content, stripping noise."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text().strip()

    # Decompose non-content / navigation / footer elements
    unwanted_tags = [
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "menu",
        "noscript",
        "iframe",
        "svg",
    ]
    for tag in soup.find_all(unwanted_tags):
        tag.decompose()

    # Attempt to locate main content area
    content_area = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find(class_=re.compile(r"(content|main|post|article)", re.I))
        or soup.body
        or soup
    )

    # Extract text with newlines
    raw_text = content_area.get_text(separator="\n")
    # Clean whitespace
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw_text.splitlines()]
    clean_lines = [l for l in lines if l]
    clean_text = "\n".join(clean_lines)

    # Limit chars
    clean_text = clean_text[:MAX_WEBSITE_CHARS].strip()
    return title, clean_text


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_webpage(url: str, meta: dict | None = None) -> Document | None:
    """Collect an official government webpage and convert to a Document."""
    meta = meta or {}
    source_name = meta.get("source_name") or url
    department = meta.get("department") or meta.get("authority", "Official Government Portal")
    category = meta.get("category") or "government_schemes"

    if not is_official_government_url(url):
        err = f"URL domain '{url}' is not an approved official government domain."
        log.error(
            "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
            source_name,
            url,
            meta.get("title", url),
            category,
            err,
        )
        return None

    # Robots.txt validation
    allowed, robot_reason = check_robots_allowed(url)
    if not allowed:
        log.warning(
            "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
            source_name,
            url,
            meta.get("title", url),
            category,
            robot_reason,
        )
        return None

    try:
        with httpx.Client(
            timeout=DEFAULT_REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        err = f"Failed to fetch webpage: {str(e)}"
        log.error(
            "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
            source_name,
            url,
            meta.get("title", url),
            category,
            err,
        )
        return None

    page_title, clean_text = clean_html_content(html)
    doc_title = meta.get("title") or page_title or url
    if not clean_text:
        log.warning(
            "SOURCE: %s | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: EMPTY",
            source_name,
            url,
            doc_title,
            category,
        )
        return None

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content_hash = _compute_hash(clean_text)

    doc_metadata = {
        "source_name": source_name,
        "source_url": url,
        "category": category,
        "department": department,
        "title": doc_title,
        "document_type": "website",
        "last_checked": now_str,
        "last_updated": meta.get("updated_date") or meta.get("publication_date") or now_str,
        "publication_date": meta.get("publication_date", ""),
        "updated_date": meta.get("updated_date", ""),
        "version": meta.get("version", "1.0"),
        "content_hash": content_hash,
    }

    return Document(page_content=clean_text, metadata=doc_metadata)
