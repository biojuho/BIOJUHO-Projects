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


def _write_operator_packet_outputs(command: list[str]) -> None:
    json_out = Path(command[command.index("--json-out") + 1])
    markdown_out = Path(command[command.index("--markdown-out") + 1])
    env_template_out = Path(command[command.index("--env-template-out") + 1])
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(
        json.dumps(
            {
                "status": "blocked",
                "preflight_status": "env_shape_blocked",
                "blocking_action_count": 1,
                "operator_actions": [{"id": "fix_env_shape_validation"}],
                "operator_env_template": {
                    "variables": ["AGRIGUARD_SECRET_KEY"],
                },
                "secrets_redacted": True,
            }
        ),
        encoding="utf-8",
    )
    markdown_out.write_text("# Operator packet\n", encoding="utf-8")
    env_template_out.write_text("AGRIGUARD_SECRET_KEY=<set-strong-secret-32-plus-chars>\n", encoding="utf-8")


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
    assert payload["env_validation_command"] is None
    assert payload["readiness_summary_command"] is None
    assert payload["will_validate_env_file_shape_before_preflight"] is False
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
        "--env-validation-json",
        str(launch_compose._default_env_validation_json_out(app_root.resolve())),
        "--exit-zero-on-blocked",
    ]
    assert payload["will_run_browser_smoke_after_compose"] is False
    assert payload["will_write_operator_packet_on_preflight_failure"] is True


def test_launch_compose_dry_run_env_shape_validation_plan(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "launch.env"
    json_out = tmp_path / "preflight.json"
    validation_json = tmp_path / "validation.json"
    validation_markdown = tmp_path / "validation.md"

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--validate-env-file-shape",
            "--env-validation-json-out",
            str(validation_json),
            "--env-validation-markdown-out",
            str(validation_markdown),
            "--json-out",
            str(json_out),
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["will_validate_env_file_shape_before_preflight"] is True
    assert payload["env_validation_requires_single_env_file"] is False
    assert payload["env_validation_command"] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "validate_launch_env_template.py"),
        "--env-file",
        str(env_file.resolve()),
        "--json-out",
        str(validation_json.resolve()),
        "--markdown-out",
        str(validation_markdown.resolve()),
    ]
    assert payload["preflight_command"][-2:] == ["--env-file", str(env_file.resolve())]


