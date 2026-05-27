#!/usr/bin/env python3
"""
Codex MCP health checker.

Checks the user-level Codex MCP configuration, CLI visibility, and optional
live MCP tool calls through `codex exec`. The script avoids printing secrets
and is intended for scheduled or ad-hoc workstation checks.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None  # type: ignore[assignment]


DEFAULT_EXPECTED_SERVERS = ("figma", "playwright", "notion")
DEFAULT_LIVE_TIMEOUT_SECONDS = 300


@dataclass
class CommandResult:
    name: str
    command: list[str]
    returncode: int
    ok: bool
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass
class LiveCheck:
    name: str
    ok: bool
    status_line: str
    returncode: int
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass
class HealthReport:
    checked_at: str
    workspace_root: str
    codex_home: str
    config_path: str
    expected_servers: list[str]
    configured_servers: list[str]
    missing_servers: list[str]
    cli_checks: list[CommandResult] = field(default_factory=list)
    live_checks: list[LiveCheck] = field(default_factory=list)
    ok: bool = False


def tail(text: str, max_lines: int = 40) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[-max_lines:])


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    if tomllib is None:
        raise RuntimeError("Python 3.11+ is required to parse config.toml")
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def configured_mcp_servers(config: dict[str, Any]) -> list[str]:
    servers = config.get("mcp_servers")
    if not isinstance(servers, dict):
        return []
    return sorted(str(name) for name in servers)


def codex_command(*args: str) -> list[str]:
    if platform.system().lower() == "windows":
        return ["cmd", "/c", "codex", *args]
    return ["codex", *args]


def run_command(name: str, command: list[str], timeout_seconds: int) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            name=name,
            command=command,
            returncode=124,
            ok=False,
            stdout_tail=tail(exc.stdout or ""),
            stderr_tail=tail(exc.stderr or f"Timed out after {timeout_seconds}s."),
        )
    except OSError as exc:
        return CommandResult(
            name=name,
            command=command,
            returncode=127,
            ok=False,
            stderr_tail=str(exc),
        )

    return CommandResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        ok=completed.returncode == 0,
        stdout_tail=tail(completed.stdout),
        stderr_tail=tail(completed.stderr),
    )


def run_codex_exec(
    *,
    name: str,
    workspace_root: Path,
    prompt: str,
    timeout_seconds: int,
    extra_config: list[str] | None = None,
) -> LiveCheck:
    with tempfile.NamedTemporaryFile(prefix=f"codex-{name}-", suffix=".txt", delete=False) as handle:
        output_path = Path(handle.name)

    command = codex_command(
        "exec",
        "--cd",
        str(workspace_root),
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
    )
    for item in extra_config or []:
        command.extend(["-c", item])
    command.extend(["--output-last-message", str(output_path), "-"])

    try:
        completed = subprocess.run(
            command,
            input=prompt,
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return LiveCheck(
            name=name,
            ok=False,
            status_line=f"{name.upper()}_FAIL: timed out after {timeout_seconds}s",
            returncode=124,
            stdout_tail=tail(exc.stdout or ""),
            stderr_tail=tail(exc.stderr or ""),
        )
    except OSError as exc:
        return LiveCheck(
            name=name,
            ok=False,
            status_line=f"{name.upper()}_FAIL: {exc}",
            returncode=127,
        )

    status_line = ""
    if output_path.exists():
        status_line = output_path.read_text(encoding="utf-8", errors="replace").strip()
        try:
            output_path.unlink()
        except OSError:
            pass
    if not status_line:
        status_line = tail(completed.stdout).strip().splitlines()[-1] if completed.stdout.strip() else ""

    ok = completed.returncode == 0 and "_OK" in status_line and "_FAIL" not in status_line
    return LiveCheck(
        name=name,
        ok=ok,
        status_line=status_line or f"{name.upper()}_FAIL: no status line returned",
        returncode=completed.returncode,
        stdout_tail=tail(completed.stdout),
        stderr_tail=tail(completed.stderr),
    )


def live_prompts() -> list[tuple[str, str, list[str] | None]]:
    return [
        (
            "notion_raw",
            "MCP health check only. Do not edit files or run shell commands. "
            "Use only the configured MCP server named notion if available, not the Notion plugin/app connector. "
            "Make the smallest harmless read-only call if possible. "
            "Return exactly one line: NOTION_RAW_OK or NOTION_RAW_FAIL: reason.\n",
            ["plugins.'notion@openai-curated'.enabled=false"],
        ),
        (
            "notion_app",
            "MCP health check only. Do not edit files or run shell commands. "
            "Use the Notion plugin/app search tool if visible. "
            "Make one smallest harmless workspace_search query with page_size 1. "
            "Return exactly one line: NOTION_APP_OK or NOTION_APP_FAIL: reason.\n",
            None,
        ),
        (
            "figma",
            "MCP health check only. Do not edit files or run shell commands. "
            "Use the Figma MCP whoami tool if visible. "
            "Return exactly one line: FIGMA_OK or FIGMA_FAIL: reason.\n",
            None,
        ),
        (
            "playwright",
            "MCP health check only. Do not edit files or run shell commands. "
            "Use the Playwright MCP browser_tabs or equivalent read-only tab listing if visible. "
            "Return exactly one line: PLAYWRIGHT_OK or PLAYWRIGHT_FAIL: reason.\n",
            None,
        ),
    ]


def build_report(args: argparse.Namespace) -> HealthReport:
    workspace_root = Path(args.workspace_root).resolve()
    home = codex_home()
    config_path = Path(args.config_path).expanduser() if args.config_path else home / "config.toml"
    expected = [server.strip() for server in args.expected_servers.split(",") if server.strip()]
    config = load_config(config_path)
    configured = configured_mcp_servers(config)
    missing = [server for server in expected if server not in configured]

    report = HealthReport(
        checked_at=datetime.now(UTC).isoformat(),
        workspace_root=str(workspace_root),
        codex_home=str(home),
        config_path=str(config_path),
        expected_servers=expected,
        configured_servers=configured,
        missing_servers=missing,
    )

    report.cli_checks.append(
        run_command("codex_mcp_list", codex_command("mcp", "list"), args.command_timeout)
    )
    for server in expected:
        report.cli_checks.append(
            run_command(f"codex_mcp_get_{server}", codex_command("mcp", "get", server), args.command_timeout)
        )

    if not args.skip_live:
        for name, prompt, extra_config in live_prompts():
            report.live_checks.append(
                run_codex_exec(
                    name=name,
                    workspace_root=workspace_root,
                    prompt=prompt,
                    timeout_seconds=args.live_timeout,
                    extra_config=extra_config,
                )
            )

    cli_ok = all(check.ok for check in report.cli_checks)
    live_ok = all(check.ok for check in report.live_checks) if report.live_checks else True
    report.ok = not report.missing_servers and cli_ok and live_ok
    return report


def write_json_report(report: HealthReport, output_path: Path | None) -> None:
    if output_path is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def print_summary(report: HealthReport) -> None:
    status = "PASS" if report.ok else "FAIL"
    print(f"MCP health: {status}")
    print(f"config: {report.config_path}")
    print(f"configured: {', '.join(report.configured_servers) or '-'}")
    if report.missing_servers:
        print(f"missing: {', '.join(report.missing_servers)}")
    for check in report.cli_checks:
        print(f"cli:{check.name}: {'PASS' if check.ok else 'FAIL'} ({check.returncode})")
    for check in report.live_checks:
        print(f"live:{check.name}: {'PASS' if check.ok else 'FAIL'} - {check.status_line}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Codex MCP configuration and live tool health.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root passed to codex exec.")
    parser.add_argument("--config-path", default="", help="Override Codex config.toml path.")
    parser.add_argument(
        "--expected-servers",
        default=",".join(DEFAULT_EXPECTED_SERVERS),
        help="Comma-separated MCP servers expected in config.toml.",
    )
    parser.add_argument("--json-out", default="", help="Optional JSON report path.")
    parser.add_argument("--skip-live", action="store_true", help="Only check config and codex mcp CLI output.")
    parser.add_argument("--command-timeout", type=int, default=60, help="Timeout for codex mcp CLI commands.")
    parser.add_argument(
        "--live-timeout",
        type=int,
        default=DEFAULT_LIVE_TIMEOUT_SECONDS,
        help="Timeout for each codex exec live MCP check.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = build_report(args)
    output_path = Path(args.json_out) if args.json_out else None
    write_json_report(report, output_path)
    print_summary(report)
    if output_path:
        print(f"json: {output_path}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
