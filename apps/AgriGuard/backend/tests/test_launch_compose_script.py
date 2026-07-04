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
    assert payload["browser_smoke_command"] is None
    assert payload["will_run_browser_smoke_after_compose"] is False


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


def test_launch_compose_dry_run_browser_smoke_plan_waits_for_compose(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    browser_json = tmp_path / "browser.json"
    browser_output_dir = tmp_path / "browser-artifacts"

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--run-browser-smoke",
            "--browser-base-url",
            "http://localhost",
            "--browser-api-url",
            "http://localhost:8002",
            "--browser-smoke-json-out",
            str(browser_json),
            "--browser-smoke-output-dir",
            str(browser_output_dir),
            "--browser-smoke-mobile",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["compose_command"] == [
        "docker",
        "compose",
        "-f",
        str(app_root.resolve() / "docker-compose.yml"),
        "up",
        "-d",
        "--build",
        "--wait",
    ]
    assert payload["browser_smoke_command"] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "run_browser_smoke_suite.py"),
        "--base-url",
        "http://localhost",
        "--api-url",
        "http://localhost:8002",
        "--json-out",
        str(browser_json.resolve()),
        "--output-dir",
        str(browser_output_dir.resolve()),
        "--timeout-ms",
        "30000",
        "--mobile",
    ]
    assert payload["will_run_browser_smoke_after_compose"] is True


def test_launch_compose_runs_browser_smoke_after_compose_passes(tmp_path: Path) -> None:
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
            "--run-browser-smoke",
            "--no-compose-wait",
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
            "--build",
        ],
        [
            sys.executable,
            str(app_root.resolve() / "scripts" / "run_browser_smoke_suite.py"),
            "--base-url",
            launch_compose.DEFAULT_COMPOSE_BROWSER_BASE_URL,
            "--api-url",
            launch_compose.DEFAULT_COMPOSE_BROWSER_API_URL,
            "--json-out",
            str(launch_compose._default_browser_smoke_json_out(app_root.resolve())),
            "--output-dir",
            str(launch_compose._default_browser_smoke_output_dir(app_root.resolve())),
            "--timeout-ms",
            "30000",
        ],
    ]


def test_launch_compose_skips_browser_smoke_when_compose_fails(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0 if len(calls) == 1 else 7)

    result = launch_compose.main(
        ["--app-root", str(app_root), "--json-out", str(json_out), "--run-browser-smoke"],
        command_runner=runner,
    )

    assert result == 7
    assert len(calls) == 2
    assert calls[1][:5] == ["docker", "compose", "-f", str(app_root.resolve() / "docker-compose.yml"), "up"]
