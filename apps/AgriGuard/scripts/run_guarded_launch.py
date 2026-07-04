from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
DEFAULT_OUTPUT_PREFIX = "agriguard-guarded-launch"


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _default_env_file(app_root: Path) -> Path:
    return _workspace_root(app_root) / "var" / "agriguard-launch-operator.env.template"


def _artifact_paths(output_dir: Path, output_prefix: str) -> dict[str, Path]:
    prefix = output_dir / output_prefix
    return {
        "env_validation_json": prefix.with_name(f"{prefix.name}-env-validation.json"),
        "env_validation_markdown": prefix.with_name(f"{prefix.name}-env-validation.md"),
        "preflight_json": prefix.with_name(f"{prefix.name}-preflight.json"),
        "launch_report_json": prefix.with_name(f"{prefix.name}-launch-report.json"),
        "operator_packet_json": prefix.with_name(f"{prefix.name}-operator-packet.json"),
        "operator_packet_markdown": prefix.with_name(f"{prefix.name}-operator-packet.md"),
        "operator_env_template": prefix.with_name(f"{prefix.name}.env.template"),
        "readiness_summary_json": prefix.with_name(f"{prefix.name}-readiness-summary.json"),
        "readiness_summary_markdown": prefix.with_name(f"{prefix.name}-readiness-summary.md"),
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _result_names(payload: dict[str, Any] | None) -> list[str]:
    if payload is None:
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return [
        str(item.get("name"))
        for item in results
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _operator_action_ids_from_packet(payload: dict[str, Any] | None) -> list[str]:
    if payload is None:
        return []
    actions = payload.get("operator_actions")
    if not isinstance(actions, list):
        return []
    return [
        str(action.get("id"))
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    ]


def _operator_action_ids_from_summary(payload: dict[str, Any] | None) -> list[str]:
    if payload is None:
        return []
    reports = payload.get("reports")
    if not isinstance(reports, dict):
        return []
    operator_packet = reports.get("operator_packet")
    if not isinstance(operator_packet, dict):
        return []
    action_ids = operator_packet.get("operator_action_ids")
    if not isinstance(action_ids, list):
        return []
    return [str(action_id) for action_id in action_ids if isinstance(action_id, str)]


def _next_commands_from_summary(payload: dict[str, Any] | None) -> list[dict[str, str]]:
    if payload is None:
        return []
    raw_commands = payload.get("next_commands")
    if not isinstance(raw_commands, list):
        return []

    commands: list[dict[str, str]] = []
    for item in raw_commands:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        command = item.get("command")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(command, str) or not command.strip():
            continue
        summary = {"name": name, "command": command}
        shell = item.get("shell")
        if isinstance(shell, str) and shell.strip():
            summary["shell"] = shell
        commands.append(summary)
    return commands


def _summary_report(payload: dict[str, Any] | None, report_name: str) -> dict[str, Any]:
    if payload is None:
        return {}
    reports = payload.get("reports")
    if not isinstance(reports, dict):
        return {}
    report = reports.get(report_name)
    return report if isinstance(report, dict) else {}


MISSING_STATUS_RECOVERY_ACTION = (
    "Generate the guarded launch operator packet so artifact-index recovery status can be read."
)
MISSING_STATUS_RECOVERY_NOTE = "Artifact index recovery status is unavailable because the operator packet is missing."


def _quote_powershell_arg(value: str) -> str:
    if value and not any(char.isspace() for char in value) and "'" not in value:
        return value
    return "'" + value.replace("'", "''") + "'"


def _format_powershell_command(command: list[str] | None) -> str | None:
    if not command:
        return None
    return "& " + " ".join(_quote_powershell_arg(str(part)) for part in command)


def _recovery_command_shell_text(recovery_summary: dict[str, object]) -> tuple[str | None, str | None]:
    command = recovery_summary.get("command")
    if isinstance(command, list):
        command_text = _format_powershell_command([str(part) for part in command])
        return ("powershell", command_text) if command_text else (None, None)
    if isinstance(command, str) and command.strip():
        command_text = command.strip()
        if not command_text.lstrip().startswith("&"):
            command_text = f"& {command_text}"
        return "powershell", command_text
    return None, None


def _packet_artifact_index_recovery_summary(packet: dict[str, Any] | None) -> dict[str, object]:
    if packet is None:
        return {
            "required": True,
            "action": MISSING_STATUS_RECOVERY_ACTION,
            "status": None,
            "note": MISSING_STATUS_RECOVERY_NOTE,
            "command": None,
        }
    evidence = packet.get("guarded_launch_evidence") if isinstance(packet.get("guarded_launch_evidence"), dict) else {}
    artifact_summary = (
        evidence.get("artifact_index_readiness_summary")
        if isinstance(evidence.get("artifact_index_readiness_summary"), dict)
        else {}
    )
    recovery_summary = artifact_summary.get("recovery_summary")
    if isinstance(recovery_summary, dict):
        return dict(recovery_summary)
    recovery_status = artifact_summary.get("recovery_command_status")
    recovery_note = artifact_summary.get("recovery_command_note")
    note = recovery_note if isinstance(recovery_note, str) else None
    if not isinstance(recovery_status, str) and note is None:
        note = "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index."
    return {
        "required": not isinstance(recovery_status, str),
        "action": artifact_summary.get("missing_index_action"),
        "status": recovery_status if isinstance(recovery_status, str) else None,
        "note": note,
        "command": artifact_summary.get("missing_index_command"),
    }


def _build_status_view(
    *,
    output_dir: Path,
    output_prefix: str,
    artifact_paths: dict[str, Path],
    artifact_index_json: Path | None = None,
) -> dict[str, object]:
    launch = _read_json(artifact_paths["launch_report_json"])
    summary = _read_json(artifact_paths["readiness_summary_json"])
    packet = _read_json(artifact_paths["operator_packet_json"])
    artifact_index = _read_json(artifact_index_json) if artifact_index_json is not None else None
    action_ids = _operator_action_ids_from_summary(summary) or _operator_action_ids_from_packet(packet)
    summary_env_validation = _summary_report(summary, "env_validation")
    summary_operator_packet = _summary_report(summary, "operator_packet")
    artifacts = {key: str(value) for key, value in artifact_paths.items()}
    if artifact_index_json is not None:
        artifacts["artifact_index_json"] = str(artifact_index_json)
    missing_required_roles = (
        artifact_index.get("missing_required_roles")
        if artifact_index is not None and isinstance(artifact_index.get("missing_required_roles"), list)
        else []
    )
    artifact_index_recovery_summary = (
        _artifact_index_recovery_summary(artifact_index, None)
        if artifact_index is not None
        else _packet_artifact_index_recovery_summary(packet)
    )
    artifact_index_recovery_command_shell, artifact_index_recovery_command_text = _recovery_command_shell_text(
        artifact_index_recovery_summary
    )
    status = "missing_artifacts"
    if summary is not None:
        status = str(summary.get("status") or "unknown")
    elif launch is not None and launch.get("status") == "pass":
        status = "ready"
    elif launch is not None:
        status = str(launch.get("status") or "unknown")
    elif packet is not None:
        status = str(packet.get("status") or "unknown")
    blocker_class = summary.get("blocker_class") if summary is not None else None
    if status == "ready" and blocker_class is None:
        blocker_class = "ready"

    return {
        "schema_version": 1,
        "status": status,
        "blocker_class": blocker_class,
        "operator_action_ids": action_ids,
        "output_dir": str(output_dir),
        "output_prefix": output_prefix,
        "secrets_redacted": True,
        "artifact_index_recovery_summary": artifact_index_recovery_summary,
        "artifact_index_recovery_command_shell": artifact_index_recovery_command_shell,
        "artifact_index_recovery_command_text": artifact_index_recovery_command_text,
        "artifacts": artifacts,
        "launch": {
            "found": launch is not None,
            "path": str(artifact_paths["launch_report_json"]),
            "status": launch.get("status") if launch is not None else None,
            "stage": launch.get("stage") if launch is not None else None,
            "stop_reason": launch.get("stop_reason") if launch is not None else None,
            "result_names": _result_names(launch),
        },
        "readiness_summary": {
            "found": summary is not None,
            "path": str(artifact_paths["readiness_summary_json"]),
            "status": summary.get("status") if summary is not None else None,
            "blocker_class": summary.get("blocker_class") if summary is not None else None,
            "next_actions": summary.get("next_actions") if summary is not None and isinstance(summary.get("next_actions"), list) else [],
            "next_commands": _next_commands_from_summary(summary),
            "operator_action_ids": action_ids,
            "env_validation_ready_for_preflight": summary_env_validation.get("ready_for_preflight"),
            "env_validation_placeholder_count": summary_env_validation.get("placeholder_count"),
            "operator_packet_preflight_status": summary_operator_packet.get("preflight_status"),
        },
        "operator_packet": {
            "found": packet is not None,
            "path": str(artifact_paths["operator_packet_json"]),
            "status": packet.get("status") if packet is not None else None,
            "operator_action_ids": _operator_action_ids_from_packet(packet),
            "blocking_action_count": packet.get("blocking_action_count")
            if packet is not None and isinstance(packet.get("blocking_action_count"), int)
            else None,
            "preflight_status": packet.get("preflight_status") if packet is not None else None,
            "preflight_errors": _string_list(packet.get("preflight_errors")) if packet is not None else [],
            "secrets_redacted": packet.get("secrets_redacted") if packet is not None else None,
        },
        "artifact_index": {
            "found": artifact_index is not None,
            "path": str(artifact_index_json) if artifact_index_json is not None else None,
            "status": artifact_index.get("status") if artifact_index is not None else None,
            "missing_required_roles": [
                str(role) for role in missing_required_roles if isinstance(role, str)
            ],
            "consumer_packet_validation_status": artifact_index.get("consumer_packet_validation_status")
            if artifact_index is not None
            else None,
            "consumer_readiness_operator_action_ids": [
                str(action_id)
                for action_id in artifact_index.get("consumer_readiness_operator_action_ids", [])
                if isinstance(action_id, str)
            ]
            if artifact_index is not None
            else [],
            "consumer_readiness_env_validation_ready_for_preflight": artifact_index.get(
                "consumer_readiness_env_validation_ready_for_preflight"
            )
            if artifact_index is not None
            else None,
            "consumer_readiness_env_validation_placeholder_count": artifact_index.get(
                "consumer_readiness_env_validation_placeholder_count"
            )
            if artifact_index is not None
            else None,
            "consumer_readiness_operator_packet_preflight_status": artifact_index.get(
                "consumer_readiness_operator_packet_preflight_status"
            )
            if artifact_index is not None
            else None,
            "recovery_command_status": artifact_index.get("recovery_command_status")
            if artifact_index is not None
            else None,
        },
    }


def _status_view_ready(status_view: dict[str, object]) -> bool:
    return status_view.get("status") == "ready" and status_view.get("blocker_class") == "ready"


def _build_launch_command(
    *,
    app_root: Path,
    env_file: Path,
    artifact_paths: dict[str, Path],
    compose_files: list[Path],
    services: list[str],
    run_browser_smoke: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "launch_compose.py"),
        "--app-root",
        str(app_root),
    ]
    for compose_file in compose_files:
        command.extend(["--compose-file", str(compose_file)])
    for service in services:
        command.extend(["--service", service])
    command.extend(
        [
            "--env-file",
            str(env_file),
            "--validate-env-file-shape",
            "--env-validation-json-out",
            str(artifact_paths["env_validation_json"]),
            "--env-validation-markdown-out",
            str(artifact_paths["env_validation_markdown"]),
            "--json-out",
            str(artifact_paths["preflight_json"]),
            "--launch-report-json",
            str(artifact_paths["launch_report_json"]),
            "--operator-packet-json",
            str(artifact_paths["operator_packet_json"]),
            "--operator-packet-markdown",
            str(artifact_paths["operator_packet_markdown"]),
            "--operator-env-template",
            str(artifact_paths["operator_env_template"]),
            "--readiness-summary-json",
            str(artifact_paths["readiness_summary_json"]),
            "--readiness-summary-markdown",
            str(artifact_paths["readiness_summary_markdown"]),
        ]
    )
    if run_browser_smoke:
        command.append("--run-browser-smoke")
    return command


def _default_handoff_json(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-handoff.json"


def _default_handoff_markdown(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-handoff.md"


def _default_handoff_validation_json(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-handoff.validation.json"


def _default_handoff_consumer_json(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-handoff.consumer.json"


def _default_ready_gate_json(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-ready-gate.json"


def _default_artifact_index_json(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-artifact-index.json"


def _default_artifact_index_markdown(output_dir: Path, output_prefix: str) -> Path:
    return output_dir / f"{output_prefix}-artifact-index.md"


MISSING_ARTIFACT_INDEX_RECOVERY_ACTION = (
    "Run the guarded launch wrapper without --dry-run to generate the artifact index evidence."
)
MISSING_ARTIFACT_INDEX_RECOVERY_NOTE = (
    "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index."
)


def _artifact_index_recovery_summary(
    index: dict[str, object] | None,
    missing_index_command: list[str] | None,
) -> dict[str, object]:
    if index is not None:
        recovery_summary = index.get("recovery_summary")
        if isinstance(recovery_summary, dict):
            return dict(recovery_summary)
        recovery_command = index.get("recovery_command")
        return {
            "required": recovery_command is not None,
            "action": index.get("recovery_action"),
            "status": index.get("recovery_command_status"),
            "note": index.get("recovery_command_note"),
            "command": recovery_command,
        }
    return {
        "required": True,
        "action": MISSING_ARTIFACT_INDEX_RECOVERY_ACTION,
        "status": None,
        "note": MISSING_ARTIFACT_INDEX_RECOVERY_NOTE,
        "command": missing_index_command,
    }


def _artifact_index_readiness_summary(
    index_json: Path,
    missing_index_command: list[str] | None = None,
) -> dict[str, object]:
    index = _read_json(index_json)
    action_ids = (
        index.get("consumer_readiness_operator_action_ids")
        if isinstance(index, dict) and isinstance(index.get("consumer_readiness_operator_action_ids"), list)
        else []
    )
    return {
        "found": index is not None,
        "path": str(index_json),
        "status": index.get("status") if index is not None else None,
        "consumer_packet_validation_status": index.get("consumer_packet_validation_status") if index is not None else None,
        "recovery_command_status": index.get("recovery_command_status") if index is not None else None,
        "recovery_command_note": None if index is not None else MISSING_ARTIFACT_INDEX_RECOVERY_NOTE,
        "recovery_summary": _artifact_index_recovery_summary(index, missing_index_command),
        "operator_action_ids": [str(action_id) for action_id in action_ids if isinstance(action_id, str)],
        "env_validation_ready_for_preflight": index.get("consumer_readiness_env_validation_ready_for_preflight")
        if index is not None
        else None,
        "env_validation_placeholder_count": index.get("consumer_readiness_env_validation_placeholder_count")
        if index is not None
        else None,
        "operator_packet_preflight_status": index.get("consumer_readiness_operator_packet_preflight_status")
        if index is not None
        else None,
        "missing_index_action": None if index is not None else MISSING_ARTIFACT_INDEX_RECOVERY_ACTION,
        "missing_index_command": None if index is not None else missing_index_command,
    }


def _build_wrapper_command(
    *,
    app_root: Path,
    env_file: Path,
    output_dir: Path,
    output_prefix: str,
    compose_files: list[Path],
    services: list[str],
    run_browser_smoke: bool,
    emit_handoff: bool,
    status_json_out: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--app-root",
        str(app_root),
        "--env-file",
        str(env_file),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
    ]
    for compose_file in compose_files:
        command.extend(["--compose-file", str(compose_file)])
    for service in services:
        command.extend(["--service", service])
    if not run_browser_smoke:
        command.append("--no-browser-smoke")
    if emit_handoff:
        command.append("--emit-handoff")
    if status_json_out is not None:
        command.extend(["--status-json-out", str(status_json_out)])
    return command


def _build_handoff_command(
    *,
    app_root: Path,
    output_dir: Path,
    output_prefix: str,
    ready_gate_json: Path,
    handoff_json: Path,
    handoff_markdown: Path,
    validation_json: Path,
) -> list[str]:
    return [
        sys.executable,
        str(app_root / "scripts" / "render_guarded_launch_handoff.py"),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
        "--ready-gate-json",
        str(ready_gate_json),
        "--json-out",
        str(handoff_json),
        "--markdown-out",
        str(handoff_markdown),
        "--validation-json-out",
        str(validation_json),
        "--exit-zero-on-blocked",
    ]


def _build_handoff_consumer_command(
    *,
    app_root: Path,
    handoff_json: Path,
    validation_json: Path,
    consumer_json: Path,
) -> list[str]:
    return [
        sys.executable,
        str(app_root / "scripts" / "consume_guarded_launch_handoff.py"),
        str(handoff_json),
        "--validation-json",
        str(validation_json),
        "--json-out",
        str(consumer_json),
        "--exit-zero-on-blocked",
    ]


def _build_artifact_index_command(
    *,
    app_root: Path,
    env_file: Path,
    output_dir: Path,
    output_prefix: str,
    json_out: Path,
    markdown_out: Path,
    status_json: Path | None,
    handoff_json: Path,
    handoff_markdown: Path,
    handoff_validation_json: Path,
    handoff_consumer_json: Path,
    ready_gate_json: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "index_guarded_launch_artifacts.py"),
        "--env-file",
        str(env_file),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
        "--json-out",
        str(json_out),
        "--markdown-out",
        str(markdown_out),
    ]
    if status_json is not None:
        command.extend(["--status-json", str(status_json)])
    command.extend(
        [
            "--handoff-json",
            str(handoff_json),
            "--handoff-markdown",
            str(handoff_markdown),
            "--handoff-validation-json",
            str(handoff_validation_json),
            "--handoff-consumer-json",
            str(handoff_consumer_json),
            "--ready-gate-json",
            str(ready_gate_json),
        ]
    )
    return command


def _build_operator_packet_refresh_command(
    *,
    app_root: Path,
    preflight_json: Path,
    env_validation_json: Path,
    env_file: Path,
    json_out: Path,
    markdown_out: Path,
    env_template_out: Path,
    guarded_output_dir: Path,
    guarded_output_prefix: str,
    guarded_status_json: Path | None,
    guarded_handoff_json: Path,
    guarded_handoff_markdown: Path,
    guarded_handoff_validation_json: Path,
    guarded_handoff_consumer_json: Path,
    guarded_ready_gate_json: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "render_launch_operator_packet.py"),
        "--app-root",
        str(app_root),
        "--preflight-json",
        str(preflight_json),
        "--env-validation-json",
        str(env_validation_json),
        "--env-file",
        str(env_file),
        "--json-out",
        str(json_out),
        "--markdown-out",
        str(markdown_out),
        "--env-template-out",
        str(env_template_out),
        "--guarded-output-dir",
        str(guarded_output_dir),
        "--guarded-output-prefix",
        guarded_output_prefix,
        "--guarded-handoff-json",
        str(guarded_handoff_json),
        "--guarded-handoff-markdown",
        str(guarded_handoff_markdown),
        "--guarded-handoff-validation-json",
        str(guarded_handoff_validation_json),
        "--guarded-handoff-consumer-json",
        str(guarded_handoff_consumer_json),
        "--guarded-ready-gate-json",
        str(guarded_ready_gate_json),
        "--exit-zero-on-blocked",
    ]
    if guarded_status_json is not None:
        command.extend(["--guarded-status-json", str(guarded_status_json)])
    return command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the canonical AgriGuard guarded compose launch with env-shape validation and readiness artifacts."
    )
    parser.add_argument("--app-root", type=Path, default=_default_app_root(), help="AgriGuard app root.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Operator env file to validate before strict preflight. Defaults to var/agriguard-launch-operator.env.template.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for launch, packet, validation, and readiness artifacts. Defaults to workspace var/.",
    )
    parser.add_argument(
        "--output-prefix",
        default=DEFAULT_OUTPUT_PREFIX,
        help=f"Artifact filename prefix. Defaults to {DEFAULT_OUTPUT_PREFIX}.",
    )
    parser.add_argument(
        "--compose-file",
        type=Path,
        action="append",
        default=[],
        help="Compose file path passed through to launch_compose.py. Can be repeated.",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        help="Compose service passed through to launch_compose.py. Can be repeated.",
    )
    parser.add_argument(
        "--no-browser-smoke",
        action="store_true",
        help="Skip the post-compose aggregate browser smoke suite.",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Print a compact status view for the selected output prefix without running launch.",
    )
    parser.add_argument(
        "--status-json-out",
        type=Path,
        default=None,
        help="Optional path for the compact status view JSON.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit nonzero unless the selected guarded-launch prefix is ready.",
    )
    parser.add_argument(
        "--emit-handoff",
        action="store_true",
        help="After launch, render the guarded-launch handoff and validation artifacts for the selected prefix.",
    )
    parser.add_argument("--handoff-json-out", type=Path, default=None)
    parser.add_argument("--handoff-markdown-out", type=Path, default=None)
    parser.add_argument("--handoff-validation-json-out", type=Path, default=None)
    parser.add_argument("--handoff-consumer-json-out", type=Path, default=None)
    parser.add_argument("--artifact-index-json-out", type=Path, default=None)
    parser.add_argument("--artifact-index-markdown-out", type=Path, default=None)
    parser.add_argument("--handoff-ready-gate-json-out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print the delegated launch_compose.py command plan.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, command_runner: CommandRunner = subprocess.run) -> int:
    args = parse_args(argv)
    app_root = args.app_root.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else (_workspace_root(app_root) / "var")
    env_file = args.env_file.resolve() if args.env_file else _default_env_file(app_root)
    compose_files = [compose_file.resolve() for compose_file in args.compose_file]
    artifact_paths = _artifact_paths(output_dir, args.output_prefix)
    command = _build_launch_command(
        app_root=app_root,
        env_file=env_file,
        artifact_paths=artifact_paths,
        compose_files=compose_files,
        services=args.service,
        run_browser_smoke=not args.no_browser_smoke,
    )
    handoff_requested = bool(
        args.emit_handoff
        or args.handoff_json_out
        or args.handoff_markdown_out
        or args.handoff_validation_json_out
        or args.handoff_consumer_json_out
        or args.artifact_index_json_out
        or args.artifact_index_markdown_out
        or args.handoff_ready_gate_json_out
    )
    effective_status_json_out = (
        args.status_json_out.resolve()
        if args.status_json_out
        else (output_dir / f"{args.output_prefix}-status.json" if handoff_requested and not args.status_only else None)
    )
    handoff_json = args.handoff_json_out.resolve() if args.handoff_json_out else _default_handoff_json(output_dir, args.output_prefix)
    handoff_markdown = (
        args.handoff_markdown_out.resolve()
        if args.handoff_markdown_out
        else _default_handoff_markdown(output_dir, args.output_prefix)
    )
    handoff_validation_json = (
        args.handoff_validation_json_out.resolve()
        if args.handoff_validation_json_out
        else _default_handoff_validation_json(output_dir, args.output_prefix)
    )
    handoff_consumer_json = (
        args.handoff_consumer_json_out.resolve()
        if args.handoff_consumer_json_out
        else _default_handoff_consumer_json(output_dir, args.output_prefix)
    )
    handoff_ready_gate_json = (
        args.handoff_ready_gate_json_out.resolve()
        if args.handoff_ready_gate_json_out
        else _default_ready_gate_json(output_dir, args.output_prefix)
    )
    artifact_index_json = (
        args.artifact_index_json_out.resolve()
        if args.artifact_index_json_out
        else _default_artifact_index_json(output_dir, args.output_prefix)
    )
    artifact_index_markdown = (
        args.artifact_index_markdown_out.resolve()
        if args.artifact_index_markdown_out
        else _default_artifact_index_markdown(output_dir, args.output_prefix)
    )
    handoff_command = (
        _build_handoff_command(
            app_root=app_root,
            output_dir=output_dir,
            output_prefix=args.output_prefix,
            ready_gate_json=handoff_ready_gate_json,
            handoff_json=handoff_json,
            handoff_markdown=handoff_markdown,
            validation_json=handoff_validation_json,
        )
        if handoff_requested
        else None
    )
    artifact_index_command = (
        _build_artifact_index_command(
            app_root=app_root,
            env_file=env_file,
            output_dir=output_dir,
            output_prefix=args.output_prefix,
            json_out=artifact_index_json,
            markdown_out=artifact_index_markdown,
            status_json=effective_status_json_out,
            handoff_json=handoff_json,
            handoff_markdown=handoff_markdown,
            handoff_validation_json=handoff_validation_json,
            handoff_consumer_json=handoff_consumer_json,
            ready_gate_json=handoff_ready_gate_json,
        )
        if handoff_requested
        else None
    )
    operator_packet_refresh_command = (
        _build_operator_packet_refresh_command(
            app_root=app_root,
            preflight_json=artifact_paths["preflight_json"],
            env_validation_json=artifact_paths["env_validation_json"],
            env_file=env_file,
            json_out=artifact_paths["operator_packet_json"],
            markdown_out=artifact_paths["operator_packet_markdown"],
            env_template_out=artifact_paths["operator_env_template"],
            guarded_output_dir=output_dir,
            guarded_output_prefix=args.output_prefix,
            guarded_status_json=effective_status_json_out,
            guarded_handoff_json=handoff_json,
            guarded_handoff_markdown=handoff_markdown,
            guarded_handoff_validation_json=handoff_validation_json,
            guarded_handoff_consumer_json=handoff_consumer_json,
            guarded_ready_gate_json=handoff_ready_gate_json,
        )
        if handoff_requested
        else None
    )
    handoff_consumer_command = (
        _build_handoff_consumer_command(
            app_root=app_root,
            handoff_json=handoff_json,
            validation_json=handoff_validation_json,
            consumer_json=handoff_consumer_json,
        )
        if handoff_requested
        else None
    )
    wrapper_command = _build_wrapper_command(
        app_root=app_root,
        env_file=env_file,
        output_dir=output_dir,
        output_prefix=args.output_prefix,
        compose_files=compose_files,
        services=args.service,
        run_browser_smoke=not args.no_browser_smoke,
        emit_handoff=handoff_requested,
        status_json_out=effective_status_json_out,
    )

    if args.status_only:
        status_view = _build_status_view(
            output_dir=output_dir,
            output_prefix=args.output_prefix,
            artifact_paths=artifact_paths,
            artifact_index_json=artifact_index_json,
        )
        if args.status_json_out:
            write_json(args.status_json_out.resolve(), status_view)
        print(json.dumps(status_view, indent=2, sort_keys=True))
        return 0 if not args.require_ready or _status_view_ready(status_view) else 1

    if args.dry_run:
        print(
            json.dumps(
                {
                    "command": command,
                    "app_root": str(app_root),
                    "env_file": str(env_file),
                    "output_dir": str(output_dir),
                    "output_prefix": args.output_prefix,
                    "run_browser_smoke": not args.no_browser_smoke,
                    "artifacts": {key: str(value) for key, value in artifact_paths.items()},
                    "handoff_command": handoff_command,
                    "handoff_json": str(handoff_json) if handoff_requested else None,
                    "handoff_markdown": str(handoff_markdown) if handoff_requested else None,
                    "handoff_validation_json": str(handoff_validation_json) if handoff_requested else None,
                    "handoff_consumer_command": handoff_consumer_command,
                    "handoff_consumer_json": str(handoff_consumer_json) if handoff_requested else None,
                    "handoff_ready_gate_json": str(handoff_ready_gate_json) if handoff_requested else None,
                    "operator_packet_refresh_command": operator_packet_refresh_command,
                    "artifact_index_command": artifact_index_command,
                    "artifact_index_json": str(artifact_index_json) if handoff_requested else None,
                    "artifact_index_markdown": str(artifact_index_markdown) if handoff_requested else None,
                    "artifact_index_readiness_summary": _artifact_index_readiness_summary(
                        artifact_index_json,
                        wrapper_command,
                    )
                    if handoff_requested
                    else None,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    completed = command_runner(command, cwd=app_root, text=True)
    status_view = None
    if effective_status_json_out is not None:
        status_view = _build_status_view(
            output_dir=output_dir,
            output_prefix=args.output_prefix,
            artifact_paths=artifact_paths,
            artifact_index_json=artifact_index_json,
        )
        write_json(effective_status_json_out, status_view)
    post_launch_returncode = 0
    if handoff_command is not None:
        handoff_result = command_runner(handoff_command, cwd=app_root, text=True)
        if handoff_result.returncode != 0 and post_launch_returncode == 0:
            post_launch_returncode = handoff_result.returncode
    if handoff_consumer_command is not None:
        consumer_result = command_runner(handoff_consumer_command, cwd=app_root, text=True)
        if consumer_result.returncode != 0 and post_launch_returncode == 0:
            post_launch_returncode = consumer_result.returncode
    if artifact_index_command is not None:
        artifact_index_result = command_runner(artifact_index_command, cwd=app_root, text=True)
        if artifact_index_result.returncode != 0 and post_launch_returncode == 0:
            post_launch_returncode = artifact_index_result.returncode
    if (
        handoff_command is not None
        and handoff_consumer_command is not None
        and artifact_index_command is not None
        and operator_packet_refresh_command is not None
        and post_launch_returncode == 0
    ):
        if effective_status_json_out is not None or args.require_ready:
            status_view = _build_status_view(
                output_dir=output_dir,
                output_prefix=args.output_prefix,
                artifact_paths=artifact_paths,
                artifact_index_json=artifact_index_json,
            )
        if effective_status_json_out is not None and status_view is not None:
            write_json(effective_status_json_out, status_view)
        operator_packet_refresh_result = command_runner(operator_packet_refresh_command, cwd=app_root, text=True)
        if operator_packet_refresh_result.returncode != 0 and post_launch_returncode == 0:
            post_launch_returncode = operator_packet_refresh_result.returncode
        handoff_result = command_runner(handoff_command, cwd=app_root, text=True)
        if handoff_result.returncode != 0 and post_launch_returncode == 0:
            post_launch_returncode = handoff_result.returncode
        consumer_result = command_runner(handoff_consumer_command, cwd=app_root, text=True)
        if consumer_result.returncode != 0 and post_launch_returncode == 0:
            post_launch_returncode = consumer_result.returncode
        artifact_index_result = command_runner(artifact_index_command, cwd=app_root, text=True)
        if artifact_index_result.returncode != 0 and post_launch_returncode == 0:
            post_launch_returncode = artifact_index_result.returncode
    if effective_status_json_out is not None or args.require_ready:
        status_view = _build_status_view(
            output_dir=output_dir,
            output_prefix=args.output_prefix,
            artifact_paths=artifact_paths,
            artifact_index_json=artifact_index_json,
        )
    if effective_status_json_out is not None and status_view is not None:
        write_json(effective_status_json_out, status_view)
    if post_launch_returncode != 0:
        return post_launch_returncode
    if args.require_ready and status_view is not None and not _status_view_ready(status_view):
        return completed.returncode or 1
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
