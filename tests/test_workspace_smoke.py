from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "run_workspace_smoke.py"
QUALITY_GATE_PATH = PROJECT_ROOT / "docs" / "QUALITY_GATE.md"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("workspace_smoke", SMOKE_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quality_gate_documents_all_supported_scopes() -> None:
    quality_gate = QUALITY_GATE_PATH.read_text(encoding="utf-8")

    for scope in ("all", "workspace", "desci", "agriguard", "mcp"):
        assert f"--scope {scope}" in quality_gate
    assert "--check-timeout" in quality_gate


def test_default_checks_cover_expected_scopes_and_existing_paths() -> None:
    smoke = load_smoke_module()
    checks = smoke.default_checks("python")

    assert {check.scope for check in checks} == {"workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie"}
    assert any(check.name == "workspace regression tests" for check in checks)
    assert any(check.name == "dashboard frontend lint" for check in checks)
    assert any(check.name == "dashboard frontend tests" for check in checks)
    assert any(check.name == "dashboard frontend build" for check in checks)
    assert any(check.name == "dashboard bundle budget" for check in checks)
    assert any(check.name == "desci frontend unit tests" for check in checks)
    assert any(check.name == "desci bundle budget" for check in checks)
    assert any(check.name == "desci contracts compile" for check in checks)
    assert any(check.name == "desci contracts tests" for check in checks)
    assert any(check.name == "agriguard contracts compile" for check in checks)
    assert any(check.name == "agriguard contracts tests" for check in checks)
    assert any(check.name == "agriguard backend tests" for check in checks)
    assert any(check.name == "notebooklm compile" for check in checks)
    assert any(check.name == "DailyNews unit tests" for check in checks)
    assert any(check.name == "getdaytrends tests" for check in checks)
    assert any(check.name == "cie compile" for check in checks)
    assert any(check.name == "cie tests" for check in checks)

    for check in checks:
        assert (PROJECT_ROOT / check.cwd).exists()
        if check.command[1:3] == ["-m", "compileall"]:
            assert smoke.EXCLUDE_REGEX in check.command


def test_uv_dependency_contract_covers_isolated_test_imports() -> None:
    smoke = load_smoke_module()

    shared_deps = smoke.UV_EXTRA_DEPENDENCIES["shared package tests"]
    cie_deps = smoke.UV_EXTRA_DEPENDENCIES["cie tests"]

    assert "google-genai>=1.0.0,<2.0" in shared_deps
    assert "google.genai" in smoke.WORKSPACE_SYNC_SENTINELS["shared package tests"]

    for dependency in (
        "loguru>=0.7.0,<1.0",
        "sqlalchemy>=2.0.0,<3.0",
        "pydantic>=2.0.0,<3.0",
        "httpx>=0.27.0",
    ):
        assert dependency in cie_deps

    assert smoke.WORKSPACE_SYNC_SENTINELS["cie tests"] == ("loguru", "sqlalchemy", "pydantic", "httpx")


def test_build_pythonpath_includes_canonical_workspace_entries() -> None:
    smoke = load_smoke_module()
    pythonpath = smoke.build_pythonpath(PROJECT_ROOT, {"PYTHONPATH": "custom-entry"})
    entries = pythonpath.split(smoke.os.pathsep)

    assert str(PROJECT_ROOT) in entries
    assert str(PROJECT_ROOT / "packages") in entries
    assert str(PROJECT_ROOT / "automation") in entries
    assert str(PROJECT_ROOT / "apps" / "desci-platform") in entries
    assert entries[-1] == "custom-entry"


def test_runtime_temp_dir_stays_under_workspace_var_tmp() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "workspace regression tests", ".", ["python", "-m", "pytest", "-q"])
    temp_dir = smoke.runtime_temp_dir(PROJECT_ROOT, check)

    assert temp_dir.is_relative_to(PROJECT_ROOT / "var" / "tmp" / "workspace-smoke")
    assert temp_dir.parts[-2] == "workspace"


def test_command_for_check_appends_workspace_local_basetemp() -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "workspace",
        "workspace regression tests",
        ".",
        ["python", "-m", "pytest", "tests/test_workspace_smoke.py", "-q"],
    )
    temp_dir = smoke.runtime_temp_dir(PROJECT_ROOT, check)

    command = smoke.command_for_check(check, temp_dir)

    assert command[-2:] == ["--basetemp", str(smoke.pytest_temp_dir(temp_dir))]


