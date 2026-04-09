"""shared.harness.token_tracker — Token Budget Tracking & Auto-Minimization.

Inspired by code-review-graph's token-efficient design philosophy:
  - get_minimal_context() costs ~100 tokens
  - All tools accept detail_level="minimal" | "standard" | "full"
  - Target: ≤5 tool calls per task, ≤800 total tokens of context

This module adds token-level budget tracking alongside the existing
USD-based budget gate in HarnessWrapper. When usage exceeds configurable
thresholds, it automatically downshifts to minimal detail level.

Usage::

    from shared.harness.token_tracker import TokenBudget

    budget = TokenBudget(max_tokens=50_000)
    budget.record(tool_name="llm_generate", tokens=1_200)

    if budget.should_minimize():
        detail_level = "minimal"  # auto-downshift

    budget.gate(estimated=3_000)  # raises TokenBudgetExceededError if over
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DetailLevel(str, Enum):
    """Output verbosity levels, matching CRG's detail_level parameter."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    FULL = "full"


class TokenBudgetExceededError(Exception):
    """Raised when token budget ceiling is reached."""

    def __init__(
        self,
        message: str,
        *,
        used: int = 0,
        limit: int = 0,
        tool_name: str = "",
    ):
        super().__init__(message)
        self.used = used
        self.limit = limit
        self.tool_name = tool_name


