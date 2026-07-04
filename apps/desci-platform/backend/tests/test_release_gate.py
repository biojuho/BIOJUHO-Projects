from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import release_gate  # noqa: E402

VALID_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _args(**overrides):
    defaults = {
        "profile": "local",
        "env_file": [],
        "ignore_process_env": False,
        "env_evidence_dir": "../../var",
        "python_command": sys.executable,
        "backend_tests": list(release_gate.DEFAULT_BACKEND_TESTS),
        "backend_test_timeout": release_gate.DEFAULT_BACKEND_TEST_TIMEOUT_SECONDS,
        "contract_step_timeout": release_gate.DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS,
        "skip_env": False,
        "skip_compose": False,
        "skip_backend": False,
        "skip_frontend": False,
        "skip_contracts": False,
        "frontend_step_timeout": release_gate.DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS,
        "frontend_test_timeout": release_gate.DEFAULT_FRONTEND_TEST_TIMEOUT_SECONDS,
        "preflight_step_timeout": release_gate.DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS,
        "runtime_smoke": False,
        "runtime_api": "http://127.0.0.1:8000",
        "runtime_frontend": "http://127.0.0.1:5173",
        "runtime_smoke_strict_ready": False,
        "runtime_smoke_strict_action_coverage": False,
        "runtime_smoke_step": [],
        "runtime_browser_expect_dev_auth": False,
        "runtime_browser_trace_on_failure_dir": None,
        "runtime_browser_screenshot_dir": None,
        "runtime_browser_only_check": [],
        "runtime_browser_timeout": None,
        "runtime_evidence_dir": "../../var",
        "runtime_smoke_timeout": release_gate.DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS,
        "external_readiness": False,
        "external_target": [],
        "external_evidence_dir": "../../var",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _write_valid_png(path: Path) -> None:
    path.write_bytes(VALID_PNG_1X1)


def _valid_launch_handoff():
    return {
        "ok": True,
        "release_decision": "go-with-watch",
        "operator_phase": "operator-review",
        "readiness_status": "degraded",
        "summary": {
            "total": 13,
            "ready_count": 12,
            "required_total": 7,
            "required_ready_count": 7,
            "blocker_count": 0,
            "warning_count": 1,
        },
        "score": {"overall_percent": 92, "required_percent": 100},
        "launch_blockers": [],
        "next_actions": [
            {
                "id": "database",
                "required": False,
                "status": "warn",
                "remediation": "Review database before launch.",
                "required_env": ["DATABASE_URL"],
            }
        ],
        "failures": [],
    }


def _valid_ready_web3():
    return {
        "ok": True,
        "status": "warn",
        "required": True,
        "configured": False,
        "available": True,
        "details": {
            "rpc_configured": True,
            "rpc_public_https": True,
            "contract_count": 1,
            "contracts": {
                "DSCI_CONTRACT_ADDRESS": True,
                "NFT_CONTRACT_ADDRESS": False,
                "DESCI_DAO_CONTRACT_ADDRESS": False,
            },
            "mock_mode_enabled": False,
            "mock_mode_allowed": False,
        },
        "failures": [],
    }


def _valid_ready_launch_action_coverage():
    return {
        "status": "match",
        "action_ids_match": True,
        "required_env_match": True,
        "ready_action_ids": ["database"],
        "launch_action_ids": ["database"],
        "shared_action_ids": ["database"],
        "ready_only_action_ids": [],
        "launch_only_action_ids": [],
        "ready_required_env": ["DATABASE_URL"],
        "launch_required_env": ["DATABASE_URL"],
        "shared_required_env": ["DATABASE_URL"],
        "ready_only_required_env": [],
        "launch_only_required_env": [],
    }


def _valid_launch_env_handoff():
    return {
        "schema_version": 1,
        "status": "watch",
        "secret_policy": "placeholder_only_no_secret_values",
        "required_action_ids": [],
        "optional_action_ids": ["database"],
        "required_env": [],
        "optional_env": ["DATABASE_URL"],
        "operator_copy_lines": [
            "# DSCI launch env handoff",
            "# Replace placeholders in the target secret manager or runtime env.",
            "# Optional before public launch hardening",
            "DATABASE_URL=<set-secure-value>",
        ],
    }


def test_release_gate_builds_expected_default_steps() -> None:
    steps = release_gate.build_steps(_args())

    assert [step.name for step in steps] == [
        "env-doctor",
        "compose-config",
        "backend-tests",
        "frontend-lint",
        "frontend-typecheck",
        "frontend-tests",
        "frontend-build",
        "frontend-bundle",
        "contracts-build",
        "contracts-config-tests",
        "contracts-tests",
        "contracts-deploy-core",
        "contracts-deploy-nft",
    ]


def test_release_gate_default_steps_all_have_parent_timeout() -> None:
    steps = release_gate.build_steps(_args())

    missing_timeouts = [step.name for step in steps if step.timeout_seconds is None]

    assert missing_timeouts == []


def test_release_gate_optional_external_and_runtime_steps_all_have_parent_timeout(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            external_readiness=True,
            runtime_smoke=True,
            runtime_evidence_dir=str(tmp_path),
        )
    )

    missing_timeouts = [step.name for step in steps if step.timeout_seconds is None]

    assert missing_timeouts == []


def test_release_gate_can_skip_frontend_and_compose() -> None:
    steps = release_gate.build_steps(_args(skip_frontend=True, skip_compose=True))

    assert [step.name for step in steps] == [
        "env-doctor",
        "backend-tests",
        "contracts-build",
        "contracts-config-tests",
        "contracts-tests",
        "contracts-deploy-core",
        "contracts-deploy-nft",
    ]


def test_release_gate_can_skip_contracts() -> None:
    steps = release_gate.build_steps(_args(skip_contracts=True, skip_compose=True))

    assert [step.name for step in steps] == [
        "env-doctor",
        "backend-tests",
        "frontend-lint",
        "frontend-typecheck",
        "frontend-tests",
        "frontend-build",
        "frontend-bundle",
    ]


def test_release_gate_preserves_uv_python_runner() -> None:
    steps = release_gate.build_steps(_args(python_command="uv run python", skip_frontend=True, skip_compose=True))

    backend = next(step for step in steps if step.name == "backend-tests")
    assert backend.command[:3] == ("uv", "run", "python")
    assert "tests" in backend.command
    assert backend.timeout_seconds == release_gate.DEFAULT_BACKEND_TEST_TIMEOUT_SECONDS


def test_release_gate_auto_python_runner_uses_uv_project_when_available(monkeypatch) -> None:
    monkeypatch.setattr(release_gate.shutil, "which", lambda name: "C:/tools/uv.exe" if name == "uv" else None)
    monkeypatch.setattr(release_gate, "_has_uv_project_context", lambda: True)

    assert release_gate._python_command("auto") == ("uv", "run", "python")
    assert release_gate._python_command_report("auto") == {
        "requested": "auto",
        "strategy": "auto_uv_project",
        "resolved": ["uv", "run", "python"],
        "resolved_display": "uv run python",
    }


def test_release_gate_auto_python_runner_falls_back_without_uv(monkeypatch) -> None:
    monkeypatch.setattr(release_gate.shutil, "which", lambda _name: None)
    monkeypatch.setattr(release_gate, "_has_uv_project_context", lambda: True)

    assert release_gate._python_command("auto") == (sys.executable,)


def test_release_gate_system_python_runner_uses_current_executable() -> None:
    assert release_gate._python_command("system") == (sys.executable,)
    assert release_gate._python_command_report("system") == {
        "requested": "system",
        "strategy": "system",
        "resolved": [sys.executable],
        "resolved_display": release_gate._format_command((sys.executable,)),
    }


def test_release_gate_cli_defaults_to_auto_python_command(monkeypatch) -> None:
    captured = {}

    def fake_build_steps(args):
        captured["python_command"] = args.python_command
        captured["backend_test_timeout"] = args.backend_test_timeout
        captured["contract_step_timeout"] = args.contract_step_timeout
        captured["frontend_step_timeout"] = args.frontend_step_timeout
        captured["frontend_test_timeout"] = args.frontend_test_timeout
        captured["preflight_step_timeout"] = args.preflight_step_timeout
        captured["runtime_smoke_timeout"] = args.runtime_smoke_timeout
        return []

    monkeypatch.setattr(release_gate, "build_steps", fake_build_steps)
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--dry-run"])

    assert release_gate.main() == 0
    assert captured["python_command"] == release_gate.AUTO_PYTHON_COMMAND
    assert captured["backend_test_timeout"] == release_gate.DEFAULT_BACKEND_TEST_TIMEOUT_SECONDS
    assert captured["contract_step_timeout"] == release_gate.DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS
    assert captured["frontend_step_timeout"] == release_gate.DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS
    assert captured["frontend_test_timeout"] == release_gate.DEFAULT_FRONTEND_TEST_TIMEOUT_SECONDS
    assert captured["preflight_step_timeout"] == release_gate.DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS
    assert captured["runtime_smoke_timeout"] == release_gate.DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS


def test_release_gate_cli_can_disable_parent_timeouts(monkeypatch) -> None:
    captured = {}

    def fake_build_steps(args):
        captured["backend_test_timeout"] = args.backend_test_timeout
        captured["contract_step_timeout"] = args.contract_step_timeout
        captured["frontend_step_timeout"] = args.frontend_step_timeout
        captured["frontend_test_timeout"] = args.frontend_test_timeout
        captured["preflight_step_timeout"] = args.preflight_step_timeout
        captured["runtime_smoke_timeout"] = args.runtime_smoke_timeout
        return []

    monkeypatch.setattr(release_gate, "build_steps", fake_build_steps)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release_gate.py",
            "--dry-run",
            "--backend-test-timeout",
            "0",
            "--contract-step-timeout",
            "0",
            "--preflight-step-timeout",
            "0",
            "--runtime-smoke-timeout",
            "0",
            "--frontend-step-timeout",
            "0",
            "--frontend-test-timeout",
            "0",
        ],
    )

    assert release_gate.main() == 0
    assert captured["backend_test_timeout"] is None
    assert captured["contract_step_timeout"] is None
    assert captured["frontend_step_timeout"] is None
    assert captured["frontend_test_timeout"] is None
    assert captured["preflight_step_timeout"] is None
    assert captured["runtime_smoke_timeout"] is None