def test_launch_compose_dry_run_readiness_summary_plan(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    launch_report_json = tmp_path / "launch-report.json"
    summary_json = tmp_path / "summary.json"
    summary_markdown = tmp_path / "summary.md"

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--launch-report-json",
            str(launch_report_json),
            "--readiness-summary-json",
            str(summary_json),
            "--readiness-summary-markdown",
            str(summary_markdown),
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["readiness_summary_json"] == str(summary_json.resolve())
    assert payload["readiness_summary_markdown"] == str(summary_markdown.resolve())
    assert payload["readiness_summary_command"] == [
        sys.executable,
        str(app_root.resolve() / "scripts" / "summarize_launch_readiness.py"),
        "--launch-report-json",
        str(launch_report_json.resolve()),
        "--env-validation-json",
        str(launch_compose._default_env_validation_json_out(app_root.resolve())),
        "--operator-packet-json",
        str(launch_compose._default_operator_packet_json_out(app_root.resolve())),
        "--json-out",
        str(summary_json.resolve()),
        "--exit-zero-on-blocked",
        "--markdown-out",
        str(summary_markdown.resolve()),
    ]


def test_launch_compose_stops_when_env_shape_validation_fails(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "launch.env"
    launch_report_json = tmp_path / "launch-report.json"
    validation_json = tmp_path / "validation.json"
    validation_markdown = tmp_path / "validation.md"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        if command[1].endswith("validate_launch_env_template.py"):
            validation_json.write_text(
                json.dumps(
                    {
                        "status": "fail",
                        "ready_for_preflight": False,
                        "placeholder_count": 6,
                        "missing_required_keys": [],
                        "forbidden_flags_enabled": [],
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=command, returncode=1, stdout="validation failed", stderr="")
        _write_operator_packet_outputs(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="packet written", stderr="")

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--validate-env-file-shape",
            "--env-validation-json-out",
            str(validation_json),
            "--env-validation-markdown-out",
            str(validation_markdown),
            "--launch-report-json",
            str(launch_report_json),
        ],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 2
    assert calls[0][1] == str(app_root.resolve() / "scripts" / "validate_launch_env_template.py")
    assert calls[1][1] == str(app_root.resolve() / "scripts" / "render_launch_operator_packet.py")
    assert "strict preflight was not run" in capsys.readouterr().err
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["stage"] == "env_shape_validation"
    assert report["stop_reason"] == "env_shape_validation_failed"
    assert [item["name"] for item in report["results"]] == ["env_validation", "operator_packet"]
    assert report["child_reports"]["env_validation"] == {
        "found": True,
        "path": str(validation_json.resolve()),
        "status": "fail",
        "ready_for_preflight": False,
        "placeholder_count": 6,
        "missing_required_keys": [],
        "forbidden_flags_enabled": [],
    }
    assert report["child_reports"]["preflight"] == {"found": False, "path": str(launch_compose._default_json_out(app_root.resolve()))}
    assert report["child_reports"]["operator_packet"]["found"] is True
    assert report["child_reports"]["operator_packet"]["preflight_status"] == "env_shape_blocked"
    assert report["child_reports"]["operator_packet"]["operator_action_ids"] == ["fix_env_shape_validation"]


def test_launch_compose_runs_preflight_after_env_shape_validation_passes(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    env_file = tmp_path / "launch.env"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"
    validation_json = tmp_path / "validation.json"
    validation_markdown = tmp_path / "validation.md"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            validation_json.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "ready_for_preflight": True,
                        "placeholder_count": 0,
                        "missing_required_keys": [],
                        "forbidden_flags_enabled": [],
                    }
                ),
                encoding="utf-8",
            )
        if len(calls) == 2:
            json_out.write_text(json.dumps({"status": "pass", "errors": [], "warnings": []}), encoding="utf-8")
        return subprocess.CompletedProcess(args=command, returncode=0)

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(env_file),
            "--validate-env-file-shape",
            "--env-validation-json-out",
            str(validation_json),
            "--env-validation-markdown-out",
            str(validation_markdown),
            "--json-out",
            str(json_out),
            "--launch-report-json",
            str(launch_report_json),
            "--service",
            "backend",
            "--no-build",
        ],
        command_runner=runner,
    )

    assert result == 0
    assert [call[1] if len(call) > 1 else call[0] for call in calls] == [
        str(app_root.resolve() / "scripts" / "validate_launch_env_template.py"),
        str(app_root.resolve() / "scripts" / "launch_env_preflight.py"),
        "compose",
    ]
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["stage"] == "compose"
    assert [item["name"] for item in report["results"]] == ["env_validation", "preflight", "compose"]
    assert report["child_reports"]["env_validation"]["ready_for_preflight"] is True


def test_launch_compose_env_shape_validation_requires_single_env_file(tmp_path: Path, capsys) -> None:
    app_root = tmp_path / "AgriGuard"
    launch_report_json = tmp_path / "launch-report.json"
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        _write_operator_packet_outputs(command)
        return subprocess.CompletedProcess(args=command, returncode=0)

    result = launch_compose.main(
        [
            "--app-root",
            str(app_root),
            "--env-file",
            str(tmp_path / "a.env"),
            "--env-file",
            str(tmp_path / "b.env"),
            "--validate-env-file-shape",
            "--launch-report-json",
            str(launch_report_json),
        ],
        command_runner=runner,
    )

    assert result == 2
    assert len(calls) == 1
    assert calls[0][1] == str(app_root.resolve() / "scripts" / "render_launch_operator_packet.py")
    assert "requires exactly one --env-file" in capsys.readouterr().err
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["stage"] == "env_shape_validation"
    assert report["stop_reason"] == "env_shape_validation_requires_single_env_file"
    assert [item["name"] for item in report["results"]] == ["operator_packet"]
    assert report["child_reports"]["operator_packet"]["found"] is True


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


