from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "launch_compose.py"
SPEC = importlib.util.spec_from_file_location("launch_compose", SCRIPT_PATH)
assert SPEC is not None
launch_compose = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(launch_compose)


def test_launch_compose_dry_run_prints_preflight_and_compose_plan(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--service",
            "backend",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["status"] == "dry_run"
    assert payload["preflight_command"] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "launch_env_preflight.py"),
        "--check-docker",
        "--json-out",
        str(json_out.resolve()),
    ]
    assert payload["compose_command"] == [
        "docker",
        "compose",
        "-f",
        str(app_root.resolve() / "docker-compose.yml"),
        "up",
        "-d",
        "--build",
        "backend",
    ]


def test_launch_compose_stops_when_preflight_fails(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=1)

    result = launch_compose.main(
        ["--app-root", str(app_root), "--json-out", str(json_out)],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 1
    assert calls[0][1] == str(app_root.resolve() / "scripts" / "launch_env_preflight.py")
    assert "docker compose up was not run" in capsys.readouterr().err


def test_launch_compose_runs_compose_after_preflight_passes(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0)

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--service",
            "postgres",
            "--service",
            "backend",
            "--no-build",
        ],
        command_runner=runner,
    )

    assert result == 0
    assert calls == [
        [
            sys.executable,
            str(app_root.resolve() / "scripts" / "launch_env_preflight.py"),
            "--check-docker",
            "--json-out",
            str(json_out.resolve()),
        ],
        [
            "docker",
            "compose",
            "-f",
            str(app_root.resolve() / "docker-compose.yml"),
            "up",
            "-d",
            "postgres",
            "backend",
        ],
    ]
