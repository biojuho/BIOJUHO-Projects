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
    assert payload["launch_report_json"] == str(launch_compose._default_launch_report_json_out(app_root.resolve()))
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
    assert payload["operator_packet_command"] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "render_launch_operator_packet.py"),
        "--preflight-json",
        str(json_out.resolve()),
        "--json-out",
        str(launch_compose._default_operator_packet_json_out(app_root.resolve())),
        "--markdown-out",
        str(launch_compose._default_operator_packet_markdown_out(app_root.resolve())),
        "--env-template-out",
        str(launch_compose._default_operator_env_template_out(app_root.resolve())),
        "--exit-zero-on-blocked",
    ]
    assert payload["will_run_browser_smoke_after_compose"] is False
    assert payload["will_write_operator_packet_on_preflight_failure"] is True


def test_launch_compose_stops_when_preflight_fails(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"
    operator_packet_json = tmp_path / "operator-packet.json"
    operator_packet_markdown = tmp_path / "operator-packet.md"
    operator_env_template = tmp_path / "operator.env.template"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 2:
            operator_packet_json.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "preflight_status": "fail",
                        "blocking_action_count": 1,
                        "operator_actions": [{"id": "set_secret_key"}],
                        "operator_env_template": {
                            "variables": ["AGRIGUARD_SECRET_KEY"],
                        },
                        "secrets_redacted": True,
                    }
                ),
                encoding="utf-8",
            )
            operator_packet_markdown.write_text("# Operator packet\n", encoding="utf-8")
            operator_env_template.write_text("AGRIGUARD_SECRET_KEY=<set-strong-secret-32-plus-chars>\n", encoding="utf-8")
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="packet written", stderr="")
        return subprocess.CompletedProcess(args=command, returncode=1, stdout="preflight failed", stderr="")

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--launch-report-json",
            str(launch_report_json),
            "--operator-packet-json",
            str(operator_packet_json),
            "--operator-packet-markdown",
            str(operator_packet_markdown),
            "--operator-env-template",
            str(operator_env_template),
        ],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 2
    assert calls[0][1] == str(app_root.resolve() / "scripts" / "launch_env_preflight.py")
    assert calls[1][1] == str(app_root.resolve() / "scripts" / "render_launch_operator_packet.py")
    assert calls[1][-1] == "--exit-zero-on-blocked"
    assert "docker compose up was not run" in capsys.readouterr().err
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["stage"] == "preflight"
    assert report["stop_reason"] == "preflight_failed"
    assert [item["name"] for item in report["results"]] == ["preflight", "operator_packet"]
    assert report["results"][0]["stdout_tail"] == "preflight failed"
    assert report["child_reports"]["preflight"] == {"found": False, "path": str(json_out.resolve())}
    assert report["child_reports"]["operator_packet"] == {
        "found": True,
        "path": str(operator_packet_json.resolve()),
        "markdown_path": str(operator_packet_markdown.resolve()),
        "env_template_path": str(operator_env_template.resolve()),
        "env_template_found": True,
        "status": "blocked",
        "preflight_status": "fail",
        "blocking_action_count": 1,
        "operator_action_ids": ["set_secret_key"],
        "env_template_variables": ["AGRIGUARD_SECRET_KEY"],
        "secrets_redacted": True,
    }


def test_launch_compose_runs_compose_after_preflight_passes(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"
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
            "--launch-report-json",
            str(launch_report_json),
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
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["stage"] == "compose"
    assert report["stop_reason"] is None
    assert [item["name"] for item in report["results"]] == ["preflight", "compose"]


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
    assert payload["launch_report_json"] == str(launch_compose._default_launch_report_json_out(app_root.resolve()))
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
    launch_report_json = tmp_path / "launch-report.json"
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
            "--launch-report-json",
            str(launch_report_json),
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
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["stage"] == "browser_smoke"
    assert report["stop_reason"] is None
    assert [item["name"] for item in report["results"]] == ["preflight", "compose", "browser_smoke"]


def test_launch_compose_skips_browser_smoke_when_compose_fails(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0 if len(calls) == 1 else 7)

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--launch-report-json",
            str(launch_report_json),
            "--run-browser-smoke",
        ],
        command_runner=runner,
    )

    assert result == 7
    assert len(calls) == 2
    assert calls[1][:5] == ["docker", "compose", "-f", str(app_root.resolve() / "docker-compose.yml"), "up"]
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["stage"] == "compose"
    assert report["stop_reason"] == "compose_failed"
    assert [item["name"] for item in report["results"]] == ["preflight", "compose"]


def test_launch_compose_reports_browser_smoke_failure(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=9 if len(calls) == 3 else 0, stderr="browser failed")

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--launch-report-json",
            str(launch_report_json),
            "--run-browser-smoke",
        ],
        command_runner=runner,
    )

    assert result == 9
    assert len(calls) == 3
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["stage"] == "browser_smoke"
    assert report["stop_reason"] == "browser_smoke_failed"
    assert report["results"][-1]["stderr_tail"] == "browser failed"


def test_launch_compose_embeds_preflight_child_report_summary(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"

    def runner(command, **kwargs):
        json_out.write_text(
            json.dumps(
                {
                    "status": "fail",
                    "errors": ["missing AGRIGUARD_SECRET_KEY"],
                    "warnings": ["diagnostic warning"],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=command, returncode=1)

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--launch-report-json",
            str(launch_report_json),
        ],
        command_runner=runner,
    )

    assert result == 1
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["child_reports"]["preflight"] == {
        "found": True,
        "path": str(json_out.resolve()),
        "status": "fail",
        "errors": ["missing AGRIGUARD_SECRET_KEY"],
        "warnings": ["diagnostic warning"],
    }


def test_launch_compose_embeds_browser_child_report_summary(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    browser_json = tmp_path / "browser.json"
    launch_report_json = tmp_path / "launch-report.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            json_out.write_text(json.dumps({"status": "pass", "errors": [], "warnings": []}), encoding="utf-8")
        if len(calls) == 3:
            browser_json.write_text(
                json.dumps(
                    {
                        "status": "fail",
                        "summary": {"total": 0, "prechecks_failed": 1},
                        "prechecks": [{"name": "backend_contract", "ok": False}],
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=command, returncode=1)
        return subprocess.CompletedProcess(args=command, returncode=0)

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--json-out",
            str(json_out),
            "--browser-smoke-json-out",
            str(browser_json),
            "--launch-report-json",
            str(launch_report_json),
            "--run-browser-smoke",
        ],
        command_runner=runner,
    )

    assert result == 1
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["child_reports"]["browser_smoke"] == {
        "found": True,
        "path": str(browser_json.resolve()),
        "status": "fail",
        "summary": {"total": 0, "prechecks_failed": 1},
        "prechecks": [{"name": "backend_contract", "ok": False}],
    }
