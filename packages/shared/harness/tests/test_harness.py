"""Tests for shared.harness — governance pipeline unit tests.

Tests the full 6-step pipeline: Permission → Rate Limit → Risk →
Budget → Hooks → Audit. Each step is tested independently and
the integration is verified end-to-end.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

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
    MetricsHook,
    OutputTruncatorHook,
)
from shared.harness.risk import RiskResult, RiskScanner


# ── Fixtures ──


def _make_constitution(**overrides) -> Constitution:
    """Factory for test constitutions with sensible defaults."""
    data = {
        "agent_name": "test-agent",
        "max_budget_usd": 1.0,
        "max_tokens_per_turn": 4000,
        "tools": [
            {"name": "web_search", "allowed": True, "max_calls": 5},
            {"name": "file_write", "allowed": True, "max_calls": 3,
             "allowed_paths": ["d:/AI project/output/**"],
             "blocked_patterns": [r".*\.env$"]},
            {"name": "shell_execute", "allowed": True, "max_calls": 2,
             "requires_approval": True},
            {"name": "file_delete", "allowed": False},
        ],
        "risk_patterns": [r"DROP TABLE"],
    }
    data.update(overrides)
    return Constitution.from_dict(data)


def _make_harness(constitution: Constitution | None = None, **config_kw) -> HarnessWrapper:
    """Factory for test harness with optional overrides."""
    const = constitution or _make_constitution()
    config = HarnessConfig(constitution=const, **config_kw)
    return HarnessWrapper(config)


async def _noop_executor(tool_name: str, tool_input) -> dict:
    """Dummy executor that echoes input."""
    return {"tool": tool_name, "result": "ok", "input": tool_input}


# ── Constitution Tests ──


class TestConstitution:
    def test_tool_allowed(self):
        c = _make_constitution()
        assert c.is_tool_allowed("web_search") is True
        assert c.is_tool_allowed("file_write") is True

    def test_tool_not_allowed(self):
        c = _make_constitution()
        assert c.is_tool_allowed("file_delete") is False

    def test_unlisted_tool_denied(self):
        c = _make_constitution()
        assert c.is_tool_allowed("unknown_tool") is False

    def test_hitl_required(self):
        c = _make_constitution()
        assert c.requires_human_approval("shell_execute") is True
        assert c.requires_human_approval("web_search") is False

    def test_unlisted_tool_requires_approval(self):
        c = _make_constitution()
        assert c.requires_human_approval("unknown_tool") is True

    def test_allowed_tools_list(self):
        c = _make_constitution()
        allowed = c.allowed_tools()
        assert "web_search" in allowed
        assert "file_delete" not in allowed

    def test_from_yaml(self, tmp_path):
        yaml_content = """
agent_name: "yaml-test"
max_budget_usd: 5.0
tools:
  - name: "api_call"
    allowed: true
    max_calls: 10
risk_patterns:
  - "DELETE FROM"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        c = Constitution.from_yaml(yaml_file)
        assert c.agent_name == "yaml-test"
        assert c.max_budget_usd == 5.0
        assert c.is_tool_allowed("api_call")
        assert "DELETE FROM" in c.risk_patterns

    def test_from_yaml_missing_file(self):
        with pytest.raises(FileNotFoundError):
            Constitution.from_yaml("/nonexistent/path.yaml")


class TestToolPermission:
    def test_path_allowed(self):
        perm = ToolPermission(
            name="file_write",
            allowed_paths=("d:/AI project/output/**",),
        )
        assert perm.is_path_allowed("d:/AI project/output/file.txt")

    def test_path_denied(self):
        perm = ToolPermission(
            name="file_write",
            allowed_paths=("d:/AI project/output/**",),
        )
        assert not perm.is_path_allowed("d:/AI project/shared/llm/client.py")

    def test_no_path_restrictions(self):
        perm = ToolPermission(name="web_search")
        assert perm.is_path_allowed("/any/path")

    def test_input_blocked(self):
        perm = ToolPermission(
            name="file_write",
            blocked_patterns=(r".*\.env$",),
        )
        assert perm.is_input_blocked("config.env") is not None
        assert perm.is_input_blocked("config.yaml") is None


