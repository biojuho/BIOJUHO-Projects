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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _env_validation_summary(path: Path, workspace_root: Path) -> dict[str, object]:
    payload = _read_json(path)
    if payload is None:
        return {"found": False, "path": _rel(path, workspace_root)}
    return {
        "found": True,
        "path": _rel(path, workspace_root),
        "status": payload.get("status"),
        "blocker_class": payload.get("blocker_class"),
        "ready_for_preflight": payload.get("ready_for_preflight"),
        "placeholder_count": payload.get("placeholder_count"),
        "missing_required_keys": _list(payload.get("missing_required_keys")),
        "forbidden_flags_enabled": _list(payload.get("forbidden_flags_enabled")),
        "validation_scope": payload.get("validation_scope"),
    }


def _summary_count(summary: dict[str, object], key: str) -> object:
    value = summary.get(key)
    return value if isinstance(value, int) else None


def _summary_ratio(report: dict[str, object], passed_key: str, total_key: str) -> str | None:
    passed = report.get(passed_key)
    total = report.get(total_key)
    if isinstance(passed, int) and isinstance(total, int):
        return f"{passed}/{total}"
    return None


def _browser_smoke_summary(report: dict[str, object], workspace_root: Path) -> dict[str, object]:
    if not report:
        return {}
    raw_path = report.get("path")
    path = _rel(Path(raw_path), workspace_root) if isinstance(raw_path, str) and raw_path else None
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "found": report.get("found"),
        "path": path,
        "status": report.get("status"),
        "base_url": report.get("base_url"),
        "api_url": report.get("api_url"),
        "mobile": report.get("mobile"),
        "include_unavailable_check": report.get("include_unavailable_check"),
        "steps_total": _summary_count(summary, "total"),
        "steps_passed": _summary_count(summary, "passed"),
        "steps_failed": _summary_count(summary, "failed"),
        "checks_total": _summary_count(summary, "checks_total"),
        "checks_passed": _summary_count(summary, "checks_passed"),
        "checks_failed": _summary_count(summary, "checks_failed"),
        "prechecks_total": _summary_count(summary, "prechecks_total"),
        "prechecks_passed": _summary_count(summary, "prechecks_passed"),
        "prechecks_failed": _summary_count(summary, "prechecks_failed"),
        "screenshot_artifacts_total": _summary_count(summary, "screenshot_artifacts_total"),
        "screenshot_artifacts_passed": _summary_count(summary, "screenshot_artifacts_passed"),
        "screenshot_artifacts_failed": _summary_count(summary, "screenshot_artifacts_failed"),
        "failed_step_names": _string_list(summary.get("failed_step_names")),
        "failed_check_names": _string_list(summary.get("failed_check_names")),
        "failed_precheck_names": _string_list(summary.get("failed_precheck_names")),
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
    browser_smoke = (
        child_reports.get("browser_smoke")
        if isinstance(child_reports.get("browser_smoke"), dict)
        else {}
    )
    return {
        "found": True,
        "path": _rel(path, workspace_root),
        "status": payload.get("status"),
        "blocker_class": payload.get("blocker_class"),
        "stage": payload.get("stage"),
        "stop_reason": payload.get("stop_reason"),
        "run_browser_smoke": payload.get("run_browser_smoke"),
        "result_names": result_names,
        "env_validation_blocker_class": env_validation.get("blocker_class"),
        "env_validation_ready_for_preflight": env_validation.get("ready_for_preflight"),
        "env_validation_status": env_validation.get("status"),
        "preflight_status": preflight.get("status"),
        "operator_packet_status": operator_packet.get("status"),
        "operator_packet_action_ids": _list(operator_packet.get("operator_action_ids")),
        "browser_smoke": _browser_smoke_summary(browser_smoke, workspace_root),
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
    checks = payload.get("preflight_checks") if isinstance(payload.get("preflight_checks"), dict) else {}
    safe_check_keys = (
        "runtime",
        "docker_checked",
        "firebase_credentials_source",
        "firebase_credentials_resolved_path",
        "forbidden_launch_flags_enabled",
        "allowed_origins_source",
        "public_verify_base_url_source",
        "database_password_source",
        "database_url_source",
    )
    summary = {
        "found": True,
        "path": _rel(path, workspace_root),
        "status": payload.get("status"),
        "blocker_class": payload.get("blocker_class"),
        "env_validation_status": payload.get("env_validation_status"),
        "env_validation_blocker_class": payload.get("env_validation_blocker_class"),
        "preflight_status": payload.get("preflight_status"),
        "blocking_action_count": payload.get("blocking_action_count"),
        "operator_action_ids": action_ids,
        "preflight_checks": {key: checks[key] for key in safe_check_keys if key in checks},
        "safe_rerun_commands": [
            str(command)
            for command in _list(payload.get("safe_rerun_commands"))
            if isinstance(command, str) and command.strip()
        ],
        "secrets_redacted": payload.get("secrets_redacted"),
    }
    guarded_evidence = (
        payload.get("guarded_launch_evidence")
        if isinstance(payload.get("guarded_launch_evidence"), dict)
        else {}
    )
    artifact_index_summary = (
        guarded_evidence.get("artifact_index_readiness_summary")
        if isinstance(guarded_evidence.get("artifact_index_readiness_summary"), dict)
        else {}
    )
    if artifact_index_summary:
        summary.update(
            {
                "artifact_index_status": artifact_index_summary.get("status"),
                "artifact_index_blocker_class": artifact_index_summary.get("blocker_class"),
                "consumer_packet_validation_status": artifact_index_summary.get(
                    "consumer_packet_validation_status"
                ),
                "consumer_command_metadata_status": artifact_index_summary.get(
                    "consumer_command_metadata_status"
                ),
                "consumer_readiness_operator_packet_consumer_command_metadata_status": artifact_index_summary.get(
                    "consumer_readiness_operator_packet_consumer_command_metadata_status"
                ),
                "artifact_index_recovery_command_status": artifact_index_summary.get(
                    "recovery_command_status"
                ),
            }
        )
    return summary


def _classify(
    *,
    launch: dict[str, object],
    env_validation: dict[str, object],
    operator_packet: dict[str, object],
) -> tuple[str, str]:
    if env_validation.get("found") and env_validation.get("status") == "fail":
        blocker_class = env_validation.get("blocker_class")
        return "blocked", str(blocker_class or "env_shape_blocked")
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


ACTION_NEXT_ACTIONS = {
    "set_firebase_service_account_file": (
        "Provide a real Firebase Admin service-account .json at an absolute host path outside the repo for "
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE."
    ),
    "set_secret_key": "Set a production-strength AGRIGUARD_SECRET_KEY.",
    "set_qr_token_pepper": "Set a stable production QR token pepper.",
    "set_public_verify_base_url": "Set the public HTTPS verification URL.",
    "set_allowed_origins": "Set explicit production browser origins.",
    "set_database_password": "Set launch-safe database credentials.",
    "disable_forbidden_auth_flags": "Disable dev/test authentication bypass flags.",
    "fix_docker_readiness": "Start Docker Desktop and verify compose config can render.",
    "run_launch_preflight": "Generate a readable strict launch preflight report.",
}


def _operator_action_ids(operator_packet: dict[str, object]) -> list[str]:
    return [
        str(action_id)
        for action_id in _list(operator_packet.get("operator_action_ids"))
        if isinstance(action_id, str)
    ]


def _action_next_actions(operator_packet: dict[str, object]) -> list[str]:
    action_ids = _operator_action_ids(operator_packet)
    actions = [ACTION_NEXT_ACTIONS[action_id] for action_id in action_ids if action_id in ACTION_NEXT_ACTIONS]
    if actions:
        return actions
    if action_ids:
        return [f"Resolve operator action IDs: {', '.join(action_ids)}."]
    return ["Satisfy the listed operator action IDs."]


def _next_actions(blocker_class: str, operator_packet: dict[str, object]) -> list[str]:
    if blocker_class == "env_shape_blocked":
        return [
            "Replace env template placeholders and sample domains.",
            "Rerun validate_launch_env_template.py on the filled env file.",
            "Retry launch_compose.py with --validate-env-file-shape after the shape report passes.",
        ]
    if blocker_class == "preflight_blocked":
        return [
            "Open the operator packet for exact variables and validation commands.",
            *_action_next_actions(operator_packet),
            "Rerun strict preflight before compose.",
        ]
    if blocker_class == "operator_values_required":
        return [
            "Open the operator packet for exact variables and validation commands.",
            *_action_next_actions(operator_packet),
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
        "next_actions": _next_actions(blocker_class, operator_packet),
        "next_commands": _next_commands(blocker_class, operator_packet),
    }


def _markdown_check_value(value: object) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "-"
    return str(value).replace("|", "\\|")


def render_markdown(summary: dict[str, object]) -> str:
    reports = summary.get("reports") if isinstance(summary.get("reports"), dict) else {}
    launch = reports.get("launch") if isinstance(reports.get("launch"), dict) else {}
    browser_smoke = launch.get("browser_smoke") if isinstance(launch.get("browser_smoke"), dict) else {}
    env_validation = reports.get("env_validation") if isinstance(reports.get("env_validation"), dict) else {}
    operator_packet = reports.get("operator_packet") if isinstance(reports.get("operator_packet"), dict) else {}
    action_ids = (
        operator_packet.get("operator_action_ids")
        if isinstance(operator_packet.get("operator_action_ids"), list)
        else []
    )
    preflight_checks = (
        operator_packet.get("preflight_checks")
        if isinstance(operator_packet.get("preflight_checks"), dict)
        else {}
    )
    preflight_check_rows = [
        (key, _markdown_check_value(preflight_checks.get(key)))
        for key in (
            "runtime",
            "docker_checked",
            "firebase_credentials_source",
            "firebase_credentials_resolved_path",
            "forbidden_launch_flags_enabled",
            "allowed_origins_source",
            "public_verify_base_url_source",
            "database_password_source",
            "database_url_source",
        )
        if key in preflight_checks and _markdown_check_value(preflight_checks.get(key)) != "-"
    ]
    lines = [
        "# AgriGuard Launch Readiness Summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Blocker class: `{summary['blocker_class']}`",
        f"- Launch report blocker class: `{launch.get('blocker_class') or '-'}`",
        f"- Env validation blocker class: `{env_validation.get('blocker_class') or '-'}`",
        f"- Env validation ready for preflight: `{str(env_validation.get('ready_for_preflight')).lower()}`",
        f"- Env validation placeholder count: `{env_validation.get('placeholder_count')}`",
        f"- Operator packet preflight status: `{operator_packet.get('preflight_status')}`",
        f"- Operator packet blocker class: `{operator_packet.get('blocker_class') or '-'}`",
        f"- Artifact index status: `{operator_packet.get('artifact_index_status')}`",
        f"- Artifact index blocker class: `{operator_packet.get('artifact_index_blocker_class') or '-'}`",
        f"- Artifact index consumer packet validation: `{operator_packet.get('consumer_packet_validation_status')}`",
        f"- Consumer command metadata: `{operator_packet.get('consumer_command_metadata_status')}`",
        "- Consumer readiness command metadata: "
        f"`{operator_packet.get('consumer_readiness_operator_packet_consumer_command_metadata_status')}`",
        f"- Artifact index recovery command status: `{operator_packet.get('artifact_index_recovery_command_status')}`",
        f"- Operator action IDs: `{', '.join(str(action_id) for action_id in action_ids) if action_ids else '-'}`",
        f"- Secrets redacted: `{str(summary.get('secrets_redacted')).lower()}`",
        "",
        "## Reports",
        "",
    ]
    for name in ("env_validation", "launch", "operator_packet"):
        report = reports.get(name) if isinstance(reports.get(name), dict) else {}
        lines.append(f"- `{name}`: found=`{str(report.get('found')).lower()}`, status=`{report.get('status')}`")

    if browser_smoke:
        lines.extend(["", "## Browser Smoke Evidence", ""])
        lines.append("| Field | Value |")
        lines.append("| --- | --- |")
        browser_rows = (
            ("found", browser_smoke.get("found")),
            ("status", browser_smoke.get("status")),
            ("path", browser_smoke.get("path")),
            ("base_url", browser_smoke.get("base_url")),
            ("api_url", browser_smoke.get("api_url")),
            ("mobile", browser_smoke.get("mobile")),
            ("include_unavailable_check", browser_smoke.get("include_unavailable_check")),
            (
                "steps",
                _summary_ratio(browser_smoke, "steps_passed", "steps_total"),
            ),
            (
                "checks",
                _summary_ratio(browser_smoke, "checks_passed", "checks_total"),
            ),
            (
                "prechecks",
                _summary_ratio(browser_smoke, "prechecks_passed", "prechecks_total"),
            ),
            (
                "screenshots",
                _summary_ratio(
                    browser_smoke,
                    "screenshot_artifacts_passed",
                    "screenshot_artifacts_total",
                ),
            ),
            ("failed_steps", browser_smoke.get("failed_step_names")),
            ("failed_prechecks", browser_smoke.get("failed_precheck_names")),
        )
        for key, value in browser_rows:
            rendered = _markdown_check_value(value)
            if rendered != "-":
                lines.append(f"| `{key}` | `{rendered}` |")

    if preflight_check_rows:
        lines.extend(["", "## Operator Packet Preflight Checks", ""])
        lines.append("| Check | Value |")
        lines.append("| --- | --- |")
        for key, value in preflight_check_rows:
            lines.append(f"| `{key}` | `{value}` |")

    lines.extend(["", "## Next Actions", ""])
    next_actions = _string_list(summary.get("next_actions"))
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
