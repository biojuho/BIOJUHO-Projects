#!/usr/bin/env python3
"""Run the DSCI-DecentBio release gate.

This is intentionally a small standard-library orchestrator. It keeps local and
CI release checks in one place while letting each project keep its own native
commands.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "biolinker"

DEFAULT_BACKEND_TESTS = (
    "tests",
)


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


@dataclass(frozen=True)
class GateStep:
    name: str
    command: tuple[str, ...]
    cwd: Path


@dataclass
class GateResult:
    name: str
    command: str
    cwd: str
    returncode: int
    elapsed_ms: float
    skipped: bool = False

    @property
    def ok(self) -> bool:
        return self.skipped or self.returncode == 0


def _python_command(value: str) -> tuple[str, ...]:
    if not value.strip():
        return (sys.executable,)
    return tuple(shlex.split(value, posix=os.name != "nt"))


def _env_command(args: argparse.Namespace, python_cmd: tuple[str, ...]) -> GateStep:
    command = [*python_cmd, "scripts/env_doctor.py", "--profile", args.profile]
    for env_file in args.env_file:
        command.extend(["--env-file", env_file])
    if args.ignore_process_env:
        command.append("--ignore-process-env")
    return GateStep("env-doctor", tuple(command), PROJECT_ROOT)


def build_steps(args: argparse.Namespace) -> list[GateStep]:
    python_cmd = _python_command(args.python_command)
    backend_tests = tuple(args.backend_tests or DEFAULT_BACKEND_TESTS)
    steps: list[GateStep] = []

    if not args.skip_env:
        steps.append(_env_command(args, python_cmd))

    if not args.skip_compose:
        steps.append(GateStep("compose-config", ("docker", "compose", "config", "--quiet"), PROJECT_ROOT))

    if not args.skip_backend:
        steps.append(GateStep("backend-tests", (*python_cmd, "-m", "pytest", *backend_tests, "-q"), BACKEND_DIR))

    if not args.skip_frontend:
        npm = _npm_command()
        steps.extend(
            [
                GateStep("frontend-lint", (npm, "run", "lint"), FRONTEND_DIR),
                GateStep("frontend-typecheck", (npm, "run", "typecheck"), FRONTEND_DIR),
                GateStep("frontend-tests", (npm, "run", "test"), FRONTEND_DIR),
                GateStep("frontend-build", (npm, "run", "build:lts"), FRONTEND_DIR),
                GateStep("frontend-bundle", (npm, "run", "check:bundle"), FRONTEND_DIR),
            ]
        )

    return steps


def _format_command(command: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def run_step(step: GateStep, *, dry_run: bool) -> GateResult:
    command_text = _format_command(step.command)
    print(f"[release-gate] START {step.name}: {command_text}", flush=True)

    if dry_run:
        return GateResult(
            name=step.name,
            command=command_text,
            cwd=str(step.cwd),
            returncode=0,
            elapsed_ms=0.0,
            skipped=True,
        )

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(step.command, cwd=step.cwd, env=env, check=False)
    except FileNotFoundError as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        print(f"[release-gate] FAIL  {step.name}: {exc}", flush=True)
        return GateResult(
            name=step.name,
            command=command_text,
            cwd=str(step.cwd),
            returncode=127,
            elapsed_ms=elapsed_ms,
        )
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    status = "PASS" if completed.returncode == 0 else "FAIL"
    print(f"[release-gate] {status}  {step.name} ({elapsed_ms:.1f}ms)", flush=True)
    return GateResult(
        name=step.name,
        command=command_text,
        cwd=str(step.cwd),
        returncode=completed.returncode,
        elapsed_ms=elapsed_ms,
    )


def write_json_report(path: Path, results: list[GateResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": all(result.ok for result in results),
        "results": [asdict(result) | {"ok": result.ok} for result in results],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DSCI-DecentBio release checks.")
    parser.add_argument("--profile", choices=("local", "production"), default="local")
    parser.add_argument("--env-file", action="append", default=[], help="Env file for env_doctor. Can be repeated.")
    parser.add_argument("--ignore-process-env", action="store_true", help="Pass through to env_doctor.")
    parser.add_argument("--python-command", default=sys.executable, help='Python runner, e.g. "uv run python".')
    parser.add_argument("--backend-tests", nargs="*", default=list(DEFAULT_BACKEND_TESTS))
    parser.add_argument("--skip-env", action="store_true")
    parser.add_argument("--skip-compose", action="store_true")
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument("--json-out", help="Write a JSON report.")
    args = parser.parse_args()

    results: list[GateResult] = []
    for step in build_steps(args):
        result = run_step(step, dry_run=args.dry_run)
        results.append(result)
        if not result.ok:
            break

    if args.json_out:
        write_json_report(Path(args.json_out), results)

    failed = [result for result in results if not result.ok]
    if failed:
        print(f"\n[release-gate] FAILED at {failed[0].name}")
        return failed[0].returncode or 1

    print(f"\n[release-gate] OK ({len(results)} step(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
