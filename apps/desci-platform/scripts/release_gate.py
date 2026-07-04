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
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evidence_io import write_json_atomic

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"
CONTRACTS_DIR = PROJECT_ROOT / "contracts"

DEFAULT_BACKEND_TESTS = ("tests",)
TRANSIENT_RETRY_STEPS = {
    "frontend-tests",
    "frontend-build",
    "contracts-build",
    "contracts-tests",
    "contracts-deploy-core",
    "contracts-deploy-nft",
}
TRANSIENT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_BACKEND_TEST_TIMEOUT_SECONDS = 600.0
DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS = 600.0
DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS = 600.0
DEFAULT_FRONTEND_TEST_TIMEOUT_SECONDS = 600.0
DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS = 600.0
DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS = 600.0
CONTRACT_STEP_PREFIX = "contracts-"
CONTRACT_LOCALAPPDATA_DIR = PROJECT_ROOT / ".release-gate-localappdata"
AUTO_PYTHON_COMMAND = "auto"
SYSTEM_PYTHON_COMMAND = "system"
SECRET_SHAPED_PATTERNS = (
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]+"),
    re.compile(r"\brk_(?:live|test)_[A-Za-z0-9]+"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]+"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b0x[0-9a-fA-F]{40}\b"),
    re.compile(r"https?://\S+"),
)
RELEASE_APPROVAL_HANDOFF_REQUIRED_SECTIONS = (
    "## Decision",
    "## Unresolved Areas",
    "## Next Operator Actions",
    "## Failure Summary",
)
RELEASE_APPROVAL_HANDOFF_UNSAFE_PATTERNS = (
    re.compile(r"postgres(?:ql)?://", re.IGNORECASE),
    re.compile(r"mcp[.]notion[.]com/authorize", re.IGNORECASE),
    re.compile(r"\bbearer\s+\S+", re.IGNORECASE),
    re.compile(r"\bsb(?:p|_secret)_[A-Za-z0-9_=-]+", re.IGNORECASE),
)
READY_LAUNCH_COVERAGE_ARRAY_FIELDS = (
    "ready_action_ids",
    "launch_action_ids",
    "shared_action_ids",
    "ready_only_action_ids",
    "launch_only_action_ids",
    "ready_required_env",
    "launch_required_env",
    "shared_required_env",
    "ready_only_required_env",
    "launch_only_required_env",
)
LAUNCH_ENV_HANDOFF_ARRAY_FIELDS = (
    "required_action_ids",
    "optional_action_ids",
    "required_env",
    "optional_env",
    "operator_copy_lines",
)


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _node_command() -> str:
    return "node.exe" if os.name == "nt" else "node"


@dataclass(frozen=True)
class GateStep:
    name: str
    command: tuple[str, ...]
    cwd: Path
    timeout_seconds: float | None = None


@dataclass
class GateResult:
    name: str
    command: str
    cwd: str
    returncode: int
    elapsed_ms: float
    command_argv: list[str] | None = None
    timeout_seconds: float | None = None
    skipped: bool = False
    attempts: int = 1
    artifacts: list[str] | None = None
    artifact_failures: list[str] | None = None
    failures: list[str] | None = None

    @property
    def ok(self) -> bool:
        return self.skipped or self.returncode == 0


