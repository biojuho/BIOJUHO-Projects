"""shared.harness.sandbox.docker_runner — Docker-based isolated tool execution.

비유: 폭발물 처리반의 방폭 컨테이너
  - 위험한 도구(shell_execute 등)를 격리된 컨테이너에서 실행
  - 실패해도 호스트 시스템에 영향 없음
  - 타임아웃, 메모리/CPU 제한, 네트워크 차단 적용

Docker가 없는 환경에서는 subprocess 기반 폴백을 제공합니다.

Usage::

    runner = DockerSandboxRunner(image="python:3.12-slim")
    result = await runner.run(
        command="python -c 'print(1+1)'",
        policy=SandboxPolicy(level=ToolPermissionLevel.WRITE_SYSTEM),
    )
    print(result.stdout)  # "2"
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .policy import SandboxPolicy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SandboxResult:
    """Result of a sandboxed tool execution.

    Attributes:
        success: Whether execution completed without error.
        exit_code: Process/container exit code.
        stdout: Standard output (truncated to max_output_chars).
        stderr: Standard error (truncated to max_output_chars).
        timed_out: Whether execution was killed due to timeout.
        execution_method: "docker" or "subprocess".
        elapsed_seconds: Wall-clock execution time.
    """

    success: bool
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    execution_method: str = "subprocess"
    elapsed_seconds: float = 0.0


class DockerSandboxRunner:
    """Runs tool commands in Docker containers with resource constraints.

    Falls back to subprocess-based execution if Docker is unavailable,
    applying timeout and basic isolation where possible.
    """

    DEFAULT_IMAGE = "python:3.12-slim"
    MAX_OUTPUT_CHARS = 50_000

    def __init__(
        self,
        image: str | None = None,
        work_dir: str | Path | None = None,
    ) -> None:
        self._image = image or self.DEFAULT_IMAGE
        self._work_dir = Path(work_dir) if work_dir else None
        self._docker_available: bool | None = None

    @property
    def docker_available(self) -> bool:
        """Check if Docker CLI is available on the system."""
        if self._docker_available is None:
            self._docker_available = shutil.which("docker") is not None
        return self._docker_available

    async def run(
        self,
        command: str,
        policy: SandboxPolicy,
        *,
        env: dict[str, str] | None = None,
        mounts: list[dict[str, str]] | None = None,
    ) -> SandboxResult:
        """Execute a command under the given sandbox policy.

        Args:
            command: Shell command to execute.
            policy: SandboxPolicy defining resource constraints.
            env: Additional environment variables.
            mounts: Volume mounts [{"src": ..., "dst": ..., "mode": "ro"|"rw"}].

        Returns:
            SandboxResult with stdout/stderr and metadata.
        """
        if not policy.sandbox:
            # No sandbox required — run directly
            return await self._run_subprocess(command, policy, env=env)

        if self.docker_available:
            return await self._run_docker(command, policy, env=env, mounts=mounts)

        logger.warning(
            "Docker not available, falling back to subprocess isolation "
            "for tool execution. Install Docker for full sandboxing."
        )
        return await self._run_subprocess(command, policy, env=env)

    def _docker_environment(self, policy: SandboxPolicy, env: dict[str, str] | None) -> dict[str, str]:
        merged_env = dict(env or {})
        for var in policy.allowed_env_vars:
            if var not in merged_env:
                merged_env[var] = os.environ.get(var, "")
        return merged_env

    def _docker_command(
        self,
        command: str,
        policy: SandboxPolicy,
        *,
        env: dict[str, str] | None = None,
        mounts: list[dict[str, str]] | None = None,
    ) -> list[str]:
        docker_opts = policy.to_docker_options()
        cmd_parts: list[str] = [
            "docker",
            "run",
            "--rm",
            "--memory",
            docker_opts["mem_limit"],
            "--cpus",
            str(policy.cpu_limit),
        ]
        for sec_opt in docker_opts.get("security_opt", []):
            cmd_parts.extend(["--security-opt", sec_opt])
        for cap in docker_opts.get("cap_drop", []):
            cmd_parts.extend(["--cap-drop", cap])
        if docker_opts.get("read_only"):
            cmd_parts.append("--read-only")
            cmd_parts.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
        if docker_opts.get("network_mode") == "none":
            cmd_parts.extend(["--network", "none"])
        for key, val in self._docker_environment(policy, env).items():
            cmd_parts.extend(["-e", f"{key}={val}"])
        for mount in mounts or []:
            mode = mount.get("mode", "ro")
            cmd_parts.extend(["-v", f"{mount['src']}:{mount['dst']}:{mode}"])
        if self._work_dir:
            cmd_parts.extend(["-w", "/workspace"])
            cmd_parts.extend(["-v", f"{self._work_dir}:/workspace:ro"])
        cmd_parts.extend([self._image, "sh", "-c", command])
        return cmd_parts

    def _subprocess_environment(self, policy: SandboxPolicy, env: dict[str, str] | None) -> dict[str, str]:
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", os.environ.get("USERPROFILE", "")),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        }
        for var in policy.allowed_env_vars:
            val = os.environ.get(var, "")
            if val:
                clean_env[var] = val
        if env:
            clean_env.update(env)
        return clean_env

    async def _create_subprocess(self, command: str, env: dict[str, str]) -> asyncio.subprocess.Process:
        cwd = str(self._work_dir) if self._work_dir else None
        if os.name == "nt":
            shell_executable = os.environ.get("COMSPEC") or shutil.which("cmd.exe") or "cmd.exe"
            for key in ("COMSPEC", "PATHEXT", "SystemRoot", "WINDIR"):
                value = os.environ.get(key)
                if value:
                    env.setdefault(key, value)
            return await asyncio.create_subprocess_shell(
                command,
                executable=shell_executable,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )
        shell_executable = shutil.which("sh") or "sh"
        return await asyncio.create_subprocess_exec(
            shell_executable,
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

    async def _kill_process(self, proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass

    def _process_result(
        self,
        *,
        proc: asyncio.subprocess.Process,
        stdout_bytes: bytes | None,
        stderr_bytes: bytes | None,
        elapsed: float,
        execution_method: str,
    ) -> SandboxResult:
        stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
        stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
        return SandboxResult(
            success=proc.returncode == 0,
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout[: self.MAX_OUTPUT_CHARS],
            stderr=stderr[: self.MAX_OUTPUT_CHARS],
            timed_out=False,
            execution_method=execution_method,
            elapsed_seconds=round(elapsed, 3),
        )

    @staticmethod
    def _failure_result(*, stderr: str, elapsed: float, execution_method: str, timed_out: bool = False) -> SandboxResult:
        return SandboxResult(
            success=False,
            exit_code=-1,
            stderr=stderr,
            timed_out=timed_out,
            execution_method=execution_method,
            elapsed_seconds=round(elapsed, 3),
        )

    async def _run_docker(
        self,
        command: str,
        policy: SandboxPolicy,
        *,
        env: dict[str, str] | None = None,
        mounts: list[dict[str, str]] | None = None,
    ) -> SandboxResult:
        """Execute command in a Docker container."""
        cmd_parts = self._docker_command(command, policy, env=env, mounts=mounts)

        # Environment variables — resolve from host env consistently
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=policy.timeout_seconds,
            )
            elapsed = time.monotonic() - start
            return self._process_result(
                proc=proc,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
                elapsed=elapsed,
                execution_method="docker",
            )

        except TimeoutError:
            elapsed = time.monotonic() - start
            await self._kill_process(proc)
            logger.warning("Docker sandbox timed out after %ds", policy.timeout_seconds)
            return self._failure_result(
                stderr=f"Sandbox timeout after {policy.timeout_seconds}s",
                timed_out=True,
                execution_method="docker",
                elapsed=elapsed,
            )

        except Exception as e:
            elapsed = time.monotonic() - start
            logger.exception("Docker sandbox execution failed")
            return self._failure_result(stderr=str(e), execution_method="docker", elapsed=elapsed)

    async def _run_subprocess(
        self,
        command: str,
        policy: SandboxPolicy,
        *,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """Fallback: execute command as a subprocess with timeout."""
        clean_env = self._subprocess_environment(policy, env)
        start = time.monotonic()
        try:
            proc = await self._create_subprocess(command, clean_env)
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=policy.timeout_seconds,
            )
            elapsed = time.monotonic() - start
            return self._process_result(
                proc=proc,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
                elapsed=elapsed,
                execution_method="subprocess",
            )

        except TimeoutError:
            elapsed = time.monotonic() - start
            await self._kill_process(proc)
            logger.warning("Subprocess timed out after %ds", policy.timeout_seconds)
            return self._failure_result(
                stderr=f"Subprocess timeout after {policy.timeout_seconds}s",
                timed_out=True,
                execution_method="subprocess",
                elapsed=elapsed,
            )

        except Exception as e:
            elapsed = time.monotonic() - start
            logger.exception("Subprocess execution failed")
            return self._failure_result(stderr=str(e), execution_method="subprocess", elapsed=elapsed)
