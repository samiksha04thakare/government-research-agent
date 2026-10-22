"""Official Government Source Registry.

Maintains metadata and configuration for all official sources:
- source_name
- source_url
- source_type ("api", "website", "pdf")
- department
- category
- enabled

Strictly scopes to the initial verified categories:
government_schemes, agriculture, crop_problems, pest_management, fertilizers, farmer_questions.
"""
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from app.sources.config import (
    DATA_GOV_API_KEY,
    API_SETU_API_KEY,
    SOURCE_TYPE_API,
    SOURCE_TYPE_DATASET,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_PERMITTED,
    SOURCE_TYPE_WEBSITE,
    SUPPORTED_CATEGORIES,
    SUPPORTED_SOURCE_TYPES,
    is_scraping_prohibited,
)


@dataclass
class SourceConfig:
    source_name: str
    source_url: str
    source_type: str
    department: str
    category: str
    enabled: bool = True
    title: str = ""
    resource_id: str | None = None
    local_path: str | None = None
    publication_date: str = ""
    updated_date: str = ""
    version: str = "1.0"
    auth_type: str = "none"             # "none", "api_key", "bearer_token", "permitted"
    auth_env_var: str = ""              # e.g. "DATA_GOV_API_KEY", "API_SETU_API_KEY"
    rate_limit_per_minute: int = 30
    timeout_seconds: float = 20.0
    max_retries: int = 2
    requires_authorization: bool = False

    def __post_init__(self):
        if self.source_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(f"Unsupported source_type: {self.source_type}")
        if self.category not in SUPPORTED_CATEGORIES:
            raise ValueError(
                f"Unsupported category: {self.category}. "
                f"Initially supported categories: {SUPPORTED_CATEGORIES}"
            )
        if not self.title:
            self.title = self.source_name

    @property
    def is_authorized(self) -> bool:
        """Verify whether automated access to this source is legally and technically authorized."""
        if is_scraping_prohibited(self.source_url):
            return False
        if self.auth_env_var:
            val = os.getenv(self.auth_env_var, "").strip()
            if self.requires_authorization and (not val or any(d in val.lower() for d in ["your-key", "your_key", "placeholder"])):
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_authorized"] = self.is_authorized
        return d


