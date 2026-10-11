"""Source routing and metadata filter mapping for categorized queries."""
from typing import Any

NO_DOCUMENTS_RESPONSE = (
    "No relevant official information is currently available in the indexed government sources for this category."
)

# Registry of source routes and their corresponding ChromaDB metadata filters
CATEGORY_ROUTES: dict[str, dict[str, Any]] = {
    "government_schemes": {
        "scope": "government_related",
        "has_documents": True,
        "target_categories": ["government_schemes"],
        "filter": {"category": "government_schemes"},
        "source_description": "Central & State Government Schemes, Subsidies, KCC, PM-KISAN, PMFBY",
    },
    "crop_problems": {
        "scope": "agriculture_related",
        "has_documents": True,
        "target_categories": ["crop_problems"],
        "filter": {"category": "crop_problems"},
        "source_description": "ICAR Crop Production Practices, Stress Management & Physiological Disorders",
    },
    "pest_management": {
        "scope": "agriculture_related",
        "has_documents": True,
        "target_categories": ["pest_management"],
        "filter": {"category": "pest_management"},
        "source_description": "CIBRC Integrated Pest Management & Approved Crop Protection Protocols",
    },
    "fertilizers": {
        "scope": "agriculture_related",
        "has_documents": True,
        "target_categories": ["fertilizers"],
        "filter": {"category": "fertilizers"},
        "source_description": "Soil Health Card Parameters, Fertilizer Dosage Standards & Subsidies",
    },
    "farmer_questions": {
        "scope": "agriculture_related",
        "has_documents": True,
        "target_categories": ["government_schemes"],
        "filter": {"category": "government_schemes"},
        "source_description": "Farmer Welfare, Land Records & Agricultural Credit Guidelines",
    },
    "agriculture": {
        "scope": "agriculture_related",
        "has_documents": True,
        "target_categories": ["crop_problems", "pest_management", "fertilizers", "government_schemes"],
        "filter": None,  # Broad agriculture searches across all agricultural sources
        "source_description": "General Agriculture Advisories, Agronomy & Scheme Guidelines",
    },
    "education_scholarships": {
        "scope": "government_related",
        "has_documents": True,
        "target_categories": ["education_scholarships"],
        "filter": {"category": "education_scholarships"},
        "source_description": "State & Central Scholarships, Fellowships & Educational Support Guidelines",
    },
    "jobs_recruitment": {
        "scope": "government_related",
        "has_documents": False,
        "target_categories": [],
        "filter": None,
        "source_description": "Public Sector Recruitment, Exams & Job Notifications (No indexed sources currently)",
    },
    "health": {
        "scope": "government_related",
        "has_documents": False,
        "target_categories": [],
        "filter": None,
        "source_description": "Public Health & Hospital Empanelment Guidelines (No indexed sources currently)",
    },
    "documents_certificates": {
        "scope": "government_related",
        "has_documents": False,
        "target_categories": [],
        "filter": None,
        "source_description": "Citizen Certificates & RoR Verification Portals (No indexed sources currently)",
    },
    "tax_gst": {
        "scope": "government_related",
        "has_documents": False,
        "target_categories": [],
        "filter": None,
        "source_description": "Direct/Indirect Taxation & GST Circulars (No indexed sources currently)",
    },
    "pension": {
        "scope": "government_related",
        "has_documents": False,
        "target_categories": [],
        "filter": None,
        "source_description": "Old Age, Disability & Social Security Pensions (No indexed sources currently)",
    },
    "transport": {
        "scope": "government_related",
        "has_documents": False,
        "target_categories": [],
        "filter": None,
        "source_description": "Parivahan, Driving Licence & RTO Circulars (No indexed sources currently)",
    },
    "other_government": {
        "scope": "government_related",
        "has_documents": True,
        "target_categories": ["government_schemes"],
        "filter": None,
        "source_description": "General Government & Administrative Guidelines",
    },
    "out_of_scope": {
        "scope": "out_of_scope",
        "has_documents": False,
        "target_categories": [],
        "filter": None,
        "source_description": "Non-governmental / Unrelated Topics",
    },
}


def get_route(category: str) -> dict[str, Any]:
    """Retrieve route metadata, filters, and availability for a detected category."""
    route_info = CATEGORY_ROUTES.get(category)
    if not route_info:
        # Unknown or unindexed category defaults to no indexed documents
        return {
            "category": category,
            "scope": "government_related",
            "has_documents": False,
            "target_categories": [],
            "filter": None,
            "source_description": "Unregistered category",
        }

    return {
        "category": category,
        "scope": route_info["scope"],
        "has_documents": route_info["has_documents"],
        "target_categories": route_info["target_categories"],
        "filter": route_info["filter"],
        "source_description": route_info["source_description"],
    }
