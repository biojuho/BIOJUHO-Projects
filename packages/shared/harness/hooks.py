"""shared.harness.hooks — Pre/Post lifecycle hooks for tool execution.

Pattern Reference: OpenHarness lifecycle hooks
Analogy: "공항 보안 게이트" — 탑승(실행) 전후에 검사(Hook)를 수행.

Hooks run in order and can:
- Transform tool inputs (PreToolHook)
- Transform tool outputs (PostToolHook)
- Log, meter, or enrich context at each stage

Usage::

    from shared.harness.hooks import PreToolHook, PostToolHook, HookChain

    class LoggingHook(PreToolHook):
        async def execute(self, tool_name, tool_input):
            print(f"About to run: {tool_name}")
            return tool_input  # pass-through

    chain = HookChain(pre_hooks=[LoggingHook()])
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class PreToolHook(ABC):
    """Hook executed before a tool call.

    Can transform the tool_input. Return the (possibly modified) input.
    Raise an exception to abort the tool call.
    """

    @abstractmethod
    async def execute(self, tool_name: str, tool_input: Any) -> Any:
        """Process and optionally transform tool input before execution."""
        ...


class PostToolHook(ABC):
    """Hook executed after a tool call.

    Can transform the tool_result. Return the (possibly modified) result.
    """

    @abstractmethod
    async def execute(self, tool_name: str, tool_result: Any) -> Any:
        """Process and optionally transform tool result after execution."""
        ...


# --- Built-in Hooks ---


class InputSanitizerHook(PreToolHook):
    """Strip potentially dangerous whitespace/control characters from string inputs."""

    async def execute(self, tool_name: str, tool_input: Any) -> Any:
        if isinstance(tool_input, dict):
            return {
                k: v.strip() if isinstance(v, str) else v
                for k, v in tool_input.items()
            }
        if isinstance(tool_input, str):
            return tool_input.strip()
        return tool_input


class OutputTruncatorHook(PostToolHook):
    """Truncate oversized tool outputs to prevent context window overflow.

    Inspired by DeepAgents' context management — offload large outputs.
    """

    def __init__(self, max_chars: int = 10_000):
        self.max_chars = max_chars

    async def execute(self, tool_name: str, tool_result: Any) -> Any:
        if isinstance(tool_result, str) and len(tool_result) > self.max_chars:
            truncated = tool_result[: self.max_chars]
            suffix = f"\n\n[TRUNCATED: {len(tool_result)} chars → {self.max_chars}]"
            return truncated + suffix
        return tool_result


class MetricsHook(PostToolHook):
    """Collect execution metrics for observability."""

    def __init__(self):
        self.call_counts: dict[str, int] = {}
        self.total_calls: int = 0

    async def execute(self, tool_name: str, tool_result: Any) -> Any:
        self.call_counts[tool_name] = self.call_counts.get(tool_name, 0) + 1
        self.total_calls += 1
        return tool_result  # pass-through


@dataclass
class HookChain:
    """Ordered chain of pre and post hooks.

    Hooks execute sequentially in list order. Each hook receives
    the output of the previous hook (pipeline pattern).
    """

    pre_hooks: list[PreToolHook] = field(default_factory=list)
    post_hooks: list[PostToolHook] = field(default_factory=list)

    async def run_pre_hooks(self, tool_name: str, tool_input: Any) -> Any:
        """Run all pre-hooks in sequence, threading input through."""
        current = tool_input
        for hook in self.pre_hooks:
            try:
                current = await hook.execute(tool_name, current)
            except Exception:
                logger.exception("pre_hook_failed: %s for tool %s", type(hook).__name__, tool_name)
                raise
        return current

    async def run_post_hooks(self, tool_name: str, tool_result: Any) -> Any:
        """Run all post-hooks in sequence, threading result through."""
        current = tool_result
        for hook in self.post_hooks:
            try:
                current = await hook.execute(tool_name, current)
            except Exception:
                logger.exception("post_hook_failed: %s for tool %s", type(hook).__name__, tool_name)
                raise
        return current
