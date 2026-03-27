"""Rate limiter for Meta Graph API.

Enforces the 200 calls/hour/user rate limit introduced in 2025.
Uses a sliding-window counter with async support.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger(__name__)

# Meta Graph API limits (2025+)
MAX_CALLS_PER_HOUR = 200
WINDOW_SECONDS = 3600


class RateLimitExceeded(Exception):
    """Raised when Meta API rate limit would be exceeded."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after:.0f}s"
        )


class MetaRateLimiter:
    """Sliding-window rate limiter for Meta Graph API.

    Tracks API call timestamps and blocks requests that would exceed
    the 200 calls/hour limit. Thread-safe via asyncio.Lock.

    Usage:
        limiter = MetaRateLimiter()
        await limiter.acquire()  # blocks or raises if rate limited
        # ... make API call ...
    """

    def __init__(
        self,
        max_calls: int = MAX_CALLS_PER_HOUR,
        window: int = WINDOW_SECONDS,
        *,
        block: bool = True,
        safety_margin: float = 0.9,
    ):
        self.max_calls = max_calls
        self.window = window
        self.block = block
        # Effective limit: leave 10% margin for safety
        self._effective_limit = int(max_calls * safety_margin)
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._total_blocked = 0

    def _purge_old(self) -> None:
        """Remove timestamps outside the sliding window."""
        cutoff = time.monotonic() - self.window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    @property
    def remaining(self) -> int:
        """Number of remaining calls in current window."""
        self._purge_old()
        return max(0, self._effective_limit - len(self._timestamps))

    @property
    def usage_pct(self) -> float:
        """Current usage as percentage."""
        self._purge_old()
        return len(self._timestamps) / self._effective_limit * 100

    async def acquire(self) -> None:
        """Acquire a rate limit slot.

        If block=True (default), waits until a slot is available.
        If block=False, raises RateLimitExceeded immediately.
        """
        async with self._lock:
            self._purge_old()

            while len(self._timestamps) >= self._effective_limit:
                if not self.block:
                    oldest = self._timestamps[0]
                    retry_after = oldest + self.window - time.monotonic()
                    raise RateLimitExceeded(retry_after)

                # Wait for the oldest call to expire
                oldest = self._timestamps[0]
                wait_time = oldest + self.window - time.monotonic()
                if wait_time > 0:
                    self._total_blocked += 1
                    logger.warning(
                        "Rate limit: waiting %.1fs (usage=%d/%d, blocked=%d)",
                        wait_time,
                        len(self._timestamps),
                        self._effective_limit,
                        self._total_blocked,
                    )
                    # Release lock while waiting
                    self._lock.release()
                    await asyncio.sleep(wait_time + 0.1)
                    await self._lock.acquire()
                    self._purge_old()

            self._timestamps.append(time.monotonic())

            # Log warning at 80% usage
            if len(self._timestamps) > self._effective_limit * 0.8:
                logger.warning(
                    "Rate limit warning: %d/%d calls used (%.0f%%)",
                    len(self._timestamps),
                    self._effective_limit,
                    self.usage_pct,
                )

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        self._purge_old()
        return {
            "calls_in_window": len(self._timestamps),
            "effective_limit": self._effective_limit,
            "remaining": self.remaining,
            "usage_pct": round(self.usage_pct, 1),
            "total_blocked": self._total_blocked,
        }
