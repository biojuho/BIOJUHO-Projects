"""Edge-case & regression tests for shared.harness — Risk Scanner deep
input flattening and HarnessWrapper executor failure / cost tracking.

Targets:
  1. RiskScanner._flatten_input  — the recursive serializer that turns
     arbitrary nested structures into a scannable string. A bypass here
     means an injection that slips past the security gate.
  2. HarnessWrapper.execute_tool — cost_estimate accumulation and
     executor-crash audit logging path.

Run:
  python -m pytest shared/harness/tests/test_risk_and_pipeline_edge_cases.py -v
"""

from __future__ import annotations

import pytest

from shared.harness.audit import AuditLogger, AuditVerdict
from shared.harness.constitution import Constitution, ToolPermission
from shared.harness.core import HarnessConfig, HarnessWrapper
from shared.harness.errors import (
    BudgetExceededError,
    RiskDetectedError,
    SessionLimitError,
    ToolNotAllowedError,
)
from shared.harness.hooks import (
    HookChain,
    InputSanitizerHook,
    OutputTruncatorHook,
    PreToolHook,
)
from shared.harness.risk import RiskResult, RiskScanner
from typing import Any


# ---------------------------------------------------------------------------
# Shared factories
# ---------------------------------------------------------------------------


def _make_constitution(**overrides) -> Constitution:
    data = {
        "agent_name": "edge-test-agent",
        "max_budget_usd": 1.0,
        "tools": [
            {"name": "web_search", "allowed": True, "max_calls": 10},
            {"name": "shell_execute", "allowed": True, "max_calls": 2,
             "blocked_patterns": [r"rm\s+-rf"]},
            {"name": "file_write", "allowed": True, "max_calls": 5,
             "allowed_paths": ["d:/project/**"]},
        ],
        "risk_patterns": [r"TRUNCATE\s+TABLE"],
    }
    data.update(overrides)
    return Constitution.from_dict(data)


def _make_harness(constitution=None, **kw) -> HarnessWrapper:
    c = constitution or _make_constitution()
    config = HarnessConfig(constitution=c, **kw)
    return HarnessWrapper(config)


async def _noop_executor(tool_name: str, tool_input) -> dict:
    return {"tool": tool_name, "result": "ok"}


async def _crashing_executor(tool_name: str, tool_input) -> dict:
    raise RuntimeError("Simulated executor crash")


# ===================================================================
# 1. RiskScanner._flatten_input — Deep / Exotic Input Coverage
# ===================================================================


