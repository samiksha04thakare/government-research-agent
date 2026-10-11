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
from dataclasses import asdict, dataclass, field
from typing import Any

from app.sources.config import (
    SOURCE_TYPE_API,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_WEBSITE,
    SUPPORTED_CATEGORIES,
    SUPPORTED_SOURCE_TYPES,
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Default verified official government sources
DEFAULT_OFFICIAL_SOURCES: list[SourceConfig] = [
    # 1. data.gov.in (API Source)
    SourceConfig(
        source_name="data.gov.in",
        source_url="https://data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
        source_type=SOURCE_TYPE_API,
        department="Ministry of Agriculture and Farmers Welfare",
        category="agriculture",
        title="Open Government Data Platform - National Agriculture Directory",
        resource_id="9ef84268-d588-465a-a308-a864a43d0070",
        enabled=True,
    ),
    # 2. PM-KISAN Portal (Official Website)
    SourceConfig(
        source_name="PM-KISAN Portal",
        source_url="https://pmkisan.gov.in/",
        source_type=SOURCE_TYPE_WEBSITE,
        department="Department of Agriculture and Farmers Welfare (DA&FW)",
        category="government_schemes",
        title="Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) Official Portal",
        enabled=True,
    ),
    # 3. services.india.gov.in (Official Website)
    SourceConfig(
        source_name="services.india.gov.in",
        source_url="https://services.india.gov.in/service/search?category=agriculture",
        source_type=SOURCE_TYPE_WEBSITE,
        department="National Informatics Centre (NIC) / MeitY",
        category="agriculture",
        title="National Government Services Portal - Agriculture Services",
        enabled=True,
    ),
    # 4. agricoop.nic.in (Official Website)
    SourceConfig(
        source_name="agricoop.nic.in",
        source_url="https://agricoop.nic.in/en/divisiontype/agricultural-credit",
        source_type=SOURCE_TYPE_WEBSITE,
        department="Ministry of Agriculture and Farmers Welfare, Govt of India",
        category="farmer_questions",
        title="Farmer Welfare, Land Records & Agricultural Credit Guidelines",
        enabled=True,
    ),
    # 5. icar.org.in (Official Website)
    SourceConfig(
        source_name="icar.org.in",
        source_url="https://icar.org.in/",
        source_type=SOURCE_TYPE_WEBSITE,
        department="Indian Council of Agricultural Research (ICAR)",
        category="crop_problems",
        title="ICAR Crop Production Practices, Stress Management & Advisory",
        enabled=True,
    ),
    # 6. cibrc.gov.in (Official Website)
    SourceConfig(
        source_name="cibrc.gov.in",
        source_url="https://cibrc.gov.in/",
        source_type=SOURCE_TYPE_WEBSITE,
        department="Central Insecticides Board & Registration Committee (CIBRC)",
        category="pest_management",
        title="CIBRC Integrated Pest Management & Approved Crop Protection Protocols",
        enabled=True,
    ),
    # 7. soilhealth.dac.gov.in (Official Website)
    SourceConfig(
        source_name="soilhealth.dac.gov.in",
        source_url="https://soilhealth.dac.gov.in/",
        source_type=SOURCE_TYPE_WEBSITE,
        department="Department of Agriculture & Farmers Welfare",
        category="fertilizers",
        title="Soil Health Card Parameters, Fertilizer Dosage & Subsidy Norms",
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
        category: str | None = None,
        source_type: str | None = None,
    ) -> list[SourceConfig]:
        results = self._sources
        if enabled_only:
            results = [s for s in results if s.enabled]
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


# Shared global registry instance
registry = SourceRegistry()
