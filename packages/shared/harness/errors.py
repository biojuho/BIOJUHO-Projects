"""shared.harness.errors — Harness-specific exception hierarchy.

Mirrors the pattern from shared.llm.errors, providing typed exceptions
so callers can catch and handle governance failures specifically.
"""

from __future__ import annotations


class HarnessError(Exception):
    """Base exception for all harness governance failures."""

    def __init__(self, message: str, *, tool_name: str = "", context: dict | None = None):
        super().__init__(message)
        self.tool_name = tool_name
        self.context = context or {}


class ToolNotAllowedError(HarnessError):
    """Raised when a tool is not in the constitution allowlist."""


class PermissionDeniedError(HarnessError):
    """Raised when a tool call violates path or pattern restrictions."""


class RiskDetectedError(HarnessError):
    """Raised when a tool input matches a blocked risk pattern."""

    def __init__(self, message: str, *, tool_name: str = "", pattern: str = "", **kwargs):
        super().__init__(message, tool_name=tool_name, **kwargs)
        self.pattern = pattern


class BudgetExceededError(HarnessError):
    """Raised when session or daily budget ceiling is reached."""

    def __init__(self, message: str, *, current_cost: float = 0.0, limit: float = 0.0, **kwargs):
        super().__init__(message, **kwargs)
        self.current_cost = current_cost
        self.limit = limit


class HumanRejectedError(HarnessError):
    """Raised when a HITL gate rejects the tool call."""


class SessionLimitError(HarnessError):
    """Raised when per-session tool call count is exhausted."""
