from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = APP_ROOT / "scripts" / "run_guarded_launch.py"
SPEC = importlib.util.spec_from_file_location("run_guarded_launch", SCRIPT_PATH)
assert SPEC is not None
run_guarded_launch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_guarded_launch)


def _arg_after(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def test_guarded_launch_dry_run_prints_canonical_command(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    command = payload["command"]
    assert result == 0
    assert command[:2] == [sys.executable, str(app_root.resolve() / "scripts" / "launch_compose.py")]
    assert _arg_after(command, "--app-root") == str(app_root.resolve())
    assert "--validate-env-file-shape" in command
    assert "--run-browser-smoke" in command
    assert _arg_after(command, "--env-file") == str(env_file.resolve())
    assert _arg_after(command, "--launch-report-json") == str(output_dir.resolve() / "release-check-launch-report.json")
    assert _arg_after(command, "--readiness-summary-json") == str(
        output_dir.resolve() / "release-check-readiness-summary.json"
    )
    assert payload["artifacts"]["operator_env_template"] == str(
        output_dir.resolve() / "release-check.env.template"
    )
    assert payload["run_browser_smoke"] is True


def test_guarded_launch_dry_run_can_plan_handoff_outputs(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"
    output_dir.mkdir()
    (output_dir / "release-check-artifact-index.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "recovery_command_status": "not_required",
                "consumer_readiness_operator_action_ids": ["fix_env_shape_validation"],
                "consumer_readiness_next_commands": [
                    {
                        "name": "validate_env_template",
                        "command": "& python validate_launch_env_template.py",
                        "shell": "powershell",
                    }
                ],
                "consumer_readiness_env_validation_ready_for_preflight": False,
                "consumer_readiness_env_validation_placeholder_count": 6,
                "consumer_readiness_operator_packet_preflight_status": "env_shape_blocked",
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

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--emit-handoff",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    delegated_launch_command = payload["command"]
    assert payload["handoff_json"] == str(output_dir.resolve() / "release-check-handoff.json")
    assert payload["handoff_markdown"] == str(output_dir.resolve() / "release-check-handoff.md")
    assert payload["handoff_validation_json"] == str(output_dir.resolve() / "release-check-handoff.validation.json")
    assert payload["handoff_consumer_json"] == str(output_dir.resolve() / "release-check-handoff.consumer.json")
    assert payload["handoff_ready_gate_json"] == str(output_dir.resolve() / "release-check-ready-gate.json")
    assert payload["artifact_index_json"] == str(output_dir.resolve() / "release-check-artifact-index.json")
    assert payload["artifact_index_markdown"] == str(output_dir.resolve() / "release-check-artifact-index.md")
    assert payload["artifact_index_readiness_summary"] == {
        "found": True,
        "path": str(output_dir.resolve() / "release-check-artifact-index.json"),
        "status": "pass",
        "consumer_packet_validation_status": "pass",
        "consumer_command_metadata_status": "pass",
        "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
        "recovery_command_status": "not_required",
        "recovery_command_note": None,
        "recovery_summary": {
            "required": False,
            "action": None,
            "status": "not_required",
            "note": None,
            "command": None,
        },
        "operator_action_ids": ["fix_env_shape_validation"],
        "next_commands": [
            {
                "name": "validate_env_template",
                "command": "& python validate_launch_env_template.py",
                "shell": "powershell",
            }
        ],
        "env_validation_ready_for_preflight": False,
        "env_validation_placeholder_count": 6,
        "operator_packet_preflight_status": "env_shape_blocked",
        "missing_index_action": None,
        "missing_index_command": None,
    }
    assert payload["handoff_command"][:2] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py"),
    ]
    assert payload["handoff_consumer_command"][:2] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py"),
    ]
    assert payload["artifact_index_command"][:2] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py"),
    ]
    assert _arg_after(delegated_launch_command, "--guarded-output-dir") == str(output_dir.resolve())
    assert _arg_after(delegated_launch_command, "--guarded-output-prefix") == "release-check"
    assert _arg_after(delegated_launch_command, "--guarded-status-json") == str(
        output_dir.resolve() / "release-check-status.json"
    )
    assert _arg_after(delegated_launch_command, "--guarded-handoff-json") == str(
        output_dir.resolve() / "release-check-handoff.json"
    )
    assert _arg_after(delegated_launch_command, "--guarded-handoff-markdown") == str(
        output_dir.resolve() / "release-check-handoff.md"
    )
    assert _arg_after(delegated_launch_command, "--guarded-handoff-validation-json") == str(
        output_dir.resolve() / "release-check-handoff.validation.json"
    )
    assert _arg_after(delegated_launch_command, "--guarded-handoff-consumer-json") == str(
        output_dir.resolve() / "release-check-handoff.consumer.json"
    )
    assert _arg_after(delegated_launch_command, "--guarded-ready-gate-json") == str(
        output_dir.resolve() / "release-check-ready-gate.json"
    )
    assert payload["operator_packet_refresh_command"][:2] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "render_launch_operator_packet.py"),
    ]
    assert "--exit-zero-on-blocked" in payload["handoff_command"]
    assert "--exit-zero-on-blocked" in payload["handoff_consumer_command"]
    assert "--exit-zero-on-blocked" in payload["operator_packet_refresh_command"]
    assert _arg_after(payload["artifact_index_command"], "--json-out") == str(
        output_dir.resolve() / "release-check-artifact-index.json"
    )
    assert _arg_after(payload["artifact_index_command"], "--env-file") == str(env_file.resolve())
    assert _arg_after(payload["artifact_index_command"], "--markdown-out") == str(
        output_dir.resolve() / "release-check-artifact-index.md"
    )
    assert _arg_after(payload["artifact_index_command"], "--status-json") == str(
        output_dir.resolve() / "release-check-status.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--app-root") == str(app_root.resolve())
    assert _arg_after(payload["operator_packet_refresh_command"], "--preflight-json") == str(
        output_dir.resolve() / "release-check-preflight.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--env-validation-json") == str(
        output_dir.resolve() / "release-check-env-validation.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--env-validation-markdown") == str(
        output_dir.resolve() / "release-check-env-validation.md"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--env-file") == str(env_file.resolve())
    assert _arg_after(payload["operator_packet_refresh_command"], "--json-out") == str(
        output_dir.resolve() / "release-check-operator-packet.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--markdown-out") == str(
        output_dir.resolve() / "release-check-operator-packet.md"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--env-template-out") == str(
        output_dir.resolve() / "release-check.env.template"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--compose-launch-report-json") == str(
        output_dir.resolve() / "release-check-launch-report.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--readiness-summary-json") == str(
        output_dir.resolve() / "release-check-readiness-summary.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--readiness-summary-markdown") == str(
        output_dir.resolve() / "release-check-readiness-summary.md"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-output-dir") == str(output_dir.resolve())
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-output-prefix") == "release-check"
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-status-json") == str(
        output_dir.resolve() / "release-check-status.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-handoff-json") == str(
        output_dir.resolve() / "release-check-handoff.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-handoff-markdown") == str(
        output_dir.resolve() / "release-check-handoff.md"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-handoff-validation-json") == str(
        output_dir.resolve() / "release-check-handoff.validation.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-handoff-consumer-json") == str(
        output_dir.resolve() / "release-check-handoff.consumer.json"
    )
    assert _arg_after(payload["operator_packet_refresh_command"], "--guarded-ready-gate-json") == str(
        output_dir.resolve() / "release-check-ready-gate.json"
    )


def test_guarded_launch_artifact_index_uses_custom_handoff_outputs(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"
    custom_dir = tmp_path / "custom-handoff"
    handoff_json = custom_dir / "current.handoff.json"
    handoff_markdown = custom_dir / "current.handoff.md"
    handoff_validation_json = custom_dir / "current.handoff.validation.json"
    handoff_consumer_json = custom_dir / "current.handoff.consumer.json"
    ready_gate_json = custom_dir / "current.ready-gate.json"

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--handoff-json-out",
            str(handoff_json),
            "--handoff-markdown-out",
            str(handoff_markdown),
            "--handoff-validation-json-out",
            str(handoff_validation_json),
            "--handoff-consumer-json-out",
            str(handoff_consumer_json),
            "--handoff-ready-gate-json-out",
            str(ready_gate_json),
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    delegated_launch_command = payload["command"]
    artifact_index_command = payload["artifact_index_command"]
    refresh_command = payload["operator_packet_refresh_command"]
    assert result == 0
    assert _arg_after(delegated_launch_command, "--guarded-handoff-json") == str(handoff_json.resolve())
    assert _arg_after(delegated_launch_command, "--guarded-handoff-markdown") == str(handoff_markdown.resolve())
    assert _arg_after(delegated_launch_command, "--guarded-handoff-validation-json") == str(
        handoff_validation_json.resolve()
    )
    assert _arg_after(delegated_launch_command, "--guarded-handoff-consumer-json") == str(
        handoff_consumer_json.resolve()
    )
    assert _arg_after(delegated_launch_command, "--guarded-ready-gate-json") == str(ready_gate_json.resolve())
    assert _arg_after(artifact_index_command, "--handoff-json") == str(handoff_json.resolve())
    assert _arg_after(artifact_index_command, "--handoff-markdown") == str(handoff_markdown.resolve())
    assert _arg_after(artifact_index_command, "--handoff-validation-json") == str(
        handoff_validation_json.resolve()
    )
    assert _arg_after(artifact_index_command, "--handoff-consumer-json") == str(handoff_consumer_json.resolve())
    assert _arg_after(artifact_index_command, "--ready-gate-json") == str(ready_gate_json.resolve())
    assert _arg_after(refresh_command, "--guarded-handoff-json") == str(handoff_json.resolve())
    assert _arg_after(refresh_command, "--guarded-handoff-markdown") == str(handoff_markdown.resolve())
    assert _arg_after(refresh_command, "--guarded-handoff-validation-json") == str(
        handoff_validation_json.resolve()
    )
    assert _arg_after(refresh_command, "--guarded-handoff-consumer-json") == str(handoff_consumer_json.resolve())
    assert _arg_after(refresh_command, "--guarded-ready-gate-json") == str(ready_gate_json.resolve())


def test_guarded_launch_packet_refresh_uses_custom_status_json(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"
    status_json = tmp_path / "status" / "guarded-status.json"

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--status-json-out",
            str(status_json),
            "--emit-handoff",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    delegated_launch_command = payload["command"]
    command = payload["operator_packet_refresh_command"]
    assert result == 0
    assert _arg_after(delegated_launch_command, "--guarded-status-json") == str(status_json.resolve())
    assert _arg_after(command, "--guarded-output-dir") == str(output_dir.resolve())
    assert _arg_after(command, "--guarded-output-prefix") == "release-check"
    assert _arg_after(command, "--guarded-status-json") == str(status_json.resolve())


def test_guarded_launch_dry_run_reports_missing_artifact_index_hint(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--emit-handoff",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    summary = payload["artifact_index_readiness_summary"]
    missing_command = summary["missing_index_command"]
    assert result == 0
    assert summary["found"] is False
    assert summary["recovery_command_status"] is None
    assert summary["recovery_command_note"] == (
        "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index."
    )
    assert summary["recovery_summary"] == {
        "required": True,
        "action": "Run the guarded launch wrapper without --dry-run to generate the artifact index evidence.",
        "status": None,
        "note": "Artifact index recovery status is resolved after the guarded wrapper emits the artifact index.",
        "command": missing_command,
    }
    assert summary["missing_index_action"] == (
        "Run the guarded launch wrapper without --dry-run to generate the artifact index evidence."
    )
    assert missing_command[:2] == [sys.executable, str(SCRIPT_PATH.resolve())]
    assert "--dry-run" not in missing_command
    assert "--emit-handoff" in missing_command
    assert _arg_after(missing_command, "--output-prefix") == "release-check"
    assert _arg_after(missing_command, "--output-dir") == str(output_dir.resolve())


def test_guarded_launch_delegates_and_returns_exit_code(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(args=command, returncode=17, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
        ],
        command_runner=runner,
    )

    assert result == 17
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[1] == str(app_root.resolve() / "scripts" / "launch_compose.py")
    assert _arg_after(command, "--app-root") == str(app_root.resolve())
    assert _arg_after(command, "--env-file") == str(env_file.resolve())
    assert kwargs == {"cwd": app_root.resolve(), "text": True}


def test_guarded_launch_can_emit_handoff_after_launch_and_preserve_launch_exit(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=1 if len(calls) == 1 else 0, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--emit-handoff",
        ],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 11
    assert calls[0][1] == str(app_root.resolve() / "scripts" / "launch_compose.py")
    assert _arg_after(calls[0], "--app-root") == str(app_root.resolve())
    assert calls[1][1] == str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py")
    assert calls[2][1] == str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py")
    assert calls[3][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")
    assert calls[4][1] == str(app_root.resolve() / "scripts" / "render_launch_operator_packet.py")
    assert calls[5][1] == str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py")
    assert calls[6][1] == str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py")
    assert calls[7][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")
    assert calls[8][1] == str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py")
    assert calls[9][1] == str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py")
    assert calls[10][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")
    assert "--exit-zero-on-blocked" in calls[1]
    assert "--exit-zero-on-blocked" in calls[2]
    assert _arg_after(calls[3], "--markdown-out").endswith("-artifact-index.md")
    assert _arg_after(calls[4], "--json-out").endswith("-operator-packet.json")


def test_guarded_launch_emit_handoff_writes_default_status_json(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"
    status_json = output_dir.resolve() / "release-check-status.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--emit-handoff",
        ],
        command_runner=runner,
    )

    index_commands = [
        command for command in calls if Path(command[1]).name == "index_guarded_launch_artifacts.py"
    ]
    refresh_commands = [
        command for command in calls if Path(command[1]).name == "render_launch_operator_packet.py"
    ]
    payload = json.loads(status_json.read_text(encoding="utf-8"))
    assert result == 0
    assert status_json.exists()
    assert payload["artifacts"]["artifact_index_json"] == str(
        output_dir.resolve() / "release-check-artifact-index.json"
    )
    assert len(index_commands) == 3
    assert _arg_after(index_commands[0], "--status-json") == str(status_json)
    assert len(refresh_commands) == 1
    assert _arg_after(refresh_commands[0], "--guarded-status-json") == str(status_json)


def test_guarded_launch_refreshes_operator_packet_after_first_artifact_index(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "release-check")
    calls: list[str] = []
    packet_refresh_saw_index: list[bool] = []
    second_handoff_action_ids: list[list[str]] = []

    def write_artifact_index(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "pass",
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
                    "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
                    "consumer_readiness_next_commands": [
                        {
                            "name": "validate_env_template",
                            "command": "& python validate_launch_env_template.py",
                            "shell": "powershell",
                        }
                    ],
                    "consumer_readiness_env_validation_ready_for_preflight": True,
                    "consumer_readiness_env_validation_placeholder_count": 0,
                    "consumer_readiness_operator_packet_preflight_status": "fail",
                }
            ),
            encoding="utf-8",
        )

    def write_initial_launch_report() -> None:
        artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
        artifacts["launch_report_json"].write_text(
            json.dumps(
                {
                    "status": "fail",
                    "stage": "preflight",
                    "child_reports": {
                        "operator_packet": {
                            "found": True,
                            "path": str(artifacts["operator_packet_json"]),
                            "preflight_status": "fail",
                            "consumer_command_metadata_status": None,
                        }
                    },
                    "results": [],
                }
            ),
            encoding="utf-8",
        )

    def write_initial_readiness_summary() -> None:
        artifacts["readiness_summary_json"].parent.mkdir(parents=True, exist_ok=True)
        artifacts["readiness_summary_json"].write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker_class": "preflight_blocked",
                    "reports": {
                        "operator_packet": {
                            "preflight_status": "fail",
                            "operator_action_ids": ["set_firebase_service_account_file"],
                            "consumer_command_metadata_status": None,
                        }
                    },
                    "next_commands": [],
                }
            ),
            encoding="utf-8",
        )

    def write_refreshed_operator_packet() -> None:
        artifacts["operator_packet_json"].parent.mkdir(parents=True, exist_ok=True)
        artifacts["operator_packet_json"].write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "operator_actions": [{"id": "set_firebase_service_account_file"}],
                    "guarded_launch_evidence": {
                        "artifact_index_readiness_summary": {
                            "status": "pass",
                            "consumer_packet_validation_status": "pass",
                            "consumer_command_metadata_status": "pass",
                            "recovery_command_status": "not_required",
                            "operator_action_ids": ["set_firebase_service_account_file"],
                            "env_validation_ready_for_preflight": True,
                            "env_validation_placeholder_count": 0,
                            "operator_packet_preflight_status": "fail",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def runner(command, **kwargs):
        script_name = Path(command[1]).name
        calls.append(script_name)
        if script_name == "launch_compose.py":
            write_initial_launch_report()
            write_initial_readiness_summary()
        if script_name == "index_guarded_launch_artifacts.py":
            write_artifact_index(Path(_arg_after(command, "--json-out")))
        if script_name == "render_launch_operator_packet.py":
            packet_refresh_saw_index.append((output_dir.resolve() / "release-check-artifact-index.json").exists())
            write_refreshed_operator_packet()
        if script_name == "render_guarded_launch_handoff.py" and calls.count("render_guarded_launch_handoff.py") == 2:
            packet = json.loads(artifacts["operator_packet_json"].read_text(encoding="utf-8"))
            evidence = packet.get("guarded_launch_evidence")
            assert isinstance(evidence, dict)
            summary = evidence.get("artifact_index_readiness_summary")
            assert isinstance(summary, dict)
            action_ids = summary.get("operator_action_ids")
            assert isinstance(action_ids, list)
            second_handoff_action_ids.append([str(action_id) for action_id in action_ids])
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--emit-handoff",
        ],
        command_runner=runner,
    )

    assert result == 0
    assert calls == [
        "launch_compose.py",
        "render_guarded_launch_handoff.py",
        "consume_guarded_launch_handoff.py",
        "index_guarded_launch_artifacts.py",
        "render_launch_operator_packet.py",
        "render_guarded_launch_handoff.py",
        "consume_guarded_launch_handoff.py",
        "index_guarded_launch_artifacts.py",
        "render_guarded_launch_handoff.py",
        "consume_guarded_launch_handoff.py",
        "index_guarded_launch_artifacts.py",
    ]
    assert packet_refresh_saw_index == [True]
    assert second_handoff_action_ids == [["set_firebase_service_account_file"]]
    launch_report = json.loads(artifacts["launch_report_json"].read_text(encoding="utf-8"))
    operator_packet = launch_report["child_reports"]["operator_packet"]
    assert operator_packet["artifact_index_status"] == "pass"
    assert operator_packet["consumer_packet_validation_status"] == "pass"
    assert operator_packet["consumer_command_metadata_status"] == "pass"
    assert operator_packet["artifact_index_recovery_command_status"] == "not_required"
    readiness_summary = json.loads(artifacts["readiness_summary_json"].read_text(encoding="utf-8"))
    readiness_operator_packet = readiness_summary["reports"]["operator_packet"]
    assert readiness_operator_packet["artifact_index_status"] == "pass"
    assert readiness_operator_packet["consumer_packet_validation_status"] == "pass"
    assert readiness_operator_packet["consumer_command_metadata_status"] == "pass"
    assert readiness_operator_packet["artifact_index_recovery_command_status"] == "not_required"
    readiness_markdown = artifacts["readiness_summary_markdown"].read_text(encoding="utf-8")
    assert "- Consumer command metadata: `pass`" in readiness_markdown


def test_guarded_launch_refreshes_status_before_second_artifact_index_pass(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"
    status_json = output_dir / "guarded-status.json"
    status_seen_by_index: list[bool | None] = []

    def write_passing_artifact_index(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "pass",
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

    def runner(command, **kwargs):
        if Path(command[1]).name == "index_guarded_launch_artifacts.py":
            status_payload = json.loads(status_json.read_text(encoding="utf-8"))
            artifact_index = status_payload.get("artifact_index")
            status_seen_by_index.append(
                artifact_index.get("found") if isinstance(artifact_index, dict) else None
            )
            write_passing_artifact_index(Path(_arg_after(command, "--json-out")))
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "release-check",
            "--emit-handoff",
            "--status-json-out",
            str(status_json),
        ],
        command_runner=runner,
    )

    final_status = json.loads(status_json.read_text(encoding="utf-8"))
    assert result == 0
    assert status_seen_by_index == [False, True, True]
    assert final_status["artifact_index"]["found"] is True
    assert (
        final_status["artifact_index"]["consumer_readiness_operator_packet_consumer_command_metadata_status"]
        == "pass"
    )
    assert final_status["artifact_index_recovery_summary"]["required"] is False


def test_guarded_launch_returns_handoff_validation_failure(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0 if len(calls) == 1 else 2, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--emit-handoff",
        ],
        command_runner=runner,
    )

    assert result == 2
    assert len(calls) == 4
    assert calls[3][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")


def test_guarded_launch_returns_handoff_consumer_failure(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0 if len(calls) < 3 else 1, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--emit-handoff",
        ],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 4
    assert calls[3][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")


def test_guarded_launch_returns_artifact_index_failure(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0 if len(calls) < 4 else 1, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--emit-handoff",
        ],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 4


def test_guarded_launch_can_skip_browser_smoke_and_pass_compose_options(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    compose_file = tmp_path / "docker-compose.launch.yml"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--compose-file",
            str(compose_file),
            "--service",
            "backend",
            "--no-browser-smoke",
        ],
        command_runner=runner,
    )

    command = calls[0]
    assert result == 0
    assert "--run-browser-smoke" not in command
    assert _arg_after(command, "--compose-file") == str(compose_file.resolve())
    assert _arg_after(command, "--service") == "backend"


def test_guarded_launch_status_only_reports_missing_artifacts(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "missing",
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["status"] == "missing_artifacts"
    assert payload["launch"]["found"] is False
    assert payload["readiness_summary"]["found"] is False
    assert payload["operator_packet"]["found"] is False
    assert payload["artifact_index_recovery_summary"] == {
        "required": True,
        "action": "Generate the guarded launch operator packet so artifact-index recovery status can be read.",
        "status": None,
        "note": "Artifact index recovery status is unavailable because the operator packet is missing.",
        "command": None,
    }
    assert payload["artifact_index_recovery_command_shell"] is None
    assert payload["artifact_index_recovery_command_text"] is None
    assert payload["operator_action_ids"] == []


def test_guarded_launch_status_only_reads_compact_prefix_view(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
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
                "next_actions": ["Open the operator packet."],
                "next_commands": [
                    {
                        "name": "validate_env_template",
                        "command": "& python validate_launch_env_template.py",
                        "shell": "powershell",
                    },
                    {
                        "name": "strict_preflight",
                        "command": "& python launch_env_preflight.py",
                        "shell": "powershell",
                    },
                ],
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
            }
        ),
        encoding="utf-8",
    )
    artifacts["operator_packet_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocking_action_count": 1,
                "preflight_status": "fail",
                "preflight_errors": ["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."],
                "operator_actions": [{"id": "fallback_action"}],
                "secrets_redacted": True,
                "guarded_launch_evidence": {
                    "artifact_index_readiness_summary": {
                        "recovery_summary": {
                            "required": False,
                            "action": None,
                            "status": "not_required",
                            "note": None,
                            "command": None,
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "blocked",
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["status"] == "blocked"
    assert payload["blocker_class"] == "preflight_blocked"
    assert payload["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert payload["launch"]["stage"] == "preflight"
    assert payload["launch"]["result_names"] == ["env_validation", "preflight"]
    assert payload["readiness_summary"]["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert payload["readiness_summary"]["env_validation_ready_for_preflight"] is False
    assert payload["readiness_summary"]["env_validation_placeholder_count"] == 6
    assert payload["readiness_summary"]["operator_packet_preflight_status"] == "env_shape_blocked"
    assert payload["readiness_summary"]["next_commands"] == [
        {
            "name": "validate_env_template",
            "command": "& python validate_launch_env_template.py",
            "shell": "powershell",
        },
        {
            "name": "strict_preflight",
            "command": "& python launch_env_preflight.py",
            "shell": "powershell",
        },
    ]
    assert payload["operator_packet"]["operator_action_ids"] == ["fallback_action"]
    assert payload["operator_packet"]["blocking_action_count"] == 1
    assert payload["operator_packet"]["preflight_status"] == "fail"
    assert payload["operator_packet"]["preflight_errors"] == [
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."
    ]
    assert payload["artifact_index_recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "note": None,
        "command": None,
    }
    assert payload["artifact_index_recovery_command_shell"] is None
    assert payload["artifact_index_recovery_command_text"] is None


def test_guarded_launch_status_only_prefers_custom_artifact_index(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    custom_index = tmp_path / "handoff" / "current.artifact-index.json"
    artifacts["operator_packet_json"].parent.mkdir(parents=True, exist_ok=True)
    custom_index.parent.mkdir(parents=True, exist_ok=True)
    artifacts["operator_packet_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "guarded_launch_evidence": {
                    "artifact_index_readiness_summary": {
                        "recovery_summary": {
                            "required": True,
                            "action": "Regenerate stale packet evidence.",
                            "status": "pass",
                            "note": "Recovery command is present because this artifact index did not meet pass criteria.",
                            "command": ["python", "stale-recovery.py"],
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    custom_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "missing_required_roles": [],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
                "consumer_readiness_next_commands": [
                    {
                        "name": "validate_env_template",
                        "command": "& python validate_launch_env_template.py",
                        "shell": "powershell",
                    }
                ],
                "consumer_readiness_env_validation_ready_for_preflight": True,
                "consumer_readiness_env_validation_placeholder_count": 0,
                "consumer_readiness_operator_packet_preflight_status": "fail",
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

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "blocked",
            "--artifact-index-json-out",
            str(custom_index),
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["artifact_index_recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "note": None,
        "command": None,
    }
    assert payload["artifact_index_recovery_command_shell"] is None
    assert payload["artifact_index_recovery_command_text"] is None
    assert payload["artifact_index"] == {
        "found": True,
        "path": str(custom_index.resolve()),
        "status": "pass",
        "missing_required_roles": [],
        "consumer_packet_validation_status": "pass",
        "consumer_command_metadata_status": "pass",
        "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
        "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
        "consumer_readiness_next_commands": [
            {
                "name": "validate_env_template",
                "command": "& python validate_launch_env_template.py",
                "shell": "powershell",
            }
        ],
        "consumer_readiness_env_validation_ready_for_preflight": True,
        "consumer_readiness_env_validation_placeholder_count": 0,
        "consumer_readiness_operator_packet_preflight_status": "fail",
        "recovery_command_status": "not_required",
    }
    assert payload["artifacts"]["artifact_index_json"] == str(custom_index.resolve())


def test_guarded_launch_status_only_exposes_recovery_command_text(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch artifacts"
    custom_index = tmp_path / "handoff" / "current.artifact-index.json"
    recovery_command = [
        sys.executable,
        str(app_root.resolve() / "scripts" / "run_guarded_launch.py"),
        "--app-root",
        str(app_root.resolve()),
        "--output-dir",
        str(output_dir.resolve()),
        "--output-prefix",
        "blocked",
        "--emit-handoff",
    ]
    custom_index.parent.mkdir(parents=True, exist_ok=True)
    custom_index.write_text(
        json.dumps(
            {
                "status": "fail",
                "missing_required_roles": ["handoff_consumer_json"],
                "consumer_packet_validation_status": "fail",
                "consumer_command_metadata_status": "fail",
                "recovery_command_status": "pass",
                "recovery_summary": {
                    "required": True,
                    "action": "Run the guarded launch wrapper command to regenerate evidence.",
                    "status": "pass",
                    "note": "Recovery command is present because this artifact index did not meet pass criteria.",
                    "command": recovery_command,
                },
            }
        ),
        encoding="utf-8",
    )

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "blocked",
            "--artifact-index-json-out",
            str(custom_index),
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["artifact_index_recovery_command_shell"] == "powershell"
    assert payload["artifact_index_recovery_command_text"].startswith("& ")
    assert f"'{output_dir.resolve()}'" in payload["artifact_index_recovery_command_text"]
    assert payload["artifact_index_recovery_summary"]["command"] == recovery_command


def test_guarded_launch_status_require_ready_fails_for_blocked_prefix(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    artifacts["readiness_summary_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["readiness_summary_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "env_shape_blocked",
                "secrets_redacted": True,
                "reports": {},
            }
        ),
        encoding="utf-8",
    )

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "blocked",
            "--status-only",
            "--require-ready",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 1
    assert payload["status"] == "blocked"
    assert payload["blocker_class"] == "env_shape_blocked"


def test_guarded_launch_status_require_ready_accepts_passing_launch(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "ready")
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

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "ready",
            "--status-only",
            "--require-ready",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["status"] == "ready"
    assert payload["blocker_class"] == "ready"
    assert payload["launch"]["stage"] == "browser_smoke"


def test_guarded_launch_can_write_status_json_after_run(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    env_file = tmp_path / "operator.env"
    status_json = tmp_path / "status.json"

    def runner(command, **kwargs):
        artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "after-run")
        artifacts["readiness_summary_json"].parent.mkdir(parents=True, exist_ok=True)
        artifacts["readiness_summary_json"].write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "blocker_class": "env_shape_blocked",
                    "secrets_redacted": True,
                    "reports": {},
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=command, returncode=9, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "after-run",
            "--status-json-out",
            str(status_json),
        ],
        command_runner=runner,
    )

    payload = json.loads(status_json.read_text(encoding="utf-8"))
    assert result == 9
    assert payload["status"] == "blocked"
    assert payload["blocker_class"] == "env_shape_blocked"


def test_guarded_launch_require_ready_checks_status_after_run(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    env_file = tmp_path / "operator.env"

    def runner(command, **kwargs):
        artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "after-run")
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
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    result = run_guarded_launch.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--output-dir",
            str(output_dir),
            "--output-prefix",
            "after-run",
            "--require-ready",
        ],
        command_runner=runner,
    )

    assert result == 0
