"""shared.resilience — Unified retry + circuit breaker decorator.

Combines exponential backoff with jitter and circuit-breaker protection
into a single, composable decorator.  Thread-safe.

Usage::

    from shared.resilience import resilient, CircuitBreaker

    notion_cb = CircuitBreaker("notion", failure_threshold=5, cooldown_sec=60)


    @resilient(max_retries=3, circuit_breaker=notion_cb)
    async def call_notion_api(page_id: str) -> dict: ...


    # Synchronous variant
    @resilient(max_retries=3, backoff_base=1.0, backoff_max=30.0)
    def call_sync_api() -> str: ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from typing import TYPE_CHECKING, Any, TypeVar

from shared.circuit_breaker import CircuitBreaker

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger("shared.resilience")

F = TypeVar("F", bound="Callable[..., Any]")

# Re-export for convenience
__all__ = ["CircuitBreaker", "resilient", "RetryExhaustedError", "CircuitOpenError"]


class RetryExhaustedError(Exception):
    """All retry attempts failed."""

    def __init__(self, last_exception: BaseException, attempts: int) -> None:
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(f"Failed after {attempts} attempts: {last_exception}")


class CircuitOpenError(Exception):
    """Circuit breaker is OPEN — request rejected."""

    def __init__(self, breaker_name: str) -> None:
        self.breaker_name = breaker_name
        super().__init__(f"Circuit breaker '{breaker_name}' is OPEN")


def _jittered_delay(base: float, attempt: int, max_delay: float) -> float:
    """Exponential backoff with full jitter (AWS-style)."""
    exp_delay = min(base * (2**attempt), max_delay)
    return random.uniform(0, exp_delay)


def _ensure_circuit_allows(circuit_breaker: CircuitBreaker | None) -> None:
    if circuit_breaker and not circuit_breaker.allow_request():
        raise CircuitOpenError(circuit_breaker.name)


def _record_circuit_success(circuit_breaker: CircuitBreaker | None) -> None:
    if circuit_breaker:
        circuit_breaker.record_success()


def _record_circuit_failure(circuit_breaker: CircuitBreaker | None) -> None:
    if circuit_breaker:
        circuit_breaker.record_failure()


def _next_retry_delay(
    *,
    func_name: str,
    attempt: int,
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
    exc: BaseException,
    on_retry: Callable[[int, BaseException], None] | None,
) -> float | None:
    total_attempts = max_retries + 1
    if attempt >= max_retries:
        logger.error(
            "%s: all %d attempts exhausted",
            func_name,
            total_attempts,
        )
        return None

    delay = _jittered_delay(backoff_base, attempt, backoff_max)
    retry_number = attempt + 1
    logger.warning(
        "%s: attempt %d/%d failed (%s), retrying in %.2fs",
        func_name,
        retry_number,
        total_attempts,
        exc,
        delay,
    )
    if on_retry:
        on_retry(retry_number, exc)
    return delay


def resilient(
    *,
    max_retries: int = 3,
    backoff_base: float = 0.5,
    backoff_max: float = 30.0,
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,),
    circuit_breaker: CircuitBreaker | None = None,
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> Callable[[F], F]:
    """Decorator: retry with exponential backoff + optional circuit breaker.

    Parameters
    ----------
    max_retries:
        Maximum number of retry attempts (0 = no retries, just circuit breaker).
    backoff_base:
        Base delay in seconds for exponential backoff.
    backoff_max:
        Maximum delay cap in seconds.
    retryable_exceptions:
        Tuple of exception types that trigger a retry.
    circuit_breaker:
        Optional CircuitBreaker instance.  If provided, the breaker gates
        entry and records success/failure automatically.
    on_retry:
        Optional callback invoked on each retry with (attempt, exception).
    """

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _ensure_circuit_allows(circuit_breaker)

                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        result = await func(*args, **kwargs)
                        _record_circuit_success(circuit_breaker)
                        return result
                    except retryable_exceptions as exc:
                        last_exc = exc
                        _record_circuit_failure(circuit_breaker)
                        delay = _next_retry_delay(
                            func_name=func.__qualname__,
                            attempt=attempt,
                            max_retries=max_retries,
                            backoff_base=backoff_base,
                            backoff_max=backoff_max,
                            exc=exc,
                            on_retry=on_retry,
                        )
                        if delay is not None:
                            await asyncio.sleep(delay)

                assert last_exc is not None  # noqa: S101  # type-narrowing before re-raise
                raise RetryExhaustedError(last_exc, max_retries + 1)

            return async_wrapper  # type: ignore[return-value]

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                _ensure_circuit_allows(circuit_breaker)

                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        result = func(*args, **kwargs)
                        _record_circuit_success(circuit_breaker)
                        return result
                    except retryable_exceptions as exc:
                        last_exc = exc
                        _record_circuit_failure(circuit_breaker)
                        delay = _next_retry_delay(
                            func_name=func.__qualname__,
                            attempt=attempt,
                            max_retries=max_retries,
                            backoff_base=backoff_base,
                            backoff_max=backoff_max,
                            exc=exc,
                            on_retry=on_retry,
                        )
                        if delay is not None:
                            time.sleep(delay)

                assert last_exc is not None  # noqa: S101  # type-narrowing before re-raise
                raise RetryExhaustedError(last_exc, max_retries + 1)

            return sync_wrapper  # type: ignore[return-value]

    return decorator
