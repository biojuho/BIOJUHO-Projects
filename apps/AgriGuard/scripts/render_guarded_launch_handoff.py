from __future__ import annotations

import argparse
import importlib.util
import json
import sys
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


run_guarded_launch = _load_peer_module("run_guarded_launch")
validate_guarded_launch_handoff = _load_peer_module("validate_guarded_launch_handoff")


EXTERNAL_BLOCKER_SUMMARY = (
    "Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin "
    "service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed "
    "origins, and database credentials."
)


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


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _artifact_index_recovery_summary(artifact_index_summary: dict[str, object]) -> dict[str, object]:
    recovery_summary = artifact_index_summary.get("recovery_summary")
    if isinstance(recovery_summary, dict):
        return dict(recovery_summary)
    recovery_command_status = artifact_index_summary.get("recovery_command_status")
    recovery_command_note = (
        None
        if isinstance(recovery_command_status, str)
        else "Artifact index recovery status is resolved after the wrapper emits the artifact index."
    )
    return {
        "required": not isinstance(recovery_command_status, str),
        "action": artifact_index_summary.get("missing_index_action"),
        "status": recovery_command_status if isinstance(recovery_command_status, str) else None,
        "note": recovery_command_note,
        "command": artifact_index_summary.get("missing_index_command"),
    }


def _packet_validation_summary(status_view: dict[str, object]) -> dict[str, object]:
    operator_packet = status_view.get("operator_packet")
    packet_path_value = operator_packet.get("path") if isinstance(operator_packet, dict) else None
    packet_path = Path(packet_path_value) if isinstance(packet_path_value, str) else None
    packet = _read_json(packet_path) if packet_path is not None else None
    evidence = packet.get("guarded_launch_evidence") if isinstance(packet, dict) else None
    evidence = evidence if isinstance(evidence, dict) else {}
    evidence_validation = evidence.get("validation") if isinstance(evidence.get("validation"), dict) else {}
    markdown_validation = (
        evidence.get("markdown_table_validation") if isinstance(evidence.get("markdown_table_validation"), dict) else {}
    )
    artifact_index_summary = (
        evidence.get("artifact_index_readiness_summary")
        if isinstance(evidence.get("artifact_index_readiness_summary"), dict)
        else {}
    )
    evidence_status = evidence_validation.get("status")
    markdown_status = markdown_validation.get("status")
    status_recovery_summary = status_view.get("artifact_index_recovery_summary")
    recovery_summary = (
        dict(status_recovery_summary)
        if isinstance(status_recovery_summary, dict)
        else _artifact_index_recovery_summary(artifact_index_summary)
    )
    recovery_command_status = recovery_summary.get("status")
    recovery_command_note = recovery_summary.get("note")
    expected_output_keys = _string_list(markdown_validation.get("expected_output_keys"))
    status = "pass" if packet is not None and evidence_status == "pass" and markdown_status == "pass" else "fail"
    return {
        "status": status,
        "found": packet is not None,
        "operator_packet_json": str(packet_path) if packet_path is not None else None,
        "evidence_outputs_status": evidence_status if isinstance(evidence_status, str) else None,
        "markdown_table_status": markdown_status if isinstance(markdown_status, str) else None,
        "missing_output_keys": _string_list(evidence_validation.get("missing_output_keys")),
        "empty_output_keys": _string_list(evidence_validation.get("empty_output_keys")),
        "expected_output_key_count": len(expected_output_keys),
        "missing_markdown_rows": _string_list(markdown_validation.get("missing_rows")),
        "extra_markdown_rows": _string_list(markdown_validation.get("extra_rows")),
        "path_mismatch_count": len(markdown_validation.get("path_mismatches"))
        if isinstance(markdown_validation.get("path_mismatches"), list)
        else 0,
        "artifact_index_recovery_command_status": recovery_command_status
        if isinstance(recovery_command_status, str)
        else None,
        "artifact_index_recovery_command_note": recovery_command_note,
        "artifact_index_recovery_summary": recovery_summary,
    }


def _wrapper_status_argv(
    *,
    app_root: Path,
    output_dir: Path,
    output_prefix: str,
    ready_gate_json: Path | None = None,
    require_ready: bool = False,
) -> list[str]:
    argv = [
        sys.executable,
        str(app_root / "scripts" / "run_guarded_launch.py"),
        "--app-root",
        str(app_root),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
        "--status-only",
    ]
    if require_ready:
        argv.append("--require-ready")
    if ready_gate_json is not None:
        argv.extend(["--status-json-out", str(ready_gate_json)])
    return argv


