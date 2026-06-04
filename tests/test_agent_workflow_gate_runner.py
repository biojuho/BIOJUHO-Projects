from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "agent_workflow_gate_runner.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "agent_workflows.json"


def load_module():
    spec = importlib.util.spec_from_file_location("agent_workflow_gate_runner", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_gate_steps_parses_workflow_quality_gates() -> None:
    runner = load_module()
    payload = runner.workflow_manifest.load_manifest(MANIFEST_PATH)
    workflow = runner.select_workflow(payload, "workspace-quality-dashboard")

    steps = runner.build_gate_steps(workflow, max_gates=2)

    assert len(steps) == 2
    assert steps[0]["cwd"] == "."
    assert steps[0]["command"][1:] == ["ops/scripts/run_workspace_smoke.py", "--scope", "workspace"]
    assert steps[1]["cwd"] == "apps/dashboard"
    assert steps[1]["command"][-2:] == ["--", "src/App.test.jsx"]


def test_dry_run_report_keeps_gates_planned(tmp_path: Path) -> None:
    runner = load_module()
    json_out = tmp_path / "gate-runner.json"
    markdown_out = tmp_path / "gate-runner.md"

    report = runner.run_workflow_gates(
        MANIFEST_PATH,
        "workspace-quality-dashboard",
        execute=False,
        max_gates=1,
        timeout_seconds=1,
        json_out=json_out,
        markdown_out=markdown_out,
    )

    persisted = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert report["status"] == "pass"
    assert report["execution_mode"] == "dry_run"
    assert report["summary"]["planned_gates"] == 1
    assert persisted["workflow"]["id"] == "workspace-quality-dashboard"
    assert "Agent Workflow Gate Runner" in markdown


def test_execute_uses_existing_quality_gate_command(monkeypatch) -> None:
    runner = load_module()
    seen: list[tuple[list[str], Path]] = []

    def fake_run(command, *, cwd, capture_output, text, encoding, errors, timeout, check, env):
        seen.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    report = runner.run_workflow_gates(
        MANIFEST_PATH,
        "dailynews-x-ops",
        execute=True,
        max_gates=1,
        timeout_seconds=10,
    )

    assert report["status"] == "pass"
    assert report["summary"]["passed_gates"] == 1
    assert seen[0][0][1:] == ["ops/scripts/run_workspace_smoke.py", "--scope", "mcp"]
    assert seen[0][1] == PROJECT_ROOT


def test_execute_failure_marks_report_failed(monkeypatch) -> None:
    runner = load_module()

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, "", "failed\n")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    try:
        runner.run_workflow_gates(
            MANIFEST_PATH,
            "dailynews-x-ops",
            execute=True,
            max_gates=1,
            timeout_seconds=10,
        )
    except ValueError as exc:
        assert "gate 1 failed" in str(exc)
    else:
        raise AssertionError("expected failed gate to raise")


def test_cli_writes_dry_run_outputs(tmp_path: Path) -> None:
    runner = load_module()
    json_out = tmp_path / "gate-runner.json"
    markdown_out = tmp_path / "gate-runner.md"

    exit_code = runner.main(
        [
            "--workflow",
            "workspace-quality-dashboard",
            "--max-gates",
            "1",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["execution_mode"] == "dry_run"
    assert "workspace-quality-dashboard" in markdown_out.read_text(encoding="utf-8")
