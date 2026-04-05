"""shared.harness.sandbox — Tool permission tiers and isolated execution.

Provides 3-tier permission classification for tools and Docker-based
sandboxed execution for high-risk tool calls.
"""

from .policy import ToolPermissionLevel, SandboxPolicy, SANDBOX_PRESETS
from .docker_runner import DockerSandboxRunner, SandboxResult

__all__ = [
    "ToolPermissionLevel",
    "SandboxPolicy",
    "SANDBOX_PRESETS",
    "DockerSandboxRunner",
    "SandboxResult",
]
