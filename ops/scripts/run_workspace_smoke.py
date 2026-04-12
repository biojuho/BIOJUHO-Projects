#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workspace_paths import find_workspace_root, rel_unit_path

EXCLUDE_REGEX = r"(^|[\\/])(\.agent|\.agents|venv|__pycache__|output|archive|var)([\\/]|$)"
TAIL_LINE_COUNT = 20
TRANSIENT_RETRY_CHECK = "desci frontend unit tests"
TRANSIENT_RETRY_PATTERNS = (
    "Failed to start threads worker",
    "Failed to start forks worker",
    "Timeout waiting for worker to respond",
)
TRANSIENT_RETRY_MAX = 2
WORKSPACE_SYNC_SENTINELS: dict[str, tuple[str, ...]] = {
    "workspace regression tests": ("fastapi", "sqlalchemy", "aiosqlite", "mcp.server.fastmcp", "pypdf"),
    "desci biolinker smoke": ("fastapi",),
    "agriguard backend tests": ("fastapi", "sqlalchemy"),
    "DailyNews unit tests": ("mcp.server.fastmcp",),
    "getdaytrends tests": ("aiosqlite",),
}
UV_EXTRA_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "workspace regression tests": ("pypdf>=4.0.0,<5.0",),
    "desci biolinker smoke": (
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
    ),
    "getdaytrends tests": ("respx>=0.21.0,<1.0",),
}
FORCE_UV_CHECKS = {
    "desci biolinker smoke",
    "agriguard backend tests",
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
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
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
    for candidate in candidates:
        if not candidate.exists():
            continue
        value = str(candidate)
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

    for candidate in existing:
        if has_module(candidate, "pytest"):
            return candidate

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
    vitest_exe = ".\\node_modules\\.bin\\vitest.cmd" if os.name == "nt" else "./node_modules/.bin/vitest"
    desci_frontend = rel_unit_path("desci-platform", "frontend")
    desci_biolinker = rel_unit_path("desci-platform", "biolinker")
    agriguard_frontend = rel_unit_path("agriguard", "frontend")
    agriguard_backend = rel_unit_path("agriguard", "backend")
    github_mcp = rel_unit_path("github-mcp")
    notebooklm_mcp = rel_unit_path("notebooklm-mcp")
    dailynews = rel_unit_path("dailynews")
    getdaytrends = rel_unit_path("getdaytrends")

    return [
        Check(
            "workspace",
            "workspace regression tests",
            ".",
            [python_exe, "-m", "pytest", "tests/test_workspace_regressions.py", "tests/test_workspace_smoke.py", "-q"],
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
                vitest_exe,
                "run",
                "--pool",
                "threads",
                "--fileParallelism",
                "false",
            ],
        ),
        Check("desci", "desci frontend build", desci_frontend, [npm_exe, "run", "build:lts"]),
        Check("desci", "desci bundle budget", desci_frontend, [npm_exe, "run", "check:bundle"]),
        Check(
            "desci",
            "desci biolinker smoke",
            ".",
            [python_exe, "-m", "pytest", f"{desci_biolinker}/tests/test_smoke_pipeline.py", "-q"],
        ),
        Check("agriguard", "agriguard frontend lint", agriguard_frontend, [npm_exe, "run", "lint"]),
        Check("agriguard", "agriguard frontend build", agriguard_frontend, [npm_exe, "run", "build:lts"]),
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
        Check("getdaytrends", "getdaytrends tests", getdaytrends, [python_exe, "-m", "pytest", "-c", "pytest.ini", "tests", "-q"]),
    ]


def is_pytest_command(command: Sequence[str]) -> bool:
    return len(command) >= 3 and command[1] == "-m" and command[2] == "pytest"


def is_python_command(command: Sequence[str]) -> bool:
    if not command:
        return False
    return Path(command[0]).name.lower().startswith("python")


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


def run_one(root: Path, item: Check) -> Result:
    cwd = (root / item.cwd).resolve()
    if not cwd.exists():
        return Result(
            item.scope, item.name, item.cwd, format_command(item.command), 2, False, "", "working directory missing"
        )

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = build_pythonpath(root, env)
    temp_dir = runtime_temp_dir(root, item)
    reset_temp_dir(temp_dir)
    command = command_for_check(item, temp_dir)
    if not is_pytest_command(command):
        env["TMP"] = str(temp_dir)
        env["TEMP"] = str(temp_dir)
        env["TMPDIR"] = str(temp_dir)
    if (USE_UV_ISOLATED_RUNNER or item.name in FORCE_UV_CHECKS) and is_python_command(command):
        command = wrap_python_command_with_uv(root, item, command)
    command_text = format_command(command)

    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=False,
            env=env,
            shell=False,
            check=False,
        )
        stdout_text = decode_output(proc.stdout)
        stderr_text = decode_output(proc.stderr)
    except OSError as exc:
        return Result(item.scope, item.name, item.cwd, command_text, 2, False, "", str(exc))

    return Result(
        scope=item.scope,
        name=item.name,
        cwd=item.cwd,
        command=command_text,
        returncode=proc.returncode,
        ok=proc.returncode == 0,
        stdout_tail=tail_lines(stdout_text),
        stderr_tail=tail_lines(stderr_text),
    )


def should_retry(check: Check, result: Result) -> bool:
    if result.ok or check.name != TRANSIENT_RETRY_CHECK:
        return False

    combined_output = "\n".join(part for part in (result.stdout_tail, result.stderr_tail) if part)
    return any(pattern in combined_output for pattern in TRANSIENT_RETRY_PATTERNS)


def run_check(root: Path, item: Check) -> Result:
    result = run_one(root, item)
    if not should_retry(item, result):
        return result

    attempt = 0
    while should_retry(item, result) and attempt < TRANSIENT_RETRY_MAX:
        attempt += 1
        print(f"[smoke] retrying: {item.name} (attempt {attempt}/{TRANSIENT_RETRY_MAX})")
        result = run_one(root, item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic smoke checks across workspace projects.")
    parser.add_argument(
        "--scope", default="all", choices=["all", "workspace", "desci", "agriguard", "mcp", "getdaytrends"]
    )
    parser.add_argument("--json-out", help="Optional JSON output file")
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

    print(f"[smoke] using python executable: {python_exe}")
    if not has_module(python_exe, "pytest"):
        print("[smoke] warning: pytest is not installed for selected Python; pytest-based checks may fail")

    print(
        "[smoke] excluded directories for python compile checks: .agent, .agents, venv, __pycache__, output, archive, var"
    )

    results: list[Result] = []
    for check in checks:
        print(f"[smoke] running: {check.name}")
        results.append(run_check(root, check))

    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed
    print(f"[smoke] summary: passed={passed}, failed={failed}, total={len(results)}")

    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"- [{status}] {result.name} ({result.command})")

    if args.json_out:
        out_path = Path(args.json_out)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"[smoke] json written: {out_path}")
        except OSError as exc:
            print(f"[smoke] warning: could not write json report to {out_path}: {exc}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
