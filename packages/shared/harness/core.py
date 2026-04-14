"""shared.harness.core — HarnessWrapper: the central governance engine.

Analogy: "공항 보안 체크포인트" — 모든 탑승객(Tool Call)이
         보안 검색(Constitution Check), 신원 확인(Audit),
         수하물 검사(Risk Scan)를 거쳐야 게이트(실행)에 도달합니다.

Implements a 6-Step Governance Pipeline:
  1. Permission Check (Constitution allowlist)
  2. Rate Limit Check (per-session tool call budget)
  3. Risk Scan (pattern matching)
  4. Budget Gate (cost control)
  5. Pre-Hooks → Execution → Post-Hooks
  6. Audit Logging

Usage::

    from shared.harness import HarnessWrapper, HarnessConfig, Constitution

    config = HarnessConfig(
        constitution=Constitution.from_yaml("constitution.yaml"),
    )
    harness = HarnessWrapper(config)
    result = await harness.execute_tool("web_search", {"query": "..."})
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from .audit import AuditLogger
from .constitution import Constitution
from .errors import (
    BudgetExceededError,
    PermissionDeniedError,
    RiskDetectedError,
    SessionLimitError,
    ToolNotAllowedError,
)
from .hooks import HookChain
from .token_tracker import TokenBudget
from .risk import RiskScanner

# Type alias for tool executor functions
ToolExecutor = Callable[[str, Any], Awaitable[Any]]


@dataclass
class HarnessConfig:
    """Configuration for the HarnessWrapper.

    Separates concerns cleanly: Constitution defines rules,
    Config wires up the runtime components.
    """

    constitution: Constitution
    audit_logger: Optional[AuditLogger] = None
    risk_scanner: Optional[RiskScanner] = None
    hook_chain: Optional[HookChain] = None
    token_budget: Optional[TokenBudget] = None
    tool_executor: Optional[ToolExecutor] = None
    hitl_callback: Optional[Callable[[str, Any], Awaitable[bool]]] = None
    sandbox_tools: frozenset[str] = frozenset({"shell_execute", "code_run"})

    def __post_init__(self):
        # Auto-create components from Constitution if not provided
        if self.audit_logger is None:
            self.audit_logger = AuditLogger(agent_name=self.constitution.agent_name)
        if self.risk_scanner is None:
            self.risk_scanner = RiskScanner(self.constitution)
        if self.hook_chain is None:
            self.hook_chain = HookChain()
        if self.token_budget is None:
            self.token_budget = TokenBudget()


class HarnessWrapper:
    """Central governance engine that wraps tool execution.

    Thread-safe for async usage. Maintains per-session state
    for rate limiting and cost tracking.
    """

    def __init__(self, config: HarnessConfig):
        self._config = config
        self._constitution = config.constitution
        self._audit = config.audit_logger
        self._risk = config.risk_scanner
        self._hooks = config.hook_chain
        self._token_budget = config.token_budget
        self._executor = config.tool_executor

        # Per-session state
        self._tool_call_counts: dict[str, int] = {}
        self._session_cost: float = 0.0
        self._total_calls: int = 0

    # --- Public API ---

    @property
    def constitution(self) -> Constitution:
        """The active constitution."""
        return self._constitution

    @property
    def session_cost(self) -> float:
        """Total accumulated cost in this session (USD)."""
        return self._session_cost

    @property
    def total_calls(self) -> int:
        """Total tool calls in this session."""
        return self._total_calls

    @property
    def audit_logger(self) -> AuditLogger:
        """Access the audit logger for diagnostics."""
        return self._audit

    @property
    def token_budget(self) -> TokenBudget:
        """Access the token budget tracker."""
        return self._token_budget

    def add_cost(self, amount: float) -> None:
        """Manually add cost (e.g., from LLM calls tracked separately)."""
        self._session_cost += amount

    def reset_session(self) -> None:
        """Reset all per-session counters."""
        self._tool_call_counts.clear()
        self._session_cost = 0.0
        self._total_calls = 0
        self._token_budget.reset()

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: Any,
        *,
        executor: Optional[ToolExecutor] = None,
        cost_estimate: float = 0.0,
        token_estimate: int = 0,
    ) -> Any:
        """Execute a tool call through the 6-step governance pipeline.

        Args:
            tool_name: The tool identifier.
            tool_input: Arguments/input for the tool.
            executor: Override tool executor for this call.
            cost_estimate: Estimated cost in USD for budget gating.
            token_estimate: Estimated token count for token budget gating.

        Returns:
            The tool execution result (potentially transformed by hooks).

        Raises:
            ToolNotAllowedError: Tool not in constitution allowlist.
            SessionLimitError: Per-session call limit exceeded.
            RiskDetectedError: Dangerous pattern found in input.
            BudgetExceededError: Session budget ceiling reached.
            TokenBudgetExceededError: Token budget ceiling reached.
            PermissionDeniedError: HITL rejection or path violation.
        """
        tool_exec = executor or self._executor
        start_time = time.monotonic()

        # ── Step 1: Permission Check ──
        if not self._constitution.is_tool_allowed(tool_name):
            self._audit.log_denied(tool_name, "NOT_IN_ALLOWLIST", tool_input)
            raise ToolNotAllowedError(
                f"Tool '{tool_name}' is not allowed by constitution",
                tool_name=tool_name,
            )

        # ── Step 2: Rate Limit Check ──
        perm = self._constitution.get_permission(tool_name)
        current_count = self._tool_call_counts.get(tool_name, 0)
        if perm and current_count >= perm.max_calls_per_session:
            self._audit.log_denied(
                tool_name,
                f"SESSION_LIMIT_EXCEEDED: {current_count}/{perm.max_calls_per_session}",
                tool_input,
            )
            raise SessionLimitError(
                f"Tool '{tool_name}' exceeded session limit: "
                f"{current_count}/{perm.max_calls_per_session}",
                tool_name=tool_name,
            )

        # ── Step 3: Risk Scan ──
        risk_result = self._risk.scan(tool_name, tool_input)
        if risk_result.is_risky:
            self._audit.log_denied(
                tool_name,
                f"RISK_DETECTED: {risk_result.risk_category}",
                tool_input,
            )
            raise RiskDetectedError(
                f"Risky pattern detected in '{tool_name}': {risk_result.risk_category}",
                tool_name=tool_name,
                pattern=risk_result.matched_pattern,
            )

        # ── Step 4: Budget Gate ──
        projected_cost = self._session_cost + cost_estimate
        if projected_cost > self._constitution.max_budget_usd:
            self._audit.log_denied(
                tool_name,
                f"BUDGET_EXCEEDED: ${projected_cost:.4f} > ${self._constitution.max_budget_usd:.2f}",
                tool_input,
            )
            raise BudgetExceededError(
                f"Budget exceeded: ${projected_cost:.4f} > ${self._constitution.max_budget_usd:.2f}",
                tool_name=tool_name,
                current_cost=self._session_cost,
                limit=self._constitution.max_budget_usd,
            )

        # ── Step 4a: Token Budget Gate ──
        if token_estimate > 0 and self._token_budget:
            try:
                self._token_budget.gate(token_estimate, tool_name=tool_name)
            except Exception as token_err:
                self._audit.log_denied(
                    tool_name,
                    f"TOKEN_BUDGET_EXCEEDED: {self._token_budget.used_tokens}+{token_estimate}"
                    f" > {self._token_budget.max_tokens}",
                    tool_input,
                )
                raise

        # ── Step 4b: HITL Gate ──
        if self._constitution.requires_human_approval(tool_name):
            if self._config.hitl_callback:
                approved = await self._config.hitl_callback(tool_name, tool_input)
                if not approved:
                    self._audit.log_denied(tool_name, "HUMAN_REJECTED", tool_input)
                    raise PermissionDeniedError(
                        f"Tool '{tool_name}' rejected by human reviewer",
                        tool_name=tool_name,
                    )

        # ── Step 5: Pre-Hooks → Execute → Post-Hooks ──
        try:
            # Pre-hooks (transform input)
            processed_input = await self._hooks.run_pre_hooks(tool_name, tool_input)

            # Execute
            if tool_exec:
                result = await tool_exec(tool_name, processed_input)
            else:
                # No executor: return input as-is (dry-run / testing mode)
                result = {"tool": tool_name, "input": processed_input, "dry_run": True}

            # Post-hooks (transform output)
            result = await self._hooks.run_post_hooks(tool_name, result)

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            self._audit.log_error(tool_name, e, tool_input, elapsed_ms=elapsed_ms)
            raise

        # ── Step 6: Audit & Bookkeeping ──
        elapsed_ms = (time.monotonic() - start_time) * 1000
        self._tool_call_counts[tool_name] = current_count + 1
        self._total_calls += 1
        self._session_cost += cost_estimate

        # Record token usage
        if token_estimate > 0 and self._token_budget:
            detail = self._token_budget.get_detail_level().value
            self._token_budget.record(
                tool_name, token_estimate, detail_level=detail,
            )

        self._audit.log_allowed(
            tool_name,
            tool_input,
            elapsed_ms=elapsed_ms,
            session_cost_usd=self._session_cost,
            session_tool_calls=self._total_calls,
        )

        return result

    def is_tool_available(self, tool_name: str, token_estimate: int = 0) -> bool:
        """Quick check if a tool can be called (permission + budget + rate + tokens)."""
        if not self._constitution.is_tool_allowed(tool_name):
            return False
        perm = self._constitution.get_permission(tool_name)
        if perm:
            current = self._tool_call_counts.get(tool_name, 0)
            if current >= perm.max_calls_per_session:
                return False
        if self._session_cost >= self._constitution.max_budget_usd:
            return False
        if token_estimate > 0 and self._token_budget:
            if not self._token_budget.can_afford(token_estimate):
                return False
        return True

    def get_session_summary(self) -> dict[str, Any]:
        """Return a summary of the current session for diagnostics."""
        summary = {
            "agent_name": self._constitution.agent_name,
            "total_calls": self._total_calls,
            "session_cost_usd": round(self._session_cost, 6),
            "budget_remaining_usd": round(
                self._constitution.max_budget_usd - self._session_cost, 6
            ),
            "tool_call_counts": dict(self._tool_call_counts),
            "audit_denied_count": self._audit.denied_count,
            "audit_total_count": self._audit.total_count,
        }
        if self._token_budget:
            summary["token_budget"] = self._token_budget.get_summary()
        return summary
