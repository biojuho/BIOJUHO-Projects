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


def _write_operator_packet(path: Path, *, recovery_command_status: str | None = "not_required") -> None:
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
    path.write_text(
        json.dumps(
            {
                "status": "blocked",
                "secrets_redacted": True,
                "operator_actions": [{"id": "set_firebase_service_account_file"}],
                "guarded_launch_evidence": {
                    "artifact_index_readiness_summary": artifact_summary,
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
                "next_commands": [
                    {
                        "name": "validate_env_template",
                        "command": "& python validate_launch_env_template.py",
                        "shell": "powershell",
                    }
                ],
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
    markdown = render_guarded_launch_handoff.render_markdown(handoff)

    assert handoff["status"] == "blocked"
    assert handoff["ready_gate"]["status"] == "fail"
    assert handoff["ready_gate"]["exit_code"] == 1
    assert handoff["external_blocker"]["blocker_class"] == "preflight_blocked"
    assert handoff["external_blocker"]["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert handoff["status_view"]["readiness_summary"]["next_commands"] == [
        {
            "name": "validate_env_template",
            "command": "& python validate_launch_env_template.py",
            "shell": "powershell",
        }
    ]
    assert handoff["packet_validation"]["status"] == "pass"
    assert handoff["packet_validation"]["evidence_outputs_status"] == "pass"
    assert handoff["packet_validation"]["markdown_table_status"] == "pass"
    assert handoff["packet_validation"]["expected_output_key_count"] == 2
    assert handoff["packet_validation"]["artifact_index_recovery_command_status"] == "not_required"
    assert handoff["packet_validation"]["artifact_index_recovery_command_note"] is None
    assert handoff["packet_validation"]["artifact_index_recovery_command_shell"] is None
    assert handoff["packet_validation"]["artifact_index_recovery_command_text"] is None
    assert handoff["packet_validation"]["artifact_index_recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "note": None,
        "command": None,
    }
    ready_command = handoff["ready_gate"]["command"]
    inspect_command = handoff["operator_commands"][0]["command"]
    assert ready_command[1] == str(APP_ROOT / "scripts" / "run_guarded_launch.py")
    assert ready_command[ready_command.index("--app-root") + 1] == str(APP_ROOT.resolve())
    assert ready_command[ready_command.index("--output-dir") + 1] == str(output_dir.resolve())
    assert ready_command[ready_command.index("--output-prefix") + 1] == "blocked"
    assert ready_command[ready_command.index("--status-json-out") + 1] == str(
        (output_dir / "blocked-ready-gate.json").resolve()
    )
    assert "--require-ready" in ready_command
    assert inspect_command[1] == str(APP_ROOT / "scripts" / "run_guarded_launch.py")
    assert inspect_command[inspect_command.index("--app-root") + 1] == str(APP_ROOT.resolve())
    assert inspect_command[inspect_command.index("--output-dir") + 1] == str(output_dir.resolve())
    assert "--require-ready" not in inspect_command
    assert handoff["ready_gate"]["command_shell"] == "powershell"
    assert handoff["ready_gate"]["command_text"] == render_guarded_launch_handoff._format_operator_command(
        ready_command
    )
    assert handoff["operator_commands"][0]["command_shell"] == "powershell"
    assert handoff["operator_commands"][0]["command_text"] == render_guarded_launch_handoff._format_operator_command(
        inspect_command
    )
    assert handoff["operator_commands"][1]["command_shell"] == "powershell"
    assert handoff["operator_commands"][1]["command_text"] == handoff["ready_gate"]["command_text"]
    assert handoff["secrets_redacted"] is True
    assert "Readiness next command count: `1`" in markdown
    assert "`validate_env_template` (powershell): `& python validate_launch_env_template.py`" in markdown


def test_guarded_launch_handoff_notes_deferred_artifact_index_recovery_status(tmp_path: Path) -> None:
    output_dir = tmp_path / "launch-artifacts"
    artifacts = RUN_WRAPPER._artifact_paths(output_dir.resolve(), "blocked")
    artifacts["readiness_summary_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["readiness_summary_json"].write_text(
        json.dumps({"status": "blocked", "blocker_class": "env_shape_blocked", "secrets_redacted": True}),
        encoding="utf-8",
    )
    _write_operator_packet(artifacts["operator_packet_json"], recovery_command_status=None)

    handoff = render_guarded_launch_handoff.build_handoff(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        ready_gate_json=output_dir / "blocked-ready-gate.json",
    )
    markdown = render_guarded_launch_handoff.render_markdown(handoff)

    assert handoff["packet_validation"]["artifact_index_recovery_command_status"] is None
    assert handoff["packet_validation"]["artifact_index_recovery_command_note"] == (
        "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index."
    )
    assert handoff["packet_validation"]["artifact_index_recovery_command_shell"] == "powershell"
    assert handoff["packet_validation"]["artifact_index_recovery_command_text"] == (
        "& python apps/AgriGuard/scripts/run_guarded_launch.py --emit-handoff"
    )
    assert handoff["packet_validation"]["artifact_index_recovery_summary"]["required"] is True
    assert "Artifact index recovery command note: `Artifact index recovery status is resolved" in markdown
    assert "Artifact index recovery command shell: `powershell`" in markdown
    assert "Artifact index recovery command: `& python apps/AgriGuard/scripts/run_guarded_launch.py" in markdown
    assert "Artifact index recovery required: `true`" in markdown


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
    assert payload["validation"]["command"][1] == str(APP_ROOT / "scripts" / "validate_guarded_launch_handoff.py")
    assert payload["validation"]["command"][2] == str(json_out.resolve())
    assert payload["validation"]["command"][-1] == str(validation_json.resolve())
    assert payload["validation"]["command_shell"] == "powershell"
    assert payload["validation"]["command_text"] == render_guarded_launch_handoff._format_operator_command(
        payload["validation"]["command"]
    )
    assert payload["ready_gate"]["command"][1] == str(APP_ROOT / "scripts" / "run_guarded_launch.py")
    assert payload["ready_gate"]["command_shell"] == "powershell"
    assert payload["ready_gate"]["command_text"] == render_guarded_launch_handoff._format_operator_command(
        payload["ready_gate"]["command"]
    )
    assert payload["ready_gate"]["command"][payload["ready_gate"]["command"].index("--app-root") + 1] == str(
        APP_ROOT.resolve()
    )
    assert validation["status"] == "pass"
    assert "Ready gate: `fail`" in markdown
    assert "## Handoff Validation" in markdown
    assert f"Schema JSON: `{APP_ROOT / 'scripts' / 'guarded_launch_handoff.schema.json'}`" in markdown
    assert f"Validation JSON: `{validation_json.resolve()}`" in markdown
    assert "Command shell: `powershell`" in markdown
    assert "Command: `& " in markdown
    assert "validate_guarded_launch_handoff.py" in markdown
    assert "Packet validation: `pass`" in markdown
    assert "Markdown table: `pass`" in markdown
    assert "Artifact index recovery command status: `not_required`" in markdown
    assert "Artifact index recovery command shell: `-`" in markdown
    assert "Readiness action IDs: `fix_env_shape_validation`" in markdown
    assert "Env validation ready for preflight: `False`" in markdown
    assert "Operator packet preflight status: `env_shape_blocked`" in markdown
    assert "`inspect_status` (powershell): `& " in markdown
    assert "`require_ready` (powershell): `& " in markdown
    assert "run_guarded_launch.py" in markdown
