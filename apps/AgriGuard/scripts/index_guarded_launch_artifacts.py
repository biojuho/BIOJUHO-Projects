from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_peer_module(module_name: str) -> Any:
    script_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script_path}")
    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous_module


run_guarded_launch = _load_peer_module("run_guarded_launch")

REQUIRED_CORE_ARTIFACT_ROLES = (
    "launch_report_json",
    "handoff_json",
    "handoff_markdown",
    "handoff_validation_json",
    "handoff_consumer_json",
)
STATUS_ARTIFACT_ROLE = "status_json"
FRESHNESS_REQUIRED_JSON_ROLES = {
    "status_json",
    "env_validation_json",
    "preflight_json",
    "launch_report_json",
    "operator_packet_json",
    "readiness_summary_json",
    "handoff_json",
    "handoff_validation_json",
    "handoff_consumer_json",
    "ready_gate_json",
}
READY_GATE_COMMAND_REQUIRED_FLAGS = (
    "--status-only",
    "--require-ready",
    "--env-file",
    "--status-json-out",
)
GENERATED_AT_ORDER_RULES = {
    "ready_gate_json": ("handoff_consumer_json",),
}


def _generated_timestamp_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_generated_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workspace_root(app_root: Path) -> Path:
    if app_root.parent.name == "apps":
        return app_root.parents[1]
    return app_root.parent


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError:
        return None


def _artifact_generated_at(path: Path, *, exists: bool) -> str | None:
    if not exists or not path.is_file() or path.suffix.lower() != ".json":
        return None
    payload = _read_json(path)
    generated_at = payload.get("generated_at") if isinstance(payload, dict) else None
    return generated_at if isinstance(generated_at, str) and generated_at else None


def _artifact(role: str, path: Path, required: bool) -> dict[str, object]:
    exists = path.exists()
    return {
        "role": role,
        "path": str(path),
        "required": required,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": _sha256_file(path) if exists and path.is_file() else None,
        "generated_at": _artifact_generated_at(path, exists=exists),
    }


def _quote_powershell_arg(value: str) -> str:
    if value and not any(char.isspace() for char in value) and "'" not in value:
        return value
    return "'" + value.replace("'", "''") + "'"


def _format_powershell_command(command: list[str] | None) -> str | None:
    if not command:
        return None
    return "& " + " ".join(_quote_powershell_arg(str(part)) for part in command)