def _external_blocker(status_view: dict[str, object], ready: bool) -> dict[str, object]:
    if ready:
        return {
            "status": "resolved",
            "blocker_class": "ready",
            "operator_action_ids": [],
            "summary": "Selected guarded-launch prefix is ready.",
        }
    return {
        "status": "blocked",
        "blocker_class": status_view.get("blocker_class"),
        "operator_action_ids": status_view.get("operator_action_ids")
        if isinstance(status_view.get("operator_action_ids"), list)
        else [],
        "summary": EXTERNAL_BLOCKER_SUMMARY,
    }


def build_handoff(
    *,
    app_root: Path,
    output_dir: Path,
    output_prefix: str,
    ready_gate_json: Path,
    handoff_json: Path | None = None,
    validation_json: Path | None = None,
) -> dict[str, object]:
    app_root = app_root.resolve()
    output_dir = output_dir.resolve()
    artifact_paths = run_guarded_launch._artifact_paths(output_dir, output_prefix)
    status_view = run_guarded_launch._build_status_view(
        output_dir=output_dir,
        output_prefix=output_prefix,
        artifact_paths=artifact_paths,
        artifact_index_json=run_guarded_launch._default_artifact_index_json(output_dir, output_prefix),
    )
    packet_validation = _packet_validation_summary(status_view)
    ready = run_guarded_launch._status_view_ready(status_view)
    ready_gate = {
        "status": "pass" if ready else "fail",
        "required_status": "ready",
        "required_blocker_class": "ready",
        "exit_code": 0 if ready else 1,
        "status_json_out": str(ready_gate_json),
        "command": _wrapper_status_argv(
            app_root=app_root,
            output_dir=output_dir,
            output_prefix=output_prefix,
            ready_gate_json=ready_gate_json,
            require_ready=True,
        ),
    }
    handoff: dict[str, object] = {
        "schema_version": 1,
        "status": "ready" if ready else "blocked",
        "secrets_redacted": True,
        "output_prefix": output_prefix,
        "output_dir": str(output_dir),
        "status_view": status_view,
        "ready_gate": ready_gate,
        "packet_validation": packet_validation,
        "external_blocker": _external_blocker(status_view, ready),
        "operator_commands": [
            {
                "id": "inspect_status",
                "description": "Print the compact guarded-launch status view.",
                "command": _wrapper_status_argv(
                    app_root=app_root,
                    output_dir=output_dir,
                    output_prefix=output_prefix,
                ),
            },
            {
                "id": "require_ready",
                "description": "Fail closed unless the selected guarded-launch prefix is ready.",
                "command": ready_gate["command"],
            },
        ],
    }
    if handoff_json is not None and validation_json is not None:
        handoff["validation"] = {
            "schema_json": str(validate_guarded_launch_handoff.DEFAULT_SCHEMA_PATH),
            "validation_json": str(validation_json),
            "command": [
                sys.executable,
                str(app_root / "scripts" / "validate_guarded_launch_handoff.py"),
                str(handoff_json),
                "--json-out",
                str(validation_json),
            ],
        }
    return handoff


