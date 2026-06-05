from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "autoresearch_completion_audit.py"
CONTRACT_PATH = PROJECT_ROOT / "ops" / "references" / "autoresearch_completion_contract.json"
SUMMARY_JSON_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json"
SUMMARY_MARKDOWN_PATH = PROJECT_ROOT / "docs" / "reports" / "2026-06" / "AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md"


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
    assert summary["status_counts"]["covered"] >= 16
    assert {item["id"] for item in summary["criteria"]} >= {
        "pre_push_regression_gate",
        "mcp_runtime_subprocess_smoke",
        "mcp_service_runtime_smoke",
        "mcp_otel_collector_handoff",
        "workspace_smoke_trace_drain_guard",
        "agent_workflow_gate_runner",
        "agent_workflow_gate_safety",
        "agent_workflow_gate_matrix",
        "current_tip_freshness_gate",
        "direct_browser_qa_freshness_gate",
        "github_source_freshness_snapshot",
        "github_source_snapshot_recency_gate",
        "github_source_viability_gate",
        "github_source_change_summary",
        "github_source_review_queue",
        "github_source_commit_digest",
        "canva_mcp_continuation_guard",
        "canva_widget_state_continuation_guard",
        "canva_mcp_openai_namespace_metadata_guard",
        "prompt_to_artifact_objective_coverage",
        "external_credential_boundary_registry",
        "external_credential_handoff",
        "external_credential_live_verifier",
        "hosted_agent_approval_boundary",
        "telegram_notification_live_delivery_verifier",
        "agent_workflow_gate_matrix_reuse",
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


def test_checked_in_summary_artifacts_match_current_contract() -> None:
    audit = load_module()

    summary = audit.audit_contract(audit.load_contract(CONTRACT_PATH), workspace_root=PROJECT_ROOT)
    expected_json = json.dumps(summary, indent=2, ensure_ascii=False)
    expected_markdown = audit.format_markdown(summary)

    assert SUMMARY_JSON_PATH.read_text(encoding="utf-8") == expected_json
    assert SUMMARY_MARKDOWN_PATH.read_text(encoding="utf-8") == expected_markdown


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


def test_git_freshness_rejects_non_evidence_changes(monkeypatch, tmp_path: Path) -> None:
    audit = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "generated_at": "2026-06-05T01:45:50+09:00",
        "objective": "test",
        "global_completion_policy": {
            "open_ended_until_user_stop": True,
            "can_mark_complete": False,
            "reason": "test",
        },
        "criteria": [
            {
                "id": "freshness",
                "requirement": "fresh launch proof",
                "required": True,
                "status": "covered",
                "evidence": [
                    {
                        "path": "evidence.md",
                        "must_contain": ["ok"],
                        "git_freshness": {
                            "proof_commit": "abc1234",
                            "remote_ref": "origin/main",
                            "allowed_paths_since_proof": ["docs/reports/"],
                        },
                    }
                ],
            }
        ],
    }

    def fake_run_git(args: list[str], workspace_root: Path):
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["diff", "--name-only"]:
            return subprocess.CompletedProcess(args, 0, "docs/reports/proof.md\napps/product/app.py\n", "")
        raise AssertionError(args)

    monkeypatch.setattr(audit, "_run_git", fake_run_git)

    summary = audit.audit_contract(payload, workspace_root=tmp_path)

    assert summary["valid"] is False
    assert summary["cycle_evidence_ready"] is False
    assert any("apps/product/app.py" in error for error in summary["errors"])


def test_git_freshness_requires_proof_ancestor(monkeypatch, tmp_path: Path) -> None:
    audit = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "generated_at": "2026-06-05T01:45:50+09:00",
        "objective": "test",
        "global_completion_policy": {
            "open_ended_until_user_stop": True,
            "can_mark_complete": False,
            "reason": "test",
        },
        "criteria": [
            {
                "id": "freshness",
                "requirement": "fresh launch proof",
                "required": True,
                "status": "covered",
                "evidence": [
                    {
                        "path": "evidence.md",
                        "must_contain": ["ok"],
                        "git_freshness": {
                            "proof_commit": "abc1234",
                            "remote_ref": "origin/main",
                            "allowed_paths_since_proof": ["docs/reports/"],
                        },
                    }
                ],
            }
        ],
    }

    def fake_run_git(args: list[str], workspace_root: Path):
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return subprocess.CompletedProcess(args, 1, "", "not ancestor")
        raise AssertionError(args)

    monkeypatch.setattr(audit, "_run_git", fake_run_git)

    summary = audit.audit_contract(payload, workspace_root=tmp_path)

    assert summary["valid"] is False
    assert any("not an ancestor" in error for error in summary["errors"])


