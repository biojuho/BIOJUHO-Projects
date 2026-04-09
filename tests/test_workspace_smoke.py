from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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


def test_default_checks_cover_expected_scopes_and_existing_paths() -> None:
    smoke = load_smoke_module()
    checks = smoke.default_checks("python")

    assert {check.scope for check in checks} == {"workspace", "desci", "agriguard", "mcp", "getdaytrends"}
    assert any(check.name == "workspace regression tests" for check in checks)
    assert any(check.name == "dashboard frontend lint" for check in checks)
    assert any(check.name == "dashboard frontend tests" for check in checks)
    assert any(check.name == "dashboard frontend build" for check in checks)
    assert any(check.name == "dashboard bundle budget" for check in checks)
    assert any(check.name == "desci frontend unit tests" for check in checks)
    assert any(check.name == "desci bundle budget" for check in checks)
    assert any(check.name == "agriguard backend tests" for check in checks)
    assert any(check.name == "notebooklm compile" for check in checks)
    assert any(check.name == "DailyNews unit tests" for check in checks)
    assert any(check.name == "getdaytrends tests" for check in checks)

    for check in checks:
        assert (PROJECT_ROOT / check.cwd).exists()
        if "compile" in check.name:
            assert smoke.EXCLUDE_REGEX in check.command


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


def test_resolve_python_executable_prefers_workspace_venv_over_current_interpreter(
    tmp_path: Path, monkeypatch
) -> None:
    smoke = load_smoke_module()
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
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
    local_python = tmp_path / ".venv" / "Scripts" / "python.exe"
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

        class Proc:
            returncode = 0
            stdout = b"ok"
            stderr = b""

        return Proc()

    monkeypatch.setattr(smoke, "USE_UV_ISOLATED_RUNNER", True)
    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is True
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

    monkeypatch.setattr(smoke, "run_one", lambda root, item: next(attempts))

    result = smoke.run_check(PROJECT_ROOT, check)

    assert result.ok is True
    assert result.stdout_tail == "31 passed"


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


def test_main_writes_json_report_for_selected_scope(tmp_path, monkeypatch) -> None:
    smoke = load_smoke_module()
    fake_check = smoke.Check("workspace", "fake check", ".", ["python", "-V"])
    fake_result = smoke.Result("workspace", "fake check", ".", "python -V", 0, True, "ok", "")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(smoke, "resolve_python_executable", lambda root: "python")
    monkeypatch.setattr(smoke, "has_module", lambda python_exe, module_name: True)
    monkeypatch.setattr(smoke, "default_checks", lambda python_exe: [fake_check])
    monkeypatch.setattr(smoke, "run_one", lambda root, item: fake_result)
    monkeypatch.setattr(
        smoke.sys,
        "argv",
        ["run_workspace_smoke.py", "--scope", "workspace", "--json-out", "smoke.json"],
    )

    exit_code = smoke.main()

    report = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert report == [
        {
            "scope": "workspace",
            "name": "fake check",
            "cwd": ".",
            "command": "python -V",
            "returncode": 0,
            "ok": True,
            "stdout_tail": "ok",
            "stderr_tail": "",
        }
    ]
