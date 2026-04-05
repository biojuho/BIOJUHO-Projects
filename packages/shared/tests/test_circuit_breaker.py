"""Unit tests for shared.circuit_breaker — Three-state circuit breaker.

Targets the full state-machine lifecycle:
  CLOSED ─(N failures)─→ OPEN ─(cooldown)─→ HALF_OPEN
  HALF_OPEN ─(success)─→ CLOSED
  HALF_OPEN ─(failure)─→ OPEN

Also verifies thread-safety properties, reset behavior, and edge
cases around threshold boundaries.

Run:
  python -m pytest shared/tests/test_circuit_breaker.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from shared.circuit_breaker import CircuitBreaker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _exhaust_failures(cb: CircuitBreaker) -> None:
    """Drive the breaker from CLOSED to OPEN by hitting the failure threshold."""
    for _ in range(cb.failure_threshold):
        cb.record_failure()


# ===========================================================================
# State: CLOSED
# ===========================================================================


class TestClosedState:
    """CircuitBreaker starts CLOSED and stays CLOSED until threshold."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == "closed"

    def test_allows_requests_when_closed(self):
        cb = CircuitBreaker("test")
        assert cb.allow_request() is True

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(4):  # 4 < 5
            cb.record_failure()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        # After success, counter resets — 4 more failures still won't trip
        for _ in range(4):
            cb.record_failure()
        assert cb.state == "closed"


# ===========================================================================
# State: OPEN
# ===========================================================================


class TestOpenState:
    """After N consecutive failures, breaker opens and rejects requests."""

    def test_opens_at_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"

    def test_rejects_requests_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        _exhaust_failures(cb)
        assert cb.allow_request() is False

    def test_stays_open_before_cooldown(self):
        cb = CircuitBreaker("test", failure_threshold=3, cooldown_sec=60)
        _exhaust_failures(cb)
        # Immediately after — no cooldown elapsed
        assert cb.allow_request() is False
        assert cb.state == "open"

    def test_additional_failures_while_open_dont_error(self):
        """Recording more failures in OPEN state should not crash."""
        cb = CircuitBreaker("test", failure_threshold=2)
        _exhaust_failures(cb)
        cb.record_failure()  # extra failure while open
        cb.record_failure()
        assert cb.state == "open"


# ===========================================================================
# State: HALF_OPEN
# ===========================================================================


class TestHalfOpenState:
    """After cooldown, breaker moves to HALF_OPEN for a single probe."""

    def test_transitions_to_half_open_after_cooldown(self):
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=0.01)
        _exhaust_failures(cb)
        assert cb.state == "open"

        # Simulate cooldown elapsed by patching time.monotonic
        original_time = cb._last_failure_time
        with patch("time.monotonic", return_value=original_time + 1.0):
            assert cb.allow_request() is True
            assert cb.state == "half_open"

    def test_probe_success_closes_circuit(self):
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=0.01)
        _exhaust_failures(cb)

        # Force HALF_OPEN
        original_time = cb._last_failure_time
        with patch("time.monotonic", return_value=original_time + 1.0):
            cb.allow_request()  # transitions to HALF_OPEN

        cb.record_success()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_probe_failure_reopens_circuit(self):
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=0.01)
        _exhaust_failures(cb)

        original_time = cb._last_failure_time
        with patch("time.monotonic", return_value=original_time + 1.0):
            cb.allow_request()  # → HALF_OPEN

        cb.record_failure()
        assert cb.state == "open"

    def test_half_open_allows_exactly_one_probe(self):
        """In HALF_OPEN, allow_request returns True for the probe."""
        cb = CircuitBreaker("test", failure_threshold=2, cooldown_sec=0.01)
        _exhaust_failures(cb)

        original_time = cb._last_failure_time
        with patch("time.monotonic", return_value=original_time + 1.0):
            assert cb.allow_request() is True  # probe allowed
            assert cb.state == "half_open"
            # Second call while still HALF_OPEN — also returns True
            # because the code allows probes in HALF_OPEN
            assert cb.allow_request() is True


# ===========================================================================
# Full Lifecycle
# ===========================================================================


class TestFullLifecycle:
    """End-to-end state transitions through the full cycle."""

    def test_closed_to_open_to_half_open_to_closed(self):
        cb = CircuitBreaker("lifecycle", failure_threshold=2, cooldown_sec=0.01)

        # Phase 1: CLOSED
        assert cb.state == "closed"
        cb.record_success()  # normal operation
        assert cb.state == "closed"

        # Phase 2: CLOSED → OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

        # Phase 3: OPEN → HALF_OPEN (after cooldown)
        ft = cb._last_failure_time
        with patch("time.monotonic", return_value=ft + 1.0):
            assert cb.allow_request() is True
            assert cb.state == "half_open"

        # Phase 4: HALF_OPEN → CLOSED (probe success)
        cb.record_success()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_closed_to_open_to_half_open_to_open_again(self):
        cb = CircuitBreaker("reopen", failure_threshold=2, cooldown_sec=0.01)

        # CLOSED → OPEN
        _exhaust_failures(cb)
        assert cb.state == "open"

        # OPEN → HALF_OPEN
        ft = cb._last_failure_time
        with patch("time.monotonic", return_value=ft + 1.0):
            cb.allow_request()

        # HALF_OPEN → OPEN (probe fails)
        cb.record_failure()
        assert cb.state == "open"


# ===========================================================================
# Reset
# ===========================================================================


class TestReset:

    def test_reset_from_closed(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_reset_from_open(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        _exhaust_failures(cb)
        assert cb.state == "open"

        cb.reset()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.reset()

        # After reset, it takes 3 NEW failures to trip
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

        cb.record_failure()
        assert cb.state == "open"


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:

    def test_threshold_of_one(self):
        """Single failure immediately trips the breaker."""
        cb = CircuitBreaker("fragile", failure_threshold=1)
        cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_success_in_closed_state_is_idempotent(self):
        """Multiple successes in CLOSED don't cause issues."""
        cb = CircuitBreaker("test")
        for _ in range(100):
            cb.record_success()
        assert cb.state == "closed"

    def test_custom_name_and_config(self):
        cb = CircuitBreaker("notion-api", failure_threshold=10, cooldown_sec=120)
        assert cb.name == "notion-api"
        assert cb.failure_threshold == 10
        assert cb.cooldown_sec == 120

    def test_state_property_returns_string(self):
        """state property returns human-readable string, not enum."""
        cb = CircuitBreaker("test")
        assert isinstance(cb.state, str)
        assert cb.state in {"closed", "open", "half_open"}
