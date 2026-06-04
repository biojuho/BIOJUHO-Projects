from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_TIMEOUT_SECONDS = 120.0
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from external_credential_boundary_audit import DEFAULT_REGISTRY, audit_registry, load_registry  # noqa: E402


def build_plan(
    registry_path: Path = DEFAULT_REGISTRY,
    *,
    env: Mapping[str, str] | None = None,
    boundary_ids: list[str] | None = None,
    ready_only: bool = False,
    workspace_root: Path = WORKSPACE_ROOT,
) -> dict[str, Any]:
    env_map = env if env is not None else os.environ
    registry = load_registry(registry_path)
    audit = audit_registry(registry, workspace_root=workspace_root, env=env_map)
    if audit["status"] != "pass":
        raise ValueError("\n".join(audit["errors"]))

    selected = _select_boundaries(audit["boundaries"], boundary_ids)
    plan_order = "explicit" if boundary_ids else "unblock_queue"
    if not boundary_ids:
        selected = sorted(selected, key=_unblock_sort_key)
    boundaries = [_planned_boundary(boundary, plan_rank=index + 1) for index, boundary in enumerate(selected)]
    if ready_only:
        boundaries = [boundary for boundary in boundaries if boundary["live_status"] == "ready_for_execution"]
    status_counts = Counter(boundary["live_status"] for boundary in boundaries)
    command_count = sum(len(boundary["verification_commands"]) for boundary in boundaries)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "registry_path": _repo_relative(registry_path, workspace_root),
        "mode": "dry_run",
        "selection": "ready_only" if ready_only else "selected",
        "plan_order": plan_order,
        "status": "pass",
        "summary": {
            "selected_boundaries": len(boundaries),
            "ready_boundaries": status_counts.get("ready_for_execution", 0),
            "blocked_boundaries": _blocked_boundary_count(status_counts),
            "commands_planned": command_count,
            "commands_executed": 0,
            "commands_passed": 0,
            "commands_failed": 0,
            "commands_skipped": command_count,
        },
        "boundaries": boundaries,
        "commands": [
            _planned_command(boundary, command)
            for boundary in boundaries
            for command in boundary["verification_commands"]
        ],
        "errors": [],
    }


def execute_plan(
    plan: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    workspace_root: Path = WORKSPACE_ROOT,
) -> dict[str, Any]:
    env_map = dict(env if env is not None else os.environ)
    env_names = sorted(
        {
            name
            for boundary in plan["boundaries"]
            for name in [*boundary["required_env"], *boundary["optional_env_any_of"]]
        }
    )
    commands: list[dict[str, Any]] = []
    for boundary in plan["boundaries"]:
        for command in boundary["verification_commands"]:
            if boundary["live_status"] != "ready_for_execution":
                commands.append(
                    {
                        **_planned_command(boundary, command),
                        "status": "skipped",
                        "skip_reason": _skip_reason(boundary),
                    }
                )
                continue
            commands.append(
                _execute_command(
                    boundary,
                    command,
                    env_map=env_map,
                    env_names=env_names,
                    timeout_seconds=timeout_seconds,
                    workspace_root=workspace_root,
                )
            )

    failed = [item for item in commands if item["status"] == "fail"]
    skipped = [item for item in commands if item["status"] == "skipped"]
    passed = [item for item in commands if item["status"] == "pass"]
    report = {
        **plan,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "execute",
        "status": "pass" if not failed and not skipped else "fail",
        "commands": commands,
        "summary": {
            **plan["summary"],
            "commands_executed": len(passed) + len(failed),
            "commands_passed": len(passed),
            "commands_failed": len(failed),
            "commands_skipped": len(skipped),
        },
        "errors": [
            *[f"{item['boundary_id']}: {item['command']} failed with {item['returncode']}" for item in failed],
            *[f"{item['boundary_id']}: skipped because {item['skip_reason']}" for item in skipped],
        ],
    }
    return report


def run(
    registry_path: Path = DEFAULT_REGISTRY,
    *,
    execute: bool = False,
    boundary_ids: list[str] | None = None,
    ready_only: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    env: Mapping[str, str] | None = None,
    workspace_root: Path = WORKSPACE_ROOT,
) -> dict[str, Any]:
    plan = build_plan(
        registry_path,
        env=env,
        boundary_ids=boundary_ids,
        ready_only=ready_only,
        workspace_root=workspace_root,
    )
    report = (
        execute_plan(plan, env=env, timeout_seconds=timeout_seconds, workspace_root=workspace_root)
        if execute
        else plan
    )
    if json_out is not None:
        _write_json_atomic(json_out, report)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, render_markdown(report))
    if report["status"] != "pass":
        raise ValueError("\n".join(report["errors"]))
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# External Credential Live Verifier",
        "",
        f"- Status: `{report['status']}`",
        f"- Mode: `{report['mode']}`",
        f"- Selection: `{report.get('selection', 'selected')}`",
        f"- Plan order: `{report.get('plan_order', 'explicit')}`",
        f"- Selected boundaries: `{summary['selected_boundaries']}`",
        f"- Ready boundaries: `{summary['ready_boundaries']}`",
        f"- Blocked boundaries: `{summary['blocked_boundaries']}`",
        f"- Commands planned: `{summary['commands_planned']}`",
        f"- Commands executed: `{summary['commands_executed']}`",
        "",
        "## Boundaries",
        "",
        "| Rank | Boundary | Live status | Missing required env | Commands |",
        "| ---: | --- | --- | ---: | ---: |",
    ]
    for boundary in report["boundaries"]:
        lines.append(
            " | ".join(
                [
                    f"| `{boundary['plan_rank']}`",
                    f"`{boundary['id']}`",
                    f"`{boundary['live_status']}`",
                    f"`{len(boundary['missing_required_env'])}`",
                    f"`{len(boundary['verification_commands'])}` |",
                ]
            )
        )
    lines.extend(["", "## Commands", ""])
    for command in report["commands"]:
        lines.extend(
            [
                f"### {command['boundary_id']}",
                "",
                f"- Status: `{command['status']}`",
                f"- Command: `{command['command']}`",
            ]
        )
        if command.get("returncode") is not None:
            lines.append(f"- Return code: `{command['returncode']}`")
        if command.get("skip_reason"):
            lines.append(f"- Skip reason: {command['skip_reason']}")
        lines.append("")
    lines.extend(["## Errors", ""])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run external credential live verification commands.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--boundary", action="append", dest="boundary_ids")
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="select only boundaries that are currently ready for execution",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(
            args.registry,
            execute=args.execute,
            boundary_ids=args.boundary_ids,
            ready_only=args.ready_only,
            timeout_seconds=args.timeout_seconds,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"external credential live verifier failed: {exc}", file=sys.stderr)
        return 1
    print(
        "external credential live verifier valid: "
        f"mode={report['mode']}, "
        f"selected={report['summary']['selected_boundaries']}, "
        f"ready={report['summary']['ready_boundaries']}, "
        f"blocked={report['summary']['blocked_boundaries']}, "
        f"executed={report['summary']['commands_executed']}"
    )
    return 0


