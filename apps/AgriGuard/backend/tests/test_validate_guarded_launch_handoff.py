from __future__ import annotations

import importlib.util
import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]

HANDOFF_PATH = APP_ROOT / "scripts" / "render_guarded_launch_handoff.py"
HANDOFF_SPEC = importlib.util.spec_from_file_location("render_guarded_launch_handoff", HANDOFF_PATH)
assert HANDOFF_SPEC is not None
render_guarded_launch_handoff = importlib.util.module_from_spec(HANDOFF_SPEC)
assert HANDOFF_SPEC.loader is not None
HANDOFF_SPEC.loader.exec_module(render_guarded_launch_handoff)

VALIDATOR_PATH = APP_ROOT / "scripts" / "validate_guarded_launch_handoff.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_guarded_launch_handoff", VALIDATOR_PATH)
assert VALIDATOR_SPEC is not None
validate_guarded_launch_handoff = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validate_guarded_launch_handoff)

RUN_WRAPPER = render_guarded_launch_handoff.run_guarded_launch


def _write_blocked_handoff(tmp_path: Path) -> dict[str, object]:
    output_dir = tmp_path / "launch-artifacts"
    artifacts = RUN_WRAPPER._artifact_paths(output_dir.resolve(), "blocked")
    artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["launch_report_json"].write_text(
        json.dumps(
            {
                "status": "fail",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
                "results": [{"name": "env_validation"}, {"name": "preflight"}],
            }
        ),
        encoding="utf-8",
    )
    artifacts["readiness_summary_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "preflight_blocked",
                "secrets_redacted": True,
                "reports": {
                    "operator_packet": {
                        "operator_action_ids": ["set_firebase_service_account_file"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return render_guarded_launch_handoff.build_handoff(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        ready_gate_json=output_dir / "blocked-ready-gate.json",
    )


def test_validate_guarded_launch_handoff_accepts_rendered_handoff(tmp_path: Path) -> None:
    handoff = _write_blocked_handoff(tmp_path)

    errors = validate_guarded_launch_handoff.validate_handoff(handoff)

    assert errors == []


def test_validate_guarded_launch_handoff_rejects_shape_drift(tmp_path: Path) -> None:
    handoff = _write_blocked_handoff(tmp_path)
    del handoff["blocker_class"]
    del handoff["ready_gate"]["command"]
    del handoff["operator_commands"][0]["command_text"]
    handoff["unexpected"] = True

    errors = validate_guarded_launch_handoff.validate_handoff(handoff)

    assert "$.blocker_class: missing required property" in errors
    assert "$.ready_gate.command: missing required property" in errors
    assert "$.operator_commands[0].command_text: missing required property" in errors
    assert "$: unexpected properties: unexpected" in errors


def test_validate_guarded_launch_handoff_main_writes_pass_report(tmp_path: Path) -> None:
    handoff = _write_blocked_handoff(tmp_path)
    handoff_json = tmp_path / "handoff.json"
    validation_json = tmp_path / "handoff.validation.json"
    handoff_json.write_text(json.dumps(handoff), encoding="utf-8")

    result = validate_guarded_launch_handoff.main(
        [
            str(handoff_json),
            "--json-out",
            str(validation_json),
        ]
    )

    report = json.loads(validation_json.read_text(encoding="utf-8"))
    assert result == 0
    assert report["status"] == "pass"
    assert report["blocker_class"] == "ready"
    assert report["errors"] == []
    assert report["handoff_sha256"]
    assert report["schema_sha256"]


def test_validate_guarded_launch_handoff_main_fails_on_invalid_report(tmp_path: Path) -> None:
    handoff_json = tmp_path / "handoff.json"
    validation_json = tmp_path / "handoff.validation.json"
    handoff_json.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    result = validate_guarded_launch_handoff.main(
        [
            str(handoff_json),
            "--json-out",
            str(validation_json),
        ]
    )

    report = json.loads(validation_json.read_text(encoding="utf-8"))
    assert result == validate_guarded_launch_handoff.VALIDATION_FAILURE_EXIT_CODE
    assert report["status"] == "fail"
    assert report["blocker_class"] == "guarded_launch_handoff_validation_blocked"
    assert any("missing required property" in error for error in report["errors"])
