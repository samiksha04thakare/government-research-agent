"""Connector stub for official portals (myScheme, data.gov.in).
Implement with each portal's official API and terms of use (doc section 10).
Do not scrape sites that prohibit automated access."""
from app.tools.web_search import fetch_government_page


def government_search(query: str, seed_urls: list[str] | None = None) -> list[dict]:
    results = []
    for url in seed_urls or []:
        page = fetch_government_page(url)
        if page:
            results.append(page)
    return results
