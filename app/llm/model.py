import os
from functools import lru_cache
from app.config import LLM_MODEL, GROQ_MODEL


@lru_cache(maxsize=1)
def get_llm():
    # If Groq API Key is configured, use high-speed Groq models
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key and not any(p in groq_key.lower() for p in ["your-groq", "your_groq", "your-key"]):
        from langchain_groq import ChatGroq
        return ChatGroq(model=GROQ_MODEL, temperature=0, groq_api_key=groq_key)

    # Fallback to Anthropic Claude
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key and not any(p in anthropic_key.lower() for p in ["your-key", "your_key"]):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=LLM_MODEL, temperature=0, max_tokens=2000, api_key=anthropic_key)

    raise ValueError("No valid GROQ_API_KEY or ANTHROPIC_API_KEY configured for LLM synthesis.")
