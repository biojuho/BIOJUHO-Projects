"""Tests for Phase 0: Adapter layer and Sandbox policy system.

Covers:
  - ToolPermissionLevel classification
  - SandboxPolicy presets and Docker options generation
  - get_tool_level / get_sandbox_policy resolution
  - NativeHarnessAdapter governance execution
  - NativeHarnessAdapter sub-agent spawning
  - DockerSandboxRunner subprocess fallback
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from shared.harness.sandbox.policy import (
    DEFAULT_TOOL_LEVELS,
    SANDBOX_PRESETS,
    SandboxPolicy,
    ToolPermissionLevel,
    get_sandbox_policy,
    get_tool_level,
)
from shared.harness.sandbox.docker_runner import DockerSandboxRunner, SandboxResult
from shared.harness.adapters.base import AbstractHarnessAdapter, AdapterResult
from shared.harness.adapters.native import NativeHarnessAdapter
from shared.harness.constitution import Constitution
from shared.harness.errors import (
    BudgetExceededError,
    RiskDetectedError,
    ToolNotAllowedError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_constitution(**overrides) -> Constitution:
    """Create a minimal test constitution."""
    defaults = {
        "agent_name": "test-agent",
        "max_budget_usd": 2.0,
        "tools": [
            {"name": "web_search", "allowed": True, "max_calls": 50},
            {"name": "llm_call", "allowed": True, "max_calls": 200},
            {"name": "file_read", "allowed": True, "max_calls": 100},
            {"name": "publish_to_x", "allowed": True, "max_calls": 10,
             "requires_approval": True},
            {"name": "shell_execute", "allowed": True, "max_calls": 5,
             "requires_approval": True},
            {"name": "file_delete", "allowed": False},
        ],
        "risk_patterns": ["rm -rf", "DROP TABLE"],
    }
    defaults.update(overrides)
    return Constitution.from_dict(defaults)


async def _dummy_executor(tool_name: str, tool_input) -> dict:
    """Simple pass-through executor for testing."""
    return {"tool": tool_name, "result": "ok", "input": tool_input}


# ===========================================================================
# Test: ToolPermissionLevel
# ===========================================================================

class TestToolPermissionLevel:
    def test_enum_values(self):
        assert ToolPermissionLevel.READ_ONLY.value == "read_only"
        assert ToolPermissionLevel.WRITE_EXTERNAL.value == "write_external"
        assert ToolPermissionLevel.WRITE_SYSTEM.value == "write_system"

    def test_default_tool_levels_completeness(self):
        """All default tools should have valid levels."""
        for tool, level in DEFAULT_TOOL_LEVELS.items():
            assert isinstance(level, ToolPermissionLevel), f"{tool}: {level}"

    def test_read_only_tools(self):
        read_only = {k for k, v in DEFAULT_TOOL_LEVELS.items()
                     if v == ToolPermissionLevel.READ_ONLY}
        assert "web_search" in read_only
        assert "llm_call" in read_only
        assert "file_read" in read_only

    def test_write_external_tools(self):
        write_ext = {k for k, v in DEFAULT_TOOL_LEVELS.items()
                     if v == ToolPermissionLevel.WRITE_EXTERNAL}
        assert "publish_to_x" in write_ext
        assert "notion_api" in write_ext

    def test_write_system_tools(self):
        write_sys = {k for k, v in DEFAULT_TOOL_LEVELS.items()
                     if v == ToolPermissionLevel.WRITE_SYSTEM}
        assert "shell_execute" in write_sys
        assert "file_delete" in write_sys


# ===========================================================================
# Test: SandboxPolicy
# ===========================================================================

class TestSandboxPolicy:
    def test_presets_cover_all_levels(self):
        for level in ToolPermissionLevel:
            assert level in SANDBOX_PRESETS

    def test_read_only_preset_no_sandbox(self):
        policy = SANDBOX_PRESETS[ToolPermissionLevel.READ_ONLY]
        assert not policy.sandbox
        assert not policy.requires_approval

    def test_write_external_preset_sandboxed(self):
        policy = SANDBOX_PRESETS[ToolPermissionLevel.WRITE_EXTERNAL]
        assert policy.sandbox
        assert policy.requires_approval
        assert policy.network_access  # 외부 API 호출 필요

    def test_write_system_preset_strict(self):
        policy = SANDBOX_PRESETS[ToolPermissionLevel.WRITE_SYSTEM]
        assert policy.sandbox
        assert policy.requires_approval
        assert not policy.network_access
        assert policy.timeout_seconds == 10  # 짧은 타임아웃

    def test_to_docker_options_network_none(self):
        policy = SandboxPolicy(
            level=ToolPermissionLevel.WRITE_SYSTEM,
            sandbox=True,
            network_access=False,
            memory_limit_mb=128,
            cpu_limit=0.5,
        )
        opts = policy.to_docker_options()
        assert opts["network_mode"] == "none"
        assert opts["mem_limit"] == "128m"
        assert opts["nano_cpus"] == 500_000_000
        assert opts["read_only"] is True
        assert "no-new-privileges:true" in opts["security_opt"]
        assert "ALL" in opts["cap_drop"]

    def test_to_docker_options_with_network(self):
        policy = SandboxPolicy(
            level=ToolPermissionLevel.WRITE_EXTERNAL,
            sandbox=True,
            network_access=True,
        )
        opts = policy.to_docker_options()
        assert "network_mode" not in opts

    def test_to_docker_options_with_env(self):
        policy = SandboxPolicy(
            level=ToolPermissionLevel.WRITE_EXTERNAL,
            allowed_env_vars=("API_KEY", "TOKEN"),
        )
        opts = policy.to_docker_options()
        assert "API_KEY" in opts["environment"]
        assert "TOKEN" in opts["environment"]


# ===========================================================================
# Test: get_tool_level / get_sandbox_policy
# ===========================================================================

class TestToolLevelResolution:
    def test_known_tool(self):
        assert get_tool_level("web_search") == ToolPermissionLevel.READ_ONLY

    def test_unknown_tool_defaults_to_write_system(self):
        assert get_tool_level("unknown_tool") == ToolPermissionLevel.WRITE_SYSTEM

    def test_override_takes_precedence(self):
        overrides = {"web_search": ToolPermissionLevel.WRITE_SYSTEM}
        assert get_tool_level("web_search", overrides) == ToolPermissionLevel.WRITE_SYSTEM

    def test_get_sandbox_policy_returns_matching_preset(self):
        policy = get_sandbox_policy("web_search")
        assert policy.level == ToolPermissionLevel.READ_ONLY
        assert not policy.sandbox

    def test_get_sandbox_policy_with_override(self):
        overrides = {"web_search": ToolPermissionLevel.WRITE_EXTERNAL}
        policy = get_sandbox_policy("web_search", overrides)
        assert policy.level == ToolPermissionLevel.WRITE_EXTERNAL
        assert policy.sandbox


# ===========================================================================
# Test: SandboxResult
# ===========================================================================

class TestSandboxResult:
    def test_success_result(self):
        r = SandboxResult(success=True, exit_code=0, stdout="hello")
        assert r.success
        assert r.stdout == "hello"
        assert not r.timed_out

    def test_timeout_result(self):
        r = SandboxResult(success=False, timed_out=True, stderr="timeout")
        assert not r.success
        assert r.timed_out

    def test_frozen(self):
        r = SandboxResult(success=True)
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore[misc]


# ===========================================================================
# Test: DockerSandboxRunner (subprocess fallback)
# ===========================================================================

class TestDockerSandboxRunnerSubprocess:
    @pytest.fixture
    def runner(self):
        return DockerSandboxRunner()

    @pytest.fixture
    def no_sandbox_policy(self):
        return SandboxPolicy(
            level=ToolPermissionLevel.READ_ONLY,
            sandbox=False,
            timeout_seconds=10,
        )

    @pytest.fixture
    def sandboxed_policy(self):
        return SandboxPolicy(
            level=ToolPermissionLevel.WRITE_SYSTEM,
            sandbox=True,
            timeout_seconds=5,
            network_access=False,
        )

    @pytest.mark.asyncio
    async def test_no_sandbox_runs_subprocess(self, runner, no_sandbox_policy):
        result = await runner.run("echo hello", no_sandbox_policy)
        assert result.success
        assert "hello" in result.stdout
        assert result.execution_method == "subprocess"

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self, runner):
        policy = SandboxPolicy(
            level=ToolPermissionLevel.WRITE_SYSTEM,
            sandbox=False,
            timeout_seconds=1,
        )
        # Sleep longer than timeout
        result = await runner.run("python -c \"import time; time.sleep(10)\"", policy)
        assert not result.success
        assert result.timed_out

    @pytest.mark.asyncio
    async def test_subprocess_failure_exit_code(self, runner, no_sandbox_policy):
        result = await runner.run("python -c \"raise SystemExit(42)\"", no_sandbox_policy)
        assert not result.success
        assert result.exit_code == 42

    @pytest.mark.asyncio
    async def test_subprocess_stderr_captured(self, runner, no_sandbox_policy):
        result = await runner.run(
            "python -c \"import sys; sys.stderr.write('err_msg')\"",
            no_sandbox_policy,
        )
        assert "err_msg" in result.stderr

    @pytest.mark.asyncio
    async def test_sandbox_falls_back_when_no_docker(self, runner, sandboxed_policy):
        """When Docker is not available, sandboxed policy falls back to subprocess."""
        with patch.object(runner, '_docker_available', False):
            result = await runner.run("echo fallback", sandboxed_policy)
            assert result.execution_method == "subprocess"
            assert "fallback" in result.stdout


# ===========================================================================
# Test: AdapterResult
# ===========================================================================

class TestAdapterResult:
    def test_defaults(self):
        r = AdapterResult(success=True)
        assert r.output is None
        assert r.trace == []
        assert r.cost_usd == 0.0
        assert r.tool_calls == 0

    def test_with_trace(self):
        r = AdapterResult(
            success=True,
            output="data",
            trace=[{"action": "web_search"}],
            cost_usd=0.01,
            tool_calls=1,
        )
        assert len(r.trace) == 1
        assert r.cost_usd == 0.01


# ===========================================================================
# Test: NativeHarnessAdapter
# ===========================================================================

class TestNativeHarnessAdapter:
    @pytest.fixture
    def constitution(self):
        return _make_constitution()

    @pytest.fixture
    def adapter(self, constitution):
        return NativeHarnessAdapter(
            constitution,
            tool_executor=_dummy_executor,
            hitl_callback=AsyncMock(return_value=True),
        )

    @pytest.mark.asyncio
    async def test_execute_allowed_tool(self, adapter):
        result = await adapter.execute_with_governance(
            task={"action": "web_search", "input": {"query": "AI"}},
            tools=["web_search"],
        )
        assert result.success
        assert result.output["tool"] == "web_search"
        assert result.output["result"] == "ok"

    @pytest.mark.asyncio
    async def test_execute_denied_tool(self, adapter):
        with pytest.raises(ToolNotAllowedError):
            await adapter.execute_with_governance(
                task={"action": "file_delete", "input": {}},
                tools=["file_delete"],
            )

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, adapter):
        with pytest.raises(ToolNotAllowedError):
            await adapter.execute_with_governance(
                task={"action": "unknown_tool", "input": {}},
                tools=["unknown_tool"],
            )

    @pytest.mark.asyncio
    async def test_risk_detection(self, adapter):
        with pytest.raises(RiskDetectedError):
            await adapter.execute_with_governance(
                task={"action": "web_search", "input": {"query": "rm -rf /"}},
                tools=["web_search"],
            )

    @pytest.mark.asyncio
    async def test_trace_recorded(self, adapter):
        await adapter.execute_with_governance(
            task={"action": "web_search", "input": {"query": "test"}},
            tools=["web_search"],
        )
        trace = adapter.get_execution_trace()
        assert len(trace) == 1
        assert trace[0]["action"] == "web_search"
        assert "timestamp" in trace[0]
        assert trace[0]["result_summary"] == "success"

    @pytest.mark.asyncio
    async def test_trace_records_errors(self, adapter):
        try:
            await adapter.execute_with_governance(
                task={"action": "file_delete", "input": {}},
                tools=["file_delete"],
            )
        except ToolNotAllowedError:
            pass
        trace = adapter.get_execution_trace()
        assert len(trace) == 1
        assert "error" in trace[0]["result_summary"]

    @pytest.mark.asyncio
    async def test_session_summary(self, adapter):
        await adapter.execute_with_governance(
            task={"action": "web_search", "input": {"query": "x"}},
            tools=["web_search"],
        )
        summary = adapter.get_session_summary()
        assert summary["total_calls"] == 1
        assert summary["adapter_type"] == "native"
        assert summary["subagents_spawned"] == 0

    @pytest.mark.asyncio
    async def test_permission_level_in_result(self, adapter):
        result = await adapter.execute_with_governance(
            task={"action": "web_search", "input": {"query": "x"}},
            tools=["web_search"],
        )
        assert result.metadata["permission_level"] == "read_only"

    @pytest.mark.asyncio
    async def test_budget_exceeded(self, constitution):
        adapter = NativeHarnessAdapter(
            constitution,
            tool_executor=_dummy_executor,
        )
        with pytest.raises(BudgetExceededError):
            await adapter.execute_with_governance(
                task={"action": "llm_call", "input": {}},
                tools=["llm_call"],
                cost_estimate=10.0,  # 예산 초과
            )


# ===========================================================================
# Test: NativeHarnessAdapter — Sub-agent spawning
# ===========================================================================

class TestNativeHarnessAdapterSubagent:
    @pytest.fixture
    def adapter(self):
        constitution = _make_constitution()
        return NativeHarnessAdapter(
            constitution,
            tool_executor=_dummy_executor,
        )

    @pytest.mark.asyncio
    async def test_spawn_subagent_creates_adapter(self, adapter):
        result = await adapter.spawn_subagent(
            role="analyzer",
            task="분석 작업 수행",
        )
        assert result.success
        sub_adapter = result.output
        assert isinstance(sub_adapter, NativeHarnessAdapter)

    @pytest.mark.asyncio
    async def test_subagent_has_scoped_name(self, adapter):
        result = await adapter.spawn_subagent(
            role="writer",
            task="콘텐츠 생성",
        )
        sub_adapter = result.output
        assert "sub-1-writer" in sub_adapter.harness.constitution.agent_name

    @pytest.mark.asyncio
    async def test_subagent_has_half_budget(self, adapter):
        result = await adapter.spawn_subagent(
            role="qa",
            task="품질 검증",
        )
        sub_adapter = result.output
        parent_budget = adapter.harness.constitution.max_budget_usd
        sub_budget = sub_adapter.harness.constitution.max_budget_usd
        assert sub_budget == parent_budget / 2

    @pytest.mark.asyncio
    async def test_subagent_tool_whitelist(self, adapter):
        result = await adapter.spawn_subagent(
            role="reader",
            task="파일 읽기만",
            allowed_tools=["file_read", "llm_call"],
        )
        sub_adapter = result.output
        allowed = sub_adapter.harness.constitution.allowed_tools()
        assert "file_read" in allowed
        assert "llm_call" in allowed
        assert "shell_execute" not in allowed

    @pytest.mark.asyncio
    async def test_spawn_count_tracked(self, adapter):
        await adapter.spawn_subagent(role="a", task="t1")
        await adapter.spawn_subagent(role="b", task="t2")
        summary = adapter.get_session_summary()
        assert summary["subagents_spawned"] == 2

    @pytest.mark.asyncio
    async def test_subagent_trace_recorded(self, adapter):
        await adapter.spawn_subagent(role="tester", task="test run")
        trace = adapter.get_execution_trace()
        assert any(e["action"] == "spawn_subagent" for e in trace)

    @pytest.mark.asyncio
    async def test_subagent_inherits_risk_patterns(self, adapter):
        result = await adapter.spawn_subagent(role="r", task="t")
        sub_adapter = result.output
        assert sub_adapter.harness.constitution.risk_patterns == ("rm -rf", "DROP TABLE")

    @pytest.mark.asyncio
    async def test_subagent_independent_session(self, adapter):
        """Sub-agent has independent rate limits and cost tracking."""
        # Use parent
        await adapter.execute_with_governance(
            task={"action": "web_search", "input": {"query": "p"}},
            tools=["web_search"],
        )

        result = await adapter.spawn_subagent(
            role="sub",
            task="independent work",
            allowed_tools=["web_search"],
        )
        sub_adapter = result.output

        # Sub-agent session should be fresh
        assert sub_adapter.harness.total_calls == 0
        assert sub_adapter.harness.session_cost == 0.0
