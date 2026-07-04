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

CONSUMER_PATH = APP_ROOT / "scripts" / "consume_guarded_launch_handoff.py"
CONSUMER_SPEC = importlib.util.spec_from_file_location("consume_guarded_launch_handoff", CONSUMER_PATH)
assert CONSUMER_SPEC is not None
consume_guarded_launch_handoff = importlib.util.module_from_spec(CONSUMER_SPEC)
assert CONSUMER_SPEC.loader is not None
CONSUMER_SPEC.loader.exec_module(consume_guarded_launch_handoff)

RUN_WRAPPER = render_guarded_launch_handoff.run_guarded_launch


def _write_launch_report(output_dir: Path, prefix: str, payload: dict[str, object]) -> None:
    artifacts = RUN_WRAPPER._artifact_paths(output_dir.resolve(), prefix)
    artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["launch_report_json"].write_text(json.dumps(payload), encoding="utf-8")


def _write_readiness_summary(output_dir: Path, prefix: str, payload: dict[str, object]) -> None:
    artifacts = RUN_WRAPPER._artifact_paths(output_dir.resolve(), prefix)
    artifacts["readiness_summary_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["readiness_summary_json"].write_text(json.dumps(payload), encoding="utf-8")


def _write_operator_packet(
    output_dir: Path,
    prefix: str,
    *,
    evidence_status: str = "pass",
    markdown_status: str = "pass",
    recovery_command_status: str | None = "not_required",
) -> None:
    artifacts = RUN_WRAPPER._artifact_paths(output_dir.resolve(), prefix)
    recovery_summary = (
        {
            "required": False,
            "action": None,
            "status": recovery_command_status,
            "note": None,
            "command": None,
        }
        if recovery_command_status is not None
        else {
            "required": True,
            "action": "Run the guarded launch wrapper command to generate the artifact index evidence.",
            "status": None,
            "note": "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index.",
            "command": "python apps/AgriGuard/scripts/run_guarded_launch.py --emit-handoff",
        }
    )
    artifact_summary = (
        {"recovery_command_status": recovery_command_status, "recovery_summary": recovery_summary}
        if recovery_command_status is not None
        else {"recovery_summary": recovery_summary}
    )
    artifacts["operator_packet_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["operator_packet_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "secrets_redacted": True,
                "operator_actions": [{"id": "set_firebase_service_account_file"}],
                "guarded_launch_evidence": {
                    "artifact_index_readiness_summary": artifact_summary,
                    "validation": {
                        "status": evidence_status,
                        "missing_output_keys": [] if evidence_status == "pass" else ["handoff_json"],
                        "empty_output_keys": [],
                    },
                    "markdown_table_validation": {
                        "status": markdown_status,
                        "expected_output_keys": ["status_json", "launch_report_json"],
                        "missing_rows": [] if markdown_status == "pass" else ["handoff_json"],
                        "extra_rows": [],
                        "path_mismatches": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def _write_handoff_and_validation(tmp_path: Path, prefix: str) -> tuple[Path, Path]:
    output_dir = tmp_path / "launch-artifacts"
    handoff_json = tmp_path / f"{prefix}-handoff.json"
    validation_json = tmp_path / f"{prefix}-handoff.validation.json"
    handoff = render_guarded_launch_handoff.build_handoff(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix=prefix,
        ready_gate_json=output_dir / f"{prefix}-ready-gate.json",
        handoff_json=handoff_json,
        validation_json=validation_json,
    )
    handoff_json.write_text(json.dumps(handoff), encoding="utf-8")
    assert validate_guarded_launch_handoff.main([str(handoff_json), "--json-out", str(validation_json)]) == 0
    return handoff_json, validation_json


def test_consume_guarded_launch_handoff_passes_ready_handoff(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_launch_report(
        output_dir,
        "ready",
        {
            "status": "pass",
            "stage": "browser_smoke",
            "stop_reason": None,
            "results": [{"name": "preflight"}, {"name": "compose"}, {"name": "browser_smoke"}],
        },
    )
    _write_operator_packet(output_dir, "ready")
    handoff_json, validation_json = _write_handoff_and_validation(tmp_path, "ready")

    view = consume_guarded_launch_handoff.build_consumer_view(
        handoff_json=handoff_json,
        validation_json=validation_json,
    )

    assert view["status"] == "pass"
    assert view["handoff_status"] == "ready"
    assert view["ready_gate_status"] == "pass"
    assert view["packet_validation_status"] == "pass"
    assert view["packet_evidence_outputs_status"] == "pass"
    assert view["packet_markdown_table_status"] == "pass"
    assert view["packet_artifact_index_recovery_command_status"] == "not_required"
    assert view["packet_artifact_index_recovery_command_note"] is None
    assert view["packet_artifact_index_recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "note": None,
        "command": None,
    }
    assert view["validation_matches_handoff"] is True
    assert view["errors"] == []


def test_consume_guarded_launch_handoff_fails_blocked_handoff(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_readiness_summary(
        output_dir,
        "blocked",
        {
            "status": "blocked",
            "blocker_class": "preflight_blocked",
            "secrets_redacted": True,
            "reports": {
                "env_validation": {
                    "ready_for_preflight": False,
                    "placeholder_count": 6,
                },
                "operator_packet": {
                    "preflight_status": "env_shape_blocked",
                    "operator_action_ids": ["set_firebase_service_account_file"],
                },
            },
        },
    )
    _write_operator_packet(output_dir, "blocked")
    handoff_json, validation_json = _write_handoff_and_validation(tmp_path, "blocked")

    view = consume_guarded_launch_handoff.build_consumer_view(
        handoff_json=handoff_json,
        validation_json=validation_json,
    )

    assert view["status"] == "fail"
    assert view["handoff_status"] == "blocked"
    assert view["blocker_class"] == "preflight_blocked"
    assert view["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert view["packet_validation_status"] == "pass"
    assert view["packet_artifact_index_recovery_command_status"] == "not_required"
    assert view["packet_artifact_index_recovery_command_note"] is None
    assert view["packet_artifact_index_recovery_summary"]["required"] is False
    assert view["readiness_operator_action_ids"] == ["set_firebase_service_account_file"]
    assert view["readiness_env_validation_ready_for_preflight"] is False
    assert view["readiness_env_validation_placeholder_count"] == 6
    assert view["readiness_operator_packet_preflight_status"] == "env_shape_blocked"
    assert view["validation_matches_handoff"] is True


def test_consume_guarded_launch_handoff_exposes_deferred_recovery_status_note(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_readiness_summary(
        output_dir,
        "blocked",
        {
            "status": "blocked",
            "blocker_class": "env_shape_blocked",
            "secrets_redacted": True,
            "reports": {},
        },
    )
    _write_operator_packet(output_dir, "blocked", recovery_command_status=None)
    handoff_json, validation_json = _write_handoff_and_validation(tmp_path, "blocked")

    view = consume_guarded_launch_handoff.build_consumer_view(
        handoff_json=handoff_json,
        validation_json=validation_json,
    )

    assert view["packet_artifact_index_recovery_command_status"] is None
    assert view["packet_artifact_index_recovery_command_note"] == (
        "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index."
    )
    assert view["packet_artifact_index_recovery_summary"]["required"] is True


def test_consume_guarded_launch_handoff_fails_packet_validation_drift(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_readiness_summary(
        output_dir,
        "blocked",
        {
            "status": "blocked",
            "blocker_class": "preflight_blocked",
            "secrets_redacted": True,
            "reports": {},
        },
    )
    _write_operator_packet(output_dir, "blocked", markdown_status="fail")
    handoff_json, validation_json = _write_handoff_and_validation(tmp_path, "blocked")

    view = consume_guarded_launch_handoff.build_consumer_view(
        handoff_json=handoff_json,
        validation_json=validation_json,
    )

    assert view["status"] == "fail"
    assert view["packet_validation_status"] == "fail"
    assert view["packet_markdown_table_status"] == "fail"
    assert "packet_validation status is not pass" in view["errors"]


def test_consume_guarded_launch_handoff_fails_stale_validation_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_launch_report(
        output_dir,
        "ready",
        {
            "status": "pass",
            "stage": "browser_smoke",
            "stop_reason": None,
            "results": [{"name": "preflight"}, {"name": "compose"}, {"name": "browser_smoke"}],
        },
    )
    _write_operator_packet(output_dir, "ready")
    handoff_json, validation_json = _write_handoff_and_validation(tmp_path, "ready")
    payload = json.loads(handoff_json.read_text(encoding="utf-8"))
    payload["output_prefix"] = "tampered"
    handoff_json.write_text(json.dumps(payload), encoding="utf-8")

    view = consume_guarded_launch_handoff.build_consumer_view(
        handoff_json=handoff_json,
        validation_json=validation_json,
    )

    assert view["status"] == "fail"
    assert view["validation_matches_handoff"] is False
    assert "validation report handoff_sha256 does not match current handoff" in view["errors"]


def test_consume_guarded_launch_handoff_main_writes_output_and_exits_nonzero_for_blocked(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    output_json = tmp_path / "consumer.json"
    _write_readiness_summary(
        output_dir,
        "blocked",
        {
            "status": "blocked",
            "blocker_class": "env_shape_blocked",
            "secrets_redacted": True,
            "reports": {},
        },
    )
    _write_operator_packet(output_dir, "blocked")
    handoff_json, validation_json = _write_handoff_and_validation(tmp_path, "blocked")

    result = consume_guarded_launch_handoff.main(
        [
            str(handoff_json),
            "--validation-json",
            str(validation_json),
            "--json-out",
            str(output_json),
        ]
    )

    view = json.loads(output_json.read_text(encoding="utf-8"))
    assert result == 1
    assert view["status"] == "fail"
    assert view["blocker_class"] == "env_shape_blocked"


def test_consume_guarded_launch_handoff_exit_zero_on_clean_blocked_only(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    _write_readiness_summary(
        output_dir,
        "blocked",
        {
            "status": "blocked",
            "blocker_class": "env_shape_blocked",
            "secrets_redacted": True,
            "reports": {},
        },
    )
    _write_operator_packet(output_dir, "blocked")
    handoff_json, validation_json = _write_handoff_and_validation(tmp_path, "blocked")

    blocked_result = consume_guarded_launch_handoff.main(
        [
            str(handoff_json),
            "--validation-json",
            str(validation_json),
            "--exit-zero-on-blocked",
        ]
    )

    payload = json.loads(handoff_json.read_text(encoding="utf-8"))
    payload["output_prefix"] = "tampered"
    handoff_json.write_text(json.dumps(payload), encoding="utf-8")
    stale_result = consume_guarded_launch_handoff.main(
        [
            str(handoff_json),
            "--validation-json",
            str(validation_json),
            "--exit-zero-on-blocked",
        ]
    )

    assert blocked_result == 0
    assert stale_result == 1
