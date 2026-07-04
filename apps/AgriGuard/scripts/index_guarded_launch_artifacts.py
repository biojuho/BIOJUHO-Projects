from __future__ import annotations

import argparse
import hashlib
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

REQUIRED_CORE_ARTIFACT_ROLES = (
    "launch_report_json",
    "handoff_json",
    "handoff_markdown",
    "handoff_validation_json",
    "handoff_consumer_json",
)
STATUS_ARTIFACT_ROLE = "status_json"


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


def _artifact(role: str, path: Path, required: bool) -> dict[str, object]:
    exists = path.exists()
    return {
        "role": role,
        "path": str(path),
        "required": required,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": _sha256_file(path) if exists and path.is_file() else None,
    }


def _artifact_paths(output_dir: Path, output_prefix: str, status_json: Path | None) -> dict[str, Path]:
    paths = run_guarded_launch._artifact_paths(output_dir, output_prefix)
    paths.update(
        {
            "handoff_json": run_guarded_launch._default_handoff_json(output_dir, output_prefix),
            "handoff_markdown": run_guarded_launch._default_handoff_markdown(output_dir, output_prefix),
            "handoff_validation_json": run_guarded_launch._default_handoff_validation_json(output_dir, output_prefix),
            "handoff_consumer_json": run_guarded_launch._default_handoff_consumer_json(output_dir, output_prefix),
            "ready_gate_json": run_guarded_launch._default_ready_gate_json(output_dir, output_prefix),
            "status_json": status_json or (output_dir / f"{output_prefix}-status.json"),
        }
    )
    return paths


def _recovery_command(
    *,
    app_root: Path,
    output_dir: Path,
    output_prefix: str,
    status_json: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(app_root / "scripts" / "run_guarded_launch.py"),
        "--app-root",
        str(app_root),
        "--env-file",
        str(run_guarded_launch._default_env_file(app_root)),
        "--output-dir",
        str(output_dir),
        "--output-prefix",
        output_prefix,
        "--emit-handoff",
    ]
    if status_json is not None:
        command.extend(["--status-json-out", str(status_json)])
    return command


def build_index(
    *,
    app_root: Path,
    output_dir: Path,
    output_prefix: str,
    status_json: Path | None = None,
) -> dict[str, object]:
    app_root = app_root.resolve()
    output_dir = output_dir.resolve()
    paths = _artifact_paths(output_dir, output_prefix, status_json.resolve() if status_json else None)
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
    validation_status = validation.get("status") if isinstance(validation, dict) else None
    index_status = (
        "pass"
        if not missing_required
        and isinstance(consumer, dict)
        and consumer_validation_matches
        and consumer_packet_validation_status == "pass"
        and validation_status == "pass"
        and not consumer_errors
        else "fail"
    )
    recovery_command = (
        None
        if index_status == "pass"
        else _recovery_command(
            app_root=app_root,
            output_dir=output_dir,
            output_prefix=output_prefix,
            status_json=status_json.resolve() if status_json else None,
        )
    )
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
        "note": recovery_command_note,
        "command": recovery_command,
    }
    return {
        "schema_version": 1,
        "status": index_status,
        "output_prefix": output_prefix,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "missing_required_roles": missing_required,
        "consumer_status": consumer.get("status") if isinstance(consumer, dict) else None,
        "consumer_blocker_class": consumer.get("blocker_class") if isinstance(consumer, dict) else None,
        "consumer_validation_matches_handoff": consumer_validation_matches,
        "consumer_packet_validation_status": consumer_packet_validation_status,
        "consumer_packet_evidence_outputs_status": consumer.get("packet_evidence_outputs_status")
        if isinstance(consumer, dict)
        else None,
        "consumer_packet_markdown_table_status": consumer.get("packet_markdown_table_status")
        if isinstance(consumer, dict)
        else None,
        "consumer_packet_path_mismatch_count": consumer.get("packet_path_mismatch_count")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_operator_action_ids": consumer_readiness_action_ids,
        "consumer_readiness_env_validation_ready_for_preflight": consumer.get("readiness_env_validation_ready_for_preflight")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_env_validation_placeholder_count": consumer.get("readiness_env_validation_placeholder_count")
        if isinstance(consumer, dict)
        else None,
        "consumer_readiness_operator_packet_preflight_status": consumer.get("readiness_operator_packet_preflight_status")
        if isinstance(consumer, dict)
        else None,
        "consumer_errors": consumer_errors,
        "validation_status": validation_status,
        "launch_status": launch.get("status") if isinstance(launch, dict) else None,
        "launch_stage": launch.get("stage") if isinstance(launch, dict) else None,
        "recovery_action": recovery_action,
        "recovery_command": recovery_command,
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
    artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), list) else []
    readiness_action_ids = (
        index.get("consumer_readiness_operator_action_ids")
        if isinstance(index.get("consumer_readiness_operator_action_ids"), list)
        else []
    )
    recovery_summary = index.get("recovery_summary") if isinstance(index.get("recovery_summary"), dict) else {}
    recovery_command = index.get("recovery_command") if isinstance(index.get("recovery_command"), list) else []
    lines = [
        "# AgriGuard Guarded Launch Artifact Index",
        "",
        f"- Status: `{index.get('status')}`",
        f"- Output prefix: `{index.get('output_prefix')}`",
        f"- Launch status: `{index.get('launch_status')}`",
        f"- Validation status: `{index.get('validation_status')}`",
        f"- Consumer validation matches handoff: `{str(index.get('consumer_validation_matches_handoff')).lower()}`",
        f"- Consumer packet validation: `{index.get('consumer_packet_validation_status')}`",
        f"- Consumer packet Markdown table: `{index.get('consumer_packet_markdown_table_status')}`",
        f"- Consumer packet path mismatch count: `{index.get('consumer_packet_path_mismatch_count')}`",
        f"- Consumer readiness action IDs: `{', '.join(str(action_id) for action_id in readiness_action_ids) if readiness_action_ids else '-'}`",
        f"- Consumer readiness env validation ready: `{index.get('consumer_readiness_env_validation_ready_for_preflight')}`",
        f"- Consumer readiness placeholder count: `{index.get('consumer_readiness_env_validation_placeholder_count')}`",
        f"- Consumer readiness packet preflight status: `{index.get('consumer_readiness_operator_packet_preflight_status')}`",
        f"- Missing required roles: `{', '.join(str(role) for role in missing_roles) if missing_roles else '-'}`",
        f"- Recovery summary required: `{str(recovery_summary.get('required')).lower()}`",
        f"- Recovery action: `{index.get('recovery_action') or '-'}`",
        f"- Recovery command status: `{index.get('recovery_command_status')}`",
        f"- Recovery command note: `{index.get('recovery_command_note') or '-'}`",
        f"- Recovery command: `{' '.join(str(part) for part in recovery_command) if recovery_command else '-'}`",
        "",
        "## Artifacts",
        "",
        "| Role | Required | Exists | Size | SHA-256 | Path |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
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
    parser.add_argument("--output-dir", type=Path, default=workspace_root / "var")
    parser.add_argument("--output-prefix", default=run_guarded_launch.DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--status-json", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    parser.add_argument("--exit-zero-on-fail", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    index = build_index(
        app_root=args.app_root,
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
        status_json=args.status_json,
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
