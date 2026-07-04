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
                "recovery_command_status": "not_required",
                "consumer_readiness_operator_action_ids": ["fix_env_shape_validation"],
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
    assert "--exit-zero-on-blocked" in payload["handoff_command"]
    assert "--exit-zero-on-blocked" in payload["handoff_consumer_command"]
    assert _arg_after(payload["artifact_index_command"], "--json-out") == str(
        output_dir.resolve() / "release-check-artifact-index.json"
    )
    assert _arg_after(payload["artifact_index_command"], "--markdown-out") == str(
        output_dir.resolve() / "release-check-artifact-index.md"
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
    artifact_index_command = payload["artifact_index_command"]
    assert result == 0
    assert _arg_after(artifact_index_command, "--handoff-json") == str(handoff_json.resolve())
    assert _arg_after(artifact_index_command, "--handoff-markdown") == str(handoff_markdown.resolve())
    assert _arg_after(artifact_index_command, "--handoff-validation-json") == str(
        handoff_validation_json.resolve()
    )
    assert _arg_after(artifact_index_command, "--handoff-consumer-json") == str(handoff_consumer_json.resolve())
    assert _arg_after(artifact_index_command, "--ready-gate-json") == str(ready_gate_json.resolve())


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
    assert len(calls) == 7
    assert calls[0][1] == str(app_root.resolve() / "scripts" / "launch_compose.py")
    assert calls[1][1] == str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py")
    assert calls[2][1] == str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py")
    assert calls[3][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")
    assert calls[4][1] == str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py")
    assert calls[5][1] == str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py")
    assert calls[6][1] == str(app_root.resolve() / "scripts" / "index_guarded_launch_artifacts.py")
    assert "--exit-zero-on-blocked" in calls[1]
    assert "--exit-zero-on-blocked" in calls[2]
    assert _arg_after(calls[3], "--markdown-out").endswith("-artifact-index.md")


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
    assert payload["operator_packet"]["operator_action_ids"] == ["fallback_action"]
    assert payload["artifact_index_recovery_summary"] == {
        "required": False,
        "action": None,
        "status": "not_required",
        "note": None,
        "command": None,
    }


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
    assert payload["artifact_index"] == {
        "found": True,
        "path": str(custom_index.resolve()),
        "status": "pass",
        "missing_required_roles": [],
        "consumer_packet_validation_status": "pass",
        "recovery_command_status": "not_required",
    }
    assert payload["artifacts"]["artifact_index_json"] == str(custom_index.resolve())


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
