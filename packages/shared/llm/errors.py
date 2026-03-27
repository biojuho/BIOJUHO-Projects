"""shared.llm.errors - Structured error classification for LLM operations.

Inspired by GiniGen SiteAgent's InvokeError pattern.
Replaces string-matching fallback with typed error hierarchy.

Usage:
    from shared.llm.errors import classify_error, LLMError

    try:
        response = client.call(...)
    except Exception as e:
        llm_err = classify_error(e)
        if llm_err.retryable:
            # try next backend
        else:
            raise
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger("shared.llm")


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base error for all LLM operations."""

    retryable: bool = False
    error_type: str = "unknown"

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


class NetworkError(LLMError):
    """Network-level failure (timeout, connection refused)."""

    retryable = True
    error_type = "network_error"


class RateLimitError(LLMError):
    """API rate limit exceeded."""

    retryable = True
    error_type = "rate_limit"


class ServerError(LLMError):
    """Provider server error (5xx)."""

    retryable = True
    error_type = "server_error"


class AuthError(LLMError):
    """Authentication / authorization failure."""

    retryable = False
    error_type = "auth_error"


class QuotaExhaustedError(LLMError):
    """Billing quota or credit exhausted — fallback to another backend."""

    retryable = True  # retryable via different backend
    error_type = "quota_exhausted"


class ContextLengthError(LLMError):
    """Input exceeds model's context window."""

    retryable = False
    error_type = "context_length"


class ContentFilterError(LLMError):
    """Response blocked by safety / content filter."""

    retryable = False
    error_type = "content_filter"


class ModelNotFoundError(LLMError):
    """Requested model does not exist on the provider."""

    retryable = True  # retryable via fallback to next backend
    error_type = "model_not_found"


class QualityGateError(LLMError):
    """Language bridge quality gate rejected the response."""

    retryable = True  # retryable via next backend
    error_type = "quality_gate"


# ---------------------------------------------------------------------------
# Classification patterns
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern[str], type[LLMError]]] = [
    # Quota / billing
    (re.compile(r"credit balance is too low", re.I), QuotaExhaustedError),
    (re.compile(r"insufficient_quota", re.I), QuotaExhaustedError),
    (re.compile(r"billing", re.I), QuotaExhaustedError),
    (re.compile(r"quota exceeded", re.I), QuotaExhaustedError),
    (re.compile(r"resource_exhausted", re.I), QuotaExhaustedError),
    # Rate limit
    (re.compile(r"rate_limit_exceeded", re.I), RateLimitError),
    (re.compile(r"rate.?limit", re.I), RateLimitError),
    (re.compile(r"too many requests", re.I), RateLimitError),
    (re.compile(r"429", re.I), RateLimitError),
    # Auth
    (re.compile(r"authentication_error", re.I), AuthError),
    (re.compile(r"invalid api key", re.I), AuthError),
    (re.compile(r"invalid_api_key", re.I), AuthError),
    (re.compile(r"permission denied", re.I), AuthError),
    (re.compile(r"unauthorized", re.I), AuthError),
    (re.compile(r"401", re.I), AuthError),
    (re.compile(r"403", re.I), AuthError),
    # Model not found
    (re.compile(r"not_found", re.I), ModelNotFoundError),
    (re.compile(r"not found", re.I), ModelNotFoundError),
    (re.compile(r"model not found", re.I), ModelNotFoundError),
    (re.compile(r"404", re.I), ModelNotFoundError),
    # Context length
    (re.compile(r"context.?length", re.I), ContextLengthError),
    (re.compile(r"maximum.?context", re.I), ContextLengthError),
    (re.compile(r"token.?limit", re.I), ContextLengthError),
    (re.compile(r"too.?long", re.I), ContextLengthError),
    # Content filter
    (re.compile(r"content.?filter", re.I), ContentFilterError),
    (re.compile(r"safety", re.I), ContentFilterError),
    (re.compile(r"blocked", re.I), ContentFilterError),
    # Server error
    (re.compile(r"internal.?server.?error", re.I), ServerError),
    (re.compile(r"server error", re.I), ServerError),
    (re.compile(r"502", re.I), ServerError),
    (re.compile(r"503", re.I), ServerError),
    (re.compile(r"504", re.I), ServerError),
    (re.compile(r"overloaded", re.I), ServerError),
    # Network
    (re.compile(r"connection.?(refused|reset|timeout)", re.I), NetworkError),
    (re.compile(r"timeout", re.I), NetworkError),
    (re.compile(r"network", re.I), NetworkError),
    (re.compile(r"ECONNREFUSED", re.I), NetworkError),
    # DeepSeek Korean prompt errors → treat as retryable (fallback)
    (re.compile(r"invalid_request_error", re.I), QuotaExhaustedError),
    (re.compile(r"invalid request", re.I), QuotaExhaustedError),
]


def classify_error(error: Exception) -> LLMError:
    """Classify a raw exception into a typed LLMError.

    If already an LLMError, returns as-is.
    Otherwise inspects the error message against known patterns.
    """
    if isinstance(error, LLMError):
        return error

    msg = str(error)

    for pattern, error_cls in _PATTERNS:
        if pattern.search(msg):
            classified = error_cls(msg, original=error)
            log.debug("Classified error as %s: %s", error_cls.error_type, msg[:80])
            return classified

    # Unknown error — not retryable by default
    return LLMError(msg, original=error)


def is_retryable(error: Exception) -> bool:
    """Quick check: should we retry with a different backend?"""
    classified = classify_error(error)
    return classified.retryable


def should_fallback_to_next_backend(error: Exception) -> bool:
    """Determines if the error warrants fallback to the next backend in the chain.

    This replaces the old _should_fallback() string-matching approach.
    """
    classified = classify_error(error)
    # These error types should trigger backend fallback
    return isinstance(classified, (
        QuotaExhaustedError,
        RateLimitError,
        ServerError,
        NetworkError,
        ModelNotFoundError,
        QualityGateError,
    ))