# Default verified official government sources
DEFAULT_OFFICIAL_SOURCES: list[SourceConfig] = [
    # 1. data.gov.in (Authorized API Source)
    SourceConfig(
        source_name="data.gov.in",
        source_url="https://data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
        source_type=SOURCE_TYPE_API,
        department="Ministry of Agriculture and Farmers Welfare",
        category="agriculture",
        title="Open Government Data Platform - National Agriculture Directory",
        resource_id="9ef84268-d588-465a-a308-a864a43d0070",
        auth_type="api_key",
        auth_env_var="DATA_GOV_API_KEY",
        enabled=True,
    ),
    # 2. API Setu / Open Government Schemes Adapter (Authorized Government API)
    SourceConfig(
        source_name="API Setu Government Schemes Adapter",
        source_url="https://apisetu.gov.in/api/schemes/catalog",
        source_type=SOURCE_TYPE_API,
        department="Ministry of Electronics and Information Technology (MeitY)",
        category="government_schemes",
        title="API Setu National Public Digital Infrastructure Catalog",
        auth_type="api_key",
        auth_env_var="API_SETU_API_KEY",
        requires_authorization=False,  # Fallback to local catalog when API key is unconfigured
        enabled=True,
    ),
    # 3. MahaPoCRA Official Downloadable Dataset (Official Dataset)
    SourceConfig(
        source_name="MahaPoCRA Agriculture DBT Catalog",
        source_url="https://dbt.mahapocra.gov.in/",
        source_type=SOURCE_TYPE_DATASET,
        department="Department of Agriculture, Government of Maharashtra",
        category="agriculture",
        title="Nanaji Deshmukh Krishi Sanjivani Prakalp (PoCRA) Direct Benefit Transfer Schemes",
        local_path="c:\\Users\\user\\Downloads\\dbt-mahapocra-gov-in-2026-10-22.csv",
        publication_date="2026-10-22",
        updated_date="2026-10-22",
        auth_type="permitted",
        enabled=True,
    ),
    # 4. MahaDBT Official State Schemes (Official Dataset)
    SourceConfig(
        source_name="MahaDBT State Welfare Schemes Catalog",
        source_url="https://mahadbt.maharashtra.gov.in/",
        source_type=SOURCE_TYPE_DATASET,
        department="Government of Maharashtra",
        category="government_schemes",
        title="MahaDBT Direct Benefit Transfer Schemes Portal",
        auth_type="permitted",
        enabled=True,
    ),
    # 5. PM-KISAN Portal (Official Website)
    SourceConfig(
        source_name="PM-KISAN Portal",
        source_url="https://pmkisan.gov.in/",
        source_type=SOURCE_TYPE_WEBSITE,
        department="Department of Agriculture and Farmers Welfare (DA&FW)",
        category="government_schemes",
        title="Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) Official Portal",
        auth_type="permitted",
        enabled=True,
    ),
    # 6. services.india.gov.in (Official Website)
    SourceConfig(
        source_name="services.india.gov.in",
        source_url="https://services.india.gov.in/service/search?category=agriculture",
        source_type=SOURCE_TYPE_WEBSITE,
        department="National Informatics Centre (NIC) / MeitY",
        category="agriculture",
        title="National Government Services Portal - Agriculture Services",
        auth_type="permitted",
        enabled=True,
    ),
    # 7. agricoop.nic.in (Official Website)
    SourceConfig(
        source_name="agricoop.nic.in",
        source_url="https://agricoop.nic.in/en/divisiontype/agricultural-credit",
        source_type=SOURCE_TYPE_WEBSITE,
        department="Ministry of Agriculture and Farmers Welfare, Govt of India",
        category="farmer_questions",
        title="Farmer Welfare, Land Records & Agricultural Credit Guidelines",
        auth_type="permitted",
        enabled=True,
    ),
    # 8. PM-KISAN Operational Guidelines (Official PDF)
    SourceConfig(
        source_name="PM-KISAN Official Guidelines",
        source_url="https://pmkisan.gov.in/Documents/PM-Kisan_Guidelines.pdf",
        source_type=SOURCE_TYPE_PDF,
        department="Ministry of Agriculture & Farmers Welfare (DAC&FW)",
        category="government_schemes",
        title="Pradhan Mantri Kisan Samman Nidhi Operational Guidelines",
        local_path="data/raw/1ed42b58950974e5.pdf",
        publication_date="2020-03-29",
        updated_date="2025-01-15",
        auth_type="permitted",
        enabled=True,
    ),
    # 9. Kisan Post Scheme Guidelines (Official PDF)
    SourceConfig(
        source_name="Kisan Post Scheme Guidelines",
        source_url="https://www.indiapost.gov.in/VAS/Pages/Content/KisanVikasPatra.aspx",
        source_type=SOURCE_TYPE_PDF,
        department="Department of Posts & Ministry of Finance",
        category="government_schemes",
        title="Kisan Post Scheme Official Guidelines",
        local_path="data/raw/89a210b145755fa9.pdf",
        publication_date="2024-01-01",
        updated_date="2025-01-15",
        auth_type="permitted",
        enabled=True,
    ),
    # 10. Maharashtra Women & Child Compendium (Official PDF / GR Source)
    SourceConfig(
        source_name="Maharashtra Women & Child Schemes Compendium",
        source_url="https://womenchild.maharashtra.gov.in/",
        source_type=SOURCE_TYPE_PDF,
        department="Department of Women and Child Development, Maharashtra",
        category="women_child",
        title="Comprehensive Compendium of Welfare Schemes for Women & Children (Sections 1-11)",
        publication_date="2024-07-01",
        updated_date="2026-10-21",
        auth_type="permitted",
        enabled=True,
    ),
]


class SourceRegistry:
    """Registry maintaining active and configured official government sources."""

    def __init__(self, sources: list[SourceConfig] | None = None):
        self._sources: list[SourceConfig] = list(sources or DEFAULT_OFFICIAL_SOURCES)

    def list_sources(
        self,
        enabled_only: bool = False,
        authorized_only: bool = False,
        category: str | None = None,
        source_type: str | None = None,
    ) -> list[SourceConfig]:
        results = self._sources
        if enabled_only:
            results = [s for s in results if s.enabled]
        if authorized_only:
            results = [s for s in results if s.is_authorized]
        if category:
            results = [s for s in results if s.category == category]
        if source_type:
            results = [s for s in results if s.source_type == source_type]
        return results

    def get_source_by_name(self, name: str) -> SourceConfig | None:
        for s in self._sources:
            if s.source_name.lower() == name.lower():
                return s
        return None

    def get_source_by_url(self, url: str) -> SourceConfig | None:
        for s in self._sources:
            if s.source_url.rstrip("/") == url.rstrip("/"):
                return s
        return None

    def add_source(self, source: SourceConfig) -> None:
        # Check if already present by URL or name
        for idx, existing in enumerate(self._sources):
            if existing.source_url == source.source_url or existing.source_name == source.source_name:
                self._sources[idx] = source
                return
        self._sources.append(source)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        s = self.get_source_by_name(name)
        if s:
            s.enabled = enabled
            return True
        return False


# Shared global registry instance
registry = SourceRegistry()
