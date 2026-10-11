"""Fetch a page from an APPROVED government domain only. Content is untrusted data."""
import httpx
from bs4 import BeautifulSoup
from app.tools.source_validator import is_approved


def fetch_government_page(url: str, max_chars: int = 6000) -> dict | None:
    if not is_approved(url):
        return None
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True,
                      headers={"User-Agent": "GovResearchAgent/0.1 (educational project)"})
        r.raise_for_status()
    except httpx.HTTPError:
        return None  # tool failures are handled gracefully
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())[:max_chars]
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    return {"text": text, "metadata": {"title": title, "source_url": url, "authority": "gov.in",
                                       "publication_date": "", "updated_date": "", "page_number": 1}}
