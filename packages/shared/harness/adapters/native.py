"""shared.harness.adapters.native — Adapter wrapping existing HarnessWrapper.

First adapter implementation: wraps our own governance engine so that
pipelines can use the adapter interface without changing their existing
HarnessWrapper-based code.

This ensures backwards compatibility while enabling future migration
to DeepAgents or other frameworks by swapping adapters.

Usage::

    from shared.harness.adapters import NativeHarnessAdapter
    from shared.harness import Constitution

    constitution = Constitution.from_yaml("constitutions/getdaytrends.yaml")
    adapter = NativeHarnessAdapter(constitution)

    result = await adapter.execute_with_governance(
        task={"action": "web_search", "input": {"query": "AI trends"}},
        tools=["web_search", "llm_call"],
    )
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime  # noqa: UTC requires Python 3.11+
from typing import Any, Awaitable, Callable, Optional

from ..constitution import Constitution
from ..core import HarnessConfig, HarnessWrapper
from ..sandbox.policy import (
    ToolPermissionLevel,
    get_sandbox_policy,
    get_tool_level,
)
from ..sandbox.docker_runner import DockerSandboxRunner, SandboxResult
from .base import AbstractHarnessAdapter, AdapterResult

logger = logging.getLogger(__name__)

# Type alias
ToolExecutor = Callable[[str, Any], Awaitable[Any]]


class NativeHarnessAdapter(AbstractHarnessAdapter):
    """Adapter that wraps the existing HarnessWrapper.

    Adds sandbox policy enforcement on top of the existing 6-step
    governance pipeline. Tools classified as WRITE_EXTERNAL or
    WRITE_SYSTEM get additional Docker isolation.
    """

    def __init__(
        self,
        constitution: Constitution,
        *,
        tool_executor: Optional[ToolExecutor] = None,
        hitl_callback: Optional[Callable[[str, Any], Awaitable[bool]]] = None,
        sandbox_runner: Optional[DockerSandboxRunner] = None,
        tool_level_overrides: dict[str, ToolPermissionLevel] | None = None,
    ):
        config = HarnessConfig(
            constitution=constitution,
            tool_executor=tool_executor,
            hitl_callback=hitl_callback,
        )
        self._harness = HarnessWrapper(config)
        self._sandbox_runner = sandbox_runner or DockerSandboxRunner()
        self._tool_level_overrides = tool_level_overrides
        self._trace: list[dict[str, Any]] = []
        self._subagent_count = 0

    @property
    def harness(self) -> HarnessWrapper:
        """Access the underlying HarnessWrapper."""
        return self._harness

    async def execute_with_governance(
        self,
        task: dict[str, Any],
        tools: list[str],
        *,
        cost_estimate: float = 0.0,
    ) -> AdapterResult:
        """Execute task through HarnessWrapper + sandbox policy.

        The task dict must contain:
          - "action": tool name (str)
          - "input": tool input (Any)
        Optionally:
          - "command": shell command for sandboxed execution
        """
        tool_name = task.get("action", "")
        tool_input = task.get("input", {})
        command = task.get("command")

        # Check tool permission level
        level = get_tool_level(tool_name, self._tool_level_overrides)
        policy = get_sandbox_policy(tool_name, self._tool_level_overrides)

        trace_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_name": self._harness.constitution.agent_name,
            "action": tool_name,
            "permission_level": level.value,
            "sandbox_required": policy.sandbox,
        }

        try:
            # If sandboxed execution with a command
            if policy.sandbox and command:
                # Run governance checks only (permission, risk, budget)
                # using a sandbox-aware executor that delegates to Docker
                async def _sandbox_executor(tn: str, ti: Any) -> dict:
                    return (await self._sandbox_runner.run(
                        command=command,
                        policy=policy,
                    )).__dict__

                sandbox_raw = await self._harness.execute_tool(
                    tool_name,
                    tool_input,
                    executor=_sandbox_executor,
                    cost_estimate=cost_estimate,
                )
                sandbox_result = SandboxResult(**sandbox_raw)

                trace_entry["result_summary"] = (
                    f"sandbox:{sandbox_result.execution_method} "
                    f"exit={sandbox_result.exit_code}"
                )
                trace_entry["sandbox_timed_out"] = sandbox_result.timed_out
                self._trace.append(trace_entry)

                return AdapterResult(
                    success=sandbox_result.success,
                    output={
                        "stdout": sandbox_result.stdout,
                        "stderr": sandbox_result.stderr,
                        "exit_code": sandbox_result.exit_code,
                    },
                    trace=list(self._trace),
                    metadata={
                        "execution_method": sandbox_result.execution_method,
                        "elapsed_seconds": sandbox_result.elapsed_seconds,
                        "permission_level": level.value,
                    },
                    cost_usd=cost_estimate,
                    tool_calls=1,
                )

            # Standard governance execution (no sandbox command)
            result = await self._harness.execute_tool(
                tool_name,
                tool_input,
                cost_estimate=cost_estimate,
            )

            trace_entry["result_summary"] = "success"
            self._trace.append(trace_entry)

            return AdapterResult(
                success=True,
                output=result,
                trace=list(self._trace),
                metadata={"permission_level": level.value},
                cost_usd=self._harness.session_cost,
                tool_calls=self._harness.total_calls,
            )

        except Exception as e:
            trace_entry["result_summary"] = f"error:{type(e).__name__}"
            trace_entry["error"] = str(e)
            self._trace.append(trace_entry)
            raise

    async def spawn_subagent(
        self,
        role: str,
        task: str,
        *,
        parent_context: dict[str, Any] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> AdapterResult:
        """Spawn a sub-agent with its own governance scope.

        Creates a new NativeHarnessAdapter with the same constitution
        but an independent session (separate rate limits, cost tracking).
        """
        self._subagent_count += 1
        agent_name = f"{self._harness.constitution.agent_name}/sub-{self._subagent_count}-{role}"

        # Create a scoped constitution for the sub-agent
        if allowed_tools is not None:
            if len(allowed_tools) == 0:
                logger.warning(
                    "spawn_subagent(%s): allowed_tools is empty list — "
                    "sub-agent will have no tool permissions. "
                    "Use None to inherit parent tools.",
                    role,
                )
            scoped_perms = {
                name: perm
                for name, perm in self._harness.constitution.tool_permissions.items()
                if name in allowed_tools
            }
        else:
            scoped_perms = dict(self._harness.constitution.tool_permissions)

        sub_constitution = Constitution(
            agent_name=agent_name,
            max_budget_usd=self._harness.constitution.max_budget_usd / 2,  # Sub-agent gets half budget
            max_tokens_per_turn=self._harness.constitution.max_tokens_per_turn,
            tool_permissions=scoped_perms,
            risk_patterns=self._harness.constitution.risk_patterns,
            metadata={
                **(self._harness.constitution.metadata),
                "parent_agent": self._harness.constitution.agent_name,
                "role": role,
            },
        )

        sub_adapter = NativeHarnessAdapter(
            constitution=sub_constitution,
            tool_level_overrides=self._tool_level_overrides,
        )

        trace_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_name": self._harness.constitution.agent_name,
            "action": "spawn_subagent",
            "result_summary": f"spawned {agent_name}",
            "subagent_role": role,
            "subagent_task": task[:200],
        }
        self._trace.append(trace_entry)

        logger.info("Spawned sub-agent: %s (role=%s)", agent_name, role)

        return AdapterResult(
            success=True,
            output=sub_adapter,
            trace=list(self._trace),
            metadata={
                "subagent_name": agent_name,
                "role": role,
                "budget_usd": sub_constitution.max_budget_usd,
                "allowed_tools": list(scoped_perms.keys()),
            },
            cost_usd=0.0,
            tool_calls=0,
        )

    def get_execution_trace(self) -> list[dict[str, Any]]:
        """Return all trace entries from this adapter session."""
        return list(self._trace)

    def get_session_summary(self) -> dict[str, Any]:
        """Merge HarnessWrapper summary with adapter-level stats."""
        base = self._harness.get_session_summary()
        base.update({
            "subagents_spawned": self._subagent_count,
            "trace_entries": len(self._trace),
            "adapter_type": "native",
        })
        return base
