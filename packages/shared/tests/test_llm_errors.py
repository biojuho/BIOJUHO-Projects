"""Unit tests for shared.llm.errors — LLM error classification engine.

This module is the BRAIN of the fallback chain. If classify_error()
misclassifies an error:
  - Auth error treated as retryable → infinite retry loop on wrong key
  - Quota error treated as non-retryable → pipeline dies instead of falling back
  - Network error missed → service outage not recovered

Run:
  python -m pytest shared/tests/test_llm_errors.py -v
"""

from __future__ import annotations

import pytest

from shared.llm.errors import (
    AuthError,
    ContentFilterError,
    ContextLengthError,
    LLMError,
    ModelNotFoundError,
    NetworkError,
    QuotaExhaustedError,
    QualityGateError,
    RateLimitError,
    ServerError,
    classify_error,
    is_retryable,
    should_fallback_to_next_backend,
)


# ===========================================================================
# 1. Error Hierarchy — retryable/non-retryable classification
# ===========================================================================


class TestErrorHierarchy:

    def test_base_llm_error_not_retryable(self):
        err = LLMError("unknown problem")
        assert err.retryable is False
        assert err.error_type == "unknown"

    def test_network_error_retryable(self):
        assert NetworkError.retryable is True
        assert NetworkError.error_type == "network_error"

    def test_rate_limit_retryable(self):
        assert RateLimitError.retryable is True

    def test_server_error_retryable(self):
        assert ServerError.retryable is True

    def test_auth_error_not_retryable(self):
        assert AuthError.retryable is False

    def test_context_length_not_retryable(self):
        assert ContextLengthError.retryable is False

    def test_content_filter_not_retryable(self):
        assert ContentFilterError.retryable is False

    def test_quota_exhausted_retryable(self):
        """Quota errors retry via DIFFERENT backend."""
        assert QuotaExhaustedError.retryable is True

    def test_model_not_found_retryable(self):
        assert ModelNotFoundError.retryable is True

    def test_quality_gate_retryable(self):
        assert QualityGateError.retryable is True

    def test_original_exception_preserved(self):
        orig = RuntimeError("original")
        err = NetworkError("wrapped", original=orig)
        assert err.original is orig


# ===========================================================================
# 2. classify_error — Pattern Matching
# ===========================================================================


class TestClassifyError:

    # --- Quota / Billing ---

    def test_credit_balance_low(self):
        err = classify_error(RuntimeError("Your credit balance is too low"))
        assert isinstance(err, QuotaExhaustedError)

    def test_insufficient_quota(self):
        err = classify_error(ValueError("insufficient_quota"))
        assert isinstance(err, QuotaExhaustedError)

    def test_billing_error(self):
        err = classify_error(Exception("Billing issue on account"))
        assert isinstance(err, QuotaExhaustedError)

    def test_quota_exceeded(self):
        err = classify_error(Exception("quota exceeded for model"))
        assert isinstance(err, QuotaExhaustedError)

    def test_resource_exhausted(self):
        err = classify_error(Exception("resource_exhausted"))
        assert isinstance(err, QuotaExhaustedError)

    # --- Rate Limit ---

    def test_rate_limit_exceeded(self):
        err = classify_error(Exception("rate_limit_exceeded"))
        assert isinstance(err, RateLimitError)

    def test_too_many_requests(self):
        err = classify_error(Exception("Too many requests, please slow down"))
        assert isinstance(err, RateLimitError)

    def test_429_code(self):
        err = classify_error(Exception("Error 429: rate limited"))
        assert isinstance(err, RateLimitError)

    # --- Auth ---

    def test_authentication_error(self):
        err = classify_error(Exception("authentication_error"))
        assert isinstance(err, AuthError)
        assert err.retryable is False

    def test_invalid_api_key(self):
        err = classify_error(Exception("Invalid API key provided"))
        assert isinstance(err, AuthError)

    def test_permission_denied(self):
        err = classify_error(Exception("permission denied for resource"))
        assert isinstance(err, AuthError)

    def test_unauthorized(self):
        err = classify_error(Exception("HTTP 401 Unauthorized"))
        assert isinstance(err, AuthError)

    # --- Model Not Found ---

    def test_model_not_found(self):
        err = classify_error(Exception("model not found: gpt-5-turbo"))
        assert isinstance(err, ModelNotFoundError)

    def test_not_found_generic(self):
        err = classify_error(Exception("not_found"))
        assert isinstance(err, ModelNotFoundError)

    def test_404_code(self):
        err = classify_error(Exception("Error 404"))
        assert isinstance(err, ModelNotFoundError)

    # --- Context Length ---

    def test_context_length(self):
        err = classify_error(Exception("context_length exceeded"))
        assert isinstance(err, ContextLengthError)
        assert err.retryable is False

    def test_maximum_context(self):
        err = classify_error(Exception("maximum context window is 128k"))
        assert isinstance(err, ContextLengthError)

    def test_token_limit(self):
        err = classify_error(Exception("token limit reached"))
        assert isinstance(err, ContextLengthError)

    def test_input_too_long(self):
        err = classify_error(Exception("Input is too long"))
        assert isinstance(err, ContextLengthError)

    # --- Content Filter ---

    def test_content_filter(self):
        err = classify_error(Exception("content_filter triggered"))
        assert isinstance(err, ContentFilterError)

    def test_safety_block(self):
        err = classify_error(Exception("safety system blocked"))
        assert isinstance(err, ContentFilterError)

    # --- Server Error ---

    def test_internal_server_error(self):
        err = classify_error(Exception("Internal server error"))
        assert isinstance(err, ServerError)

    def test_502_bad_gateway(self):
        err = classify_error(Exception("502 Bad Gateway"))
        assert isinstance(err, ServerError)

    def test_503_unavailable(self):
        err = classify_error(Exception("503 Service Unavailable"))
        assert isinstance(err, ServerError)

    def test_overloaded(self):
        err = classify_error(Exception("The server is overloaded"))
        assert isinstance(err, ServerError)

    # --- Network ---

    def test_connection_refused(self):
        err = classify_error(ConnectionRefusedError("Connection refused"))
        assert isinstance(err, NetworkError)

    def test_connection_timeout(self):
        err = classify_error(TimeoutError("Connection timeout"))
        assert isinstance(err, NetworkError)

    def test_timeout(self):
        err = classify_error(Exception("Request timeout after 30s"))
        assert isinstance(err, NetworkError)

    # --- DeepSeek Korean errors ---

    def test_deepseek_invalid_request(self):
        """DeepSeek Korean prompt errors should be retryable (fallback)."""
        err = classify_error(Exception("invalid_request_error"))
        assert isinstance(err, QuotaExhaustedError)
        assert err.retryable is True

    # --- Pass-through for existing LLMError ---

    def test_already_classified_passes_through(self):
        original = AuthError("already classified")
        result = classify_error(original)
        assert result is original

    # --- Unknown errors ---

    def test_unknown_error_returns_base_llm_error(self):
        err = classify_error(Exception("some totally unknown error xyz"))
        assert type(err) is LLMError
        assert err.retryable is False

    def test_preserves_original_exception(self):
        orig = ValueError("original trigger")
        err = classify_error(orig)
        assert err.original is orig


