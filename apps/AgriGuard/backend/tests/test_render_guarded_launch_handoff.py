from __future__ import annotations

import importlib.util
import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = APP_ROOT / "scripts" / "render_guarded_launch_handoff.py"
SPEC = importlib.util.spec_from_file_location("render_guarded_launch_handoff", SCRIPT_PATH)
assert SPEC is not None
render_guarded_launch_handoff = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(render_guarded_launch_handoff)

RUN_WRAPPER = render_guarded_launch_handoff.run_guarded_launch


def _write_operator_packet(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "blocked",
                "secrets_redacted": True,
                "operator_actions": [{"id": "set_firebase_service_account_file"}],
                "guarded_launch_evidence": {
                    "validation": {
                        "status": "pass",
                        "missing_output_keys": [],
                        "empty_output_keys": [],
                    },
                    "markdown_table_validation": {
                        "status": "pass",
                        "expected_output_keys": ["status_json", "launch_report_json"],
                        "missing_rows": [],
                        "extra_rows": [],
                        "path_mismatches": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_guarded_launch_handoff_blocks_on_prefight_status(tmp_path: Path) -> None:
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
    _write_operator_packet(artifacts["operator_packet_json"])

    handoff = render_guarded_launch_handoff.build_handoff(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        ready_gate_json=output_dir / "blocked-ready-gate.json",
    )

    assert handoff["status"] == "blocked"
    assert handoff["ready_gate"]["status"] == "fail"
    assert handoff["ready_gate"]["exit_code"] == 1
    assert handoff["external_blocker"]["blocker_class"] == "preflight_blocked"
    assert handoff["external_blocker"]["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert handoff["packet_validation"]["status"] == "pass"
    assert handoff["packet_validation"]["evidence_outputs_status"] == "pass"
    assert handoff["packet_validation"]["markdown_table_status"] == "pass"
    assert handoff["packet_validation"]["expected_output_key_count"] == 2
    assert "--require-ready" in handoff["ready_gate"]["command"]
    assert handoff["secrets_redacted"] is True


def test_guarded_launch_handoff_accepts_ready_prefix(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    artifacts = RUN_WRAPPER._artifact_paths(output_dir.resolve(), "ready")
    artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["launch_report_json"].write_text(
        json.dumps(
            {
                "status": "pass",
                "stage": "browser_smoke",
                "stop_reason": None,
                "results": [{"name": "preflight"}, {"name": "compose"}, {"name": "browser_smoke"}],
            }
        ),
        encoding="utf-8",
    )

    handoff = render_guarded_launch_handoff.build_handoff(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="ready",
        ready_gate_json=output_dir / "ready-gate.json",
    )

    assert handoff["status"] == "ready"
    assert handoff["ready_gate"]["status"] == "pass"
    assert handoff["ready_gate"]["exit_code"] == 0
    assert handoff["external_blocker"] == {
        "status": "resolved",
        "blocker_class": "ready",
        "operator_action_ids": [],
        "summary": "Selected guarded-launch prefix is ready.",
    }


def test_guarded_launch_handoff_main_writes_outputs_and_exits_nonzero_when_blocked(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    json_out = tmp_path / "handoff.json"
    markdown_out = tmp_path / "handoff.md"
    validation_json = tmp_path / "handoff.validation.json"
    artifacts = RUN_WRAPPER._artifact_paths(output_dir.resolve(), "blocked")
    artifacts["readiness_summary_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["readiness_summary_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "env_shape_blocked",
                "secrets_redacted": True,
                "reports": {
                    "env_validation": {
                        "ready_for_preflight": False,
                        "placeholder_count": 6,
                    },
                    "operator_packet": {
                        "preflight_status": "env_shape_blocked",
                        "operator_action_ids": ["fix_env_shape_validation"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    _write_operator_packet(artifacts["operator_packet_json"])

    result = render_guarded_launch_handoff.main(
        [
            "--app-root",
            str(APP_ROOT),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "blocked",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--validation-json-out",
            str(validation_json),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    validation = json.loads(validation_json.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 1
    assert payload["status"] == "blocked"
    assert payload["ready_gate"]["status"] == "fail"
    assert payload["validation"]["validation_json"] == str(validation_json.resolve())
    assert payload["validation"]["command"][-1].endswith("handoff.validation.json")
    assert validation["status"] == "pass"
    assert "Ready gate: `fail`" in markdown
    assert "Packet validation: `pass`" in markdown
    assert "Markdown table: `pass`" in markdown
    assert "Readiness action IDs: `fix_env_shape_validation`" in markdown
    assert "Env validation ready for preflight: `False`" in markdown
    assert "Operator packet preflight status: `env_shape_blocked`" in markdown
    assert "run_guarded_launch.py" in markdown