def _python_command(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if not stripped:
        return (sys.executable,)
    normalized = stripped.lower()
    if normalized == AUTO_PYTHON_COMMAND:
        return _project_python_command()
    if normalized == SYSTEM_PYTHON_COMMAND:
        return (sys.executable,)
    expanded = Path(stripped).expanduser()
    if expanded.exists():
        return (str(expanded),)
    return tuple(shlex.split(stripped, posix=os.name != "nt"))


def _python_command_report(value: str) -> dict[str, Any]:
    resolved = _python_command(value)
    return {
        "requested": value,
        "strategy": _python_command_strategy(value, resolved),
        "resolved": list(resolved),
        "resolved_display": _format_command(resolved),
    }


def _python_command_strategy(value: str, resolved: tuple[str, ...]) -> str:
    stripped = value.strip()
    if not stripped:
        return "current_executable"
    normalized = stripped.lower()
    if normalized == AUTO_PYTHON_COMMAND:
        return "auto_uv_project" if resolved == ("uv", "run", "python") else "auto_current_executable"
    if normalized == SYSTEM_PYTHON_COMMAND:
        return "system"
    expanded = Path(stripped).expanduser()
    if expanded.exists():
        return "path"
    return "command"


def _project_python_command() -> tuple[str, ...]:
    if shutil.which("uv") is not None and _has_uv_project_context():
        return ("uv", "run", "python")
    return (sys.executable,)


def _has_uv_project_context() -> bool:
    for directory in (PROJECT_ROOT, *PROJECT_ROOT.parents):
        if (directory / "pyproject.toml").exists() or (directory / "uv.lock").exists():
            return True
    return (BACKEND_DIR / "pyproject.toml").exists()


def _env_file_args(args: argparse.Namespace) -> list[str]:
    return [str(Path(env_file).expanduser().resolve()) for env_file in args.env_file]


def _env_command(args: argparse.Namespace, python_cmd: tuple[str, ...]) -> GateStep:
    evidence_dir = _env_evidence_dir(args)
    command = [*python_cmd, "scripts/env_doctor.py", "--profile", args.profile]
    for env_file in _env_file_args(args):
        command.extend(["--env-file", env_file])
    if args.ignore_process_env:
        command.append("--ignore-process-env")
    command.extend(["--json-out", str(evidence_dir / "desci-env-doctor-release-gate.json")])
    return GateStep("env-doctor", tuple(command), PROJECT_ROOT, timeout_seconds=args.preflight_step_timeout)


def _deploy_readiness_command(args: argparse.Namespace, python_cmd: tuple[str, ...]) -> GateStep:
    targets = args.external_target or ["all"]
    evidence_dir = _external_evidence_dir(args)
    command = [*python_cmd, "scripts/deploy_readiness.py"]
    for target in targets:
        command.extend(["--target", target])
    for env_file in _env_file_args(args):
        command.extend(["--env-file", env_file])
    if args.ignore_process_env:
        command.append("--ignore-process-env")
    command.extend(["--json-out", str(evidence_dir / "desci-deploy-readiness-release-gate.json")])
    return GateStep("deploy-readiness", tuple(command), PROJECT_ROOT, timeout_seconds=args.preflight_step_timeout)


def _external_evidence_dir(args: argparse.Namespace) -> Path:
    output_dir = Path(args.external_evidence_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    return output_dir.resolve()


def _env_evidence_dir(args: argparse.Namespace) -> Path:
    output_dir = Path(args.env_evidence_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    return output_dir.resolve()


def _runtime_evidence_dir(args: argparse.Namespace) -> Path:
    output_dir = Path(args.runtime_evidence_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    return output_dir.resolve()


def _runtime_smoke_steps(args: argparse.Namespace, python_cmd: tuple[str, ...]) -> list[GateStep]:
    evidence_dir = _runtime_evidence_dir(args)
    product_command = [
        *python_cmd,
        "scripts/product_smoke.py",
        "--api",
        args.runtime_api,
        "--frontend",
        args.runtime_frontend,
        "--json-out",
        str(evidence_dir / "desci-product-smoke-release-gate.json"),
    ]
    if args.runtime_smoke_strict_ready:
        product_command.append("--strict-ready")
    browser_command = [
        *python_cmd,
        "scripts/browser_smoke.py",
        "--frontend",
        args.runtime_frontend,
        "--json-out",
        str(evidence_dir / "desci-browser-smoke-release-gate.json"),
    ]
    if args.runtime_browser_expect_dev_auth:
        browser_command.append("--expect-dev-auth")
    if args.runtime_browser_trace_on_failure_dir:
        browser_command.extend(["--trace-on-failure-dir", args.runtime_browser_trace_on_failure_dir])
    if args.runtime_browser_screenshot_dir:
        browser_command.extend(["--screenshot-dir", args.runtime_browser_screenshot_dir])
    for check_name in args.runtime_browser_only_check:
        browser_command.extend(["--only-check", check_name])
    if args.runtime_browser_timeout is not None:
        browser_command.extend(["--timeout", str(args.runtime_browser_timeout)])

    selected_steps = set(args.runtime_smoke_step or ("product", "browser"))
    steps: list[GateStep] = []
    if "product" in selected_steps:
        steps.append(GateStep("product-smoke", tuple(product_command), PROJECT_ROOT, timeout_seconds=args.runtime_smoke_timeout))
    if "browser" in selected_steps:
        steps.append(GateStep("browser-smoke", tuple(browser_command), PROJECT_ROOT, timeout_seconds=args.runtime_smoke_timeout))
    return steps


def build_steps(args: argparse.Namespace) -> list[GateStep]:
    python_cmd = _python_command(args.python_command)
    backend_tests = tuple(args.backend_tests or DEFAULT_BACKEND_TESTS)
    steps: list[GateStep] = []

    if not args.skip_env:
        steps.append(_env_command(args, python_cmd))

    if args.external_readiness:
        steps.append(_deploy_readiness_command(args, python_cmd))

    if not args.skip_compose:
        steps.append(
            GateStep(
                "compose-config",
                ("docker", "compose", "config", "--quiet"),
                PROJECT_ROOT,
                timeout_seconds=args.preflight_step_timeout,
            )
        )

    if not args.skip_backend:
        steps.append(
            GateStep(
                "backend-tests",
                (*python_cmd, "-m", "pytest", *backend_tests, "-q"),
                BACKEND_DIR,
                timeout_seconds=args.backend_test_timeout,
            )
        )

    if not args.skip_frontend:
        npm = _npm_command()
        node = _node_command()
        steps.extend(
            [
                GateStep(
                    "frontend-lint",
                    (npm, "run", "lint"),
                    FRONTEND_DIR,
                    timeout_seconds=args.frontend_step_timeout,
                ),
                GateStep(
                    "frontend-typecheck",
                    (npm, "run", "typecheck"),
                    FRONTEND_DIR,
                    timeout_seconds=args.frontend_step_timeout,
                ),
                GateStep(
                    "frontend-tests",
                    (
                        node,
                        "scripts/run-vitest-split.mjs",
                    ),
                    FRONTEND_DIR,
                    timeout_seconds=args.frontend_test_timeout,
                ),
                GateStep(
                    "frontend-build",
                    (node, "node_modules/vite/bin/vite.js", "build", "--configLoader", "native"),
                    FRONTEND_DIR,
                    timeout_seconds=args.frontend_step_timeout,
                ),
                GateStep(
                    "frontend-bundle",
                    (npm, "run", "check:bundle"),
                    FRONTEND_DIR,
                    timeout_seconds=args.frontend_step_timeout,
                ),
            ]
        )

    if not args.skip_contracts:
        node = _node_command()
        steps.extend(
            [
                GateStep(
                    "contracts-build",
                    (node, "node_modules/hardhat/dist/src/cli.js", "--build-profile", "default", "build"),
                    CONTRACTS_DIR,
                    timeout_seconds=args.contract_step_timeout,
                ),
                GateStep(
                    "contracts-config-tests",
                    (node, "--test", "tests/runtime-config.test.js"),
                    CONTRACTS_DIR,
                    timeout_seconds=args.contract_step_timeout,
                ),
                GateStep(
                    "contracts-tests",
                    (node, "node_modules/hardhat/dist/src/cli.js", "test"),
                    CONTRACTS_DIR,
                    timeout_seconds=args.contract_step_timeout,
                ),
                GateStep(
                    "contracts-deploy-core",
                    (
                        node,
                        "node_modules/hardhat/dist/src/cli.js",
                        "--build-profile",
                        "default",
                        "run",
                        "scripts/deploy.js",
                    ),
                    CONTRACTS_DIR,
                    timeout_seconds=args.contract_step_timeout,
                ),
                GateStep(
                    "contracts-deploy-nft",
                    (
                        node,
                        "node_modules/hardhat/dist/src/cli.js",
                        "--build-profile",
                        "default",
                        "run",
                        "scripts/deploy_nft.js",
                    ),
                    CONTRACTS_DIR,
                    timeout_seconds=args.contract_step_timeout,
                ),
            ]
        )

    if args.runtime_smoke:
        steps.extend(_runtime_smoke_steps(args, python_cmd))

    return steps


def _format_command(command: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _run_subprocess(step: GateStep, env: dict[str, str]) -> int:
    try:
        completed = subprocess.run(step.command, cwd=step.cwd, env=env, check=False, timeout=step.timeout_seconds)
    except FileNotFoundError:
        raise
    return completed.returncode


def _step_env(step: GateStep) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if step.name.startswith(CONTRACT_STEP_PREFIX):
        cache_root = str(CONTRACT_LOCALAPPDATA_DIR)
        if os.name == "nt":
            env["LOCALAPPDATA"] = cache_root
        else:
            env["XDG_CACHE_HOME"] = str(CONTRACT_LOCALAPPDATA_DIR / "cache")
    if step.name == "frontend-tests" and step.timeout_seconds is not None:
        env.setdefault("DESCI_VITEST_TIMEOUT_MS", str(max(1, int(step.timeout_seconds * 1000 * 0.9))))
    return env


def _seed_contract_cache(env: dict[str, str]) -> None:
    if os.name != "nt":
        return

    source_root = os.environ.get("LOCALAPPDATA")
    if source_root is None:
        return

    source = Path(source_root) / "hardhat-nodejs" / "Cache"
    destination = Path(env["LOCALAPPDATA"]) / "hardhat-nodejs" / "Cache"
    if not source.exists() or source == destination:
        return

    destination.mkdir(parents=True, exist_ok=True)
    for cache_dir in ("compilers-v2", "compilers-v3"):
        source_dir = source / cache_dir
        if source_dir.exists():
            shutil.copytree(source_dir, destination / cache_dir, dirs_exist_ok=True)


def _max_attempts(step: GateStep) -> int:
    return 2 if step.name in TRANSIENT_RETRY_STEPS else 1


def run_step(step: GateStep, *, dry_run: bool) -> GateResult:
    command_text = _format_command(step.command)
    artifacts = _step_artifacts(step)
    print(f"[release-gate] START {step.name}: {command_text}", flush=True)

    if dry_run:
        return GateResult(
            name=step.name,
            command=command_text,
            cwd=str(step.cwd),
            returncode=0,
            elapsed_ms=0.0,
            command_argv=list(step.command),
            timeout_seconds=step.timeout_seconds,
            skipped=True,
            artifacts=artifacts,
        )

    env = _step_env(step)
    if step.name.startswith(CONTRACT_STEP_PREFIX):
        _seed_contract_cache(env)
    started_at = time.perf_counter()
    attempts = 0
    returncode = 1
    try:
        for attempt in range(1, _max_attempts(step) + 1):
            attempts = attempt
            returncode = _run_subprocess(step, env)
            if returncode == 0 or attempt >= _max_attempts(step):
                break
            print(
                f"[release-gate] RETRY {step.name}: returncode={returncode}; "
                f"waiting {TRANSIENT_RETRY_DELAY_SECONDS:.0f}s",
                flush=True,
            )
            time.sleep(TRANSIENT_RETRY_DELAY_SECONDS)
    except FileNotFoundError as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        print(f"[release-gate] FAIL  {step.name}: {exc}", flush=True)
        return GateResult(
            name=step.name,
            command=command_text,
            cwd=str(step.cwd),
            returncode=127,
            elapsed_ms=elapsed_ms,
            command_argv=list(step.command),
            timeout_seconds=step.timeout_seconds,
            attempts=attempts or 1,
            artifacts=artifacts,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        timeout_seconds = float(exc.timeout or step.timeout_seconds or 0)
        failure = f"timed out after {timeout_seconds:.1f}s"
        print(f"[release-gate] TIMEOUT {step.name}: {failure}", flush=True)
        return GateResult(
            name=step.name,
            command=command_text,
            cwd=str(step.cwd),
            returncode=124,
            elapsed_ms=elapsed_ms,
            command_argv=list(step.command),
            timeout_seconds=step.timeout_seconds,
            attempts=attempts or 1,
            artifacts=artifacts,
            failures=[failure],
        )
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    artifact_failures = artifact_validation_failures(artifacts, step.cwd, step.name) if returncode == 0 else None
    if artifact_failures:
        returncode = 1
        for failure in artifact_failures:
            print(f"[release-gate] ARTIFACT {step.name}: {failure}", flush=True)

    status = "PASS" if returncode == 0 else "FAIL"
    attempt_text = f", attempts={attempts}" if attempts > 1 else ""
    print(f"[release-gate] {status}  {step.name} ({elapsed_ms:.1f}ms{attempt_text})", flush=True)
    return GateResult(
        name=step.name,
        command=command_text,
        cwd=str(step.cwd),
        returncode=returncode,
        elapsed_ms=elapsed_ms,
        command_argv=list(step.command),
        timeout_seconds=step.timeout_seconds,
        attempts=attempts,
        artifacts=artifacts,
        artifact_failures=artifact_failures,
    )


def _step_artifacts(step: GateStep) -> list[str] | None:
    artifacts: list[str] = []
    command = list(step.command)
    for index, part in enumerate(command):
        if part == "--json-out" and index + 1 < len(command):
            artifacts.append(command[index + 1])
    return artifacts or None


def _artifact_path(raw_path: str, cwd: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(cwd) / path


def artifact_validation_failures(paths: list[str] | None, cwd: Path, step_name: str | None = None) -> list[str] | None:
    if not paths:
        return None
    failures: list[str] = []
    for raw_path in paths:
        path = _artifact_path(raw_path, cwd)
        if not path.exists():
            failures.append(f"missing expected JSON evidence artifact: {raw_path}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"invalid JSON evidence artifact: {raw_path} ({exc})")
            continue
        if not isinstance(payload, dict):
            failures.append(f"invalid JSON evidence artifact: {raw_path} (top-level JSON must be an object)")
            continue
        if payload.get("ok") is not True:
            failures.append(f"JSON evidence artifact must report ok=true: {raw_path}")
        failures.extend(_artifact_schema_failures(raw_path, payload, step_name, cwd))
    return failures or None


def _artifact_schema_failures(
    raw_path: str,
    payload: dict[str, Any],
    step_name: str | None,
    cwd: str | Path,
) -> list[str]:
    if step_name not in {"product-smoke", "browser-smoke", "deploy-readiness", "env-doctor"}:
        return []

    failures: list[str] = []
    if payload.get("schema_version") != 1:
        failures.append(f"JSON evidence artifact schema_version must be 1: {raw_path}")
    if not _is_parseable_datetime(payload.get("generated_at")):
        failures.append(f"JSON evidence artifact generated_at must be an ISO-8601 timestamp: {raw_path}")
    if step_name == "deploy-readiness":
        failures.extend(_deploy_readiness_schema_failures(raw_path, payload))
        return failures
    if step_name == "env-doctor":
        failures.extend(_env_doctor_schema_failures(raw_path, payload))
        return failures
    if step_name == "product-smoke":
        for field in ("api", "frontend"):
            if not isinstance(payload.get(field), str) or not payload.get(field):
                failures.append(f"JSON evidence artifact missing {field} target URL: {raw_path}")
        failures.extend(_product_smoke_launch_handoff_failures(raw_path, payload))
        if "launch_env_handoff" in payload:
            failures.extend(_product_smoke_launch_env_handoff_failures(raw_path, payload))
        if "ready_web3" in payload:
            failures.extend(_product_smoke_ready_web3_failures(raw_path, payload))
        if "ready_launch_action_coverage" in payload:
            failures.extend(_product_smoke_ready_launch_action_coverage_failures(raw_path, payload))
    if step_name == "browser-smoke":
        if not isinstance(payload.get("frontend"), str) or not payload.get("frontend"):
            failures.append(f"JSON evidence artifact missing frontend target URL: {raw_path}")
        failures.extend(_browser_smoke_launch_control_failures(raw_path, payload))
        failures.extend(_browser_smoke_trace_artifact_failures(raw_path, payload, cwd))
        failures.extend(_browser_smoke_screenshot_artifact_failures(raw_path, payload, cwd))

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        failures.append(f"JSON evidence artifact missing summary object: {raw_path}")
    elif not all(isinstance(summary.get(key), int) for key in ("total", "passed", "failed")):
        failures.append(f"JSON evidence artifact summary counts must be integers: {raw_path}")

    evidence_failures = payload.get("failures")
    if not isinstance(evidence_failures, list):
        failures.append(f"JSON evidence artifact failures must be a list: {raw_path}")

    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        failures.append(f"JSON evidence artifact checks must be a non-empty list: {raw_path}")
        return failures

    if isinstance(summary, dict) and isinstance(evidence_failures, list):
        failures.extend(_artifact_summary_consistency_failures(raw_path, summary, checks, evidence_failures))

    invalid_ok_checks = [
        index
        for index, check in enumerate(checks)
        if not isinstance(check, dict) or not isinstance(check.get("name"), str) or check.get("ok") is not True
    ]
    if invalid_ok_checks:
        failures.append(f"JSON evidence artifact checks must all report ok=true: {raw_path}")
    invalid_failure_lists = [
        index
        for index, check in enumerate(checks)
        if not isinstance(check, dict)
        or not isinstance(check.get("failures"), list)
        or not all(isinstance(failure, str) for failure in check.get("failures", []))
    ]
    if invalid_failure_lists:
        failures.append(f"JSON evidence artifact checks must include failures lists: {raw_path}")
    return failures


def _deploy_readiness_schema_failures(raw_path: str, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not isinstance(payload.get("targets"), list) or not payload.get("targets"):
        failures.append(f"JSON evidence artifact targets must be a non-empty list: {raw_path}")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        failures.append(f"JSON evidence artifact missing summary object: {raw_path}")
    elif not all(isinstance(summary.get(key), int) for key in ("total", "passed", "failed", "warnings")):
        failures.append(f"JSON evidence artifact summary counts must be integers: {raw_path}")
    sources = payload.get("sources")
    failures.extend(_preflight_sources_failures(raw_path, sources))
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        failures.append(f"JSON evidence artifact checks must be a non-empty list: {raw_path}")
    elif preflight_check_failures := _preflight_check_shape_failures(raw_path, checks):
        failures.extend(preflight_check_failures)
    elif isinstance(summary, dict):
        failures.extend(_preflight_summary_consistency_failures(raw_path, summary, checks))
    return failures


def _env_doctor_schema_failures(raw_path: str, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not isinstance(payload.get("profile"), str) or not payload.get("profile"):
        failures.append(f"JSON evidence artifact profile must be a non-empty string: {raw_path}")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        failures.append(f"JSON evidence artifact missing summary object: {raw_path}")
    elif not all(isinstance(summary.get(key), int) for key in ("total", "passed", "failed", "warnings")):
        failures.append(f"JSON evidence artifact summary counts must be integers: {raw_path}")
    sources = payload.get("sources")
    failures.extend(_preflight_sources_failures(raw_path, sources))
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        failures.append(f"JSON evidence artifact checks must be a non-empty list: {raw_path}")
    elif preflight_check_failures := _preflight_check_shape_failures(raw_path, checks):
        failures.extend(preflight_check_failures)
    elif isinstance(summary, dict):
        failures.extend(_preflight_summary_consistency_failures(raw_path, summary, checks))
    return failures


def _is_parseable_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _artifact_summary_consistency_failures(
    raw_path: str,
    summary: dict[str, Any],
    checks: list[Any],
    evidence_failures: list[Any],
) -> list[str]:
    if not all(isinstance(summary.get(key), int) for key in ("total", "passed", "failed")):
        return []

    passed_count = sum(1 for check in checks if isinstance(check, dict) and check.get("ok") is True)
    failed_count = sum(1 for check in checks if isinstance(check, dict) and check.get("ok") is False)
    expected = {
        "total": len(checks),
        "passed": passed_count,
        "failed": failed_count,
    }
    actual = {key: summary.get(key) for key in expected}
    if actual == expected:
        return []
    return [f"JSON evidence artifact summary does not match checks/failures: {raw_path}"]


def _product_smoke_launch_handoff_failures(raw_path: str, payload: dict[str, Any]) -> list[str]:
    if "launch_handoff" not in payload:
        return [f"JSON evidence artifact missing launch_handoff object: {raw_path}"]

    launch_handoff = payload.get("launch_handoff")
    if not isinstance(launch_handoff, dict):
        return [f"JSON evidence artifact launch_handoff must be an object: {raw_path}"]

    failures: list[str] = []
    if not isinstance(launch_handoff.get("ok"), bool):
        failures.append(f"JSON evidence artifact launch_handoff.ok must be a boolean: {raw_path}")

    decision = launch_handoff.get("release_decision")
    phase = launch_handoff.get("operator_phase")
    readiness_status = launch_handoff.get("readiness_status")
    if decision not in {"go", "go-with-watch", "no-go"}:
        failures.append(f"JSON evidence artifact launch_handoff.release_decision is invalid: {raw_path}")
    if phase not in {"launch-ready", "operator-review", "blocked"}:
        failures.append(f"JSON evidence artifact launch_handoff.operator_phase is invalid: {raw_path}")
    if readiness_status not in {"ready", "degraded", "blocked"}:
        failures.append(f"JSON evidence artifact launch_handoff.readiness_status is invalid: {raw_path}")

    summary = launch_handoff.get("summary")
    summary_counts: dict[str, int] = {}
    if not isinstance(summary, dict):
        failures.append(f"JSON evidence artifact launch_handoff.summary must be an object: {raw_path}")
    else:
        for field in ("total", "ready_count", "required_total", "required_ready_count", "blocker_count", "warning_count"):
            value = summary.get(field)
            if not _is_non_negative_int(value):
                failures.append(
                    f"JSON evidence artifact launch_handoff.summary.{field} must be a non-negative integer: {raw_path}"
                )
            else:
                summary_counts[field] = value
        total = summary_counts.get("total")
        ready_count = summary_counts.get("ready_count")
        required_total = summary_counts.get("required_total")
        required_ready_count = summary_counts.get("required_ready_count")
        if total == 0:
            failures.append(f"JSON evidence artifact launch_handoff.summary.total must be greater than zero: {raw_path}")
        if ready_count is not None and total is not None and ready_count > total:
            failures.append(
                f"JSON evidence artifact launch_handoff.summary.ready_count cannot exceed total: {raw_path}"
            )
        if required_ready_count is not None and required_total is not None and required_ready_count > required_total:
            failures.append(
                f"JSON evidence artifact launch_handoff.summary.required_ready_count cannot exceed required_total: {raw_path}"
            )

    score = launch_handoff.get("score")
    if not isinstance(score, dict):
        failures.append(f"JSON evidence artifact launch_handoff.score must be an object: {raw_path}")
    else:
        for field in ("overall_percent", "required_percent"):
            value = score.get(field)
            if not _is_percentage_int(value):
                failures.append(
                    f"JSON evidence artifact launch_handoff.score.{field} must be an integer from 0 to 100: {raw_path}"
                )

    launch_blockers = launch_handoff.get("launch_blockers")
    if not isinstance(launch_blockers, list) or not all(isinstance(blocker, str) for blocker in launch_blockers):
        failures.append(f"JSON evidence artifact launch_handoff.launch_blockers must be a list of strings: {raw_path}")
        launch_blockers = None

    next_actions = launch_handoff.get("next_actions")
    if not isinstance(next_actions, list):
        failures.append(f"JSON evidence artifact launch_handoff.next_actions must be a list: {raw_path}")
        next_actions = None
    else:
        failures.extend(_launch_handoff_next_action_failures(raw_path, next_actions))

    handoff_failures = launch_handoff.get("failures")
    if not isinstance(handoff_failures, list) or not all(isinstance(failure, str) for failure in handoff_failures):
        failures.append(f"JSON evidence artifact launch_handoff.failures must be a list of strings: {raw_path}")

    if isinstance(launch_blockers, list):
        blocker_count = summary_counts.get("blocker_count")
        if blocker_count is not None and blocker_count != len(launch_blockers):
            failures.append(
                f"JSON evidence artifact launch_handoff.summary.blocker_count must match launch_blockers length: {raw_path}"
            )
    if isinstance(next_actions, list):
        blocker_count = summary_counts.get("blocker_count")
        warning_count = summary_counts.get("warning_count")
        if blocker_count is not None and warning_count is not None and len(next_actions) != blocker_count + warning_count:
            failures.append(
                f"JSON evidence artifact launch_handoff.next_actions length must match blocker_count plus warning_count: {raw_path}"
            )

    failures.extend(_product_smoke_launch_decision_failures(raw_path, decision, phase, readiness_status, summary_counts))
    return failures


def _launch_handoff_next_action_failures(raw_path: str, next_actions: list[Any]) -> list[str]:
    failures: list[str] = []
    for index, action in enumerate(next_actions):
        prefix = f"JSON evidence artifact launch_handoff.next_actions[{index}]"
        if not isinstance(action, dict):
            failures.append(f"{prefix} must be an object: {raw_path}")
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            failures.append(f"{prefix}.id must be a non-empty string: {raw_path}")
        required = action.get("required")
        if not isinstance(required, bool):
            failures.append(f"{prefix}.required must be a boolean: {raw_path}")
        status = action.get("status")
        if status not in {"fail", "warn"}:
            failures.append(f"{prefix}.status must be fail or warn: {raw_path}")
        remediation = action.get("remediation")
        if not isinstance(remediation, str) or not remediation.strip():
            failures.append(f"{prefix}.remediation must be a non-empty string: {raw_path}")
        elif _contains_secret_shaped_value(remediation):
            failures.append(
                f"{prefix}.remediation must not contain raw URLs, addresses, or secret-shaped values: {raw_path}"
            )
        required_env = action.get("required_env")
        if not isinstance(required_env, list) or not all(isinstance(item, str) and item.strip() for item in required_env):
            failures.append(f"{prefix}.required_env must be a list of non-empty strings: {raw_path}")
        elif any(_contains_secret_shaped_value(item) for item in required_env):
            failures.append(
                f"{prefix}.required_env must not contain raw URLs, addresses, or secret-shaped values: {raw_path}"
            )
    return failures


def _product_smoke_launch_env_handoff_failures(raw_path: str, payload: dict[str, Any]) -> list[str]:
    handoff = payload.get("launch_env_handoff")
    if not isinstance(handoff, dict):
        return [f"JSON evidence artifact launch_env_handoff must be an object: {raw_path}"]

    return _launch_env_handoff_failures(raw_path, handoff, "launch_env_handoff")


def _launch_env_handoff_failures(raw_path: str, handoff: dict[str, Any], field_path: str) -> list[str]:
    failures: list[str] = []
    if handoff.get("schema_version") != 1:
        failures.append(f"JSON evidence artifact {field_path}.schema_version must be 1: {raw_path}")

    status = handoff.get("status")
    if status not in {"blocked", "watch", "clear"}:
        failures.append(f"JSON evidence artifact {field_path}.status is invalid: {raw_path}")
    if handoff.get("secret_policy") != "placeholder_only_no_secret_values":
        failures.append(
            f"JSON evidence artifact {field_path}.secret_policy must be placeholder_only_no_secret_values: {raw_path}"
        )

    string_lists: dict[str, list[str]] = {}
    for field in LAUNCH_ENV_HANDOFF_ARRAY_FIELDS:
        values = handoff.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            failures.append(f"JSON evidence artifact {field_path}.{field} must be a list of strings: {raw_path}")
        else:
            string_lists[field] = values

    required_env = string_lists.get("required_env", [])
    optional_env = string_lists.get("optional_env", [])
    operator_copy_lines = string_lists.get("operator_copy_lines", [])
    all_env = [*required_env, *optional_env]

    if any(_contains_secret_shaped_value(value) or not _looks_like_env_key(value) for value in all_env):
        failures.append(
            f"JSON evidence artifact {field_path} env keys must be placeholder key names only: {raw_path}"
        )
    if set(required_env).intersection(optional_env):
        failures.append(f"JSON evidence artifact {field_path} required_env and optional_env must not overlap: {raw_path}")
    if isinstance(status, str):
        expected_status = "blocked" if required_env else "watch" if optional_env else "clear"
        if status != expected_status:
            failures.append(f"JSON evidence artifact {field_path}.status must match env blockers: {raw_path}")

    if operator_copy_lines:
        failures.extend(_launch_env_operator_copy_line_failures(raw_path, operator_copy_lines, all_env, field_path))
    elif "operator_copy_lines" in string_lists:
        failures.append(f"JSON evidence artifact {field_path}.operator_copy_lines must not be empty: {raw_path}")
    return failures


def _launch_env_operator_copy_line_failures(
    raw_path: str,
    lines: list[str],
    env_keys: list[str],
    field_path: str = "launch_env_handoff",
) -> list[str]:
    failures: list[str] = []
    env_key_set = set(env_keys)
    for line in lines:
        if _contains_secret_shaped_value(line):
            failures.append(
                f"JSON evidence artifact {field_path}.operator_copy_lines must not contain raw URLs, "
                f"addresses, or secret-shaped values: {raw_path}"
            )
            break
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key not in env_key_set or value != "<set-secure-value>":
            failures.append(
                f"JSON evidence artifact {field_path}.operator_copy_lines must use placeholder assignments only: {raw_path}"
            )
            break
    for env_key in env_keys:
        if f"{env_key}=<set-secure-value>" not in lines:
            failures.append(
                f"JSON evidence artifact {field_path}.operator_copy_lines missing placeholder for {env_key}: {raw_path}"
            )
    return failures


def _looks_like_env_key(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]*", value))


def _contains_secret_shaped_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_SHAPED_PATTERNS)


def _product_smoke_ready_web3_failures(raw_path: str, payload: dict[str, Any]) -> list[str]:
    ready_web3 = payload.get("ready_web3")
    if not isinstance(ready_web3, dict):
        return [f"JSON evidence artifact ready_web3 must be an object: {raw_path}"]

    failures: list[str] = []
    if not isinstance(ready_web3.get("ok"), bool):
        failures.append(f"JSON evidence artifact ready_web3.ok must be a boolean: {raw_path}")
    if ready_web3.get("status") not in {"pass", "warn", "fail"}:
        failures.append(f"JSON evidence artifact ready_web3.status is invalid: {raw_path}")
    for field in ("required", "configured", "available"):
        if not isinstance(ready_web3.get(field), bool):
            failures.append(f"JSON evidence artifact ready_web3.{field} must be a boolean: {raw_path}")

    details = ready_web3.get("details")
    if not isinstance(details, dict):
        failures.append(f"JSON evidence artifact ready_web3.details must be an object: {raw_path}")
        return failures
    for field in ("rpc_configured", "rpc_public_https", "mock_mode_enabled", "mock_mode_allowed"):
        if not isinstance(details.get(field), bool):
            failures.append(f"JSON evidence artifact ready_web3.details.{field} must be a boolean: {raw_path}")
    contract_count = details.get("contract_count")
    if not isinstance(contract_count, int) or contract_count < 0:
        failures.append(f"JSON evidence artifact ready_web3.details.contract_count must be a non-negative integer: {raw_path}")
    contracts = details.get("contracts")
    if not isinstance(contracts, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in contracts.items()
    ):
        failures.append(f"JSON evidence artifact ready_web3.details.contracts must map env keys to booleans: {raw_path}")
    ready_failures = ready_web3.get("failures")
    if not isinstance(ready_failures, list) or not all(isinstance(failure, str) for failure in ready_failures):
        failures.append(f"JSON evidence artifact ready_web3.failures must be a list of strings: {raw_path}")
    return failures


def _product_smoke_ready_launch_action_coverage_failures(raw_path: str, payload: dict[str, Any]) -> list[str]:
    coverage = payload.get("ready_launch_action_coverage")
    if not isinstance(coverage, dict):
        return [f"JSON evidence artifact ready_launch_action_coverage must be an object: {raw_path}"]

    failures: list[str] = []
    status = coverage.get("status")
    if status not in {"match", "drift"}:
        failures.append(f"JSON evidence artifact ready_launch_action_coverage.status is invalid: {raw_path}")
    action_ids_match = coverage.get("action_ids_match")
    required_env_match = coverage.get("required_env_match")
    if not isinstance(action_ids_match, bool):
        failures.append(f"JSON evidence artifact ready_launch_action_coverage.action_ids_match must be a boolean: {raw_path}")
    if not isinstance(required_env_match, bool):
        failures.append(f"JSON evidence artifact ready_launch_action_coverage.required_env_match must be a boolean: {raw_path}")
    if isinstance(action_ids_match, bool) and isinstance(required_env_match, bool) and status in {"match", "drift"}:
        expected_status = "match" if action_ids_match and required_env_match else "drift"
        if status != expected_status:
            failures.append(
                f"JSON evidence artifact ready_launch_action_coverage.status must match action/env booleans: {raw_path}"
            )
        if expected_status == "drift" and payload.get("ok") is True:
            failures.append(
                f"JSON evidence artifact ready_launch_action_coverage drift must make product-smoke ok=false: {raw_path}"
            )
    for field in READY_LAUNCH_COVERAGE_ARRAY_FIELDS:
        values = coverage.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            failures.append(f"JSON evidence artifact ready_launch_action_coverage.{field} must be a list of strings: {raw_path}")
    return failures


def _product_smoke_launch_decision_failures(
    raw_path: str,
    decision: Any,
    phase: Any,
    readiness_status: Any,
    summary_counts: dict[str, int],
) -> list[str]:
    failures: list[str] = []
    blocker_count = summary_counts.get("blocker_count")
    warning_count = summary_counts.get("warning_count")
    if decision == "go":
        if phase != "launch-ready" or readiness_status != "ready":
            failures.append(
                f"JSON evidence artifact launch_handoff go decision must use launch-ready phase and ready status: {raw_path}"
            )
        if blocker_count or warning_count:
            failures.append(
                f"JSON evidence artifact launch_handoff go decision cannot include blockers or warnings: {raw_path}"
            )
    if decision == "go-with-watch":
        if phase != "operator-review" or readiness_status == "blocked":
            failures.append(
                f"JSON evidence artifact launch_handoff go-with-watch decision must use operator-review phase without blocked readiness: {raw_path}"
            )
        if blocker_count:
            failures.append(
                f"JSON evidence artifact launch_handoff go-with-watch decision cannot include required blockers: {raw_path}"
            )
    if decision == "no-go":
        if phase != "blocked" or readiness_status != "blocked":
            failures.append(
                f"JSON evidence artifact launch_handoff no-go decision must use blocked phase and blocked readiness: {raw_path}"
            )
        if blocker_count == 0:
            failures.append(
                f"JSON evidence artifact launch_handoff no-go decision must include at least one required blocker: {raw_path}"
            )
    return failures


def _browser_smoke_launch_control_failures(raw_path: str, payload: dict[str, Any]) -> list[str]:
    if "launch_control" not in payload:
        return []

    launch_control = payload.get("launch_control")
    if not isinstance(launch_control, dict):
        return [f"JSON evidence artifact launch_control must be an object: {raw_path}"]

    failures: list[str] = []
    if not isinstance(launch_control.get("check_name"), str) or not launch_control.get("check_name"):
        failures.append(f"JSON evidence artifact launch_control.check_name must be a non-empty string: {raw_path}")
    if not isinstance(launch_control.get("ok"), bool):
        failures.append(f"JSON evidence artifact launch_control.ok must be a boolean: {raw_path}")
    if not isinstance(launch_control.get("evidence_source"), str) or not launch_control.get("evidence_source"):
        failures.append(f"JSON evidence artifact launch_control.evidence_source must be a non-empty string: {raw_path}")
    if not isinstance(launch_control.get("api_mocked"), bool):
        failures.append(f"JSON evidence artifact launch_control.api_mocked must be a boolean: {raw_path}")
    mocked_endpoints = launch_control.get("mocked_endpoints")
    if not isinstance(mocked_endpoints, list) or not all(isinstance(endpoint, str) for endpoint in mocked_endpoints):
        failures.append(f"JSON evidence artifact launch_control.mocked_endpoints must be a list of strings: {raw_path}")
    if launch_control.get("release_decision") not in {"go", "go-with-watch", "no-go"}:
        failures.append(f"JSON evidence artifact launch_control.release_decision is invalid: {raw_path}")
    if launch_control.get("operator_phase") not in {"launch-ready", "operator-review", "blocked"}:
        failures.append(f"JSON evidence artifact launch_control.operator_phase is invalid: {raw_path}")
    if launch_control.get("readiness_status") not in {"ready", "degraded", "blocked"}:
        failures.append(f"JSON evidence artifact launch_control.readiness_status is invalid: {raw_path}")
    if not isinstance(launch_control.get("summary"), dict):
        failures.append(f"JSON evidence artifact launch_control.summary must be an object: {raw_path}")
    if not isinstance(launch_control.get("score"), dict):
        failures.append(f"JSON evidence artifact launch_control.score must be an object: {raw_path}")
    launch_blockers = launch_control.get("launch_blockers")
    if not isinstance(launch_blockers, list) or not all(isinstance(blocker, str) for blocker in launch_blockers):
        failures.append(f"JSON evidence artifact launch_control.launch_blockers must be a list of strings: {raw_path}")
    next_action_count = launch_control.get("next_action_count")
    if not _is_non_negative_int(next_action_count):
        failures.append(f"JSON evidence artifact launch_control.next_action_count must be a non-negative integer: {raw_path}")
    next_action_ids = launch_control.get("next_action_ids")
    if not isinstance(next_action_ids, list) or not all(
        isinstance(action_id, str) and action_id.strip() for action_id in next_action_ids
    ):
        failures.append(f"JSON evidence artifact launch_control.next_action_ids must be a list of non-empty strings: {raw_path}")
    elif isinstance(next_action_count, int) and len(next_action_ids) != next_action_count:
        failures.append(
            f"JSON evidence artifact launch_control.next_action_ids length must match next_action_count: {raw_path}"
        )
    next_action_required_env = launch_control.get("next_action_required_env")
    if not isinstance(next_action_required_env, list) or not all(
        isinstance(env_key, str) and env_key.strip() for env_key in next_action_required_env
    ):
        failures.append(
            f"JSON evidence artifact launch_control.next_action_required_env must be a list of non-empty strings: {raw_path}"
        )
    elif any(_contains_secret_shaped_value(env_key) for env_key in next_action_required_env):
        failures.append(
            f"JSON evidence artifact launch_control.next_action_required_env must not contain raw URLs, addresses, or secret-shaped values: {raw_path}"
        )
    control_failures = launch_control.get("failures")
    if not isinstance(control_failures, list) or not all(isinstance(failure, str) for failure in control_failures):
        failures.append(f"JSON evidence artifact launch_control.failures must be a list of strings: {raw_path}")
    launch_env_handoff = launch_control.get("launch_env_handoff")
    if launch_env_handoff is not None:
        if not isinstance(launch_env_handoff, dict):
            failures.append(f"JSON evidence artifact launch_control.launch_env_handoff must be an object: {raw_path}")
        else:
            failures.extend(
                _launch_env_handoff_failures(raw_path, launch_env_handoff, "launch_control.launch_env_handoff")
            )
    return failures


def _browser_smoke_trace_artifact_failures(raw_path: str, payload: dict[str, Any], cwd: str | Path) -> list[str]:
    trace_artifacts = payload.get("trace_artifacts")
    if trace_artifacts is None:
        return []
    if not isinstance(trace_artifacts, list):
        return [f"JSON evidence artifact trace_artifacts must be a list: {raw_path}"]

    failures: list[str] = []
    for trace_artifact in trace_artifacts:
        if (
            not isinstance(trace_artifact, dict)
            or not isinstance(trace_artifact.get("check_name"), str)
            or not trace_artifact.get("check_name")
            or not isinstance(trace_artifact.get("path"), str)
            or not trace_artifact.get("path")
        ):
            failures.append(
                f"JSON evidence artifact trace_artifacts entries must include non-empty check_name and path: {raw_path}"
            )
            break
        trace_path = trace_artifact.get("path")
        if isinstance(trace_path, str) and trace_path:
            resolved_path = _resolve_child_artifact_path(trace_path, cwd)
            if not resolved_path.exists():
                failures.append(f"JSON evidence artifact trace_artifacts path does not exist: {trace_path} ({raw_path})")

    checks = payload.get("checks")
    if isinstance(checks, list):
        invalid_check_trace_paths = [
            index
            for index, check in enumerate(checks)
            if isinstance(check, dict)
            and "trace_path" in check
            and (not isinstance(check.get("trace_path"), str) or not check.get("trace_path"))
        ]
        if invalid_check_trace_paths:
            failures.append(f"JSON evidence artifact checks trace_path values must be non-empty strings: {raw_path}")
    return failures


def _browser_smoke_screenshot_artifact_failures(raw_path: str, payload: dict[str, Any], cwd: str | Path) -> list[str]:
    screenshot_artifacts = payload.get("screenshot_artifacts")
    if screenshot_artifacts is None:
        return []
    if not isinstance(screenshot_artifacts, list):
        return [f"JSON evidence artifact screenshot_artifacts must be a list: {raw_path}"]

    failures: list[str] = []
    for screenshot_artifact in screenshot_artifacts:
        if (
            not isinstance(screenshot_artifact, dict)
            or not isinstance(screenshot_artifact.get("check_name"), str)
            or not screenshot_artifact.get("check_name")
            or not isinstance(screenshot_artifact.get("path"), str)
            or not screenshot_artifact.get("path")
        ):
            failures.append(
                f"JSON evidence artifact screenshot_artifacts entries must include non-empty check_name and path: {raw_path}"
            )
            break
        screenshot_path = screenshot_artifact.get("path")
        if isinstance(screenshot_path, str) and screenshot_path:
            resolved_path = _resolve_child_artifact_path(screenshot_path, cwd)
            if not resolved_path.exists():
                failures.append(
                    f"JSON evidence artifact screenshot_artifacts path does not exist: {screenshot_path} ({raw_path})"
                )

    checks = payload.get("checks")
    if isinstance(checks, list):
        invalid_check_screenshot_paths = [
            index
            for index, check in enumerate(checks)
            if isinstance(check, dict)
            and "screenshot_path" in check
            and (not isinstance(check.get("screenshot_path"), str) or not check.get("screenshot_path"))
        ]
        if invalid_check_screenshot_paths:
            failures.append(f"JSON evidence artifact checks screenshot_path values must be non-empty strings: {raw_path}")
    return failures


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_percentage_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def _preflight_summary_consistency_failures(
    raw_path: str,
    summary: dict[str, Any],
    checks: list[Any],
) -> list[str]:
    if not all(isinstance(summary.get(key), int) for key in ("total", "passed", "failed", "warnings")):
        return []
    passed_count = sum(1 for check in checks if isinstance(check, dict) and check.get("status") == "pass")
    failed_count = sum(1 for check in checks if isinstance(check, dict) and check.get("status") == "fail")
    warning_count = sum(1 for check in checks if isinstance(check, dict) and check.get("status") == "warn")
    expected = {
        "total": len(checks),
        "passed": passed_count,
        "failed": failed_count,
        "warnings": warning_count,
    }
    actual = {key: summary.get(key) for key in expected}
    if actual == expected:
        return []
    return [f"JSON evidence artifact preflight summary does not match checks: {raw_path}"]


def _preflight_check_shape_failures(raw_path: str, checks: list[Any]) -> list[str]:
    invalid_checks = [
        index
        for index, check in enumerate(checks)
        if not isinstance(check, dict)
        or not isinstance(check.get("id"), str)
        or not check.get("id")
        or check.get("status") not in {"pass", "fail", "warn"}
    ]
    if not invalid_checks:
        return []
    return [f"JSON evidence artifact preflight checks must include id and pass/fail/warn status: {raw_path}"]


def _preflight_sources_failures(raw_path: str, sources: Any) -> list[str]:
    if not isinstance(sources, dict) or not isinstance(sources.get("env_files"), list):
        return [f"JSON evidence artifact sources.env_files must be a list: {raw_path}"]
    failures: list[str] = []
    if not isinstance(sources.get("include_process_env"), bool):
        failures.append(f"JSON evidence artifact sources.include_process_env must be a boolean: {raw_path}")
    env_files = sources.get("env_files", [])
    invalid_env_files = [
        index
        for index, env_file in enumerate(env_files)
        if not isinstance(env_file, dict)
        or not isinstance(env_file.get("path"), str)
        or not env_file.get("path")
        or not isinstance(env_file.get("resolved_path"), str)
        or not env_file.get("resolved_path")
        or not isinstance(env_file.get("exists"), bool)
    ]
    if invalid_env_files:
        failures.append(
            f"JSON evidence artifact sources.env_files entries must include non-empty path, resolved_path, and exists: {raw_path}"
        )
    missing_env_files = [
        env_file.get("path")
        for env_file in env_files
        if isinstance(env_file, dict) and env_file.get("exists") is False and isinstance(env_file.get("path"), str)
    ]
    if missing_env_files:
        failures.append(f"JSON evidence artifact sources.env_files must exist: {raw_path}")
    return failures


def write_json_report(
    path: Path,
    results: list[GateResult],
    python_command: dict[str, Any] | None = None,
    release_approval_handoff_path: str | None = None,
) -> None:
    write_json_atomic(
        path,
        json_report_payload(
            results,
            python_command=python_command,
            release_approval_handoff_path=release_approval_handoff_path,
        ),
    )


def json_report_payload(
    results: list[GateResult],
    python_command: dict[str, Any] | None = None,
    release_approval_handoff_path: str | None = None,
) -> dict[str, Any]:
    failed = failed_results(results)
    result_payloads = [result_report(result) for result in results]
    payload = {
        "schema_version": 1,
        "ok": all(result.ok for result in results),
        "generated_at": datetime.now(UTC).isoformat(),
        "duration_ms": sum(result.elapsed_ms for result in results),
        "summary": json_report_summary(results, failed),
        "results": result_payloads,
    }
    if python_command is not None:
        payload["python_command"] = python_command
    if release_approval_handoff_path:
        payload["release_approval_handoff_summary"] = release_approval_handoff_summary(release_approval_handoff_path)
    artifact_result_reports = [
        artifact_report
        for result_payload in result_payloads
        for artifact_report in result_payload.get("artifact_reports", [])
    ]
    if artifact_result_reports:
        payload["artifact_summary"] = artifact_report_summary(artifact_result_reports)
        launch_summary = launch_handoff_summary(artifact_result_reports)
        if launch_summary is not None:
            payload["launch_handoff_summary"] = launch_summary
        launch_env_summary = launch_env_handoff_summary(artifact_result_reports)
        if launch_env_summary is not None:
            payload["launch_env_handoff_summary"] = launch_env_summary
        ready_web3 = ready_web3_summary(artifact_result_reports)
        if ready_web3 is not None:
            payload["ready_web3_summary"] = ready_web3
        ready_launch_coverage = ready_launch_action_coverage_summary(artifact_result_reports)
        if ready_launch_coverage is not None:
            payload["ready_launch_action_coverage_summary"] = ready_launch_coverage
        browser_launch_summary = browser_launch_control_summary(artifact_result_reports)
        if browser_launch_summary is not None:
            payload["browser_launch_control_summary"] = browser_launch_summary
        coverage_comparison = launch_action_coverage_comparison(launch_summary, browser_launch_summary)
        if coverage_comparison is not None:
            payload["launch_action_coverage_comparison"] = coverage_comparison
        browser_trace_summary = browser_trace_artifact_summary(artifact_result_reports)
        if browser_trace_summary is not None:
            payload["browser_trace_artifact_summary"] = browser_trace_summary
        browser_screenshot_summary = browser_screenshot_artifact_summary(artifact_result_reports)
        if browser_screenshot_summary is not None:
            payload["browser_screenshot_artifact_summary"] = browser_screenshot_summary
    return payload


def release_approval_handoff_summary(raw_path: str) -> dict[str, Any]:
    path = Path(raw_path).expanduser()
    resolved = path if path.is_absolute() else PROJECT_ROOT / path
    summary: dict[str, Any] = {
        "path": raw_path,
        "resolved_path": str(resolved.resolve()),
        "exists": resolved.exists(),
        "title_present": False,
        "required_sections": list(RELEASE_APPROVAL_HANDOFF_REQUIRED_SECTIONS),
        "missing_sections": list(RELEASE_APPROVAL_HANDOFF_REQUIRED_SECTIONS),
        "line_count": 0,
        "unsafe_marker_count": 0,
        "ready_for_job_summary": False,
    }
    if not resolved.exists():
        return summary
    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        summary["read_error"] = str(exc)
        return summary
    missing_sections = [section for section in RELEASE_APPROVAL_HANDOFF_REQUIRED_SECTIONS if section not in text]
    unsafe_marker_count = sum(1 for pattern in RELEASE_APPROVAL_HANDOFF_UNSAFE_PATTERNS if pattern.search(text))
    summary.update(
        {
            "title_present": "# Release Approval Operator Handoff" in text,
            "missing_sections": missing_sections,
            "line_count": len(text.splitlines()),
            "unsafe_marker_count": unsafe_marker_count,
            "ready_for_job_summary": "# Release Approval Operator Handoff" in text and not missing_sections and unsafe_marker_count == 0,
        }
    )
    return summary


def release_approval_handoff_result(raw_path: str) -> GateResult:
    summary = release_approval_handoff_summary(raw_path)
    failures = release_approval_handoff_failures(summary)
    return GateResult(
        name="release-approval-handoff",
        command=f"validate release approval handoff {raw_path}",
        cwd=str(PROJECT_ROOT),
        returncode=1 if failures else 0,
        elapsed_ms=0.0,
        command_argv=["release-approval-handoff", raw_path],
        failures=failures or None,
    )


def release_approval_handoff_failures(summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    path = summary.get("path") or "<unknown>"
    if summary.get("exists") is not True:
        failures.append(f"release approval handoff artifact does not exist: {path}")
        return failures
    if summary.get("title_present") is not True:
        failures.append(f"release approval handoff artifact missing title: {path}")
    missing_sections = summary.get("missing_sections")
    if isinstance(missing_sections, list) and missing_sections:
        failures.append(f"release approval handoff artifact missing sections: {', '.join(str(item) for item in missing_sections)}")
    if summary.get("unsafe_marker_count") not in {0, None}:
        failures.append(f"release approval handoff artifact contains unsafe secret-shaped markers: {path}")
    if summary.get("ready_for_job_summary") is not True:
        failures.append(f"release approval handoff artifact is not ready for job summary: {path}")
    return failures


def result_report(result: GateResult) -> dict[str, Any]:
    payload = asdict(result) | {"ok": result.ok}
    if not result.failures:
        payload.pop("failures", None)
    if not result.command_argv:
        payload["command_argv"] = []
    if result.timeout_seconds is None:
        payload.pop("timeout_seconds", None)
    if not result.artifacts:
        payload.pop("artifacts", None)
        payload.pop("artifact_failures", None)
    else:
        reports = dry_run_artifact_reports(result.artifacts) if result.skipped else artifact_reports(result.artifacts, result.cwd, result.name)
        payload["artifact_reports"] = reports
        payload["artifact_summary"] = artifact_report_summary(reports)
        if not result.artifact_failures:
            payload.pop("artifact_failures", None)
    return payload


def dry_run_artifact_reports(paths: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "path": raw_path,
            "exists": None,
            "size_bytes": None,
            "validation_ok": None,
            "validation_skipped": True,
            "validation_skip_reason": "dry_run",
            "validation_failures": [],
        }
        for raw_path in paths
    ]


def artifact_reports(paths: list[str], cwd: str | Path, step_name: str | None = None) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for raw_path in paths:
        path = _artifact_path(raw_path, cwd)
        exists = path.exists()
        validation_failures = artifact_validation_failures([raw_path], Path(cwd), step_name) or []
        report = {
            "path": raw_path,
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else None,
            "validation_ok": not validation_failures,
            "validation_failures": validation_failures,
        }
        if exists:
            report.update(_artifact_json_report(path, cwd))
        reports.append(report)
    return reports


def artifact_report_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    validation_failed = sum(1 for report in reports if report.get("validation_ok") is False)
    validation_skipped = sum(1 for report in reports if report.get("validation_skipped") is True)
    json_valid = [report for report in reports if report.get("json_valid") is True]
    summary = {
        "total": len(reports),
        "existing": sum(1 for report in reports if report.get("exists") is True),
        "missing": sum(1 for report in reports if report.get("exists") is False),
        "validation_passed": sum(1 for report in reports if report.get("validation_ok") is True),
        "validation_failed": validation_failed,
        "json_valid": len(json_valid),
        "json_invalid": sum(1 for report in reports if report.get("json_valid") is False),
        "json_ok": sum(1 for report in reports if report.get("json_ok") is True),
        "json_not_ok": sum(1 for report in reports if report.get("json_ok") is False),
        "schema_versioned": sum(1 for report in json_valid if isinstance(report.get("json_schema_version"), int)),
        "schema_unversioned": sum(1 for report in json_valid if not isinstance(report.get("json_schema_version"), int)),
        "has_failures": validation_failed > 0,
    }
    if validation_skipped:
        summary["validation_skipped"] = validation_skipped
    validation_failures = _aggregate_artifact_check_names(reports, "validation_failures")
    if validation_failures:
        summary["validation_failures"] = validation_failures
        summary["validation_failed_artifact_paths"] = _artifact_paths(
            report for report in reports if report.get("validation_ok") is False
        )
    warning_counts = [report.get("json_check_warnings") for report in reports]
    if any(isinstance(count, int) for count in warning_counts):
        json_warning_count = sum(count for count in warning_counts if isinstance(count, int))
        summary["json_warning_count"] = json_warning_count
        summary["has_warnings"] = json_warning_count > 0
    failed_checks = _aggregate_artifact_check_names(reports, "json_failed_checks")
    if failed_checks:
        summary["json_failed_checks"] = failed_checks
    warning_checks = _aggregate_artifact_check_names(reports, "json_warning_checks")
    if warning_checks:
        summary["json_warning_checks"] = warning_checks
    missing_env_file_counts = [report.get("json_missing_env_file_count") for report in reports]
    if any(isinstance(count, int) for count in missing_env_file_counts):
        missing_env_file_count = sum(count for count in missing_env_file_counts if isinstance(count, int))
        summary["json_missing_env_file_count"] = missing_env_file_count
        summary["has_missing_env_files"] = missing_env_file_count > 0
    missing_env_files = _aggregate_artifact_check_names(reports, "json_missing_env_files")
    if missing_env_files:
        summary["json_missing_env_files"] = missing_env_files
    trace_artifact_counts = [report.get("json_trace_artifact_count") for report in reports]
    if any(isinstance(count, int) for count in trace_artifact_counts):
        trace_artifact_count = sum(count for count in trace_artifact_counts if isinstance(count, int))
        summary["json_trace_artifact_count"] = trace_artifact_count
        summary["has_trace_artifacts"] = trace_artifact_count > 0
    trace_artifact_paths = _aggregate_artifact_check_names(reports, "json_trace_artifact_paths")
    if trace_artifact_paths:
        summary["json_trace_artifact_paths"] = trace_artifact_paths
    trace_artifact_resolved_paths = _aggregate_artifact_check_names(reports, "json_trace_artifact_resolved_paths")
    if trace_artifact_resolved_paths:
        summary["json_trace_artifact_resolved_paths"] = trace_artifact_resolved_paths
    trace_artifact_existing_counts = [report.get("json_trace_artifact_existing_count") for report in reports]
    if any(isinstance(count, int) for count in trace_artifact_existing_counts):
        summary["json_trace_artifact_existing_count"] = sum(
            count for count in trace_artifact_existing_counts if isinstance(count, int)
        )
    trace_artifact_missing_counts = [report.get("json_trace_artifact_missing_count") for report in reports]
    if any(isinstance(count, int) for count in trace_artifact_missing_counts):
        trace_artifact_missing_count = sum(
            count for count in trace_artifact_missing_counts if isinstance(count, int)
        )
        summary["json_trace_artifact_missing_count"] = trace_artifact_missing_count
        summary["has_missing_trace_artifacts"] = trace_artifact_missing_count > 0
    trace_artifact_missing_paths = _aggregate_artifact_check_names(reports, "json_trace_artifact_missing_paths")
    if trace_artifact_missing_paths:
        summary["json_trace_artifact_missing_paths"] = trace_artifact_missing_paths
    screenshot_artifact_counts = [report.get("json_screenshot_artifact_count") for report in reports]
    if any(isinstance(count, int) for count in screenshot_artifact_counts):
        screenshot_artifact_count = sum(count for count in screenshot_artifact_counts if isinstance(count, int))
        summary["json_screenshot_artifact_count"] = screenshot_artifact_count
        summary["has_screenshot_artifacts"] = screenshot_artifact_count > 0
    screenshot_artifact_paths = _aggregate_artifact_check_names(reports, "json_screenshot_artifact_paths")
    if screenshot_artifact_paths:
        summary["json_screenshot_artifact_paths"] = screenshot_artifact_paths
    screenshot_artifact_resolved_paths = _aggregate_artifact_check_names(
        reports, "json_screenshot_artifact_resolved_paths"
    )
    if screenshot_artifact_resolved_paths:
        summary["json_screenshot_artifact_resolved_paths"] = screenshot_artifact_resolved_paths
    screenshot_artifact_existing_counts = [report.get("json_screenshot_artifact_existing_count") for report in reports]
    if any(isinstance(count, int) for count in screenshot_artifact_existing_counts):
        summary["json_screenshot_artifact_existing_count"] = sum(
            count for count in screenshot_artifact_existing_counts if isinstance(count, int)
        )
    screenshot_artifact_missing_counts = [report.get("json_screenshot_artifact_missing_count") for report in reports]
    if any(isinstance(count, int) for count in screenshot_artifact_missing_counts):
        screenshot_artifact_missing_count = sum(
            count for count in screenshot_artifact_missing_counts if isinstance(count, int)
        )
        summary["json_screenshot_artifact_missing_count"] = screenshot_artifact_missing_count
        summary["has_missing_screenshot_artifacts"] = screenshot_artifact_missing_count > 0
    screenshot_artifact_missing_paths = _aggregate_artifact_check_names(
        reports, "json_screenshot_artifact_missing_paths"
    )
    if screenshot_artifact_missing_paths:
        summary["json_screenshot_artifact_missing_paths"] = screenshot_artifact_missing_paths
    if failed_checks or warning_checks:
        summary["artifact_paths"] = [
            report["path"] for report in reports if isinstance(report.get("path"), str) and report.get("path")
        ]
    return summary


def launch_handoff_summary(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    report = next(
        (item for item in reports if item.get("validation_ok") is True and "json_launch_release_decision" in item),
        None,
    )
    if report is None:
        return None

    summary: dict[str, Any] = {}
    path = report.get("path")
    if isinstance(path, str) and path:
        summary["artifact_path"] = path
    summary["evidence_source"] = "product-smoke-live-api"
    if isinstance(report.get("json_launch_ok"), bool):
        summary["ok"] = report.get("json_launch_ok")

    for source_key, output_key in (
        ("json_launch_release_decision", "release_decision"),
        ("json_launch_operator_phase", "operator_phase"),
        ("json_launch_readiness_status", "readiness_status"),
    ):
        value = report.get(source_key)
        if isinstance(value, str):
            summary[output_key] = value

    blocker_count = report.get("json_launch_blocker_count")
    if isinstance(blocker_count, int):
        summary["launch_blocker_count"] = blocker_count
    blockers = report.get("json_launch_blockers")
    if isinstance(blockers, list) and all(isinstance(blocker, str) for blocker in blockers):
        summary["launch_blockers"] = blockers

    action_count = report.get("json_launch_action_count")
    if isinstance(action_count, int):
        summary["next_action_count"] = action_count
    action_ids = report.get("json_launch_action_ids")
    if isinstance(action_ids, list) and all(isinstance(action_id, str) for action_id in action_ids):
        summary["next_action_ids"] = action_ids
    action_required_env = report.get("json_launch_action_required_env")
    if isinstance(action_required_env, list) and all(isinstance(env_key, str) for env_key in action_required_env):
        summary["next_action_required_env"] = action_required_env

    readiness_summary = _launch_handoff_nested_summary(report)
    if readiness_summary:
        summary["readiness_summary"] = readiness_summary

    score = _launch_handoff_score(report)
    if score:
        summary["score"] = score

    return summary


def launch_env_handoff_summary(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    report = next(
        (item for item in reports if item.get("validation_ok") is True and "json_launch_env_status" in item),
        None,
    )
    if report is None:
        return None

    summary: dict[str, Any] = {}
    path = report.get("path")
    if isinstance(path, str) and path:
        summary["artifact_path"] = path
    evidence_source = report.get("json_launch_env_source")
    summary["evidence_source"] = evidence_source if isinstance(evidence_source, str) else "product-smoke-live-api"

    for source_key, output_key in (
        ("json_launch_env_status", "status"),
        ("json_launch_env_secret_policy", "secret_policy"),
    ):
        value = report.get(source_key)
        if isinstance(value, str):
            summary[output_key] = value
    for source_key, output_key in (
        ("json_launch_env_required_action_ids", "required_action_ids"),
        ("json_launch_env_optional_action_ids", "optional_action_ids"),
        ("json_launch_env_required_env", "required_env"),
        ("json_launch_env_optional_env", "optional_env"),
        ("json_launch_env_operator_copy_lines", "operator_copy_lines"),
    ):
        values = report.get(source_key)
        if isinstance(values, list) and all(isinstance(value, str) for value in values):
            summary[output_key] = values
    for source_key, output_key in (
        ("json_launch_env_required_env_count", "required_env_count"),
        ("json_launch_env_optional_env_count", "optional_env_count"),
        ("json_launch_env_operator_copy_line_count", "operator_copy_line_count"),
    ):
        value = report.get(source_key)
        if isinstance(value, int):
            summary[output_key] = value
    return summary


def _launch_handoff_nested_summary(report: dict[str, Any]) -> dict[str, int]:
    fields = {
        "total": "json_launch_summary_total",
        "ready_count": "json_launch_summary_ready_count",
        "required_total": "json_launch_summary_required_total",
        "required_ready_count": "json_launch_summary_required_ready_count",
        "blocker_count": "json_launch_summary_blocker_count",
        "warning_count": "json_launch_summary_warning_count",
    }
    return {target: value for target, source in fields.items() if isinstance((value := report.get(source)), int)}


def _launch_handoff_score(report: dict[str, Any]) -> dict[str, int]:
    fields = {
        "overall_percent": "json_launch_score_overall_percent",
        "required_percent": "json_launch_score_required_percent",
    }
    return {target: value for target, source in fields.items() if isinstance((value := report.get(source)), int)}


def ready_web3_summary(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    report = next(
        (item for item in reports if item.get("validation_ok") is True and "json_ready_web3_status" in item),
        None,
    )
    if report is None:
        return None

    summary: dict[str, Any] = {}
    path = report.get("path")
    if isinstance(path, str) and path:
        summary["artifact_path"] = path
    summary["evidence_source"] = "product-smoke-live-api"
    if isinstance(report.get("json_ready_web3_ok"), bool):
        summary["ok"] = report.get("json_ready_web3_ok")
    status = report.get("json_ready_web3_status")
    if isinstance(status, str):
        summary["status"] = status
    for source_key, output_key in (
        ("json_ready_web3_required", "required"),
        ("json_ready_web3_configured", "configured"),
        ("json_ready_web3_available", "available"),
    ):
        value = report.get(source_key)
        if isinstance(value, bool):
            summary[output_key] = value

    details = _ready_web3_summary_details(report)
    if details:
        summary["details"] = details
    failure_count = report.get("json_ready_web3_failure_count")
    if isinstance(failure_count, int):
        summary["failure_count"] = failure_count
    return summary


def _ready_web3_summary_details(report: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for source_key, output_key in (
        ("json_ready_web3_rpc_configured", "rpc_configured"),
        ("json_ready_web3_rpc_public_https", "rpc_public_https"),
        ("json_ready_web3_mock_mode_enabled", "mock_mode_enabled"),
        ("json_ready_web3_mock_mode_allowed", "mock_mode_allowed"),
    ):
        value = report.get(source_key)
        if isinstance(value, bool):
            details[output_key] = value
    contract_count = report.get("json_ready_web3_contract_count")
    if isinstance(contract_count, int):
        details["contract_count"] = contract_count
    contracts = report.get("json_ready_web3_contracts")
    if isinstance(contracts, dict) and all(isinstance(key, str) and isinstance(value, bool) for key, value in contracts.items()):
        details["contracts"] = contracts
    return details


def ready_launch_action_coverage_summary(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    report = next(
        (item for item in reports if item.get("validation_ok") is True and "json_ready_launch_coverage_status" in item),
        None,
    )
    if report is None:
        return None

    summary: dict[str, Any] = {}
    path = report.get("path")
    if isinstance(path, str) and path:
        summary["artifact_path"] = path
    summary["evidence_source"] = "product-smoke-live-api"

    status = report.get("json_ready_launch_coverage_status")
    if isinstance(status, str):
        summary["status"] = status
    for source_key, output_key in (
        ("json_ready_launch_action_ids_match", "action_ids_match"),
        ("json_ready_launch_required_env_match", "required_env_match"),
    ):
        value = report.get(source_key)
        if isinstance(value, bool):
            summary[output_key] = value
    for field in READY_LAUNCH_COVERAGE_ARRAY_FIELDS:
        values = report.get(f"json_ready_launch_{field}")
        if isinstance(values, list) and all(isinstance(value, str) for value in values):
            summary[field] = values
    return summary


def browser_launch_control_summary(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    report = next(
        (item for item in reports if item.get("validation_ok") is True and "json_browser_launch_release_decision" in item),
        None,
    )
    if report is None:
        return None

    summary: dict[str, Any] = {}
    path = report.get("path")
    if isinstance(path, str) and path:
        summary["artifact_path"] = path
    check_name = report.get("json_browser_launch_check_name")
    if isinstance(check_name, str) and check_name:
        summary["check_name"] = check_name
    evidence_source = report.get("json_browser_launch_evidence_source")
    if isinstance(evidence_source, str) and evidence_source:
        summary["evidence_source"] = evidence_source
    if isinstance(report.get("json_browser_launch_api_mocked"), bool):
        summary["api_mocked"] = report.get("json_browser_launch_api_mocked")
    mocked_endpoints = report.get("json_browser_launch_mocked_endpoints")
    if isinstance(mocked_endpoints, list) and all(isinstance(endpoint, str) for endpoint in mocked_endpoints):
        summary["mocked_endpoints"] = mocked_endpoints
    if isinstance(report.get("json_browser_launch_ok"), bool):
        summary["ok"] = report.get("json_browser_launch_ok")

    for source_key, output_key in (
        ("json_browser_launch_release_decision", "release_decision"),
        ("json_browser_launch_operator_phase", "operator_phase"),
        ("json_browser_launch_readiness_status", "readiness_status"),
    ):
        value = report.get(source_key)
        if isinstance(value, str):
            summary[output_key] = value

    blocker_count = report.get("json_browser_launch_blocker_count")
    if isinstance(blocker_count, int):
        summary["launch_blocker_count"] = blocker_count
    action_count = report.get("json_browser_launch_action_count")
    if isinstance(action_count, int):
        summary["next_action_count"] = action_count
    action_ids = report.get("json_browser_launch_action_ids")
    if isinstance(action_ids, list) and all(isinstance(action_id, str) for action_id in action_ids):
        summary["next_action_ids"] = action_ids
    action_required_env = report.get("json_browser_launch_action_required_env")
    if isinstance(action_required_env, list) and all(isinstance(env_key, str) for env_key in action_required_env):
        summary["next_action_required_env"] = action_required_env
    readiness_summary = _browser_launch_control_nested_summary(report)
    if readiness_summary:
        summary["readiness_summary"] = readiness_summary
    score = _browser_launch_control_score(report)
    if score:
        summary["score"] = score
    return summary


def _browser_launch_control_nested_summary(report: dict[str, Any]) -> dict[str, int]:
    fields = {
        "total": "json_browser_launch_summary_total",
        "ready_count": "json_browser_launch_summary_ready_count",
        "required_total": "json_browser_launch_summary_required_total",
        "required_ready_count": "json_browser_launch_summary_required_ready_count",
        "blocker_count": "json_browser_launch_summary_blocker_count",
        "warning_count": "json_browser_launch_summary_warning_count",
    }
    return {target: value for target, source in fields.items() if isinstance((value := report.get(source)), int)}


def _browser_launch_control_score(report: dict[str, Any]) -> dict[str, int]:
    fields = {
        "overall_percent": "json_browser_launch_score_overall_percent",
        "required_percent": "json_browser_launch_score_required_percent",
    }
    return {target: value for target, source in fields.items() if isinstance((value := report.get(source)), int)}


def launch_action_coverage_comparison(
    launch_summary: dict[str, Any] | None,
    browser_launch_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if launch_summary is None or browser_launch_summary is None:
        return None

    live_action_ids = _summary_string_list(launch_summary, "next_action_ids")
    browser_action_ids = _summary_string_list(browser_launch_summary, "next_action_ids")
    live_required_env = _summary_string_list(launch_summary, "next_action_required_env")
    browser_required_env = _summary_string_list(browser_launch_summary, "next_action_required_env")
    action_ids_match = live_action_ids == browser_action_ids
    required_env_match = live_required_env == browser_required_env

    comparison: dict[str, Any] = {
        "status": "match" if action_ids_match and required_env_match else "drift",
        "action_ids_match": action_ids_match,
        "required_env_match": required_env_match,
        "live_action_ids": live_action_ids,
        "browser_action_ids": browser_action_ids,
        "shared_action_ids": _ordered_intersection(live_action_ids, browser_action_ids),
        "live_only_action_ids": _ordered_difference(live_action_ids, browser_action_ids),
        "browser_only_action_ids": _ordered_difference(browser_action_ids, live_action_ids),
        "live_required_env": live_required_env,
        "browser_required_env": browser_required_env,
        "shared_required_env": _ordered_intersection(live_required_env, browser_required_env),
        "live_only_required_env": _ordered_difference(live_required_env, browser_required_env),
        "browser_only_required_env": _ordered_difference(browser_required_env, live_required_env),
    }
    live_next_action_count = launch_summary.get("next_action_count")
    if isinstance(live_next_action_count, int):
        comparison["live_next_action_count"] = live_next_action_count
    browser_next_action_count = browser_launch_summary.get("next_action_count")
    if isinstance(browser_next_action_count, int):
        comparison["browser_next_action_count"] = browser_next_action_count
    for source_summary, prefix in ((launch_summary, "live"), (browser_launch_summary, "browser")):
        artifact_path = source_summary.get("artifact_path")
        if isinstance(artifact_path, str) and artifact_path:
            comparison[f"{prefix}_artifact_path"] = artifact_path
        evidence_source = source_summary.get("evidence_source")
        if isinstance(evidence_source, str) and evidence_source:
            comparison[f"{prefix}_evidence_source"] = evidence_source
    return comparison


def _summary_string_list(summary: dict[str, Any], key: str) -> list[str]:
    values = summary.get(key)
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str)]


def _ordered_intersection(left: list[str], right: list[str]) -> list[str]:
    right_values = set(right)
    return [value for value in left if value in right_values]


def _ordered_difference(left: list[str], right: list[str]) -> list[str]:
    right_values = set(right)
    return [value for value in left if value not in right_values]


def strict_launch_action_coverage_result(payload: dict[str, Any]) -> GateResult | None:
    failures = strict_launch_action_coverage_failures(payload)
    if not failures:
        return None
    return GateResult(
        name="launch-action-coverage",
        command="release_gate strict launch action coverage comparison",
        cwd=str(PROJECT_ROOT),
        returncode=1,
        elapsed_ms=0.0,
        command_argv=["release_gate", "strict", "launch-action-coverage"],
        failures=failures,
    )


def strict_launch_action_coverage_failures(payload: dict[str, Any]) -> list[str]:
    comparison = payload.get("launch_action_coverage_comparison")
    if not isinstance(comparison, dict):
        return [
            "strict launch action coverage requires validated product-smoke and browser-smoke launch action coverage"
        ]
    status = comparison.get("status")
    if status == "match":
        return []
    if status != "drift":
        return ["strict launch action coverage comparison status must be match or drift"]

    failures = ["strict launch action coverage drift: live and browser launch action coverage differ"]
    for key, label in (
        ("live_only_action_ids", "live-only action ids"),
        ("browser_only_action_ids", "browser-only action ids"),
        ("live_only_required_env", "live-only required env"),
        ("browser_only_required_env", "browser-only required env"),
    ):
        values = comparison.get(key)
        if isinstance(values, list) and all(isinstance(value, str) for value in values) and values:
            failures.append(f"{label}: {', '.join(values)}")
    return failures


def browser_trace_artifact_summary(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    trace_reports = [
        report
        for report in reports
        if isinstance(report.get("json_trace_artifact_count"), int) and report.get("json_trace_artifact_count") > 0
    ]
    if not trace_reports:
        return None

    trace_artifact_count = sum(
        count
        for report in trace_reports
        if isinstance((count := report.get("json_trace_artifact_count")), int)
    )
    existing_count = sum(
        count
        for report in trace_reports
        if isinstance((count := report.get("json_trace_artifact_existing_count")), int)
    )
    missing_count = sum(
        count
        for report in trace_reports
        if isinstance((count := report.get("json_trace_artifact_missing_count")), int)
    )
    summary: dict[str, Any] = {
        "artifact_paths": _artifact_paths(trace_reports),
        "trace_artifact_count": trace_artifact_count,
        "existing_count": existing_count,
        "missing_count": missing_count,
        "has_missing_trace_artifacts": missing_count > 0,
    }

    trace_artifact_paths = _aggregate_artifact_check_names(trace_reports, "json_trace_artifact_paths")
    if trace_artifact_paths:
        summary["trace_artifact_paths"] = trace_artifact_paths
    resolved_paths = _aggregate_artifact_check_names(trace_reports, "json_trace_artifact_resolved_paths")
    if resolved_paths:
        summary["resolved_paths"] = resolved_paths
    missing_paths = _aggregate_artifact_check_names(trace_reports, "json_trace_artifact_missing_paths")
    if missing_paths:
        summary["missing_paths"] = missing_paths
    checks = _aggregate_artifact_check_names(trace_reports, "json_trace_artifact_checks")
    if checks:
        summary["checks"] = checks
    trace_viewer_commands = _trace_viewer_commands(resolved_paths, missing_paths)
    if trace_viewer_commands:
        summary["trace_viewer_commands"] = trace_viewer_commands
    return summary


def browser_screenshot_artifact_summary(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    screenshot_reports = [
        report
        for report in reports
        if isinstance(report.get("json_screenshot_artifact_count"), int)
        and report.get("json_screenshot_artifact_count") > 0
    ]
    if not screenshot_reports:
        return None

    screenshot_artifact_count = sum(
        count
        for report in screenshot_reports
        if isinstance((count := report.get("json_screenshot_artifact_count")), int)
    )
    existing_count = sum(
        count
        for report in screenshot_reports
        if isinstance((count := report.get("json_screenshot_artifact_existing_count")), int)
    )
    missing_count = sum(
        count
        for report in screenshot_reports
        if isinstance((count := report.get("json_screenshot_artifact_missing_count")), int)
    )
    summary: dict[str, Any] = {
        "artifact_paths": _artifact_paths(screenshot_reports),
        "screenshot_artifact_count": screenshot_artifact_count,
        "existing_count": existing_count,
        "missing_count": missing_count,
        "has_missing_screenshot_artifacts": missing_count > 0,
    }

    screenshot_artifact_paths = _aggregate_artifact_check_names(screenshot_reports, "json_screenshot_artifact_paths")
    if screenshot_artifact_paths:
        summary["screenshot_artifact_paths"] = screenshot_artifact_paths
    resolved_paths = _aggregate_artifact_check_names(screenshot_reports, "json_screenshot_artifact_resolved_paths")
    if resolved_paths:
        summary["resolved_paths"] = resolved_paths
    missing_paths = _aggregate_artifact_check_names(screenshot_reports, "json_screenshot_artifact_missing_paths")
    if missing_paths:
        summary["missing_paths"] = missing_paths
    checks = _aggregate_artifact_check_names(screenshot_reports, "json_screenshot_artifact_checks")
    if checks:
        summary["checks"] = checks
    return summary


def _trace_viewer_commands(resolved_paths: list[str], missing_paths: list[str]) -> list[dict[str, Any]]:
    missing_path_set = set(missing_paths)
    return [
        {"path": path, "argv": ["npx", "playwright", "show-trace", path]}
        for path in resolved_paths
        if path not in missing_path_set
    ]


def _artifact_paths(reports: Iterable[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for report in reports:
        path = report.get("path")
        if isinstance(path, str) and path and path not in paths:
            paths.append(path)
    return paths


def _aggregate_artifact_check_names(reports: list[dict[str, Any]], field: str) -> list[str]:
    names: list[str] = []
    for report in reports:
        values = report.get(field)
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and value and value not in names:
                names.append(value)
    return names


def _artifact_json_report(path: Path, cwd: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"json_valid": False, "json_ok": None, "json_schema_version": None}
    if not isinstance(payload, dict):
        return {"json_valid": False, "json_ok": None, "json_schema_version": None}
    return {
        "json_valid": True,
        "json_ok": payload.get("ok"),
        "json_schema_version": payload.get("schema_version"),
        "json_generated_at": payload.get("generated_at"),
        "json_api": payload.get("api"),
        "json_frontend": payload.get("frontend"),
        **_artifact_json_provenance_report(payload),
        **_artifact_json_trace_report(payload, cwd),
        **_artifact_json_screenshot_report(payload, cwd),
        **_artifact_json_launch_handoff_report(payload),
        **_artifact_json_launch_env_handoff_report(payload),
        **_artifact_json_ready_web3_report(payload),
        **_artifact_json_ready_launch_action_coverage_report(payload),
        **_artifact_json_browser_launch_control_report(payload),
        **_artifact_json_check_report(payload),
    }


def _artifact_json_trace_report(payload: dict[str, Any], cwd: str | Path) -> dict[str, Any]:
    trace_artifacts = payload.get("trace_artifacts")
    if not isinstance(trace_artifacts, list):
        return {}
    paths: list[str] = []
    resolved_paths: list[str] = []
    missing_paths: list[str] = []
    checks: list[str] = []
    for trace_artifact in trace_artifacts:
        if not isinstance(trace_artifact, dict):
            continue
        path = trace_artifact.get("path")
        check_name = trace_artifact.get("check_name")
        if isinstance(path, str) and path:
            paths.append(path)
            resolved_path = _resolve_child_artifact_path(path, cwd)
            resolved_path_text = str(resolved_path)
            resolved_paths.append(resolved_path_text)
            if not resolved_path.exists():
                missing_paths.append(resolved_path_text)
        if isinstance(check_name, str) and check_name:
            checks.append(check_name)
    existing_count = len(resolved_paths) - len(missing_paths)
    return {
        "json_trace_artifact_count": len(paths),
        "json_trace_artifact_paths": paths,
        "json_trace_artifact_resolved_paths": resolved_paths,
        "json_trace_artifact_existing_count": existing_count,
        "json_trace_artifact_missing_count": len(missing_paths),
        "json_trace_artifact_missing_paths": missing_paths,
        "json_trace_artifact_checks": checks,
    }


def _artifact_json_screenshot_report(payload: dict[str, Any], cwd: str | Path) -> dict[str, Any]:
    screenshot_artifacts = payload.get("screenshot_artifacts")
    if not isinstance(screenshot_artifacts, list):
        return {}
    paths: list[str] = []
    resolved_paths: list[str] = []
    missing_paths: list[str] = []
    checks: list[str] = []
    for screenshot_artifact in screenshot_artifacts:
        if not isinstance(screenshot_artifact, dict):
            continue
        path = screenshot_artifact.get("path")
        check_name = screenshot_artifact.get("check_name")
        if isinstance(path, str) and path:
            paths.append(path)
            resolved_path = _resolve_child_artifact_path(path, cwd)
            resolved_path_text = str(resolved_path)
            resolved_paths.append(resolved_path_text)
            if not resolved_path.exists():
                missing_paths.append(resolved_path_text)
        if isinstance(check_name, str) and check_name:
            checks.append(check_name)
    existing_count = len(resolved_paths) - len(missing_paths)
    return {
        "json_screenshot_artifact_count": len(paths),
        "json_screenshot_artifact_paths": paths,
        "json_screenshot_artifact_resolved_paths": resolved_paths,
        "json_screenshot_artifact_existing_count": existing_count,
        "json_screenshot_artifact_missing_count": len(missing_paths),
        "json_screenshot_artifact_missing_paths": missing_paths,
        "json_screenshot_artifact_checks": checks,
    }


def _resolve_child_artifact_path(raw_path: str, cwd: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path(cwd) / path
    return path.resolve()


def _artifact_json_provenance_report(payload: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    if isinstance(payload.get("profile"), str):
        report["json_profile"] = payload.get("profile")
    targets = payload.get("targets")
    if isinstance(targets, list) and all(isinstance(target, str) for target in targets):
        report["json_targets"] = targets
    sources = payload.get("sources")
    if isinstance(sources, dict):
        env_files = sources.get("env_files")
        if isinstance(env_files, list):
            report["json_env_file_count"] = len(env_files)
            missing_env_files = [
                env_file.get("path")
                for env_file in env_files
                if isinstance(env_file, dict) and env_file.get("exists") is False and isinstance(env_file.get("path"), str)
            ]
            report["json_missing_env_file_count"] = len(missing_env_files)
            report["json_missing_env_files"] = missing_env_files
        include_process_env = sources.get("include_process_env")
        if isinstance(include_process_env, bool):
            report["json_include_process_env"] = include_process_env
    return report


def _artifact_json_launch_handoff_report(payload: dict[str, Any]) -> dict[str, Any]:
    launch_handoff = payload.get("launch_handoff")
    if not isinstance(launch_handoff, dict):
        return {}

    report: dict[str, Any] = {"json_launch_ok": launch_handoff.get("ok")}
    for source_key, report_key in (
        ("release_decision", "json_launch_release_decision"),
        ("operator_phase", "json_launch_operator_phase"),
        ("readiness_status", "json_launch_readiness_status"),
    ):
        value = launch_handoff.get(source_key)
        if isinstance(value, str):
            report[report_key] = value

    launch_blockers = launch_handoff.get("launch_blockers")
    if isinstance(launch_blockers, list) and all(isinstance(blocker, str) for blocker in launch_blockers):
        report["json_launch_blocker_count"] = len(launch_blockers)
        report["json_launch_blockers"] = launch_blockers

    next_actions = launch_handoff.get("next_actions")
    if isinstance(next_actions, list):
        report["json_launch_action_count"] = len(next_actions)
        action_ids, required_env = _launch_action_coverage(next_actions)
        if action_ids:
            report["json_launch_action_ids"] = action_ids
        if required_env:
            report["json_launch_action_required_env"] = required_env

    summary = launch_handoff.get("summary")
    if isinstance(summary, dict):
        for field in ("total", "ready_count", "required_total", "required_ready_count", "blocker_count", "warning_count"):
            value = summary.get(field)
            if isinstance(value, int):
                report[f"json_launch_summary_{field}"] = value

    score = launch_handoff.get("score")
    if isinstance(score, dict):
        for field in ("overall_percent", "required_percent"):
            value = score.get(field)
            if isinstance(value, int):
                report[f"json_launch_score_{field}"] = value

    return report


def _artifact_json_launch_env_handoff_report(payload: dict[str, Any]) -> dict[str, Any]:
    handoff = _artifact_json_launch_env_handoff_payload(payload)
    if not isinstance(handoff, dict):
        return {}

    report: dict[str, Any] = {}
    source = handoff.get("source")
    if isinstance(source, str) and source:
        report["json_launch_env_source"] = source
    status = handoff.get("status")
    if isinstance(status, str):
        report["json_launch_env_status"] = status
    secret_policy = handoff.get("secret_policy")
    if isinstance(secret_policy, str):
        report["json_launch_env_secret_policy"] = secret_policy
    for field in LAUNCH_ENV_HANDOFF_ARRAY_FIELDS:
        values = handoff.get(field)
        if isinstance(values, list) and all(isinstance(value, str) for value in values):
            report[f"json_launch_env_{field}"] = values
    required_env = handoff.get("required_env")
    if isinstance(required_env, list):
        report["json_launch_env_required_env_count"] = len(required_env)
    optional_env = handoff.get("optional_env")
    if isinstance(optional_env, list):
        report["json_launch_env_optional_env_count"] = len(optional_env)
    operator_copy_lines = handoff.get("operator_copy_lines")
    if isinstance(operator_copy_lines, list):
        report["json_launch_env_operator_copy_line_count"] = len(operator_copy_lines)
    return report


def _artifact_json_launch_env_handoff_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    handoff = payload.get("launch_env_handoff")
    if isinstance(handoff, dict):
        return handoff

    launch_control = payload.get("launch_control")
    if not isinstance(launch_control, dict):
        return None
    nested_handoff = launch_control.get("launch_env_handoff")
    return nested_handoff if isinstance(nested_handoff, dict) else None


def _launch_action_coverage(next_actions: list[Any]) -> tuple[list[str], list[str]]:
    action_ids: list[str] = []
    required_env: list[str] = []
    for action in next_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if isinstance(action_id, str) and action_id:
            action_ids.append(action_id)
        env_values = action.get("required_env")
        if isinstance(env_values, list):
            required_env.extend(item for item in env_values if isinstance(item, str) and item)
    return _unique_strings(action_ids), _unique_strings(required_env)


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _artifact_json_ready_web3_report(payload: dict[str, Any]) -> dict[str, Any]:
    ready_web3 = payload.get("ready_web3")
    if not isinstance(ready_web3, dict):
        return {}

    report: dict[str, Any] = {"json_ready_web3_ok": ready_web3.get("ok")}
    status = ready_web3.get("status")
    if isinstance(status, str):
        report["json_ready_web3_status"] = status
    for source_key, report_key in (
        ("required", "json_ready_web3_required"),
        ("configured", "json_ready_web3_configured"),
        ("available", "json_ready_web3_available"),
    ):
        value = ready_web3.get(source_key)
        if isinstance(value, bool):
            report[report_key] = value

    details = ready_web3.get("details")
    if isinstance(details, dict):
        for source_key, report_key in (
            ("rpc_configured", "json_ready_web3_rpc_configured"),
            ("rpc_public_https", "json_ready_web3_rpc_public_https"),
            ("mock_mode_enabled", "json_ready_web3_mock_mode_enabled"),
            ("mock_mode_allowed", "json_ready_web3_mock_mode_allowed"),
        ):
            value = details.get(source_key)
            if isinstance(value, bool):
                report[report_key] = value
        contract_count = details.get("contract_count")
        if isinstance(contract_count, int) and not isinstance(contract_count, bool):
            report["json_ready_web3_contract_count"] = contract_count
        contracts = details.get("contracts")
        if isinstance(contracts, dict) and all(isinstance(key, str) and isinstance(value, bool) for key, value in contracts.items()):
            report["json_ready_web3_contracts"] = contracts
    ready_failures = ready_web3.get("failures")
    if isinstance(ready_failures, list) and all(isinstance(failure, str) for failure in ready_failures):
        report["json_ready_web3_failure_count"] = len(ready_failures)
    return report


def _artifact_json_ready_launch_action_coverage_report(payload: dict[str, Any]) -> dict[str, Any]:
    coverage = payload.get("ready_launch_action_coverage")
    if not isinstance(coverage, dict):
        return {}

    report: dict[str, Any] = {}
    status = coverage.get("status")
    if isinstance(status, str):
        report["json_ready_launch_coverage_status"] = status
    action_ids_match = coverage.get("action_ids_match")
    if isinstance(action_ids_match, bool):
        report["json_ready_launch_action_ids_match"] = action_ids_match
    required_env_match = coverage.get("required_env_match")
    if isinstance(required_env_match, bool):
        report["json_ready_launch_required_env_match"] = required_env_match
    for field in READY_LAUNCH_COVERAGE_ARRAY_FIELDS:
        values = coverage.get(field)
        if isinstance(values, list) and all(isinstance(value, str) for value in values):
            report[f"json_ready_launch_{field}"] = values
    return report


def _artifact_json_browser_launch_control_report(payload: dict[str, Any]) -> dict[str, Any]:
    launch_control = payload.get("launch_control")
    if not isinstance(launch_control, dict):
        return {}

    report: dict[str, Any] = {"json_browser_launch_ok": launch_control.get("ok")}
    check_name = launch_control.get("check_name")
    if isinstance(check_name, str):
        report["json_browser_launch_check_name"] = check_name
    evidence_source = launch_control.get("evidence_source")
    if isinstance(evidence_source, str):
        report["json_browser_launch_evidence_source"] = evidence_source
    api_mocked = launch_control.get("api_mocked")
    if isinstance(api_mocked, bool):
        report["json_browser_launch_api_mocked"] = api_mocked
    mocked_endpoints = launch_control.get("mocked_endpoints")
    if isinstance(mocked_endpoints, list) and all(isinstance(endpoint, str) for endpoint in mocked_endpoints):
        report["json_browser_launch_mocked_endpoints"] = mocked_endpoints
    for source_key, report_key in (
        ("release_decision", "json_browser_launch_release_decision"),
        ("operator_phase", "json_browser_launch_operator_phase"),
        ("readiness_status", "json_browser_launch_readiness_status"),
    ):
        value = launch_control.get(source_key)
        if isinstance(value, str):
            report[report_key] = value

    launch_blockers = launch_control.get("launch_blockers")
    if isinstance(launch_blockers, list) and all(isinstance(blocker, str) for blocker in launch_blockers):
        report["json_browser_launch_blocker_count"] = len(launch_blockers)
        report["json_browser_launch_blockers"] = launch_blockers

    action_count = launch_control.get("next_action_count")
    if isinstance(action_count, int):
        report["json_browser_launch_action_count"] = action_count
    action_ids = launch_control.get("next_action_ids")
    if isinstance(action_ids, list) and all(isinstance(action_id, str) for action_id in action_ids):
        report["json_browser_launch_action_ids"] = action_ids
    action_required_env = launch_control.get("next_action_required_env")
    if isinstance(action_required_env, list) and all(isinstance(env_key, str) for env_key in action_required_env):
        report["json_browser_launch_action_required_env"] = action_required_env

    summary = launch_control.get("summary")
    if isinstance(summary, dict):
        for field in ("total", "ready_count", "required_total", "required_ready_count", "blocker_count", "warning_count"):
            value = summary.get(field)
            if isinstance(value, int):
                report[f"json_browser_launch_summary_{field}"] = value

    score = launch_control.get("score")
    if isinstance(score, dict):
        for field in ("overall_percent", "required_percent"):
            value = score.get(field)
            if isinstance(value, int):
                report[f"json_browser_launch_score_{field}"] = value

    return report


def _artifact_json_check_report(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    checks = payload.get("checks")
    failed_checks: list[str] = []
    warning_checks: list[str] = []
    if isinstance(checks, list):
        failed_checks = [
            _check_display_name(check)
            for check in checks
            if isinstance(check, dict) and _check_failed(check) and _check_display_name(check)
        ]
        warning_checks = [
            _check_display_name(check)
            for check in checks
            if isinstance(check, dict) and _check_warned(check) and _check_display_name(check)
        ]
    report = {
        "json_check_total": summary.get("total") if isinstance(summary, dict) else None,
        "json_check_passed": summary.get("passed") if isinstance(summary, dict) else None,
        "json_check_failed": summary.get("failed") if isinstance(summary, dict) else None,
        "json_failed_checks": failed_checks,
    }
    if isinstance(summary, dict) and isinstance(summary.get("warnings"), int):
        report["json_check_warnings"] = summary.get("warnings")
        report["json_warning_checks"] = warning_checks
    return report


def _check_failed(check: dict[str, Any]) -> bool:
    return check.get("ok") is False or check.get("status") == "fail"


def _check_warned(check: dict[str, Any]) -> bool:
    return check.get("status") == "warn"


def _check_display_name(check: dict[str, Any]) -> str | None:
    for key in ("name", "id", "label"):
        value = check.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def failed_results(results: list[GateResult]) -> list[GateResult]:
    return [result for result in results if not result.ok]


def json_report_summary(results: list[GateResult], failed: list[GateResult]) -> dict[str, Any]:
    return {
        "total": len(results),
        "passed": sum(1 for result in results if result.ok and not result.skipped),
        "failed": len(failed),
        "skipped": sum(1 for result in results if result.skipped),
        "failed_step": failed[0].name if failed else None,
    }


def json_report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://dsci-decentbio.local/schemas/release-gate-report.schema.json",
        "title": "DSCI-DecentBio release-gate parent report",
        "type": "object",
        "required": ["schema_version", "ok", "generated_at", "duration_ms", "summary", "results"],
        "properties": {
            "schema_version": {"const": 1},
            "ok": {"type": "boolean"},
            "generated_at": {"type": "string", "format": "date-time"},
            "duration_ms": {"type": "number"},
            "python_command": {"type": "object"},
            "summary": {
                "type": "object",
                "required": ["total", "passed", "failed", "skipped", "failed_step"],
                "properties": {
                    "total": {"type": "integer"},
                    "passed": {"type": "integer"},
                    "failed": {"type": "integer"},
                    "skipped": {"type": "integer"},
                    "failed_step": {"type": ["string", "null"]},
                },
            },
            "results": {
                "type": "array",
                "items": _gate_result_schema(),
            },
            "artifact_summary": {"type": "object"},
            "release_approval_handoff_summary": {
                "type": "object",
                "required": [
                    "path",
                    "resolved_path",
                    "exists",
                    "title_present",
                    "required_sections",
                    "missing_sections",
                    "line_count",
                    "unsafe_marker_count",
                    "ready_for_job_summary",
                ],
                "properties": {
                    "path": {"type": "string"},
                    "resolved_path": {"type": "string"},
                    "exists": {"type": "boolean"},
                    "title_present": {"type": "boolean"},
                    "required_sections": _string_array_schema(),
                    "missing_sections": _string_array_schema(),
                    "line_count": {"type": "integer"},
                    "unsafe_marker_count": {"type": "integer"},
                    "ready_for_job_summary": {"type": "boolean"},
                    "read_error": {"type": "string"},
                },
            },
            "launch_handoff_summary": {
                "type": "object",
                "properties": {
                    "artifact_path": {"type": "string"},
                    "evidence_source": {"type": "string"},
                    "ok": {"type": "boolean"},
                    "release_decision": {"type": "string", "enum": ["go", "go-with-watch", "no-go"]},
                    "operator_phase": {"type": "string", "enum": ["launch-ready", "operator-review", "blocked"]},
                    "readiness_status": {"type": "string", "enum": ["ready", "degraded", "blocked"]},
                    "launch_blocker_count": {"type": "integer"},
                    "launch_blockers": {"type": "array", "items": {"type": "string"}},
                    "next_action_count": {"type": "integer"},
                    "next_action_ids": {"type": "array", "items": {"type": "string"}},
                    "next_action_required_env": {"type": "array", "items": {"type": "string"}},
                    "readiness_summary": {"type": "object"},
                    "score": {"type": "object"},
                },
            },
            "launch_env_handoff_summary": _launch_env_handoff_schema(),
            "ready_web3_summary": {
                "type": "object",
                "properties": {
                    "artifact_path": {"type": "string"},
                    "evidence_source": {"type": "string"},
                    "ok": {"type": "boolean"},
                    "status": {"type": "string", "enum": ["pass", "warn", "fail"]},
                    "required": {"type": "boolean"},
                    "configured": {"type": "boolean"},
                    "available": {"type": "boolean"},
                    "failure_count": {"type": "integer"},
                    "details": {
                        "type": "object",
                        "properties": {
                            "rpc_configured": {"type": "boolean"},
                            "rpc_public_https": {"type": "boolean"},
                            "contract_count": {"type": "integer"},
                            "contracts": {
                                "type": "object",
                                "additionalProperties": {"type": "boolean"},
                            },
                            "mock_mode_enabled": {"type": "boolean"},
                            "mock_mode_allowed": {"type": "boolean"},
                        },
                    },
                },
            },
            "ready_launch_action_coverage_summary": _ready_launch_action_coverage_schema(),
            "browser_launch_control_summary": {
                "type": "object",
                "properties": {
                    "artifact_path": {"type": "string"},
                    "check_name": {"type": "string"},
                    "evidence_source": {"type": "string"},
                    "api_mocked": {"type": "boolean"},
                    "mocked_endpoints": _string_array_schema(),
                    "ok": {"type": "boolean"},
                    "release_decision": {"type": "string", "enum": ["go", "go-with-watch", "no-go"]},
                    "operator_phase": {"type": "string", "enum": ["launch-ready", "operator-review", "blocked"]},
                    "readiness_status": {"type": "string", "enum": ["ready", "degraded", "blocked"]},
                    "launch_blocker_count": {"type": "integer"},
                    "next_action_count": {"type": "integer"},
                    "next_action_ids": _string_array_schema(),
                    "next_action_required_env": _string_array_schema(),
                    "readiness_summary": {
                        "type": "object",
                        "properties": {
                            "total": {"type": "integer"},
                            "ready_count": {"type": "integer"},
                            "required_total": {"type": "integer"},
                            "required_ready_count": {"type": "integer"},
                            "blocker_count": {"type": "integer"},
                            "warning_count": {"type": "integer"},
                        },
                    },
                    "score": {
                        "type": "object",
                        "properties": {
                            "overall_percent": {"type": "integer"},
                            "required_percent": {"type": "integer"},
                        },
                    },
                },
            },
            "launch_action_coverage_comparison": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["match", "drift"]},
                    "action_ids_match": {"type": "boolean"},
                    "required_env_match": {"type": "boolean"},
                    "live_artifact_path": {"type": "string"},
                    "browser_artifact_path": {"type": "string"},
                    "live_evidence_source": {"type": "string"},
                    "browser_evidence_source": {"type": "string"},
                    "live_next_action_count": {"type": "integer"},
                    "browser_next_action_count": {"type": "integer"},
                    "live_action_ids": _string_array_schema(),
                    "browser_action_ids": _string_array_schema(),
                    "shared_action_ids": _string_array_schema(),
                    "live_only_action_ids": _string_array_schema(),
                    "browser_only_action_ids": _string_array_schema(),
                    "live_required_env": _string_array_schema(),
                    "browser_required_env": _string_array_schema(),
                    "shared_required_env": _string_array_schema(),
                    "live_only_required_env": _string_array_schema(),
                    "browser_only_required_env": _string_array_schema(),
                },
            },
            "browser_trace_artifact_summary": {
                "type": "object",
                "required": [
                    "artifact_paths",
                    "trace_artifact_count",
                    "existing_count",
                    "missing_count",
                    "has_missing_trace_artifacts",
                ],
                "properties": {
                    "artifact_paths": _string_array_schema(),
                    "trace_artifact_count": {"type": "integer"},
                    "existing_count": {"type": "integer"},
                    "missing_count": {"type": "integer"},
                    "has_missing_trace_artifacts": {"type": "boolean"},
                    "trace_artifact_paths": _string_array_schema(),
                    "resolved_paths": _string_array_schema(),
                    "missing_paths": _string_array_schema(),
                    "checks": _string_array_schema(),
                    "trace_viewer_commands": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["path", "argv"],
                            "properties": {
                                "path": {"type": "string"},
                                "argv": _string_array_schema(),
                            },
                        },
                    },
                },
            },
            "browser_screenshot_artifact_summary": {
                "type": "object",
                "required": [
                    "artifact_paths",
                    "screenshot_artifact_count",
                    "existing_count",
                    "missing_count",
                    "has_missing_screenshot_artifacts",
                ],
                "properties": {
                    "artifact_paths": _string_array_schema(),
                    "screenshot_artifact_count": {"type": "integer"},
                    "existing_count": {"type": "integer"},
                    "missing_count": {"type": "integer"},
                    "has_missing_screenshot_artifacts": {"type": "boolean"},
                    "screenshot_artifact_paths": _string_array_schema(),
                    "resolved_paths": _string_array_schema(),
                    "missing_paths": _string_array_schema(),
                    "checks": _string_array_schema(),
                },
            },
        },
    }


def _gate_result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "name",
            "command",
            "cwd",
            "returncode",
            "elapsed_ms",
            "command_argv",
            "skipped",
            "attempts",
            "ok",
        ],
        "properties": {
            "name": {"type": "string"},
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "returncode": {"type": "integer"},
            "elapsed_ms": {"type": "number"},
            "command_argv": _string_array_schema(),
            "timeout_seconds": {"type": "number"},
            "skipped": {"type": "boolean"},
            "attempts": {"type": "integer", "minimum": 1},
            "artifacts": _string_array_schema(),
            "artifact_failures": _string_array_schema(),
            "artifact_reports": {"type": "array", "items": {"type": "object"}},
            "artifact_summary": {"type": "object"},
            "failures": _string_array_schema(),
            "ok": {"type": "boolean"},
        },
    }


def _string_array_schema() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}}


def _ready_launch_action_coverage_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "artifact_path": {"type": "string"},
            "evidence_source": {"type": "string"},
            "status": {"type": "string", "enum": ["match", "drift"]},
            "action_ids_match": {"type": "boolean"},
            "required_env_match": {"type": "boolean"},
            **{field: _string_array_schema() for field in READY_LAUNCH_COVERAGE_ARRAY_FIELDS},
        },
    }


def _launch_env_handoff_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "artifact_path": {"type": "string"},
            "evidence_source": {"type": "string"},
            "status": {"type": "string", "enum": ["blocked", "watch", "clear"]},
            "secret_policy": {"type": "string", "enum": ["placeholder_only_no_secret_values"]},
            "required_action_ids": _string_array_schema(),
            "optional_action_ids": _string_array_schema(),
            "required_env": _string_array_schema(),
            "optional_env": _string_array_schema(),
            "operator_copy_lines": _string_array_schema(),
            "required_env_count": {"type": "integer"},
            "optional_env_count": {"type": "integer"},
            "operator_copy_line_count": {"type": "integer"},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DSCI-DecentBio release checks.")
    parser.add_argument("--profile", choices=("local", "production"), default="local")
    parser.add_argument("--env-file", action="append", default=[], help="Env file for env_doctor. Can be repeated.")
    parser.add_argument("--ignore-process-env", action="store_true", help="Pass through to env_doctor.")
    parser.add_argument("--env-evidence-dir", default="../../var", help="Directory for env_doctor JSON evidence.")
    parser.add_argument(
        "--python-command",
        default=AUTO_PYTHON_COMMAND,
        help='Python runner for child Python scripts. Defaults to "auto" (uv run python when available); use "system" for sys.executable.',
    )
    parser.add_argument("--backend-tests", nargs="*", default=list(DEFAULT_BACKEND_TESTS))
    parser.add_argument("--skip-env", action="store_true")
    parser.add_argument("--skip-compose", action="store_true")
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-contracts", action="store_true")
    parser.add_argument(
        "--preflight-step-timeout",
        type=float,
        default=DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS,
        help=(
            "Maximum seconds for env-doctor, deploy-readiness, and compose-config release-gate steps. "
            "Use 0 to disable the parent timeout."
        ),
    )
    parser.add_argument(
        "--backend-test-timeout",
        type=float,
        default=DEFAULT_BACKEND_TEST_TIMEOUT_SECONDS,
        help=(
            "Maximum seconds for the backend pytest release-gate step. "
            "Use 0 to disable the parent timeout."
        ),
    )
    parser.add_argument(
        "--contract-step-timeout",
        type=float,
        default=DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS,
        help=(
            "Maximum seconds for contract build/test/deploy release-gate steps. "
            "Use 0 to disable the parent timeout."
        ),
    )
    parser.add_argument(
        "--runtime-smoke",
        action="store_true",
        help="Run product/browser runtime smoke checks against already-running services.",
    )
    parser.add_argument("--runtime-api", default="http://127.0.0.1:8000", help="API URL for --runtime-smoke.")
    parser.add_argument(
        "--runtime-frontend",
        default="http://127.0.0.1:5173",
        help="Frontend URL for --runtime-smoke.",
    )
    parser.add_argument(
        "--runtime-smoke-strict-ready",
        action="store_true",
        help="Fail product smoke when launch readiness is blocked.",
    )
    parser.add_argument(
        "--runtime-smoke-strict-action-coverage",
        action="store_true",
        help=(
            "Fail after runtime smoke when validated live /launch action coverage differs from "
            "browser dashboard launch-control coverage."
        ),
    )
    parser.add_argument(
        "--runtime-smoke-step",
        action="append",
        choices=("product", "browser"),
        default=[],
        help="Limit --runtime-smoke to one child step. Repeat for both; defaults to product and browser.",
    )
    parser.add_argument(
        "--runtime-browser-expect-dev-auth",
        action="store_true",
        help="Pass --expect-dev-auth to runtime browser smoke for local dev-auth frontend runs.",
    )
    parser.add_argument(
        "--runtime-browser-trace-on-failure-dir",
        help="Pass --trace-on-failure-dir to runtime browser smoke and surface trace evidence in parent JSON.",
    )
    parser.add_argument(
        "--runtime-browser-screenshot-dir",
        help="Pass --screenshot-dir to runtime browser smoke and surface successful PNG evidence in parent JSON.",
    )
    parser.add_argument(
        "--runtime-browser-only-check",
        action="append",
        default=[],
        help="Pass --only-check to runtime browser smoke. Can be provided multiple times for targeted trace diagnostics.",
    )
    parser.add_argument(
        "--runtime-browser-timeout",
        type=float,
        help="Pass --timeout seconds to runtime browser smoke for targeted diagnostics.",
    )
    parser.add_argument(
        "--runtime-evidence-dir",
        default="../../var",
        help="Directory for runtime smoke JSON evidence when --runtime-smoke is enabled.",
    )
    parser.add_argument(
        "--runtime-smoke-timeout",
        type=float,
        default=DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS,
        help=(
            "Maximum seconds for product-smoke and browser-smoke release-gate steps. "
            "Use 0 to disable the parent timeout."
        ),
    )
    parser.add_argument(
        "--external-readiness",
        action="store_true",
        help="Run offline Railway/Vercel/Amoy/GitHub deployment preflight before local release checks.",
    )
    parser.add_argument(
        "--external-evidence-dir",
        default="../../var",
        help="Directory for external readiness JSON evidence when --external-readiness is enabled.",
    )
    parser.add_argument(
        "--external-target",
        action="append",
        choices=("railway", "vercel", "amoy", "github", "all"),
        default=[],
        help="Deployment target for --external-readiness. Repeatable; defaults to all.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Run all steps before returning failure.")
    parser.add_argument(
        "--release-approval-handoff",
        help=(
            "Optional Markdown handoff artifact from release_approval_check.py --markdown-out. "
            "When provided, the parent JSON report records existence, section coverage, and unsafe marker checks."
        ),
    )
    parser.add_argument(
        "--frontend-step-timeout",
        type=float,
        default=DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS,
        help=(
            "Maximum seconds for frontend lint/typecheck/build/bundle release-gate steps. "
            "Use 0 to disable the parent timeout."
        ),
    )
    parser.add_argument(
        "--frontend-test-timeout",
        type=float,
        default=DEFAULT_FRONTEND_TEST_TIMEOUT_SECONDS,
        help=(
            "Maximum seconds for the frontend Vitest release-gate step. "
            "Use 0 to disable the parent timeout."
        ),
    )
    parser.add_argument(
        "--print-report-schema",
        action="store_true",
        help="Print the release-gate parent JSON report schema and exit without running checks.",
    )
    parser.add_argument("--json-out", help="Write a JSON report.")
    args = parser.parse_args()
    if args.backend_test_timeout <= 0:
        args.backend_test_timeout = None
    if args.contract_step_timeout <= 0:
        args.contract_step_timeout = None
    if args.preflight_step_timeout <= 0:
        args.preflight_step_timeout = None
    if args.runtime_smoke_timeout <= 0:
        args.runtime_smoke_timeout = None
    if args.frontend_step_timeout <= 0:
        args.frontend_step_timeout = None
    if args.frontend_test_timeout <= 0:
        args.frontend_test_timeout = None

    if args.print_report_schema:
        print(json.dumps(json_report_schema(), indent=2, sort_keys=True), flush=True)
        return 0

    results: list[GateResult] = []
    for step in build_steps(args):
        result = run_step(step, dry_run=args.dry_run)
        results.append(result)
        if not result.ok and not args.continue_on_failure:
            break

    if args.release_approval_handoff:
        handoff_result = release_approval_handoff_result(args.release_approval_handoff)
        results.append(handoff_result)
        if not handoff_result.ok:
            for failure in handoff_result.failures or []:
                print(f"[release-gate] HANDOFF {handoff_result.name}: {failure}", flush=True)

    if args.runtime_smoke_strict_action_coverage and not args.dry_run and all(result.ok for result in results):
        strict_result = strict_launch_action_coverage_result(json_report_payload(results))
        if strict_result is not None:
            for failure in strict_result.failures or []:
                print(f"[release-gate] STRICT {strict_result.name}: {failure}", flush=True)
            results.append(strict_result)

    if args.json_out:
        write_json_report(
            Path(args.json_out),
            results,
            python_command=_python_command_report(args.python_command),
            release_approval_handoff_path=args.release_approval_handoff,
        )

    failed = [result for result in results if not result.ok]
    if failed:
        print(f"\n[release-gate] FAILED at {failed[0].name}", flush=True)
        return failed[0].returncode or 1

    print(f"\n[release-gate] OK ({len(results)} step(s))", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
