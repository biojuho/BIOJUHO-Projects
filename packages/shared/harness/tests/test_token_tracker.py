"""Tests for shared.harness.token_tracker — Token Budget Layer.

Tests are structured to match CRG's token-efficient design principles:
  - Budget tracking and auto-minimization
  - Gate enforcement (hard limit)
  - Session management and reporting
  - Integration with HarnessWrapper
"""

from __future__ import annotations

import pytest

from shared.harness.token_tracker import (
    DetailLevel,
    TokenBudget,
    TokenBudgetExceededError,
    TokenUsageRecord,
)


# ── Unit Tests: TokenBudget ──


class TestTokenBudgetBasics:
    """Basic budget arithmetic and state tracking."""

    def test_initial_state(self):
        budget = TokenBudget(max_tokens=10_000)
        assert budget.used_tokens == 0
        assert budget.remaining_tokens == 10_000
        assert budget.usage_ratio == 0.0
        assert budget.total_calls == 0

    def test_record_updates_counters(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("llm_generate", 1_500)
        assert budget.used_tokens == 1_500
        assert budget.remaining_tokens == 8_500
        assert budget.total_calls == 1

    def test_record_accumulates(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("llm_generate", 1_000)
        budget.record("llm_generate", 2_000)
        budget.record("web_search", 500)
        assert budget.used_tokens == 3_500
        assert budget.total_calls == 3

    def test_per_tool_tracking(self):
        budget = TokenBudget(max_tokens=50_000)
        budget.record("llm_generate", 3_000)
        budget.record("llm_generate", 2_000)
        budget.record("web_search", 500)

        summary = budget.get_summary()
        assert summary["tool_usage"]["llm_generate"] == 5_000
        assert summary["tool_usage"]["web_search"] == 500
        assert summary["tool_call_counts"]["llm_generate"] == 2
        assert summary["tool_call_counts"]["web_search"] == 1

    def test_reset_clears_all(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("llm_generate", 5_000)
        budget.force_detail_level(DetailLevel.MINIMAL)
        budget.reset()

        assert budget.used_tokens == 0
        assert budget.remaining_tokens == 10_000
        assert budget.total_calls == 0
        assert budget.get_detail_level() == DetailLevel.STANDARD


class TestDetailLevelAutoSwitch:
    """Auto-minimization based on usage thresholds."""

    def test_standard_below_threshold(self):
        budget = TokenBudget(max_tokens=10_000, minimize_threshold=0.7)
        budget.record("tool", 5_000)  # 50% — below 70%
        assert budget.get_detail_level() == DetailLevel.STANDARD
        assert budget.should_minimize() is False

    def test_minimize_at_threshold(self):
        budget = TokenBudget(max_tokens=10_000, minimize_threshold=0.7)
        budget.record("tool", 7_000)  # 70% — at threshold
        assert budget.get_detail_level() == DetailLevel.MINIMAL
        assert budget.should_minimize() is True

    def test_minimize_above_warn(self):
        budget = TokenBudget(max_tokens=10_000, warn_threshold=0.9)
        budget.record("tool", 9_500)  # 95% — above warn
        assert budget.get_detail_level() == DetailLevel.MINIMAL
        assert budget.should_minimize() is True

    def test_forced_override(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.force_detail_level(DetailLevel.FULL)
        budget.record("tool", 9_000)  # 90% — would normally minimize
        assert budget.get_detail_level() == DetailLevel.FULL

    def test_forced_minimal_always_minimize(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.force_detail_level(DetailLevel.MINIMAL)
        assert budget.should_minimize() is True  # even at 0% usage

    def test_forced_none_restores_auto(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.force_detail_level(DetailLevel.FULL)
        budget.force_detail_level(None)
        assert budget.get_detail_level() == DetailLevel.STANDARD


class TestBudgetGate:
    """Hard budget enforcement."""

    def test_gate_passes_within_budget(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("tool", 5_000)
        assert budget.gate(3_000) is True

    def test_gate_raises_on_exceed(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("tool", 8_000)
        with pytest.raises(TokenBudgetExceededError) as exc_info:
            budget.gate(5_000, tool_name="llm_generate")
        assert exc_info.value.used == 8_000
        assert exc_info.value.limit == 10_000
        assert exc_info.value.tool_name == "llm_generate"

    def test_gate_exact_boundary(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("tool", 7_000)
        assert budget.gate(3_000) is True  # exactly 10k — allowed

    def test_gate_one_over_boundary(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("tool", 7_001)
        with pytest.raises(TokenBudgetExceededError):
            budget.gate(3_000)  # 10001 > 10000

    def test_can_afford_non_raising(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("tool", 8_000)
        assert budget.can_afford(2_000) is True
        assert budget.can_afford(3_000) is False


class TestBudgetReporting:
    """Summary and top-consumer reporting."""

    def test_get_summary_structure(self):
        budget = TokenBudget(max_tokens=50_000)
        budget.record("llm_generate", 10_000)
        budget.record("web_search", 500)

        summary = budget.get_summary()
        assert summary["used_tokens"] == 10_500
        assert summary["max_tokens"] == 50_000
        assert summary["remaining_tokens"] == 39_500
        assert "usage_ratio" in summary
        assert "detail_level" in summary
        assert "should_minimize" in summary

    def test_top_consumers_sorted(self):
        budget = TokenBudget(max_tokens=100_000)
        budget.record("small_tool", 100)
        budget.record("big_tool", 10_000)
        budget.record("medium_tool", 3_000)

        top = budget.get_top_consumers(n=2)
        assert len(top) == 2
        assert top[0]["tool"] == "big_tool"
        assert top[1]["tool"] == "medium_tool"
        assert top[0]["pct_of_total"] > top[1]["pct_of_total"]

    def test_suggest_next_action_start(self):
        budget = TokenBudget(max_tokens=50_000)
        assert "START" in budget.suggest_next_action()

    def test_suggest_next_action_continue(self):
        budget = TokenBudget(max_tokens=50_000)
        budget.record("tool", 1_000)
        assert "CONTINUE" in budget.suggest_next_action()

    def test_suggest_next_action_downshift(self):
        budget = TokenBudget(max_tokens=10_000, minimize_threshold=0.7)
        budget.record("tool", 7_500)
        assert "DOWNSHIFT" in budget.suggest_next_action()

    def test_suggest_next_action_minimize(self):
        budget = TokenBudget(max_tokens=10_000, warn_threshold=0.9)
        budget.record("tool", 9_200)
        assert "MINIMIZE" in budget.suggest_next_action()

    def test_suggest_next_action_stop(self):
        budget = TokenBudget(max_tokens=10_000)
        budget.record("tool", 9_600)
        assert "STOP" in budget.suggest_next_action()


class TestEdgeCases:
    """Boundary and edge-case scenarios."""

    def test_zero_max_tokens(self):
        budget = TokenBudget(max_tokens=0)
        assert budget.usage_ratio == 1.0
        assert budget.should_minimize() is True
        with pytest.raises(TokenBudgetExceededError):
            budget.gate(1)

    def test_negative_not_possible(self):
        budget = TokenBudget(max_tokens=100)
        assert budget.remaining_tokens == 100
        budget.record("tool", 150)  # over-record
        assert budget.remaining_tokens == 0  # clamped to 0

    def test_empty_summary_no_crash(self):
        budget = TokenBudget(max_tokens=50_000)
        summary = budget.get_summary()
        assert summary["used_tokens"] == 0
        assert summary["tool_usage"] == {}
        top = budget.get_top_consumers()
        assert top == []


# ── Integration Tests: HarnessWrapper + TokenBudget ──


class TestHarnessTokenIntegration:
    """Verify TokenBudget wiring in HarnessWrapper."""

    @pytest.fixture
    def harness(self):
        from shared.harness import HarnessWrapper, HarnessConfig
        from shared.harness.constitution import Constitution, ToolPermission

        constitution = Constitution(
            agent_name="test_agent",
            tool_permissions={
                "web_search": ToolPermission(name="web_search"),
                "llm_generate": ToolPermission(name="llm_generate"),
            },
        )
        config = HarnessConfig(
            constitution=constitution,
            token_budget=TokenBudget(max_tokens=5_000),
        )
        return HarnessWrapper(config)

    def test_token_budget_accessible(self, harness):
        assert harness.token_budget is not None
        assert harness.token_budget.max_tokens == 5_000

    def test_session_summary_includes_tokens(self, harness):
        summary = harness.get_session_summary()
        assert "token_budget" in summary
        assert summary["token_budget"]["max_tokens"] == 5_000

    def test_reset_session_resets_tokens(self, harness):
        harness.token_budget.record("test", 1_000)
        harness.reset_session()
        assert harness.token_budget.used_tokens == 0

    def test_is_tool_available_with_tokens(self, harness):
        assert harness.is_tool_available("web_search", token_estimate=3_000) is True
        assert harness.is_tool_available("web_search", token_estimate=6_000) is False

    @pytest.mark.asyncio
    async def test_execute_with_token_estimate(self, harness):
        result = await harness.execute_tool(
            "web_search",
            {"query": "test"},
            token_estimate=1_000,
        )
        assert result["dry_run"] is True
        assert harness.token_budget.used_tokens == 1_000

    @pytest.mark.asyncio
    async def test_execute_token_gate_blocks(self, harness):
        # Use up most of the budget
        harness.token_budget.record("prior", 4_500)
        with pytest.raises(TokenBudgetExceededError):
            await harness.execute_tool(
                "web_search",
                {"query": "test"},
                token_estimate=1_000,
            )
        # Verify audit logged the denial
        denied = [r for r in harness.audit_logger.records if r.verdict == "denied"]
        assert len(denied) >= 1
        assert "TOKEN_BUDGET" in denied[-1].reason
