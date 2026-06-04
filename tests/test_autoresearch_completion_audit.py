from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "autoresearch_completion_audit.py"
CONTRACT_PATH = PROJECT_ROOT / "ops" / "references" / "autoresearch_completion_contract.json"


def load_module():
    spec = importlib.util.spec_from_file_location("autoresearch_completion_audit", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_contract_maps_objective_to_existing_artifacts() -> None:
    audit = load_module()

    summary = audit.audit_contract(audit.load_contract(CONTRACT_PATH), workspace_root=PROJECT_ROOT)

    assert summary["valid"] is True
    assert summary["cycle_evidence_ready"] is True
    assert summary["global_objective_complete"] is False
    assert summary["missing_required"] == []
    assert "external_credential_boundaries" in summary["explicit_blockers"]
    assert summary["status_counts"]["covered"] >= 8
    assert {item["id"] for item in summary["criteria"]} >= {
        "pre_push_regression_gate",
        "mcp_runtime_subprocess_smoke",
    }


def test_run_writes_json_and_markdown_outputs(tmp_path: Path) -> None:
    audit = load_module()
    json_out = tmp_path / "audit.json"
    markdown_out = tmp_path / "audit.md"

    summary = audit.run(CONTRACT_PATH, json_out=json_out, markdown_out=markdown_out)

    persisted = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert persisted["criterion_count"] == summary["criterion_count"]
    assert "Global objective complete: `false`" in markdown
    assert "external_credential_boundaries" in markdown


def test_missing_required_evidence_invalidates_contract(tmp_path: Path) -> None:
    audit = load_module()
    payload = audit.load_contract(CONTRACT_PATH)
    payload["criteria"][0]["evidence"][0]["path"] = "docs/reports/missing.md"

    summary = audit.audit_contract(payload, workspace_root=PROJECT_ROOT)

    assert summary["valid"] is False
    assert summary["cycle_evidence_ready"] is False
    assert any("does not exist" in error for error in summary["errors"])


def test_required_partial_criterion_blocks_cycle_readiness() -> None:
    audit = load_module()
    payload = audit.load_contract(CONTRACT_PATH)
    payload["criteria"][0]["status"] = "partial"

    summary = audit.audit_contract(payload, workspace_root=PROJECT_ROOT)

    assert summary["valid"] is True
    assert summary["cycle_evidence_ready"] is False
    assert summary["missing_required"] == ["product_launch_gate"]
