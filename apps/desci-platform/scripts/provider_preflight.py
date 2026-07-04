#!/usr/bin/env python3
"""Run secret-free provider CLI preflight checks for DeSci launch."""

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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_handoff
from evidence_io import write_json_atomic

PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_PROVIDERS = ("railway", "vercel", "github")
SECRET_PATTERNS = (
    re.compile(r"sk_(?:live|test)_[A-Za-z0-9_/-]+"),
    re.compile(r"whsec_[A-Za-z0-9_/-]+"),
    re.compile(r"github_pat_[A-Za-z0-9_/-]+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_/-]+"),
    re.compile(r"AIza[0-9A-Za-z_-]+"),
    re.compile(r"(?i)(token|secret|password|private[_-]?key)\s*[:=]\s*\S+"),
)
AUTH_CONTEXT_PATTERNS = (
    re.compile(r"(?i)\bunauthorized\b"),
    re.compile(r"(?i)\bnot\s+(?:logged\s+in|authenticated)\b"),
    re.compile(r"(?i)\bplease\s+(?:log\s*in|login)\b"),
    re.compile(r"(?i)\blogin\s+required\b"),
)


@dataclass(frozen=True)
class CommandSpec:
    provider: str
    id: str
    command: tuple[str, ...]
    required: bool
    docs_url: str


@dataclass(frozen=True)
class CommandExecution:
    exit_code: int | None
    duration_ms: int
    stdout: str = ""
    stderr: str = ""
    command_found: bool = True
    auth_context_missing: bool = False
    project_context_missing: bool = False
    timed_out: bool = False
    error: str = ""


CommandRunner = Callable[[CommandSpec, int], CommandExecution]


def command_specs_for_provider(provider: str) -> list[CommandSpec]:
    provider_key = provider.strip().lower()
    guidance = release_handoff.provider_apply_guidance(provider_key)
    docs_url = guidance.get("docs_url") if isinstance(guidance.get("docs_url"), str) else ""
    specs: list[CommandSpec] = []
    for index, command_text in enumerate(release_handoff._string_list(guidance.get("preflight_commands"))):
        command = tuple(shlex.split(command_text))
        if not command:
            continue
        specs.append(
            CommandSpec(
                provider=provider_key,
                id=f"{provider_key}_preflight_{index + 1}",
                command=command,
                required=True,
                docs_url=docs_url,
            )
        )
    return specs


def _command_text(command: tuple[str, ...]) -> str:
    return " ".join(command)


def _sanitize_output(value: str, *, max_chars: int = 500) -> str:
    sanitized = value[:max_chars]
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def _looks_like_auth_context_missing(execution: CommandExecution) -> bool:
    if execution.auth_context_missing:
        return True
    if execution.exit_code in {None, 0} or not execution.command_found or execution.timed_out:
        return False
    combined_output = "\n".join(
        value for value in (execution.stdout, execution.stderr, execution.error) if value
    )
    return any(pattern.search(combined_output) for pattern in AUTH_CONTEXT_PATTERNS)


def _failure_remediation(spec: CommandSpec, failure_reason: str) -> str:
    executable = spec.command[0] if spec.command else spec.provider
    provider = spec.provider
    command_text = _command_text(spec.command)

    if failure_reason == "missing_cli":
        return f"Install the {executable} CLI, confirm it is on PATH, then rerun `{command_text}`."
    if failure_reason == "auth_context_missing":
        if provider == "railway":
            return (
                "Run `railway login`, link the intended backend project if needed, then rerun provider preflight "
                "before applying Railway variables."
            )
        if provider == "vercel":
            return (
                "Set `VERCEL_TOKEN` or run `vercel login`, confirm the intended Vercel project is linked, then "
                "rerun provider preflight before applying production env values."
            )
        if provider == "github":
            return (
                "Run `gh auth login` with repository secret access, then rerun provider preflight before setting "
                "GitHub Actions secrets."
            )
        return f"Authenticate the {provider} CLI context, then rerun `{command_text}`."
    if failure_reason == "timeout":
        return f"Run `{command_text}` manually to resolve the timeout, then rerun provider preflight."
    if failure_reason == "project_context_missing":
        if provider == "vercel":
            return (
                "Run `vercel link --yes --project <name-or-id> --scope <team>` or set "
                "VERCEL_ORG_ID and VERCEL_PROJECT_ID before rerunning provider preflight."
            )
        return f"Link the {provider} project context, then rerun `{command_text}`."
    if failure_reason == "nonzero_exit":
        return (
            f"Resolve the provider CLI error for `{command_text}`. If the command requires a selected project or "
            "workspace, relink the local checkout before rerunning provider preflight."
        )
    return f"Resolve `{command_text}` and rerun provider preflight."


