"""Unit tests for shared.llm.stats.CostTracker — LLM cost tracking engine.

Targets:
  1. CostTracker.record()  — cost calculation formula using MODEL_COSTS table
  2. CostTracker.get_stats()  — aggregation correctness, rounding
  3. CostTracker in-memory mode (persist=False)  — CI-safe, no file IO

These tests catch:
  - Cost formula bugs (off-by-factor of 1M division → overspend)
  - Stat aggregation drift across backends/tiers/models
  - success_rate division-by-zero on empty stats

Run:
  python -m pytest shared/tests/test_cost_tracker.py -v
"""

from __future__ import annotations

import pytest

from shared.llm.models import CostRecord, TaskTier
from shared.llm.stats import CostTracker, UsageStats


# ---------------------------------------------------------------------------
# Fixtures — all in-memory (persist=False) to avoid touching disk
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker() -> CostTracker:
    return CostTracker(persist=False)


# ===========================================================================
# 1. Cost Calculation Formula
# ===========================================================================


class TestCostCalculation:
    """Verify: cost = (in_tok * $/1M_in + out_tok * $/1M_out) / 1_000_000."""

    def test_known_model_cost(self, tracker: CostTracker):
        """claude-sonnet-4 costs ($3.0, $15.0) per 1M tokens."""
        rec = tracker.record(
            backend="anthropic",
            model="claude-sonnet-4-20250514",
            tier=TaskTier.HEAVY,
            input_tokens=1000,
            output_tokens=500,
        )
        # Expected: (1000 * 3.0 + 500 * 15.0) / 1_000_000
        #         = (3000 + 7500) / 1_000_000 = 0.0105
        assert rec.cost_usd == pytest.approx(0.0105, abs=1e-6)

    def test_free_model_costs_zero(self, tracker: CostTracker):
        """Ollama local models should cost $0."""
        rec = tracker.record(
            backend="ollama",
            model="phi3:3.8b",
            tier=TaskTier.LIGHTWEIGHT,
            input_tokens=10000,
            output_tokens=5000,
        )
        assert rec.cost_usd == 0.0

    def test_unknown_model_costs_zero(self, tracker: CostTracker):
        """Models not in MODEL_COSTS default to (0.0, 0.0)."""
        rec = tracker.record(
            backend="custom",
            model="totally-new-model-v99",
            tier=TaskTier.MEDIUM,
            input_tokens=5000,
            output_tokens=3000,
        )
        assert rec.cost_usd == 0.0

    def test_zero_tokens(self, tracker: CostTracker):
        """Zero tokens should produce zero cost."""
        rec = tracker.record(
            backend="anthropic",
            model="claude-sonnet-4-20250514",
            tier=TaskTier.HEAVY,
            input_tokens=0,
            output_tokens=0,
        )
        assert rec.cost_usd == 0.0

    def test_mini_model_cost(self, tracker: CostTracker):
        """gpt-4o-mini costs ($0.15, $0.6) per 1M tokens."""
        rec = tracker.record(
            backend="openai",
            model="gpt-4o-mini",
            tier=TaskTier.LIGHTWEIGHT,
            input_tokens=2000,
            output_tokens=1000,
        )
        # (2000 * 0.15 + 1000 * 0.6) / 1_000_000 = (300 + 600) / 1M = 0.0009
        assert rec.cost_usd == pytest.approx(0.0009, abs=1e-7)

    def test_high_volume_cost(self, tracker: CostTracker):
        """1M input tokens + 1M output tokens on claude-sonnet-4."""
        rec = tracker.record(
            backend="anthropic",
            model="claude-sonnet-4-20250514",
            tier=TaskTier.HEAVY,
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        # (1M * 3.0 + 1M * 15.0) / 1M = 18.0
        assert rec.cost_usd == pytest.approx(18.0, abs=0.01)


# ===========================================================================
# 2. Stats Aggregation
# ===========================================================================


class TestStatsAggregation:

    def test_empty_stats(self, tracker: CostTracker):
        stats = tracker.get_stats()
        assert stats.total_calls == 0
        assert stats.total_errors == 0
        assert stats.total_cost_usd == 0.0
        assert stats.success_rate == 0.0

    def test_single_call_stats(self, tracker: CostTracker):
        tracker.record(
            backend="gemini",
            model="gemini-2.5-flash-lite",
            tier=TaskTier.LIGHTWEIGHT,
            input_tokens=1000,
            output_tokens=500,
        )
        stats = tracker.get_stats()
        assert stats.total_calls == 1
        assert stats.total_errors == 0
        assert stats.calls_by_backend["gemini"] == 1
        assert stats.calls_by_tier["lightweight"] == 1

    def test_multi_backend_stats(self, tracker: CostTracker):
        """Stats should correctly separate backends and tiers."""
        tracker.record("anthropic", "claude-sonnet-4-20250514", TaskTier.HEAVY,
                        input_tokens=1000, output_tokens=200)
        tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM,
                        input_tokens=2000, output_tokens=500)
        tracker.record("gemini", "gemini-2.5-flash-lite", TaskTier.LIGHTWEIGHT,
                        input_tokens=500, output_tokens=100)

        stats = tracker.get_stats()
        assert stats.total_calls == 3
        assert stats.calls_by_backend["anthropic"] == 1
        assert stats.calls_by_backend["gemini"] == 2
        assert stats.calls_by_tier["heavy"] == 1
        assert stats.calls_by_tier["medium"] == 1
        assert stats.calls_by_tier["lightweight"] == 1

    def test_error_tracking(self, tracker: CostTracker):
        tracker.record("anthropic", "claude-sonnet-4-20250514", TaskTier.HEAVY,
                        success=True)
        tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM,
                        success=False, error="rate_limit_exceeded")
        tracker.record("openai", "gpt-4o", TaskTier.HEAVY,
                        success=False, error="billing_error")

        stats = tracker.get_stats()
        assert stats.total_calls == 3
        assert stats.total_errors == 2
        assert stats.success_rate == pytest.approx(33.3, abs=0.1)

    def test_cost_by_model_aggregation(self, tracker: CostTracker):
        """Same model called twice — costs should sum."""
        tracker.record("anthropic", "claude-sonnet-4-20250514", TaskTier.HEAVY,
                        input_tokens=1000, output_tokens=500)
        tracker.record("anthropic", "claude-sonnet-4-20250514", TaskTier.HEAVY,
                        input_tokens=1000, output_tokens=500)

        stats = tracker.get_stats()
        # Each call costs 0.0105, total = 0.021
        assert stats.cost_by_model["claude-sonnet-4-20250514"] == pytest.approx(0.021, abs=1e-5)
        assert stats.total_cost_usd == pytest.approx(0.021, abs=1e-5)

    def test_token_tracking_by_backend(self, tracker: CostTracker):
        tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM,
                        input_tokens=3000, output_tokens=1000)
        tracker.record("gemini", "gemini-2.5-flash-lite", TaskTier.LIGHTWEIGHT,
                        input_tokens=2000, output_tokens=500)

        stats = tracker.get_stats()
        assert stats.tokens_by_backend["gemini"]["input"] == 5000
        assert stats.tokens_by_backend["gemini"]["output"] == 1500


