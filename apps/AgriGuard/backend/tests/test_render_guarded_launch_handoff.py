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


def _write_operator_packet(
    path: Path,
    *,
    recovery_command_status: str | None = "not_required",
    preflight_checks: dict[str, object] | None = None,
) -> None:
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
                "preflight_checks": preflight_checks or {},
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
                "next_actions": [
                    "Open the operator packet for exact variables and validation commands.",
                    "Provide a real Firebase Admin service-account .json outside the repo.",
                ],
                "next_commands": [
                    {
                        "name": "validate_env_template",
                        "command": "& python validate_launch_env_template.py",
                        "shell": "powershell",
                    }
                ],
                "reports": {
                    "launch": {
                        "browser_smoke": {
                            "found": False,
                            "path": "var/agriguard-browser-smoke-suite-compose-launch.json",
                            "status": None,
                            "base_url": None,
                            "api_url": None,
                            "mobile": None,
                            "include_unavailable_check": None,
                            "steps_total": None,
                            "steps_passed": None,
                            "steps_failed": None,
                            "checks_total": None,
                            "checks_passed": None,
                            "checks_failed": None,
                            "prechecks_total": None,
                            "prechecks_passed": None,
                            "prechecks_failed": None,
                            "screenshot_artifacts_total": None,
                            "screenshot_artifacts_passed": None,
                            "screenshot_artifacts_failed": None,
                            "failed_step_names": [],
                            "failed_check_names": [],
                            "failed_precheck_names": [],
                        }
                    },
                    "operator_packet": {
                        "operator_action_ids": ["set_firebase_service_account_file"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    _write_operator_packet(
        artifacts["operator_packet_json"],
        preflight_checks={
            "runtime": "compose",
            "docker_checked": True,
            "firebase_credentials_source": "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",
            "firebase_credentials_resolved_path": "C:/secure/missing-firebase.json",
        },
    )
    artifact_index_json = RUN_WRAPPER._default_artifact_index_json(output_dir.resolve(), "blocked")
    artifact_index_json.write_text(
        json.dumps(
            {
                "status": "pass",
                "blocker_class": "ready",
                "missing_required_roles": [],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "recovery_command_status": "not_required",
                "recovery_summary": {
                    "required": False,
                    "action": None,
                    "status": "not_required",
                    "note": None,
                    "command": None,
                },
            }
        ),
        encoding="utf-8",
    )

    handoff = render_guarded_launch_handoff.build_handoff(
        app_root=APP_ROOT,
        output_dir=output_dir,
        output_prefix="blocked",
        ready_gate_json=output_dir / "blocked-ready-gate.json",
    )
    markdown = render_guarded_launch_handoff.render_markdown(handoff)

    assert handoff["status"] == "blocked"
    assert handoff["blocker_class"] == "preflight_blocked"
    assert handoff["ready_gate"]["status"] == "fail"
    assert handoff["ready_gate"]["blocker_class"] == "preflight_blocked"
    assert handoff["ready_gate"]["exit_code"] == 1
    assert handoff["external_blocker"]["blocker_class"] == "preflight_blocked"
    assert handoff["external_blocker"]["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert handoff["external_blocker"]["summary"] == (
        "Real compose/browser launch remains externally blocked until the operator "
        "provides a real Firebase Admin service-account .json at an absolute host path outside the repo."
    )
    assert handoff["status_view"]["readiness_summary"]["next_commands"] == [
        {
            "name": "validate_env_template",
            "command": "& python validate_launch_env_template.py",
            "shell": "powershell",
        }
    ]
    assert handoff["status_view"]["readiness_summary"]["next_actions"] == [
        "Open the operator packet for exact variables and validation commands.",
        "Provide a real Firebase Admin service-account .json outside the repo.",
    ]
    assert handoff["status_view"]["readiness_summary"]["browser_smoke"]["found"] is False
    assert handoff["status_view"]["readiness_summary"]["browser_smoke"]["path"] == (
        "var/agriguard-browser-smoke-suite-compose-launch.json"
    )
    assert handoff["packet_validation"]["status"] == "pass"
    assert handoff["packet_validation"]["blocker_class"] == "ready"
    assert handoff["packet_validation"]["evidence_outputs_status"] == "pass"
    assert handoff["packet_validation"]["evidence_outputs_blocker_class"] == "ready"
    assert handoff["packet_validation"]["markdown_table_status"] == "pass"
    assert handoff["packet_validation"]["markdown_table_blocker_class"] == "ready"
    assert handoff["status_view"]["artifact_index"]["status"] == "pass"
    assert handoff["status_view"]["artifact_index"]["blocker_class"] == "ready"
    assert handoff["status_view"]["operator_packet"]["preflight_checks"]["firebase_credentials_resolved_path"] == (
        "C:/secure/missing-firebase.json"
    )
    assert handoff["packet_validation"]["expected_output_key_count"] == 2
    assert handoff["packet_validation"]["artifact_index_recovery_command_status"] == "not_required"
    assert handoff["packet_validation"]["artifact_index_recovery_command_note"] is None
    assert handoff["packet_validation"]["artifact_index_recovery_command_shell"] is None
    assert handoff["packet_validation"]["artifact_index_recovery_command_text"] is None
    assert handoff["packet_validation"]["artifact_index_recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "blocker_class": "ready",
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
    assert "Artifact index status: `pass`" in markdown
    assert f"Artifact index path: `{artifact_index_json.resolve()}`" in markdown
    assert "Artifact index blocker class: `ready`" in markdown
    assert "Artifact index consumer packet validation: `pass`" in markdown
    assert "Artifact index consumer command metadata: `pass`" in markdown
    assert "Artifact index readiness command metadata: `pass`" in markdown
    assert "Readiness next action count: `2`" in markdown
    assert "Readiness next command count: `1`" in markdown
    assert "## Status Preflight Checks" in markdown
    assert "| `firebase_credentials_resolved_path` | `C:/secure/missing-firebase.json` |" in markdown
    assert "## Status Browser Smoke Evidence" in markdown
    assert "| `found` | `false` |" in markdown
    assert "| `path` | `var/agriguard-browser-smoke-suite-compose-launch.json` |" in markdown
    assert "None/None" not in markdown
    assert "## Readiness Next Actions" in markdown
    assert "- Open the operator packet for exact variables and validation commands." in markdown
    assert "- Provide a real Firebase Admin service-account .json outside the repo." in markdown
    assert "Blocker class: `preflight_blocked`" in markdown
    assert "Ready gate blocker class: `preflight_blocked`" in markdown
    assert "Packet validation blocker class: `ready`" in markdown
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
    assert (
        handoff["packet_validation"]["artifact_index_recovery_summary"]["blocker_class"]
        == "artifact_index_recovery_blocked"
    )
    assert "Artifact index recovery command note: `Artifact index recovery status is resolved" in markdown
    assert "Artifact index recovery command shell: `powershell`" in markdown
    assert "Artifact index recovery command: `& python apps/AgriGuard/scripts/run_guarded_launch.py" in markdown
    assert "Artifact index recovery required: `true`" in markdown
    assert "Evidence outputs blocker class: `ready`" in markdown
    assert "Markdown table blocker class: `ready`" in markdown


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
    assert handoff["blocker_class"] == "ready"
    assert handoff["ready_gate"]["status"] == "pass"
    assert handoff["ready_gate"]["blocker_class"] == "ready"
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
                "next_actions": [
                    "Replace launch env placeholders with real operator values.",
                    "Rerun strict preflight after env validation passes.",
                ],
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
    assert payload["blocker_class"] == "env_shape_blocked"
    assert payload["external_blocker"]["summary"] == (
        "Real compose/browser launch remains externally blocked until the operator "
        "fixes launch env template findings before strict preflight."
    )
    assert payload["ready_gate"]["status"] == "fail"
    assert payload["ready_gate"]["blocker_class"] == "env_shape_blocked"
    assert payload["packet_validation"]["blocker_class"] == "ready"
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
    assert "Ready gate blocker class: `env_shape_blocked`" in markdown
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
    assert "Readiness next action count: `2`" in markdown
    assert "## Readiness Next Actions" in markdown
    assert "- Replace launch env placeholders with real operator values." in markdown
    assert "- Rerun strict preflight after env validation passes." in markdown
    assert "Env validation ready for preflight: `false`" in markdown
    assert "Operator packet preflight status: `env_shape_blocked`" in markdown
    assert "`inspect_status` (powershell): `& " in markdown
    assert "`require_ready` (powershell): `& " in markdown
    assert "run_guarded_launch.py" in markdown
