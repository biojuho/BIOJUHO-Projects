"""shared.harness.sandbox.policy — 3-tier tool permission system.

비유: 건물 출입카드 시스템
  - READ_ONLY (로비): 모든 에이전트가 자유롭게 접근
  - WRITE_EXTERNAL (회의실): 외부 서비스 발행, 승인 권장
  - WRITE_SYSTEM (서버실): 관리자 승인 + 보안 에스코트(sandbox) 필수

Usage::

    from shared.harness.sandbox import ToolPermissionLevel, SandboxPolicy

    policy = SandboxPolicy(
        level=ToolPermissionLevel.WRITE_EXTERNAL,
        requires_approval=True,
        sandbox=True,
        timeout_seconds=60,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolPermissionLevel(Enum):
    """3-tier permission classification for agent tools.

    READ_ONLY:      뉴스 수집, 트렌드 분석, DB 조회 등 읽기 전용
    WRITE_EXTERNAL: Notion/X/Slack 발행 등 외부 서비스 쓰기
    WRITE_SYSTEM:   파일시스템 변경, 셸 실행, DB 스키마 변경 등
    """

    READ_ONLY = "read_only"
    WRITE_EXTERNAL = "write_external"
    WRITE_SYSTEM = "write_system"


@dataclass(frozen=True)
class SandboxPolicy:
    """Execution policy for a tool based on its permission level.

    Attributes:
        level: Permission tier.
        requires_approval: HITL gate before execution.
        sandbox: Run in Docker-isolated environment.
        timeout_seconds: Maximum execution time.
        network_access: Allow network in sandbox (whitelist-based).
        allowed_env_vars: Environment variables passed to sandbox.
        memory_limit_mb: Container memory cap.
        cpu_limit: CPU quota (1.0 = one full core).
        read_only_rootfs: Mount root filesystem as read-only.
    """

    level: ToolPermissionLevel
    requires_approval: bool = False
    sandbox: bool = False
    timeout_seconds: int = 30
    network_access: bool = False
    allowed_env_vars: tuple[str, ...] = ()
    memory_limit_mb: int = 512
    cpu_limit: float = 1.0
    read_only_rootfs: bool = True

    def to_docker_options(self) -> dict[str, Any]:
        """Convert policy to Docker container create options."""
        opts: dict[str, Any] = {
            "mem_limit": f"{self.memory_limit_mb}m",
            "nano_cpus": int(self.cpu_limit * 1e9),
            "read_only": self.read_only_rootfs,
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
        }
        if not self.network_access:
            opts["network_mode"] = "none"
        if self.allowed_env_vars:
            opts["environment"] = list(self.allowed_env_vars)
        return opts


# --- Preset Policies ---

SANDBOX_PRESETS: dict[ToolPermissionLevel, SandboxPolicy] = {
    ToolPermissionLevel.READ_ONLY: SandboxPolicy(
        level=ToolPermissionLevel.READ_ONLY,
        requires_approval=False,
        sandbox=False,
        timeout_seconds=30,
    ),
    ToolPermissionLevel.WRITE_EXTERNAL: SandboxPolicy(
        level=ToolPermissionLevel.WRITE_EXTERNAL,
        requires_approval=True,
        sandbox=True,
        timeout_seconds=60,
        network_access=True,  # 외부 API 호출 필요
        memory_limit_mb=256,
    ),
    ToolPermissionLevel.WRITE_SYSTEM: SandboxPolicy(
        level=ToolPermissionLevel.WRITE_SYSTEM,
        requires_approval=True,
        sandbox=True,
        timeout_seconds=10,
        network_access=False,
        memory_limit_mb=128,
        read_only_rootfs=False,  # 파일 쓰기 필요
    ),
}


# --- Tool → Permission Level Registry ---

# 기본 도구 분류 (constitution YAML에서 override 가능)
DEFAULT_TOOL_LEVELS: dict[str, ToolPermissionLevel] = {
    # READ_ONLY
    "web_search": ToolPermissionLevel.READ_ONLY,
    "rss_fetch": ToolPermissionLevel.READ_ONLY,
    "file_read": ToolPermissionLevel.READ_ONLY,
    "database_read": ToolPermissionLevel.READ_ONLY,
    "llm_call": ToolPermissionLevel.READ_ONLY,
    "collect_trends": ToolPermissionLevel.READ_ONLY,
    "analyze_content": ToolPermissionLevel.READ_ONLY,
    # WRITE_EXTERNAL
    "notion_api": ToolPermissionLevel.WRITE_EXTERNAL,
    "publish_to_notion": ToolPermissionLevel.WRITE_EXTERNAL,
    "publish_to_x": ToolPermissionLevel.WRITE_EXTERNAL,
    "send_notification": ToolPermissionLevel.WRITE_EXTERNAL,
    # WRITE_SYSTEM
    "file_write": ToolPermissionLevel.WRITE_SYSTEM,
    "file_delete": ToolPermissionLevel.WRITE_SYSTEM,
    "database_write": ToolPermissionLevel.WRITE_SYSTEM,
    "shell_execute": ToolPermissionLevel.WRITE_SYSTEM,
    "code_run": ToolPermissionLevel.WRITE_SYSTEM,
}


def get_tool_level(
    tool_name: str,
    overrides: dict[str, ToolPermissionLevel] | None = None,
) -> ToolPermissionLevel:
    """Resolve the permission level for a tool.

    Checks overrides first, then defaults. Unknown tools default to
    WRITE_SYSTEM (최소 권한 원칙: 모르면 가장 엄격하게).
    """
    if overrides and tool_name in overrides:
        return overrides[tool_name]
    return DEFAULT_TOOL_LEVELS.get(tool_name, ToolPermissionLevel.WRITE_SYSTEM)


def get_sandbox_policy(
    tool_name: str,
    overrides: dict[str, ToolPermissionLevel] | None = None,
    custom_presets: dict[ToolPermissionLevel, SandboxPolicy] | None = None,
) -> SandboxPolicy:
    """Get the sandbox policy for a tool by resolving its permission level."""
    level = get_tool_level(tool_name, overrides)
    presets = custom_presets or SANDBOX_PRESETS
    return presets.get(level, SANDBOX_PRESETS[ToolPermissionLevel.WRITE_SYSTEM])
