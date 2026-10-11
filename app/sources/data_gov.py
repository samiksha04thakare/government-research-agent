"""Open Government Data (data.gov.in) API Collector.

Provides structured ingestion for official datasets from data.gov.in.
Requires DATA_GOV_API_KEY from environment.
Does NOT invent fake data or fake URLs.
"""
import hashlib
import os
from datetime import datetime, timezone
from typing import Any
import httpx
from langchain_core.documents import Document

from app.sources.config import (
    DATA_GOV_API_KEY,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_USER_AGENT,
)
from app.utils.logging import get_logger

log = get_logger("data_gov_collector")

DATA_GOV_BASE_URL = "https://api.data.gov.in/resource"


def get_api_key() -> str:
    """Retrieve DATA_GOV_API_KEY from environment or config."""
    key = os.getenv("DATA_GOV_API_KEY", "").strip() or DATA_GOV_API_KEY
    if key in {"", "your-data-gov-key", "your-data-gov-key-here", "your-key-here"}:
        return ""
    return key


def check_api_key() -> tuple[bool, str]:
    """Check whether a valid data.gov.in API key is configured."""
    key = get_api_key()
    if not key:
        return (
            False,
            "DATA_GOV_API_KEY is not configured in .env. "
            "To enable live data.gov.in data ingestion, register at https://data.gov.in "
            "and add DATA_GOV_API_KEY=<your_api_key> to .env.",
        )
    return (True, "DATA_GOV_API_KEY is configured.")


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_data_gov_resource(
    resource_id: str,
    title: str,
    department: str,
    category: str,
    limit: int = 50,
) -> dict[str, Any]:
    """Fetch an official dataset resource from data.gov.in.

    Returns structured dict with status, message, and list of Document objects.
    If the API key is not configured, returns clear message without fake data.
    """
    has_key, msg = check_api_key()
    if not has_key:
        log.info(
            "SOURCE: data.gov.in | URL: %s/%s | DOCUMENT: %s | CATEGORY: %s | STATUS: UNCONFIGURED | %s",
            DATA_GOV_BASE_URL,
            resource_id,
            title,
            category,
            msg,
        )
        return {
            "status": "unconfigured",
            "message": msg,
            "documents": [],
            "source_name": "data.gov.in",
            "resource_id": resource_id,
        }

    api_key = get_api_key()
    endpoint = f"{DATA_GOV_BASE_URL}/{resource_id}"
    params = {
        "api-key": api_key,
        "format": "json",
        "offset": "0",
        "limit": str(limit),
    }
    source_url = f"https://data.gov.in/resource/{resource_id}"

    try:
        with httpx.Client(timeout=DEFAULT_REQUEST_TIMEOUT) as client:
            resp = client.get(
                endpoint,
                params=params,
                headers={"User-Agent": DEFAULT_USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        err_msg = f"data.gov.in API HTTP error {e.response.status_code}: {e.response.text[:200]}"
        log.error(
            "SOURCE: data.gov.in | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
            source_url,
            title,
            category,
            err_msg,
        )
        return {"status": "error", "message": err_msg, "documents": []}
    except Exception as e:
        err_msg = f"data.gov.in API request failure: {str(e)}"
        log.error(
            "SOURCE: data.gov.in | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: ERROR | ERROR: %s",
            source_url,
            title,
            category,
            err_msg,
        )
        return {"status": "error", "message": err_msg, "documents": []}

    records = data.get("records") or data.get("data") or []
    if not records:
        log.warning(
            "SOURCE: data.gov.in | URL: %s | DOCUMENT: %s | CATEGORY: %s | STATUS: EMPTY",
            source_url,
            title,
            category,
        )
        return {
            "status": "empty",
            "message": "Resource returned 0 records.",
            "documents": [],
        }

    # Format official records into readable document text
    lines = [
        f"Title: {title}",
        f"Official Authority: {department}",
        f"Source: Open Government Data Platform India (data.gov.in)",
        f"Resource ID: {resource_id}",
        f"Source URL: {source_url}",
        f"Retrieved Records Count: {len(records)}",
        "--- Official Records ---",
    ]
    for idx, rec in enumerate(records, start=1):
        lines.append(f"\n[Record {idx}]")
        if isinstance(rec, dict):
            for k, v in rec.items():
                if v is not None and str(v).strip():
                    lines.append(f"  {k}: {v}")
        else:
            lines.append(f"  {rec}")

    full_text = "\n".join(lines).strip()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content_hash = _compute_hash(full_text)

    metadata = {
        "source_name": "data.gov.in",
        "source_url": source_url,
        "category": category,
        "department": department,
        "title": title,
        "document_type": "api",
        "last_checked": now_str,
        "last_updated": data.get("updated_date") or now_str,
        "content_hash": content_hash,
    }

    doc = Document(page_content=full_text, metadata=metadata)
    return {
        "status": "success",
        "message": f"Successfully collected {len(records)} records from data.gov.in.",
        "documents": [doc],
    }
