import os
from functools import lru_cache
from app.config import LLM_MODEL, GROQ_MODEL


@lru_cache(maxsize=1)
def get_llm():
    # If Groq API Key is configured, use high-speed Groq models
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key and groq_key != "your-groq-key-here":
        from langchain_groq import ChatGroq
        return ChatGroq(model=GROQ_MODEL, temperature=0, groq_api_key=groq_key)

    # Fallback to Anthropic Claude
    from langchain_anthropic import ChatAnthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return ChatAnthropic(model=LLM_MODEL, temperature=0, max_tokens=2000, api_key=anthropic_key or None)