def test_build_json_report_adds_scope_summary_and_mcp_trace() -> None:
    smoke = load_smoke_module()
    results = [
        smoke.Result("workspace", "workspace regression tests", ".", "python -m pytest tests", 0, True, "ok", ""),
        smoke.Result(
            "mcp",
            "notebooklm compile",
            ".",
            "python -m compileall mcp/notebooklm-mcp",
            0,
            True,
            "ok",
            "",
            elapsed_seconds=1.25,
        ),
        smoke.Result(
            "mcp",
            "DailyNews unit tests",
            "automation/DailyNews",
            "python -m pytest tests/unit",
            1,
            False,
            "",
            "failed",
            elapsed_seconds=2.5,
        ),
    ]

    report = smoke.build_json_report(results, total_checks=3, complete=True, duration_seconds=4.0)

    assert report["scope_summary"]["workspace"] == {
        "completed": 1,
        "passed": 1,
        "failed": 0,
        "elapsed_seconds": 0.0,
    }
    assert report["scope_summary"]["mcp"] == {
        "completed": 2,
        "passed": 1,
        "failed": 1,
        "elapsed_seconds": 3.75,
    }
    assert report["mcp_trace"]["enabled"] is True
    assert report["mcp_trace"]["completed"] == 2
    assert report["mcp_trace"]["passed"] == 1
    assert report["mcp_trace"]["failed"] == 1
    assert report["mcp_trace"]["elapsed_seconds"] == 3.75
    assert report["mcp_trace"]["checked_units"] == [".", "automation/DailyNews"]
    assert report["mcp_trace"]["command_kinds"] == {"compileall": 1, "pytest": 1}
    assert report["mcp_trace"]["checks"][0]["command_kind"] == "compileall"
    assert report["mcp_trace"]["checks"][1]["command_kind"] == "pytest"


def test_build_mcp_trace_events_exports_jsonl_ready_rows() -> None:
    smoke = load_smoke_module()
    results = [
        smoke.Result("workspace", "workspace regression tests", ".", "python -m pytest tests", 0, True, "ok", ""),
        smoke.Result(
            "mcp",
            "DailyNews unit tests",
            "automation/DailyNews",
            "python -m pytest tests/unit",
            1,
            False,
            "",
            "failed",
            elapsed_seconds=2.5,
        ),
    ]

    events = smoke.build_mcp_trace_events(results)

    assert len(events) == 1
    assert events[0]["schema_version"] == 1
    assert events[0]["event_type"] == "workspace_smoke.mcp_check"
    assert events[0]["scope"] == "mcp"
    assert events[0]["name"] == "DailyNews unit tests"
    assert events[0]["command_kind"] == "pytest"
    assert events[0]["returncode"] == 1
    assert events[0]["ok"] is False
    assert events[0]["stderr_tail"] == "failed"


def test_build_mcp_otel_export_uses_file_exporter_shape() -> None:
    smoke = load_smoke_module()
    results = [
        smoke.Result("workspace", "workspace regression tests", ".", "python -m pytest tests", 0, True, "ok", ""),
        smoke.Result(
            "mcp",
            "DailyNews unit tests",
            "automation/DailyNews",
            "python -m pytest tests/unit",
            1,
            False,
            "",
            "failed",
            elapsed_seconds=2.5,
            started_at_unix_nano=1000,
            ended_at_unix_nano=3000,
        ),
    ]

    export = smoke.build_mcp_otel_export(results, trace_id="1" * 32)

    assert export is not None
    resource_span = export["resourceSpans"][0]
    resource_attrs = {item["key"]: next(iter(item["value"].values())) for item in resource_span["resource"]["attributes"]}
    assert resource_attrs["service.name"] == "workspace-smoke"
    assert resource_attrs["workspace_smoke.signal"] == "mcp"
    scope_span = resource_span["scopeSpans"][0]
    assert scope_span["scope"] == {"name": "workspace_smoke.mcp", "version": "1"}
    span = scope_span["spans"][0]
    attrs = {item["key"]: next(iter(item["value"].values())) for item in span["attributes"]}
    assert span["traceId"] == "1" * 32
    assert len(span["spanId"]) == 16
    assert span["name"] == "workspace_smoke.mcp_check DailyNews unit tests"
    assert span["kind"] == 1
    assert span["startTimeUnixNano"] == "1000"
    assert span["endTimeUnixNano"] == "3000"
    assert span["status"] == {"code": 2, "message": "failed"}
    assert attrs["workspace_smoke.command.kind"] == "pytest"
    assert attrs["workspace_smoke.ok"] is False
    assert attrs["workspace_smoke.returncode"] == "1"