def test_release_gate_cli_help_lists_timeout_options(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--help"])

    try:
        release_gate.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("--help should exit through argparse")

    output = capsys.readouterr().out
    for option in (
        "--preflight-step-timeout",
        "--backend-test-timeout",
        "--contract-step-timeout",
        "--runtime-smoke-timeout",
        "--runtime-browser-timeout",
        "--frontend-step-timeout",
        "--frontend-test-timeout",
    ):
        assert option in output
    assert "Use 0 to disable the parent timeout." in output


def test_release_gate_cli_prints_report_schema_without_running_steps(monkeypatch, capsys) -> None:
    def fail_build_steps(_args):
        raise AssertionError("schema printing must not build release-gate steps")

    monkeypatch.setattr(release_gate, "build_steps", fail_build_steps)
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--print-report-schema"])

    assert release_gate.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    result_items = payload["properties"]["results"]["items"]
    assert result_items["required"] == [
        "name",
        "command",
        "cwd",
        "returncode",
        "elapsed_ms",
        "command_argv",
        "skipped",
        "attempts",
        "ok",
    ]
    assert result_items["properties"]["returncode"]["type"] == "integer"
    assert result_items["properties"]["elapsed_ms"]["type"] == "number"
    assert result_items["properties"]["command_argv"]["items"]["type"] == "string"
    assert result_items["properties"]["timeout_seconds"]["type"] == "number"
    assert result_items["properties"]["failures"]["items"]["type"] == "string"
    assert payload["properties"]["browser_trace_artifact_summary"]["properties"]["trace_viewer_commands"]


def test_release_gate_cli_json_report_includes_python_command_provenance(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate.json"
    step = release_gate.GateStep(
        name="noop",
        command=("uv", "run", "python", "--version"),
        cwd=release_gate.PROJECT_ROOT,
    )

    def fake_run_step(_step, *, dry_run):
        assert dry_run is True
        return release_gate.GateResult(
            name="noop",
            command="uv run python --version",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=0.0,
            command_argv=["uv", "run", "python", "--version"],
            skipped=True,
        )

    monkeypatch.setattr(release_gate, "build_steps", lambda _args: [step])
    monkeypatch.setattr(release_gate, "_python_command_report", lambda value: {"requested": value, "resolved": ["uv", "run", "python"]})
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--dry-run", "--json-out", str(report_path)])

    assert release_gate.main() == 0

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["python_command"] == {"requested": "auto", "resolved": ["uv", "run", "python"]}
    assert payload["results"][0]["command_argv"] == ["uv", "run", "python", "--version"]


def test_release_gate_preserves_python_executable_paths_with_spaces(tmp_path: Path) -> None:
    python_path = tmp_path / "Python With Space" / "python.exe"
    python_path.parent.mkdir()
    python_path.write_text("", encoding="utf-8")

    steps = release_gate.build_steps(_args(python_command=str(python_path), skip_frontend=True, skip_compose=True))

    assert steps[0].command[0] == str(python_path)
    assert " " in steps[0].command[0]


def test_release_gate_can_include_external_readiness() -> None:
    evidence_dir = Path("D:/tmp/desci-evidence") if release_gate.os.name == "nt" else Path("/tmp/desci-evidence")
    steps = release_gate.build_steps(
        _args(
            external_readiness=True,
            external_target=["railway", "github"],
            external_evidence_dir=str(evidence_dir),
            env_file=[".env.production"],
            ignore_process_env=True,
            skip_frontend=True,
            skip_contracts=True,
            skip_compose=True,
        )
    )

    assert [step.name for step in steps[:3]] == ["env-doctor", "deploy-readiness", "backend-tests"]
    readiness = steps[1]
    env_doctor = steps[0]
    assert env_doctor.timeout_seconds == release_gate.DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS
    assert readiness.timeout_seconds == release_gate.DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS
    assert "--json-out" in env_doctor.command
    assert any(Path(part).name == "desci-env-doctor-release-gate.json" for part in env_doctor.command)
    assert readiness.command[:2] == (sys.executable, "scripts/deploy_readiness.py")
    assert readiness.command.count("--target") == 2
    assert "railway" in readiness.command
    assert "github" in readiness.command
    assert "--ignore-process-env" in readiness.command
    assert "--json-out" in readiness.command
    assert str(evidence_dir / "desci-deploy-readiness-release-gate.json") in readiness.command


def test_release_gate_preflight_steps_have_parent_timeout() -> None:
    steps = release_gate.build_steps(
        _args(
            external_readiness=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    preflight_timeouts = {step.name: step.timeout_seconds for step in steps}

    assert preflight_timeouts["env-doctor"] == release_gate.DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS
    assert preflight_timeouts["deploy-readiness"] == release_gate.DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS
    assert preflight_timeouts["compose-config"] == release_gate.DEFAULT_PREFLIGHT_STEP_TIMEOUT_SECONDS


def test_release_gate_can_include_runtime_smoke_evidence(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_api="https://api.example.com",
            runtime_frontend="https://app.example.com",
            runtime_smoke_strict_ready=True,
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    assert [step.name for step in steps] == ["product-smoke", "browser-smoke"]
    product_smoke, browser_smoke = steps
    assert product_smoke.timeout_seconds == release_gate.DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS
    assert browser_smoke.timeout_seconds == release_gate.DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS
    assert product_smoke.command[:2] == (sys.executable, "scripts/product_smoke.py")
    assert "--strict-ready" in product_smoke.command
    assert "https://api.example.com" in product_smoke.command
    assert str(tmp_path / "desci-product-smoke-release-gate.json") in product_smoke.command
    assert browser_smoke.command[:2] == (sys.executable, "scripts/browser_smoke.py")
    assert "https://app.example.com" in browser_smoke.command
    assert str(tmp_path / "desci-browser-smoke-release-gate.json") in browser_smoke.command
    assert "--expect-dev-auth" not in browser_smoke.command


def test_release_gate_runtime_smoke_steps_have_parent_timeout(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    runtime_timeouts = {step.name: step.timeout_seconds for step in steps}

    assert runtime_timeouts["product-smoke"] == release_gate.DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS
    assert runtime_timeouts["browser-smoke"] == release_gate.DEFAULT_RUNTIME_SMOKE_TIMEOUT_SECONDS


def test_release_gate_runtime_browser_smoke_can_expect_dev_auth(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_frontend="http://127.0.0.1:5175",
            runtime_browser_expect_dev_auth=True,
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    browser_smoke = steps[1]

    assert browser_smoke.name == "browser-smoke"
    assert browser_smoke.command[:2] == (sys.executable, "scripts/browser_smoke.py")
    assert "--expect-dev-auth" in browser_smoke.command


def test_release_gate_runtime_browser_smoke_can_capture_failure_traces(tmp_path: Path) -> None:
    trace_dir = tmp_path / "browser-traces"
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_frontend="http://127.0.0.1:5175",
            runtime_browser_trace_on_failure_dir=str(trace_dir),
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    browser_smoke = steps[1]

    assert browser_smoke.name == "browser-smoke"
    assert browser_smoke.command[:2] == (sys.executable, "scripts/browser_smoke.py")
    assert "--trace-on-failure-dir" in browser_smoke.command
    assert str(trace_dir) in browser_smoke.command


def test_release_gate_runtime_browser_smoke_can_capture_success_screenshots(tmp_path: Path) -> None:
    screenshot_dir = tmp_path / "browser-screenshots"
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_frontend="http://127.0.0.1:5175",
            runtime_browser_screenshot_dir=str(screenshot_dir),
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    browser_smoke = steps[1]

    assert browser_smoke.name == "browser-smoke"
    assert browser_smoke.command[:2] == (sys.executable, "scripts/browser_smoke.py")
    assert "--screenshot-dir" in browser_smoke.command
    assert str(screenshot_dir) in browser_smoke.command


def test_release_gate_runtime_smoke_can_target_single_browser_check(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_smoke_step=["browser"],
            runtime_frontend="http://127.0.0.1:5175",
            runtime_browser_only_check=["dashboard-readiness-refresh"],
            runtime_browser_timeout=0.75,
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    assert [step.name for step in steps] == ["browser-smoke"]
    browser_smoke = steps[0]
    assert browser_smoke.command[:2] == (sys.executable, "scripts/browser_smoke.py")
    assert "--only-check" in browser_smoke.command
    assert "dashboard-readiness-refresh" in browser_smoke.command
    assert "--timeout" in browser_smoke.command
    assert "0.75" in browser_smoke.command
    assert "scripts/product_smoke.py" not in browser_smoke.command


def test_release_gate_runtime_smoke_can_trace_discovery_biolinker_handoff(tmp_path: Path) -> None:
    trace_dir = tmp_path / "browser-traces"
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_smoke_step=["browser"],
            runtime_frontend="http://127.0.0.1:5176",
            runtime_browser_expect_dev_auth=True,
            runtime_browser_trace_on_failure_dir=str(trace_dir),
            runtime_browser_only_check=["notices-discovery-biolinker-handoff"],
            runtime_browser_timeout=5.0,
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    assert [step.name for step in steps] == ["browser-smoke"]
    browser_smoke = steps[0]
    assert browser_smoke.command[:2] == (sys.executable, "scripts/browser_smoke.py")
    assert "--expect-dev-auth" in browser_smoke.command
    assert "--trace-on-failure-dir" in browser_smoke.command
    assert str(trace_dir) in browser_smoke.command
    assert "--only-check" in browser_smoke.command
    assert "notices-discovery-biolinker-handoff" in browser_smoke.command
    assert "--timeout" in browser_smoke.command
    assert "5.0" in browser_smoke.command
    assert str(tmp_path / "desci-browser-smoke-release-gate.json") in browser_smoke.command
    assert "scripts/product_smoke.py" not in browser_smoke.command


def test_release_gate_runtime_smoke_can_target_product_only(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_smoke_step=["product"],
            runtime_api="https://api.example.com",
            runtime_frontend="https://app.example.com",
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    assert [step.name for step in steps] == ["product-smoke"]
    product_smoke = steps[0]
    assert product_smoke.command[:2] == (sys.executable, "scripts/product_smoke.py")
    assert "scripts/browser_smoke.py" not in product_smoke.command


def test_release_gate_normalizes_env_file_paths(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / "release.env"
    env_file.write_text("ENV=production\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    steps = release_gate.build_steps(
        _args(
            external_readiness=True,
            env_file=[os.path.relpath(env_file, tmp_path)],
            ignore_process_env=True,
            skip_frontend=True,
            skip_contracts=True,
            skip_compose=True,
        )
    )

    env_doctor = steps[0]
    readiness = steps[1]
    expected = str(env_file.resolve())

    assert expected in env_doctor.command
    assert expected in readiness.command


def test_release_gate_external_readiness_records_json_artifact(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            external_readiness=True,
            external_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    assert [step.name for step in steps] == ["deploy-readiness"]
    result = release_gate.run_step(steps[0], dry_run=True)

    assert result.artifacts == [str(tmp_path / "desci-deploy-readiness-release-gate.json")]


def test_release_gate_env_doctor_records_json_artifact(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            env_evidence_dir=str(tmp_path),
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    assert [step.name for step in steps] == ["env-doctor"]
    result = release_gate.run_step(steps[0], dry_run=True)

    assert result.artifacts == [str(tmp_path / "desci-env-doctor-release-gate.json")]
    assert result.command_argv == list(steps[0].command)


def test_release_gate_uses_lts_frontend_test_runner() -> None:
    steps = release_gate.build_steps(_args(skip_backend=True, skip_contracts=True, skip_compose=True, skip_env=True))

    frontend_tests = next(step for step in steps if step.name == "frontend-tests")
    assert frontend_tests.command == (
        release_gate._node_command(),
        "scripts/run-vitest-split.mjs",
    )
    assert frontend_tests.timeout_seconds == release_gate.DEFAULT_FRONTEND_TEST_TIMEOUT_SECONDS


def test_release_gate_frontend_non_test_steps_have_parent_timeout() -> None:
    steps = release_gate.build_steps(_args(skip_backend=True, skip_contracts=True, skip_compose=True, skip_env=True))

    frontend_timeouts = {step.name: step.timeout_seconds for step in steps if step.name.startswith("frontend-")}

    assert frontend_timeouts["frontend-lint"] == release_gate.DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS
    assert frontend_timeouts["frontend-typecheck"] == release_gate.DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS
    assert frontend_timeouts["frontend-build"] == release_gate.DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS
    assert frontend_timeouts["frontend-bundle"] == release_gate.DEFAULT_FRONTEND_STEP_TIMEOUT_SECONDS
    assert frontend_timeouts["frontend-tests"] == release_gate.DEFAULT_FRONTEND_TEST_TIMEOUT_SECONDS


def test_release_gate_frontend_test_timeout_sets_vitest_child_timeout() -> None:
    step = release_gate.GateStep(
        name="frontend-tests",
        command=(release_gate._node_command(), "scripts/run-vitest-split.mjs"),
        cwd=release_gate.FRONTEND_DIR,
        timeout_seconds=12.5,
    )

    env = release_gate._step_env(step)

    assert env["DESCI_VITEST_TIMEOUT_MS"] == "11250"


def test_release_gate_step_timeout_is_reported(monkeypatch) -> None:
    def fake_run_subprocess(step, env):  # noqa: ARG001
        raise release_gate.subprocess.TimeoutExpired(cmd=step.command, timeout=2.5)

    monkeypatch.setattr(release_gate, "_run_subprocess", fake_run_subprocess)
    step = release_gate.GateStep(
        name="frontend-tests",
        command=(release_gate._node_command(), "scripts/run-vitest-split.mjs"),
        cwd=release_gate.FRONTEND_DIR,
        timeout_seconds=2.5,
    )

    result = release_gate.run_step(step, dry_run=False)
    report = release_gate.result_report(result)

    assert result.ok is False
    assert result.returncode == 124
    assert result.failures == ["timed out after 2.5s"]
    assert report["failures"] == ["timed out after 2.5s"]
    assert report["command_argv"] == list(step.command)
    assert report["timeout_seconds"] == 2.5


def test_release_gate_uses_local_node_for_frontend_build_and_hardhat() -> None:
    steps = release_gate.build_steps(_args(skip_backend=True, skip_compose=True, skip_env=True))

    frontend_build = next(step for step in steps if step.name == "frontend-build")
    contracts_build = next(step for step in steps if step.name == "contracts-build")
    contracts_config = next(step for step in steps if step.name == "contracts-config-tests")

    assert frontend_build.command == (
        release_gate._node_command(),
        "node_modules/vite/bin/vite.js",
        "build",
        "--configLoader",
        "native",
    )
    assert contracts_build.command[:2] == (release_gate._node_command(), "node_modules/hardhat/dist/src/cli.js")
    assert contracts_config.command == (release_gate._node_command(), "--test", "tests/runtime-config.test.js")


def test_release_gate_contract_steps_have_parent_timeout() -> None:
    steps = release_gate.build_steps(_args(skip_backend=True, skip_compose=True, skip_env=True, skip_frontend=True))

    contract_timeouts = {step.name: step.timeout_seconds for step in steps if step.name.startswith("contracts-")}

    assert contract_timeouts["contracts-build"] == release_gate.DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS
    assert contract_timeouts["contracts-config-tests"] == release_gate.DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS
    assert contract_timeouts["contracts-tests"] == release_gate.DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS
    assert contract_timeouts["contracts-deploy-core"] == release_gate.DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS
    assert contract_timeouts["contracts-deploy-nft"] == release_gate.DEFAULT_CONTRACT_STEP_TIMEOUT_SECONDS


def test_release_gate_retries_transient_steps(monkeypatch) -> None:
    calls = []

    def fake_run_subprocess(step, env):
        calls.append((step.name, env["PYTHONUTF8"]))
        return 1 if len(calls) == 1 else 0

    monkeypatch.setattr(release_gate, "_run_subprocess", fake_run_subprocess)
    monkeypatch.setattr(release_gate.time, "sleep", lambda _seconds: None)

    step = release_gate.GateStep(
        name="contracts-build",
        command=("npm.cmd", "run", "build"),
        cwd=release_gate.CONTRACTS_DIR,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is True
    assert result.returncode == 0
    assert result.attempts == 2
    assert calls == [("contracts-build", "1"), ("contracts-build", "1")]


def test_release_gate_final_summary_prints_flush(monkeypatch) -> None:
    step = release_gate.GateStep(
        name="noop",
        command=(sys.executable, "--version"),
        cwd=release_gate.PROJECT_ROOT,
    )
    returncode = {"value": 0}
    print_calls = []

    def fake_run_step(_step, *, dry_run):
        assert dry_run is True
        return release_gate.GateResult(
            name="noop",
            command="python --version",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=returncode["value"],
            elapsed_ms=1.0,
        )

    def fake_print(*args, **kwargs):
        print_calls.append((args, kwargs))

    monkeypatch.setattr(release_gate, "build_steps", lambda _args: [step])
    monkeypatch.setattr(release_gate, "run_step", fake_run_step)
    monkeypatch.setattr(release_gate, "print", fake_print, raising=False)
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--dry-run"])

    assert release_gate.main() == 0
    assert print_calls[-1] == (("\n[release-gate] OK (1 step(s))",), {"flush": True})

    print_calls.clear()
    returncode["value"] = 7

    assert release_gate.main() == 7
    assert print_calls[-1] == (("\n[release-gate] FAILED at noop",), {"flush": True})


def test_release_gate_cli_strict_action_coverage_fails_on_drift(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate.json"
    product_artifact = tmp_path / "product-smoke.json"
    browser_artifact = tmp_path / "browser-smoke.json"
    product_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_handoff": {
                    "ok": True,
                    "release_decision": "no-go",
                    "operator_phase": "blocked",
                    "readiness_status": "blocked",
                    "summary": {
                        "total": 7,
                        "ready_count": 5,
                        "required_total": 4,
                        "required_ready_count": 3,
                        "blocker_count": 1,
                        "warning_count": 1,
                    },
                    "score": {"overall_percent": 71, "required_percent": 75},
                    "launch_blockers": ["stripe"],
                    "next_actions": [
                        {
                            "id": "stripe",
                            "required": True,
                            "status": "fail",
                            "remediation": "Configure Stripe secret.",
                            "required_env": ["STRIPE_SECRET_KEY"],
                        },
                        {
                            "id": "database",
                            "required": False,
                            "status": "warn",
                            "remediation": "Review database before launch.",
                            "required_env": ["DATABASE_URL"],
                        },
                    ],
                    "failures": [],
                },
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 20.0,
                "skip_protected": False,
                "skip_login_validation": True,
                "expect_dev_auth": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_control": {
                    "check_name": "dashboard-readiness-refresh",
                    "ok": True,
                    "evidence_source": "browser-smoke-dashboard-fixture",
                    "api_mocked": True,
                    "mocked_endpoints": ["/ready", "/launch"],
                    "release_decision": "no-go",
                    "operator_phase": "blocked",
                    "readiness_status": "blocked",
                    "summary": {
                        "ready_count": 5,
                        "total": 7,
                        "required_ready_count": 3,
                        "required_total": 4,
                        "blocker_count": 1,
                        "warning_count": 1,
                    },
                    "score": {"overall_percent": 71, "required_percent": 75},
                    "launch_blockers": ["stripe"],
                    "next_action_count": 2,
                    "next_action_ids": ["stripe", "web3"],
                    "next_action_required_env": ["STRIPE_SECRET_KEY", "WEB3_RPC_URL"],
                    "failures": [],
                },
                "failures": [],
                "checks": [
                    {"name": "dashboard-readiness-refresh", "path": "/dashboard", "ok": True, "failures": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    steps = [
        release_gate.GateStep("product-smoke", ("python", "scripts/product_smoke.py"), release_gate.PROJECT_ROOT),
        release_gate.GateStep("browser-smoke", ("python", "scripts/browser_smoke.py"), release_gate.PROJECT_ROOT),
    ]
    results = {
        "product-smoke": release_gate.GateResult(
            name="product-smoke",
            command=f"python scripts/product_smoke.py --json-out {product_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=12.5,
            artifacts=[str(product_artifact)],
        ),
        "browser-smoke": release_gate.GateResult(
            name="browser-smoke",
            command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=30.0,
            artifacts=[str(browser_artifact)],
        ),
    }

    monkeypatch.setattr(release_gate, "build_steps", lambda _args: steps)
    monkeypatch.setattr(release_gate, "run_step", lambda step, *, dry_run: results[step.name])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release_gate.py",
            "--runtime-smoke-strict-action-coverage",
            "--json-out",
            str(report_path),
        ],
    )

    assert release_gate.main() == 1

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["summary"]["failed_step"] == "launch-action-coverage"
    assert payload["launch_action_coverage_comparison"]["status"] == "drift"
    assert payload["launch_action_coverage_comparison"]["live_only_action_ids"] == ["database"]
    assert payload["launch_action_coverage_comparison"]["browser_only_required_env"] == ["WEB3_RPC_URL"]
    assert payload["results"][-1] == {
        "name": "launch-action-coverage",
            "command": "release_gate strict launch action coverage comparison",
            "cwd": str(release_gate.PROJECT_ROOT),
            "returncode": 1,
            "elapsed_ms": 0.0,
            "command_argv": ["release_gate", "strict", "launch-action-coverage"],
            "skipped": False,
            "attempts": 1,
            "failures": [
            "strict launch action coverage drift: live and browser launch action coverage differ",
            "live-only action ids: database",
            "browser-only action ids: web3",
            "live-only required env: DATABASE_URL",
            "browser-only required env: WEB3_RPC_URL",
        ],
        "ok": False,
    }


def test_release_gate_cli_strict_action_coverage_skips_dry_run(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate.json"
    step = release_gate.GateStep(
        "product-smoke",
        ("python", "scripts/product_smoke.py", "--json-out", str(tmp_path / "product.json")),
        release_gate.PROJECT_ROOT,
    )

    monkeypatch.setattr(release_gate, "build_steps", lambda _args: [step])
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--dry-run", "--runtime-smoke-strict-action-coverage", "--json-out", str(report_path)])

    assert release_gate.main() == 0

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert [result["name"] for result in payload["results"]] == ["product-smoke"]
    assert "launch_action_coverage_comparison" not in payload


def test_release_gate_isolates_contract_cache_environment(monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", "C:\\shared-cache")

    step = release_gate.GateStep(
        name="contracts-build",
        command=(release_gate._node_command(), "node_modules/hardhat/dist/src/cli.js", "build"),
        cwd=release_gate.CONTRACTS_DIR,
    )

    env = release_gate._step_env(step)

    if release_gate.os.name == "nt":
        assert env["LOCALAPPDATA"] == str(release_gate.CONTRACT_LOCALAPPDATA_DIR)
    else:
        assert env["XDG_CACHE_HOME"] == str(release_gate.CONTRACT_LOCALAPPDATA_DIR / "cache")


def test_release_gate_does_not_isolate_frontend_environment(monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", "C:\\shared-cache")

    step = release_gate.GateStep(
        name="frontend-tests",
        command=(release_gate._node_command(), "node_modules/vitest/vitest.mjs", "run"),
        cwd=release_gate.FRONTEND_DIR,
    )

    env = release_gate._step_env(step)

    assert env["LOCALAPPDATA"] == "C:\\shared-cache"


def test_release_gate_seeds_contract_cache_before_subprocess(monkeypatch) -> None:
    seeded = []

    def fake_seed(env):
        seeded.append(env)

    def fake_run_subprocess(step, env):
        return 0

    monkeypatch.setattr(release_gate, "_seed_contract_cache", fake_seed)
    monkeypatch.setattr(release_gate, "_run_subprocess", fake_run_subprocess)

    step = release_gate.GateStep(
        name="contracts-build",
        command=(release_gate._node_command(), "node_modules/hardhat/dist/src/cli.js", "build"),
        cwd=release_gate.CONTRACTS_DIR,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is True
    assert len(seeded) == 1


def test_release_gate_does_not_retry_non_transient_steps(monkeypatch) -> None:
    calls = []

    def fake_run_subprocess(step, env):
        calls.append(step.name)
        return 1

    monkeypatch.setattr(release_gate, "_run_subprocess", fake_run_subprocess)

    step = release_gate.GateStep(
        name="backend-tests",
        command=(sys.executable, "-m", "pytest", "tests", "-q"),
        cwd=release_gate.BACKEND_DIR,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.returncode == 1
    assert result.attempts == 1
    assert calls == ["backend-tests"]


def test_release_gate_fails_successful_step_when_json_artifact_is_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", "missing-evidence.json"),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.returncode == 1
    assert result.artifacts == ["missing-evidence.json"]
    assert result.artifact_failures == ["missing expected JSON evidence artifact: missing-evidence.json"]


def test_release_gate_passes_successful_step_when_json_artifact_exists(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text('{"ok": true}', encoding="utf-8")
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="custom-json-step",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is True
    assert result.returncode == 0
    assert result.artifact_failures is None


def test_release_gate_passes_deploy_readiness_artifact_with_expected_shape(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "deploy-readiness.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "targets": ["railway"],
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [
                    {
                        "id": "railway_env",
                        "target": "railway",
                        "label": "Runtime",
                        "status": "pass",
                        "required": True,
                        "keys": ["ENV"],
                        "message": "ENV=production is set.",
                        "remediation": "",
                    }
                ],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="deploy-readiness",
        command=(sys.executable, "scripts/deploy_readiness.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is True
    assert result.artifact_failures is None


def test_release_gate_rejects_deploy_readiness_artifact_without_sources(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "deploy-readiness.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "targets": ["railway"],
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [{"id": "railway_env", "target": "railway", "status": "pass"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="deploy-readiness",
        command=(sys.executable, "scripts/deploy_readiness.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact sources.env_files must be a list: deploy-readiness.json"
    ]


def test_release_gate_rejects_deploy_readiness_artifact_with_inconsistent_summary(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "deploy-readiness.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "targets": ["railway"],
                "summary": {"total": 2, "passed": 2, "failed": 0, "warnings": 0},
                "checks": [
                    {"id": "railway_env", "target": "railway", "status": "pass"},
                    {"id": "railway_queue", "target": "railway", "status": "warn"},
                ],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="deploy-readiness",
        command=(sys.executable, "scripts/deploy_readiness.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact preflight summary does not match checks: deploy-readiness.json"
    ]


def test_release_gate_rejects_deploy_readiness_artifact_with_invalid_check_status(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "deploy-readiness.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "targets": ["railway"],
                "summary": {"total": 1, "passed": 0, "failed": 0, "warnings": 0},
                "checks": [{"id": "railway_env", "target": "railway", "status": "blocked"}],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="deploy-readiness",
        command=(sys.executable, "scripts/deploy_readiness.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact preflight checks must include id and pass/fail/warn status: deploy-readiness.json"
    ]


def test_release_gate_rejects_deploy_readiness_artifact_without_process_env_source(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "deploy-readiness.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "targets": ["railway"],
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [{"id": "railway_env", "target": "railway", "status": "pass"}],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="deploy-readiness",
        command=(sys.executable, "scripts/deploy_readiness.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact sources.include_process_env must be a boolean: deploy-readiness.json"
    ]


def test_release_gate_passes_env_doctor_artifact_with_expected_shape(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "env-doctor.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "profile": "production",
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [
                    {
                        "id": "env",
                        "label": "Environment",
                        "status": "pass",
                        "required": True,
                        "message": "ENV=production is set.",
                        "remediation": "",
                    }
                ],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="env-doctor",
        command=(sys.executable, "scripts/env_doctor.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is True
    assert result.artifact_failures is None


def test_release_gate_rejects_env_doctor_artifact_without_sources(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "env-doctor.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "profile": "production",
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [{"id": "env", "status": "pass"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="env-doctor",
        command=(sys.executable, "scripts/env_doctor.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact sources.env_files must be a list: env-doctor.json"]


def test_release_gate_rejects_env_doctor_artifact_with_inconsistent_summary(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "env-doctor.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "profile": "production",
                "summary": {"total": 2, "passed": 2, "failed": 0, "warnings": 0},
                "checks": [
                    {"id": "env", "status": "pass"},
                    {"id": "database", "status": "fail"},
                ],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="env-doctor",
        command=(sys.executable, "scripts/env_doctor.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact preflight summary does not match checks: env-doctor.json"
    ]


def test_release_gate_rejects_env_doctor_artifact_with_missing_check_id(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "env-doctor.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "profile": "production",
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [{"label": "Environment", "status": "pass"}],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="env-doctor",
        command=(sys.executable, "scripts/env_doctor.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact preflight checks must include id and pass/fail/warn status: env-doctor.json"
    ]


def test_release_gate_rejects_env_doctor_artifact_with_invalid_env_file_source(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "env-doctor.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "profile": "production",
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [{"id": "env", "status": "pass"}],
                "sources": {
                    "env_files": [{"path": ".env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="env-doctor",
        command=(sys.executable, "scripts/env_doctor.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact sources.env_files entries must include non-empty path, resolved_path, and exists: env-doctor.json"
    ]


def test_release_gate_rejects_env_doctor_artifact_with_empty_env_file_source_path(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "env-doctor.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "profile": "production",
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [{"id": "env", "status": "pass"}],
                "sources": {
                    "env_files": [{"path": "", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="env-doctor",
        command=(sys.executable, "scripts/env_doctor.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact sources.env_files entries must include non-empty path, resolved_path, and exists: env-doctor.json"
    ]


def test_release_gate_rejects_env_doctor_artifact_with_missing_env_file_source(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "env-doctor.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "ok": True,
                "profile": "production",
                "summary": {"total": 1, "passed": 1, "failed": 0, "warnings": 0},
                "checks": [{"id": "env", "status": "pass"}],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": False}],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="env-doctor",
        command=(sys.executable, "scripts/env_doctor.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact sources.env_files must exist: env-doctor.json"]


def test_release_gate_passes_product_smoke_artifact_with_expected_shape(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": _valid_launch_handoff(),
                "ready_web3": _valid_ready_web3(),
                "ready_launch_action_coverage": _valid_ready_launch_action_coverage(),
                "launch_env_handoff": _valid_launch_env_handoff(),
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is True
    assert result.artifact_failures is None


def test_release_gate_fails_product_smoke_artifact_without_launch_handoff(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact missing launch_handoff object: evidence.json"]


def test_release_gate_fails_product_smoke_artifact_with_malformed_launch_handoff(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": {
                    "ok": "yes",
                    "release_decision": "maybe",
                    "operator_phase": "operator-review",
                    "readiness_status": "degraded",
                    "summary": {
                        "total": 13,
                        "ready_count": 12,
                        "required_total": 7,
                        "required_ready_count": 7,
                        "blocker_count": 0,
                        "warning_count": 0,
                    },
                    "score": {"overall_percent": 92, "required_percent": 100},
                    "launch_blockers": [],
                    "next_actions": [],
                    "failures": [],
                },
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact launch_handoff.ok must be a boolean: evidence.json",
        "JSON evidence artifact launch_handoff.release_decision is invalid: evidence.json",
    ]


def test_release_gate_fails_product_smoke_artifact_with_malformed_launch_action(
    monkeypatch, tmp_path: Path
) -> None:
    launch_handoff = _valid_launch_handoff()
    launch_handoff["next_actions"] = [
        {
            "id": "web3",
            "required": False,
            "status": "warn",
            "remediation": "Use https://secret-rpc.example and 0x1111111111111111111111111111111111111111.",
            "required_env": ["WEB3_RPC_URL", "https://secret-rpc.example"],
        },
        {"id": "", "required": "no", "status": "pass", "remediation": "", "required_env": []},
    ]
    launch_handoff["summary"]["warning_count"] = 2
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-06-10T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": launch_handoff,
                "ready_web3": _valid_ready_web3(),
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        (
            "JSON evidence artifact launch_handoff.next_actions[0].remediation must not contain raw URLs, "
            "addresses, or secret-shaped values: evidence.json"
        ),
        (
            "JSON evidence artifact launch_handoff.next_actions[0].required_env must not contain raw URLs, "
            "addresses, or secret-shaped values: evidence.json"
        ),
        "JSON evidence artifact launch_handoff.next_actions[1].id must be a non-empty string: evidence.json",
        "JSON evidence artifact launch_handoff.next_actions[1].required must be a boolean: evidence.json",
        "JSON evidence artifact launch_handoff.next_actions[1].status must be fail or warn: evidence.json",
        "JSON evidence artifact launch_handoff.next_actions[1].remediation must be a non-empty string: evidence.json",
    ]


def test_release_gate_fails_product_smoke_artifact_with_malformed_launch_env_handoff(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-07-04T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": _valid_launch_handoff(),
                "launch_env_handoff": {
                    "schema_version": 1,
                    "status": "clear",
                    "secret_policy": "placeholder_only_no_secret_values",
                    "required_action_ids": ["stripe"],
                    "optional_action_ids": [],
                    "required_env": ["STRIPE_SECRET_KEY"],
                    "optional_env": [],
                    "operator_copy_lines": ["STRIPE_SECRET_KEY=sk_live_secret"],
                },
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact launch_env_handoff.status must match env blockers: evidence.json",
        (
            "JSON evidence artifact launch_env_handoff.operator_copy_lines must not contain raw URLs, "
            "addresses, or secret-shaped values: evidence.json"
        ),
        (
            "JSON evidence artifact launch_env_handoff.operator_copy_lines missing placeholder for "
            "STRIPE_SECRET_KEY: evidence.json"
        ),
    ]


def test_release_gate_launch_action_coverage_preserves_order_and_dedupes() -> None:
    action_ids, required_env = release_gate._launch_action_coverage(
        [
            {"id": "web3", "required_env": ["MOCK_MODE", "WEB3_RPC_URL"]},
            {"id": "stripe", "required_env": ["STRIPE_SECRET_KEY", "WEB3_RPC_URL"]},
            {"id": "web3", "required_env": ["MOCK_MODE"]},
            {"id": "", "required_env": [None, ""]},
            "not-an-action",
        ]
    )

    assert action_ids == ["web3", "stripe"]
    assert required_env == ["MOCK_MODE", "WEB3_RPC_URL", "STRIPE_SECRET_KEY"]


def test_release_gate_launch_action_coverage_comparison_reports_drift() -> None:
    comparison = release_gate.launch_action_coverage_comparison(
        {
            "artifact_path": "product.json",
            "evidence_source": "product-smoke-live-api",
            "next_action_count": 2,
            "next_action_ids": ["stripe", "database"],
            "next_action_required_env": ["STRIPE_SECRET_KEY", "DATABASE_URL"],
        },
        {
            "artifact_path": "browser.json",
            "evidence_source": "browser-smoke-dashboard-fixture",
            "next_action_count": 2,
            "next_action_ids": ["stripe", "web3"],
            "next_action_required_env": ["STRIPE_SECRET_KEY", "WEB3_RPC_URL"],
        },
    )

    assert comparison == {
        "status": "drift",
        "action_ids_match": False,
        "required_env_match": False,
        "live_action_ids": ["stripe", "database"],
        "browser_action_ids": ["stripe", "web3"],
        "shared_action_ids": ["stripe"],
        "live_only_action_ids": ["database"],
        "browser_only_action_ids": ["web3"],
        "live_required_env": ["STRIPE_SECRET_KEY", "DATABASE_URL"],
        "browser_required_env": ["STRIPE_SECRET_KEY", "WEB3_RPC_URL"],
        "shared_required_env": ["STRIPE_SECRET_KEY"],
        "live_only_required_env": ["DATABASE_URL"],
        "browser_only_required_env": ["WEB3_RPC_URL"],
        "live_next_action_count": 2,
        "browser_next_action_count": 2,
        "live_artifact_path": "product.json",
        "live_evidence_source": "product-smoke-live-api",
        "browser_artifact_path": "browser.json",
        "browser_evidence_source": "browser-smoke-dashboard-fixture",
    }


def test_release_gate_strict_launch_action_coverage_result_reports_drift() -> None:
    result = release_gate.strict_launch_action_coverage_result(
        {
            "launch_action_coverage_comparison": {
                "status": "drift",
                "live_only_action_ids": ["database"],
                "browser_only_action_ids": ["web3"],
                "live_only_required_env": ["DATABASE_URL"],
                "browser_only_required_env": ["WEB3_RPC_URL"],
            }
        }
    )

    assert result is not None
    assert result.name == "launch-action-coverage"
    assert result.returncode == 1
    assert result.command_argv == ["release_gate", "strict", "launch-action-coverage"]
    assert result.failures == [
        "strict launch action coverage drift: live and browser launch action coverage differ",
        "live-only action ids: database",
        "browser-only action ids: web3",
        "live-only required env: DATABASE_URL",
        "browser-only required env: WEB3_RPC_URL",
    ]
    assert release_gate.result_report(result)["command_argv"] == [
        "release_gate",
        "strict",
        "launch-action-coverage",
    ]


def test_release_gate_strict_launch_action_coverage_result_passes_match() -> None:
    result = release_gate.strict_launch_action_coverage_result(
        {
            "launch_action_coverage_comparison": {
                "status": "match",
                "live_only_action_ids": [],
                "browser_only_action_ids": [],
                "live_only_required_env": [],
                "browser_only_required_env": [],
            }
        }
    )

    assert result is None


def test_release_gate_fails_product_smoke_artifact_with_malformed_ready_web3(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-06-10T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": _valid_launch_handoff(),
                "ready_web3": {
                    "ok": "yes",
                    "status": "unknown",
                    "required": True,
                    "configured": False,
                    "available": True,
                    "details": {
                        "rpc_configured": "yes",
                        "rpc_public_https": True,
                        "contract_count": -1,
                        "contracts": {"DSCI_CONTRACT_ADDRESS": "yes"},
                        "mock_mode_enabled": False,
                        "mock_mode_allowed": False,
                    },
                    "failures": [],
                },
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact ready_web3.ok must be a boolean: evidence.json",
        "JSON evidence artifact ready_web3.status is invalid: evidence.json",
        "JSON evidence artifact ready_web3.details.rpc_configured must be a boolean: evidence.json",
        "JSON evidence artifact ready_web3.details.contract_count must be a non-negative integer: evidence.json",
        "JSON evidence artifact ready_web3.details.contracts must map env keys to booleans: evidence.json",
    ]


def test_release_gate_fails_product_smoke_artifact_with_malformed_ready_launch_coverage(
    monkeypatch, tmp_path: Path
) -> None:
    coverage = _valid_ready_launch_action_coverage()
    coverage["status"] = "match"
    coverage["action_ids_match"] = False
    coverage["ready_only_action_ids"] = ["llm", 123]
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-06-10T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": _valid_launch_handoff(),
                "ready_web3": _valid_ready_web3(),
                "ready_launch_action_coverage": coverage,
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact ready_launch_action_coverage.status must match action/env booleans: evidence.json",
        "JSON evidence artifact ready_launch_action_coverage drift must make product-smoke ok=false: evidence.json",
        "JSON evidence artifact ready_launch_action_coverage.ready_only_action_ids must be a list of strings: evidence.json",
    ]


def test_release_gate_fails_product_smoke_artifact_when_ready_launch_coverage_drifts_but_ok(
    monkeypatch, tmp_path: Path
) -> None:
    coverage = _valid_ready_launch_action_coverage()
    coverage.update(
        {
            "status": "drift",
            "action_ids_match": False,
            "required_env_match": True,
            "ready_action_ids": ["llm"],
            "launch_action_ids": ["stripe"],
            "shared_action_ids": [],
            "ready_only_action_ids": ["llm"],
            "launch_only_action_ids": ["stripe"],
        }
    )
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-06-10T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": _valid_launch_handoff(),
                "ready_web3": _valid_ready_web3(),
                "ready_launch_action_coverage": coverage,
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact ready_launch_action_coverage drift must make product-smoke ok=false: evidence.json",
    ]


def test_release_gate_fails_product_smoke_artifact_without_checks(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 0, "passed": 0, "failed": 0},
                "launch_handoff": _valid_launch_handoff(),
                "failures": [],
                "checks": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact checks must be a non-empty list: evidence.json"]


def test_release_gate_fails_product_smoke_artifact_without_schema_version(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_handoff": {
                    "ok": True,
                    "release_decision": "go-with-watch",
                    "operator_phase": "operator-review",
                    "readiness_status": "degraded",
                    "summary": {
                        "total": 13,
                        "ready_count": 12,
                        "required_total": 7,
                        "required_ready_count": 7,
                        "blocker_count": 0,
                        "warning_count": 1,
                    },
                    "score": {"overall_percent": 92, "required_percent": 100},
                    "launch_blockers": [],
                    "next_actions": [
                        {
                            "id": "database",
                            "required": False,
                            "status": "warn",
                            "remediation": "Review database before launch.",
                            "required_env": ["DATABASE_URL"],
                        }
                    ],
                    "failures": [],
                },
                "ready_web3": _valid_ready_web3(),
                "ready_launch_action_coverage": _valid_ready_launch_action_coverage(),
                "launch_env_handoff": _valid_launch_env_handoff(),
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact schema_version must be 1: evidence.json"]


def test_release_gate_fails_product_smoke_artifact_without_audit_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "not-a-date",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_handoff": _valid_launch_handoff(),
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact generated_at must be an ISO-8601 timestamp: evidence.json",
        "JSON evidence artifact missing api target URL: evidence.json",
        "JSON evidence artifact missing frontend target URL: evidence.json",
    ]


def test_release_gate_fails_browser_smoke_artifact_without_frontend_target(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "failures": [],
                "checks": [{"name": "home", "path": "/", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="browser-smoke",
        command=(sys.executable, "scripts/browser_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact missing frontend target URL: evidence.json"]


def test_release_gate_fails_product_smoke_artifact_without_check_failure_lists(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_handoff": _valid_launch_handoff(),
                "failures": [],
                "checks": [{"name": "api", "ok": True}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact checks must include failures lists: evidence.json"]


def test_release_gate_fails_browser_smoke_artifact_when_a_check_is_not_ok(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "https://app.example.com",
                "playwright_available": True,
                "summary": {"total": 1, "passed": 0, "failed": 1},
                "failures": [],
                "checks": [{"name": "home", "path": "/", "ok": False, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="browser-smoke",
        command=(sys.executable, "scripts/browser_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact checks must all report ok=true: evidence.json",
    ]


def test_release_gate_rejects_malformed_browser_trace_artifacts(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "https://app.example.com",
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "trace_artifacts": [{"check_name": "home"}],
                "failures": [],
                "checks": [{"name": "home", "path": "/", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="browser-smoke",
        command=(sys.executable, "scripts/browser_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact trace_artifacts entries must include non-empty check_name and path: evidence.json",
    ]


def test_release_gate_fails_product_smoke_artifact_when_summary_total_is_inconsistent(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 2, "passed": 1, "failed": 0, "strict_ready": True},
                "launch_handoff": _valid_launch_handoff(),
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact summary does not match checks/failures: evidence.json"
    ]


def test_release_gate_fails_browser_smoke_artifact_when_summary_failed_is_inconsistent(
    monkeypatch, tmp_path: Path
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "https://app.example.com",
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 1},
                "failures": [],
                "checks": [{"name": "home", "path": "/", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="browser-smoke",
        command=(sys.executable, "scripts/browser_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == [
        "JSON evidence artifact summary does not match checks/failures: evidence.json"
    ]


def test_release_gate_accepts_failed_count_as_failed_check_count(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 0, "failed": 1},
                "launch_handoff": _valid_launch_handoff(),
                "failures": ["api: missing header", "api: unexpected service"],
                "checks": [
                    {
                        "name": "api",
                        "ok": False,
                        "failures": ["api: missing header", "api: unexpected service"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.artifact_failures == ["JSON evidence artifact checks must all report ok=true: evidence.json"]


def test_release_gate_fails_successful_step_when_json_artifact_is_invalid(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.returncode == 1
    assert result.artifact_failures
    assert result.artifact_failures[0].startswith("invalid JSON evidence artifact: evidence.json")


def test_release_gate_fails_successful_step_when_json_artifact_reports_not_ok(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text('{"ok": false}', encoding="utf-8")
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.returncode == 1
    assert result.artifact_failures == [
        "JSON evidence artifact must report ok=true: evidence.json",
        "JSON evidence artifact schema_version must be 1: evidence.json",
        "JSON evidence artifact generated_at must be an ISO-8601 timestamp: evidence.json",
        "JSON evidence artifact missing api target URL: evidence.json",
        "JSON evidence artifact missing frontend target URL: evidence.json",
        "JSON evidence artifact missing launch_handoff object: evidence.json",
        "JSON evidence artifact missing summary object: evidence.json",
        "JSON evidence artifact failures must be a list: evidence.json",
        "JSON evidence artifact checks must be a non-empty list: evidence.json",
    ]


def test_release_gate_fails_successful_step_when_json_artifact_omits_ok(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text('{"summary": {"passed": 1}}', encoding="utf-8")
    monkeypatch.setattr(release_gate, "_run_subprocess", lambda step, env: 0)
    step = release_gate.GateStep(
        name="product-smoke",
        command=(sys.executable, "scripts/product_smoke.py", "--json-out", artifact.name),
        cwd=tmp_path,
    )

    result = release_gate.run_step(step, dry_run=False)

    assert result.ok is False
    assert result.returncode == 1
    assert result.artifact_failures == [
        "JSON evidence artifact must report ok=true: evidence.json",
        "JSON evidence artifact schema_version must be 1: evidence.json",
        "JSON evidence artifact generated_at must be an ISO-8601 timestamp: evidence.json",
        "JSON evidence artifact missing api target URL: evidence.json",
        "JSON evidence artifact missing frontend target URL: evidence.json",
        "JSON evidence artifact missing launch_handoff object: evidence.json",
        "JSON evidence artifact summary counts must be integers: evidence.json",
        "JSON evidence artifact failures must be a list: evidence.json",
        "JSON evidence artifact checks must be a non-empty list: evidence.json",
    ]


def test_release_gate_json_report_contains_operator_summary(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate.json"
    results = [
        release_gate.GateResult(
            name="env-doctor",
            command="python scripts/env_doctor.py",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=12.5,
        ),
        release_gate.GateResult(
            name="backend-tests",
            command="python -m pytest tests -q",
            cwd=str(release_gate.BACKEND_DIR),
            returncode=1,
            elapsed_ms=30.0,
        ),
    ]

    release_gate.write_json_report(report_path, results)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["ok"] is False
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["passed"] == 1
    assert payload["summary"]["failed"] == 1
    assert payload["summary"]["failed_step"] == "backend-tests"
    assert payload["duration_ms"] == 42.5


def test_release_gate_json_report_can_reference_release_approval_handoff(tmp_path: Path) -> None:
    handoff = tmp_path / "release-approval-handoff.md"
    handoff.write_text(
        "\n".join(
            [
                "# Release Approval Operator Handoff",
                "",
                "## Decision",
                "",
                "## Unresolved Areas",
                "",
                "## Next Operator Actions",
                "",
                "## Failure Summary",
            ]
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="env-doctor",
        command="python scripts/env_doctor.py",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
    )

    payload = release_gate.json_report_payload([result], release_approval_handoff_path=str(handoff))

    assert payload["release_approval_handoff_summary"] == {
        "path": str(handoff),
        "resolved_path": str(handoff.resolve()),
        "exists": True,
        "title_present": True,
        "required_sections": list(release_gate.RELEASE_APPROVAL_HANDOFF_REQUIRED_SECTIONS),
        "missing_sections": [],
        "line_count": 9,
        "unsafe_marker_count": 0,
        "ready_for_job_summary": True,
    }


def test_release_gate_release_approval_handoff_summary_reports_missing_and_unsafe(tmp_path: Path) -> None:
    missing = release_gate.release_approval_handoff_summary(str(tmp_path / "missing.md"))
    assert missing["exists"] is False
    assert missing["ready_for_job_summary"] is False

    unsafe = tmp_path / "unsafe.md"
    unsafe.write_text(
        "# Release Approval Operator Handoff\n\n"
        "## Decision\n\n"
        "## Unresolved Areas\n\n"
        "## Next Operator Actions\n\n"
        "Use postgres://user:secret@db.example/postgres and https://mcp.notion.com/authorize?x=1\n\n"
        "## Failure Summary\n",
        encoding="utf-8",
    )

    summary = release_gate.release_approval_handoff_summary(str(unsafe))

    assert summary["exists"] is True
    assert summary["missing_sections"] == []
    assert summary["unsafe_marker_count"] == 2
    assert summary["ready_for_job_summary"] is False


def test_release_gate_release_approval_handoff_result_fails_invalid_artifact(tmp_path: Path) -> None:
    missing_result = release_gate.release_approval_handoff_result(str(tmp_path / "missing.md"))

    assert missing_result.name == "release-approval-handoff"
    assert missing_result.returncode == 1
    assert missing_result.failures == [f"release approval handoff artifact does not exist: {tmp_path / 'missing.md'}"]

    unsafe = tmp_path / "unsafe.md"
    unsafe.write_text(
        "# Release Approval Operator Handoff\n\n"
        "## Decision\n\n"
        "## Unresolved Areas\n\n"
        "## Next Operator Actions\n\n"
        "Use postgres://user:secret@db.example/postgres\n\n"
        "## Failure Summary\n",
        encoding="utf-8",
    )

    unsafe_result = release_gate.release_approval_handoff_result(str(unsafe))

    assert unsafe_result.returncode == 1
    assert any("unsafe secret-shaped markers" in failure for failure in unsafe_result.failures or [])
    assert any("not ready for job summary" in failure for failure in unsafe_result.failures or [])


def test_release_gate_cli_fails_when_supplied_handoff_is_invalid(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "release-gate.json"
    missing = tmp_path / "missing.md"
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--dry-run", "--release-approval-handoff", str(missing), "--json-out", str(out)])
    monkeypatch.setattr(release_gate, "build_steps", lambda _args: [])

    assert release_gate.main() == 1

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["summary"]["failed"] == 1
    assert payload["summary"]["failed_step"] == "release-approval-handoff"
    assert payload["release_approval_handoff_summary"]["exists"] is False
    assert payload["results"][0]["name"] == "release-approval-handoff"
    assert payload["results"][0]["failures"] == [f"release approval handoff artifact does not exist: {missing}"]


def test_release_gate_report_schema_documents_parent_contract() -> None:
    schema = release_gate.json_report_schema()

    json.dumps(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["required"] == ["schema_version", "ok", "generated_at", "duration_ms", "summary", "results"]
    assert schema["properties"]["schema_version"] == {"const": 1}
    assert schema["properties"]["summary"]["required"] == [
        "total",
        "passed",
        "failed",
        "skipped",
        "failed_step",
    ]
    browser_trace_schema = schema["properties"]["browser_trace_artifact_summary"]
    browser_screenshot_schema = schema["properties"]["browser_screenshot_artifact_summary"]
    ready_web3_schema = schema["properties"]["ready_web3_summary"]
    ready_launch_schema = schema["properties"]["ready_launch_action_coverage_summary"]
    launch_schema = schema["properties"]["launch_handoff_summary"]
    launch_env_schema = schema["properties"]["launch_env_handoff_summary"]
    browser_launch_schema = schema["properties"]["browser_launch_control_summary"]
    comparison_schema = schema["properties"]["launch_action_coverage_comparison"]
    release_approval_handoff_schema = schema["properties"]["release_approval_handoff_summary"]
    assert release_approval_handoff_schema["required"] == [
        "path",
        "resolved_path",
        "exists",
        "title_present",
        "required_sections",
        "missing_sections",
        "line_count",
        "unsafe_marker_count",
        "ready_for_job_summary",
    ]
    assert launch_schema["properties"]["next_action_ids"] == {"type": "array", "items": {"type": "string"}}
    assert launch_schema["properties"]["next_action_required_env"] == {"type": "array", "items": {"type": "string"}}
    assert launch_env_schema["properties"]["status"] == {"type": "string", "enum": ["blocked", "watch", "clear"]}
    assert launch_env_schema["properties"]["secret_policy"] == {
        "type": "string",
        "enum": ["placeholder_only_no_secret_values"],
    }
    assert launch_env_schema["properties"]["operator_copy_lines"] == {"type": "array", "items": {"type": "string"}}
    assert browser_launch_schema["properties"]["next_action_ids"] == {"type": "array", "items": {"type": "string"}}
    assert browser_launch_schema["properties"]["next_action_required_env"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert browser_launch_schema["properties"]["dashboard_layout"]["properties"]["missingTargets"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert browser_launch_schema["properties"]["dashboard_layout"]["properties"]["hasHorizontalOverflow"] == {
        "type": "boolean",
    }
    assert comparison_schema["properties"]["status"] == {"type": "string", "enum": ["match", "drift"]}
    assert comparison_schema["properties"]["live_only_action_ids"] == {"type": "array", "items": {"type": "string"}}
    assert comparison_schema["properties"]["browser_only_required_env"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert ready_web3_schema["properties"]["status"] == {"type": "string", "enum": ["pass", "warn", "fail"]}
    assert ready_web3_schema["properties"]["details"]["properties"]["contracts"] == {
        "type": "object",
        "additionalProperties": {"type": "boolean"},
    }
    assert ready_launch_schema["properties"]["status"] == {"type": "string", "enum": ["match", "drift"]}
    assert ready_launch_schema["properties"]["action_ids_match"] == {"type": "boolean"}
    assert ready_launch_schema["properties"]["ready_only_action_ids"] == {"type": "array", "items": {"type": "string"}}
    assert ready_launch_schema["properties"]["launch_only_required_env"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert browser_trace_schema["required"] == [
        "artifact_paths",
        "trace_artifact_count",
        "existing_count",
        "missing_count",
        "has_missing_trace_artifacts",
    ]
    assert browser_trace_schema["properties"]["trace_viewer_commands"]["items"]["required"] == ["path", "argv"]
    assert browser_screenshot_schema["required"] == [
        "artifact_paths",
        "screenshot_artifact_count",
        "existing_count",
        "missing_count",
        "has_missing_screenshot_artifacts",
        "valid_png_count",
        "invalid_png_count",
        "has_invalid_screenshot_artifacts",
    ]
    assert browser_screenshot_schema["properties"]["screenshot_artifact_paths"] == {
        "type": "array",
        "items": {"type": "string"},
    }


def test_release_gate_json_report_replaces_existing_report_atomically(tmp_path: Path) -> None:
    report_path = tmp_path / "nested" / "release-gate.json"
    report_path.parent.mkdir()
    report_path.write_text('{"old": true}', encoding="utf-8")
    result = release_gate.GateResult(
        name="env-doctor",
        command="python scripts/env_doctor.py",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["summary"]["passed"] == 1
    assert payload["results"][0]["name"] == "env-doctor"
    assert not (report_path.parent / "release-gate.json.tmp").exists()


def test_release_gate_json_report_exposes_runtime_smoke_artifacts(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    product_artifact = tmp_path / "desci-product-smoke-release-gate.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    product_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_handoff": {
                    "ok": True,
                    "release_decision": "go-with-watch",
                    "operator_phase": "operator-review",
                    "readiness_status": "degraded",
                    "summary": {
                        "total": 13,
                        "ready_count": 12,
                        "required_total": 7,
                        "required_ready_count": 7,
                        "blocker_count": 0,
                        "warning_count": 1,
                    },
                    "score": {"overall_percent": 92, "required_percent": 100},
                    "launch_blockers": [],
                    "next_actions": [
                        {
                            "id": "database",
                            "required": False,
                            "status": "warn",
                            "remediation": "Review database before launch.",
                            "required_env": ["DATABASE_URL"],
                        }
                    ],
                    "failures": [],
                },
                "ready_web3": _valid_ready_web3(),
                "ready_launch_action_coverage": _valid_ready_launch_action_coverage(),
                "launch_env_handoff": _valid_launch_env_handoff(),
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    results = [
        release_gate.GateResult(
            name="product-smoke",
            command=f"python scripts/product_smoke.py --json-out {product_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=12.5,
            artifacts=[str(product_artifact)],
        ),
        release_gate.GateResult(
            name="browser-smoke",
            command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=30.0,
            artifacts=[str(browser_artifact)],
        ),
    ]

    release_gate.write_json_report(report_path, results)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    product_result, browser_result = payload["results"]
    assert payload["schema_version"] == 1
    assert payload["launch_handoff_summary"] == {
        "artifact_path": str(product_artifact),
        "evidence_source": "product-smoke-live-api",
        "ok": True,
        "release_decision": "go-with-watch",
        "operator_phase": "operator-review",
        "readiness_status": "degraded",
        "launch_blocker_count": 0,
        "launch_blockers": [],
        "next_action_count": 1,
        "next_action_ids": ["database"],
        "next_action_required_env": ["DATABASE_URL"],
        "readiness_summary": {
            "total": 13,
            "ready_count": 12,
            "required_total": 7,
            "required_ready_count": 7,
            "blocker_count": 0,
            "warning_count": 1,
        },
        "score": {"overall_percent": 92, "required_percent": 100},
    }
    assert payload["launch_env_handoff_summary"] == {
        "artifact_path": str(product_artifact),
        "evidence_source": "product-smoke-live-api",
        "status": "watch",
        "secret_policy": "placeholder_only_no_secret_values",
        "required_action_ids": [],
        "optional_action_ids": ["database"],
        "required_env": [],
        "optional_env": ["DATABASE_URL"],
        "operator_copy_lines": [
            "# DSCI launch env handoff",
            "# Replace placeholders in the target secret manager or runtime env.",
            "# Optional before public launch hardening",
            "DATABASE_URL=<set-secure-value>",
        ],
        "required_env_count": 0,
        "optional_env_count": 1,
        "operator_copy_line_count": 4,
    }
    assert payload["ready_web3_summary"] == {
        "artifact_path": str(product_artifact),
        "evidence_source": "product-smoke-live-api",
        "ok": True,
        "status": "warn",
        "required": True,
        "configured": False,
        "available": True,
        "details": {
            "rpc_configured": True,
            "rpc_public_https": True,
            "mock_mode_enabled": False,
            "mock_mode_allowed": False,
            "contract_count": 1,
            "contracts": {
                "DSCI_CONTRACT_ADDRESS": True,
                "NFT_CONTRACT_ADDRESS": False,
                "DESCI_DAO_CONTRACT_ADDRESS": False,
            },
        },
        "failure_count": 0,
    }
    assert payload["ready_launch_action_coverage_summary"] == {
        "artifact_path": str(product_artifact),
        "evidence_source": "product-smoke-live-api",
        **_valid_ready_launch_action_coverage(),
    }
    assert payload["artifact_summary"] == {
        "total": 2,
        "existing": 1,
        "missing": 1,
        "validation_passed": 1,
        "validation_failed": 1,
        "json_valid": 1,
        "json_invalid": 0,
        "json_ok": 1,
        "json_not_ok": 0,
        "schema_versioned": 1,
        "schema_unversioned": 0,
        "has_failures": True,
        "validation_failures": [f"missing expected JSON evidence artifact: {browser_artifact}"],
        "validation_failed_artifact_paths": [str(browser_artifact)],
    }
    assert product_result["artifacts"] == [str(product_artifact)]
    assert browser_result["artifacts"] == [str(browser_artifact)]
    assert product_result["artifact_summary"] == {
        "total": 1,
        "existing": 1,
        "missing": 0,
        "validation_passed": 1,
        "validation_failed": 0,
        "json_valid": 1,
        "json_invalid": 0,
        "json_ok": 1,
        "json_not_ok": 0,
        "schema_versioned": 1,
        "schema_unversioned": 0,
        "has_failures": False,
    }
    assert browser_result["artifact_summary"] == {
        "total": 1,
        "existing": 0,
        "missing": 1,
        "validation_passed": 0,
        "validation_failed": 1,
        "json_valid": 0,
        "json_invalid": 0,
        "json_ok": 0,
        "json_not_ok": 0,
        "schema_versioned": 0,
        "schema_unversioned": 0,
        "has_failures": True,
        "validation_failures": [f"missing expected JSON evidence artifact: {browser_artifact}"],
        "validation_failed_artifact_paths": [str(browser_artifact)],
    }
    assert product_result["artifact_reports"] == [
        {
            "path": str(product_artifact),
            "exists": True,
            "size_bytes": product_artifact.stat().st_size,
            "validation_ok": True,
            "validation_failures": [],
            "json_valid": True,
            "json_ok": True,
            "json_schema_version": 1,
            "json_generated_at": "2026-05-27T00:00:00+00:00",
            "json_api": "http://api",
            "json_frontend": "http://frontend",
            "json_launch_ok": True,
            "json_launch_release_decision": "go-with-watch",
            "json_launch_operator_phase": "operator-review",
            "json_launch_readiness_status": "degraded",
            "json_launch_blocker_count": 0,
            "json_launch_blockers": [],
            "json_launch_action_count": 1,
            "json_launch_action_ids": ["database"],
            "json_launch_action_required_env": ["DATABASE_URL"],
            "json_launch_summary_total": 13,
            "json_launch_summary_ready_count": 12,
            "json_launch_summary_required_total": 7,
            "json_launch_summary_required_ready_count": 7,
            "json_launch_summary_blocker_count": 0,
            "json_launch_summary_warning_count": 1,
            "json_launch_score_overall_percent": 92,
            "json_launch_score_required_percent": 100,
            "json_launch_env_status": "watch",
            "json_launch_env_secret_policy": "placeholder_only_no_secret_values",
            "json_launch_env_required_action_ids": [],
            "json_launch_env_optional_action_ids": ["database"],
            "json_launch_env_required_env": [],
            "json_launch_env_optional_env": ["DATABASE_URL"],
            "json_launch_env_operator_copy_lines": [
                "# DSCI launch env handoff",
                "# Replace placeholders in the target secret manager or runtime env.",
                "# Optional before public launch hardening",
                "DATABASE_URL=<set-secure-value>",
            ],
            "json_launch_env_required_env_count": 0,
            "json_launch_env_optional_env_count": 1,
            "json_launch_env_operator_copy_line_count": 4,
            "json_ready_web3_ok": True,
            "json_ready_web3_status": "warn",
            "json_ready_web3_required": True,
            "json_ready_web3_configured": False,
            "json_ready_web3_available": True,
            "json_ready_web3_rpc_configured": True,
            "json_ready_web3_rpc_public_https": True,
            "json_ready_web3_contract_count": 1,
            "json_ready_web3_mock_mode_enabled": False,
            "json_ready_web3_mock_mode_allowed": False,
            "json_ready_web3_contracts": {
                "DSCI_CONTRACT_ADDRESS": True,
                "NFT_CONTRACT_ADDRESS": False,
                "DESCI_DAO_CONTRACT_ADDRESS": False,
            },
            "json_ready_web3_failure_count": 0,
            "json_ready_launch_coverage_status": "match",
            "json_ready_launch_action_ids_match": True,
            "json_ready_launch_required_env_match": True,
            "json_ready_launch_ready_action_ids": ["database"],
            "json_ready_launch_launch_action_ids": ["database"],
            "json_ready_launch_shared_action_ids": ["database"],
            "json_ready_launch_ready_only_action_ids": [],
            "json_ready_launch_launch_only_action_ids": [],
            "json_ready_launch_ready_required_env": ["DATABASE_URL"],
            "json_ready_launch_launch_required_env": ["DATABASE_URL"],
            "json_ready_launch_shared_required_env": ["DATABASE_URL"],
            "json_ready_launch_ready_only_required_env": [],
            "json_ready_launch_launch_only_required_env": [],
            "json_check_total": 1,
            "json_check_passed": 1,
            "json_check_failed": 0,
            "json_failed_checks": [],
        }
    ]
    assert browser_result["artifact_reports"] == [
        {
            "path": str(browser_artifact),
            "exists": False,
            "size_bytes": None,
            "validation_ok": False,
            "validation_failures": [f"missing expected JSON evidence artifact: {browser_artifact}"],
        }
    ]


def test_release_gate_json_report_does_not_promote_invalid_launch_handoff(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    product_artifact = tmp_path / "desci-product-smoke-release-gate.json"
    product_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_handoff": {
                    "ok": True,
                    "release_decision": "go-with-watch",
                    "operator_phase": "operator-review",
                    "readiness_status": "degraded",
                    "summary": {
                        "total": 13,
                        "ready_count": 12,
                        "required_total": 7,
                        "required_ready_count": 7,
                        "blocker_count": 1,
                        "warning_count": 0,
                    },
                    "score": {"overall_percent": 92, "required_percent": 100},
                    "launch_blockers": [],
                    "next_actions": [],
                    "failures": [],
                },
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="product-smoke",
        command=f"python scripts/product_smoke.py --json-out {product_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
        artifacts=[str(product_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifact_report = payload["results"][0]["artifact_reports"][0]
    assert "launch_handoff_summary" not in payload
    assert artifact_report["validation_ok"] is False
    assert artifact_report["validation_failures"] == [
        f"JSON evidence artifact launch_handoff.summary.blocker_count must match launch_blockers length: {product_artifact}",
        f"JSON evidence artifact launch_handoff.next_actions length must match blocker_count plus warning_count: {product_artifact}",
        f"JSON evidence artifact launch_handoff go-with-watch decision cannot include required blockers: {product_artifact}",
    ]


def test_release_gate_json_report_exposes_browser_launch_control_summary(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    mocked_endpoints = ["/ready", "/launch", "/me", "/papers/me", "/health", "/vcs", "/notices"]
    next_action_ids = ["stripe", "stripe_return_url", "auth", "stripe_portal", "web3"]
    next_action_required_env = [
        "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_PRO_MONTHLY",
        "STRIPE_PRICE_PRO_YEARLY",
        "DESCI_FRONTEND_URL",
        "STRIPE_PORTAL_CONFIGURATION_ID",
        "MOCK_MODE",
        "WEB3_RPC_URL",
        "NFT_CONTRACT_ADDRESS",
        "DESCI_DAO_CONTRACT_ADDRESS",
    ]
    dashboard_layout = {
        "viewportWidth": 1280,
        "scrollWidth": 1280,
        "missingTargets": [],
        "zeroSizedTargets": [],
        "horizontallyClippedTargets": [],
    }
    expected_dashboard_layout = {
        **dashboard_layout,
        "hasHorizontalOverflow": False,
        "hasLayoutTargetFailures": False,
    }
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 20.0,
                "skip_protected": False,
                "skip_login_validation": True,
                "expect_dev_auth": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_control": {
                    "check_name": "dashboard-readiness-refresh",
                    "ok": True,
                    "evidence_source": "browser-smoke-dashboard-fixture",
                    "api_mocked": True,
                    "mocked_endpoints": mocked_endpoints,
                    "release_decision": "no-go",
                    "operator_phase": "blocked",
                    "readiness_status": "blocked",
                    "summary": {
                        "ready_count": 2,
                        "total": 7,
                        "required_ready_count": 1,
                        "required_total": 4,
                        "blocker_count": 2,
                        "warning_count": 3,
                    },
                    "score": {"overall_percent": 29, "required_percent": 25},
                    "launch_blockers": ["stripe", "stripe_return_url"],
                    "next_action_count": 5,
                    "next_action_ids": next_action_ids,
                    "next_action_required_env": next_action_required_env,
                    "dashboard_layout": dashboard_layout,
                    "failures": [],
                },
                "failures": [],
                "checks": [
                    {"name": "dashboard-readiness-refresh", "path": "/dashboard", "ok": True, "failures": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
        artifacts=[str(browser_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["browser_launch_control_summary"] == {
        "artifact_path": str(browser_artifact),
        "check_name": "dashboard-readiness-refresh",
        "evidence_source": "browser-smoke-dashboard-fixture",
        "api_mocked": True,
        "mocked_endpoints": mocked_endpoints,
        "ok": True,
        "release_decision": "no-go",
        "operator_phase": "blocked",
        "readiness_status": "blocked",
        "launch_blocker_count": 2,
        "next_action_count": 5,
        "next_action_ids": next_action_ids,
        "next_action_required_env": next_action_required_env,
        "readiness_summary": {
            "total": 7,
            "ready_count": 2,
            "required_total": 4,
            "required_ready_count": 1,
            "blocker_count": 2,
            "warning_count": 3,
        },
        "score": {"overall_percent": 29, "required_percent": 25},
        "dashboard_layout": expected_dashboard_layout,
    }
    artifact_report = payload["results"][0]["artifact_reports"][0]
    assert artifact_report["json_browser_launch_check_name"] == "dashboard-readiness-refresh"
    assert artifact_report["json_browser_launch_evidence_source"] == "browser-smoke-dashboard-fixture"
    assert artifact_report["json_browser_launch_api_mocked"] is True
    assert artifact_report["json_browser_launch_mocked_endpoints"] == mocked_endpoints
    assert artifact_report["json_browser_launch_release_decision"] == "no-go"
    assert artifact_report["json_browser_launch_operator_phase"] == "blocked"
    assert artifact_report["json_browser_launch_readiness_status"] == "blocked"
    assert artifact_report["json_browser_launch_blocker_count"] == 2
    assert artifact_report["json_browser_launch_action_count"] == 5
    assert artifact_report["json_browser_launch_action_ids"] == next_action_ids
    assert artifact_report["json_browser_launch_action_required_env"] == next_action_required_env
    assert artifact_report["json_browser_launch_score_required_percent"] == 25
    assert artifact_report["json_browser_launch_layout_viewport_width"] == 1280
    assert artifact_report["json_browser_launch_layout_scroll_width"] == 1280
    assert artifact_report["json_browser_launch_layout_missing_targets"] == []
    assert artifact_report["json_browser_launch_layout_zero_sized_targets"] == []
    assert artifact_report["json_browser_launch_layout_horizontally_clipped_targets"] == []
    assert artifact_report["json_browser_launch_layout_has_horizontal_overflow"] is False
    assert artifact_report["json_browser_launch_layout_has_target_failures"] is False


def test_release_gate_reports_browser_launch_layout_overflow(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 20.0,
                "skip_protected": False,
                "skip_login_validation": True,
                "expect_dev_auth": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_control": {
                    "check_name": "dashboard-readiness-refresh",
                    "ok": True,
                    "evidence_source": "browser-smoke-dashboard-fixture",
                    "api_mocked": True,
                    "mocked_endpoints": ["/ready", "/launch"],
                    "release_decision": "no-go",
                    "operator_phase": "blocked",
                    "readiness_status": "blocked",
                    "summary": {
                        "ready_count": 2,
                        "total": 7,
                        "required_ready_count": 1,
                        "required_total": 4,
                        "blocker_count": 1,
                        "warning_count": 1,
                    },
                    "score": {"overall_percent": 29, "required_percent": 25},
                    "launch_blockers": ["stripe"],
                    "next_action_count": 2,
                    "next_action_ids": ["stripe", "cors"],
                    "next_action_required_env": ["STRIPE_SECRET_KEY", "ALLOWED_ORIGINS"],
                    "dashboard_layout": {
                        "viewportWidth": 1280,
                        "scrollWidth": 1320,
                        "missingTargets": [],
                        "zeroSizedTargets": [],
                        "horizontallyClippedTargets": [],
                    },
                    "failures": [],
                },
                "failures": [],
                "checks": [
                    {"name": "dashboard-readiness-refresh", "path": "/dashboard", "ok": True, "failures": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
        artifacts=[str(browser_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifact_report = payload["results"][0]["artifact_reports"][0]
    assert (
        f"JSON evidence artifact launch_control.dashboard_layout reports horizontal overflow: {browser_artifact}"
        in artifact_report["validation_failures"]
    )
    assert artifact_report["json_browser_launch_layout_has_horizontal_overflow"] is True
    assert "browser_launch_control_summary" not in payload


def test_release_gate_json_report_compares_live_and_browser_launch_action_coverage(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    product_artifact = tmp_path / "desci-product-smoke-release-gate.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    next_action_ids = ["stripe", "web3"]
    next_action_required_env = ["STRIPE_SECRET_KEY", "WEB3_RPC_URL"]
    product_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_handoff": {
                    "ok": True,
                    "release_decision": "no-go",
                    "operator_phase": "blocked",
                    "readiness_status": "blocked",
                    "summary": {
                        "total": 7,
                        "ready_count": 5,
                        "required_total": 4,
                        "required_ready_count": 3,
                        "blocker_count": 1,
                        "warning_count": 1,
                    },
                    "score": {"overall_percent": 71, "required_percent": 75},
                    "launch_blockers": ["stripe"],
                    "next_actions": [
                        {
                            "id": "stripe",
                            "required": True,
                            "status": "fail",
                            "remediation": "Configure Stripe secret.",
                            "required_env": ["STRIPE_SECRET_KEY"],
                        },
                        {
                            "id": "web3",
                            "required": False,
                            "status": "warn",
                            "remediation": "Set public Web3 RPC.",
                            "required_env": ["WEB3_RPC_URL"],
                        },
                    ],
                    "failures": [],
                },
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 20.0,
                "skip_protected": False,
                "skip_login_validation": True,
                "expect_dev_auth": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "launch_control": {
                    "check_name": "dashboard-readiness-refresh",
                    "ok": True,
                    "evidence_source": "browser-smoke-dashboard-fixture",
                    "api_mocked": True,
                    "mocked_endpoints": ["/ready", "/launch"],
                    "release_decision": "no-go",
                    "operator_phase": "blocked",
                    "readiness_status": "blocked",
                    "summary": {
                        "ready_count": 5,
                        "total": 7,
                        "required_ready_count": 3,
                        "required_total": 4,
                        "blocker_count": 1,
                        "warning_count": 1,
                    },
                    "score": {"overall_percent": 71, "required_percent": 75},
                    "launch_blockers": ["stripe"],
                    "next_action_count": 2,
                    "next_action_ids": next_action_ids,
                    "next_action_required_env": next_action_required_env,
                    "failures": [],
                },
                "failures": [],
                "checks": [
                    {"name": "dashboard-readiness-refresh", "path": "/dashboard", "ok": True, "failures": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    results = [
        release_gate.GateResult(
            name="product-smoke",
            command=f"python scripts/product_smoke.py --json-out {product_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=12.5,
            artifacts=[str(product_artifact)],
        ),
        release_gate.GateResult(
            name="browser-smoke",
            command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=30.0,
            artifacts=[str(browser_artifact)],
        ),
    ]

    release_gate.write_json_report(report_path, results)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["launch_action_coverage_comparison"] == {
        "status": "match",
        "action_ids_match": True,
        "required_env_match": True,
        "live_action_ids": next_action_ids,
        "browser_action_ids": next_action_ids,
        "shared_action_ids": next_action_ids,
        "live_only_action_ids": [],
        "browser_only_action_ids": [],
        "live_required_env": next_action_required_env,
        "browser_required_env": next_action_required_env,
        "shared_required_env": next_action_required_env,
        "live_only_required_env": [],
        "browser_only_required_env": [],
        "live_next_action_count": 2,
        "browser_next_action_count": 2,
        "live_artifact_path": str(product_artifact),
        "live_evidence_source": "product-smoke-live-api",
        "browser_artifact_path": str(browser_artifact),
        "browser_evidence_source": "browser-smoke-dashboard-fixture",
    }


def test_release_gate_json_report_exposes_browser_trace_artifacts(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    trace_path = tmp_path / "browser-traces" / "home.trace.zip"
    trace_path.parent.mkdir()
    trace_path.write_bytes(b"trace")
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": False,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 1.0,
                "skip_protected": True,
                "skip_login_validation": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 0, "failed": 1},
                "trace_artifacts": [{"check_name": "home", "path": str(trace_path)}],
                "failures": ["home: timed out"],
                "checks": [
                    {
                        "name": "home",
                        "path": "/",
                        "ok": False,
                        "failures": ["home: timed out"],
                        "trace_path": str(trace_path),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=1,
        elapsed_ms=12.5,
        artifacts=[str(browser_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifact_report = payload["results"][0]["artifact_reports"][0]
    assert artifact_report["json_trace_artifact_count"] == 1
    assert artifact_report["json_trace_artifact_paths"] == [str(trace_path)]
    assert artifact_report["json_trace_artifact_resolved_paths"] == [str(trace_path.resolve())]
    assert artifact_report["json_trace_artifact_existing_count"] == 1
    assert artifact_report["json_trace_artifact_missing_count"] == 0
    assert artifact_report["json_trace_artifact_missing_paths"] == []
    assert artifact_report["json_trace_artifact_checks"] == ["home"]
    assert payload["artifact_summary"]["json_trace_artifact_count"] == 1
    assert payload["artifact_summary"]["has_trace_artifacts"] is True
    assert payload["artifact_summary"]["json_trace_artifact_paths"] == [str(trace_path)]
    assert payload["artifact_summary"]["json_trace_artifact_resolved_paths"] == [str(trace_path.resolve())]
    assert payload["artifact_summary"]["json_trace_artifact_existing_count"] == 1
    assert payload["artifact_summary"]["json_trace_artifact_missing_count"] == 0
    assert payload["artifact_summary"]["has_missing_trace_artifacts"] is False
    assert payload["browser_trace_artifact_summary"] == {
        "artifact_paths": [str(browser_artifact)],
        "trace_artifact_count": 1,
        "existing_count": 1,
        "missing_count": 0,
        "has_missing_trace_artifacts": False,
        "trace_artifact_paths": [str(trace_path)],
        "resolved_paths": [str(trace_path.resolve())],
        "checks": ["home"],
        "trace_viewer_commands": [
            {
                "path": str(trace_path.resolve()),
                "argv": ["npx", "playwright", "show-trace", str(trace_path.resolve())],
            }
        ],
    }


def test_release_gate_reports_missing_browser_trace_artifact(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    trace_path = tmp_path / "browser-traces" / "missing.trace.zip"
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": False,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 1.0,
                "skip_protected": True,
                "skip_login_validation": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 0, "failed": 1},
                "trace_artifacts": [{"check_name": "home", "path": str(trace_path)}],
                "failures": ["home: timed out"],
                "checks": [
                    {
                        "name": "home",
                        "path": "/",
                        "ok": False,
                        "failures": ["home: timed out"],
                        "trace_path": str(trace_path),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=1,
        elapsed_ms=12.5,
        artifacts=[str(browser_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifact_report = payload["results"][0]["artifact_reports"][0]
    expected_failure = f"JSON evidence artifact trace_artifacts path does not exist: {trace_path} ({browser_artifact})"
    assert expected_failure in artifact_report["validation_failures"]
    assert artifact_report["json_trace_artifact_existing_count"] == 0
    assert artifact_report["json_trace_artifact_missing_count"] == 1
    assert artifact_report["json_trace_artifact_missing_paths"] == [str(trace_path.resolve())]
    assert payload["artifact_summary"]["json_trace_artifact_missing_count"] == 1
    assert payload["artifact_summary"]["has_missing_trace_artifacts"] is True
    assert payload["artifact_summary"]["json_trace_artifact_missing_paths"] == [str(trace_path.resolve())]
    assert payload["browser_trace_artifact_summary"] == {
        "artifact_paths": [str(browser_artifact)],
        "trace_artifact_count": 1,
        "existing_count": 0,
        "missing_count": 1,
        "has_missing_trace_artifacts": True,
        "trace_artifact_paths": [str(trace_path)],
        "resolved_paths": [str(trace_path.resolve())],
        "missing_paths": [str(trace_path.resolve())],
        "checks": ["home"],
    }


def test_release_gate_json_report_exposes_browser_screenshot_artifacts(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    screenshot_path = tmp_path / "browser-screenshots" / "dashboard-readiness-refresh.png"
    screenshot_path.parent.mkdir()
    _write_valid_png(screenshot_path)
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-07-04T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 1.0,
                "skip_protected": True,
                "skip_login_validation": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "screenshot_artifacts": [
                    {"check_name": "dashboard-readiness-refresh", "path": str(screenshot_path)}
                ],
                "failures": [],
                "checks": [
                    {
                        "name": "dashboard-readiness-refresh",
                        "path": "/dashboard",
                        "ok": True,
                        "failures": [],
                        "screenshot_path": str(screenshot_path),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
        artifacts=[str(browser_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifact_report = payload["results"][0]["artifact_reports"][0]
    assert artifact_report["validation_ok"] is True
    assert artifact_report["json_screenshot_artifact_count"] == 1
    assert artifact_report["json_screenshot_artifact_paths"] == [str(screenshot_path)]
    assert artifact_report["json_screenshot_artifact_resolved_paths"] == [str(screenshot_path.resolve())]
    assert artifact_report["json_screenshot_artifact_existing_count"] == 1
    assert artifact_report["json_screenshot_artifact_missing_count"] == 0
    assert artifact_report["json_screenshot_artifact_missing_paths"] == []
    assert artifact_report["json_screenshot_artifact_valid_png_count"] == 1
    assert artifact_report["json_screenshot_artifact_invalid_png_count"] == 0
    assert artifact_report["json_screenshot_artifact_invalid_png_paths"] == []
    assert artifact_report["json_screenshot_artifact_png_dimensions"] == [
        {"path": str(screenshot_path.resolve()), "width": 1, "height": 1}
    ]
    assert artifact_report["json_screenshot_artifact_checks"] == ["dashboard-readiness-refresh"]
    assert payload["artifact_summary"]["json_screenshot_artifact_count"] == 1
    assert payload["artifact_summary"]["has_screenshot_artifacts"] is True
    assert payload["artifact_summary"]["json_screenshot_artifact_paths"] == [str(screenshot_path)]
    assert payload["artifact_summary"]["json_screenshot_artifact_resolved_paths"] == [str(screenshot_path.resolve())]
    assert payload["artifact_summary"]["json_screenshot_artifact_existing_count"] == 1
    assert payload["artifact_summary"]["json_screenshot_artifact_missing_count"] == 0
    assert payload["artifact_summary"]["has_missing_screenshot_artifacts"] is False
    assert payload["artifact_summary"]["json_screenshot_artifact_valid_png_count"] == 1
    assert payload["artifact_summary"]["json_screenshot_artifact_invalid_png_count"] == 0
    assert payload["artifact_summary"]["has_invalid_screenshot_artifacts"] is False
    assert payload["browser_screenshot_artifact_summary"] == {
        "artifact_paths": [str(browser_artifact)],
        "screenshot_artifact_count": 1,
        "existing_count": 1,
        "missing_count": 0,
        "has_missing_screenshot_artifacts": False,
        "valid_png_count": 1,
        "invalid_png_count": 0,
        "has_invalid_screenshot_artifacts": False,
        "screenshot_artifact_paths": [str(screenshot_path)],
        "resolved_paths": [str(screenshot_path.resolve())],
        "checks": ["dashboard-readiness-refresh"],
    }


def test_release_gate_reports_missing_browser_screenshot_artifact(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    screenshot_path = tmp_path / "browser-screenshots" / "missing.png"
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-07-04T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 1.0,
                "skip_protected": True,
                "skip_login_validation": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "screenshot_artifacts": [{"check_name": "home", "path": str(screenshot_path)}],
                "failures": [],
                "checks": [
                    {
                        "name": "home",
                        "path": "/",
                        "ok": True,
                        "failures": [],
                        "screenshot_path": str(screenshot_path),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
        artifacts=[str(browser_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifact_report = payload["results"][0]["artifact_reports"][0]
    expected_failure = (
        f"JSON evidence artifact screenshot_artifacts path does not exist: {screenshot_path} ({browser_artifact})"
    )
    assert expected_failure in artifact_report["validation_failures"]
    assert artifact_report["json_screenshot_artifact_existing_count"] == 0
    assert artifact_report["json_screenshot_artifact_missing_count"] == 1
    assert artifact_report["json_screenshot_artifact_missing_paths"] == [str(screenshot_path.resolve())]
    assert artifact_report["json_screenshot_artifact_valid_png_count"] == 0
    assert artifact_report["json_screenshot_artifact_invalid_png_count"] == 0
    assert artifact_report["json_screenshot_artifact_invalid_png_paths"] == []
    assert payload["artifact_summary"]["json_screenshot_artifact_missing_count"] == 1
    assert payload["artifact_summary"]["has_missing_screenshot_artifacts"] is True
    assert payload["artifact_summary"]["json_screenshot_artifact_missing_paths"] == [str(screenshot_path.resolve())]
    assert payload["artifact_summary"]["json_screenshot_artifact_valid_png_count"] == 0
    assert payload["artifact_summary"]["json_screenshot_artifact_invalid_png_count"] == 0
    assert payload["artifact_summary"]["has_invalid_screenshot_artifacts"] is False
    assert payload["browser_screenshot_artifact_summary"] == {
        "artifact_paths": [str(browser_artifact)],
        "screenshot_artifact_count": 1,
        "existing_count": 0,
        "missing_count": 1,
        "has_missing_screenshot_artifacts": True,
        "valid_png_count": 0,
        "invalid_png_count": 0,
        "has_invalid_screenshot_artifacts": False,
        "screenshot_artifact_paths": [str(screenshot_path)],
        "resolved_paths": [str(screenshot_path.resolve())],
        "missing_paths": [str(screenshot_path.resolve())],
        "checks": ["home"],
    }


def test_release_gate_reports_invalid_browser_screenshot_png(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-runtime.json"
    browser_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    screenshot_path = tmp_path / "browser-screenshots" / "invalid.png"
    screenshot_path.parent.mkdir()
    screenshot_path.write_bytes(b"png")
    browser_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-07-04T00:00:00+00:00",
                "frontend": "http://frontend",
                "timeout_seconds": 1.0,
                "skip_protected": True,
                "skip_login_validation": True,
                "playwright_available": True,
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "screenshot_artifacts": [{"check_name": "home", "path": str(screenshot_path)}],
                "failures": [],
                "checks": [
                    {
                        "name": "home",
                        "path": "/",
                        "ok": True,
                        "failures": [],
                        "screenshot_path": str(screenshot_path),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {browser_artifact}",
        cwd=str(release_gate.PROJECT_ROOT),
        returncode=0,
        elapsed_ms=12.5,
        artifacts=[str(browser_artifact)],
    )

    release_gate.write_json_report(report_path, [result])

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    artifact_report = payload["results"][0]["artifact_reports"][0]
    assert any(
        failure.startswith(
            f"JSON evidence artifact screenshot_artifacts path is not a valid PNG: {screenshot_path} ({browser_artifact})"
        )
        for failure in artifact_report["validation_failures"]
    )
    assert artifact_report["json_screenshot_artifact_existing_count"] == 1
    assert artifact_report["json_screenshot_artifact_valid_png_count"] == 0
    assert artifact_report["json_screenshot_artifact_invalid_png_count"] == 1
    assert artifact_report["json_screenshot_artifact_invalid_png_paths"] == [str(screenshot_path.resolve())]
    assert artifact_report["json_screenshot_artifact_png_dimensions"] == []
    assert payload["artifact_summary"]["json_screenshot_artifact_valid_png_count"] == 0
    assert payload["artifact_summary"]["json_screenshot_artifact_invalid_png_count"] == 1
    assert payload["artifact_summary"]["has_invalid_screenshot_artifacts"] is True
    assert payload["artifact_summary"]["json_screenshot_artifact_invalid_png_paths"] == [str(screenshot_path.resolve())]
    assert payload["browser_screenshot_artifact_summary"] == {
        "artifact_paths": [str(browser_artifact)],
        "screenshot_artifact_count": 1,
        "existing_count": 1,
        "missing_count": 0,
        "has_missing_screenshot_artifacts": False,
        "valid_png_count": 0,
        "invalid_png_count": 1,
        "has_invalid_screenshot_artifacts": True,
        "screenshot_artifact_paths": [str(screenshot_path)],
        "resolved_paths": [str(screenshot_path.resolve())],
        "invalid_png_paths": [str(screenshot_path.resolve())],
        "checks": ["home"],
    }


def test_release_gate_json_report_exposes_preflight_artifact_provenance(tmp_path: Path) -> None:
    report_path = tmp_path / "release-gate-preflight.json"
    env_artifact = tmp_path / "desci-env-doctor-release-gate.json"
    deploy_artifact = tmp_path / "desci-deploy-readiness-release-gate.json"
    env_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "profile": "production",
                "summary": {"total": 2, "passed": 1, "failed": 0, "warnings": 1},
                "checks": [
                    {"id": "env", "label": "Environment", "status": "pass"},
                    {"id": "database", "label": "Database", "status": "warn"},
                ],
                "sources": {
                    "env_files": [
                        {"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True},
                        {"path": "contracts/.env", "resolved_path": "/repo/contracts/.env", "exists": False},
                    ],
                    "include_process_env": False,
                },
            }
        ),
        encoding="utf-8",
    )
    deploy_artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:01+00:00",
                "targets": ["railway", "github"],
                "summary": {"total": 2, "passed": 1, "failed": 1, "warnings": 0},
                "checks": [
                    {"id": "railway_env", "target": "railway", "status": "pass"},
                    {"id": "railway_llm", "target": "railway", "status": "fail"},
                ],
                "sources": {
                    "env_files": [{"path": ".env.production", "resolved_path": "/repo/.env.production", "exists": True}],
                    "include_process_env": True,
                },
            }
        ),
        encoding="utf-8",
    )
    results = [
        release_gate.GateResult(
            name="env-doctor",
            command=f"python scripts/env_doctor.py --json-out {env_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=10.0,
            artifacts=[str(env_artifact)],
        ),
        release_gate.GateResult(
            name="deploy-readiness",
            command=f"python scripts/deploy_readiness.py --json-out {deploy_artifact}",
            cwd=str(release_gate.PROJECT_ROOT),
            returncode=0,
            elapsed_ms=10.0,
            artifacts=[str(deploy_artifact)],
        ),
    ]

    release_gate.write_json_report(report_path, results)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    env_result, deploy_result = payload["results"]
    env_report, deploy_report = [result["artifact_reports"][0] for result in payload["results"]]
    assert payload["artifact_summary"]["json_warning_count"] == 1
    assert payload["artifact_summary"]["has_warnings"] is True
    assert payload["artifact_summary"]["json_failed_checks"] == ["railway_llm"]
    assert payload["artifact_summary"]["json_warning_checks"] == ["database"]
    assert payload["artifact_summary"]["json_missing_env_file_count"] == 1
    assert payload["artifact_summary"]["has_missing_env_files"] is True
    assert payload["artifact_summary"]["json_missing_env_files"] == ["contracts/.env"]
    assert payload["artifact_summary"]["artifact_paths"] == [str(env_artifact), str(deploy_artifact)]
    assert env_result["artifact_summary"]["json_warning_count"] == 1
    assert env_result["artifact_summary"]["has_warnings"] is True
    assert env_result["artifact_summary"]["json_warning_checks"] == ["database"]
    assert env_result["artifact_summary"]["json_missing_env_file_count"] == 1
    assert env_result["artifact_summary"]["has_missing_env_files"] is True
    assert env_result["artifact_summary"]["json_missing_env_files"] == ["contracts/.env"]
    assert env_result["artifact_summary"]["artifact_paths"] == [str(env_artifact)]
    assert deploy_result["artifact_summary"]["json_warning_count"] == 0
    assert deploy_result["artifact_summary"]["has_warnings"] is False
    assert deploy_result["artifact_summary"]["json_missing_env_file_count"] == 0
    assert deploy_result["artifact_summary"]["has_missing_env_files"] is False
    assert deploy_result["artifact_summary"]["json_failed_checks"] == ["railway_llm"]
    assert deploy_result["artifact_summary"]["artifact_paths"] == [str(deploy_artifact)]
    assert env_report["json_profile"] == "production"
    assert env_report["json_env_file_count"] == 2
    assert env_report["json_missing_env_file_count"] == 1
    assert env_report["json_missing_env_files"] == ["contracts/.env"]
    assert env_report["json_include_process_env"] is False
    assert env_report["json_check_warnings"] == 1
    assert env_report["json_warning_checks"] == ["database"]
    assert deploy_report["json_targets"] == ["railway", "github"]
    assert deploy_report["json_env_file_count"] == 1
    assert deploy_report["json_missing_env_file_count"] == 0
    assert deploy_report["json_missing_env_files"] == []
    assert deploy_report["json_include_process_env"] is True
    assert deploy_report["json_check_warnings"] == 0
    assert deploy_report["json_failed_checks"] == ["railway_llm"]


def test_release_gate_detects_json_out_artifacts_for_dry_run_runtime_smoke(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )

    results = [release_gate.run_step(step, dry_run=True) for step in steps]

    assert results[0].artifacts == [str(tmp_path / "desci-product-smoke-release-gate.json")]
    assert results[1].artifacts == [str(tmp_path / "desci-browser-smoke-release-gate.json")]
    assert results[0].command_argv == list(steps[0].command)
    assert results[1].command_argv == list(steps[1].command)


def test_release_gate_dry_run_json_report_marks_artifacts_unchecked(tmp_path: Path) -> None:
    steps = release_gate.build_steps(
        _args(
            runtime_smoke=True,
            runtime_evidence_dir=str(tmp_path),
            skip_env=True,
            skip_compose=True,
            skip_backend=True,
            skip_frontend=True,
            skip_contracts=True,
        )
    )
    results = [release_gate.run_step(step, dry_run=True) for step in steps]

    payload = release_gate.json_report_payload(results)

    assert payload["results"][0]["command_argv"] == list(steps[0].command)
    assert payload["results"][1]["command_argv"] == list(steps[1].command)
    assert payload["artifact_summary"] == {
        "total": 2,
        "existing": 0,
        "missing": 0,
        "validation_passed": 0,
        "validation_failed": 0,
        "validation_skipped": 2,
        "json_valid": 0,
        "json_invalid": 0,
        "json_ok": 0,
        "json_not_ok": 0,
        "schema_versioned": 0,
        "schema_unversioned": 0,
        "has_failures": False,
    }
    assert payload["results"][0]["artifact_reports"] == [
        {
            "path": str(tmp_path / "desci-product-smoke-release-gate.json"),
            "exists": None,
            "size_bytes": None,
            "validation_ok": None,
            "validation_skipped": True,
            "validation_skip_reason": "dry_run",
            "validation_failures": [],
        }
    ]
    assert payload["results"][1]["artifact_reports"] == [
        {
            "path": str(tmp_path / "desci-browser-smoke-release-gate.json"),
            "exists": None,
            "size_bytes": None,
            "validation_ok": None,
            "validation_skipped": True,
            "validation_skip_reason": "dry_run",
            "validation_failures": [],
        }
    ]


def test_release_gate_dry_run_json_report_does_not_parse_stale_artifacts(tmp_path: Path) -> None:
    stale_artifact = tmp_path / "desci-product-smoke-release-gate.json"
    stale_artifact.write_text("{not-json", encoding="utf-8")
    result = release_gate.GateResult(
        name="product-smoke",
        command=f"python scripts/product_smoke.py --json-out {stale_artifact}",
        cwd=str(tmp_path),
        returncode=0,
        elapsed_ms=0.0,
        skipped=True,
        artifacts=[str(stale_artifact)],
    )

    payload = release_gate.json_report_payload([result])

    report = payload["results"][0]["artifact_reports"][0]
    assert report["exists"] is None
    assert report["validation_ok"] is None
    assert report["validation_skipped"] is True
    assert report["validation_failures"] == []
    assert payload["artifact_summary"]["validation_skipped"] == 1
    assert "validation_failures" not in payload["artifact_summary"]


def test_release_gate_dry_run_json_report_ignores_stale_browser_trace_artifacts(tmp_path: Path) -> None:
    stale_artifact = tmp_path / "desci-browser-smoke-release-gate.json"
    missing_trace = tmp_path / "stale-traces" / "home.trace.zip"
    stale_artifact.write_text(
        json.dumps(
            {
                "ok": False,
                "schema_version": 1,
                "generated_at": "2026-06-10T00:00:00+00:00",
                "frontend": "http://127.0.0.1:5173",
                "summary": {"total": 1, "passed": 0, "failed": 1},
                "trace_artifacts": [{"check_name": "home", "path": str(missing_trace)}],
                "failures": ["home: stale failure"],
                "checks": [
                    {
                        "name": "home",
                        "path": "/",
                        "ok": False,
                        "failures": ["home: stale failure"],
                        "trace_path": str(missing_trace),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="browser-smoke",
        command=f"python scripts/browser_smoke.py --json-out {stale_artifact}",
        cwd=str(tmp_path),
        returncode=0,
        elapsed_ms=0.0,
        skipped=True,
        artifacts=[str(stale_artifact)],
    )

    payload = release_gate.json_report_payload([result])

    report = payload["results"][0]["artifact_reports"][0]
    assert report == {
        "path": str(stale_artifact),
        "exists": None,
        "size_bytes": None,
        "validation_ok": None,
        "validation_skipped": True,
        "validation_skip_reason": "dry_run",
        "validation_failures": [],
    }
    assert payload["artifact_summary"]["validation_skipped"] == 1
    assert "json_trace_artifact_count" not in payload["artifact_summary"]
    assert "json_trace_artifact_missing_count" not in payload["artifact_summary"]
    assert "has_missing_trace_artifacts" not in payload["artifact_summary"]
    assert "validation_failures" not in payload["artifact_summary"]


def test_release_gate_json_report_exposes_artifact_failures(tmp_path: Path) -> None:
    result = release_gate.GateResult(
        name="product-smoke",
        command="python scripts/product_smoke.py --json-out missing.json",
        cwd=str(tmp_path),
        returncode=1,
        elapsed_ms=10.0,
        artifacts=["missing.json"],
        artifact_failures=["missing expected JSON evidence artifact: missing.json"],
    )

    payload = release_gate.json_report_payload([result])

    assert payload["ok"] is False
    assert payload["summary"]["failed_step"] == "product-smoke"
    assert payload["artifact_summary"] == {
        "total": 1,
        "existing": 0,
        "missing": 1,
        "validation_passed": 0,
        "validation_failed": 1,
        "json_valid": 0,
        "json_invalid": 0,
        "json_ok": 0,
        "json_not_ok": 0,
        "schema_versioned": 0,
        "schema_unversioned": 0,
        "has_failures": True,
        "validation_failures": ["missing expected JSON evidence artifact: missing.json"],
        "validation_failed_artifact_paths": ["missing.json"],
    }
    assert payload["results"][0]["artifact_reports"] == [
        {
            "path": "missing.json",
            "exists": False,
            "size_bytes": None,
            "validation_ok": False,
            "validation_failures": ["missing expected JSON evidence artifact: missing.json"],
        }
    ]
    assert payload["results"][0]["artifact_failures"] == ["missing expected JSON evidence artifact: missing.json"]


def test_release_gate_json_report_exposes_invalid_artifact_status(tmp_path: Path) -> None:
    artifact = tmp_path / "invalid.json"
    artifact.write_text("{not-json", encoding="utf-8")
    result = release_gate.GateResult(
        name="product-smoke",
        command="python scripts/product_smoke.py --json-out invalid.json",
        cwd=str(tmp_path),
        returncode=1,
        elapsed_ms=10.0,
        artifacts=["invalid.json"],
        artifact_failures=["invalid JSON evidence artifact: invalid.json"],
    )

    payload = release_gate.json_report_payload([result])

    assert payload["results"][0]["artifact_reports"] == [
        {
            "path": "invalid.json",
            "exists": True,
            "size_bytes": artifact.stat().st_size,
            "validation_ok": False,
            "validation_failures": [
                "invalid JSON evidence artifact: invalid.json (Expecting property name enclosed in double quotes: line 1 column 2 (char 1))"
            ],
            "json_valid": False,
            "json_ok": None,
            "json_schema_version": None,
        }
    ]


def test_release_gate_json_report_exposes_artifact_schema_validation_failures(tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 2, "passed": 1, "failed": 0},
                "launch_handoff": _valid_launch_handoff(),
                "failures": [],
                "checks": [{"name": "api", "ok": True, "failures": []}],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="product-smoke",
        command="python scripts/product_smoke.py --json-out evidence.json",
        cwd=str(tmp_path),
        returncode=1,
        elapsed_ms=10.0,
        artifacts=["evidence.json"],
        artifact_failures=["JSON evidence artifact summary does not match checks/failures: evidence.json"],
    )

    payload = release_gate.json_report_payload([result])

    assert payload["results"][0]["artifact_reports"][0]["validation_ok"] is False
    assert payload["results"][0]["artifact_reports"][0]["json_check_total"] == 2
    assert payload["results"][0]["artifact_reports"][0]["json_check_passed"] == 1
    assert payload["results"][0]["artifact_reports"][0]["json_check_failed"] == 0
    assert payload["results"][0]["artifact_reports"][0]["json_failed_checks"] == []
    assert payload["results"][0]["artifact_reports"][0]["validation_failures"] == [
        "JSON evidence artifact summary does not match checks/failures: evidence.json"
    ]


def test_release_gate_json_report_exposes_child_failed_check_names(tmp_path: Path) -> None:
    artifact = tmp_path / "failed-evidence.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "schema_version": 1,
                "generated_at": "2026-05-27T00:00:00+00:00",
                "api": "http://api",
                "frontend": "http://frontend",
                "summary": {"total": 2, "passed": 1, "failed": 1},
                "launch_handoff": _valid_launch_handoff(),
                "failures": ["ready: launch is blocked"],
                "checks": [
                    {"name": "api", "ok": True, "failures": []},
                    {"name": "ready", "ok": False, "failures": ["ready: launch is blocked"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    result = release_gate.GateResult(
        name="product-smoke",
        command="python scripts/product_smoke.py --json-out failed-evidence.json",
        cwd=str(tmp_path),
        returncode=1,
        elapsed_ms=10.0,
        artifacts=["failed-evidence.json"],
        artifact_failures=["JSON evidence artifact checks must all report ok=true: failed-evidence.json"],
    )

    payload = release_gate.json_report_payload([result])

    artifact_report = payload["results"][0]["artifact_reports"][0]
    assert artifact_report["json_check_total"] == 2
    assert artifact_report["json_check_passed"] == 1
    assert artifact_report["json_check_failed"] == 1
    assert artifact_report["json_failed_checks"] == ["ready"]


def test_release_gate_summarizes_browser_smoke_nested_launch_env_handoff(tmp_path: Path) -> None:
    browser_artifact = tmp_path / "browser-smoke.json"
    operator_copy_lines = [
        "# DSCI launch env handoff",
        "# Replace placeholders in the target secret manager or runtime environment.",
        "",
        "# Required before release",
        "STRIPE_SECRET_KEY=<set-secure-value>",
        "ALLOWED_ORIGINS=<set-secure-value>",
        "",
        "# Optional launch hardening",
        "PINATA_JWT=<set-secure-value>",
    ]
    browser_artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-04T00:00:00+00:00",
                "ok": True,
                "frontend": "http://frontend",
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "failures": [],
                "launch_control": {
                    "check_name": "dashboard-readiness-refresh",
                    "ok": True,
                    "evidence_source": "browser-smoke-dashboard-fixture",
                    "api_mocked": True,
                    "mocked_endpoints": ["/ready", "/launch"],
                    "release_decision": "no-go",
                    "operator_phase": "blocked",
                    "readiness_status": "blocked",
                    "summary": {"ready_count": 7, "total": 13, "required_ready_count": 4, "required_total": 7},
                    "score": {"overall_percent": 54, "required_percent": 57},
                    "launch_blockers": ["stripe", "cors"],
                    "next_action_count": 2,
                    "next_action_ids": ["stripe", "cors"],
                    "next_action_required_env": ["STRIPE_SECRET_KEY", "ALLOWED_ORIGINS", "PINATA_JWT"],
                    "launch_env_handoff": {
                        "schema_version": 1,
                        "status": "blocked",
                        "secret_policy": "placeholder_only_no_secret_values",
                        "source": "dashboard-readiness-refresh-browser-click",
                        "required_action_ids": ["stripe", "cors"],
                        "optional_action_ids": ["ipfs"],
                        "required_env": ["STRIPE_SECRET_KEY", "ALLOWED_ORIGINS"],
                        "optional_env": ["PINATA_JWT"],
                        "operator_copy_lines": operator_copy_lines,
                    },
                    "failures": [],
                },
                "checks": [
                    {"name": "dashboard-readiness-refresh", "path": "/dashboard", "ok": True, "failures": []}
                ],
            }
        ),
        encoding="utf-8",
    )

    validation_failures = release_gate.artifact_validation_failures(
        [str(browser_artifact)],
        tmp_path,
        step_name="browser-smoke",
    )
    report = {
        "path": str(browser_artifact),
        "validation_ok": validation_failures is None,
        **release_gate._artifact_json_report(browser_artifact, tmp_path),  # pylint: disable=protected-access
    }

    assert validation_failures is None
    assert report["json_launch_env_source"] == "dashboard-readiness-refresh-browser-click"
    assert report["json_launch_env_status"] == "blocked"
    assert report["json_launch_env_required_action_ids"] == ["stripe", "cors"]
    assert report["json_launch_env_optional_action_ids"] == ["ipfs"]
    assert report["json_launch_env_required_env"] == ["STRIPE_SECRET_KEY", "ALLOWED_ORIGINS"]
    assert report["json_launch_env_optional_env"] == ["PINATA_JWT"]
    assert report["json_launch_env_operator_copy_line_count"] == len(operator_copy_lines)
    assert release_gate.launch_env_handoff_summary([report]) == {
        "artifact_path": str(browser_artifact),
        "evidence_source": "dashboard-readiness-refresh-browser-click",
        "status": "blocked",
        "secret_policy": "placeholder_only_no_secret_values",
        "required_action_ids": ["stripe", "cors"],
        "optional_action_ids": ["ipfs"],
        "required_env": ["STRIPE_SECRET_KEY", "ALLOWED_ORIGINS"],
        "optional_env": ["PINATA_JWT"],
        "operator_copy_lines": operator_copy_lines,
        "required_env_count": 2,
        "optional_env_count": 1,
        "operator_copy_line_count": len(operator_copy_lines),
    }