def test_protected_path_freshness_rejects_changed_browser_surface(monkeypatch, tmp_path: Path) -> None:
    audit = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok\n", encoding="utf-8")
    payload = _freshness_payload(
        {
            "protected_path_freshness": {
                "proof_commit": "abc1234",
                "remote_ref": "origin/main",
                "protected_paths": ["apps/dashboard/", "ops/scripts/dev_server_browser_smoke.py"],
            }
        }
    )

    def fake_run_git(args: list[str], workspace_root: Path):
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["diff", "--name-only"]:
            return subprocess.CompletedProcess(args, 0, "docs/reports/proof.md\napps/dashboard/src/App.jsx\n", "")
        raise AssertionError(args)

    monkeypatch.setattr(audit, "_run_git", fake_run_git)

    summary = audit.audit_contract(payload, workspace_root=tmp_path)

    assert summary["valid"] is False
    assert summary["cycle_evidence_ready"] is False
    assert any("apps/dashboard/src/App.jsx" in error for error in summary["errors"])


def test_protected_path_freshness_allows_unrelated_changes(monkeypatch, tmp_path: Path) -> None:
    audit = load_module()
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok\n", encoding="utf-8")
    payload = _freshness_payload(
        {
            "protected_path_freshness": {
                "proof_commit": "abc1234",
                "remote_ref": "origin/main",
                "protected_paths": ["apps/dashboard/", "mcp/canva-mcp/"],
            }
        }
    )

    def fake_run_git(args: list[str], workspace_root: Path):
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["diff", "--name-only"]:
            return subprocess.CompletedProcess(args, 0, "docs/reports/proof.md\nops/scripts/audit.py\n", "")
        raise AssertionError(args)

    monkeypatch.setattr(audit, "_run_git", fake_run_git)

    summary = audit.audit_contract(payload, workspace_root=tmp_path)

    assert summary["valid"] is True
    assert summary["cycle_evidence_ready"] is True
    assert summary["errors"] == []


def test_json_freshness_accepts_recent_passing_snapshot(tmp_path: Path) -> None:
    audit = load_module()
    evidence_file = tmp_path / "source.json"
    evidence_file.write_text(
        json.dumps({"status": "pass", "generated_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )
    payload = _freshness_payload(
        {
            "path": "source.json",
            "must_contain": ["pass"],
            "json_freshness": {
                "timestamp_field": "generated_at",
                "max_age_hours": 72,
                "status_field": "status",
                "required_status": "pass",
            },
        }
    )

    summary = audit.audit_contract(payload, workspace_root=tmp_path)

    assert summary["valid"] is True
    assert summary["cycle_evidence_ready"] is True
    assert summary["criteria"][0]["evidence"][0]["json_freshness"] is True


def test_json_freshness_rejects_stale_snapshot(tmp_path: Path) -> None:
    audit = load_module()
    evidence_file = tmp_path / "source.json"
    stale_timestamp = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    evidence_file.write_text(
        json.dumps({"status": "pass", "generated_at": stale_timestamp}),
        encoding="utf-8",
    )
    payload = _freshness_payload(
        {
            "path": "source.json",
            "must_contain": ["pass"],
            "json_freshness": {
                "timestamp_field": "generated_at",
                "max_age_hours": 1,
                "status_field": "status",
                "required_status": "pass",
            },
        }
    )

    summary = audit.audit_contract(payload, workspace_root=tmp_path)

    assert summary["valid"] is False
    assert summary["cycle_evidence_ready"] is False
    assert any("is stale" in error for error in summary["errors"])


def test_json_freshness_rejects_wrong_status(tmp_path: Path) -> None:
    audit = load_module()
    evidence_file = tmp_path / "source.json"
    evidence_file.write_text(
        json.dumps({"status": "fail", "generated_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )
    payload = _freshness_payload(
        {
            "path": "source.json",
            "must_contain": ["fail"],
            "json_freshness": {
                "timestamp_field": "generated_at",
                "max_age_hours": 72,
                "status_field": "status",
                "required_status": "pass",
            },
        }
    )

    summary = audit.audit_contract(payload, workspace_root=tmp_path)

    assert summary["valid"] is False
    assert summary["cycle_evidence_ready"] is False
    assert any("status must be 'pass'" in error for error in summary["errors"])


def _freshness_payload(extra_evidence: dict) -> dict:
    evidence = {
        "path": "evidence.md",
        "must_contain": ["ok"],
    }
    evidence.update(extra_evidence)
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T02:20:00+09:00",
        "objective": "test",
        "global_completion_policy": {
            "open_ended_until_user_stop": True,
            "can_mark_complete": False,
            "reason": "test",
        },
        "criteria": [
            {
                "id": "freshness",
                "requirement": "fresh launch proof",
                "required": True,
                "status": "covered",
                "evidence": [evidence],
            }
        ],
    }