def test_resolve_python_executable_prefers_workspace_venv_over_current_interpreter(tmp_path: Path, monkeypatch) -> None:
    smoke = load_smoke_module()
    venv_python_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    venv_python = tmp_path / ".venv" / venv_python_rel
    current_python = tmp_path / "current-python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    current_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(smoke.sys, "executable", str(current_python))
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)

    assert smoke.resolve_python_executable(tmp_path) == str(venv_python)


def test_ensure_workspace_environment_falls_back_to_uv_runner_when_local_venv_is_incomplete(
    tmp_path: Path, monkeypatch
) -> None:
    smoke = load_smoke_module()
    venv_rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    local_python = tmp_path / ".venv" / venv_rel
    local_python.parent.mkdir(parents=True)
    local_python.write_text("", encoding="utf-8")
    global_python = tmp_path / "global-python.exe"
    global_python.write_text("", encoding="utf-8")
    check = smoke.Check("workspace", "workspace regression tests", ".", ["python", "-m", "pytest", "-q"])

    def fake_has_module(python_exe: str, module_name: str) -> bool:
        return False

    monkeypatch.setattr(smoke, "has_module", fake_has_module)
    monkeypatch.setattr(smoke.shutil, "which", lambda name: "uv" if name == "uv" else None)
    monkeypatch.setattr(smoke, "USE_UV_ISOLATED_RUNNER", False)

    result = smoke.ensure_workspace_environment(tmp_path, str(global_python), [check])

    assert result == str(global_python)
    assert smoke.USE_UV_ISOLATED_RUNNER is True


def test_run_one_uses_uv_isolated_runner_for_python_checks_when_bootstrap_fallback_is_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "workspace regression tests", ".", ["python", "-m", "pytest", "-q"])
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return smoke.subprocess.CompletedProcess(command, 0, b"ok", b"")

    monkeypatch.setattr(smoke, "USE_UV_ISOLATED_RUNNER", True)
    monkeypatch.setattr(smoke, "run_command_with_timeout", fake_run)

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is True
    assert result.elapsed_seconds >= 0
    assert commands[0][:4] == ["uv", "run", "--isolated", "--no-project"]
    assert "--with" in commands[0]
    assert "--with-editable" in commands[0]
    assert commands[0][-6:] == [
        "python",
        "-m",
        "pytest",
        "-q",
        "--basetemp",
        str(smoke.pytest_temp_dir(smoke.runtime_temp_dir(PROJECT_ROOT, check))),
    ]


def test_run_command_with_timeout_terminates_process_tree(monkeypatch) -> None:
    smoke = load_smoke_module()
    killed: list[int] = []

    class FakeProcess:
        pid = 12345
        returncode = 124
        calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if timeout is not None:
                raise smoke.subprocess.TimeoutExpired(["slow"], timeout, output=b"partial", stderr=b"err")
            return b"after kill", b"after kill err"

    monkeypatch.setattr(smoke.subprocess, "Popen", lambda command, **kwargs: FakeProcess())
    monkeypatch.setattr(smoke, "terminate_process_tree", lambda pid: killed.append(pid))

    with pytest.raises(smoke.subprocess.TimeoutExpired) as exc_info:
        smoke.run_command_with_timeout(["slow"], cwd=str(PROJECT_ROOT), env={}, timeout_seconds=0.01)

    assert killed == [12345]
    assert exc_info.value.output == b"after kill"
    assert exc_info.value.stderr == b"after kill err"


