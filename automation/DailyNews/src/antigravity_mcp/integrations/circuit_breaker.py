"""Lightweight circuit breaker for external API calls (Notion, LLM providers).

States:
  CLOSED   - requests flow normally; failures are counted
  OPEN     - requests are rejected immediately; checked after cooldown
  HALF_OPEN - one probe request is allowed; success resets, failure reopens

Usage:
    breaker = CircuitBreaker("notion", failure_threshold=5, cooldown_sec=60)
    breaker.record_success()
    breaker.record_failure()
    if not breaker.allow_request():
        raise NotionAdapterError("circuit_open", ...)
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        cooldown_sec: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec

        self._state = _State.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state.value

    def allow_request(self) -> bool:
        with self._lock:
            if self._state is _State.CLOSED:
                return True
            if self._state is _State.OPEN:
                if time.monotonic() - self._last_failure_time >= self.cooldown_sec:
                    self._state = _State.HALF_OPEN
                    logger.info("Circuit %s: OPEN -> HALF_OPEN (cooldown elapsed)", self.name)
                    return True
                return False
            # HALF_OPEN: allow one probe
            return True

    def record_success(self) -> None:
        with self._lock:
            if self._state is _State.HALF_OPEN:
                logger.info("Circuit %s: HALF_OPEN -> CLOSED (probe succeeded)", self.name)
            self._state = _State.CLOSED
            self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state is _State.HALF_OPEN:
                self._state = _State.OPEN
                logger.warning("Circuit %s: HALF_OPEN -> OPEN (probe failed)", self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = _State.OPEN
                logger.warning(
                    "Circuit %s: CLOSED -> OPEN (%d consecutive failures)",
                    self.name,
                    self._failure_count,
                )

    def reset(self) -> None:
        with self._lock:
            self._state = _State.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0
