"""shared.harness.adapters.deepagents — DeepAgents/LangGraph adapter stub.

Phase 2 adapter for integrating DeepAgents (LangChain official) into
our governance pipeline. Currently a stub that defines the integration
pattern; full implementation requires DeepAgents SDK.

Architecture:

    요청 → DeepAgentsAdapter
             ↓
        [기존 harness/core.py 거버넌스]  ← 그대로 유지
             ↓
        [기존 llm/client.py 라우팅]     ← 그대로 유지
             ↓
        DeepAgents Orchestrator
             ↓
        LLM Backend (Anthropic/Gemini/...)

Usage (future)::

    from shared.harness.adapters import DeepAgentsAdapter
    adapter = DeepAgentsAdapter(constitution, llm_client=client)
    result = await adapter.execute_with_governance(task, tools)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from ..constitution import Constitution
from ..core import HarnessConfig, HarnessWrapper
from .base import AbstractHarnessAdapter, AdapterResult

logger = logging.getLogger(__name__)

# --- DeepAgents SDK import (optional) ---
try:
    import deepagents  # type: ignore[import-not-found]

    DEEPAGENTS_AVAILABLE = True
except ImportError:
    DEEPAGENTS_AVAILABLE = False


class DeepAgentsAdapter(AbstractHarnessAdapter):
    """Adapter for DeepAgents (LangChain official) framework.

    Wraps DeepAgents orchestration with our existing governance pipeline.
    The key principle: our Constitution is always the source of truth,
    DeepAgents provides the multi-agent coordination patterns.

    Currently a **stub** — full implementation requires:
      - pip install deepagents langgraph
      - DeepAgents v0.4+ API stabilization

    The stub provides the correct interface so that:
      1. Pipelines can be written against this adapter now
      2. When DeepAgents is installed, it activates automatically
      3. Without DeepAgents, it falls back to NativeHarnessAdapter behavior
    """

    def __init__(
        self,
        constitution: Constitution,
        *,
        llm_client: Any = None,
        tool_executor: Optional[Callable[[str, Any], Awaitable[Any]]] = None,
        hitl_callback: Optional[Callable[[str, Any], Awaitable[bool]]] = None,
    ):
        self._constitution = constitution
        self._llm_client = llm_client

        config = HarnessConfig(
            constitution=constitution,
            tool_executor=tool_executor,
            hitl_callback=hitl_callback,
        )
        self._harness = HarnessWrapper(config)
        self._trace: list[dict[str, Any]] = []
        self._subagent_count = 0

        if DEEPAGENTS_AVAILABLE:
            logger.info("DeepAgents SDK available — full orchestration enabled")
        else:
            logger.info(
                "DeepAgents SDK not installed — using governance-only mode. "
                "Install with: pip install deepagents"
            )

    @property
    def is_full_mode(self) -> bool:
        """Whether DeepAgents SDK is available for full orchestration."""
        return DEEPAGENTS_AVAILABLE

    async def execute_with_governance(
        self,
        task: dict[str, Any],
        tools: list[str],
        *,
        cost_estimate: float = 0.0,
    ) -> AdapterResult:
        """Execute task through governance + DeepAgents orchestration.

        When DeepAgents is not available, falls back to direct
        HarnessWrapper execution (same as NativeHarnessAdapter).
        """
        tool_name = task.get("action", "")
        tool_input = task.get("input", {})

        trace_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": self._constitution.agent_name,
            "action": tool_name,
            "adapter": "deepagents" if DEEPAGENTS_AVAILABLE else "deepagents-fallback",
        }

        try:
            if DEEPAGENTS_AVAILABLE:
                result = await self._execute_with_deepagents(
                    task, tools, cost_estimate=cost_estimate
                )
            else:
                # Fallback: governance-only execution
                output = await self._harness.execute_tool(
                    tool_name,
                    tool_input,
                    cost_estimate=cost_estimate,
                )
                result = AdapterResult(
                    success=True,
                    output=output,
                    cost_usd=self._harness.session_cost,
                    tool_calls=self._harness.total_calls,
                )

            trace_entry["result_summary"] = "success"
            self._trace.append(trace_entry)
            result.trace = list(self._trace)
            return result

        except Exception as e:
            trace_entry["result_summary"] = f"error:{type(e).__name__}"
            trace_entry["error"] = str(e)
            self._trace.append(trace_entry)
            raise

    async def _execute_with_deepagents(
        self,
        task: dict[str, Any],
        tools: list[str],
        *,
        cost_estimate: float = 0.0,
    ) -> AdapterResult:
        """Full DeepAgents orchestration (requires SDK).

        TODO: Implement when DeepAgents API stabilizes (target: v1.0).
        Expected integration pattern:

            1. Create DeepAgents Agent with our LLM client as backend
            2. Register allowed tools from Constitution
            3. Run governance pre-check
            4. Execute via DeepAgents orchestrator
            5. Run governance post-check + audit
        """
        raise NotImplementedError(
            "Full DeepAgents orchestration not yet implemented. "
            "Waiting for DeepAgents v1.0 API stabilization. "
            "Use NativeHarnessAdapter or set DEEPAGENTS_AVAILABLE=False."
        )

    async def spawn_subagent(
        self,
        role: str,
        task: str,
        *,
        parent_context: dict[str, Any] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> AdapterResult:
        """Spawn a sub-agent via DeepAgents.

        When DeepAgents is available, uses its native sub-agent spawning.
        Otherwise, creates a new DeepAgentsAdapter with scoped constitution.
        """
        self._subagent_count += 1
        agent_name = f"{self._constitution.agent_name}/deep-{self._subagent_count}-{role}"

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
                for name, perm in self._constitution.tool_permissions.items()
                if name in allowed_tools
            }
        else:
            scoped_perms = dict(self._constitution.tool_permissions)

        sub_constitution = Constitution(
            agent_name=agent_name,
            max_budget_usd=self._constitution.max_budget_usd / 2,
            max_tokens_per_turn=self._constitution.max_tokens_per_turn,
            tool_permissions=scoped_perms,
            risk_patterns=self._constitution.risk_patterns,
            metadata={
                **self._constitution.metadata,
                "parent_agent": self._constitution.agent_name,
                "role": role,
                "framework": "deepagents",
            },
        )

        sub_adapter = DeepAgentsAdapter(
            constitution=sub_constitution,
            llm_client=self._llm_client,
        )

        self._trace.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": self._constitution.agent_name,
            "action": "spawn_subagent",
            "result_summary": f"spawned {agent_name}",
            "subagent_role": role,
        })

        return AdapterResult(
            success=True,
            output=sub_adapter,
            trace=list(self._trace),
            metadata={
                "subagent_name": agent_name,
                "role": role,
                "framework": "deepagents" if DEEPAGENTS_AVAILABLE else "fallback",
            },
        )

    def get_execution_trace(self) -> list[dict[str, Any]]:
        return list(self._trace)

    def get_session_summary(self) -> dict[str, Any]:
        base = self._harness.get_session_summary()
        base.update({
            "subagents_spawned": self._subagent_count,
            "trace_entries": len(self._trace),
            "adapter_type": "deepagents",
            "deepagents_available": DEEPAGENTS_AVAILABLE,
        })
        return base