def _with_vercel_project_context_remediation(remediation: str) -> str:
    if "vercel link" in remediation or "VERCEL_ORG_ID" in remediation:
        return remediation
    return (
        f"{remediation} Also run `vercel link --yes --project <name-or-id> --scope <team>` "
        "or set VERCEL_ORG_ID and VERCEL_PROJECT_ID if this checkout is not linked."
    )


def _resolve_executable(executable: str) -> str | None:
    resolved = shutil.which(executable)
    if resolved is None:
        return None
    if os.name == "nt" and not Path(resolved).suffix:
        cmd_resolved = shutil.which(f"{executable}.cmd")
        if cmd_resolved is not None:
            return cmd_resolved
    return resolved


def _has_vercel_auth_context() -> bool:
    if os.environ.get("VERCEL_TOKEN"):
        return True
    return (Path.home() / ".vercel" / "auth.json").exists()


def _has_vercel_project_context(project_root: Path = PROJECT_ROOT) -> bool:
    if os.environ.get("VERCEL_ORG_ID") and os.environ.get("VERCEL_PROJECT_ID"):
        return True
    return _vercel_project_json_has_ids(project_root / ".vercel" / "project.json")


def _vercel_project_json_has_ids(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("orgId") and payload.get("projectId"))


def _vercel_command_needs_project_context(spec: CommandSpec) -> bool:
    return len(spec.command) >= 2 and spec.command[1] in {"env", "deploy", "build", "pull", "open"}


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=5,
            )
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    process.kill()


