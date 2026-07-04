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
    required_roles = {
        "launch_report_json",
        "handoff_json",
        "handoff_markdown",
        "handoff_validation_json",
        "handoff_consumer_json",
    }
    if status_json is not None:
        required_roles.add("status_json")

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
    validation_status = validation.get("status") if isinstance(validation, dict) else None
    index_status = (
        "pass"
        if not missing_required
        and isinstance(consumer, dict)
        and consumer_validation_matches
        and validation_status == "pass"
        and not consumer_errors
        else "fail"
    )
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
        "consumer_errors": consumer_errors,
        "validation_status": validation_status,
        "launch_status": launch.get("status") if isinstance(launch, dict) else None,
        "launch_stage": launch.get("stage") if isinstance(launch, dict) else None,
        "secrets_redacted": True,
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    app_root = _default_app_root()
    workspace_root = _workspace_root(app_root)
    parser = argparse.ArgumentParser(description="Index AgriGuard guarded-launch artifacts for an output prefix.")
    parser.add_argument("--app-root", type=Path, default=app_root)
    parser.add_argument("--output-dir", type=Path, default=workspace_root / "var")
    parser.add_argument("--output-prefix", default=run_guarded_launch.DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--status-json", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
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
    print(json.dumps(index, indent=2, sort_keys=True))
    return 0 if index["status"] == "pass" or args.exit_zero_on_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
