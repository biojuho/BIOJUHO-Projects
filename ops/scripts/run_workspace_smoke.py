#!/usr/bin/env python3
"""
Workspace smoke test runner.
Discovers and executes end-to-end tests across the monorepo projects using virtual environments.
Supports executing pre-defined integration and module workflows natively.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root, rel_unit_path  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

EXCLUDE_REGEX = r"(^|[\\/])(\.agent|\.agents|venv|__pycache__|output|archive|var)([\\/]|$)"
TAIL_LINE_COUNT = 20
DEFAULT_CHECK_TIMEOUT_SECONDS = 600.0
NPM_INSTALL_TIMEOUT_SECONDS = 600
TRANSIENT_RETRY_CHECK = "desci frontend unit tests"
TRANSIENT_RETRY_PATTERNS = (
    "Failed to start threads worker",
    "Failed to start forks worker",
    "Timeout waiting for worker to respond",
)
UV_TRANSIENT_RETRY_PATTERNS = (
    "os error -2147024891",
    "Access is denied",
    "액세스가 거부되었습니다",
)
NPM_TRANSIENT_RETRY_PATTERNS = (
    "EPERM",
    "EBUSY",
    "operation not permitted",
    "Permission denied",
)
TRANSIENT_RETRY_MAX = 2
WORKSPACE_SYNC_SENTINELS: dict[str, tuple[str, ...]] = {
    "workspace regression tests": ("fastapi", "sqlalchemy", "aiosqlite", "mcp.server.fastmcp", "pypdf"),
    "shared package tests": ("sqlalchemy", "pydantic", "httpx", "google.genai"),
    "desci backend smoke": ("fastapi",),
    "agriguard backend tests": ("fastapi", "sqlalchemy"),
    "DailyNews unit tests": ("mcp.server.fastmcp",),
    "getdaytrends tests": ("aiosqlite", "sqlalchemy"),
    "cie tests": ("loguru", "sqlalchemy", "pydantic", "httpx"),
}
UV_EXTRA_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "workspace regression tests": (
        "fastapi>=0.115.0,<1.0",
        "sqlalchemy>=2.0.0,<3.0",
        "aiosqlite>=0.19.0,<1.0",
        "pypdf>=4.0.0,<5.0",
    ),
    "shared package tests": (
        "sqlalchemy>=2.0.0,<3.0",
        "pydantic>=2.0.0,<3.0",
        "httpx>=0.27.0",
        "google-genai>=1.0.0,<2.0",
    ),
    "desci backend smoke": (
        "fastapi>=0.115.0,<1.0",
        "uvicorn>=0.32.0,<1.0",
        "python-dotenv>=1.0.0",
        "firebase-admin>=6.1.0,<7.0",
        "langchain>=0.3.0,<1.0",
        "langchain-openai>=0.3.0,<1.0",
        "langchain-google-genai>=2.0.0,<3.0",
        "qdrant-client>=1.9.1,<2.0",
        "pydantic>=2.0.0,<3.0",
        "pydantic-settings>=2.0.0,<3.0",
        "structlog>=24.0.0,<26.0",
        "aiohttp>=3.10.0,<4.0",
        "beautifulsoup4>=4.12.0",
        "python-multipart>=0.0.9",
        "web3>=7.0.0,<8.0",
        "pypdf>=4.0.0,<5.0",
        "numpy>=1.26.0,<3.0",
        "apscheduler>=3.10.0,<4.0",
        "duckduckgo-search>=6.0.0,<8.0",
        "youtube-transcript-api>=1.0.0,<2.0",
        "httpx>=0.27.0",
        "slowapi>=0.1.9,<1.0",
        "stripe>=9.0.0,<12.0",
        "prometheus_client>=0.21.0",
        "redis>=5.0.0,<6.0.0",
        "pika>=1.3.0,<2.0.0",
    ),
    "getdaytrends tests": (
        "respx>=0.21.0,<1.0",
        "sqlalchemy>=2.0.0,<3.0",
        "redis>=5.0.0,<8.0",
    ),
    "cie tests": (
        "loguru>=0.7.0,<1.0",
        "sqlalchemy>=2.0.0,<3.0",
        "pydantic>=2.0.0,<3.0",
        "httpx>=0.27.0",
    ),
}
FORCE_UV_CHECKS = {
    "desci backend smoke",
    "agriguard backend tests",
    "getdaytrends tests",
}
USE_UV_ISOLATED_RUNNER = False


@dataclass
class Check:
    scope: str
    name: str
    cwd: str
    command: list[str]


@dataclass
class Result:
    scope: str
    name: str
    cwd: str
    command: str
    returncode: int
    ok: bool
    stdout_tail: str
    stderr_tail: str
    elapsed_seconds: float = 0.0
    started_at_unix_nano: int = 0
    ended_at_unix_nano: int = 0


def format_command(command: Sequence[str]) -> str:
    parts: list[str] = []
    for part in command:
        if part == "":
            parts.append('""')
        elif any(ch.isspace() for ch in part):
            escaped = part.replace('"', '\\"')
            parts.append(f'"{escaped}"')
        else:
            parts.append(part)
    return " ".join(parts)


def decode_output(data: bytes | None) -> str:
    if not data:
        return ""
    return data.decode("utf-8", errors="replace")


def tail_lines(text: str, line_count: int = TAIL_LINE_COUNT) -> str:
    lines = text.splitlines()
    if len(lines) <= line_count:
        return text
    return "\n".join(lines[-line_count:])


def compile_command(python_exe: str, *targets: str) -> list[str]:
    return [python_exe, "-m", "compileall", "-q", "-x", EXCLUDE_REGEX, *targets]


def slugify_check_name(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    compact = "-".join(part for part in cleaned.split("-") if part) or "check"
    digest = hashlib.sha1(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
    return f"{compact[:40]}-{digest}"


def build_pythonpath(root: Path, env: dict[str, str] | None = None) -> str:
    env_map = env or os.environ
    existing_pythonpath = env_map.get("PYTHONPATH", "")
    candidates = [
        root,
        root / "packages",
        root / "automation",
        root / "apps" / "desci-platform",
        root / "apps" / "AgriGuard" / "backend",
        root / "automation" / "DailyNews" / "src",
        root / "automation" / "DailyNews" / "scripts",
    ]

    parts: list[str] = []
    seen: set[str] = set()
    for candidate_path in candidates:
        if not candidate_path.exists():
            continue
        value = str(candidate_path)
        dedupe_key = value.lower() if os.name == "nt" else value
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        parts.append(value)

    if existing_pythonpath:
        parts.append(existing_pythonpath)

    return os.pathsep.join(parts)


def has_module(python_exe: str, module_name: str) -> bool:
    try:
        proc = subprocess.run(
            [python_exe, "-c", f"import {module_name}"],
            capture_output=True,
            text=False,
            shell=False,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0


def resolve_python_executable(root: Path) -> str:
    venv_python = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    candidates = [
        root / ".venv" / venv_python,
        root / "venv" / venv_python,
        Path(sys.executable),
    ]

    existing: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate.exists():
            continue
        value = str(candidate)
        dedupe_key = value.lower() if os.name == "nt" else value
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        existing.append(value)

    if not existing:
        return sys.executable

    for python_path in existing:
        if has_module(python_path, "pytest"):
            return python_path

    return existing[0]


def local_python_candidates(root: Path) -> list[Path]:
    venv_python = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return [
        root / ".venv" / venv_python,
        root / "venv" / venv_python,
    ]


def required_modules_for_checks(checks: Sequence[Check]) -> list[str]:
    modules = {"pytest"}
    for check in checks:
        modules.update(WORKSPACE_SYNC_SENTINELS.get(check.name, ()))
    return sorted(modules)


def ensure_workspace_environment(root: Path, python_exe: str, checks: Sequence[Check]) -> str:
    global USE_UV_ISOLATED_RUNNER

    required_modules = required_modules_for_checks(checks)
    target_python = next((candidate for candidate in local_python_candidates(root) if candidate.exists()), None)
    if target_python is not None:
        missing_modules = [module for module in required_modules if not has_module(str(target_python), module)]
    else:
        missing_modules = required_modules
    if target_python is not None and not missing_modules:
        return str(target_python)

    if all(has_module(python_exe, module) for module in required_modules):
        if target_python is None:
            print("[smoke] workspace-local Python is unavailable; using selected Python interpreter")
        else:
            print(
                "[smoke] workspace-local Python is incomplete "
                f"({', '.join(missing_modules)}); using selected Python interpreter"
            )
        return python_exe

    uv_executable = shutil.which("uv")
    if not uv_executable:
        if target_python is None:
            print("[smoke] warning: workspace-local Python is unavailable and uv is not installed")
        else:
            print(
                "[smoke] warning: missing workspace-local modules "
                f"({', '.join(missing_modules)}) and uv is not available for isolated execution"
            )
        return python_exe

    USE_UV_ISOLATED_RUNNER = True
    if target_python is None:
        print("[smoke] workspace-local Python is unavailable; using uv isolated runner for Python-based checks")
    else:
        print(
            "[smoke] workspace-local Python is incomplete "
            f"({', '.join(missing_modules)}); using uv isolated runner for Python-based checks"
        )
    return python_exe


def default_checks(python_exe: str) -> list[Check]:
    npm_exe = "npm.cmd" if os.name == "nt" else "npm"
    desci_frontend = rel_unit_path("desci-platform", "frontend")
    desci_backend = rel_unit_path("desci-platform", "backend")
    desci_contracts = rel_unit_path("desci-platform", "contracts")
    agriguard_frontend = rel_unit_path("agriguard", "frontend")
    agriguard_backend = rel_unit_path("agriguard", "backend")
    agriguard_contracts = rel_unit_path("agriguard", "contracts")
    github_mcp = rel_unit_path("github-mcp")
    notebooklm_mcp = rel_unit_path("notebooklm-mcp")
    dailynews = rel_unit_path("dailynews")
    getdaytrends = rel_unit_path("getdaytrends")
    cie = rel_unit_path("content-intelligence")

    return [
        Check(
            "workspace",
            "workspace regression tests",
            ".",
            [python_exe, "-m", "pytest", "tests/test_workspace_regressions.py", "tests/test_workspace_smoke.py", "-q"],
        ),
        Check(
            "workspace",
            "shared package tests",
            ".",
            [python_exe, "-m", "pytest", "packages/shared/tests/", "-q"],
        ),
        Check("workspace", "dashboard frontend lint", rel_unit_path("dashboard"), [npm_exe, "run", "lint"]),
        Check("workspace", "dashboard frontend tests", rel_unit_path("dashboard"), [npm_exe, "run", "test"]),
        Check("workspace", "dashboard frontend build", rel_unit_path("dashboard"), [npm_exe, "run", "build"]),
        Check("workspace", "dashboard bundle budget", rel_unit_path("dashboard"), [npm_exe, "run", "check:bundle"]),
        Check("desci", "desci frontend lint", desci_frontend, [npm_exe, "run", "lint"]),
        Check(
            "desci",
            "desci frontend unit tests",
            desci_frontend,
            [
                npm_exe,
                "run",
                "test:lts",
                "--",
                "--fileParallelism",
                "false",
            ],
        ),
        Check("desci", "desci frontend build", desci_frontend, [npm_exe, "run", "build:lts"]),
        Check("desci", "desci bundle budget", desci_frontend, [npm_exe, "run", "check:bundle"]),
        Check("desci", "desci contracts compile", desci_contracts, [npm_exe, "run", "compile"]),
        Check("desci", "desci contracts tests", desci_contracts, [npm_exe, "run", "test"]),
        Check(
            "desci",
            "desci backend smoke",
            ".",
            [python_exe, "-m", "pytest", f"{desci_backend}/tests/test_smoke_pipeline.py", "-q"],
        ),
        Check("agriguard", "agriguard frontend lint", agriguard_frontend, [npm_exe, "run", "lint"]),
        Check("agriguard", "agriguard frontend build", agriguard_frontend, [npm_exe, "run", "build:lts"]),
        Check(
            "agriguard",
            "agriguard contracts compile",
            agriguard_contracts,
            [npm_exe, "run", "compile"],
        ),
        Check("agriguard", "agriguard contracts tests", agriguard_contracts, [npm_exe, "run", "test"]),
        Check("agriguard", "agriguard backend tests", agriguard_backend, [python_exe, "-m", "pytest", "tests", "-q"]),
        Check(
            "mcp",
            "notebooklm compile",
            ".",
            compile_command(python_exe, f"{notebooklm_mcp}/scripts", f"{notebooklm_mcp}/tests"),
        ),
        Check("mcp", "github-mcp compile", ".", compile_command(python_exe, f"{github_mcp}/scripts")),
        Check("mcp", "DailyNews unit tests", dailynews, [python_exe, "-m", "pytest", "tests/unit", "-q"]),
        Check("getdaytrends", "getdaytrends compile", ".", compile_command(python_exe, getdaytrends)),
        Check(
            "getdaytrends",
            "getdaytrends tests",
            getdaytrends,
            [python_exe, "-m", "pytest", "-c", "pytest.ini", "tests", "-q"],
        ),
        Check("cie", "cie compile", ".", compile_command(python_exe, cie)),
        Check("cie", "cie tests", cie, [python_exe, "-m", "pytest", "tests", "-q"]),
    ]


def is_pytest_command(command: Sequence[str]) -> bool:
    return len(command) >= 3 and command[1] == "-m" and command[2] == "pytest"


def is_python_command(command: Sequence[str]) -> bool:
    if not command:
        return False
    return Path(command[0]).name.lower().startswith("python")


def is_npm_command(command: Sequence[str]) -> bool:
    if not command:
        return False
    return Path(command[0]).name.lower() in {"npm", "npm.cmd"}


def node_dependency_workspaces(root: Path, checks: Sequence[Check]) -> list[Path]:
    workspaces: list[Path] = []
    seen: set[str] = set()
    for check in checks:
        if not is_npm_command(check.command):
            continue
        cwd = (root / check.cwd).resolve()
        if not (cwd / "package-lock.json").exists():
            continue
        key = str(cwd).lower() if os.name == "nt" else str(cwd)
        if key in seen:
            continue
        seen.add(key)
        workspaces.append(cwd)
    return workspaces


def npm_install_environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    cache_dir = root / "var" / "tmp" / "workspace-smoke" / ".tool-cache" / "npm"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env["npm_config_cache"] = str(cache_dir)
    env["NPM_CONFIG_CACHE"] = str(cache_dir)
    return env


def ensure_node_environments(root: Path, checks: Sequence[Check]) -> None:
    npm_exe = "npm.cmd" if os.name == "nt" else "npm"
    for workspace in node_dependency_workspaces(root, checks):
        if (workspace / "node_modules").exists():
            continue
        rel_workspace = workspace.relative_to(root) if workspace.is_relative_to(root) else workspace
        print(f"[smoke] installing npm dependencies: {rel_workspace}")
        try:
            proc = run_command_with_timeout(
                [npm_exe, "ci", "--no-audit"],
                cwd=str(workspace),
                env=npm_install_environment(root),
                timeout_seconds=NPM_INSTALL_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            print(
                "[smoke] warning: npm ci timed out for "
                f"{rel_workspace}\n{tail_lines(decode_output(exc.stderr))}"
            )
            continue
        except OSError as exc:
            print(f"[smoke] warning: npm ci failed for {rel_workspace}: {exc}")
            continue
        if proc.returncode != 0:
            print(
                "[smoke] warning: npm ci returned "
                f"{proc.returncode} for {rel_workspace}\n{tail_lines(decode_output(proc.stderr))}"
            )


def editable_paths_for_check(root: Path, check: Check) -> list[str]:
    editable_units = {
        "workspace regression tests": [
            rel_unit_path("dailynews"),
            rel_unit_path("getdaytrends"),
        ],
        "agriguard backend tests": [rel_unit_path("agriguard", "backend")],
        "DailyNews unit tests": [rel_unit_path("dailynews")],
        "getdaytrends tests": [rel_unit_path("getdaytrends")],
    }
    return [str((root / path).resolve()) for path in editable_units.get(check.name, [])]


def wrap_python_command_with_uv(root: Path, check: Check, command: Sequence[str]) -> list[str]:
    wrapped = [
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--with",
        "pytest>=8.0",
        "--with",
        "pytest-asyncio>=0.23.0",
        "--with-editable",
        str(root.resolve()),
    ]
    for editable_path in editable_paths_for_check(root, check):
        wrapped.extend(["--with-editable", editable_path])
    for dependency in UV_EXTRA_DEPENDENCIES.get(check.name, ()):
        wrapped.extend(["--with", dependency])
    wrapped.extend(["python", *command[1:]])
    return wrapped


def runtime_temp_dir(root: Path, item: Check) -> Path:
    return root / "var" / "tmp" / "workspace-smoke" / item.scope / slugify_check_name(item.name)


def pytest_temp_dir(temp_dir: Path) -> Path:
    return temp_dir.parents[2] / f"pytest-{temp_dir.parent.name}-{temp_dir.name}"


def reset_temp_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def command_for_check(item: Check, temp_dir: Path) -> list[str]:
    command = list(item.command)
    if is_pytest_command(command) and "--basetemp" not in command:
        command.extend(["--basetemp", str(pytest_temp_dir(temp_dir))])
    return command


def elapsed_since(started: float) -> float:
    return round(max(time.perf_counter() - started, 0.0), 3)


def result_timing(started: float, started_wall_ns: int) -> dict[str, float | int]:
    ended_wall_ns = time.time_ns()
    return {
        "elapsed_seconds": elapsed_since(started),
        "started_at_unix_nano": started_wall_ns,
        "ended_at_unix_nano": max(ended_wall_ns, started_wall_ns),
    }


def format_timeout_seconds(timeout_seconds: float) -> str:
    value = float(timeout_seconds)
    return str(int(value)) if value.is_integer() else str(value)


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=False,
            shell=False,
            check=False,
        )
        return

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_command_with_timeout(
    command: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[bytes]:
    popen_kwargs: dict[str, object] = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env,
        "shell": False,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        terminate_process_tree(proc.pid)
        stdout, stderr = proc.communicate()
        raise subprocess.TimeoutExpired(command, timeout_seconds, output=stdout, stderr=stderr)

    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def run_one(root: Path, item: Check, *, timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS) -> Result:
    started = time.perf_counter()
    started_wall_ns = time.time_ns()
    cwd = (root / item.cwd).resolve()
    if not cwd.exists():
        return Result(
            item.scope,
            item.name,
            item.cwd,
            format_command(item.command),
            2,
            False,
            "",
            "working directory missing",
            **result_timing(started, started_wall_ns),
        )

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = build_pythonpath(root, env)
    temp_dir = runtime_temp_dir(root, item)
    reset_temp_dir(temp_dir)
    cache_root = root / "var" / "tmp" / "workspace-smoke" / ".tool-cache"
    uv_cache_dir = cache_root / "uv"
    npm_cache_dir = cache_root / "npm"
    uv_cache_dir.mkdir(parents=True, exist_ok=True)
    npm_cache_dir.mkdir(parents=True, exist_ok=True)
    env["UV_CACHE_DIR"] = str(uv_cache_dir)
    env["npm_config_cache"] = str(npm_cache_dir)
    env["NPM_CONFIG_CACHE"] = str(npm_cache_dir)
    command = command_for_check(item, temp_dir)
    if not is_pytest_command(command):
        env["TMP"] = str(temp_dir)
        env["TEMP"] = str(temp_dir)
        env["TMPDIR"] = str(temp_dir)
    if (USE_UV_ISOLATED_RUNNER or item.name in FORCE_UV_CHECKS) and is_python_command(command):
        command = wrap_python_command_with_uv(root, item, command)
    command_text = format_command(command)

    try:
        proc = run_command_with_timeout(
            command,
            cwd=str(cwd),
            env=env,
            timeout_seconds=timeout_seconds,
        )
        stdout_text = decode_output(proc.stdout)
        stderr_text = decode_output(proc.stderr)
    except subprocess.TimeoutExpired as exc:
        stdout_text = decode_output(exc.stdout)
        stderr_text = decode_output(exc.stderr)
        return Result(
            item.scope,
            item.name,
            item.cwd,
            command_text,
            124,
            False,
            tail_lines(stdout_text),
            f"Command timed out after {format_timeout_seconds(timeout_seconds)}s\n{tail_lines(stderr_text)}",
            **result_timing(started, started_wall_ns),
        )
    except OSError as exc:
        return Result(
            item.scope,
            item.name,
            item.cwd,
            command_text,
            2,
            False,
            "",
            str(exc),
            **result_timing(started, started_wall_ns),
        )

    return Result(
        scope=item.scope,
        name=item.name,
        cwd=item.cwd,
        command=command_text,
        returncode=proc.returncode,
        ok=proc.returncode == 0,
        stdout_tail=tail_lines(stdout_text),
        stderr_tail=tail_lines(stderr_text),
        **result_timing(started, started_wall_ns),
    )


def should_retry(check: Check, result: Result) -> bool:
    if result.ok:
        return False

    combined_output = "\n".join(part for part in (result.stdout_tail, result.stderr_tail) if part)
    if check.name == TRANSIENT_RETRY_CHECK and any(pattern in combined_output for pattern in TRANSIENT_RETRY_PATTERNS):
        return True

    if result.command.startswith("uv run ") and any(
        pattern in combined_output for pattern in UV_TRANSIENT_RETRY_PATTERNS
    ):
        return True

    return result.command.startswith("npm") and any(
        pattern in combined_output for pattern in NPM_TRANSIENT_RETRY_PATTERNS
    )


def run_check(root: Path, item: Check, *, timeout_seconds: float = DEFAULT_CHECK_TIMEOUT_SECONDS) -> Result:
    result = run_one(root, item, timeout_seconds=timeout_seconds)
    if not should_retry(item, result):
        return result

    attempt = 0
    while should_retry(item, result) and attempt < TRANSIENT_RETRY_MAX:
        attempt += 1
        print(f"[smoke] retrying: {item.name} (attempt {attempt}/{TRANSIENT_RETRY_MAX})")
        result = run_one(root, item, timeout_seconds=timeout_seconds)
    return result


def resolve_json_out_path(path_value: str) -> Path:
    out_path = Path(path_value)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    return out_path


def classify_command_kind(command: str) -> str:
    normalized = f" {command.lower()} "
    if " -m compileall " in normalized:
        return "compileall"
    if " -m pytest " in normalized:
        return "pytest"
    if normalized.lstrip().startswith(("npm ", "npm.cmd ")):
        return "npm"
    if normalized.lstrip().startswith("uv run "):
        return "uv"
    return "command"


def build_scope_summary(results: Sequence[Result]) -> dict[str, dict[str, object]]:
    summary: dict[str, dict[str, object]] = {}
    for result in results:
        scope = summary.setdefault(
            result.scope,
            {
                "completed": 0,
                "passed": 0,
                "failed": 0,
                "elapsed_seconds": 0.0,
            },
        )
        scope["completed"] = int(scope["completed"]) + 1
        if result.ok:
            scope["passed"] = int(scope["passed"]) + 1
        else:
            scope["failed"] = int(scope["failed"]) + 1
        scope["elapsed_seconds"] = round(float(scope["elapsed_seconds"]) + result.elapsed_seconds, 3)
    return summary


def build_mcp_trace(results: Sequence[Result]) -> dict[str, object]:
    mcp_results = [result for result in results if result.scope == "mcp"]
    command_kinds: dict[str, int] = {}
    for result in mcp_results:
        kind = classify_command_kind(result.command)
        command_kinds[kind] = command_kinds.get(kind, 0) + 1

    return {
        "enabled": bool(mcp_results),
        "completed": len(mcp_results),
        "passed": sum(1 for result in mcp_results if result.ok),
        "failed": sum(1 for result in mcp_results if not result.ok),
        "elapsed_seconds": round(sum(result.elapsed_seconds for result in mcp_results), 3),
        "checked_units": sorted({result.cwd for result in mcp_results}),
        "command_kinds": dict(sorted(command_kinds.items())),
        "checks": [
            {
                "name": result.name,
                "cwd": result.cwd,
                "ok": result.ok,
                "returncode": result.returncode,
                "elapsed_seconds": result.elapsed_seconds,
                "command_kind": classify_command_kind(result.command),
            }
            for result in mcp_results
        ],
    }


def build_mcp_trace_events(results: Sequence[Result]) -> list[dict[str, object]]:
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        {
            "schema_version": 1,
            "event_type": "workspace_smoke.mcp_check",
            "generated_at": generated_at,
            "scope": result.scope,
            "name": result.name,
            "cwd": result.cwd,
            "command": result.command,
            "command_kind": classify_command_kind(result.command),
            "returncode": result.returncode,
            "ok": result.ok,
            "elapsed_seconds": result.elapsed_seconds,
            "stdout_tail": result.stdout_tail,
            "stderr_tail": result.stderr_tail,
        }
        for result in results
        if result.scope == "mcp"
    ]


def build_mcp_trace_complete_event(results: Sequence[Result]) -> dict[str, object]:
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    trace = build_mcp_trace(results)
    return {
        "schema_version": 1,
        "event_type": "workspace_smoke.mcp_trace_complete",
        "generated_at": generated_at,
        "scope": "mcp",
        "partial": False,
        "completed": trace["completed"],
        "passed": trace["passed"],
        "failed": trace["failed"],
        "elapsed_seconds": trace["elapsed_seconds"],
        "checked_units": trace["checked_units"],
        "command_kinds": trace["command_kinds"],
    }


def make_otel_trace_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def make_otel_span_id(trace_id: str, result: Result, index: int) -> str:
    seed = f"{trace_id}|{index}|{result.scope}|{result.name}|{result.command}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def otel_value(value: object) -> dict[str, object]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def otel_attributes(values: dict[str, object]) -> list[dict[str, object]]:
    return [{"key": key, "value": otel_value(value)} for key, value in values.items() if value is not None]


def otel_span_bounds(result: Result, export_time_ns: int) -> tuple[int, int]:
    end_ns = result.ended_at_unix_nano or export_time_ns
    duration_ns = max(int(result.elapsed_seconds * 1_000_000_000), 0)
    start_ns = result.started_at_unix_nano or max(end_ns - duration_ns, 0)
    return start_ns, max(end_ns, start_ns)


def build_mcp_otel_export(results: Sequence[Result], *, trace_id: str | None = None) -> dict[str, object] | None:
    mcp_results = [result for result in results if result.scope == "mcp"]
    if not mcp_results:
        return None

    export_time_ns = time.time_ns()
    trace_id = trace_id or make_otel_trace_id(f"workspace-smoke-mcp|{export_time_ns}|{len(mcp_results)}")
    spans = []
    for index, result in enumerate(mcp_results):
        start_ns, end_ns = otel_span_bounds(result, export_time_ns)
        status: dict[str, object] = {"code": 1 if result.ok else 2}
        if not result.ok:
            status["message"] = result.stderr_tail or result.stdout_tail or f"returncode {result.returncode}"
        spans.append(
            {
                "traceId": trace_id,
                "spanId": make_otel_span_id(trace_id, result, index),
                "parentSpanId": "",
                "name": f"workspace_smoke.mcp_check {result.name}",
                "kind": 1,
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(end_ns),
                "attributes": otel_attributes(
                    {
                        "workspace_smoke.scope": result.scope,
                        "workspace_smoke.check.name": result.name,
                        "workspace_smoke.cwd": result.cwd,
                        "workspace_smoke.command": result.command,
                        "workspace_smoke.command.kind": classify_command_kind(result.command),
                        "workspace_smoke.returncode": result.returncode,
                        "workspace_smoke.ok": result.ok,
                        "workspace_smoke.elapsed_seconds": result.elapsed_seconds,
                    }
                ),
                "status": status,
            }
        )

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": otel_attributes(
                        {
                            "service.name": "workspace-smoke",
                            "service.namespace": "biojuho-projects",
                            "workspace_smoke.exporter": "run_workspace_smoke.py",
                            "workspace_smoke.signal": "mcp",
                        }
                    )
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "workspace_smoke.mcp", "version": "1"},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def build_json_report(
    results: Sequence[Result],
    *,
    total_checks: int,
    complete: bool,
    duration_seconds: float,
) -> dict[str, object]:
    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "complete" if complete else "partial",
        "duration_seconds": round(max(duration_seconds, 0.0), 3),
        "summary": {
            "total": total_checks,
            "completed": len(results),
            "passed": passed,
            "failed": failed,
            "remaining": max(total_checks - len(results), 0),
        },
        "scope_summary": build_scope_summary(results),
        "mcp_trace": build_mcp_trace(results),
        "results": [asdict(result) for result in results],
    }


def write_json_report(
    out_path: Path,
    results: Sequence[Result],
    *,
    total_checks: int,
    complete: bool,
    duration_seconds: float,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    payload = build_json_report(
        results,
        total_checks=total_checks,
        complete=complete,
        duration_seconds=duration_seconds,
    )
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(out_path)


def drain_mcp_trace_events(
    events: "Iterable[dict[str, object]]",
    *,
    event_stream_handler: "Callable[[Iterable[dict[str, object]]], object] | None" = None,
) -> list[dict[str, object]]:
    iterator = iter(events)
    drained: list[dict[str, object]] = []

    if event_stream_handler is not None:
        def observed_events() -> "Iterable[dict[str, object]]":
            for event in iterator:
                drained.append(event)
                yield event

        event_stream_handler(observed_events())

    for event in iterator:
        drained.append(event)
    return drained


def write_mcp_trace_export(
    out_path: Path,
    results: Sequence[Result],
    *,
    event_stream_handler: "Callable[[Iterable[dict[str, object]]], object] | None" = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    events = drain_mcp_trace_events(
        [*build_mcp_trace_events(results), build_mcp_trace_complete_event(results)],
        event_stream_handler=event_stream_handler,
    )
    content = "".join(f"{json.dumps(event, ensure_ascii=False)}\n" for event in events)
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(out_path)


def write_mcp_otel_export(out_path: Path, results: Sequence[Result], *, trace_id: str | None = None) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    export = build_mcp_otel_export(results, trace_id=trace_id)
    content = "" if export is None else f"{json.dumps(export, ensure_ascii=False)}\n"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic smoke checks across workspace projects.")
    # Windows stdout UTF-8 설정
    if sys.platform == "win32":
        try:
            stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
            stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
            if callable(stdout_reconfigure) and callable(stderr_reconfigure):
                stdout_reconfigure(encoding="utf-8", errors="replace")
                stderr_reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser.add_argument(
        "--scope", default="all", choices=["all", "workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie"]
    )
    parser.add_argument("--json-out", help="Optional JSON output file")
    parser.add_argument("--mcp-trace-out", help="Optional JSONL output file for MCP trace events")
    parser.add_argument("--mcp-otel-out", help="Optional OTLP JSONL output file for MCP check spans")
    parser.add_argument(
        "--check-timeout",
        type=float,
        default=DEFAULT_CHECK_TIMEOUT_SECONDS,
        help="Timeout per smoke check in seconds before terminating the process tree",
    )
    args = parser.parse_args()

    root = find_workspace_root()
    python_exe = resolve_python_executable(root)
    checks = default_checks(python_exe)
    if args.scope != "all":
        checks = [check for check in checks if check.scope == args.scope]

    if not checks:
        print("[smoke] no checks to run")
        return 1

    python_exe = ensure_workspace_environment(root, python_exe, checks)
    checks = default_checks(python_exe)
    if args.scope != "all":
        checks = [check for check in checks if check.scope == args.scope]

    ensure_node_environments(root, checks)

    print(f"[smoke] using python executable: {python_exe}")
    if not has_module(python_exe, "pytest"):
        print("[smoke] warning: pytest is not installed for selected Python; pytest-based checks may fail")

    print(
        "[smoke] excluded directories for python compile checks: .agent, .agents, venv, __pycache__, output, archive, var"
    )

    results: list[Result] = []
    run_started = time.perf_counter()
    out_path = resolve_json_out_path(args.json_out) if args.json_out else None
    mcp_trace_out_path = resolve_json_out_path(args.mcp_trace_out) if args.mcp_trace_out else None
    mcp_otel_out_path = resolve_json_out_path(args.mcp_otel_out) if args.mcp_otel_out else None
    mcp_otel_trace_id = make_otel_trace_id(f"{root}|{time.time_ns()}") if mcp_otel_out_path else None
    json_write_failed = False
    mcp_trace_write_failed = False
    mcp_otel_write_failed = False
    for check in checks:
        print(f"[smoke] running: {check.name}")
        results.append(run_check(root, check, timeout_seconds=args.check_timeout))
        if out_path and not json_write_failed:
            try:
                write_json_report(
                    out_path,
                    results,
                    total_checks=len(checks),
                    complete=len(results) == len(checks),
                    duration_seconds=elapsed_since(run_started),
                )
            except OSError as exc:
                print(f"[smoke] warning: could not write json report to {out_path}: {exc}")
                json_write_failed = True
        if mcp_trace_out_path and not mcp_trace_write_failed:
            try:
                write_mcp_trace_export(mcp_trace_out_path, results)
            except OSError as exc:
                print(f"[smoke] warning: could not write MCP trace export to {mcp_trace_out_path}: {exc}")
                mcp_trace_write_failed = True
        if mcp_otel_out_path and not mcp_otel_write_failed:
            try:
                write_mcp_otel_export(mcp_otel_out_path, results, trace_id=mcp_otel_trace_id)
            except OSError as exc:
                print(f"[smoke] warning: could not write MCP OTLP export to {mcp_otel_out_path}: {exc}")
                mcp_otel_write_failed = True

    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed
    print(f"[smoke] summary: passed={passed}, failed={failed}, total={len(results)}")

    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"- [{status}] {result.name} ({result.command})")

    if out_path and not json_write_failed:
        print(f"[smoke] json written: {out_path}")
    if mcp_trace_out_path and not mcp_trace_write_failed:
        print(f"[smoke] mcp trace written: {mcp_trace_out_path}")
    if mcp_otel_out_path and not mcp_otel_write_failed:
        print(f"[smoke] mcp otlp written: {mcp_otel_out_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
