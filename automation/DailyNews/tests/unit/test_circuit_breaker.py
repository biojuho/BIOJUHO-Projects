"""Tests for the circuit breaker module."""

from __future__ import annotations

import time
from unittest.mock import patch

from antigravity_mcp.integrations.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_sec=10)
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_sec=10)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_opens_at_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_sec=10)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_sec=10)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == "closed"
        # Need full threshold again to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        time.sleep(0.15)
        assert cb.allow_request() is True
        assert cb.state == "half_open"

    def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # transitions to half_open
        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.allow_request()  # transitions to half_open
        cb.record_failure()
        assert cb.state == "open"

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=10)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        cb.reset()
        assert cb.state == "closed"
        assert cb.allow_request() is True
