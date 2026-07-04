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
    return path if path.is_absolute() else handoff_json.resolve().parents[0] / path


def _operator_action_ids(handoff: dict[str, Any]) -> list[str]:
    blocker = handoff.get("external_blocker")
    if not isinstance(blocker, dict):
        return []
    action_ids = blocker.get("operator_action_ids")
    if not isinstance(action_ids, list):
        return []
    return [str(action_id) for action_id in action_ids if isinstance(action_id, str)]


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
    status_view = handoff.get("status_view") if handoff is not None and isinstance(handoff.get("status_view"), dict) else {}
    external_blocker = (
        handoff.get("external_blocker")
        if handoff is not None and isinstance(handoff.get("external_blocker"), dict)
        else {}
    )
    ready_gate_status = ready_gate.get("status")
    pass_ready = handoff_status == "ready" and ready_gate_status == "pass"
    status = "pass" if pass_ready and not errors else "fail"

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
        "blocker_class": status_view.get("blocker_class"),
        "operator_action_ids": _operator_action_ids(handoff or {}),
        "external_blocker_status": external_blocker.get("status"),
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
    if view["status"] == "pass" or args.exit_zero_on_blocked:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