def test_node_dependency_workspaces_dedupes_npm_check_dirs(tmp_path: Path) -> None:
    smoke = load_smoke_module()
    app_dir = tmp_path / "apps" / "dashboard"
    app_dir.mkdir(parents=True)
    (app_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    checks = [
        smoke.Check("workspace", "lint", "apps/dashboard", ["npm.cmd", "run", "lint"]),
        smoke.Check("workspace", "test", "apps/dashboard", ["npm.cmd", "run", "test"]),
        smoke.Check("workspace", "python", ".", [sys.executable, "-V"]),
    ]

    assert smoke.node_dependency_workspaces(tmp_path, checks) == [app_dir.resolve()]


def test_ensure_node_environments_runs_npm_ci_for_missing_node_modules(tmp_path: Path, monkeypatch) -> None:
    smoke = load_smoke_module()
    app_dir = tmp_path / "apps" / "dashboard"
    app_dir.mkdir(parents=True)
    (app_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    check = smoke.Check("workspace", "lint", "apps/dashboard", ["npm.cmd", "run", "lint"])
    calls: list[tuple[list[str], str]] = []

    def fake_run(command, *, cwd, env, timeout_seconds):
        calls.append((command, cwd))
        return smoke.subprocess.CompletedProcess(command, 0, b"installed", b"")

    monkeypatch.setattr(smoke, "run_command_with_timeout", fake_run)

    smoke.ensure_node_environments(tmp_path, [check])

    assert calls == [(["npm.cmd" if smoke.os.name == "nt" else "npm", "ci", "--no-audit"], str(app_dir.resolve()))]


def test_ensure_node_environments_skips_existing_node_modules(tmp_path: Path, monkeypatch) -> None:
    smoke = load_smoke_module()
    app_dir = tmp_path / "apps" / "dashboard"
    (app_dir / "node_modules").mkdir(parents=True)
    (app_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    check = smoke.Check("workspace", "lint", "apps/dashboard", ["npm.cmd", "run", "lint"])

    monkeypatch.setattr(
        smoke,
        "run_command_with_timeout",
        lambda *args, **kwargs: pytest.fail("npm ci should not run when node_modules exists"),
    )

    smoke.ensure_node_environments(tmp_path, [check])


def test_run_one_cleans_stale_temp_dir(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    temp_dir = tmp_path / "workspace-smoke-temp"
    stale_file = temp_dir / "stale.txt"
    temp_dir.mkdir(parents=True)
    stale_file.write_text("stale", encoding="utf-8")

    monkeypatch.setattr(smoke, "runtime_temp_dir", lambda root, item: temp_dir)
    check = smoke.Check("workspace", "temp cleanup", ".", [sys.executable, "-c", "print('ok')"])

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is True
    assert temp_dir.exists()
    assert stale_file.exists() is False


def test_run_one_reports_missing_working_directory() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "missing", "does-not-exist", ["python", "-V"])

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is False
    assert result.returncode == 2
    assert result.stderr_tail == "working directory missing"
    assert result.elapsed_seconds >= 0


def test_run_check_retries_transient_desci_vitest_worker_failure(monkeypatch) -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "desci", "desci frontend unit tests", "apps/desci-platform/frontend", ["npm.cmd", "run", "test:lts"]
    )
    attempts = iter(
        [
            smoke.Result(
                "desci",
                "desci frontend unit tests",
                "apps/desci-platform/frontend",
                "npm.cmd run test:lts",
                1,
                False,
                "",
                "Error: [vitest-pool]: Failed to start threads worker\nCaused by: Error: [vitest-pool-runner]: Timeout waiting for worker to respond",
            ),
            smoke.Result(
                "desci",
                "desci frontend unit tests",
                "apps/desci-platform/frontend",
                "npm.cmd run test:lts",
                0,
                True,
                "31 passed",
                "",
            ),
        ]
    )

    monkeypatch.setattr(smoke, "run_one", lambda root, item, *, timeout_seconds=600.0: next(attempts))

    result = smoke.run_check(PROJECT_ROOT, check)

    assert result.ok is True
    assert result.stdout_tail == "31 passed"


def test_run_one_uses_configurable_check_timeout(monkeypatch) -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "timeout check", ".", [sys.executable, "-V"])
    seen_timeouts: list[float] = []

    def fake_run(command, *, cwd, env, timeout_seconds):
        seen_timeouts.append(timeout_seconds)
        raise smoke.subprocess.TimeoutExpired(command, timeout_seconds, output=b"partial", stderr=b"slow")

    monkeypatch.setattr(smoke, "run_command_with_timeout", fake_run)

    result = smoke.run_one(PROJECT_ROOT, check, timeout_seconds=1.5)

    assert seen_timeouts == [1.5]
    assert result.returncode == 124
    assert result.stdout_tail == "partial"
    assert "Command timed out after 1.5s" in result.stderr_tail


def test_should_retry_ignores_non_transient_failures() -> None:
    smoke = load_smoke_module()
    check = smoke.Check(
        "desci", "desci frontend unit tests", "apps/desci-platform/frontend", ["npm.cmd", "run", "test:lts"]
    )
    result = smoke.Result(
        "desci",
        "desci frontend unit tests",
        "apps/desci-platform/frontend",
        "npm.cmd run test:lts",
        1,
        False,
        "",
        "AssertionError: expected false to be true",
    )

    assert smoke.should_retry(check, result) is False


def test_should_retry_uv_access_denied_install_failure() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("mcp", "DailyNews unit tests", "automation/DailyNews", ["python", "-m", "pytest", "tests/unit"])
    result = smoke.Result(
        "mcp",
        "DailyNews unit tests",
        "automation/DailyNews",
        "uv run --isolated --no-project python -m pytest tests/unit",
        2,
        False,
        "",
        "error: 액세스가 거부되었습니다. (os error -2147024891)",
    )

    assert smoke.should_retry(check, result) is True


def test_main_writes_json_report_for_selected_scope(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    fake_check = smoke.Check("workspace", "fake check", ".", ["python", "-V"])
    fake_result = smoke.Result("workspace", "fake check", ".", "python -V", 0, True, "ok", "")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: [fake_check])
    monkeypatch.setattr(smoke, "run_one", lambda root, item, *, timeout_seconds=600.0: fake_result)
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        ["run_workspace_smoke.py", "--scope", "workspace", "--json-out", "smoke.json"],
    )

    exit_code = smoke.main()

    report = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report["schema_version"] == 1
    assert report["status"] == "complete"
    assert report["duration_seconds"] >= 0
    assert report["summary"] == {
        "total": 1,
        "completed": 1,
        "passed": 1,
        "failed": 0,
        "remaining": 0,
    }
    assert report["scope_summary"] == {
        "workspace": {
            "completed": 1,
            "passed": 1,
            "failed": 0,
            "elapsed_seconds": 0.0,
        }
    }
    assert report["mcp_trace"] == {
        "enabled": False,
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "elapsed_seconds": 0,
        "checked_units": [],
        "command_kinds": {},
        "checks": [],
    }
    assert report["results"] == [
        {
            "scope": "workspace",
            "name": "fake check",
            "cwd": ".",
            "command": "python -V",
            "returncode": 0,
            "ok": True,
            "stdout_tail": "ok",
            "stderr_tail": "",
            "elapsed_seconds": 0.0,
            "started_at_unix_nano": 0,
            "ended_at_unix_nano": 0,
        }
    ]


