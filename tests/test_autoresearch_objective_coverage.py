from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "autoresearch_objective_coverage.py"
REQUIREMENTS_PATH = PROJECT_ROOT / "ops" / "references" / "autoresearch_objective_requirements.json"


def load_module():
    spec = importlib.util.spec_from_file_location("autoresearch_objective_coverage", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_requirements_map_prompt_to_artifacts() -> None:
    coverage = load_module()
    payload = coverage.load_requirements(REQUIREMENTS_PATH)

    report = coverage.audit_requirements(payload, workspace_root=PROJECT_ROOT)

    assert report["valid"] is True
    assert report["cycle_prompt_covered"] is True
    assert report["global_objective_complete"] is False
    assert report["requirement_count"] >= 7
    assert "제품출시" in payload["objective_original"]
    assert "오토리서치" in payload["objective_original"]
    assert "external_credential_and_runtime_boundaries" in report["blocked_requirements"]
    assert {
        requirement["id"]
        for requirement in report["requirements"]
    } >= {
        "launch_ready_product_hardening",
        "github_related_project_research",
        "self_improving_autoresearch_skill",
        "continuous_ab_adoption_commit_push",
        "direct_app_click_qa",
        "beyond_user_expected_quality",
        "external_credential_and_runtime_boundaries",
    }


def test_run_writes_json_and_markdown_outputs(tmp_path: Path) -> None:
    coverage = load_module()
    json_out = tmp_path / "coverage.json"
    markdown_out = tmp_path / "coverage.md"

    report = coverage.run(REQUIREMENTS_PATH, json_out=json_out, markdown_out=markdown_out)

    persisted = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert persisted["requirement_count"] == report["requirement_count"]
    assert "AutoResearch Objective Coverage Audit" in markdown
    assert "Global objective complete: `false`" in markdown


def test_unknown_completion_criterion_is_invalid() -> None:
    coverage = load_module()
    payload = coverage.load_requirements(REQUIREMENTS_PATH)
    payload["requirements"][0]["completion_criteria"] = ["missing_criterion"]

    report = coverage.audit_requirements(payload, workspace_root=PROJECT_ROOT)

    assert report["valid"] is False
    assert any("missing_criterion" in error for error in report["errors"])


def test_missing_evidence_term_is_invalid() -> None:
    coverage = load_module()
    payload = coverage.load_requirements(REQUIREMENTS_PATH)
    payload["requirements"][0]["evidence"][0]["must_contain"] = ["definitely absent objective term"]

    report = coverage.audit_requirements(payload, workspace_root=PROJECT_ROOT)

    assert report["valid"] is False
    assert any("definitely absent objective term" in error for error in report["errors"])


def test_blocked_requirement_requires_blockers() -> None:
    coverage = load_module()
    payload = coverage.load_requirements(REQUIREMENTS_PATH)
    for requirement in payload["requirements"]:
        if requirement["id"] == "external_credential_and_runtime_boundaries":
            requirement["blockers"] = []
            break

    report = coverage.audit_requirements(payload, workspace_root=PROJECT_ROOT)

    assert report["valid"] is False
    assert any("blockers" in error for error in report["errors"])


def test_mojibake_prompt_terms_are_invalid() -> None:
    coverage = load_module()
    payload = coverage.load_requirements(REQUIREMENTS_PATH)
    payload["requirements"][0]["prompt_terms"] = ["?쒗뭹異쒖떆"]

    report = coverage.audit_requirements(payload, workspace_root=PROJECT_ROOT)

    assert report["valid"] is False
    assert any("mojibake" in error for error in report["errors"])
