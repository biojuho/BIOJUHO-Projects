"""Regression: a single backend's AuthError must fall through to the next backend.

Before this fix AuthError was retryable=False and absent from the fallback set, so a
revoked/leaked key (e.g. a Gemini 403 whose message misses the legacy substrings) aborted
the whole chain even with 5-8 valid backends remaining (the 2026-06-15 Gemini-key incident).
"""

from __future__ import annotations

from shared.llm.client import _should_fallback
from shared.llm.errors import AuthError, classify_error


def test_autherror_falls_back_to_next_backend() -> None:
    assert _should_fallback(AuthError("invalid api key")) is True


def test_raw_403_classifies_as_auth_and_falls_back() -> None:
    classified = classify_error(Exception("403 PERMISSION_DENIED: API key revoked"))
    assert isinstance(classified, AuthError)
    assert _should_fallback(Exception("403 PERMISSION_DENIED: API key revoked")) is True


def test_autherror_stays_non_retryable_on_same_backend() -> None:
    # retryable governs SAME-backend retry; it must remain False (no point retrying a bad key).
    assert AuthError("x").retryable is False