def test_launch_compose_preflight_failure_can_emit_readiness_summary(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"
    operator_packet_json = tmp_path / "operator-packet.json"
    operator_packet_markdown = tmp_path / "operator-packet.md"
    operator_env_template = tmp_path / "operator.env.template"
    readiness_summary_json = tmp_path / "readiness-summary.json"
    readiness_summary_markdown = tmp_path / "readiness-summary.md"
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
                        "operator_actions": [{"id": "set_firebase_service_account_file"}],
                        "operator_env_template": {
                            "variables": ["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE"],
                        },
                        "secrets_redacted": True,
                    }
                ),
                encoding="utf-8",
            )
            operator_packet_markdown.write_text("# Operator packet\n", encoding="utf-8")
            operator_env_template.write_text(
                "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=<absolute-path-outside-repo-to-firebase-service-account.json>\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="packet written", stderr="")
        if len(calls) == 3:
            readiness_summary_json.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "blocker_class": "preflight_blocked",
                        "secrets_redacted": True,
                        "next_actions": ["Open the operator packet."],
                    }
                ),
                encoding="utf-8",
            )
            readiness_summary_markdown.write_text("# Summary\n", encoding="utf-8")
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="summary written", stderr="")
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
            "--readiness-summary-json",
            str(readiness_summary_json),
            "--readiness-summary-markdown",
            str(readiness_summary_markdown),
        ],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 3
    assert calls[2][1] == str(app_root.resolve() / "scripts" / "summarize_launch_readiness.py")
    assert "--exit-zero-on-blocked" in calls[2]
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert [item["name"] for item in report["results"]] == [
        "preflight",
        "operator_packet",
        "readiness_summary",
    ]
    assert report["child_reports"]["readiness_summary"] == {
        "found": True,
        "path": str(readiness_summary_json.resolve()),
        "status": "blocked",
        "blocker_class": "preflight_blocked",
        "secrets_redacted": True,
        "next_actions": ["Open the operator packet."],
    }


def test_launch_compose_readiness_summary_failure_does_not_reuse_stale_json(tmp_path: Path) -> None:
    app_root = tmp_path / "AgriGuard"
    json_out = tmp_path / "preflight.json"
    launch_report_json = tmp_path / "launch-report.json"
    operator_packet_json = tmp_path / "operator-packet.json"
    operator_packet_markdown = tmp_path / "operator-packet.md"
    operator_env_template = tmp_path / "operator.env.template"
    readiness_summary_json = tmp_path / "readiness-summary.json"
    readiness_summary_json.write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocker_class": "stale_blocker",
                "secrets_redacted": True,
            }
        ),
        encoding="utf-8",
    )
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
                        "operator_actions": [{"id": "set_firebase_service_account_file"}],
                        "secrets_redacted": True,
                    }
                ),
                encoding="utf-8",
            )
            operator_packet_markdown.write_text("# Operator packet\n", encoding="utf-8")
            operator_env_template.write_text(
                "AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=<absolute-path-outside-repo-to-firebase-service-account.json>\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="packet written", stderr="")
        if len(calls) == 3:
            return subprocess.CompletedProcess(args=command, returncode=2, stdout="", stderr="summary failed")
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
            "--readiness-summary-json",
            str(readiness_summary_json),
        ],
        command_runner=runner,
    )

    assert result == 1
    assert len(calls) == 3
    report = json.loads(launch_report_json.read_text(encoding="utf-8"))
    assert report["results"][-1]["name"] == "readiness_summary"
    assert report["results"][-1]["returncode"] == 2
    assert report["child_reports"]["readiness_summary"] == {
        "found": False,
        "path": str(readiness_summary_json.resolve()),
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