def execute_command(spec: CommandSpec, timeout_seconds: int) -> CommandExecution:
    started = time.monotonic()
    executable = spec.command[0]
    resolved_executable = _resolve_executable(executable)
    if resolved_executable is None:
        return CommandExecution(
            exit_code=None,
            duration_ms=0,
            command_found=False,
            error=f"{executable} executable was not found on PATH",
        )
    if spec.provider == "vercel" and not _has_vercel_auth_context():
        return CommandExecution(
            exit_code=None,
            duration_ms=0,
            auth_context_missing=True,
            project_context_missing=not _has_vercel_project_context(),
            error=(
                "vercel auth context is not configured; set VERCEL_TOKEN or run vercel login"
            ),
        )
    if spec.provider == "vercel" and _vercel_command_needs_project_context(spec) and not _has_vercel_project_context():
        return CommandExecution(
            exit_code=None,
            duration_ms=0,
            project_context_missing=True,
            error=(
                "vercel project context is not configured; run vercel link or set "
                "VERCEL_ORG_ID and VERCEL_PROJECT_ID"
            ),
        )

    env = os.environ.copy()
    env.setdefault("CI", "1")
    env.setdefault("NO_COLOR", "1")
    try:
        process = subprocess.Popen(
            [resolved_executable, *spec.command[1:]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandExecution(
            exit_code=None,
            duration_ms=int((time.monotonic() - started) * 1000),
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=True,
            error=f"command timed out after {timeout_seconds}s",
        )
    except FileNotFoundError:
        return CommandExecution(
            exit_code=None,
            duration_ms=int((time.monotonic() - started) * 1000),
            command_found=False,
            error=f"{executable} executable was not found on PATH",
        )
    except OSError as exc:
        return CommandExecution(
            exit_code=None,
            duration_ms=int((time.monotonic() - started) * 1000),
            error=str(exc),
        )

    return CommandExecution(
        exit_code=process.returncode,
        duration_ms=int((time.monotonic() - started) * 1000),
        stdout=stdout or "",
        stderr=stderr or "",
    )


def check_payload(
    spec: CommandSpec,
    execution: CommandExecution,
    *,
    include_output_preview: bool = False,
) -> dict[str, Any]:
    ok = execution.command_found and not execution.timed_out and execution.exit_code == 0
    payload: dict[str, Any] = {
        "id": spec.id,
        "provider": spec.provider,
        "command": _command_text(spec.command),
        "required": spec.required,
        "ok": ok,
        "exit_code": execution.exit_code,
        "duration_ms": execution.duration_ms,
        "docs_url": spec.docs_url,
    }
    if not execution.command_found:
        payload["failure_reason"] = "missing_cli"
    elif _looks_like_auth_context_missing(execution):
        payload["failure_reason"] = "auth_context_missing"
    elif execution.project_context_missing:
        payload["failure_reason"] = "project_context_missing"
    elif execution.timed_out:
        payload["failure_reason"] = "timeout"
    elif execution.exit_code != 0:
        payload["failure_reason"] = "nonzero_exit"
    failure_reason = payload.get("failure_reason")
    if isinstance(failure_reason, str) and failure_reason:
        payload["remediation"] = _failure_remediation(spec, failure_reason)
        if execution.project_context_missing and spec.provider == "vercel":
            payload["remediation"] = _with_vercel_project_context_remediation(payload["remediation"])
    if execution.project_context_missing:
        payload["project_context_missing"] = True
    if execution.error:
        payload["error"] = _sanitize_output(execution.error)
    if include_output_preview:
        if execution.stdout:
            payload["stdout_preview"] = _sanitize_output(execution.stdout)
        if execution.stderr:
            payload["stderr_preview"] = _sanitize_output(execution.stderr)
    return payload


def run_preflight(
    providers: list[str] | tuple[str, ...] = DEFAULT_PROVIDERS,
    *,
    timeout_seconds: int = 15,
    include_output_preview: bool = False,
    runner: CommandRunner = execute_command,
) -> dict[str, Any]:
    provider_reports: list[dict[str, Any]] = []
    for provider in providers:
        specs = command_specs_for_provider(provider)
        checks = [
            check_payload(
                spec,
                runner(spec, timeout_seconds),
                include_output_preview=include_output_preview,
            )
            for spec in specs
        ]
        required_checks = [check for check in checks if check["required"]]
        provider_reports.append(
            {
                "provider": provider,
                "label": release_handoff.PROVIDER_LABELS.get(provider, provider),
                "ok": all(check["ok"] for check in required_checks),
                "docs_url": specs[0].docs_url if specs else "",
                "checks": checks,
            }
        )

    checks_flat = [check for provider in provider_reports for check in provider["checks"]]
    failed_checks = [check for check in checks_flat if not check["ok"]]
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failed_checks,
        "summary": {
            "provider_count": len(provider_reports),
            "ready_provider_count": sum(1 for provider in provider_reports if provider["ok"]),
            "check_count": len(checks_flat),
            "passed_check_count": sum(1 for check in checks_flat if check["ok"]),
            "failed_check_count": len(failed_checks),
            "missing_cli_count": sum(1 for check in failed_checks if check.get("failure_reason") == "missing_cli"),
            "auth_context_missing_count": sum(
                1 for check in failed_checks if check.get("failure_reason") == "auth_context_missing"
            ),
            "project_context_missing_count": sum(
                1 for check in failed_checks if check.get("project_context_missing") is True
            ),
        },
        "providers": provider_reports,
        "failed_checks": [
            {
                "provider": check["provider"],
                "id": check["id"],
                "command": check["command"],
                "failure_reason": check.get("failure_reason", "unknown"),
                "remediation": check.get("remediation", "") if isinstance(check.get("remediation"), str) else "",
                "docs_url": check.get("docs_url", "") if isinstance(check.get("docs_url"), str) else "",
                "project_context_missing": check.get("project_context_missing") is True,
            }
            for check in failed_checks
        ],
    }
    return payload


def write_json_report(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_json_atomic(path, payload, trailing_newline=True)


def render_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# DeSci Provider Preflight",
        "",
        "## Summary",
        "",
        f"- Status: `{_markdown_bool(payload.get('ok') is True)}`",
        f"- Generated at: `{_markdown_code(payload.get('generated_at'))}`",
        f"- Providers ready: `{_markdown_count(summary.get('ready_provider_count'))}/{_markdown_count(summary.get('provider_count'))}`",
        f"- Checks passed: `{_markdown_count(summary.get('passed_check_count'))}/{_markdown_count(summary.get('check_count'))}`",
        f"- Failed checks: `{_markdown_count(summary.get('failed_check_count'))}`",
        f"- Missing CLI: `{_markdown_count(summary.get('missing_cli_count'))}`",
        f"- Auth context missing: `{_markdown_count(summary.get('auth_context_missing_count'))}`",
        f"- Project context missing: `{_markdown_count(summary.get('project_context_missing_count'))}`",
        "",
        "## Providers",
        "",
    ]
    providers = payload.get("providers") if isinstance(payload.get("providers"), list) else []
    if not providers:
        lines.append("- `none`")
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        status = "OK" if provider.get("ok") is True else "FAIL"
        failed = sum(
            1
            for check in provider.get("checks", [])
            if isinstance(check, dict) and check.get("ok") is not True
        )
        lines.append(
            f"- `{_markdown_code(provider.get('provider'))}`: `{status}` "
            f"failed=`{failed}` docs={_markdown_link_or_none(provider.get('docs_url'))}"
        )
    lines.extend(["", "## Failed Checks", ""])
    failed_checks = payload.get("failed_checks") if isinstance(payload.get("failed_checks"), list) else []
    if not failed_checks:
        lines.append("- `none`")
    for check in failed_checks:
        if not isinstance(check, dict):
            continue
        provider = _markdown_code(check.get("provider") or "provider")
        command = _markdown_code(check.get("command") or "manual provider check")
        reason = _markdown_code(check.get("failure_reason") or "unknown")
        project_context = " project_context=`missing`" if check.get("project_context_missing") is True else ""
        lines.append(f"- `{provider}` `{command}`: `{reason}`{project_context}")
        docs_url = _markdown_text(check.get("docs_url"))
        remediation = _markdown_text(check.get("remediation"))
        if docs_url:
            lines.append(f"  Docs: {docs_url}")
        if remediation:
            lines.append(f"  Next: {remediation}")
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(path: str | Path, payload: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    temp_path.write_text(render_markdown_report(payload), encoding="utf-8")
    temp_path.replace(output_path)
    return output_path


def _markdown_bool(value: bool) -> str:
    return "true" if value else "false"


def _markdown_count(value: Any) -> str:
    if isinstance(value, bool):
        return "0"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "0"
    return str(max(number, 0))


def _markdown_code(value: Any) -> str:
    return _markdown_text(value).replace("`", "'")


def _markdown_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _markdown_link_or_none(value: Any) -> str:
    text = _markdown_text(value)
    return text or "`none`"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run secret-free DeSci provider CLI preflight checks.")
    parser.add_argument(
        "--provider",
        action="append",
        choices=DEFAULT_PROVIDERS,
        help="Provider to check. Can be repeated. Defaults to railway, vercel, and github.",
    )
    parser.add_argument("--timeout", type=int, default=15, help="Timeout per CLI command in seconds.")
    parser.add_argument("--json-out", help="Optional JSON evidence output path.")
    parser.add_argument("--markdown-out", help="Optional Markdown evidence output path.")
    parser.add_argument(
        "--include-output-preview",
        action="store_true",
        help="Include sanitized stdout/stderr previews. Secret-like substrings are redacted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_preflight(
        tuple(args.provider or DEFAULT_PROVIDERS),
        timeout_seconds=args.timeout,
        include_output_preview=args.include_output_preview,
    )
    for provider in payload["providers"]:
        status = "OK" if provider["ok"] else "FAIL"
        print(f"[provider-preflight] {provider['provider']:<8} {status}")
        for check in provider["checks"]:
            check_status = "OK" if check["ok"] else "FAIL"
            reason = f" {check.get('failure_reason')}" if not check["ok"] else ""
            docs_url = check.get("docs_url") if isinstance(check.get("docs_url"), str) else ""
            docs = f" docs={docs_url}" if not check["ok"] and docs_url else ""
            remediation = check.get("remediation") if isinstance(check.get("remediation"), str) else ""
            next_action = f" next={remediation}" if not check["ok"] and remediation else ""
            print(f"  - {check['command']}: {check_status}{reason}{docs}{next_action}")
    if args.json_out:
        write_json_report(args.json_out, payload)
        print(f"[provider-preflight] json written: {args.json_out}")
    if args.markdown_out:
        write_markdown_report(args.markdown_out, payload)
        print(f"[provider-preflight] markdown written: {args.markdown_out}")
    print(f"[provider-preflight] ok={payload['ok']}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
