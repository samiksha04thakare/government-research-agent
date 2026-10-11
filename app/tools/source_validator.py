from urllib.parse import urlparse
from app.config import APPROVED_DOMAINS


def is_approved(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in APPROVED_DOMAINS)


def validate_source(metadata: dict) -> dict:
    """Small status record used by the verifier and the UI."""
    url = metadata.get("source_url", "")
    return {
        "approved_domain": is_approved(url) if url else None,
        "has_date": bool(metadata.get("publication_date") or metadata.get("updated_date")),
        "has_authority": metadata.get("authority", "unknown") != "unknown",
    }