@dataclass
class TokenUsageRecord:
    """Single token usage event."""

    timestamp: float
    tool_name: str
    tokens: int
    detail_level: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenBudget:
    """Token-level budget tracker with auto-minimization.

    Provides three capabilities:
    1. Track cumulative token usage per session
    2. Auto-downshift detail_level when thresholds are exceeded
    3. Hard gate to block calls that would exceed the budget

    Thresholds (configurable):
        - minimize_threshold: 0.7 → switch to "minimal" at 70% usage
        - warn_threshold: 0.9 → log warning at 90% usage

    Thread-safe for async usage (single-writer pattern).
    """

    max_tokens: int = 50_000
    minimize_threshold: float = 0.7
    warn_threshold: float = 0.9
    _used_tokens: int = field(default=0, repr=False)
    _tool_usage: dict[str, int] = field(default_factory=dict, repr=False)
    _tool_call_counts: dict[str, int] = field(default_factory=dict, repr=False)
    _records: list[TokenUsageRecord] = field(default_factory=list, repr=False)
    _forced_level: DetailLevel | None = field(default=None, repr=False)

    @property
    def used_tokens(self) -> int:
        """Total tokens consumed in this session."""
        return self._used_tokens

    @property
    def remaining_tokens(self) -> int:
        """Tokens remaining before budget ceiling."""
        return max(0, self.max_tokens - self._used_tokens)

    @property
    def usage_ratio(self) -> float:
        """Current usage as a ratio (0.0 to 1.0+)."""
        if self.max_tokens <= 0:
            return 1.0
        return self._used_tokens / self.max_tokens

    @property
    def total_calls(self) -> int:
        """Total tool calls recorded."""
        return sum(self._tool_call_counts.values())

    # --- Detail Level Logic ---

    def force_detail_level(self, level: DetailLevel | None) -> None:
        """Override automatic detail level selection.

        Set to None to restore automatic behavior.
        """
        self._forced_level = level

    def get_detail_level(self) -> DetailLevel:
        """Determine the optimal detail level based on budget state.

        Priority: forced override > threshold-based auto-selection.
        """
        if self._forced_level is not None:
            return self._forced_level

        ratio = self.usage_ratio
        if ratio >= self.warn_threshold:
            return DetailLevel.MINIMAL
        if ratio >= self.minimize_threshold:
            return DetailLevel.MINIMAL
        return DetailLevel.STANDARD

    def should_minimize(self) -> bool:
        """True when usage exceeds minimize_threshold.

        Convenience method matching CRG's pattern where tools check
        this before generating output.
        """
        if self._forced_level == DetailLevel.MINIMAL:
            return True
        return self.usage_ratio >= self.minimize_threshold

    # --- Budget Gate ---

    def gate(self, estimated: int, *, tool_name: str = "") -> bool:
        """Check if an estimated token usage would exceed the budget.

        Args:
            estimated: Expected token count for the upcoming call.
            tool_name: For error reporting.

        Returns:
            True if the call is within budget.

        Raises:
            TokenBudgetExceededError: If the call would exceed the budget.
        """
        if self._used_tokens + estimated > self.max_tokens:
            raise TokenBudgetExceededError(
                f"Token budget exceeded: {self._used_tokens + estimated:,} > "
                f"{self.max_tokens:,} (tool: {tool_name})",
                used=self._used_tokens,
                limit=self.max_tokens,
                tool_name=tool_name,
            )
        return True

    def can_afford(self, estimated: int) -> bool:
        """Non-raising version of gate(). Returns True if within budget."""
        return self._used_tokens + estimated <= self.max_tokens

    # --- Recording ---

    def record(
        self,
        tool_name: str,
        tokens: int,
        *,
        detail_level: str = "standard",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record actual token usage for a completed tool call.

        Args:
            tool_name: The tool that consumed the tokens.
            tokens: Actual token count used.
            detail_level: The detail level that was used.
            metadata: Optional extra context.
        """
        self._used_tokens += tokens
        self._tool_usage[tool_name] = self._tool_usage.get(tool_name, 0) + tokens
        self._tool_call_counts[tool_name] = self._tool_call_counts.get(tool_name, 0) + 1
        self._records.append(
            TokenUsageRecord(
                timestamp=time.time(),
                tool_name=tool_name,
                tokens=tokens,
                detail_level=detail_level,
                metadata=metadata or {},
            )
        )

        # Threshold-based logging
        ratio = self.usage_ratio
        if ratio >= self.warn_threshold:
            logger.warning(
                "token_budget_warning: %d/%d (%.0f%%) — tool=%s",
                self._used_tokens,
                self.max_tokens,
                ratio * 100,
                tool_name,
            )
        elif ratio >= self.minimize_threshold:
            logger.info(
                "token_budget_minimize: %d/%d (%.0f%%) — auto-downshift",
                self._used_tokens,
                self.max_tokens,
                ratio * 100,
            )

    # --- Session Management ---

    def reset(self) -> None:
        """Reset all session state."""
        self._used_tokens = 0
        self._tool_usage.clear()
        self._tool_call_counts.clear()
        self._records.clear()
        self._forced_level = None

    # --- Reporting ---

    def get_summary(self) -> dict[str, Any]:
        """Return session summary for diagnostics and audit integration."""
        return {
            "used_tokens": self._used_tokens,
            "max_tokens": self.max_tokens,
            "remaining_tokens": self.remaining_tokens,
            "usage_ratio": round(self.usage_ratio, 4),
            "detail_level": self.get_detail_level().value,
            "should_minimize": self.should_minimize(),
            "total_calls": self.total_calls,
            "tool_usage": dict(self._tool_usage),
            "tool_call_counts": dict(self._tool_call_counts),
        }

    def get_top_consumers(self, n: int = 5) -> list[dict[str, Any]]:
        """Return top-N token consuming tools for cost optimization.

        Mirrors CRG's philosophy: know where your tokens go.
        """
        sorted_tools = sorted(
            self._tool_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            {
                "tool": name,
                "tokens": tokens,
                "calls": self._tool_call_counts.get(name, 0),
                "avg_per_call": tokens // max(1, self._tool_call_counts.get(name, 0)),
                "pct_of_total": round(tokens / max(1, self._used_tokens) * 100, 1),
            }
            for name, tokens in sorted_tools[:n]
        ]

    def suggest_next_action(self) -> str:
        """CRG-style 'next_tool_suggestions' — advise caller on best next step.

        Returns a concise suggestion based on current budget state.
        """
        ratio = self.usage_ratio
        if ratio >= 0.95:
            return "STOP: Budget almost exhausted. Finalize and persist results."
        if ratio >= self.warn_threshold:
            return "MINIMIZE: Use detail_level='minimal' for all remaining calls."
        if ratio >= self.minimize_threshold:
            return "DOWNSHIFT: Consider minimal detail for non-critical lookups."
        if self.total_calls == 0:
            return "START: Use get_minimal_context() to survey before deep-diving."
        return "CONTINUE: Budget healthy. Standard detail level OK."
