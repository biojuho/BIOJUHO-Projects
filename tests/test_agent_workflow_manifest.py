from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "agent_workflow_manifest.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "agent_workflows.json"


def load_manifest_module():
    spec = importlib.util.spec_from_file_location("agent_workflow_manifest", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_manifest_validates_against_real_workspace_paths() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    summary = manifest.summarize_manifest(payload)

    assert errors == []
    assert summary["workflow_count"] == 6
    assert summary["launch_status_counts"] == {"active": 6}
    assert summary["smoke_scope_counts"] == {
        "agriguard": 1,
        "desci": 1,
        "getdaytrends": 1,
        "mcp": 2,
        "workspace": 1,
    }
    assert {workflow["id"] for workflow in summary["workflows"]} == {
        "dailynews-x-ops",
        "getdaytrends-operator-run",
        "desci-launch-readiness",
        "agriguard-qr-product-verification",
        "canva-widget-oauth-preview",
        "workspace-quality-dashboard",
    }
    assert all(workflow["entrypoint_count"] >= 2 for workflow in summary["workflows"])


def test_cli_writes_machine_and_markdown_evidence(tmp_path: Path) -> None:
    manifest = load_manifest_module()
    json_out = tmp_path / "agent-workflows.json"
    markdown_out = tmp_path / "agent-workflows.md"

    result = manifest.main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    machine = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert machine["workflow_count"] == 6
    assert machine["mcp_server_counts"]["playwright"] >= 4
    assert "Agent Workflow Manifest" in markdown
    assert "evalstate/fast-agent" in markdown
    assert "workspace-quality-dashboard" in markdown


def test_build_workflow_plan_parses_quality_gate_cwd() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)

    plan = manifest.build_workflow_plan(payload, "dailynews-x-ops")

    assert plan["execution_mode"] == "dry_run"
    assert plan["will_execute"] is False
    assert plan["workflow"]["id"] == "dailynews-x-ops"
    quality_steps = [step for step in plan["steps"] if step["phase"] == "quality_gate"]
    assert quality_steps[0]["cwd"] == "."
    assert quality_steps[0]["command"] == "python ops/scripts/run_workspace_smoke.py --scope mcp"
    assert quality_steps[1]["cwd"] == "automation/DailyNews"
    assert quality_steps[1]["command"] == "python -m pytest tests/unit -q"


def test_cli_writes_workflow_plan_outputs(tmp_path: Path) -> None:
    manifest = load_manifest_module()
    plan_json = tmp_path / "workflow-plan.json"
    plan_markdown = tmp_path / "workflow-plan.md"

    result = manifest.main(
        [
            "--manifest",
            str(MANIFEST_PATH),
            "--workflow-plan",
            "workspace-quality-dashboard",
            "--plan-json-out",
            str(plan_json),
            "--plan-markdown-out",
            str(plan_markdown),
        ]
    )

    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    markdown = plan_markdown.read_text(encoding="utf-8")
    assert result == 0
    assert plan["workflow"]["id"] == "workspace-quality-dashboard"
    assert plan["execution_mode"] == "dry_run"
    assert any(step["phase"] == "quality_gate" for step in plan["steps"])
    assert "Agent Workflow Dry-Run Plan" in markdown
    assert "workspace-quality-dashboard" in markdown


def test_workflow_plan_rejects_unknown_workflow() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)

    try:
        manifest.build_workflow_plan(payload, "missing-workflow")
    except ValueError as exc:
        assert "unknown workflow id: missing-workflow" in str(exc)
    else:
        raise AssertionError("expected unknown workflow to fail")


def test_manifest_rejects_missing_entrypoint() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)
    payload["workflows"][0]["entrypoints"] = ["missing/workflow.py"]

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "workflows[0].entrypoints[0] must exist in the workspace" in errors


def test_manifest_rejects_untrusted_source_and_escaping_evidence() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)
    payload["source_context"]["url"] = "https://example.com/agent"
    payload["workflows"][0]["evidence"] = ["../outside.md"]

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "source_context.url must be a GitHub HTTPS URL" in errors
    assert "workflows[0].evidence[0] must be a repo-relative path" in errors
