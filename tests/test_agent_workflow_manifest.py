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


def test_current_manifest_validates_real_entrypoints_and_evidence() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)
    summary = manifest.summarize_manifest(payload)

    assert errors == []
    assert summary["workflow_count"] == 5
    assert summary["status_counts"] == {"active": 5}
    assert summary["smoke_scope_counts"] == {
        "desci": 1,
        "getdaytrends": 1,
        "mcp": 2,
        "workspace": 1,
    }
    assert summary["provider_counts"] == {
        "canva": 1,
        "google": 1,
        "local": 5,
        "openai": 3,
    }
    assert {workflow["id"] for workflow in summary["workflows"]} == {
        "getdaytrends-content-loop",
        "dailynews-x-ops-loop",
        "canva-mcp-widget-ops",
        "desci-grant-readiness-agent",
        "workspace-quality-operator",
    }


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
    assert machine["workflow_count"] == 5
    assert machine["smoke_scope_counts"]["mcp"] == 2
    assert "Agent Workflow Manifest" in markdown
    assert "canva-mcp-widget-ops" in markdown
    assert "workspace-quality-operator" in markdown


def test_manifest_rejects_unsafe_and_missing_paths() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)
    payload["workflows"][0]["entrypoints"] = ["../outside.py"]
    payload["workflows"][0]["evidence"] = ["missing/evidence.md"]

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "workflows[0].entrypoints[0] must be a repo-relative path" in errors
    assert "workflows[0].evidence[0] must exist in the workspace" in errors


def test_manifest_rejects_duplicate_ids_and_unknown_provider() -> None:
    manifest = load_manifest_module()
    payload = manifest.load_manifest(MANIFEST_PATH)
    payload["workflows"][1]["id"] = payload["workflows"][0]["id"]
    payload["workflows"][1]["providers"] = ["mystery"]

    errors = manifest.validate_manifest(payload, workspace_root=PROJECT_ROOT)

    assert "workflows[1].id must be unique" in errors
    assert "workflows[1].providers contains unsupported provider: mystery" in errors