# ===========================================================================
# 3. Helper Functions
# ===========================================================================


class TestHelperFunctions:

    def test_is_retryable_for_quota(self):
        assert is_retryable(Exception("quota exceeded")) is True

    def test_is_retryable_for_auth(self):
        assert is_retryable(Exception("authentication_error")) is False

    def test_is_retryable_for_unknown(self):
        assert is_retryable(Exception("random failure")) is False

    def test_should_fallback_quota(self):
        assert should_fallback_to_next_backend(Exception("quota exceeded")) is True

    def test_should_fallback_rate_limit(self):
        assert should_fallback_to_next_backend(Exception("rate_limit_exceeded")) is True

    def test_should_fallback_server_error(self):
        assert should_fallback_to_next_backend(Exception("503 Unavailable")) is True

    def test_should_fallback_network(self):
        assert should_fallback_to_next_backend(Exception("Connection timeout")) is True

    def test_should_fallback_model_not_found(self):
        assert should_fallback_to_next_backend(Exception("model not found")) is True

    def test_should_NOT_fallback_auth(self):
        """Auth errors should NOT fallback — the key is wrong, not the backend."""
        assert should_fallback_to_next_backend(Exception("authentication_error")) is False

    def test_should_NOT_fallback_context_length(self):
        """Context too long won't be fixed by a different backend."""
        assert should_fallback_to_next_backend(Exception("context_length exceeded")) is False

    def test_should_NOT_fallback_content_filter(self):
        assert should_fallback_to_next_backend(Exception("content_filter")) is False

    def test_should_NOT_fallback_unknown(self):
        assert should_fallback_to_next_backend(Exception("random boom")) is False


# ===========================================================================
# 4. Case Insensitivity
# ===========================================================================


class TestCaseInsensitivity:
    """All patterns use re.IGNORECASE — verify it actually works."""

    def test_uppercase_rate_limit(self):
        err = classify_error(Exception("RATE_LIMIT_EXCEEDED"))
        assert isinstance(err, RateLimitError)

    def test_mixed_case_auth(self):
        err = classify_error(Exception("Authentication_Error"))
        assert isinstance(err, AuthError)

    def test_upper_model_not_found(self):
        err = classify_error(Exception("MODEL NOT FOUND"))
        assert isinstance(err, ModelNotFoundError)
