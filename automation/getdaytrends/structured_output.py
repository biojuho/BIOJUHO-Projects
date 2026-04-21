"""
Structured LLM output helpers for getdaytrends.

This module wraps Instructor so callers can request validated Pydantic output
without caring whether the underlying backend exposes a sync or async
`create()` method.
"""

from __future__ import annotations

import inspect
import os
from typing import TypeVar

from loguru import logger as log
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_instructor_client = None
_instructor_backend: str = ""


def _get_instructor_client():
    """Initialize the Instructor client lazily."""
    global _instructor_client, _instructor_backend

    if _instructor_client is not None:
        return _instructor_client

    import instructor

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if anthropic_key:
        try:
            import anthropic

            base_client = anthropic.AsyncAnthropic(api_key=anthropic_key)
            _instructor_client = instructor.from_anthropic(base_client)
            _instructor_backend = "anthropic"
            log.info("[Instructor] Anthropic backend initialized")
            return _instructor_client
        except Exception as exc:
            log.warning(f"[Instructor] Anthropic init failed: {type(exc).__name__}: {exc}")

    if gemini_key:
        try:
            import google.genai as genai

            base_client = genai.Client(api_key=gemini_key)
            _instructor_client = instructor.from_genai(base_client)
            _instructor_backend = "gemini"
            log.info("[Instructor] Gemini backend initialized")
            return _instructor_client
        except Exception as exc:
            log.warning(f"[Instructor] Gemini init failed: {type(exc).__name__}: {exc}")

    raise RuntimeError("[Instructor] No supported LLM API key is available")


def _get_model_name(tier: str = "lightweight") -> str:
    """Pick a backend-specific model name."""
    if _instructor_backend == "gemini":
        if tier == "heavy":
            return "gemini-2.5-pro-preview-03-25"
        return "gemini-2.5-flash-preview-04-17"
    if tier == "heavy":
        return "claude-sonnet-4-6-20250514"
    return "claude-haiku-4-5-20251001"


def reset_instructor_client():
    """Reset the lazy singleton for tests."""
    global _instructor_client, _instructor_backend
    _instructor_client = None
    _instructor_backend = ""


def _log_fallback(kind: str, exc: Exception) -> None:
    """Downgrade expected Instructor retries to debug-level fallback logs."""
    message = f"[Instructor] {kind}: {type(exc).__name__}: {exc}"
    if type(exc).__name__ in {"InstructorRetryException", "ValidationError"}:
        log.debug(message)
    elif isinstance(exc, ModuleNotFoundError) and "instructor" in str(exc).lower():
        log.debug(message)
    else:
        log.warning(message)


async def _instructor_create(client, **kwargs):
    """
    Call Instructor in a backend-agnostic way.

    Some backends expose an async coroutine function, while others return a
    regular value from `create()`. We normalize both shapes here.
    """
    result = client.chat.completions.create(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def extract_structured(
    prompt: str,
    response_model: type[T],
    *,
    system: str = "",
    tier: str = "lightweight",
    max_retries: int = 2,
    max_tokens: int = 1500,
) -> T | None:
    """Return a validated structured response, or None on fallback."""
    del system

    try:
        client = _get_instructor_client()
        model = _get_model_name(tier)
        messages = [{"role": "user", "content": prompt}]

        return await _instructor_create(
            client,
            model=model,
            messages=messages,
            response_model=response_model,
            max_retries=max_retries,
            max_tokens=max_tokens,
        )
    except (RuntimeError, ConnectionError, TimeoutError) as exc:
        log.warning(f"[Instructor] Structured extract failed: {type(exc).__name__}: {exc}")
        return None
    except Exception as exc:
        _log_fallback("Structured extract fallback", exc)
        return None


async def extract_structured_list(
    prompt: str,
    item_model: type[T],
    *,
    system: str = "",
    tier: str = "lightweight",
    max_retries: int = 2,
    max_tokens: int = 3000,
    expected_count: int | None = None,
) -> list[T] | None:
    """Return a validated list response, or None on fallback."""
    del system

    class ListWrapper(BaseModel):
        items: list[item_model]  # type: ignore[valid-type]

    try:
        client = _get_instructor_client()
        model = _get_model_name(tier)
        messages = [{"role": "user", "content": prompt}]

        result = await _instructor_create(
            client,
            model=model,
            messages=messages,
            response_model=ListWrapper,
            max_retries=max_retries,
            max_tokens=max_tokens,
        )
        items = result.items

        if expected_count is not None and len(items) != expected_count:
            log.warning(f"[Instructor] List length mismatch: expected={expected_count}, got={len(items)}")

        return items
    except (RuntimeError, ConnectionError, TimeoutError) as exc:
        log.warning(f"[Instructor] List extract failed: {type(exc).__name__}: {exc}")
        return None
    except Exception as exc:
        _log_fallback("List extract fallback", exc)
        return None


class ScoringResponseItem(BaseModel):
    """Schema for trend scoring results."""

    keyword: str
    publishable: bool = True
    publishability_reason: str = ""
    corrected_keyword: str = ""
    volume_last_24h: int = 0
    trend_acceleration: str = "+0%"
    viral_potential: int = 0
    top_insight: str = ""
    why_trending: str = ""
    peak_status: str = ""
    relevance_score: int = 0
    suggested_angles: list[str] = []
    best_hook_starter: str = ""
    category: str = ""
    sentiment: str = "neutral"
    safety_flag: bool = False
    joongyeon_kick: int = 0
    joongyeon_angle: str = ""
    trigger_event: str = ""
    chain_reaction: str = ""
    why_now: str = ""
    key_positions: list[str] = []


class TweetItem(BaseModel):
    """Schema for one generated short-form post."""

    type: str = ""
    content: str
    best_posting_time: str = ""
    expected_engagement: str = ""
    reasoning: str = ""


class TweetGenerationResponse(BaseModel):
    """Schema for tweet generation output."""

    topic: str = ""
    tweets: list[TweetItem] = []


class LongPostResponse(BaseModel):
    """Schema for long-form content such as blogs."""

    topic: str = ""
    content: str = ""
    seo_keywords: list[str] = []


class ThreadResponse(BaseModel):
    """Schema for thread generation output."""

    topic: str = ""
    hook: str = ""
    tweets: list[str] = []
