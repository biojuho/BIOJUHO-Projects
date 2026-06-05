from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "autoresearch_completion_audit.py"
CONTRACT_PATH = PROJECT_ROOT / "ops" / "references" / "autoresearch_completion_contract.json"

VOLATILE_FRESHNESS_KEYS = {
    "git_freshness",
    "protected_path_freshness",
    "json_freshness",
}


def load_module():
    spec = importlib.util.spec_from_file_location("autoresearch_completion_audit", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_completion_contract_artifacts_are_ci_auditable_without_volatile_freshness() -> None:
    audit = load_module()
    payload = _without_volatile_freshness(audit.load_contract(CONTRACT_PATH))

    summary = audit.audit_contract(payload, workspace_root=PROJECT_ROOT)

    assert summary["valid"] is True
    assert summary["cycle_evidence_ready"] is True
    assert summary["global_objective_complete"] is False
    assert "external_credential_boundaries" in summary["explicit_blockers"]
    assert {
        "workspace_smoke_ci_autoresearch_audit_tests",
        "completion_audit_summary_drift_guard",
        "objective_coverage_artifact_drift_guard",
    } <= {criterion["id"] for criterion in summary["criteria"]}


def _without_volatile_freshness(payload: dict) -> dict:
    cloned = copy.deepcopy(payload)
    for criterion in cloned.get("criteria", []):
        for evidence in criterion.get("evidence", []):
            for key in VOLATILE_FRESHNESS_KEYS:
                evidence.pop(key, None)
    return cloned
