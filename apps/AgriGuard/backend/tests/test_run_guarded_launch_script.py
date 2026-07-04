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
