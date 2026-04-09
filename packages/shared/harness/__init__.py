"""shared.harness — AI Agent Governance & Harness Engineering Module.

Provides declarative governance, tool permission management, audit logging,
risk scanning, and lifecycle hooks for AI agent pipelines.

Architecture: Agent = Model + Harness
  - Model: shared.llm (Unified Client, Fallback Chain, Budget-Aware Routing)
  - Harness: shared.harness (Constitution, Audit, Risk, Hooks, Sandbox)

Inspired by:
  - AutoHarness: YAML Constitution, governance pipelines
  - OpenHarness: Lifecycle hooks, playback mode
  - DeepAgents: Sub-agent orchestration patterns

Usage::

    from shared.harness import HarnessWrapper, Constitution, AuditLogger

    constitution = Constitution.from_yaml("constitutions/getdaytrends.yaml")
    harness = HarnessWrapper(constitution=constitution)

    # Wrap existing tool calls with governance
    result = await harness.execute_tool("web_search", {"query": "AI trends"})
"""

from __future__ import annotations

from .audit import AuditLogger, AuditRecord
from .constitution import Constitution, ToolPermission
from .core import HarnessWrapper, HarnessConfig
from .errors import (
    BudgetExceededError,
    HarnessError,
    PermissionDeniedError,
    RiskDetectedError,
    ToolNotAllowedError,
)
from .hooks import HookChain, PostToolHook, PreToolHook
from .hitl import (
    auto_approve_callback,
    auto_deny_callback,
    create_notifier_hitl_callback,
)
from .risk import RiskResult, RiskScanner
from .token_tracker import (
    DetailLevel,
    TokenBudget,
    TokenBudgetExceededError,
    TokenUsageRecord,
)

# Phase 0: Adapter & Sandbox layer
from .adapters import AbstractHarnessAdapter, AdapterResult, NativeHarnessAdapter, DeepAgentsAdapter
from .sandbox import (
    DockerSandboxRunner,
    SandboxPolicy,
    SandboxResult,
    ToolPermissionLevel,
    SANDBOX_PRESETS,
)
from .sandbox.policy import get_sandbox_policy, get_tool_level

# Phase 1: Validators
from .validators import KoreanQualityValidator, KoreanQualityResult, validate_korean_output

__all__ = [
    # Core
    "HarnessWrapper",
    "HarnessConfig",
    # Constitution
    "Constitution",
    "ToolPermission",
    # Audit
    "AuditLogger",
    "AuditRecord",
    # Risk
    "RiskScanner",
    "RiskResult",
    # Hooks
    "HookChain",
    "PreToolHook",
    "PostToolHook",
    # Errors
    "HarnessError",
    "BudgetExceededError",
    "PermissionDeniedError",
    "RiskDetectedError",
    "ToolNotAllowedError",
    # HITL
    "auto_approve_callback",
    "auto_deny_callback",
    "create_notifier_hitl_callback",
    # Adapters
    "AbstractHarnessAdapter",
    "AdapterResult",
    "NativeHarnessAdapter",
    "DeepAgentsAdapter",
    # Sandbox
    "DockerSandboxRunner",
    "SandboxPolicy",
    "SandboxResult",
    "ToolPermissionLevel",
    "SANDBOX_PRESETS",
    "get_sandbox_policy",
    "get_tool_level",
    # Validators
    "KoreanQualityValidator",
    "KoreanQualityResult",
    "validate_korean_output",
    # Token Budget
    "TokenBudget",
    "TokenBudgetExceededError",
    "TokenUsageRecord",
    "DetailLevel",
]
