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


def test_guarded_launch_load_peer_module_supports_dataclasses() -> None:
    previous_module = sys.modules.get("ab_test_qr_page")

    module = run_guarded_launch._load_peer_module("ab_test_qr_page")
    observation = module.QRSessionObservation(
        "session-1",
        "A",
        True,
        True,
        False,
        False,
        9.5,
        4.0,
    )

    assert observation.session_id == "session-1"
    if previous_module is None:
        assert "ab_test_qr_page" not in sys.modules
    else:
        assert sys.modules["ab_test_qr_page"] is previous_module


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
                "blocker_class": "ready",
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "recovery_command_status": "not_required",
                "consumer_readiness_operator_action_ids": ["fix_env_shape_validation"],
                "consumer_readiness_next_actions": [
                    "Replace env template placeholders and sample domains.",
                ],
                "consumer_readiness_next_commands": [
                    {
                        "name": "validate_env_template",
                        "command": "& python validate_launch_env_template.py",
                        "shell": "powershell",
                    }
                ],
                "consumer_readiness_env_validation_blocker_class": "env_shape_blocked",
                "consumer_readiness_env_validation_ready_for_preflight": False,
                "consumer_readiness_env_validation_placeholder_count": 6,
                "consumer_readiness_operator_packet_preflight_status": "env_shape_blocked",
                "launch_browser_smoke": {
                    "found": True,
                    "status": "fail",
                    "path": "var/agriguard-browser-smoke-suite-compose-launch.json",
                    "prechecks_total": 3,
                    "prechecks_passed": 2,
                    "prechecks_failed": 1,
                    "failed_precheck_names": ["public_verify_cache_headers"],
                },
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
        "blocker_class": "ready",
        "consumer_packet_validation_status": "pass",
        "consumer_command_metadata_status": "pass",
        "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
        "recovery_command_status": "not_required",
        "recovery_command_note": None,
        "recovery_summary": {
            "required": False,
            "action": None,
            "status": "not_required",
            "blocker_class": "ready",
            "note": None,
            "command": None,
        },
        "launch_browser_smoke": {
            "found": True,
            "path": "var/agriguard-browser-smoke-suite-compose-launch.json",
            "status": "fail",
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
            "prechecks_total": 3,
            "prechecks_passed": 2,
            "prechecks_failed": 1,
            "screenshot_artifacts_total": None,
            "screenshot_artifacts_passed": None,
            "screenshot_artifacts_failed": None,
            "failed_step_names": [],
            "failed_check_names": [],
            "failed_precheck_names": ["public_verify_cache_headers"],
        },
        "stale_generated_at_roles": [],
        "stale_generated_at_details": [],
        "operator_action_ids": ["fix_env_shape_validation"],
        "next_actions": [
            "Replace env template placeholders and sample domains.",
        ],
        "next_commands": [
            {
                "name": "validate_env_template",
                "command": "& python validate_launch_env_template.py",
                "shell": "powershell",
            }
        ],
        "env_validation_blocker_class": "env_shape_blocked",
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
    assert _arg_after(payload["handoff_command"], "--env-file") == str(env_file.resolve())
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
        "blocker_class": "artifact_index_recovery_blocked",
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
    assert len(calls) == 15
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
    assert calls[11][1] == str(app_root.resolve() / "scripts" / "render_launch_operator_packet.py")
    assert calls[12][1] == str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py")
    assert calls[13][1] == str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py")
    assert calls[14][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")
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
    assert len(index_commands) == 4
    assert _arg_after(index_commands[0], "--status-json") == str(status_json)
    assert len(refresh_commands) == 2
    assert _arg_after(refresh_commands[0], "--guarded-status-json") == str(status_json)
    assert _arg_after(refresh_commands[1], "--guarded-status-json") == str(status_json)


def test_guarded_launch_refreshes_operator_packet_after_final_artifact_index(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "operator.env"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "release-check")
    calls: list[str] = []
    artifact_index_write_count = 0
    packet_refresh_saw_index: list[bool] = []
    packet_refresh_readiness_command_metadata: list[object] = []
    second_handoff_action_ids: list[list[str]] = []
    final_handoff_readiness_command_metadata: list[object] = []

    def write_artifact_index(path: Path) -> None:
        nonlocal artifact_index_write_count
        artifact_index_write_count += 1
        readiness_command_metadata_status = "pass" if artifact_index_write_count >= 3 else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "blocker_class": "ready",
                    "missing_required_roles": [],
                    "consumer_packet_validation_status": "pass",
                    "consumer_command_metadata_status": "pass",
                    "consumer_readiness_operator_packet_consumer_command_metadata_status": (
                        readiness_command_metadata_status
                    ),
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
                    "consumer_readiness_env_validation_blocker_class": "ready",
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
                    "generated_at": "initial-launch",
                    "status": "fail",
                    "stage": "preflight",
                    "child_reports": {
                        "operator_packet": {
                            "found": True,
                            "path": str(artifacts["operator_packet_json"]),
                            "generated_at": "initial-packet",
                            "preflight_status": "fail",
                            "consumer_command_metadata_status": None,
                            "artifact_index_stale_generated_at_roles": ["ready_gate_json"],
                            "artifact_index_stale_generated_at_details": [
                                {"role": "ready_gate_json", "minimum_role": "handoff_consumer_json"}
                            ],
                        },
                        "readiness_summary": {
                            "found": True,
                            "path": str(artifacts["readiness_summary_json"]),
                            "generated_at": "initial-readiness",
                            "status": "blocked",
                            "blocker_class": "preflight_blocked",
                        },
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
                    "generated_at": "initial-readiness",
                    "reports": {
                        "operator_packet": {
                            "generated_at": "initial-packet",
                            "preflight_status": "fail",
                            "operator_action_ids": ["set_firebase_service_account_file"],
                            "consumer_command_metadata_status": None,
                            "artifact_index_stale_generated_at_roles": ["ready_gate_json"],
                            "artifact_index_stale_generated_at_details": [
                                {"role": "ready_gate_json", "minimum_role": "handoff_consumer_json"}
                            ],
                        }
                    },
                    "next_commands": [],
                }
            ),
            encoding="utf-8",
        )

    def write_refreshed_operator_packet() -> None:
        artifact_index = json.loads(
            (output_dir.resolve() / "release-check-artifact-index.json").read_text(encoding="utf-8")
        )
        packet_refresh_readiness_command_metadata.append(
            artifact_index.get("consumer_readiness_operator_packet_consumer_command_metadata_status")
        )
        artifacts["operator_packet_json"].parent.mkdir(parents=True, exist_ok=True)
        artifacts["operator_packet_json"].write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "generated_at": f"refresh-{artifact_index_write_count}",
                    "operator_actions": [{"id": "set_firebase_service_account_file"}],
                    "guarded_launch_evidence": {
                        "artifact_index_readiness_summary": {
                            "status": "pass",
                            "blocker_class": "ready",
                            "consumer_packet_validation_status": "pass",
                            "consumer_command_metadata_status": "pass",
                            "consumer_readiness_operator_packet_consumer_command_metadata_status": artifact_index.get(
                                "consumer_readiness_operator_packet_consumer_command_metadata_status"
                            ),
                            "recovery_command_status": "not_required",
                            "operator_action_ids": ["set_firebase_service_account_file"],
                            "env_validation_blocker_class": "ready",
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
        if script_name == "render_guarded_launch_handoff.py" and calls.count("render_guarded_launch_handoff.py") == 4:
            packet = json.loads(artifacts["operator_packet_json"].read_text(encoding="utf-8"))
            evidence = packet.get("guarded_launch_evidence")
            assert isinstance(evidence, dict)
            summary = evidence.get("artifact_index_readiness_summary")
            assert isinstance(summary, dict)
            final_handoff_readiness_command_metadata.append(
                summary.get("consumer_readiness_operator_packet_consumer_command_metadata_status")
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
        "render_launch_operator_packet.py",
        "render_guarded_launch_handoff.py",
        "consume_guarded_launch_handoff.py",
        "index_guarded_launch_artifacts.py",
    ]
    assert packet_refresh_saw_index == [True, True]
    assert packet_refresh_readiness_command_metadata == [None, "pass"]
    assert second_handoff_action_ids == [["set_firebase_service_account_file"]]
    assert final_handoff_readiness_command_metadata == ["pass"]
    launch_report = json.loads(artifacts["launch_report_json"].read_text(encoding="utf-8"))
    assert launch_report["generated_at"] == "refresh-3"
    operator_packet = launch_report["child_reports"]["operator_packet"]
    assert operator_packet["generated_at"] == "refresh-3"
    launch_readiness_summary = launch_report["child_reports"]["readiness_summary"]
    assert launch_readiness_summary["generated_at"] == "refresh-3"
    assert operator_packet["artifact_index_status"] == "pass"
    assert operator_packet["artifact_index_blocker_class"] == "ready"
    assert operator_packet["artifact_index_stale_generated_at_roles"] == []
    assert operator_packet["artifact_index_stale_generated_at_details"] == []
    assert operator_packet["consumer_packet_validation_status"] == "pass"
    assert operator_packet["consumer_command_metadata_status"] == "pass"
    assert operator_packet["consumer_readiness_operator_packet_consumer_command_metadata_status"] == "pass"
    assert operator_packet["artifact_index_recovery_command_status"] == "not_required"
    readiness_summary = json.loads(artifacts["readiness_summary_json"].read_text(encoding="utf-8"))
    assert readiness_summary["generated_at"] == "refresh-3"
    readiness_operator_packet = readiness_summary["reports"]["operator_packet"]
    assert readiness_operator_packet["generated_at"] == "refresh-3"
    assert readiness_operator_packet["artifact_index_status"] == "pass"
    assert readiness_operator_packet["artifact_index_blocker_class"] == "ready"
    assert readiness_operator_packet["artifact_index_stale_generated_at_roles"] == []
    assert readiness_operator_packet["artifact_index_stale_generated_at_details"] == []
    assert readiness_operator_packet["consumer_packet_validation_status"] == "pass"
    assert readiness_operator_packet["consumer_command_metadata_status"] == "pass"
    assert (
        readiness_operator_packet["consumer_readiness_operator_packet_consumer_command_metadata_status"]
        == "pass"
    )
    assert readiness_operator_packet["artifact_index_recovery_command_status"] == "not_required"
    readiness_markdown = artifacts["readiness_summary_markdown"].read_text(encoding="utf-8")
    assert "- Generated: `refresh-3`" in readiness_markdown
    assert "- Operator packet generated at: `refresh-3`" in readiness_markdown
    assert "- Consumer command metadata: `pass`" in readiness_markdown
    assert "- Consumer readiness command metadata: `pass`" in readiness_markdown


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
                    "blocker_class": "ready",
                    "missing_required_roles": [],
                    "consumer_packet_validation_status": "pass",
                    "consumer_metadata_status": "pass",
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
    assert status_seen_by_index == [False, True, True, True]
    assert final_status["artifact_index"]["found"] is True
    assert final_status["artifact_index"]["blocker_class"] == "ready"
    assert (
        final_status["artifact_index"]["consumer_readiness_operator_packet_consumer_command_metadata_status"]
        == "pass"
    )
    assert final_status["artifact_index_recovery_summary"]["required"] is False
    assert final_status["artifact_index_recovery_summary"]["blocker_class"] == "ready"


def test_guarded_launch_reruns_stale_ready_gate_index_after_refresh(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    output_prefix = "release-check"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), output_prefix)
    artifact_index_json = output_dir.resolve() / "release-check-artifact-index.json"
    artifact_index_markdown = output_dir.resolve() / "release-check-artifact-index.md"
    ready_gate_json = output_dir.resolve() / "release-check-ready-gate.json"
    artifact_index_command = [
        sys.executable,
        str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py"),
    ]
    calls: list[list[str]] = []

    def write_index(payload: dict[str, object]) -> None:
        artifact_index_json.parent.mkdir(parents=True, exist_ok=True)
        artifact_index_json.write_text(json.dumps(payload), encoding="utf-8")

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            write_index(
                {
                    "status": "fail",
                    "blocker_class": "artifact_index_blocked",
                    "missing_required_roles": [],
                    "missing_generated_at_roles": [],
                    "stale_generated_at_roles": ["ready_gate_json"],
                    "stale_generated_at_details": [
                        {
                            "role": "ready_gate_json",
                            "minimum_role": "handoff_consumer_json",
                        }
                    ],
                }
            )
            return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr="")

        ready_gate = json.loads(ready_gate_json.read_text(encoding="utf-8"))
        assert ready_gate["artifacts"]["ready_gate_json"] == str(ready_gate_json)
        assert ready_gate["ready_gate"]["found"] is True
        assert ready_gate["ready_gate"]["exists"] is True
        assert ready_gate["ready_gate"]["generated_at"] == ready_gate["generated_at"]
        assert ready_gate["ready_gate"]["sha256"] is None
        assert ready_gate["ready_gate"]["sha256_status"] == "self_referential_unavailable"
        write_index(
            {
                "status": "pass",
                "blocker_class": "ready",
                "missing_required_roles": [],
                "missing_generated_at_roles": [],
                "stale_generated_at_roles": [],
                "stale_generated_at_details": [],
            }
        )
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    result = run_guarded_launch._run_artifact_index_command(
        command_runner=runner,
        app_root=app_root.resolve(),
        output_dir=output_dir.resolve(),
        output_prefix=output_prefix,
        artifact_paths=artifacts,
        artifact_index_json=artifact_index_json,
        artifact_index_markdown=artifact_index_markdown,
        ready_gate_json=ready_gate_json,
        artifact_index_command=artifact_index_command,
    )

    assert result.returncode == 0
    assert calls == [artifact_index_command, artifact_index_command]
    final_index = json.loads(artifact_index_json.read_text(encoding="utf-8"))
    assert final_index["status"] == "pass"
    assert final_index["stale_generated_at_roles"] == []


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