def render_markdown(handoff: dict[str, object]) -> str:
    status_view = handoff.get("status_view") if isinstance(handoff.get("status_view"), dict) else {}
    launch = status_view.get("launch") if isinstance(status_view.get("launch"), dict) else {}
    readiness_summary = (
        status_view.get("readiness_summary") if isinstance(status_view.get("readiness_summary"), dict) else {}
    )
    ready_gate = handoff.get("ready_gate") if isinstance(handoff.get("ready_gate"), dict) else {}
    packet_validation = handoff.get("packet_validation") if isinstance(handoff.get("packet_validation"), dict) else {}
    external_blocker = handoff.get("external_blocker") if isinstance(handoff.get("external_blocker"), dict) else {}
    commands = handoff.get("operator_commands") if isinstance(handoff.get("operator_commands"), list) else []
    action_ids = external_blocker.get("operator_action_ids")
    action_text = ", ".join(f"`{item}`" for item in action_ids) if isinstance(action_ids, list) and action_ids else "-"
    lines = [
        "# AgriGuard Guarded Launch Handoff",
        "",
        f"- Status: `{handoff.get('status')}`",
        f"- Output prefix: `{handoff.get('output_prefix')}`",
        f"- Launch stage: `{launch.get('stage')}`",
        f"- Blocker class: `{status_view.get('blocker_class')}`",
        f"- Ready gate: `{ready_gate.get('status')}`",
        f"- Packet validation: `{packet_validation.get('status')}`",
        f"- Secrets redacted: `{str(handoff.get('secrets_redacted')).lower()}`",
        "",
        "## Packet Validation",
        "",
        f"- Operator packet JSON: `{packet_validation.get('operator_packet_json')}`",
        f"- Evidence outputs: `{packet_validation.get('evidence_outputs_status')}`",
        f"- Markdown table: `{packet_validation.get('markdown_table_status')}`",
        f"- Expected evidence keys: `{packet_validation.get('expected_output_key_count')}`",
        f"- Missing output keys: `{', '.join(packet_validation.get('missing_output_keys', [])) or '-'}`",
        f"- Empty output keys: `{', '.join(packet_validation.get('empty_output_keys', [])) or '-'}`",
        f"- Missing Markdown rows: `{', '.join(packet_validation.get('missing_markdown_rows', [])) or '-'}`",
        f"- Extra Markdown rows: `{', '.join(packet_validation.get('extra_markdown_rows', [])) or '-'}`",
        f"- Path mismatch count: `{packet_validation.get('path_mismatch_count')}`",
        f"- Artifact index recovery command status: `{packet_validation.get('artifact_index_recovery_command_status')}`",
        f"- Artifact index recovery command note: `{packet_validation.get('artifact_index_recovery_command_note') or '-'}`",
        f"- Artifact index recovery required: `{str((packet_validation.get('artifact_index_recovery_summary') or {}).get('required')).lower()}`",
        f"- Readiness action IDs: `{', '.join(readiness_summary.get('operator_action_ids', [])) or '-'}`",
        f"- Env validation ready for preflight: `{readiness_summary.get('env_validation_ready_for_preflight')}`",
        f"- Env validation placeholder count: `{readiness_summary.get('env_validation_placeholder_count')}`",
        f"- Operator packet preflight status: `{readiness_summary.get('operator_packet_preflight_status')}`",
        "",
        "## External Blocker",
        "",
        f"- Status: `{external_blocker.get('status')}`",
        f"- Operator action IDs: {action_text}",
        f"- Summary: {external_blocker.get('summary')}",
        "",
        "## Operator Commands",
        "",
    ]
    for command in commands:
        if not isinstance(command, dict):
            continue
        argv = command.get("command") if isinstance(command.get("command"), list) else []
        lines.append(f"- `{command.get('id')}`: `{' '.join(str(part) for part in argv)}`")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    app_root = _default_app_root()
    workspace_root = _workspace_root(app_root)
    parser = argparse.ArgumentParser(description="Render an AgriGuard guarded-launch operator handoff.")
    parser.add_argument("--app-root", type=Path, default=app_root)
    parser.add_argument("--output-dir", type=Path, default=workspace_root / "var")
    parser.add_argument("--output-prefix", default=run_guarded_launch.DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--ready-gate-json", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    parser.add_argument("--validation-json-out", type=Path, default=None)
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--exit-zero-on-blocked", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app_root = args.app_root.resolve()
    output_dir = args.output_dir.resolve()
    ready_gate_json = (
        args.ready_gate_json.resolve()
        if args.ready_gate_json
        else output_dir / f"{args.output_prefix}-ready-gate.json"
    )
    json_out = args.json_out.resolve() if args.json_out else output_dir / f"{args.output_prefix}-handoff.json"
    markdown_out = (
        args.markdown_out.resolve()
        if args.markdown_out
        else output_dir / f"{args.output_prefix}-handoff.md"
    )
    validation_json = (
        args.validation_json_out.resolve()
        if args.validation_json_out
        else output_dir / f"{args.output_prefix}-handoff.validation.json"
    )
    handoff = build_handoff(
        app_root=app_root,
        output_dir=output_dir,
        output_prefix=args.output_prefix,
        ready_gate_json=ready_gate_json,
        handoff_json=json_out,
        validation_json=validation_json,
    )
    write_json(json_out, handoff)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(render_markdown(handoff), encoding="utf-8")
    validation_exit_code = 0
    if not args.skip_validation:
        validation_exit_code = validate_guarded_launch_handoff.main(
            [
                str(json_out),
                "--json-out",
                str(validation_json),
            ]
        )
    print(f"wrote guarded launch handoff markdown: {markdown_out}")
    print(f"wrote guarded launch handoff: {json_out}")
    if not args.skip_validation:
        print(f"wrote guarded launch handoff validation: {validation_json}")
    if validation_exit_code != 0:
        return validation_exit_code
    return 0 if args.exit_zero_on_blocked or handoff["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
