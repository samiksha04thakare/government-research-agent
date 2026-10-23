import os
import re
import time
from functools import lru_cache
from typing import Any

from app.config import ANTHROPIC_API_KEY, GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, LLM_MODEL
from app.utils.logging import get_logger

log = get_logger("llm_model")


def normalize_groq_base_url(base_url: str | None) -> str:
    """Normalize Groq API base URL for the Groq Python SDK / ChatGroq.
    
    The official OpenAI-compatible endpoint is https://api.groq.com/openai/v1.
    The Groq SDK internally appends '/openai/v1' to its base_url, so if '/openai/v1'
    is included in the base_url, we normalize it to prevent duplicated path segments
    (e.g., /openai/v1/openai/v1/chat/completions -> 404).
    """
    if not base_url or not isinstance(base_url, str):
        return "https://api.groq.com"
    raw = base_url.strip()
    normalized = re.sub(r"/openai/v1/?$", "", raw)
    return normalized or "https://api.groq.com"


def mask_api_key(key: str | None) -> str:
    """Safely mask an API key for logs and public diagnostics."""
    if not key:
        return ""
    clean = key.strip()
    if len(clean) <= 8:
        return "gsk_***"
    return f"{clean[:4]}...{clean[-4:]}"


def parse_groq_exception(exc: Exception) -> dict[str, Any]:
    """Parse exceptions from Groq / LangChain and return structured, safe diagnostics."""
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__

    if "auth" in exc_str or "api_key" in exc_str or "401" in exc_str or "invalid api key" in exc_str or "authenticationerror" in exc_type.lower():
        return {
            "error_type": "authentication_error",
            "status_code": 401,
            "message": "Invalid or expired Groq API key. Please verify your GROQ_API_KEY at https://console.groq.com/keys.",
        }
    if "rate_limit" in exc_str or "429" in exc_str or "ratelimit" in exc_str or "rate limit" in exc_str:
        return {
            "error_type": "rate_limit_error",
            "status_code": 429,
            "message": "Groq rate limit exceeded (tokens/requests per minute). The agent will seamlessly use grounded database fallback.",
        }
    if "timeout" in exc_str or "timed out" in exc_str or "timeouterror" in exc_type.lower():
        return {
            "error_type": "timeout_error",
            "status_code": 504,
            "message": "Groq API request timed out (limit: 30s). The agent will use grounded fallback.",
        }
    if "connect" in exc_str or "connection" in exc_str or "failed to resolve" in exc_str:
        return {
            "error_type": "connection_error",
            "status_code": 502,
            "message": f"Unable to establish connection to Groq API Base URL ({GROQ_BASE_URL}).",
        }
    return {
        "error_type": "api_error",
        "status_code": 500,
        "message": f"Groq API error ({exc_type}): {str(exc)}",
    }


@lru_cache(maxsize=1)
def get_llm():
    """Instantiate and cache the configured LLM client.
    
    Prefers Groq (model: llama-3.3-70b-versatile, base_url: https://api.groq.com/openai/v1),
    with graceful fallback to Anthropic Claude or structured vector fallback.
    """
    groq_key = (os.getenv("GROQ_API_KEY", "") or GROQ_API_KEY).strip()
    if groq_key and not any(p in groq_key.lower() for p in ["your-groq", "your_groq", "your-key"]):
        from langchain_groq import ChatGroq

        model = os.getenv("GROQ_MODEL", "") or GROQ_MODEL
        base_url = os.getenv("GROQ_BASE_URL", "") or GROQ_BASE_URL
        sdk_base_url = normalize_groq_base_url(base_url)

        log.info(
            "Initializing ChatGroq: model='%s', base_url='%s' (sdk_url='%s'), masked_key='%s'",
            model,
            base_url,
            sdk_base_url,
            mask_api_key(groq_key),
        )
        return ChatGroq(
            model=model,
            temperature=0,
            groq_api_key=groq_key,
            groq_api_base=sdk_base_url,
            request_timeout=30.0,
            max_retries=2,
        )

    # Fallback to Anthropic Claude
    anthropic_key = (os.getenv("ANTHROPIC_API_KEY", "") or ANTHROPIC_API_KEY).strip()
    if anthropic_key and not any(p in anthropic_key.lower() for p in ["your-key", "your_key"]):
        from langchain_anthropic import ChatAnthropic

        log.info("Initializing ChatAnthropic: model='%s', masked_key='%s'", LLM_MODEL, mask_api_key(anthropic_key))
        return ChatAnthropic(
            model=LLM_MODEL,
            temperature=0,
            max_tokens=2000,
            api_key=anthropic_key,
            timeout=30.0,
            max_retries=2,
        )

    raise ValueError("No valid GROQ_API_KEY or ANTHROPIC_API_KEY configured for LLM synthesis.")


def test_groq_connection(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Test the Groq API connection and return diagnostic info WITHOUT exposing secrets."""
    key = (api_key or os.getenv("GROQ_API_KEY", "") or GROQ_API_KEY).strip()
    url = (base_url or os.getenv("GROQ_BASE_URL", "") or GROQ_BASE_URL).strip()
    mod = (model or os.getenv("GROQ_MODEL", "") or GROQ_MODEL).strip()
    sdk_url = normalize_groq_base_url(url)

    if not key or any(p in key.lower() for p in ["your-groq", "your_groq", "your-key"]):
        return {
            "success": False,
            "provider": "groq",
            "model": mod,
            "base_url": url,
            "has_key": False,
            "error_type": "missing_api_key",
            "message": "No valid GROQ_API_KEY configured. Please set a valid key in .env or via POST /config/api-key.",
        }

    masked = mask_api_key(key)
    t0 = time.time()
    try:
        from groq import Groq

        client = Groq(
            api_key=key,
            base_url=sdk_url,
            timeout=10.0,
            max_retries=1,
        )
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "ping"}],
            model=mod,
            max_tokens=5,
            temperature=0,
        )
        latency = round((time.time() - t0) * 1000, 2)
        return {
            "success": True,
            "provider": "groq",
            "model": mod,
            "base_url": url,
            "masked_key": masked,
            "latency_ms": latency,
            "message": f"Successfully connected to Groq API ({mod}) in {latency}ms.",
            "response_sample": response.choices[0].message.content if response.choices else "ok",
        }
    except Exception as exc:
        latency = round((time.time() - t0) * 1000, 2)
        err = parse_groq_exception(exc)
        return {
            "success": False,
            "provider": "groq",
            "model": mod,
            "base_url": url,
            "masked_key": masked,
            "latency_ms": latency,
            "error_type": err["error_type"],
            "message": err["message"],
        }
