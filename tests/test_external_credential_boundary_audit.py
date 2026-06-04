from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "external_credential_boundary_audit.py"
REGISTRY_PATH = PROJECT_ROOT / "ops" / "references" / "external_credential_boundaries.json"


def load_module():
    spec = importlib.util.spec_from_file_location("external_credential_boundary_audit", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_registry_validates_boundaries_without_secret_values() -> None:
    audit = load_module()

    summary = audit.audit_registry(audit.load_registry(REGISTRY_PATH), workspace_root=PROJECT_ROOT, env={})

    assert summary["status"] == "pass"
    assert summary["boundary_count"] >= 5
    assert "canva_oauth_and_openapi_tool_execution" in {
        boundary["id"] for boundary in summary["boundaries"]
    }
    assert summary["missing_required_env_count"] >= 1
    assert "CANVA_CLIENT_SECRET" in summary["missing_required_env"]
    assert all(boundary["verification_commands"] for boundary in summary["boundaries"])
    hosted = next(boundary for boundary in summary["boundaries"] if boundary["id"] == "hosted_agent_runtime_credentials")
    assert hosted["operator_approval_required"] is True
    assert hosted["operator_approval_env"] == "HOSTED_AGENT_RUNTIME_APPROVED"
    assert hosted["operator_approval_available"] is False


def test_registry_rejects_missing_evidence_terms() -> None:
    audit = load_module()
    payload = audit.load_registry(REGISTRY_PATH)
    payload["boundaries"][0]["evidence"][0]["must_contain"] = ["definitely absent term"]

    summary = audit.audit_registry(payload, workspace_root=PROJECT_ROOT, env={})

    assert summary["status"] == "fail"
    assert any("definitely absent term" in error for error in summary["errors"])


def test_registry_rejects_missing_verification_commands() -> None:
    audit = load_module()
    payload = audit.load_registry(REGISTRY_PATH)
    payload["boundaries"][0].pop("verification_commands")

    summary = audit.audit_registry(payload, workspace_root=PROJECT_ROOT, env={})

    assert summary["status"] == "fail"
    assert any("verification_commands" in error for error in summary["errors"])


def test_required_env_reports_names_without_values(tmp_path: Path) -> None:
    audit = load_module()
    evidence = tmp_path / "evidence.md"
    evidence.write_text("external approval required\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "generated_at": "2026-06-05T03:04:31+09:00",
        "objective": "test",
        "boundaries": [
            {
                "id": "sample",
                "title": "Sample",
                "status": "credential_gated",
                "owner": "operator",
                "required_env": ["SAMPLE_TOKEN"],
                "optional_env_any_of": ["SAMPLE_ALT_TOKEN"],
                "blocked_until": ["operator supplies credentials"],
                "verification_commands": ["python verify-sample.py"],
                "claim_policy": "do not claim complete without credentials",
                "evidence": [
                    {
                        "path": "evidence.md",
                        "must_contain": ["external approval required"],
                    }
                ],
            }
        ],
    }

    summary = audit.audit_registry(
        payload,
        workspace_root=tmp_path,
        env={"SAMPLE_TOKEN": "super-secret-value", "SAMPLE_ALT_TOKEN": "other-secret"},
    )

    serialized = json.dumps(summary)
    assert summary["status"] == "pass"
    assert summary["missing_required_env"] == []
    assert summary["boundaries"][0]["optional_env_available"] is True
    assert "super-secret-value" not in serialized
    assert "other-secret" not in serialized


def test_cli_writes_json_and_markdown_outputs(tmp_path: Path) -> None:
    audit = load_module()
    json_out = tmp_path / "credential-boundary.json"
    markdown_out = tmp_path / "credential-boundary.md"

    exit_code = audit.main(
        [
            "--registry",
            str(REGISTRY_PATH),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    report = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert exit_code == 0
    assert report["status"] == "pass"
    assert "External Credential Boundary Audit" in markdown
    assert "do not claim" in markdown
