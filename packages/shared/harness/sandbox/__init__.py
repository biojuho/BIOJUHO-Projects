"""shared.harness.sandbox — Tool permission tiers and isolated execution.

Provides 3-tier permission classification for tools and Docker-based
sandboxed execution for high-risk tool calls.
"""

from .docker_runner import DockerSandboxRunner, SandboxResult
from .policy import SANDBOX_PRESETS, SandboxPolicy, ToolPermissionLevel

__all__ = [
    "ToolPermissionLevel",
    "SandboxPolicy",
    "SANDBOX_PRESETS",
    "DockerSandboxRunner",
    "SandboxResult",
]
