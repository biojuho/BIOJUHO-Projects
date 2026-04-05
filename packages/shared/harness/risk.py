"""shared.harness.risk — Risk pattern scanner for tool inputs.

Detects dangerous patterns in tool call inputs before execution.
Acts as the "security checkpoint" — all inputs are scanned against
both the Constitution's risk_patterns and tool-specific blocked_patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from .constitution import Constitution


# Built-in patterns that are always checked regardless of Constitution
_BUILTIN_RISK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"rm\s+-rf\s+/", "destructive_rm_rf"),
    (r"DROP\s+(TABLE|DATABASE)\s+", "sql_drop"),
    (r"os\.system\s*\(", "unsafe_os_system"),
    (r"eval\s*\(", "unsafe_eval"),
    (r"exec\s*\(", "unsafe_exec"),
    (r"__import__\s*\(", "unsafe_import"),
    (r"subprocess\.call\s*\(", "unsafe_subprocess"),
    (r"shutil\.rmtree\s*\(", "destructive_rmtree"),
)


@dataclass(frozen=True)
class RiskResult:
    """Result of a risk scan.

    Attributes:
        is_risky: Whether any risk pattern matched.
        matched_pattern: The regex pattern that matched (if any).
        risk_category: Human-readable category of the risk.
        scanned_text_length: Length of text that was scanned.
    """

    is_risky: bool
    matched_pattern: str = ""
    risk_category: str = ""
    scanned_text_length: int = 0

    @staticmethod
    def safe(text_length: int = 0) -> RiskResult:
        """Factory for a clean (no risk) result."""
        return RiskResult(is_risky=False, scanned_text_length=text_length)


class RiskScanner:
    """Scans tool inputs against risk patterns before execution.

    Combines three layers of defense:
    1. Built-in patterns (always active, cannot be disabled)
    2. Constitution-level risk_patterns (global for the agent)
    3. Tool-specific blocked_patterns (per-tool granularity)
    """

    def __init__(
        self,
        constitution: Constitution,
        *,
        enable_builtins: bool = True,
        extra_patterns: list[tuple[str, str]] | None = None,
    ):
        self._constitution = constitution
        self._enable_builtins = enable_builtins

        # Compile all patterns once for performance
        self._compiled_builtins: list[tuple[re.Pattern, str]] = []
        if enable_builtins:
            for pattern, category in _BUILTIN_RISK_PATTERNS:
                self._compiled_builtins.append(
                    (re.compile(pattern, re.IGNORECASE), category)
                )

        self._compiled_constitution: list[tuple[re.Pattern, str]] = []
        for pattern in constitution.risk_patterns:
            try:
                self._compiled_constitution.append(
                    (re.compile(pattern, re.IGNORECASE), f"constitution:{pattern}")
                )
            except re.error:
                pass  # Skip invalid regex quietly

        self._extra: list[tuple[re.Pattern, str]] = []
        if extra_patterns:
            for pattern, category in extra_patterns:
                try:
                    self._extra.append(
                        (re.compile(pattern, re.IGNORECASE), category)
                    )
                except re.error:
                    pass

    def _flatten_input(self, tool_input: Any) -> str:
        """Recursively flatten input to a single scannable string."""
        if isinstance(tool_input, str):
            return tool_input
        if isinstance(tool_input, dict):
            parts = []
            for v in tool_input.values():
                parts.append(self._flatten_input(v))
            return " ".join(parts)
        if isinstance(tool_input, (list, tuple)):
            return " ".join(self._flatten_input(item) for item in tool_input)
        return str(tool_input)

    def scan(self, tool_name: str, tool_input: Any) -> RiskResult:
        """Scan tool input for risk patterns.

        Returns a RiskResult indicating whether the input is safe.
        Checks in order: builtins → constitution → tool-specific → extra.
        """
        text = self._flatten_input(tool_input)
        text_len = len(text)

        # Layer 1: Built-in patterns
        for compiled, category in self._compiled_builtins:
            if compiled.search(text):
                return RiskResult(
                    is_risky=True,
                    matched_pattern=compiled.pattern,
                    risk_category=category,
                    scanned_text_length=text_len,
                )

        # Layer 2: Constitution-level patterns
        for compiled, category in self._compiled_constitution:
            if compiled.search(text):
                return RiskResult(
                    is_risky=True,
                    matched_pattern=compiled.pattern,
                    risk_category=category,
                    scanned_text_length=text_len,
                )

        # Layer 3: Tool-specific blocked_patterns
        perm = self._constitution.get_permission(tool_name)
        if perm:
            blocked = perm.is_input_blocked(text)
            if blocked:
                return RiskResult(
                    is_risky=True,
                    matched_pattern=blocked,
                    risk_category=f"tool_blocked:{tool_name}",
                    scanned_text_length=text_len,
                )

        # Layer 4: Extra custom patterns
        for compiled, category in self._extra:
            if compiled.search(text):
                return RiskResult(
                    is_risky=True,
                    matched_pattern=compiled.pattern,
                    risk_category=category,
                    scanned_text_length=text_len,
                )

        return RiskResult.safe(text_len)
