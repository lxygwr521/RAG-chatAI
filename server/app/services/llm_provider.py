"""Central OpenRouter-backed chat LLM factory."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import settings


PLACEHOLDER_KEYS = {"", "sk-placeholder", "sk-your-key-here", "your-openrouter-api-key"}


def _openrouter_headers() -> dict[str, str] | None:
    headers: dict[str, str] = {}
    if settings.openrouter_referer:
        headers["HTTP-Referer"] = settings.openrouter_referer
    if settings.openrouter_app_name:
        headers["X-OpenRouter-Title"] = settings.openrouter_app_name
    return headers or None


def _api_key() -> str:
    key = (settings.openrouter_api_key or settings.open_router_key).strip()
    if key in PLACEHOLDER_KEYS:
        # Keep app import/startup possible; the provider will return an auth
        # error on the first real LLM call if the key is still not configured.
        return "missing-openrouter-api-key"
    return key


def create_openrouter_llm(
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.2,
) -> ChatOpenAI:
    """Create a ChatOpenAI client routed through OpenRouter."""
    kwargs = {
        "api_key": _api_key(),
        "base_url": settings.openrouter_base_url,
        "model": model or settings.openrouter_model,
        "max_tokens": max_tokens or settings.openrouter_max_tokens,
        "temperature": temperature,
    }
    headers = _openrouter_headers()
    if headers:
        kwargs["default_headers"] = headers
    return ChatOpenAI(**kwargs)


def create_light_openrouter_llm(
    *,
    max_tokens: int,
    temperature: float,
) -> ChatOpenAI:
    """Create a low-cost OpenRouter chat client for internal helper tasks."""
    return create_openrouter_llm(
        model=settings.openrouter_light_model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def create_judge_openrouter_llm(
    *,
    max_tokens: int = 1200,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """Create the OpenRouter chat client used by LLM-as-judge evaluation."""
    return create_openrouter_llm(
        model=settings.openrouter_judge_model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