def test_guarded_launch_packet_refresh_preserves_no_browser_smoke(tmp_path: Path, capsys) -> None:
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
            "--no-browser-smoke",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    delegated_launch_command = payload["command"]
    refresh_command = payload["operator_packet_refresh_command"]
    assert result == 0
    assert "--run-browser-smoke" not in delegated_launch_command
    assert "--no-browser-smoke" in refresh_command


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
    assert payload["generated_at"].endswith("Z")
    payload["generated_at"].encode("ascii")
    assert " " not in payload["generated_at"]
    assert payload["status"] == "missing_artifacts"
    assert payload["launch"]["found"] is False
    assert payload["readiness_summary"]["found"] is False
    assert payload["operator_packet"]["found"] is False
    assert payload["artifact_index_recovery_summary"] == {
        "required": True,
        "action": "Generate the guarded launch operator packet so artifact-index recovery status can be read.",
        "status": None,
        "blocker_class": "artifact_index_recovery_blocked",
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
                "blocker_class": "preflight_blocked",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
                "compose_replacement_guard": {
                    "current_runtime_action_before_preflight": "none",
                    "compose_replacement_requires_env_shape_validation": True,
                    "compose_replacement_requires_strict_preflight": True,
                    "compose_runs_only_after_preflight_passes": True,
                    "blocked_stop_reasons": [
                        "env_shape_validation_requires_single_env_file",
                        "env_shape_validation_failed",
                        "preflight_failed",
                    ],
                },
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
                    "Open the operator packet.",
                    {"action": "not status-safe"},
                ],
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
                    "launch": {
                        "browser_smoke": {
                            "found": True,
                            "path": "var/browser-smoke.json",
                            "status": "pass",
                            "base_url": "http://127.0.0.1:5330",
                            "api_url": "http://127.0.0.1:8060",
                            "mobile": True,
                            "include_unavailable_check": True,
                            "steps_total": 7,
                            "steps_passed": 7,
                            "steps_failed": 0,
                            "checks_total": 191,
                            "checks_passed": 191,
                            "checks_failed": 0,
                            "prechecks_total": 3,
                            "prechecks_passed": 3,
                            "prechecks_failed": 0,
                            "screenshot_artifacts_total": 19,
                            "screenshot_artifacts_passed": 19,
                            "screenshot_artifacts_failed": 0,
                            "failed_step_names": [],
                            "failed_check_names": [],
                            "failed_precheck_names": [],
                        }
                    },
                    "env_validation": {
                        "blocker_class": "env_shape_blocked",
                        "ready_for_preflight": False,
                        "placeholder_count": 6,
                    },
                    "operator_packet": {
                        "blocker_class": "env_shape_blocked",
                        "preflight_status": "env_shape_blocked",
                        "operator_action_ids": ["set_firebase_service_account_file"],
                        "consumer_command_metadata_status": "fail",
                        "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
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
                "blocker_class": "operator_values_required",
                "blocking_action_count": 1,
                "preflight_status": "fail",
                "preflight_checks": {
                    "runtime": "compose",
                    "firebase_credentials_source": "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",
                    "firebase_credentials_resolved_path": "C:/secure/missing-firebase.json",
                },
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
    assert payload["launch"]["blocker_class"] == "preflight_blocked"
    assert payload["launch"]["result_names"] == ["env_validation", "preflight"]
    assert payload["launch"]["compose_replacement_guard"] == {
        "current_runtime_action_before_preflight": "none",
        "compose_replacement_requires_env_shape_validation": True,
        "compose_replacement_requires_strict_preflight": True,
        "compose_runs_only_after_preflight_passes": True,
        "blocked_stop_reasons": [
            "env_shape_validation_requires_single_env_file",
            "env_shape_validation_failed",
            "preflight_failed",
        ],
    }
    assert payload["readiness_summary"]["operator_action_ids"] == ["set_firebase_service_account_file"]
    assert payload["readiness_summary"]["env_validation_blocker_class"] == "env_shape_blocked"
    assert payload["readiness_summary"]["env_validation_ready_for_preflight"] is False
    assert payload["readiness_summary"]["env_validation_placeholder_count"] == 6
    assert payload["readiness_summary"]["operator_packet_blocker_class"] == "env_shape_blocked"
    assert payload["readiness_summary"]["operator_packet_preflight_status"] == "env_shape_blocked"
    assert payload["readiness_summary"]["operator_packet_consumer_command_metadata_status"] == "fail"
    assert payload["readiness_summary"]["operator_packet_consumer_readiness_command_metadata_status"] == "pass"
    assert payload["readiness_summary"]["browser_smoke"]["status"] == "pass"
    assert payload["readiness_summary"]["browser_smoke"]["mobile"] is True
    assert payload["readiness_summary"]["browser_smoke"]["checks_passed"] == 191
    assert payload["readiness_summary"]["next_actions"] == ["Open the operator packet."]
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
    assert payload["operator_packet"]["blocker_class"] == "operator_values_required"
    assert payload["operator_packet"]["preflight_status"] == "fail"
    assert payload["operator_packet"]["preflight_checks"] == {
        "runtime": "compose",
        "firebase_credentials_source": "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE",
        "firebase_credentials_resolved_path": "C:/secure/missing-firebase.json",
    }
    assert payload["operator_packet"]["preflight_errors"] == [
        "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."
    ]
    assert payload["artifact_index_recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "blocker_class": "ready",
        "note": None,
        "command": None,
    }
    assert payload["artifact_index_recovery_command_shell"] is None
    assert payload["artifact_index_recovery_command_text"] is None


def test_guarded_launch_status_only_derives_missing_child_blocker_classes(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    artifact_index = output_dir.resolve() / "blocked-artifact-index.json"
    artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["launch_report_json"].write_text(
        json.dumps(
            {
                "status": "fail",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
                "results": [{"name": "env_validation"}, {"name": "preflight"}, {"name": "operator_packet"}],
            }
        ),
        encoding="utf-8",
    )
    artifacts["readiness_summary_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "preflight_blocked",
                "reports": {
                    "env_validation": {
                        "status": "pass",
                        "ready_for_preflight": True,
                        "placeholder_count": 0,
                    },
                    "operator_packet": {
                        "status": "blocked",
                        "preflight_status": "fail",
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
                "env_validation_status": "pass",
                "preflight_status": "fail",
                "operator_actions": [{"id": "set_firebase_service_account_file"}],
                "secrets_redacted": True,
            }
        ),
        encoding="utf-8",
    )
    artifact_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "missing_required_roles": [],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
                "launch_browser_smoke": {
                    "found": True,
                    "status": "fail",
                    "path": "var/agriguard-browser-smoke-suite-compose-launch.json",
                    "prechecks_total": 3,
                    "prechecks_passed": 2,
                    "prechecks_failed": 1,
                    "failed_precheck_names": ["public_verify_cache_headers"],
                },
                "recovery_command_status": "not_required",
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
            "--artifact-index-json",
            str(artifact_index),
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["blocker_class"] == "preflight_blocked"
    assert payload["launch"]["blocker_class"] == "preflight_blocked"
    assert payload["readiness_summary"]["env_validation_blocker_class"] == "ready"
    assert payload["readiness_summary"]["operator_packet_blocker_class"] == "operator_values_required"
    assert payload["operator_packet"]["blocker_class"] == "operator_values_required"
    assert payload["operator_packet"]["env_validation_blocker_class"] == "ready"
    assert payload["artifact_index"]["blocker_class"] == "ready"
    assert payload["artifact_index"]["consumer_metadata_status"] == "pass"
    assert payload["artifact_index"]["missing_generated_at_roles"] == []
    assert payload["artifact_index"]["stale_generated_at_roles"] == []
    assert payload["artifact_index"]["stale_generated_at_details"] == []
    assert payload["artifact_index"]["launch_browser_smoke"]["status"] == "fail"
    assert payload["artifact_index"]["launch_browser_smoke"]["prechecks_passed"] == 2
    assert payload["artifact_index"]["launch_browser_smoke"]["prechecks_total"] == 3
    assert payload["artifact_index"]["launch_browser_smoke"]["failed_precheck_names"] == [
        "public_verify_cache_headers"
    ]


def test_guarded_launch_status_only_blocks_stale_pass_artifact_index_metadata(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    artifact_index = output_dir.resolve() / "blocked-artifact-index.json"
    artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["launch_report_json"].write_text(
        json.dumps(
            {
                "status": "fail",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
            }
        ),
        encoding="utf-8",
    )
    artifact_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "consumer_packet_validation_status": "pass",
                "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
                "recovery_command_status": "not_required",
            }
        ),
        encoding="utf-8",
    )
    wrapper_command = "& python run_guarded_launch.py --output-prefix blocked --emit-handoff"
    artifacts["operator_packet_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "guarded_launch_evidence": {
                    "wrapper_command": wrapper_command,
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
            "--artifact-index-json",
            str(artifact_index),
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["artifact_index"]["status"] == "pass"
    assert payload["artifact_index"]["consumer_metadata_status"] == "fail"
    assert payload["artifact_index"]["blocker_class"] == "artifact_index_blocked"
    assert payload["artifact_index_recovery_summary"] == {
        "required": True,
        "action": run_guarded_launch.STALE_ARTIFACT_INDEX_METADATA_RECOVERY_ACTION,
        "status": "fail",
        "blocker_class": "artifact_index_recovery_blocked",
        "note": run_guarded_launch.STALE_ARTIFACT_INDEX_METADATA_RECOVERY_NOTE,
        "command": wrapper_command,
    }
    assert payload["artifact_index_recovery_command_shell"] == "powershell"
    assert payload["artifact_index_recovery_command_text"] == wrapper_command


def test_guarded_launch_status_only_reports_missing_artifact_freshness_roles(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    artifact_index = output_dir.resolve() / "blocked-artifact-index.json"
    artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["launch_report_json"].write_text(
        json.dumps(
            {
                "status": "fail",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
            }
        ),
        encoding="utf-8",
    )
    artifact_index.write_text(
        json.dumps(
            {
                "status": "fail",
                "missing_required_roles": [],
                "missing_generated_at_roles": ["handoff_consumer_json"],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "recovery_command_status": "pass",
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
            "--artifact-index-json",
            str(artifact_index),
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["artifact_index"]["status"] == "fail"
    assert payload["artifact_index"]["blocker_class"] == "artifact_index_blocked"
    assert payload["artifact_index"]["missing_generated_at_roles"] == ["handoff_consumer_json"]
    assert payload["artifact_index"]["stale_generated_at_roles"] == []
    assert payload["artifact_index"]["stale_generated_at_details"] == []


def test_guarded_launch_status_only_reports_stale_artifact_freshness_roles(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    artifact_index = output_dir.resolve() / "blocked-artifact-index.json"
    artifacts["launch_report_json"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["launch_report_json"].write_text(
        json.dumps(
            {
                "status": "fail",
                "stage": "preflight",
                "stop_reason": "preflight_failed",
            }
        ),
        encoding="utf-8",
    )
    artifact_index.write_text(
        json.dumps(
            {
                "status": "fail",
                "missing_required_roles": [],
                "missing_generated_at_roles": [],
                "stale_generated_at_roles": ["ready_gate_json"],
                "stale_generated_at_details": [
                    {
                        "role": "ready_gate_json",
                        "generated_at": "2026-07-06T12:52:04Z",
                        "minimum_role": "handoff_consumer_json",
                        "minimum_generated_at": "2026-07-06T15:20:59Z",
                    }
                ],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "recovery_command_status": "pass",
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
            "--artifact-index-json",
            str(artifact_index),
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["artifact_index"]["status"] == "fail"
    assert payload["artifact_index"]["blocker_class"] == "artifact_index_blocked"
    assert payload["artifact_index"]["stale_generated_at_roles"] == ["ready_gate_json"]
    assert payload["artifact_index"]["stale_generated_at_details"] == [
        {
            "role": "ready_gate_json",
            "generated_at": "2026-07-06T12:52:04Z",
            "minimum_role": "handoff_consumer_json",
            "minimum_generated_at": "2026-07-06T15:20:59Z",
        }
    ]


def test_guarded_launch_status_only_derives_top_blocker_without_summary(tmp_path: Path, capsys) -> None:
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
    assert payload["status"] == "fail"
    assert payload["blocker_class"] == "preflight_blocked"
    assert payload["launch"]["blocker_class"] == "preflight_blocked"


def test_guarded_launch_status_only_prefers_custom_artifact_index(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    custom_index = tmp_path / "handoff" / "current.artifact-index.json"
    custom_handoff = tmp_path / "handoff" / "current.handoff.json"
    custom_handoff_consumer = tmp_path / "handoff" / "current.handoff.consumer.json"
    custom_ready_gate = tmp_path / "handoff" / "current.ready-gate.json"
    custom_status = tmp_path / "handoff" / "current.status.json"
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
                "blocker_class": "ready",
                "missing_required_roles": [],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
                "consumer_readiness_next_actions": [
                    "Provide a real Firebase Admin service-account .json at an absolute host path outside the repo.",
                ],
                "consumer_readiness_next_commands": [
                    {
                        "name": "validate_env_template",
                        "command": "& python validate_launch_env_template.py",
                        "shell": "powershell",
                    }
                ],
                "consumer_readiness_env_validation_blocker_class": "ready",
                "consumer_readiness_env_validation_ready_for_preflight": True,
                "consumer_readiness_env_validation_placeholder_count": 0,
                "consumer_readiness_operator_packet_preflight_status": "fail",
                "consumer_ready_gate_command_shell": "powershell",
                "consumer_ready_gate_command_text": "& python run_guarded_launch.py --status-only --require-ready",
                "recovery_command_status": "not_required",
                "recovery_summary": {
                    "required": False,
                    "action": None,
                    "status": "not_required",
                    "note": None,
                    "command": None,
                },
                "artifacts": [
                    {"role": "handoff_json", "path": str(custom_handoff.resolve())},
                    {"role": "handoff_consumer_json", "path": str(custom_handoff_consumer.resolve())},
                    {"role": "ready_gate_json", "path": str(custom_ready_gate.resolve())},
                    {"role": "status_json", "path": str(custom_status.resolve())},
                ],
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
        "blocker_class": "ready",
        "note": None,
        "command": None,
    }
    assert payload["artifact_index_recovery_command_shell"] is None
    assert payload["artifact_index_recovery_command_text"] is None
    assert payload["artifact_index"] == {
        "found": True,
        "path": str(custom_index.resolve()),
        "status": "pass",
        "blocker_class": "ready",
        "missing_required_roles": [],
        "missing_generated_at_roles": [],
        "stale_generated_at_roles": [],
        "stale_generated_at_details": [],
        "consumer_packet_validation_status": "pass",
        "consumer_metadata_status": "pass",
        "consumer_command_metadata_status": "pass",
        "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
        "consumer_readiness_operator_action_ids": ["set_firebase_service_account_file"],
        "consumer_readiness_next_actions": [
            "Provide a real Firebase Admin service-account .json at an absolute host path outside the repo.",
        ],
        "consumer_readiness_next_commands": [
            {
                "name": "validate_env_template",
                "command": "& python validate_launch_env_template.py",
                "shell": "powershell",
            }
        ],
        "consumer_readiness_env_validation_blocker_class": "ready",
        "consumer_readiness_env_validation_ready_for_preflight": True,
        "consumer_readiness_env_validation_placeholder_count": 0,
        "consumer_readiness_operator_packet_preflight_status": "fail",
        "recovery_command_status": "not_required",
    }
    assert payload["artifacts"]["artifact_index_json"] == str(custom_index.resolve())
    assert payload["artifacts"]["artifact_index_markdown"] == str(
        output_dir.resolve() / "blocked-artifact-index.md"
    )
    assert payload["artifacts"]["handoff_json"] == str(custom_handoff.resolve())
    assert payload["artifacts"]["handoff_consumer_json"] == str(custom_handoff_consumer.resolve())
    assert payload["artifacts"]["ready_gate_json"] == str(custom_ready_gate.resolve())
    assert payload["artifacts"]["status_json"] == str(custom_status.resolve())
    assert payload["ready_gate"] == {
        "found": False,
        "path": str(custom_ready_gate.resolve()),
        "exists": False,
        "sha256": None,
        "status": None,
        "blocker_class": None,
        "current_status": "fail",
        "current_blocker_class": "operator_values_required",
        "command_shell": "powershell",
        "command_text": "& python run_guarded_launch.py --status-only --require-ready",
    }


def test_guarded_launch_status_only_prefers_live_ready_gate_file_state(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    custom_index = tmp_path / "handoff" / "current.artifact-index.json"
    custom_ready_gate = tmp_path / "handoff" / "current.ready-gate.json"
    custom_index.parent.mkdir(parents=True, exist_ok=True)
    custom_ready_gate.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T12:50:00Z",
                "status": "blocked",
                "blocker_class": "preflight_blocked",
            }
        ),
        encoding="utf-8",
    )
    custom_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "blocker_class": "ready",
                "missing_required_roles": [],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "consumer_ready_gate_command_shell": "powershell",
                "consumer_ready_gate_command_text": "& python run_guarded_launch.py --status-only --require-ready",
                "recovery_command_status": "not_required",
                "artifacts": [
                    {
                        "role": "ready_gate_json",
                        "path": str(custom_ready_gate.resolve()),
                        "exists": False,
                        "sha256": None,
                    }
                ],
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
    assert payload["ready_gate"] == {
        "found": True,
        "path": str(custom_ready_gate.resolve()),
        "exists": True,
        "sha256": run_guarded_launch._sha256_file(custom_ready_gate),
        "generated_at": "2026-07-06T12:50:00Z",
        "status": "blocked",
        "blocker_class": "preflight_blocked",
        "current_status": "fail",
        "current_blocker_class": None,
        "command_shell": "powershell",
        "command_text": "& python run_guarded_launch.py --status-only --require-ready",
    }


def test_guarded_launch_status_only_self_ready_gate_output_is_current(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    custom_index = tmp_path / "handoff" / "current.artifact-index.json"
    custom_ready_gate = tmp_path / "handoff" / "current.ready-gate.json"
    artifacts = run_guarded_launch._artifact_paths(output_dir.resolve(), "blocked")
    artifacts["readiness_summary_json"].parent.mkdir(parents=True, exist_ok=True)
    custom_index.parent.mkdir(parents=True, exist_ok=True)
    artifacts["readiness_summary_json"].write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "preflight_blocked",
            }
        ),
        encoding="utf-8",
    )
    custom_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "blocker_class": "ready",
                "missing_required_roles": [],
                "consumer_packet_validation_status": "pass",
                "consumer_command_metadata_status": "pass",
                "consumer_readiness_operator_packet_consumer_command_metadata_status": "pass",
                "consumer_ready_gate_command_shell": "powershell",
                "consumer_ready_gate_command_text": "& python run_guarded_launch.py --status-only --require-ready",
                "recovery_command_status": "not_required",
                "artifacts": [
                    {
                        "role": "ready_gate_json",
                        "path": str(custom_ready_gate.resolve()),
                        "exists": False,
                        "sha256": None,
                    }
                ],
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
            "--require-ready",
            "--status-json-out",
            str(custom_ready_gate),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    persisted = json.loads(custom_ready_gate.read_text(encoding="utf-8"))
    assert result == 1
    assert payload == persisted
    assert payload["ready_gate"]["found"] is True
    assert payload["ready_gate"]["exists"] is True
    assert payload["ready_gate"]["path"] == str(custom_ready_gate.resolve())
    assert payload["ready_gate"]["generated_at"] == payload["generated_at"]
    assert payload["ready_gate"]["status"] == "blocked"
    assert payload["ready_gate"]["blocker_class"] == "preflight_blocked"
    assert payload["ready_gate"]["sha256"] is None
    assert payload["ready_gate"]["sha256_status"] == "self_referential_unavailable"


def test_guarded_launch_status_only_ready_gate_arg_overrides_index_path(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    output_dir = tmp_path / "launch-artifacts"
    custom_index = tmp_path / "handoff" / "current.artifact-index.json"
    stale_ready_gate = tmp_path / "handoff" / "stale.ready-gate.json"
    selected_ready_gate = tmp_path / "handoff" / "selected.ready-gate.json"
    custom_index.parent.mkdir(parents=True, exist_ok=True)
    stale_ready_gate.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T12:00:00Z",
                "status": "ready",
                "blocker_class": "ready",
            }
        ),
        encoding="utf-8",
    )
    selected_ready_gate.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T13:00:00Z",
                "status": "blocked",
                "blocker_class": "preflight_blocked",
            }
        ),
        encoding="utf-8",
    )
    custom_index.write_text(
        json.dumps(
            {
                "status": "pass",
                "blocker_class": "ready",
                "artifacts": [
                    {
                        "role": "ready_gate_json",
                        "path": str(stale_ready_gate.resolve()),
                        "exists": True,
                        "sha256": run_guarded_launch._sha256_file(stale_ready_gate),
                    }
                ],
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
            "--handoff-ready-gate-json-out",
            str(selected_ready_gate),
            "--status-only",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["artifacts"]["ready_gate_json"] == str(selected_ready_gate.resolve())
    assert payload["ready_gate"]["path"] == str(selected_ready_gate.resolve())
    assert payload["ready_gate"]["generated_at"] == "2026-07-06T13:00:00Z"
    assert payload["ready_gate"]["status"] == "blocked"
    assert payload["ready_gate"]["sha256"] == run_guarded_launch._sha256_file(selected_ready_gate)


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
                "blocker_class": "artifact_index_blocked",
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
    assert payload["artifact_index_recovery_summary"]["blocker_class"] == "ready"


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