# ── Risk Scanner Tests ──


class TestRiskScanner:
    def test_builtin_patterns(self):
        c = _make_constitution()
        scanner = RiskScanner(c)
        result = scanner.scan("shell_execute", {"command": "rm -rf /"})
        assert result.is_risky
        assert "destructive" in result.risk_category

    def test_constitution_patterns(self):
        c = _make_constitution()
        scanner = RiskScanner(c)
        result = scanner.scan("database_write", {"query": "DROP TABLE users"})
        assert result.is_risky

    def test_safe_input(self):
        c = _make_constitution()
        scanner = RiskScanner(c)
        result = scanner.scan("web_search", {"query": "AI trends 2026"})
        assert not result.is_risky

    def test_nested_input_scanning(self):
        c = _make_constitution()
        scanner = RiskScanner(c)
        result = scanner.scan("shell_execute", {
            "command": "echo hello",
            "nested": {"deep": "eval(malicious_code)"},
        })
        assert result.is_risky
        assert "unsafe_eval" in result.risk_category

    def test_builtins_disabled(self):
        c = _make_constitution()
        scanner = RiskScanner(c, enable_builtins=False)
        result = scanner.scan("shell_execute", {"command": "eval('1+1')"})
        # Built-in eval pattern disabled, but constitution pattern doesn't match
        assert not result.is_risky


# ── Audit Logger Tests ──


class TestAuditLogger:
    def test_log_allowed(self):
        logger = AuditLogger(agent_name="test", emit_to_logging=False)
        record = logger.log_allowed("web_search", {"query": "test"})
        assert record.verdict == AuditVerdict.ALLOWED
        assert logger.total_count == 1

    def test_log_denied(self):
        logger = AuditLogger(agent_name="test", emit_to_logging=False)
        logger.log_denied("file_delete", "NOT_ALLOWED")
        assert logger.denied_count == 1

    def test_file_persistence(self, tmp_path):
        log_file = tmp_path / "audit.jsonl"
        logger = AuditLogger(
            agent_name="test",
            log_path=log_file,
            emit_to_logging=False,
        )
        logger.log_allowed("web_search", {"q": "test"})
        logger.log_denied("file_delete", "BLOCKED")

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        record1 = json.loads(lines[0])
        assert record1["verdict"] == "allowed"
        record2 = json.loads(lines[1])
        assert record2["verdict"] == "denied"

    def test_input_truncation(self):
        logger = AuditLogger(agent_name="test", max_input_chars=10, emit_to_logging=False)
        record = logger.log_allowed("web_search", "a" * 100)
        assert len(record.tool_input_summary) <= 13  # 10 + "..."


# ── Hooks Tests ──


class TestHooks:
    @pytest.mark.asyncio
    async def test_input_sanitizer(self):
        hook = InputSanitizerHook()
        result = await hook.execute("test", {"key": "  value  "})
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_output_truncator(self):
        hook = OutputTruncatorHook(max_chars=20)
        result = await hook.execute("test", "x" * 100)
        assert len(result) < 100
        assert "[TRUNCATED:" in result

    @pytest.mark.asyncio
    async def test_metrics_hook(self):
        hook = MetricsHook()
        await hook.execute("tool_a", "result")
        await hook.execute("tool_a", "result")
        await hook.execute("tool_b", "result")
        assert hook.call_counts["tool_a"] == 2
        assert hook.call_counts["tool_b"] == 1
        assert hook.total_calls == 3

    @pytest.mark.asyncio
    async def test_hook_chain(self):
        chain = HookChain(
            pre_hooks=[InputSanitizerHook()],
            post_hooks=[OutputTruncatorHook(max_chars=50)],
        )
        processed = await chain.run_pre_hooks("test", {"key": "  val  "})
        assert processed == {"key": "val"}

        output = await chain.run_post_hooks("test", "y" * 100)
        assert "[TRUNCATED:" in output


# ── HarnessWrapper Integration Tests ──