class TestRiskScannerFlattenInput:
    """Verify that _flatten_input correctly serializes all input shapes
    so that risk patterns can never be smuggled past the scanner."""

    def _scanner(self) -> RiskScanner:
        return RiskScanner(_make_constitution())

    # --- Deep nesting ---

    def test_deeply_nested_dict(self):
        """Risk pattern buried 5 levels deep must still be detected."""
        scanner = self._scanner()
        payload = {"a": {"b": {"c": {"d": {"e": "rm -rf /"}}}}}
        result = scanner.scan("shell_execute", payload)
        assert result.is_risky, "Deeply nested dangerous input was not caught"

    def test_deeply_nested_list(self):
        """Risk pattern inside nested list-of-lists."""
        scanner = self._scanner()
        payload = [[[["eval(exploit)"]]]]
        result = scanner.scan("web_search", payload)
        assert result.is_risky

    def test_mixed_dict_list_nesting(self):
        """Dict containing lists containing dicts — realistic payload shape."""
        scanner = self._scanner()
        payload = {
            "commands": [
                {"cmd": "echo hello"},
                {"cmd": "safe command"},
                {"cmd": "os.system('hack')"},
            ]
        }
        result = scanner.scan("web_search", payload)
        assert result.is_risky
        assert "unsafe_os_system" in result.risk_category

    # --- Non-string primitives ---

    def test_integer_input_does_not_crash(self):
        scanner = self._scanner()
        result = scanner.scan("web_search", 42)
        assert not result.is_risky

    def test_none_input_does_not_crash(self):
        scanner = self._scanner()
        result = scanner.scan("web_search", None)
        assert not result.is_risky

    def test_boolean_input(self):
        scanner = self._scanner()
        result = scanner.scan("web_search", True)
        assert not result.is_risky

    def test_float_input(self):
        scanner = self._scanner()
        result = scanner.scan("web_search", 3.14)
        assert not result.is_risky

    # --- Tuple inputs ---

    def test_tuple_input(self):
        scanner = self._scanner()
        result = scanner.scan("web_search", ("safe", "eval(bad)"))
        assert result.is_risky

    # --- Empty containers ---

    def test_empty_dict(self):
        scanner = self._scanner()
        result = scanner.scan("web_search", {})
        assert not result.is_risky

    def test_empty_list(self):
        scanner = self._scanner()
        result = scanner.scan("web_search", [])
        assert not result.is_risky

    # --- Constitution-level patterns on nested input ---

    def test_constitution_pattern_in_nested_input(self):
        """Custom constitution risk_pattern must also match nested inputs."""
        scanner = self._scanner()
        payload = {"query": {"sub": "TRUNCATE TABLE users"}}
        result = scanner.scan("web_search", payload)
        assert result.is_risky
        assert "constitution:" in result.risk_category

    # --- Tool-specific blocked patterns on flattened input ---

    def test_tool_blocked_pattern_on_nested_input(self):
        """shell_execute has blocked_patterns ['rm\\s+-rf']. Verify it
        catches nested input too."""
        scanner = self._scanner()
        payload = {"args": ["-v", "rm -rf /"]}
        result = scanner.scan("shell_execute", payload)
        assert result.is_risky

    # --- Extra patterns ---

    def test_extra_patterns(self):
        scanner = RiskScanner(
            _make_constitution(),
            extra_patterns=[("CUSTOM_DANGER", "custom_risk")],
        )
        result = scanner.scan("web_search", "contains CUSTOM_DANGER keyword")
        assert result.is_risky
        assert result.risk_category == "custom_risk"

    # --- Safe result factory ---

    def test_safe_result_factory(self):
        safe = RiskResult.safe(text_length=100)
        assert not safe.is_risky
        assert safe.scanned_text_length == 100
        assert safe.matched_pattern == ""


# ===================================================================
# 2. HarnessWrapper — Executor Crash, Cost, and Audit Edge Cases
# ===================================================================


class TestHarnessExecutorCrash:
    """Verify that when the tool executor itself throws, the harness:
     - Logs an ERROR audit record (not ALLOWED/DENIED)
     - Re-raises the original exception
     - Does NOT increment call counters or cost
    """

    @pytest.mark.asyncio
    async def test_executor_exception_is_reraised(self):
        harness = _make_harness(tool_executor=_crashing_executor)
        with pytest.raises(RuntimeError, match="Simulated"):
            await harness.execute_tool("web_search", {"q": "test"})

    @pytest.mark.asyncio
    async def test_executor_crash_logs_error_audit(self):
        harness = _make_harness(tool_executor=_crashing_executor)
        try:
            await harness.execute_tool("web_search", {"q": "test"})
        except RuntimeError:
            pass

        audit = harness.audit_logger
        assert audit.total_count == 1
        error_records = [r for r in audit.records if r.verdict == AuditVerdict.ERROR]
        assert len(error_records) == 1
        assert "RuntimeError" in error_records[0].reason

    @pytest.mark.asyncio
    async def test_executor_crash_does_not_increment_counters(self):
        """Counters must remain at 0 after a failed execution."""
        harness = _make_harness(tool_executor=_crashing_executor)
        try:
            await harness.execute_tool("web_search", {"q": "test"})
        except RuntimeError:
            pass

        assert harness.total_calls == 0
        assert harness.session_cost == 0.0
        summary = harness.get_session_summary()
        assert summary["tool_call_counts"] == {}