def _next_commands(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    commands: list[dict[str, str]] = []
    for item in value:
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


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _int_value(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _operator_commands(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    commands: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        command_id = _string_value(item.get("id"))
        command_text = _string_value(item.get("command_text"))
        if command_id is None or command_text is None:
            continue
        summary = {"id": command_id, "command_text": command_text}
        description = _string_value(item.get("description"))
        command_shell = _string_value(item.get("command_shell"))
        if description is not None:
            summary["description"] = description
        if command_shell is not None:
            summary["command_shell"] = command_shell
        commands.append(summary)
    return commands


def _missing_command_flags(command_text: str | None, required_flags: tuple[str, ...]) -> list[str]:
    if command_text is None:
        return list(required_flags)
    return [flag for flag in required_flags if flag not in command_text]


def _stale_generated_at_details(artifacts: list[dict[str, object]]) -> list[dict[str, str]]:
    artifacts_by_role = {str(item.get("role")): item for item in artifacts}
    stale_details: list[dict[str, str]] = []
    for role, source_roles in GENERATED_AT_ORDER_RULES.items():
        artifact = artifacts_by_role.get(role)
        if not artifact or not artifact.get("exists"):
            continue
        artifact_generated_at = artifact.get("generated_at")
        artifact_timestamp = _parse_generated_timestamp(artifact_generated_at)
        if artifact_timestamp is None:
            continue

        latest_source: tuple[str, object, datetime] | None = None
        for source_role in source_roles:
            source = artifacts_by_role.get(source_role)
            if not source or not source.get("exists"):
                continue
            source_generated_at = source.get("generated_at")
            source_timestamp = _parse_generated_timestamp(source_generated_at)
            if source_timestamp is None:
                continue
            if latest_source is None or source_timestamp > latest_source[2]:
                latest_source = (source_role, source_generated_at, source_timestamp)
        if latest_source is not None and artifact_timestamp < latest_source[2]:
            stale_details.append(
                {
                    "role": role,
                    "generated_at": str(artifact_generated_at),
                    "minimum_role": latest_source[0],
                    "minimum_generated_at": str(latest_source[1]),
                }
            )
    return stale_details


def _artifact_index_blocker_class(status: object) -> str:
    return "ready" if status == "pass" else "artifact_index_blocked"


def _artifact_index_recovery_blocker_class(status: object) -> str:
    return "ready" if status in {"pass", "not_required"} else "artifact_index_recovery_blocked"


def _artifact_paths(
    output_dir: Path,
    output_prefix: str,
    status_json: Path | None,
    *,
    handoff_json: Path | None = None,
    handoff_markdown: Path | None = None,
    handoff_validation_json: Path | None = None,
    handoff_consumer_json: Path | None = None,
    ready_gate_json: Path | None = None,
) -> dict[str, Path]:
    paths = run_guarded_launch._artifact_paths(output_dir, output_prefix)
    paths.update(
        {
            "handoff_json": handoff_json or run_guarded_launch._default_handoff_json(output_dir, output_prefix),
            "handoff_markdown": handoff_markdown or run_guarded_launch._default_handoff_markdown(output_dir, output_prefix),
            "handoff_validation_json": handoff_validation_json
            or run_guarded_launch._default_handoff_validation_json(output_dir, output_prefix),
            "handoff_consumer_json": handoff_consumer_json
            or run_guarded_launch._default_handoff_consumer_json(output_dir, output_prefix),
            "ready_gate_json": ready_gate_json or run_guarded_launch._default_ready_gate_json(output_dir, output_prefix),
            "status_json": status_json or (output_dir / f"{output_prefix}-status.json"),
        }
    )
    return paths


def _recovery_command(
    *,
    app_root: Path,
    env_file: Path | None,
    output_dir: Path,
    output_prefix: str,
    status_json: Path | None,
    handoff_json: Path | None,
    handoff_markdown: Path | None,
    handoff_validation_json: Path | None,
    handoff_consumer_json: Path | None,
    ready_gate_json: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "run_guarded_launch.py"),
        "--app-root",
        str(app_root),
        "--env-file",
        str(env_file or run_guarded_launch._default_env_file(app_root)),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
        "--emit-handoff",
    ]
    if status_json is not None:
        command.extend(["--status-json-out", str(status_json)])
    if handoff_json is not None:
        command.extend(["--handoff-json-out", str(handoff_json)])
    if handoff_markdown is not None:
        command.extend(["--handoff-markdown-out", str(handoff_markdown)])
    if handoff_validation_json is not None:
        command.extend(["--handoff-validation-json-out", str(handoff_validation_json)])
    if handoff_consumer_json is not None:
        command.extend(["--handoff-consumer-json-out", str(handoff_consumer_json)])
    if ready_gate_json is not None:
        command.extend(["--handoff-ready-gate-json-out", str(ready_gate_json)])
    return command


def build_index(
    *,
    app_root: Path,
    output_dir: Path,
    output_prefix: str,
    env_file: Path | None = None,
    status_json: Path | None = None,
    handoff_json: Path | None = None,
    handoff_markdown: Path | None = None,
    handoff_validation_json: Path | None = None,
    handoff_consumer_json: Path | None = None,
    ready_gate_json: Path | None = None,
) -> dict[str, object]:
    app_root = app_root.resolve()
    output_dir = output_dir.resolve()
    paths = _artifact_paths(
        output_dir,
        output_prefix,
        status_json.resolve() if status_json else None,
        handoff_json=handoff_json.resolve() if handoff_json else None,
        handoff_markdown=handoff_markdown.resolve() if handoff_markdown else None,
        handoff_validation_json=handoff_validation_json.resolve() if handoff_validation_json else None,
        handoff_consumer_json=handoff_consumer_json.resolve() if handoff_consumer_json else None,
        ready_gate_json=ready_gate_json.resolve() if ready_gate_json else None,
    )
    required_roles = set(REQUIRED_CORE_ARTIFACT_ROLES)
    if status_json is not None:
        required_roles.add(STATUS_ARTIFACT_ROLE)

    artifacts = [
        _artifact(role, paths[role], role in required_roles)
        for role in (
            "status_json",
            "env_validation_json",
            "env_validation_markdown",
            "preflight_json",
            "launch_report_json",
            "operator_packet_json",
            "operator_packet_markdown",
            "operator_env_template",
            "readiness_summary_json",
            "readiness_summary_markdown",
            "handoff_json",
            "handoff_markdown",
            "handoff_validation_json",
            "handoff_consumer_json",
            "ready_gate_json",
        )
    ]
    missing_required = [item["role"] for item in artifacts if item["required"] and not item["exists"]]
    missing_generated_at_roles = [
        str(item["role"])
        for item in artifacts
        if item["role"] in FRESHNESS_REQUIRED_JSON_ROLES and item["exists"] and not item["generated_at"]
    ]
    stale_generated_at_details = _stale_generated_at_details(artifacts)
    stale_generated_at_roles = [detail["role"] for detail in stale_generated_at_details]
    consumer = _read_json(paths["handoff_consumer_json"])
    validation = _read_json(paths["handoff_validation_json"])
    launch = _read_json(paths["launch_report_json"])
    consumer_errors = consumer.get("errors") if isinstance(consumer, dict) and isinstance(consumer.get("errors"), list) else []
    consumer_validation_matches = bool(consumer.get("validation_matches_handoff")) if isinstance(consumer, dict) else False
    consumer_packet_validation_status = consumer.get("packet_validation_status") if isinstance(consumer, dict) else None
    consumer_readiness_action_ids = (
        consumer.get("readiness_operator_action_ids")
        if isinstance(consumer, dict) and isinstance(consumer.get("readiness_operator_action_ids"), list)
        else []
    )
    consumer_readiness_next_actions = (
        _string_list(consumer.get("readiness_next_actions")) if isinstance(consumer, dict) else []
    )
    consumer_readiness_next_commands = (
        _next_commands(consumer.get("readiness_next_commands")) if isinstance(consumer, dict) else []
    )
    consumer_operator_commands = _operator_commands(consumer.get("operator_commands")) if isinstance(consumer, dict) else []
    consumer_ready_gate_command_shell = (
        _string_value(consumer.get("ready_gate_command_shell")) if isinstance(consumer, dict) else None
    )
    consumer_ready_gate_command_text = (
        _string_value(consumer.get("ready_gate_command_text")) if isinstance(consumer, dict) else None
    )
    consumer_ready_gate_command_missing_flags = _missing_command_flags(
        consumer_ready_gate_command_text,
        READY_GATE_COMMAND_REQUIRED_FLAGS,
    )
    consumer_operator_command_count = (
        _int_value(consumer.get("operator_command_count")) if isinstance(consumer, dict) else None
    )
    consumer_operator_command_text_count = (
        _int_value(consumer.get("operator_command_text_count")) if isinstance(consumer, dict) else None
    )
    consumer_handoff_validation_command_shell = (
        _string_value(consumer.get("handoff_validation_command_shell")) if isinstance(consumer, dict) else None
    )
    consumer_handoff_validation_command_text = (
        _string_value(consumer.get("handoff_validation_command_text")) if isinstance(consumer, dict) else None
    )
    consumer_command_metadata_status = (
        "pass"
        if consumer_ready_gate_command_text
        and not consumer_ready_gate_command_missing_flags
        and consumer_operator_command_count is not None
        and consumer_operator_command_count > 0
        and consumer_operator_command_text_count == consumer_operator_command_count
        and len(consumer_operator_commands) == consumer_operator_command_count
        and consumer_handoff_validation_command_text
        else "fail"
    )
    consumer_readiness_operator_packet_consumer_command_metadata_status = (
        _string_value(consumer.get("consumer_readiness_operator_packet_consumer_command_metadata_status"))
        or _string_value(consumer.get("readiness_operator_packet_consumer_command_metadata_status"))
        if isinstance(consumer, dict)
        else None
    )
    validation_status = validation.get("status") if isinstance(validation, dict) else None
    validation_blocker_class = validation.get("blocker_class") if isinstance(validation, dict) else None
    index_status = (
        "pass"
        if not missing_required
        and not missing_generated_at_roles
        and not stale_generated_at_roles
        and isinstance(consumer, dict)
        and consumer_validation_matches
        and consumer_packet_validation_status == "pass"
        and consumer_command_metadata_status == "pass"
        and validation_status == "pass"
        and not consumer_errors
        else "fail"
    )
    recovery_command = (
        None
        if index_status == "pass"
        else _recovery_command(
            app_root=app_root,
            env_file=env_file.resolve() if env_file else None,
            output_dir=output_dir,
            output_prefix=output_prefix,
            status_json=status_json.resolve() if status_json else None,
            handoff_json=handoff_json.resolve() if handoff_json else None,
            handoff_markdown=handoff_markdown.resolve() if handoff_markdown else None,
            handoff_validation_json=handoff_validation_json.resolve() if handoff_validation_json else None,
            handoff_consumer_json=handoff_consumer_json.resolve() if handoff_consumer_json else None,
            ready_gate_json=ready_gate_json.resolve() if ready_gate_json else None,
        )
    )
    recovery_command_text = _format_powershell_command(recovery_command)
    recovery_command_shell = "powershell" if recovery_command_text else None
    recovery_command_status = "not_required" if index_status == "pass" else "pass" if recovery_command else "fail"
    recovery_action = (
        None
        if recovery_command is None
        else "Run the guarded launch wrapper command to regenerate required artifact-index evidence."
    )
    recovery_command_note = (
        None
        if recovery_command is None
        else "Recovery command is present because this artifact index did not meet pass criteria."
    )
    recovery_summary = {
        "required": recovery_command is not None,
        "action": recovery_action,
        "status": recovery_command_status,
        "blocker_class": _artifact_index_recovery_blocker_class(recovery_command_status),
        "note": recovery_command_note,
        "command": recovery_command,
    }
    return {
        "schema_version": 1,
        "generated_at": _generated_timestamp_utc(),
        "status": index_status,
        "blocker_class": _artifact_index_blocker_class(index_status),
        "output_prefix": output_prefix,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "missing_required_roles": missing_required,
        "missing_generated_at_roles": missing_generated_at_roles,
        "stale_generated_at_roles": stale_generated_at_roles,
        "stale_generated_at_details": stale_generated_at_details,
        "consumer_status": consumer.get("status") if isinstance(consumer, dict) else None,
        "consumer_blocker_class": consumer.get("blocker_class") if isinstance(consumer, dict) else None,
        "consumer_validation_matches_handoff": consumer_validation_matches,
        "consumer_packet_validation_status": consumer_packet_validation_status,
        "consumer_packet_evidence_outputs_status": consumer.get("packet_evidence_outputs_status")
        if isinstance(consumer, dict)
        else None,
        "consumer_packet_evidence_outputs_blocker_class": consumer.get("packet_evidence_outputs_blocker_class")
        if isinstance(consumer, dict)
        else None,
        "consumer_packet_markdown_table_status": consumer.get("packet_markdown_table_status")
        if isinstance(consumer, dict)
        else None,
        "consumer_packet_markdown_table_blocker_class": consumer.get("packet_markdown_table_blocker_class")
        if isinstance(consumer, dict)
        else None,
        "consumer_packet_path_mismatch_count": consumer.get("packet_path_mismatch_count")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_operator_action_ids": consumer_readiness_action_ids,
        "consumer_readiness_next_actions": consumer_readiness_next_actions,
        "consumer_readiness_next_commands": consumer_readiness_next_commands,
        "consumer_command_metadata_status": consumer_command_metadata_status,
        "consumer_ready_gate_command_shell": consumer_ready_gate_command_shell,
        "consumer_ready_gate_command_text": consumer_ready_gate_command_text,
        "consumer_ready_gate_command_required_flags": list(READY_GATE_COMMAND_REQUIRED_FLAGS),
        "consumer_ready_gate_command_missing_flags": consumer_ready_gate_command_missing_flags,
        "consumer_operator_command_count": consumer_operator_command_count,
        "consumer_operator_command_text_count": consumer_operator_command_text_count,
        "consumer_operator_commands": consumer_operator_commands,
        "consumer_handoff_validation_command_shell": consumer_handoff_validation_command_shell,
        "consumer_handoff_validation_command_text": consumer_handoff_validation_command_text,
        "consumer_readiness_env_validation_blocker_class": consumer.get("readiness_env_validation_blocker_class")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_env_validation_ready_for_preflight": consumer.get("readiness_env_validation_ready_for_preflight")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_env_validation_placeholder_count": consumer.get("readiness_env_validation_placeholder_count")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_operator_packet_preflight_status": consumer.get("readiness_operator_packet_preflight_status")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_operator_packet_consumer_command_metadata_status": (
            consumer_readiness_operator_packet_consumer_command_metadata_status
        ),
        "consumer_errors": consumer_errors,
        "validation_status": validation_status,
        "validation_blocker_class": validation_blocker_class,
        "launch_status": launch.get("status") if isinstance(launch, dict) else None,
        "launch_stage": launch.get("stage") if isinstance(launch, dict) else None,
        "recovery_action": recovery_action,
        "recovery_command": recovery_command,
        "recovery_command_shell": recovery_command_shell,
        "recovery_command_text": recovery_command_text,
        "recovery_command_status": recovery_command_status,
        "recovery_command_note": recovery_command_note,
        "recovery_summary": recovery_summary,
        "secrets_redacted": True,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(index: dict[str, object]) -> str:
    missing_roles = index.get("missing_required_roles") if isinstance(index.get("missing_required_roles"), list) else []
    missing_generated_at_roles = (
        index.get("missing_generated_at_roles")
        if isinstance(index.get("missing_generated_at_roles"), list)
        else []
    )
    stale_generated_at_roles = (
        index.get("stale_generated_at_roles")
        if isinstance(index.get("stale_generated_at_roles"), list)
        else []
    )
    artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), list) else []
    consumer_errors = index.get("consumer_errors") if isinstance(index.get("consumer_errors"), list) else []
    consumer_error_text = "; ".join(str(error) for error in consumer_errors) if consumer_errors else "-"
    readiness_action_ids = (
        index.get("consumer_readiness_operator_action_ids")
        if isinstance(index.get("consumer_readiness_operator_action_ids"), list)
        else []
    )
    readiness_next_commands = (
        index.get("consumer_readiness_next_commands")
        if isinstance(index.get("consumer_readiness_next_commands"), list)
        else []
    )
    readiness_next_actions = (
        index.get("consumer_readiness_next_actions")
        if isinstance(index.get("consumer_readiness_next_actions"), list)
        else []
    )
    operator_commands = (
        index.get("consumer_operator_commands")
        if isinstance(index.get("consumer_operator_commands"), list)
        else []
    )
    recovery_summary = index.get("recovery_summary") if isinstance(index.get("recovery_summary"), dict) else {}
    recovery_command_text = index.get("recovery_command_text")
    recovery_command_shell = index.get("recovery_command_shell")
    operator_command_count = index.get("consumer_operator_command_count")
    operator_command_text_count = index.get("consumer_operator_command_text_count")
    ready_gate_missing_flags = index.get("consumer_ready_gate_command_missing_flags")
    ready_gate_missing_flags_text = (
        ", ".join(str(flag) for flag in ready_gate_missing_flags)
        if isinstance(ready_gate_missing_flags, list) and ready_gate_missing_flags
        else "-"
    )
    lines = [
        "# AgriGuard Guarded Launch Artifact Index",
        "",
        f"- Generated: `{index.get('generated_at') or '-'}`",
        f"- Status: `{index.get('status')}`",
        f"- Blocker class: `{index.get('blocker_class') or '-'}`",
        f"- Output prefix: `{index.get('output_prefix')}`",
        f"- Launch status: `{index.get('launch_status')}`",
        f"- Validation status: `{index.get('validation_status')}`",
        f"- Validation blocker class: `{index.get('validation_blocker_class') or '-'}`",
        f"- Consumer validation matches handoff: `{str(index.get('consumer_validation_matches_handoff')).lower()}`",
        f"- Consumer packet validation: `{index.get('consumer_packet_validation_status')}`",
        f"- Consumer packet evidence outputs blocker class: `{index.get('consumer_packet_evidence_outputs_blocker_class') or '-'}`",
        f"- Consumer packet Markdown table: `{index.get('consumer_packet_markdown_table_status')}`",
        f"- Consumer packet Markdown table blocker class: `{index.get('consumer_packet_markdown_table_blocker_class') or '-'}`",
        f"- Consumer packet path mismatch count: `{index.get('consumer_packet_path_mismatch_count')}`",
        f"- Consumer readiness action IDs: `{', '.join(str(action_id) for action_id in readiness_action_ids) if readiness_action_ids else '-'}`",
        f"- Consumer readiness next action count: `{len(readiness_next_actions)}`",
        f"- Consumer readiness next command count: `{len(readiness_next_commands)}`",
        f"- Consumer command metadata: `{index.get('consumer_command_metadata_status')}`",
        f"- Consumer ready gate command shell: `{index.get('consumer_ready_gate_command_shell') or '-'}`",
        f"- Consumer ready gate command: `{index.get('consumer_ready_gate_command_text') or '-'}`",
        f"- Consumer ready gate command missing flags: `{ready_gate_missing_flags_text}`",
        f"- Consumer operator command count: `{operator_command_count if isinstance(operator_command_count, int) else '-'}`",
        f"- Consumer operator command text count: `{operator_command_text_count if isinstance(operator_command_text_count, int) else '-'}`",
        f"- Consumer handoff validation command shell: `{index.get('consumer_handoff_validation_command_shell') or '-'}`",
        f"- Consumer handoff validation command: `{index.get('consumer_handoff_validation_command_text') or '-'}`",
        f"- Consumer readiness env validation blocker class: `{index.get('consumer_readiness_env_validation_blocker_class') or '-'}`",
        "- Consumer readiness env validation ready: "
        f"`{str(index.get('consumer_readiness_env_validation_ready_for_preflight')).lower()}`",
        f"- Consumer readiness placeholder count: `{index.get('consumer_readiness_env_validation_placeholder_count')}`",
        f"- Consumer readiness packet preflight status: `{index.get('consumer_readiness_operator_packet_preflight_status')}`",
        f"- Consumer readiness command metadata: `{index.get('consumer_readiness_operator_packet_consumer_command_metadata_status')}`",
        f"- Consumer errors: `{consumer_error_text}`",
        f"- Missing required roles: `{', '.join(str(role) for role in missing_roles) if missing_roles else '-'}`",
        "- Missing generated_at roles: "
        f"`{', '.join(str(role) for role in missing_generated_at_roles) if missing_generated_at_roles else '-'}`",
        "- Stale generated_at roles: "
        f"`{', '.join(str(role) for role in stale_generated_at_roles) if stale_generated_at_roles else '-'}`",
        f"- Recovery summary required: `{str(recovery_summary.get('required')).lower()}`",
        f"- Recovery summary blocker class: `{recovery_summary.get('blocker_class') or '-'}`",
        f"- Recovery action: `{index.get('recovery_action') or '-'}`",
        f"- Recovery command status: `{index.get('recovery_command_status')}`",
        f"- Recovery command note: `{index.get('recovery_command_note') or '-'}`",
        f"- Recovery command shell: `{recovery_command_shell if isinstance(recovery_command_shell, str) else '-'}`",
        f"- Recovery command: `{recovery_command_text if isinstance(recovery_command_text, str) else '-'}`",
        "",
    ]
    if readiness_next_actions:
        lines.extend(["## Consumer Readiness Next Actions", ""])
        for action in readiness_next_actions:
            if isinstance(action, str):
                lines.append(f"- {action}")
        lines.append("")
    if readiness_next_commands:
        lines.extend(["## Consumer Readiness Next Commands", ""])
        for item in readiness_next_commands:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            command = item.get("command")
            if not isinstance(name, str) or not isinstance(command, str):
                continue
            shell = item.get("shell")
            shell_text = f" ({shell})" if isinstance(shell, str) and shell else ""
            lines.append(f"- `{name}`{shell_text}: `{command}`")
        lines.append("")
    if operator_commands:
        lines.extend(["## Consumer Operator Commands", ""])
        for item in operator_commands:
            if not isinstance(item, dict):
                continue
            command_id = item.get("id")
            command_text = item.get("command_text")
            if not isinstance(command_id, str) or not isinstance(command_text, str):
                continue
            shell = item.get("command_shell")
            shell_text = f" ({shell})" if isinstance(shell, str) and shell else ""
            lines.append(f"- `{command_id}`{shell_text}: `{command_text}`")
        lines.append("")
    lines.extend(
        [
            "## Artifacts",
            "",
            "| Role | Required | Exists | Size | Generated | SHA-256 | Path |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{artifact.get('role')}`",
                    str(artifact.get("required")).lower(),
                    str(artifact.get("exists")).lower(),
                    str(artifact.get("size_bytes") if artifact.get("size_bytes") is not None else "-"),
                    f"`{artifact.get('generated_at') or '-'}`",
                    f"`{artifact.get('sha256') or '-'}`",
                    f"`{artifact.get('path')}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    app_root = _default_app_root()
    workspace_root = _workspace_root(app_root)
    parser = argparse.ArgumentParser(description="Index AgriGuard guarded-launch artifacts for an output prefix.")
    parser.add_argument("--app-root", type=Path, default=app_root)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=workspace_root / "var")
    parser.add_argument("--output-prefix", default=run_guarded_launch.DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--status-json", type=Path, default=None)
    parser.add_argument("--handoff-json", type=Path, default=None)
    parser.add_argument("--handoff-markdown", type=Path, default=None)
    parser.add_argument("--handoff-validation-json", type=Path, default=None)
    parser.add_argument("--handoff-consumer-json", type=Path, default=None)
    parser.add_argument("--ready-gate-json", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    parser.add_argument("--exit-zero-on-fail", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    index = build_index(
        app_root=args.app_root,
        env_file=args.env_file,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
        status_json=args.status_json,
        handoff_json=args.handoff_json,
        handoff_markdown=args.handoff_markdown,
        handoff_validation_json=args.handoff_validation_json,
        handoff_consumer_json=args.handoff_consumer_json,
        ready_gate_json=args.ready_gate_json,
    )
    if args.json_out is not None:
        write_json(args.json_out, index)
    if args.markdown_out is not None:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown(index), encoding="utf-8")
    print(json.dumps(index, indent=2, sort_keys=True))
    return 0 if index["status"] == "pass" or args.exit_zero_on_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
