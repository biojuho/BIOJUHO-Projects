"""Tests for shared.resilience — retry + circuit breaker decorator."""

from __future__ import annotations

import asyncio
import time

import pytest

from shared.circuit_breaker import CircuitBreaker
from shared.resilience import (
    CircuitOpenError,
    RetryExhaustedError,
    resilient,
)


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


class TestSyncResilience:
    def test_succeeds_on_first_attempt(self) -> None:
        call_count = 0

        @resilient(max_retries=3)
        def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retries_on_transient_failure(self) -> None:
        attempts: list[int] = []

        @resilient(max_retries=2, backoff_base=0.01, backoff_max=0.05)
        def flaky() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("transient")
            return "recovered"

        assert flaky() == "recovered"
        assert len(attempts) == 3

    def test_raises_retry_exhausted_after_max_attempts(self) -> None:
        @resilient(max_retries=2, backoff_base=0.01)
        def always_fail() -> str:
            raise ValueError("permanent")

        with pytest.raises(RetryExhaustedError) as exc_info:
            always_fail()

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ValueError)

    def test_respects_retryable_exceptions_filter(self) -> None:
        """Non-retryable exceptions propagate immediately."""

        @resilient(
            max_retries=3,
            retryable_exceptions=(ConnectionError,),
            backoff_base=0.01,
        )
        def type_error() -> str:
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            type_error()

    def test_circuit_breaker_integration(self) -> None:
        cb = CircuitBreaker("test-sync", failure_threshold=2, cooldown_sec=60)

        @resilient(max_retries=0, circuit_breaker=cb)
        def fail_fast() -> str:
            raise RuntimeError("fail")

        # Drive breaker to OPEN
        for _ in range(2):
            with pytest.raises(RetryExhaustedError):
                fail_fast()

        assert cb.state == "open"

        # Next call should be rejected by circuit breaker
        with pytest.raises(CircuitOpenError):
            fail_fast()

    def test_on_retry_callback_invoked(self) -> None:
        retries: list[tuple[int, BaseException]] = []

        @resilient(
            max_retries=2,
            backoff_base=0.01,
            on_retry=lambda attempt, exc: retries.append((attempt, exc)),
        )
        def flaky() -> str:
            if len(retries) < 2:
                raise ConnectionError("retry me")
            return "ok"

        assert flaky() == "ok"
        assert len(retries) == 2
        assert retries[0][0] == 1
        assert retries[1][0] == 2

    def test_zero_retries_no_backoff(self) -> None:
        """With max_retries=0, the function is called exactly once."""
        calls = 0

        @resilient(max_retries=0)
        def once() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("fail")

        with pytest.raises(RetryExhaustedError) as exc_info:
            once()

        assert calls == 1
        assert exc_info.value.attempts == 1


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestAsyncResilience:
    @pytest.mark.asyncio
    async def test_async_succeeds_first_attempt(self) -> None:
        @resilient(max_retries=2)
        async def succeed() -> str:
            return "async-ok"

        assert await succeed() == "async-ok"

    @pytest.mark.asyncio
    async def test_async_retries_on_failure(self) -> None:
        attempts: list[int] = []

        @resilient(max_retries=2, backoff_base=0.01, backoff_max=0.05)
        async def flaky() -> str:
            attempts.append(1)
            if len(attempts) < 2:
                raise ConnectionError("transient")
            return "recovered"

        assert await flaky() == "recovered"
        assert len(attempts) == 2

    @pytest.mark.asyncio
    async def test_async_exhaustion(self) -> None:
        @resilient(max_retries=1, backoff_base=0.01)
        async def always_fail() -> str:
            raise ValueError("permanent")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await always_fail()

        assert exc_info.value.attempts == 2

    @pytest.mark.asyncio
    async def test_async_circuit_breaker(self) -> None:
        cb = CircuitBreaker("test-async", failure_threshold=1, cooldown_sec=60)

        @resilient(max_retries=0, circuit_breaker=cb)
        async def fail_once() -> str:
            raise RuntimeError("boom")

        with pytest.raises(RetryExhaustedError):
            await fail_once()

        assert cb.state == "open"

        with pytest.raises(CircuitOpenError):
            await fail_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self) -> None:
        cb = CircuitBreaker("half-open", failure_threshold=1, cooldown_sec=0.05)
        call_count = 0

        @resilient(max_retries=0, circuit_breaker=cb)
        async def sometimes_fail() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise RuntimeError("first fail")
            return "recovered"

        # First call fails → OPEN
        with pytest.raises(RetryExhaustedError):
            await sometimes_fail()
        assert cb.state == "open"

        # Wait for cooldown
        await asyncio.sleep(0.1)

        # Second call succeeds via HALF_OPEN → CLOSED
        result = await sometimes_fail()
        assert result == "recovered"
        assert cb.state == "closed"
