from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
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


def assert_utc_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(parsed)


def test_build_gate_steps_parses_workflow_quality_gates() -> None:
    runner = load_module()
    payload = runner.workflow_manifest.load_manifest(MANIFEST_PATH)
    workflow = runner.select_workflow(payload, "workspace-quality-dashboard")

    steps = runner.build_gate_steps(workflow, max_gates=2)

    assert len(steps) == 2
    assert steps[0]["cwd"] == "."
    assert steps[0]["command"][1:] == ["ops/scripts/run_workspace_smoke.py", "--scope", "workspace"]
    assert steps[0]["safety"]["risk"] == "deterministic"
    assert steps[1]["cwd"] == "apps/dashboard"
    assert steps[1]["command"][-2:] == ["--", "src/App.test.jsx"]
    assert steps[1]["safety"]["requires_approval"] is False


def test_build_gate_steps_marks_side_effecting_gates() -> None:
    runner = load_module()
    payload = runner.workflow_manifest.load_manifest(MANIFEST_PATH)
    workflow = runner.select_workflow(payload, "desci-launch-readiness")

    steps = runner.build_gate_steps(workflow, max_gates=2)

    assert steps[0]["safety"]["risk"] == "deterministic"
    assert steps[1]["safety"]["risk"] == "side_effecting"
    assert steps[1]["safety"]["requires_approval"] is True
    assert "dev_server_start" in steps[1]["safety"]["reasons"]


def test_build_gate_steps_selects_single_gate_index() -> None:
    runner = load_module()
    payload = runner.workflow_manifest.load_manifest(MANIFEST_PATH)
    workflow = runner.select_workflow(payload, "desci-launch-readiness")

    steps = runner.build_gate_steps(workflow, gate_index=2)

    assert len(steps) == 1
    assert steps[0]["index"] == 2
    assert steps[0]["cwd"] == "."
    assert steps[0]["safety"]["requires_approval"] is True


def test_select_workflows_filters_by_smoke_scope() -> None:
    runner = load_module()
    payload = runner.workflow_manifest.load_manifest(MANIFEST_PATH)

    workflows = runner.select_workflows(payload, None, all_workflows=False, smoke_scope="mcp")

    assert [workflow["id"] for workflow in workflows] == [
        "dailynews-x-ops",
        "canva-widget-oauth-preview",
    ]
    assert {workflow["smoke_scope"] for workflow in workflows} == {"mcp"}


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
    assert_utc_timestamp(report["generated_at"])
    assert persisted["generated_at"] == report["generated_at"]
    assert persisted["workflow"]["id"] == "workspace-quality-dashboard"
    assert "Agent Workflow Gate Runner" in markdown


def test_matrix_and_workflow_reports_use_utc_generated_at() -> None:
    runner = load_module()

    workflow_report = runner.run_workflow_gates(
        MANIFEST_PATH,
        "workspace-quality-dashboard",
        execute=False,
        max_gates=1,
        timeout_seconds=1,
    )
    matrix_report = runner.run_workflow_matrix(
        MANIFEST_PATH,
        execute=False,
        max_gates=1,
        timeout_seconds=1,
    )

    assert_utc_timestamp(workflow_report["generated_at"])
    assert_utc_timestamp(matrix_report["generated_at"])
    for nested_workflow in matrix_report["workflows"]:
        assert_utc_timestamp(nested_workflow["generated_at"])


def test_report_snapshots_do_not_mutate_manifest_nested_state() -> None:
    runner = load_module()
    payload = runner.workflow_manifest.load_manifest(MANIFEST_PATH)
    workflow = runner.select_workflow(payload, "workspace-quality-dashboard")
    steps = runner.build_gate_steps(workflow, max_gates=1)
    result = {
        **steps[0],
        "status": "planned",
        "returncode": None,
        "elapsed_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "skip_reason": "",
    }

    report = runner.build_report(
        payload,
        workflow,
        [result],
        execute=False,
        allow_side_effect_gates=False,
        max_gates=1,
        gate_index=None,
    )
    report["source_context"]["repo"] = "mutated/repo"
    report["workflow"]["agent_roles"].append("mutated-role")
    report["workflow"]["mcp_servers"].append("mutated-server")
    report["gates"][0]["command"].append("--mutated")

    assert payload["source_context"]["repo"] == "evalstate/fast-agent"
    assert "mutated-role" not in workflow["agent_roles"]
    assert "mutated-server" not in workflow["mcp_servers"]
    assert "--mutated" not in result["command"]


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


def test_execute_skips_side_effecting_gates_without_override(monkeypatch) -> None:
    runner = load_module()
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    report = runner.run_workflow_gates(
        MANIFEST_PATH,
        "desci-launch-readiness",
        execute=True,
        max_gates=2,
        timeout_seconds=10,
    )

    assert report["status"] == "pass"
    assert report["summary"]["passed_gates"] == 1
    assert report["summary"]["skipped_gates"] == 1
    assert report["summary"]["approval_required_gates"] == 1
    assert report["gates"][1]["status"] == "skipped"
    assert "--allow-side-effect-gates" in report["gates"][1]["skip_reason"]
    assert len(seen) == 1


def test_execute_allows_side_effecting_gates_with_override(monkeypatch) -> None:
    runner = load_module()
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    report = runner.run_workflow_gates(
        MANIFEST_PATH,
        "desci-launch-readiness",
        execute=True,
        allow_side_effect_gates=True,
        max_gates=2,
        timeout_seconds=10,
    )

    assert report["summary"]["passed_gates"] == 2
    assert report["summary"]["skipped_gates"] == 0
    assert len(seen) == 2


