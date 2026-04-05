"""shared.harness.constitution — YAML-based declarative governance rules.

Pattern Reference: AutoHarness YAML Constitution
Analogy: "교통법규집" — 에이전트가 어떤 도구를 쓸 수 있고,
         어떤 경로에 접근 가능한지를 미리 정의한 규칙서.

Usage::

    constitution = Constitution.from_yaml("constitutions/getdaytrends.yaml")
    assert constitution.is_tool_allowed("web_search")
    assert not constitution.is_tool_allowed("file_delete")
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ToolPermission:
    """Permission rules for a single tool.

    Attributes:
        name: Tool identifier (e.g. "web_search", "file_write").
        allowed: Whether the tool is enabled at all.
        max_calls_per_session: Rate limit per agent session (circuit breaker).
        requires_approval: If True, a HITL gate fires before execution.
        allowed_paths: Glob patterns for filesystem tools (whitelist).
        blocked_patterns: Regex patterns to block in tool inputs.
    """

    name: str
    allowed: bool = True
    max_calls_per_session: int = 100
    requires_approval: bool = False
    allowed_paths: tuple[str, ...] = ()
    blocked_patterns: tuple[str, ...] = ()

    def is_path_allowed(self, path: str) -> bool:
        """Check if a filesystem path matches the allowlist.

        Returns True if no allowed_paths are defined (open policy)
        or if the path matches at least one pattern.
        """
        if not self.allowed_paths:
            return True
        normalized = path.replace("\\", "/")
        return any(fnmatch.fnmatch(normalized, p.replace("\\", "/")) for p in self.allowed_paths)

    def is_input_blocked(self, text: str) -> Optional[str]:
        """Check if input text matches any blocked pattern.

        Returns the matching pattern string if blocked, None if clean.
        """
        for pattern in self.blocked_patterns:
            if re.search(pattern, text):
                return pattern
        return None


@dataclass
class Constitution:
    """Declarative governance ruleset for an AI agent.

    Defines what an agent is allowed to do, enforcing the
    Principle of Least Privilege: anything not explicitly
    permitted is denied.
    """

    agent_name: str
    max_budget_usd: float = 2.0
    max_tokens_per_turn: int = 8000
    tool_permissions: Dict[str, ToolPermission] = field(default_factory=dict)
    risk_patterns: tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Constitution:
        """Load a constitution from a YAML file.

        Raises:
            ImportError: If PyYAML is not installed.
            FileNotFoundError: If the constitution file doesn't exist.
            ValueError: If the YAML structure is invalid.
        """
        if yaml is None:
            raise ImportError(
                "PyYAML is required for Constitution.from_yaml(). "
                "Install with: pip install pyyaml"
            )

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Constitution file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"Constitution YAML must be a mapping, got {type(config).__name__}")

        agent_name = config.get("agent_name", path.stem)

        permissions: dict[str, ToolPermission] = {}
        for tool_cfg in config.get("tools", []):
            if not isinstance(tool_cfg, dict) or "name" not in tool_cfg:
                continue
            perm = ToolPermission(
                name=tool_cfg["name"],
                allowed=tool_cfg.get("allowed", True),
                max_calls_per_session=tool_cfg.get("max_calls", 100),
                requires_approval=tool_cfg.get("requires_approval", False),
                allowed_paths=tuple(tool_cfg.get("allowed_paths", [])),
                blocked_patterns=tuple(tool_cfg.get("blocked_patterns", [])),
            )
            permissions[perm.name] = perm

        return cls(
            agent_name=agent_name,
            max_budget_usd=config.get("max_budget_usd", 2.0),
            max_tokens_per_turn=config.get("max_tokens_per_turn", 8000),
            tool_permissions=permissions,
            risk_patterns=tuple(config.get("risk_patterns", [])),
            metadata=config.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Constitution:
        """Create a Constitution from a plain dictionary (for testing)."""
        permissions: dict[str, ToolPermission] = {}
        for tool_cfg in data.get("tools", []):
            perm = ToolPermission(
                name=tool_cfg["name"],
                allowed=tool_cfg.get("allowed", True),
                max_calls_per_session=tool_cfg.get("max_calls", 100),
                requires_approval=tool_cfg.get("requires_approval", False),
                allowed_paths=tuple(tool_cfg.get("allowed_paths", [])),
                blocked_patterns=tuple(tool_cfg.get("blocked_patterns", [])),
            )
            permissions[perm.name] = perm

        return cls(
            agent_name=data.get("agent_name", "test-agent"),
            max_budget_usd=data.get("max_budget_usd", 2.0),
            max_tokens_per_turn=data.get("max_tokens_per_turn", 8000),
            tool_permissions=permissions,
            risk_patterns=tuple(data.get("risk_patterns", [])),
            metadata=data.get("metadata", {}),
        )

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is in the allowlist and enabled.

        Principle of Least Privilege: unlisted tools are denied.
        """
        perm = self.tool_permissions.get(tool_name)
        if perm is None:
            return False
        return perm.allowed

    def requires_human_approval(self, tool_name: str) -> bool:
        """Check if a tool requires HITL approval.

        Unregistered tools always require approval (fail-safe).
        """
        perm = self.tool_permissions.get(tool_name)
        return perm.requires_approval if perm else True

    def get_permission(self, tool_name: str) -> Optional[ToolPermission]:
        """Get the ToolPermission for a specific tool, or None."""
        return self.tool_permissions.get(tool_name)

    def tool_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self.tool_permissions.keys())

    def allowed_tools(self) -> list[str]:
        """List only tools that are allowed."""
        return [name for name, perm in self.tool_permissions.items() if perm.allowed]
