import os
from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHROMA_DIR = os.getenv("CHROMA_DIR", "vectorstore")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./research.db")
MAX_AGENT_LOOPS = int(os.getenv("MAX_AGENT_LOOPS", "2"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.25"))
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY", "")

# Only these domains may be fetched by tools (doc section 24: restrict tools to approved domains)
APPROVED_DOMAINS = [
    "india.gov.in",
    "services.india.gov.in",
    "myscheme.gov.in",
    "data.gov.in",
    "pmkisan.gov.in",
    "icar.org.in",
    "gov.in",
    "nic.in",
]