def test_run_rejects_combined_gate_limits() -> None:
    runner = load_module()

    try:
        runner.run_workflow_gates(
            MANIFEST_PATH,
            "desci-launch-readiness",
            execute=False,
            max_gates=1,
            gate_index=2,
            timeout_seconds=10,
        )
    except ValueError as exc:
        assert "--max-gates and --gate-index cannot be combined" in str(exc)
    else:
        raise AssertionError("expected combined gate selectors to fail")


def test_execute_gate_index_skips_side_effecting_gate_without_running(monkeypatch) -> None:
    runner = load_module()

    def fake_run(command, **kwargs):
        raise AssertionError("side-effecting gate should be skipped before subprocess.run")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    report = runner.run_workflow_gates(
        MANIFEST_PATH,
        "desci-launch-readiness",
        execute=True,
        max_gates=None,
        gate_index=2,
        timeout_seconds=10,
    )

    assert report["summary"]["selected_gates"] == 1
    assert report["summary"]["requested_gate_index"] == 2
    assert report["summary"]["skipped_gates"] == 1
    assert report["gates"][0]["status"] == "skipped"


def test_matrix_dry_run_plans_all_workflows(tmp_path: Path) -> None:
    runner = load_module()
    json_out = tmp_path / "matrix.json"
    markdown_out = tmp_path / "matrix.md"

    report = runner.run_workflow_matrix(
        MANIFEST_PATH,
        execute=False,
        max_gates=1,
        timeout_seconds=10,
        json_out=json_out,
        markdown_out=markdown_out,
    )

    persisted = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert report["status"] == "pass"
    assert report["summary"]["workflow_count"] == 6
    assert report["summary"]["selected_gates"] == 6
    assert report["summary"]["planned_gates"] == 6
    assert report["summary"]["reused_gates"] == 0
    assert persisted["summary"]["workflow_count"] == 6
    assert "Agent Workflow Gate Matrix" in markdown
    assert "dailynews-x-ops" in markdown


def test_matrix_dry_run_routes_by_smoke_scope(tmp_path: Path) -> None:
    runner = load_module()
    json_out = tmp_path / "matrix-mcp.json"
    markdown_out = tmp_path / "matrix-mcp.md"

    report = runner.run_workflow_matrix(
        MANIFEST_PATH,
        execute=False,
        max_gates=1,
        timeout_seconds=10,
        smoke_scope="mcp",
        json_out=json_out,
        markdown_out=markdown_out,
    )

    persisted = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    workflow_ids = [workflow["workflow"]["id"] for workflow in report["workflows"]]
    assert workflow_ids == ["dailynews-x-ops", "canva-widget-oauth-preview"]
    assert report["summary"]["requested_smoke_scope"] == "mcp"
    assert report["summary"]["workflow_count"] == 2
    assert report["summary"]["selected_gates"] == 2
    assert report["summary"]["planned_gates"] == 2
    assert persisted["summary"]["requested_smoke_scope"] == "mcp"
    assert "Smoke scope selector: `mcp`" in markdown
    assert "workspace-quality-dashboard" not in markdown


def test_matrix_execute_runs_safe_gates_and_skips_side_effecting(monkeypatch) -> None:
    runner = load_module()
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    report = runner.run_workflow_matrix(
        MANIFEST_PATH,
        execute=True,
        max_gates=2,
        timeout_seconds=10,
    )

    assert report["status"] == "pass"
    assert report["summary"]["workflow_count"] == 6
    assert report["summary"]["selected_gates"] == 12
    assert report["summary"]["skipped_gates"] == 2
    assert report["summary"]["reused_gates"] == 1
    assert report["summary"]["approval_required_gates"] == 2
    assert report["summary"]["passed_gates"] == 9
    assert len(seen) == 9
    reused = [
        gate
        for workflow in report["workflows"]
        for gate in workflow["gates"]
        if gate["status"] == "reused"
    ]
    assert reused[0]["workflow_id"] == "canva-widget-oauth-preview"
    assert reused[0]["reused_from"]["workflow_id"] == "dailynews-x-ops"
    assert reused[0]["reused_from"]["gate_index"] == 1
    assert reused[0]["reused_from"]["status"] == "pass"


def test_cli_writes_matrix_dry_run_outputs(tmp_path: Path) -> None:
    runner = load_module()
    json_out = tmp_path / "matrix.json"
    markdown_out = tmp_path / "matrix.md"

    exit_code = runner.main(
        [
            "--all-workflows",
            "--max-gates",
            "1",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    assert exit_code == 0
    assert json.loads(json_out.read_text(encoding="utf-8"))["summary"]["workflow_count"] == 6
    assert "Agent Workflow Gate Matrix" in markdown_out.read_text(encoding="utf-8")


def test_cli_rejects_ambiguous_or_missing_workflow_selection() -> None:
    runner = load_module()

    assert runner.main([]) == 1
    assert runner.main(["--workflow", "dailynews-x-ops", "--all-workflows"]) == 1
    assert runner.main(["--all-workflows", "--gate-index", "1"]) == 1
    assert runner.main(["--workflow", "dailynews-x-ops", "--smoke-scope", "mcp"]) == 1
    assert runner.main(["--smoke-scope", "mcp", "--gate-index", "1"]) == 1


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


def test_cli_writes_smoke_scope_dry_run_outputs(tmp_path: Path) -> None:
    runner = load_module()
    json_out = tmp_path / "scope-mcp.json"
    markdown_out = tmp_path / "scope-mcp.md"

    exit_code = runner.main(
        [
            "--smoke-scope",
            "mcp",
            "--max-gates",
            "1",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["summary"]["requested_smoke_scope"] == "mcp"
    assert payload["summary"]["workflow_count"] == 2
    assert "Smoke scope selector: `mcp`" in markdown_out.read_text(encoding="utf-8")
