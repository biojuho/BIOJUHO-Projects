from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_workspace_smoke.py"
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

    assert {check.scope for check in checks} == {"workspace", "desci", "agriguard", "mcp"}
    assert any(check.name == "workspace regression tests" for check in checks)
    assert any(check.name == "desci frontend unit tests" for check in checks)
    assert any(check.name == "desci bundle budget" for check in checks)
    assert any(check.name == "notebooklm compile" for check in checks)

    for check in checks:
        assert (PROJECT_ROOT / check.cwd).exists()
        if "compile" in check.name:
            assert smoke.EXCLUDE_REGEX in check.command


def test_run_one_reports_missing_working_directory() -> None:
    smoke = load_smoke_module()
    check = smoke.Check("workspace", "missing", "does-not-exist", ["python", "-V"])

    result = smoke.run_one(PROJECT_ROOT, check)

    assert result.ok is False
    assert result.returncode == 2
    assert result.stderr_tail == "working directory missing"


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
