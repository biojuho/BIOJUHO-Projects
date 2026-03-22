#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

EXCLUDE_REGEX = r"(^|[\\/])(\.agent|\.agents|venv|__pycache__|output)([\\/]|$)"
TAIL_LINE_COUNT = 20


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
        Path(sys.executable),
        root / ".venv" / venv_python,
        root / "venv" / venv_python,
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


def default_checks(python_exe: str) -> list[Check]:
    npm_exe = "npm.cmd" if os.name == "nt" else "npm"
    return [
        Check(
            "workspace",
            "workspace regression tests",
            ".",
            [
                python_exe,
                "-m",
                "pytest",
                "tests/test_workspace_regressions.py",
                "tests/test_workspace_smoke.py",
                "-q",
            ],
        ),
        Check("desci", "desci frontend lint", "desci-platform/frontend", [npm_exe, "run", "lint"]),
        Check("desci", "desci frontend unit tests", "desci-platform/frontend", [npm_exe, "run", "test"]),
        Check("desci", "desci frontend build", "desci-platform/frontend", [npm_exe, "run", "build:lts"]),
        Check("desci", "desci bundle budget", "desci-platform/frontend", [npm_exe, "run", "check:bundle"]),
        Check(
            "desci",
            "desci biolinker smoke",
            ".",
            [python_exe, "-m", "pytest", "desci-platform/biolinker/tests/test_smoke_pipeline.py", "-q"],
        ),
        Check("agriguard", "agriguard frontend lint", "AgriGuard/frontend", [npm_exe, "run", "lint"]),
        Check("agriguard", "agriguard frontend build", "AgriGuard/frontend", [npm_exe, "run", "build:lts"]),
        Check(
            "agriguard",
            "agriguard backend compile",
            ".",
            compile_command(python_exe, "AgriGuard/backend"),
        ),

        Check(
            "mcp",
            "notebooklm compile",
            ".",
            compile_command(python_exe, "notebooklm-mcp/scripts", "notebooklm-mcp/tests"),
        ),
        Check(
            "mcp",
            "github-mcp compile",
            ".",
            compile_command(python_exe, "github-mcp/scripts"),
        ),
        Check(
            "mcp",
            "DailyNews unit tests",
            "DailyNews",
            [python_exe, "-m", "pytest", "tests/unit", "-q"],
        ),
        Check(
            "mcp",
            "notebooklm-automation unit tests",
            "notebooklm-automation",
            [python_exe, "-m", "pytest", "tests", "-q"],
        ),
        Check(
            "getdaytrends",
            "getdaytrends compile",
            ".",
            compile_command(python_exe, "getdaytrends"),
        ),
        Check(
            "getdaytrends",
            "getdaytrends tests",
            "getdaytrends",
            [python_exe, "-m", "pytest", "tests", "-q"],
        ),
    ]


def run_one(root: Path, item: Check) -> Result:
    cwd = (root / item.cwd).resolve()
    command_text = format_command(item.command)
    if not cwd.exists():
        return Result(item.scope, item.name, item.cwd, command_text, 2, False, "", "working directory missing")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = subprocess.run(
            item.command,
            cwd=str(cwd),
            capture_output=True,
            text=False,
            env=env,
            shell=False,
            check=False,
        )
    except OSError as exc:
        return Result(item.scope, item.name, item.cwd, command_text, 2, False, "", str(exc))

    stdout_text = decode_output(proc.stdout)
    stderr_text = decode_output(proc.stderr)

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic smoke checks across workspace projects.")
    parser.add_argument("--scope", default="all", choices=["all", "workspace", "desci", "agriguard", "mcp", "getdaytrends"])
    parser.add_argument("--json-out", help="Optional JSON output file")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    python_exe = resolve_python_executable(root)
    checks = default_checks(python_exe)
    if args.scope != "all":
        checks = [check for check in checks if check.scope == args.scope]

    if not checks:
        print("[smoke] no checks to run")
        return 1

    print(f"[smoke] using python executable: {python_exe}")
    if not has_module(python_exe, "pytest"):
        print("[smoke] warning: pytest is not installed for selected Python; pytest-based checks may fail")

    print("[smoke] excluded directories for python compile checks: .agent, .agents, venv, __pycache__, output")

    results: list[Result] = []
    for check in checks:
        print(f"[smoke] running: {check.name}")
        results.append(run_one(root, check))

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
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[smoke] json written: {out_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