class TestHarnessCostTracking:
    """Verify cost_estimate parameter integrates correctly with budget gating."""

    @pytest.mark.asyncio
    async def test_cost_accumulates_across_calls(self):
        harness = _make_harness(tool_executor=_noop_executor)
        await harness.execute_tool("web_search", {"q": "1"}, cost_estimate=0.10)
        await harness.execute_tool("web_search", {"q": "2"}, cost_estimate=0.25)
        assert harness.session_cost == pytest.approx(0.35, abs=0.001)

    @pytest.mark.asyncio
    async def test_cost_zero_by_default(self):
        harness = _make_harness(tool_executor=_noop_executor)
        await harness.execute_tool("web_search", {"q": "free"})
        assert harness.session_cost == 0.0

    @pytest.mark.asyncio
    async def test_budget_gate_blocks_projected_overspend(self):
        """Budget gate uses projected_cost = session_cost + cost_estimate.
        If current session_cost is 0.90 and budget is 1.00, a call
        with cost_estimate=0.20 should be blocked (0.90 + 0.20 > 1.00)."""
        const = _make_constitution(max_budget_usd=1.00)
        harness = _make_harness(constitution=const, tool_executor=_noop_executor)
        harness.add_cost(0.90)

        with pytest.raises(BudgetExceededError):
            await harness.execute_tool("web_search", {"q": "expensive"}, cost_estimate=0.20)

    @pytest.mark.asyncio
    async def test_budget_gate_allows_exact_ceiling(self):
        """At exactly the ceiling, cost should still be blocked because
        projected_cost == max_budget_usd is NOT exceeded (it's >, not >=)."""
        const = _make_constitution(max_budget_usd=1.00)
        harness = _make_harness(constitution=const, tool_executor=_noop_executor)
        harness.add_cost(0.50)
        # 0.50 + 0.50 = 1.00, which is NOT > 1.00 → should PASS
        result = await harness.execute_tool("web_search", {"q": "exact"}, cost_estimate=0.50)
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_budget_remaining_in_summary(self):
        const = _make_constitution(max_budget_usd=2.00)
        harness = _make_harness(constitution=const, tool_executor=_noop_executor)
        await harness.execute_tool("web_search", {"q": "1"}, cost_estimate=0.75)
        summary = harness.get_session_summary()
        assert summary["budget_remaining_usd"] == pytest.approx(1.25, abs=0.001)


class TestHarnessRateLimitEdge:
    """Rate limit edge cases beyond the basic test in test_harness.py."""

    @pytest.mark.asyncio
    async def test_different_tools_have_independent_limits(self):
        """web_search max=10, shell_execute max=2 — they don't interfere."""
        harness = _make_harness(tool_executor=_noop_executor)
        # Exhaust shell_execute limit
        await harness.execute_tool("shell_execute", {"cmd": "echo 1"})
        await harness.execute_tool("shell_execute", {"cmd": "echo 2"})

        with pytest.raises(SessionLimitError):
            await harness.execute_tool("shell_execute", {"cmd": "echo 3"})

        # web_search should still work fine
        result = await harness.execute_tool("web_search", {"q": "still works"})
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_reset_session_restores_rate_limits(self):
        harness = _make_harness(tool_executor=_noop_executor)
        await harness.execute_tool("shell_execute", {"cmd": "1"})
        await harness.execute_tool("shell_execute", {"cmd": "2"})

        with pytest.raises(SessionLimitError):
            await harness.execute_tool("shell_execute", {"cmd": "3"})

        harness.reset_session()
        # After reset, limit is restored
        result = await harness.execute_tool("shell_execute", {"cmd": "after reset"})
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_is_tool_available_respects_rate_limit(self):
        harness = _make_harness(tool_executor=_noop_executor)
        assert harness.is_tool_available("shell_execute") is True

        await harness.execute_tool("shell_execute", {"cmd": "1"})
        await harness.execute_tool("shell_execute", {"cmd": "2"})

        assert harness.is_tool_available("shell_execute") is False

    @pytest.mark.asyncio
    async def test_is_tool_available_respects_budget(self):
        const = _make_constitution(max_budget_usd=0.50)
        harness = _make_harness(constitution=const, tool_executor=_noop_executor)
        assert harness.is_tool_available("web_search") is True

        harness.add_cost(0.60)
        assert harness.is_tool_available("web_search") is False


