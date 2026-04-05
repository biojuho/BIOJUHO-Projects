"""shared.harness.adapters.base — Abstract adapter interface.

비유: 전원 어댑터 — 외부 프레임워크(DeepAgents, OpenHarness 등)를
      우리 거버넌스 파이프라인에 통합하는 공통 인터페이스.

All external harness frameworks are integrated through this adapter,
ensuring our existing governance (Constitution, Audit, Risk) is always
applied regardless of which framework orchestrates the agents.

Usage::

    class DeepAgentsAdapter(AbstractHarnessAdapter):
        async def execute_with_governance(self, task, tools, constitution):
            # 1. Pre-check via our governance
            # 2. Run DeepAgents orchestrator
            # 3. Post-check and audit
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdapterResult:
    """Standardized result from any adapter execution.

    Attributes:
        success: Whether the task completed successfully.
        output: The primary output data.
        trace: Execution trace entries for audit/debugging.
        metadata: Framework-specific metadata.
        cost_usd: Total LLM cost incurred during execution.
        tool_calls: Number of tool calls made.
    """

    success: bool
    output: Any = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    tool_calls: int = 0


class AbstractHarnessAdapter(ABC):
    """Common interface for integrating external harness frameworks.

    Guarantees:
      - Our Constitution is always the source of truth for permissions
      - Audit logging is always applied
      - Risk scanning happens before any tool execution
      - Budget gates are enforced

    Subclasses implement the actual orchestration logic while
    this base ensures governance compliance.
    """

    @abstractmethod
    async def execute_with_governance(
        self,
        task: dict[str, Any],
        tools: list[str],
        *,
        cost_estimate: float = 0.0,
    ) -> AdapterResult:
        """Execute a task through the governance pipeline.

        Args:
            task: Task definition (framework-specific format).
            tools: List of tool names the task may use.
            cost_estimate: Estimated cost in USD for budget gating.

        Returns:
            AdapterResult with output, trace, and cost info.

        Raises:
            HarnessError subclasses for governance violations.
        """
        ...

    @abstractmethod
    async def spawn_subagent(
        self,
        role: str,
        task: str,
        *,
        parent_context: dict[str, Any] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> AdapterResult:
        """Spawn a sub-agent for multi-agent coordination.

        Args:
            role: The sub-agent's role/persona.
            task: The task description for the sub-agent.
            parent_context: Context inherited from the parent agent.
            allowed_tools: Tool whitelist for the sub-agent
                           (defaults to parent's tools if None).

        Returns:
            AdapterResult from the sub-agent's execution.
        """
        ...

    @abstractmethod
    def get_execution_trace(self) -> list[dict[str, Any]]:
        """Return the full execution trace for audit/debugging.

        Each entry should include at minimum:
          - timestamp (ISO 8601)
          - agent_name
          - action (tool call, LLM call, sub-agent spawn, etc.)
          - result_summary
        """
        ...

    @abstractmethod
    def get_session_summary(self) -> dict[str, Any]:
        """Return a summary of the current adapter session.

        Should include: total_calls, cost, denied_count, etc.
        """
        ...
