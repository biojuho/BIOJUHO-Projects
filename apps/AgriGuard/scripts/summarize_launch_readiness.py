from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _env_validation_summary(path: Path, workspace_root: Path) -> dict[str, object]:
    payload = _read_json(path)
    if payload is None:
        return {"found": False, "path": _rel(path, workspace_root)}
    return {
        "found": True,
        "path": _rel(path, workspace_root),
        "status": payload.get("status"),
        "ready_for_preflight": payload.get("ready_for_preflight"),
        "placeholder_count": payload.get("placeholder_count"),
        "missing_required_keys": _list(payload.get("missing_required_keys")),
        "forbidden_flags_enabled": _list(payload.get("forbidden_flags_enabled")),
        "validation_scope": payload.get("validation_scope"),
    }


def _launch_report_summary(path: Path, workspace_root: Path) -> dict[str, object]:
    payload = _read_json(path)
    if payload is None:
        return {"found": False, "path": _rel(path, workspace_root)}

    results = _list(payload.get("results"))
    result_names = [
        str(item.get("name"))
        for item in results
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    child_reports = payload.get("child_reports") if isinstance(payload.get("child_reports"), dict) else {}
    env_validation = (
        child_reports.get("env_validation")
        if isinstance(child_reports.get("env_validation"), dict)
        else {}
    )
    preflight = child_reports.get("preflight") if isinstance(child_reports.get("preflight"), dict) else {}
    operator_packet = (
        child_reports.get("operator_packet")
        if isinstance(child_reports.get("operator_packet"), dict)
        else {}
    )
    return {
        "found": True,
        "path": _rel(path, workspace_root),
        "status": payload.get("status"),
        "stage": payload.get("stage"),
        "stop_reason": payload.get("stop_reason"),
        "run_browser_smoke": payload.get("run_browser_smoke"),
        "result_names": result_names,
        "env_validation_ready_for_preflight": env_validation.get("ready_for_preflight"),
        "env_validation_status": env_validation.get("status"),
        "preflight_status": preflight.get("status"),
        "operator_packet_status": operator_packet.get("status"),
        "operator_packet_action_ids": _list(operator_packet.get("operator_action_ids")),
    }


def _operator_packet_summary(path: Path, workspace_root: Path) -> dict[str, object]:
    payload = _read_json(path)
    if payload is None:
        return {"found": False, "path": _rel(path, workspace_root)}

    actions = _list(payload.get("operator_actions"))
    action_ids = [
        str(item.get("id"))
        for item in actions
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    return {
        "found": True,
        "path": _rel(path, workspace_root),
        "status": payload.get("status"),
        "preflight_status": payload.get("preflight_status"),
        "blocking_action_count": payload.get("blocking_action_count"),
        "operator_action_ids": action_ids,
        "safe_rerun_commands": [
            str(command)
            for command in _list(payload.get("safe_rerun_commands"))
            if isinstance(command, str) and command.strip()
        ],
        "secrets_redacted": payload.get("secrets_redacted"),
    }


def _classify(
    *,
    launch: dict[str, object],
    env_validation: dict[str, object],
    operator_packet: dict[str, object],
) -> tuple[str, str]:
    if env_validation.get("found") and env_validation.get("status") == "fail":
        return "blocked", "env_shape_blocked"
    if launch.get("found") and launch.get("stop_reason") in {
        "env_shape_validation_failed",
        "env_shape_validation_requires_single_env_file",
    }:
        return "blocked", "env_shape_blocked"
    if launch.get("found") and launch.get("status") == "pass":
        return "ready", "ready"
    if launch.get("found") and launch.get("stop_reason") == "preflight_failed":
        return "blocked", "preflight_blocked"
    if operator_packet.get("found") and operator_packet.get("status") == "blocked":
        return "blocked", "operator_values_required"
    if not launch.get("found") and not env_validation.get("found") and not operator_packet.get("found"):
        return "unknown", "no_launch_evidence"
    if launch.get("found") and launch.get("status") == "fail":
        stage = str(launch.get("stage") or "launch")
        return "blocked", f"{stage}_blocked"
    return "unknown", "incomplete_launch_evidence"


def _next_actions(blocker_class: str) -> list[str]:
    if blocker_class == "env_shape_blocked":
        return [
            "Replace env template placeholders and sample domains.",
            "Rerun validate_launch_env_template.py on the filled env file.",
            "Retry launch_compose.py with --validate-env-file-shape after the shape report passes.",
        ]
    if blocker_class == "preflight_blocked":
        return [
            "Open the operator packet and satisfy the listed action IDs.",
            "Provide real external launch credentials and paths outside the repo.",
            "Rerun strict preflight before compose.",
        ]
    if blocker_class == "operator_values_required":
        return [
            "Follow operator_action_ids from the packet.",
            "Rerun shape validation and strict preflight after values are supplied.",
        ]
    if blocker_class == "ready":
        return ["Run or review compose/browser smoke evidence for the target release."]
    return ["Run launch_compose.py or provide report paths to classify the current blocker."]


def _command_shell(command: str) -> str | None:
    return "powershell" if command.lstrip().startswith("&") else None


def _next_commands(blocker_class: str, operator_packet: dict[str, object]) -> list[dict[str, str]]:
    if blocker_class not in {"env_shape_blocked", "preflight_blocked", "operator_values_required"}:
        return []

    raw_commands = operator_packet.get("safe_rerun_commands")
    if not isinstance(raw_commands, list):
        return []

    labels = (
        "validate_env_template",
        "guarded_launch",
        "strict_preflight",
        "compose_launch",
    )
    commands: list[dict[str, str]] = []
    for index, command in enumerate(raw_commands):
        if not isinstance(command, str) or not command.strip():
            continue
        name = labels[index] if index < len(labels) else f"safe_rerun_{index + 1}"
        item = {"name": name, "command": command}
        shell = _command_shell(command)
        if shell is not None:
            item["shell"] = shell
        commands.append(item)
    return commands


def build_summary(
    *,
    launch_report_json: Path,
    env_validation_json: Path,
    operator_packet_json: Path,
    app_root: Path | None = None,
) -> dict[str, object]:
    app_root = (app_root or _default_app_root()).resolve()
    workspace_root = _workspace_root(app_root)
    launch = _launch_report_summary(launch_report_json.resolve(), workspace_root)
    env_validation = _env_validation_summary(env_validation_json.resolve(), workspace_root)
    operator_packet = _operator_packet_summary(operator_packet_json.resolve(), workspace_root)
    status, blocker_class = _classify(
        launch=launch,
        env_validation=env_validation,
        operator_packet=operator_packet,
    )
    return {
        "schema_version": 1,
        "status": status,
        "blocker_class": blocker_class,
        "secrets_redacted": True,
        "reports": {
            "launch": launch,
            "env_validation": env_validation,
            "operator_packet": operator_packet,
        },
        "next_actions": _next_actions(blocker_class),
        "next_commands": _next_commands(blocker_class, operator_packet),
    }


def render_markdown(summary: dict[str, object]) -> str:
    reports = summary.get("reports") if isinstance(summary.get("reports"), dict) else {}
    env_validation = reports.get("env_validation") if isinstance(reports.get("env_validation"), dict) else {}
    operator_packet = reports.get("operator_packet") if isinstance(reports.get("operator_packet"), dict) else {}
    action_ids = (
        operator_packet.get("operator_action_ids")
        if isinstance(operator_packet.get("operator_action_ids"), list)
        else []
    )
    lines = [
        "# AgriGuard Launch Readiness Summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Blocker class: `{summary['blocker_class']}`",
        f"- Env validation ready for preflight: `{env_validation.get('ready_for_preflight')}`",
        f"- Env validation placeholder count: `{env_validation.get('placeholder_count')}`",
        f"- Operator packet preflight status: `{operator_packet.get('preflight_status')}`",
        f"- Operator action IDs: `{', '.join(str(action_id) for action_id in action_ids) if action_ids else '-'}`",
        f"- Secrets redacted: `{str(summary['secrets_redacted']).lower()}`",
        "",
        "## Reports",
        "",
    ]
    for name in ("env_validation", "launch", "operator_packet"):
        report = reports.get(name) if isinstance(reports.get(name), dict) else {}
        lines.append(f"- `{name}`: found=`{str(report.get('found')).lower()}`, status=`{report.get('status')}`")

    lines.extend(["", "## Next Actions", ""])
    next_actions = summary.get("next_actions") if isinstance(summary.get("next_actions"), list) else []
    lines.extend(f"- {action}" for action in next_actions)
    next_commands = summary.get("next_commands") if isinstance(summary.get("next_commands"), list) else []
    lines.extend(["", "## Next Commands", ""])
    if next_commands:
        for item in next_commands:
            if isinstance(item, dict):
                shell = item.get("shell")
                shell_text = f" ({shell})" if isinstance(shell, str) else ""
                lines.append(f"- `{item.get('name')}`{shell_text}: `{item.get('command')}`")
    else:
        lines.append("No copyable next commands are available for the current evidence set.")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    app_root = _default_app_root()
    workspace_root = _workspace_root(app_root)
    parser = argparse.ArgumentParser(description="Summarize AgriGuard launch readiness without exposing values.")
    parser.add_argument("--app-root", type=Path, default=app_root)
    parser.add_argument(
        "--launch-report-json",
        type=Path,
        default=workspace_root / "var" / "agriguard-compose-launch-report.json",
    )
    parser.add_argument(
        "--env-validation-json",
        type=Path,
        default=workspace_root / "var" / "agriguard-launch-env-template-validation.json",
    )
    parser.add_argument(
        "--operator-packet-json",
        type=Path,
        default=workspace_root / "var" / "agriguard-launch-operator-packet.json",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=workspace_root / "var" / "agriguard-launch-readiness-summary.json",
    )
    parser.add_argument("--markdown-out", type=Path, default=None)
    parser.add_argument("--exit-zero-on-blocked", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_summary(
        launch_report_json=args.launch_report_json,
        env_validation_json=args.env_validation_json,
        operator_packet_json=args.operator_packet_json,
        app_root=args.app_root,
    )
    write_json(args.json_out.resolve(), summary)
    if args.markdown_out:
        args.markdown_out.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.resolve().write_text(render_markdown(summary), encoding="utf-8")
        print(f"wrote launch readiness markdown: {args.markdown_out}")
    print(f"wrote launch readiness summary: {args.json_out}")
    return 0 if args.exit_zero_on_blocked or summary["status"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