# ===================================================================
# 3. HookChain — Exception Propagation and Multi-Hook Interplay
# ===================================================================


class _BombHook(PreToolHook):
    """A pre-hook that always throws."""

    async def execute(self, tool_name: str, tool_input: Any) -> Any:
        raise ValueError("Hook detonated")


class _UpperCaseHook(PreToolHook):
    """A pre-hook that uppercases string inputs."""

    async def execute(self, tool_name: str, tool_input: Any) -> Any:
        if isinstance(tool_input, str):
            return tool_input.upper()
        return tool_input


class TestHookChainEdgeCases:

    @pytest.mark.asyncio
    async def test_failing_pre_hook_stops_chain(self):
        """If a pre-hook raises, subsequent hooks must NOT run."""
        chain = HookChain(pre_hooks=[_BombHook(), _UpperCaseHook()])
        with pytest.raises(ValueError, match="detonated"):
            await chain.run_pre_hooks("test", "hello")

    @pytest.mark.asyncio
    async def test_multi_pre_hook_pipeline(self):
        """Multiple pre-hooks chain: sanitize → uppercase."""
        chain = HookChain(
            pre_hooks=[InputSanitizerHook(), _UpperCaseHook()],
        )
        result = await chain.run_pre_hooks("test", "  hello world  ")
        assert result == "HELLO WORLD"

    @pytest.mark.asyncio
    async def test_empty_chain_is_passthrough(self):
        chain = HookChain()
        original = {"key": "value"}
        result = await chain.run_pre_hooks("test", original)
        assert result == original

        result = await chain.run_post_hooks("test", "output")
        assert result == "output"

    @pytest.mark.asyncio
    async def test_pre_hook_crash_triggers_audit_in_harness(self):
        """When a pre-hook explodes inside execute_tool, the harness must
        log an ERROR audit and re-raise."""
        chain = HookChain(pre_hooks=[_BombHook()])
        harness = _make_harness(
            tool_executor=_noop_executor,
            hook_chain=chain,
        )
        with pytest.raises(ValueError, match="detonated"):
            await harness.execute_tool("web_search", {"q": "test"})

        audit = harness.audit_logger
        error_records = [r for r in audit.records if r.verdict == AuditVerdict.ERROR]
        assert len(error_records) == 1
        assert "ValueError" in error_records[0].reason


# ===================================================================
# 4. ToolPermission — Path Normalization Edge Cases
# ===================================================================


class TestToolPermissionPathEdge:

    def test_backslash_normalized_to_forward_slash(self):
        """Windows paths with backslashes must match forward-slash patterns."""
        perm = ToolPermission(
            name="file_write",
            allowed_paths=("d:/project/**",),
        )
        assert perm.is_path_allowed("d:\\project\\output\\file.txt")

    def test_case_sensitivity_in_path(self):
        """fnmatch on Windows is case-insensitive by default."""
        import sys
        perm = ToolPermission(
            name="file_write",
            allowed_paths=("d:/project/**",),
        )
        # This tests actual platform behavior — on Windows fnmatch is case-insensitive
        if sys.platform == "win32":
            assert perm.is_path_allowed("D:/PROJECT/output/FILE.TXT")

    def test_empty_blocked_patterns_returns_none(self):
        perm = ToolPermission(name="web_search")
        assert perm.is_input_blocked("anything") is None

    def test_multiple_blocked_patterns_first_match_wins(self):
        perm = ToolPermission(
            name="shell",
            blocked_patterns=(r"rm\s+-rf", r"mkfs\."),
        )
        assert perm.is_input_blocked("rm -rf /home") is not None
        assert perm.is_input_blocked("mkfs.ext4 /dev/sda") is not None
        assert perm.is_input_blocked("echo hello") is None