class TestHarnessWrapper:
    @pytest.mark.asyncio
    async def test_allowed_tool_passes(self):
        harness = _make_harness(tool_executor=_noop_executor)
        result = await harness.execute_tool("web_search", {"query": "test"})
        assert result["result"] == "ok"
        assert harness.total_calls == 1

    @pytest.mark.asyncio
    async def test_blocked_tool_raises(self):
        harness = _make_harness(tool_executor=_noop_executor)
        with pytest.raises(ToolNotAllowedError):
            await harness.execute_tool("file_delete", {})

    @pytest.mark.asyncio
    async def test_unlisted_tool_raises(self):
        harness = _make_harness(tool_executor=_noop_executor)
        with pytest.raises(ToolNotAllowedError):
            await harness.execute_tool("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self):
        harness = _make_harness(tool_executor=_noop_executor)
        # web_search max_calls = 5
        for _ in range(5):
            await harness.execute_tool("web_search", {"q": "test"})
        with pytest.raises(SessionLimitError):
            await harness.execute_tool("web_search", {"q": "one more"})

    @pytest.mark.asyncio
    async def test_risk_pattern_blocked(self):
        harness = _make_harness(tool_executor=_noop_executor)
        with pytest.raises(RiskDetectedError):
            await harness.execute_tool("web_search", {"query": "DROP TABLE users"})

    @pytest.mark.asyncio
    async def test_budget_exceeded(self):
        const = _make_constitution(max_budget_usd=0.01)
        harness = _make_harness(constitution=const, tool_executor=_noop_executor)
        harness.add_cost(0.02)  # Exceed budget
        with pytest.raises(BudgetExceededError):
            await harness.execute_tool("web_search", {"q": "test"})

    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        harness = _make_harness()  # No executor = dry run
        result = await harness.execute_tool("web_search", {"q": "test"})
        assert result["dry_run"] is True

    @pytest.mark.asyncio
    async def test_session_summary(self):
        harness = _make_harness(tool_executor=_noop_executor)
        await harness.execute_tool("web_search", {"q": "1"})
        await harness.execute_tool("web_search", {"q": "2"})

        summary = harness.get_session_summary()
        assert summary["total_calls"] == 2
        assert summary["agent_name"] == "test-agent"
        assert summary["tool_call_counts"]["web_search"] == 2

    @pytest.mark.asyncio
    async def test_audit_trail_complete(self):
        harness = _make_harness(tool_executor=_noop_executor)
        await harness.execute_tool("web_search", {"q": "ok"})

        try:
            await harness.execute_tool("file_delete", {})
        except ToolNotAllowedError:
            pass

        audit = harness.audit_logger
        assert audit.total_count == 2
        assert audit.denied_count == 1

    @pytest.mark.asyncio
    async def test_is_tool_available(self):
        harness = _make_harness(tool_executor=_noop_executor)
        assert harness.is_tool_available("web_search") is True
        assert harness.is_tool_available("file_delete") is False
        assert harness.is_tool_available("unknown") is False

    @pytest.mark.asyncio
    async def test_reset_session(self):
        harness = _make_harness(tool_executor=_noop_executor)
        await harness.execute_tool("web_search", {"q": "1"})
        harness.add_cost(0.5)

        assert harness.total_calls == 1
        assert harness.session_cost == 0.5

        harness.reset_session()
        assert harness.total_calls == 0
        assert harness.session_cost == 0.0

    @pytest.mark.asyncio
    async def test_hitl_callback_approve(self):
        async def approve_all(tool_name, tool_input):
            return True

        harness = _make_harness(
            tool_executor=_noop_executor,
            hitl_callback=approve_all,
        )
        # shell_execute requires approval
        result = await harness.execute_tool("shell_execute", {"cmd": "echo hi"})
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_hitl_callback_reject(self):
        from shared.harness.errors import PermissionDeniedError

        async def reject_all(tool_name, tool_input):
            return False

        harness = _make_harness(
            tool_executor=_noop_executor,
            hitl_callback=reject_all,
        )
        with pytest.raises(PermissionDeniedError, match="rejected"):
            await harness.execute_tool("shell_execute", {"cmd": "echo hi"})