def _select_boundaries(boundaries: list[dict[str, Any]], boundary_ids: list[str] | None) -> list[dict[str, Any]]:
    if not boundary_ids:
        return list(boundaries)
    by_id = {boundary["id"]: boundary for boundary in boundaries}
    missing = sorted(set(boundary_ids) - set(by_id))
    if missing:
        raise ValueError(f"unknown boundary id(s): {', '.join(missing)}")
    return [by_id[boundary_id] for boundary_id in boundary_ids]


def _planned_boundary(boundary: dict[str, Any], *, plan_rank: int) -> dict[str, Any]:
    missing = boundary["missing_required_env"]
    live_status = _live_status(boundary)
    return {
        "id": boundary["id"],
        "plan_rank": plan_rank,
        "title": boundary["title"],
        "registry_status": boundary["status"],
        "live_status": live_status,
        "owner": boundary["owner"],
        "required_env": boundary["required_env"],
        "missing_required_env": missing,
        "optional_env_any_of": boundary["optional_env_any_of"],
        "optional_env_available": boundary["optional_env_available"],
        "verification_commands": boundary["verification_commands"],
        "claim_policy": boundary["claim_policy"],
    }


def _unblock_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    status_priority = {
        "external_auth_blocked": 0,
        "optional_token_absent": 1,
        "credential_gated": 2,
        "future_scoped": 3,
    }
    if item["missing_required_env"]:
        env_gap_priority = 0
    elif item["optional_env_any_of"]:
        env_gap_priority = 1
    else:
        env_gap_priority = 2
    return (status_priority.get(item["status"], 99), env_gap_priority, item["id"])


def _live_status(boundary: dict[str, Any]) -> str:
    if boundary["missing_required_env"]:
        return "blocked_missing_required_env"
    if (
        boundary["status"] == "optional_token_absent"
        and boundary["optional_env_any_of"]
        and not boundary["optional_env_available"]
    ):
        return "blocked_missing_optional_env"
    return "ready_for_execution"


def _blocked_boundary_count(status_counts: Counter[str]) -> int:
    return sum(count for status, count in status_counts.items() if status != "ready_for_execution")


def _skip_reason(boundary: dict[str, Any]) -> str:
    if boundary["live_status"] == "blocked_missing_optional_env":
        return "missing optional token env"
    if boundary["live_status"] == "blocked_missing_required_env":
        return "missing required env"
    return boundary["live_status"]


def _planned_command(boundary: dict[str, Any], command: str) -> dict[str, Any]:
    return {
        "boundary_id": boundary["id"],
        "command": command,
        "status": "planned",
        "returncode": None,
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "skip_reason": "",
    }


def _execute_command(
    boundary: dict[str, Any],
    command: str,
    *,
    env_map: dict[str, str],
    env_names: list[str],
    timeout_seconds: float,
    workspace_root: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        process = subprocess.run(
            command,
            cwd=workspace_root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            env=env_map,
        )
        return {
            **_planned_command(boundary, command),
            "status": "pass" if process.returncode == 0 else "fail",
            "returncode": process.returncode,
            "elapsed_seconds": round(max(time.perf_counter() - started, 0.0), 3),
            "stdout_tail": _redact_text(_tail_text(process.stdout), env_map, env_names),
            "stderr_tail": _redact_text(_tail_text(process.stderr), env_map, env_names),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            **_planned_command(boundary, command),
            "status": "fail",
            "returncode": 124,
            "elapsed_seconds": round(max(time.perf_counter() - started, 0.0), 3),
            "stdout_tail": _redact_text(_tail_text(exc.stdout or ""), env_map, env_names),
            "stderr_tail": _redact_text(f"Command timed out after {timeout_seconds}s\n{_tail_text(exc.stderr or '')}", env_map, env_names),
        }


def _redact_text(value: str, env_map: Mapping[str, str], env_names: list[str]) -> str:
    redacted = value
    for name in env_names:
        secret = env_map.get(name)
        if secret and len(secret) >= 4:
            redacted = redacted.replace(secret, f"<redacted:{name}>")
    return redacted


def _tail_text(value: str, *, max_lines: int = 20) -> str:
    lines = value.strip().splitlines()
    return "\n".join(lines[-max_lines:])


def _repo_relative(path: Path, workspace_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(workspace_root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