def test_main_keeps_partial_json_report_when_later_check_crashes(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    first_check = smoke.Check("workspace", "first check", ".", ["python", "-V"])
    second_check = smoke.Check("workspace", "second check", ".", ["python", "-V"])
    first_result = smoke.Result(
        "workspace",
        "first check",
        ".",
        "python -V",
        0,
        True,
        "ok",
        "",
        elapsed_seconds=1.25,
    )

    def fake_run_one(root, item, *, timeout_seconds=600.0):
        if item.name == "first check":
            return first_result
        raise RuntimeError("boom")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "ensure_workspace_environment", lambda root, python_exe, checks: python_exe)
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: [first_check, second_check])
    monkeypatch.setattr(smoke, "run_one", fake_run_one)
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        ["run_workspace_smoke.py", "--scope", "workspace", "--json-out", "smoke.json"],
    )

    with pytest.raises(RuntimeError, match="boom"):
        smoke.main()

    report = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["status"] == "partial"
    assert report["summary"] == {
        "total": 2,
        "completed": 1,
        "passed": 1,
        "failed": 0,
        "remaining": 1,
    }
    assert report["scope_summary"]["workspace"]["completed"] == 1
    assert report["mcp_trace"]["enabled"] is False
    assert report["results"][0]["elapsed_seconds"] == 1.25


