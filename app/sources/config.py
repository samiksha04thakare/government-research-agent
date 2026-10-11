"""Official Government Data Source Configuration.

Supported official sources:
- data.gov.in (Open Government Data Platform India)
- India.gov.in (National Portal of India)
- services.india.gov.in (National Government Services Portal)
- Official government department websites (*.gov.in, *.nic.in, icar.org.in)
- Official government PDFs (Guidelines, Gazettes, Compendiums)
"""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Open Government Data (data.gov.in) API Key
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY", "").strip()

# Source Types
SOURCE_TYPE_API = "api"
SOURCE_TYPE_WEBSITE = "website"
SOURCE_TYPE_PDF = "pdf"

# Supported Source Types Set
SUPPORTED_SOURCE_TYPES = {SOURCE_TYPE_API, SOURCE_TYPE_WEBSITE, SOURCE_TYPE_PDF}

# Step 5 initial verified categories strictly supported
# (jobs, health, tax, passport, etc. are intentionally excluded until official data is indexed)
SUPPORTED_CATEGORIES = [
    "government_schemes",
    "agriculture",
    "crop_problems",
    "pest_management",
    "fertilizers",
    "farmer_questions",
]

# Official government domains approved for collection
OFFICIAL_GOVERNMENT_DOMAINS = [
    "data.gov.in",
    "api.data.gov.in",
    "india.gov.in",
    "services.india.gov.in",
    "myscheme.gov.in",
    "pmkisan.gov.in",
    "agricoop.nic.in",
    "cibrc.gov.in",
    "soilhealth.dac.gov.in",
    "agmarknet.gov.in",
    "icar.org.in",
    "indiapost.gov.in",
    "krishi.maharashtra.gov.in",
    "gov.in",
    "nic.in",
]

# HTTP collection defaults
DEFAULT_USER_AGENT = "GovResearchAgent/0.1 (+https://india.gov.in; official educational research agent)"
DEFAULT_REQUEST_TIMEOUT = 20.0
MAX_WEBSITE_CHARS = 15000
MAX_PDF_DOWNLOAD_BYTES = 25 * 1024 * 1024  # 25 MB safety limit

# Scheduler & Update Configurations (Step 6)
# Default check interval: 24 hours (configurable via UPDATE_INTERVAL_HOURS)
UPDATE_INTERVAL_HOURS = float(os.getenv("UPDATE_INTERVAL_HOURS", "24.0"))
SOURCE_MAX_RETRIES = int(os.getenv("SOURCE_MAX_RETRIES", "2"))
SOURCE_RETRY_BACKOFF_SECONDS = float(os.getenv("SOURCE_RETRY_BACKOFF_SECONDS", "2.0"))
SOURCE_TIMEOUT_SECONDS = float(os.getenv("SOURCE_TIMEOUT_SECONDS", "20.0"))
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "false").lower() in ("true", "1", "yes")


def is_official_government_url(url: str) -> bool:
    """Validate that a URL points to an authorized official government domain."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        # Disallow IP addresses or suspicious prefixes
        if hostname.replace(".", "").isdigit():
            return False
        for domain in OFFICIAL_GOVERNMENT_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                return True
        return False
    except Exception:
        return False
