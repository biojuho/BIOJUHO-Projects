from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_peer_module(module_name: str) -> Any:
    script_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_guarded_launch_handoff = _load_peer_module("validate_guarded_launch_handoff")


def read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"{path}: file not found"]
    except json.JSONDecodeError as exc:
        return None, [f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"]
    if not isinstance(payload, dict):
        return None, [f"{path}: expected a JSON object"]
    return payload, []


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError:
        return None


def _validation_path_from_handoff(handoff: dict[str, Any], handoff_json: Path) -> Path | None:
    validation = handoff.get("validation")
    if not isinstance(validation, dict) or not isinstance(validation.get("validation_json"), str):
        return None
    path = Path(validation["validation_json"])
    if path.is_absolute():
        return path

    candidates = [Path.cwd() / path, handoff_json.resolve().parent / path]
    output_dir = handoff.get("output_dir")
    if isinstance(output_dir, str):
        output_path = Path(output_dir)
        if output_path.is_absolute():
            candidates.insert(0, output_path.parent / path)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _operator_action_ids(handoff: dict[str, Any]) -> list[str]:
    blocker = handoff.get("external_blocker")
    if not isinstance(blocker, dict):
        return []
    action_ids = blocker.get("operator_action_ids")
    if not isinstance(action_ids, list):
        return []
    return [str(action_id) for action_id in action_ids if isinstance(action_id, str)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


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


def _packet_validation(handoff: dict[str, Any] | None) -> dict[str, Any]:
    packet_validation = handoff.get("packet_validation") if handoff is not None else None
    return packet_validation if isinstance(packet_validation, dict) else {}


def _append_semantic_consistency_errors(
    errors: list[str],
    *,
    handoff_status: object,
    ready_gate_status: object,
    status_view: dict[str, Any],
    external_blocker: dict[str, Any],
    external_action_ids: list[str],
) -> None:
    status_view_status = status_view.get("status")
    status_view_blocker_class = status_view.get("blocker_class")
    status_view_action_ids = _string_list(status_view.get("operator_action_ids"))
    external_blocker_status = external_blocker.get("status")
    external_blocker_class = external_blocker.get("blocker_class")

    if handoff_status in {"ready", "blocked"} and status_view_status != handoff_status:
        errors.append(
            f"status_view status {status_view_status!r} does not match handoff status {handoff_status!r}"
        )
    if external_blocker_class != status_view_blocker_class:
        errors.append(
            "external_blocker blocker_class "
            f"{external_blocker_class!r} does not match status_view blocker_class {status_view_blocker_class!r}"
        )
    if external_action_ids != status_view_action_ids:
        errors.append(
            "external_blocker operator_action_ids "
            f"{external_action_ids!r} do not match status_view operator_action_ids {status_view_action_ids!r}"
        )

    if handoff_status == "ready":
        if ready_gate_status != "pass":
            errors.append(f"ready handoff has ready_gate status {ready_gate_status!r}")
        if external_blocker_status != "resolved":
            errors.append(f"ready handoff has external_blocker status {external_blocker_status!r}")
        if status_view_blocker_class != "ready":
            errors.append(f"ready handoff has status_view blocker_class {status_view_blocker_class!r}")
    elif handoff_status == "blocked":
        if ready_gate_status != "fail":
            errors.append(f"blocked handoff has ready_gate status {ready_gate_status!r}")
        if external_blocker_status != "blocked":
            errors.append(f"blocked handoff has external_blocker status {external_blocker_status!r}")


def build_consumer_view(
    *,
    handoff_json: Path,
    validation_json: Path | None = None,
) -> dict[str, object]:
    handoff, handoff_errors = read_json(handoff_json)
    inferred_validation_json = _validation_path_from_handoff(handoff, handoff_json) if handoff else None
    effective_validation_json = validation_json or inferred_validation_json
    validation, validation_errors = (
        read_json(effective_validation_json) if effective_validation_json is not None else (None, ["validation JSON path missing"])
    )

    errors = handoff_errors + validation_errors
    current_schema_errors = validate_guarded_launch_handoff.validate_handoff(handoff) if handoff is not None else []
    errors.extend(current_schema_errors)
    current_handoff_sha256 = sha256_file(handoff_json)
    validation_status = validation.get("status") if validation is not None else None
    validation_handoff_sha256 = validation.get("handoff_sha256") if validation is not None else None
    validation_matches_handoff = bool(
        current_handoff_sha256
        and isinstance(validation_handoff_sha256, str)
        and validation_handoff_sha256 == current_handoff_sha256
    )
    if validation is not None and validation_status != "pass":
        errors.append("validation report status is not pass")
    if validation is not None and not validation_matches_handoff:
        errors.append("validation report handoff_sha256 does not match current handoff")

    handoff_status = handoff.get("status") if handoff is not None else None
    ready_gate = handoff.get("ready_gate") if handoff is not None and isinstance(handoff.get("ready_gate"), dict) else {}
    validation_block = (
        handoff.get("validation")
        if handoff is not None and isinstance(handoff.get("validation"), dict)
        else {}
    )
    status_view = handoff.get("status_view") if handoff is not None and isinstance(handoff.get("status_view"), dict) else {}
    readiness_summary = (
        status_view.get("readiness_summary")
        if isinstance(status_view.get("readiness_summary"), dict)
        else {}
    )
    artifact_index = (
        status_view.get("artifact_index")
        if isinstance(status_view.get("artifact_index"), dict)
        else {}
    )
    readiness_action_ids = (
        readiness_summary.get("operator_action_ids")
        if isinstance(readiness_summary.get("operator_action_ids"), list)
        else []
    )
    external_blocker = (
        handoff.get("external_blocker")
        if handoff is not None and isinstance(handoff.get("external_blocker"), dict)
        else {}
    )
    external_action_ids = _operator_action_ids(handoff or {})
    ready_gate_status = ready_gate.get("status")
    if handoff is not None:
        _append_semantic_consistency_errors(
            errors,
            handoff_status=handoff_status,
            ready_gate_status=ready_gate_status,
            status_view=status_view,
            external_blocker=external_blocker,
            external_action_ids=external_action_ids,
        )
    packet_validation = _packet_validation(handoff)
    packet_validation_status = packet_validation.get("status")
    packet_recovery_summary = (
        packet_validation.get("artifact_index_recovery_summary")
        if isinstance(packet_validation.get("artifact_index_recovery_summary"), dict)
        else {}
    )
    if handoff is not None and packet_validation_status != "pass":
        errors.append("packet_validation status is not pass")
    pass_ready = handoff_status == "ready" and ready_gate_status == "pass"
    status = "pass" if pass_ready and not errors else "fail"
    readiness_next_commands = _next_commands(readiness_summary.get("next_commands"))
    operator_commands = _operator_commands(handoff.get("operator_commands") if handoff is not None else None)

    return {
        "schema_version": 1,
        "status": status,
        "handoff_json": str(handoff_json),
        "handoff_sha256": current_handoff_sha256,
        "validation_json": str(effective_validation_json) if effective_validation_json is not None else None,
        "validation_status": validation_status,
        "validation_matches_handoff": validation_matches_handoff,
        "handoff_status": handoff_status,
        "ready_gate_status": ready_gate_status,
        "ready_gate_command_shell": _string_value(ready_gate.get("command_shell")),
        "ready_gate_command_text": _string_value(ready_gate.get("command_text")),
        "operator_command_count": len(operator_commands),
        "operator_command_text_count": sum(1 for command in operator_commands if command.get("command_text")),
        "operator_commands": operator_commands,
        "handoff_validation_command_shell": _string_value(validation_block.get("command_shell")),
        "handoff_validation_command_text": _string_value(validation_block.get("command_text")),
        "status_view_status": status_view.get("status"),
        "packet_validation_status": packet_validation_status,
        "packet_evidence_outputs_status": packet_validation.get("evidence_outputs_status"),
        "packet_markdown_table_status": packet_validation.get("markdown_table_status"),
        "packet_path_mismatch_count": packet_validation.get("path_mismatch_count"),
        "packet_artifact_index_recovery_command_status": packet_validation.get(
            "artifact_index_recovery_command_status"
        ),
        "packet_artifact_index_recovery_command_note": packet_validation.get("artifact_index_recovery_command_note"),
        "packet_artifact_index_recovery_command_shell": packet_validation.get(
            "artifact_index_recovery_command_shell"
        ),
        "packet_artifact_index_recovery_command_text": packet_validation.get("artifact_index_recovery_command_text"),
        "packet_artifact_index_recovery_summary": packet_recovery_summary,
        "artifact_index_status": artifact_index.get("status"),
        "consumer_packet_validation_status": artifact_index.get("consumer_packet_validation_status"),
        "consumer_command_metadata_status": artifact_index.get("consumer_command_metadata_status"),
        "consumer_readiness_operator_packet_consumer_command_metadata_status": artifact_index.get(
            "consumer_readiness_operator_packet_consumer_command_metadata_status"
        ),
        "artifact_index_recovery_command_status": artifact_index.get("recovery_command_status"),
        "readiness_operator_action_ids": readiness_action_ids,
        "readiness_next_commands": readiness_next_commands,
        "readiness_env_validation_ready_for_preflight": readiness_summary.get("env_validation_ready_for_preflight"),
        "readiness_env_validation_placeholder_count": readiness_summary.get("env_validation_placeholder_count"),
        "readiness_operator_packet_preflight_status": readiness_summary.get("operator_packet_preflight_status"),
        "readiness_operator_packet_consumer_command_metadata_status": readiness_summary.get(
            "operator_packet_consumer_command_metadata_status"
        ),
        "blocker_class": status_view.get("blocker_class"),
        "status_view_operator_action_ids": _string_list(status_view.get("operator_action_ids")),
        "operator_action_ids": external_action_ids,
        "external_blocker_status": external_blocker.get("status"),
        "external_blocker_class": external_blocker.get("blocker_class"),
        "external_blocker_summary": external_blocker.get("summary"),
        "errors": errors,
        "secrets_redacted": True,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consume an AgriGuard guarded-launch handoff as a compact gate view.")
    parser.add_argument("handoff_json", type=Path)
    parser.add_argument("--validation-json", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--exit-zero-on-blocked", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    view = build_consumer_view(
        handoff_json=args.handoff_json,
        validation_json=args.validation_json,
    )
    if args.json_out is not None:
        write_json(args.json_out, view)
    print(json.dumps(view, indent=2, sort_keys=True))
    if view["status"] == "pass":
        return 0
    if args.exit_zero_on_blocked and not view["errors"] and view.get("handoff_status") == "blocked":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
