"""shared.resilience — Unified retry + circuit breaker decorator.

Combines exponential backoff with jitter and circuit-breaker protection
into a single, composable decorator.  Thread-safe.

Usage::

    from shared.resilience import resilient, CircuitBreaker

    notion_cb = CircuitBreaker("notion", failure_threshold=5, cooldown_sec=60)

    @resilient(max_retries=3, circuit_breaker=notion_cb)
    async def call_notion_api(page_id: str) -> dict:
        ...

    # Synchronous variant
    @resilient(max_retries=3, backoff_base=1.0, backoff_max=30.0)
    def call_sync_api() -> str:
        ...
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
    exp_delay = min(base * (2 ** attempt), max_delay)
    return random.uniform(0, exp_delay)


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
                if circuit_breaker and not circuit_breaker.allow_request():
                    raise CircuitOpenError(circuit_breaker.name)

                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        result = await func(*args, **kwargs)
                        if circuit_breaker:
                            circuit_breaker.record_success()
                        return result
                    except retryable_exceptions as exc:
                        last_exc = exc
                        if circuit_breaker:
                            circuit_breaker.record_failure()
                        if attempt < max_retries:
                            delay = _jittered_delay(
                                backoff_base, attempt, backoff_max
                            )
                            logger.warning(
                                "%s: attempt %d/%d failed (%s), retrying in %.2fs",
                                func.__qualname__,
                                attempt + 1,
                                max_retries + 1,
                                exc,
                                delay,
                            )
                            if on_retry:
                                on_retry(attempt + 1, exc)
                            await asyncio.sleep(delay)
                        else:
                            logger.error(
                                "%s: all %d attempts exhausted",
                                func.__qualname__,
                                max_retries + 1,
                            )

                assert last_exc is not None
                raise RetryExhaustedError(last_exc, max_retries + 1)

            return async_wrapper  # type: ignore[return-value]

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if circuit_breaker and not circuit_breaker.allow_request():
                    raise CircuitOpenError(circuit_breaker.name)

                last_exc: BaseException | None = None
                for attempt in range(max_retries + 1):
                    try:
                        result = func(*args, **kwargs)
                        if circuit_breaker:
                            circuit_breaker.record_success()
                        return result
                    except retryable_exceptions as exc:
                        last_exc = exc
                        if circuit_breaker:
                            circuit_breaker.record_failure()
                        if attempt < max_retries:
                            delay = _jittered_delay(
                                backoff_base, attempt, backoff_max
                            )
                            logger.warning(
                                "%s: attempt %d/%d failed (%s), retrying in %.2fs",
                                func.__qualname__,
                                attempt + 1,
                                max_retries + 1,
                                exc,
                                delay,
                            )
                            if on_retry:
                                on_retry(attempt + 1, exc)
                            time.sleep(delay)
                        else:
                            logger.error(
                                "%s: all %d attempts exhausted",
                                func.__qualname__,
                                max_retries + 1,
                            )

                assert last_exc is not None
                raise RetryExhaustedError(last_exc, max_retries + 1)

            return sync_wrapper  # type: ignore[return-value]

    return decorator