# ===========================================================================
# 3. Success Rate Edge Cases
# ===========================================================================


class TestSuccessRate:

    def test_all_success(self, tracker: CostTracker):
        for _ in range(5):
            tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM, success=True)
        assert tracker.get_stats().success_rate == 100.0

    def test_all_failures(self, tracker: CostTracker):
        for _ in range(3):
            tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM,
                            success=False, error="timeout")
        assert tracker.get_stats().success_rate == 0.0

    def test_empty_returns_zero(self, tracker: CostTracker):
        """No calls → 0.0, NOT division by zero."""
        assert tracker.get_stats().success_rate == 0.0


# ===========================================================================
# 4. Reset
# ===========================================================================


class TestReset:

    def test_reset_clears_in_memory(self, tracker: CostTracker):
        tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM,
                        input_tokens=1000, output_tokens=500)
        tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM,
                        input_tokens=1000, output_tokens=500)
        assert tracker.get_stats().total_calls == 2

        tracker.reset()
        assert tracker.get_stats().total_calls == 0
        assert tracker.get_stats().total_cost_usd == 0.0

    def test_record_after_reset(self, tracker: CostTracker):
        tracker.record("gemini", "gemini-2.5-flash", TaskTier.MEDIUM)
        tracker.reset()
        tracker.record("anthropic", "claude-sonnet-4-20250514", TaskTier.HEAVY,
                        input_tokens=500, output_tokens=100)

        stats = tracker.get_stats()
        assert stats.total_calls == 1
        assert "gemini" not in stats.calls_by_backend
        assert stats.calls_by_backend["anthropic"] == 1


# ===========================================================================
# 5. CostRecord & UsageStats Dataclass Integrity
# ===========================================================================


class TestDataclassIntegrity:

    def test_cost_record_defaults(self):
        rec = CostRecord()
        assert rec.backend == ""
        assert rec.model == ""
        assert rec.tier == TaskTier.MEDIUM
        assert rec.cost_usd == 0.0
        assert rec.success is True

    def test_usage_stats_defaults(self):
        stats = UsageStats()
        assert stats.total_calls == 0
        assert stats.calls_by_backend == {}
        assert stats.tokens_by_backend == {}
