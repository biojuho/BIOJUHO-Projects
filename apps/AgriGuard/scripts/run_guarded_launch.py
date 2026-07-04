from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


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


def _build_status_view(
    *,
    output_dir: Path,
    output_prefix: str,
    artifact_paths: dict[str, Path],
) -> dict[str, object]:
    launch = _read_json(artifact_paths["launch_report_json"])
    summary = _read_json(artifact_paths["readiness_summary_json"])
    packet = _read_json(artifact_paths["operator_packet_json"])
    action_ids = _operator_action_ids_from_summary(summary) or _operator_action_ids_from_packet(packet)
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
        "artifacts": {key: str(value) for key, value in artifact_paths.items()},
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
        },
        "operator_packet": {
            "found": packet is not None,
            "path": str(artifact_paths["operator_packet_json"]),
            "status": packet.get("status") if packet is not None else None,
            "operator_action_ids": _operator_action_ids_from_packet(packet),
            "secrets_redacted": packet.get("secrets_redacted") if packet is not None else None,
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
        or args.handoff_ready_gate_json_out
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

    if args.status_only:
        status_view = _build_status_view(
            output_dir=output_dir,
            output_prefix=args.output_prefix,
            artifact_paths=artifact_paths,
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
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    completed = command_runner(command, cwd=app_root, text=True)
    status_view = None
    if args.status_json_out or args.require_ready:
        status_view = _build_status_view(
            output_dir=output_dir,
            output_prefix=args.output_prefix,
            artifact_paths=artifact_paths,
        )
    if args.status_json_out and status_view is not None:
        write_json(args.status_json_out.resolve(), status_view)
    if handoff_command is not None:
        handoff_result = command_runner(handoff_command, cwd=app_root, text=True)
        if handoff_result.returncode != 0:
            return handoff_result.returncode
    if handoff_consumer_command is not None:
        consumer_result = command_runner(handoff_consumer_command, cwd=app_root, text=True)
        if consumer_result.returncode != 0:
            return consumer_result.returncode
    if args.require_ready and status_view is not None and not _status_view_ready(status_view):
        return completed.returncode or 1
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