def test_write_json_report_replaces_existing_report(tmp_path) -> None:
    smoke = load_smoke_module()
    report_path = tmp_path / "smoke.json"
    report_path.write_text("stale", encoding="utf-8")
    result = smoke.Result("workspace", "fake check", ".", "python -V", 0, True, "ok", "", elapsed_seconds=0.5)

    smoke.write_json_report(
        report_path,
        [result],
        total_checks=2,
        complete=False,
        duration_seconds=3.4567,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "partial"
    assert report["duration_seconds"] == 3.457
    assert report["scope_summary"]["workspace"]["elapsed_seconds"] == 0.5
    assert report["mcp_trace"]["enabled"] is False
    assert report["results"][0]["elapsed_seconds"] == 0.5
    assert (tmp_path / ".smoke.json.tmp").exists() is False


def test_write_mcp_trace_export_replaces_existing_jsonl(tmp_path) -> None:
    smoke = load_smoke_module()
    trace_path = tmp_path / "mcp-trace.jsonl"
    trace_path.write_text("stale\n", encoding="utf-8")
    results = [
        smoke.Result("workspace", "fake check", ".", "python -V", 0, True, "ok", ""),
        smoke.Result("mcp", "DailyNews unit tests", "automation/DailyNews", "python -m pytest tests/unit", 0, True, "ok", ""),
    ]

    smoke.write_mcp_trace_export(trace_path, results)

    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event_type"] == "workspace_smoke.mcp_check"
    assert event["name"] == "DailyNews unit tests"
    assert event["command_kind"] == "pytest"
    assert (tmp_path / ".mcp-trace.jsonl.tmp").exists() is False


def test_write_mcp_otel_export_replaces_existing_jsonl(tmp_path) -> None:
    smoke = load_smoke_module()
    otel_path = tmp_path / "mcp-otel.jsonl"
    otel_path.write_text("stale\n", encoding="utf-8")
    results = [
        smoke.Result("workspace", "fake check", ".", "python -V", 0, True, "ok", ""),
        smoke.Result("mcp", "DailyNews unit tests", "automation/DailyNews", "python -m pytest tests/unit", 0, True, "ok", ""),
    ]

    smoke.write_mcp_otel_export(otel_path, results, trace_id="2" * 32)

    lines = otel_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["traceId"] == "2" * 32
    assert span["status"] == {"code": 1}
    assert (tmp_path / ".mcp-otel.jsonl.tmp").exists() is False

    smoke.write_mcp_otel_export(otel_path, [results[0]], trace_id="2" * 32)
    assert otel_path.read_text(encoding="utf-8") == ""


def test_main_writes_mcp_trace_export_for_selected_scope(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    fake_check = smoke.Check("mcp", "fake mcp check", ".", ["python", "-V"])
    fake_result = smoke.Result(
        "mcp",
        "fake mcp check",
        ".",
        "python -V",
        0,
        True,
        "ok",
        "",
        elapsed_seconds=0.25,
        started_at_unix_nano=1000,
        ended_at_unix_nano=2000,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "ensure_workspace_environment", lambda root, python_exe, checks: python_exe)
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: [fake_check])
    monkeypatch.setattr(smoke, "ensure_node_environments", lambda root, checks: None)
    monkeypatch.setattr(smoke, "run_one", lambda root, item, *, timeout_seconds=600.0: fake_result)
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        [
            "run_workspace_smoke.py",
            "--scope",
            "mcp",
            "--json-out",
            "smoke.json",
            "--mcp-trace-out",
            "mcp-trace.jsonl",
            "--mcp-otel-out",
            "mcp-otel.jsonl",
        ],
    )

    exit_code = smoke.main()

    assert exit_code == 0
    report = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    events = (tmp_path / "mcp-trace.jsonl").read_text(encoding="utf-8").splitlines()
    otel_lines = (tmp_path / "mcp-otel.jsonl").read_text(encoding="utf-8").splitlines()
    assert report["mcp_trace"]["enabled"] is True
    assert len(events) == 1
    assert json.loads(events[0])["name"] == "fake mcp check"
    assert len(otel_lines) == 1
    otel_payload = json.loads(otel_lines[0])
    assert otel_payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"] == (
        "workspace_smoke.mcp_check fake mcp check"
    )
