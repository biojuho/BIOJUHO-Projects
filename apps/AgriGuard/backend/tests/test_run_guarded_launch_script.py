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
    assert payload["handoff_command"][:2] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py"),
    ]
    assert payload["handoff_consumer_command"][:2] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py"),
    ]
    assert "--exit-zero-on-blocked" in payload["handoff_command"]
    assert "--exit-zero-on-blocked" in payload["handoff_consumer_command"]


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
    assert len(calls) == 3
    assert calls[0][1] == str(app_root.resolve() / "scripts" / "launch_compose.py")
    assert calls[1][1] == str(app_root.resolve() / "scripts" / "render_guarded_launch_handoff.py")
    assert calls[2][1] == str(app_root.resolve() / "scripts" / "consume_guarded_launch_handoff.py")
    assert "--exit-zero-on-blocked" in calls[1]
    assert "--exit-zero-on-blocked" in calls[2]


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
    assert len(calls) == 2


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
    assert len(calls) == 3


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
                    "operator_packet": {
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
    assert payload["operator_packet"]["operator_action_ids"] == ["fallback_action"]


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
