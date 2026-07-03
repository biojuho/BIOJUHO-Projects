from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import external_gate_handoff  # noqa: E402


def gate_payload(*, ok: bool = False) -> dict[str, object]:
    failed_surfaces = [] if ok else ["deploy_readiness", "provider_preflight"]
    return {
        "schema_version": 1,
        "ok": ok,
        "targets": ["railway", "vercel", "amoy", "github"],
        "provider_targets": ["railway", "vercel", "github"],
        "failed_surfaces": failed_surfaces,
        "summary": {
            "deploy_failed": 0 if ok else 2,
            "deploy_warnings": 0 if ok else 1,
            "provider_ready": 3 if ok else 1,
            "provider_count": 3,
            "provider_failed_checks": 0 if ok else 2,
            "failed_surface_count": len(failed_surfaces),
        },
        "deploy_readiness": {
            "ok": ok,
            "owner_surface_summary": []
            if ok
            else [
                {
                    "owner": "Firebase",
                    "surface": "Backend authentication",
                    "failed": 1,
                    "warnings": 0,
                    "failed_checks": ["railway_auth"],
                    "warning_checks": [],
                    "required_env": ["FIREBASE_SERVICE_ACCOUNT_JSON"],
                    "actions": [
                        {
                            "id": "railway_auth",
                            "target": "railway",
                            "status": "fail",
                            "required": True,
                            "keys": ["FIREBASE_SERVICE_ACCOUNT_JSON"],
                            "remediation": "Set Firebase service account JSON in Railway.",
                        }
                    ],
                },
                {
                    "owner": "Pinata/IPFS",
                    "surface": "Public asset minting",
                    "failed": 0,
                    "warnings": 1,
                    "failed_checks": [],
                    "warning_checks": ["railway_ipfs"],
                    "required_env": ["PINATA_JWT"],
                    "actions": [
                        {
                            "id": "railway_ipfs",
                            "target": "railway",
                            "status": "warn",
                            "required": False,
                            "keys": ["PINATA_JWT"],
                            "remediation": "Set Pinata credentials before public minting.",
                        }
                    ],
                },
            ],
        },
        "provider_preflight": {
            "ok": ok,
            "failed_checks": []
            if ok
            else [
                {
                    "provider": "vercel",
                    "id": "vercel_preflight_1",
                    "command": "vercel whoami",
                    "failure_reason": "auth_context_missing",
                },
                {
                    "provider": "vercel",
                    "id": "vercel_preflight_2",
                    "command": "vercel env ls production",
                    "failure_reason": "auth_context_missing",
                },
            ],
        },
    }


def test_external_gate_handoff_fails_closed_with_provider_rollup() -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    railway = next(item for item in payload["provider_rollup"] if item["provider"] == "railway")
    vercel = next(item for item in payload["provider_rollup"] if item["provider"] == "vercel")

    assert payload["ok"] is False
    assert payload["release_decision"] == "no-go"
    assert payload["operator_phase"] == "external_launch_blocked"
    assert payload["summary"]["next_action_count"] == 3
    assert railway["failed"] == 1
    assert railway["warnings"] == 1
    assert railway["template_filename"] == "railway.env"
    assert railway["has_env_template"] is True
    assert railway["required_env"] == ["FIREBASE_SERVICE_ACCOUNT_JSON", "PINATA_JWT"]
    assert vercel["failed"] == 2
    assert vercel["template_filename"] == "vercel.env"
    assert vercel["has_env_template"] is False
    assert vercel["failure_reasons"] == ["auth_context_missing"]
    assert vercel["commands"] == ["vercel whoami", "vercel env ls production"]


def test_external_gate_handoff_passes_when_gate_is_ready() -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(ok=True), evidence_path="var/gate.json")

    assert payload["ok"] is True
    assert payload["release_decision"] == "go"
    assert payload["operator_phase"] == "external_launch_ready"
    assert payload["summary"]["next_action_count"] == 0
    assert payload["next_actions"] == []
    assert payload["provider_rollup"] == []


def test_external_gate_handoff_markdown_uses_no_secret_values() -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    markdown = external_gate_handoff.render_markdown_report(payload)

    assert "DeSci External Gate Handoff" in markdown
    assert "Release decision: `no-go`" in markdown
    assert "`FIREBASE_SERVICE_ACCOUNT_JSON`" in markdown
    assert "vercel whoami" in markdown
    assert "private_key" not in markdown
    assert "sk_live_" not in markdown


def test_external_gate_handoff_writes_json_and_markdown(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    json_path = tmp_path / "handoff.json"
    markdown_path = tmp_path / "handoff.md"

    external_gate_handoff.write_json_report(json_path, payload)
    external_gate_handoff.write_markdown_report(markdown_path, payload)

    assert json.loads(json_path.read_text(encoding="utf-8"))["release_decision"] == "no-go"
    assert "Provider Rollup" in markdown_path.read_text(encoding="utf-8")
    assert not (tmp_path / "handoff.json.tmp").exists()
    assert not (tmp_path / "handoff.md.tmp").exists()


def test_external_gate_handoff_writes_no_secret_provider_templates(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")

    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    railway_text = paths["railway"].read_text(encoding="utf-8")

    assert set(paths) == {"railway"}
    assert paths["railway"].name == "railway.env"
    assert railway_text.count("FIREBASE_SERVICE_ACCOUNT_JSON=") == 1
    assert railway_text.count("PINATA_JWT=") == 1
    assert "Set Firebase service account JSON in Railway." in railway_text
    assert "vercel whoami" not in railway_text
    assert "sk_live_" not in railway_text
    assert not (paths["railway"].parent / "railway.env.tmp").exists()


def test_external_gate_handoff_can_preserve_existing_provider_templates(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    template_dir = tmp_path / "providers"
    template_dir.mkdir()
    railway_env = template_dir / "railway.env"
    railway_env.write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")

    paths = external_gate_handoff.write_provider_templates(template_dir, payload, overwrite=False)

    assert paths["railway"] == railway_env
    assert "super-secret" in railway_env.read_text(encoding="utf-8")


def test_external_gate_handoff_writes_provider_template_index(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    index_path = tmp_path / "provider-index.json"

    external_gate_handoff.write_provider_template_index(index_path, payload, paths)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    provider = index["providers"][0]

    assert index["ok"] is True
    assert index["safe_to_commit"] is True
    assert index["populated_key_count"] == 0
    assert provider["provider"] == "railway"
    assert provider["template_filename"] == "railway.env"
    assert provider["has_env_template"] is True
    assert provider["env_keys"] == ["FIREBASE_SERVICE_ACCOUNT_JSON", "PINATA_JWT"]
    assert provider["env_key_count"] == 2
    assert provider["populated_key_count"] == 0
    assert len(provider["sha256"]) == 64


def test_external_gate_handoff_template_index_flags_populated_values_without_leaking_them(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=\n", encoding="utf-8")

    index = external_gate_handoff.provider_template_index_payload(payload, paths)
    serialized = json.dumps(index)

    assert index["ok"] is False
    assert index["safe_to_commit"] is False
    assert index["populated_key_count"] == 1
    assert index["providers"][0]["populated_keys"] == ["FIREBASE_SERVICE_ACCOUNT_JSON"]
    assert "super-secret" not in serialized


def test_external_gate_handoff_writes_redacted_provider_apply_plan(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    plan_path = tmp_path / "apply-plan.json"
    markdown_path = tmp_path / "apply-plan.md"

    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    external_gate_handoff.write_provider_apply_plan_markdown(markdown_path, plan)
    markdown = markdown_path.read_text(encoding="utf-8")

    assert plan["ok"] is True
    assert plan["ready_provider_count"] == 0
    assert plan["provider_count"] == 1
    assert plan["operator_status"] == {
        "stage": "fill_provider_templates",
        "ready_to_apply": False,
        "ready_provider_count": 0,
        "blocked_provider_count": 1,
        "provider_templates_safe_to_commit": True,
        "apply_plan_safe_to_commit": True,
        "private_template_values_present": False,
        "completion_marker": "external_release_gate.ok=true",
        "next_required_action": (
            "Fill blank provider templates in a private local directory, then regenerate this apply plan with "
            "--preserve-provider-templates."
        ),
    }
    provider = plan["providers"][0]
    assert provider["provider"] == "railway"
    assert provider["ready_to_apply"] is False
    assert provider["env_keys"] == ["FIREBASE_SERVICE_ACCOUNT_JSON", "PINATA_JWT"]
    assert provider["blank_key_count"] == 2
    assert plan["provider_apply_plan_verification"]["success_condition"] == (
        "provider_apply_plan_verification.ok=true"
    )
    assert plan["provider_apply_plan_verification"]["ready_success_condition"] == (
        "provider_apply_plan_verification.ok=true and provider_apply_plan.ready_to_apply=true"
    )
    assert plan["provider_apply_plan_verification"]["provider_apply_plan_json"] == str(plan_path)
    assert plan["provider_apply_plan_verification"]["verify_json_out"] == str(
        tmp_path / "apply-plan-verify.json"
    )
    assert plan["provider_apply_plan_verification"]["require_ready_json_out"] == str(
        tmp_path / "apply-plan-require-ready.json"
    )
    assert plan["provider_apply_results_verification"]["success_condition"] == (
        "provider_apply_results_verification.ok=true and provider_apply_results.all_commands_succeeded=true"
    )
    assert plan["provider_apply_results_verification"]["provider_apply_plan_json"] == str(plan_path)
    assert plan["provider_apply_results_verification"]["provider_apply_results_json"] == str(
        tmp_path / "apply-plan-results.json"
    )
    assert plan["provider_apply_results_verification"]["template_json_out"] == str(
        tmp_path / "apply-plan-results-template.json"
    )
    assert plan["provider_apply_results_verification"]["verify_json_out"] == str(
        tmp_path / "apply-plan-results-verify.json"
    )
    assert (
        plan["provider_apply_results_verification"]["template_command"]
        == "python scripts/external_gate_handoff.py "
        f"--provider-apply-results-template-from-plan {plan_path} "
        f"--json-out {tmp_path / 'apply-plan-results-template.json'}"
    )
    assert (
        plan["provider_apply_results_verification"]["verify_command"]
        == "python scripts/external_gate_handoff.py "
        f"--verify-provider-apply-results {tmp_path / 'apply-plan-results.json'} "
        f"--provider-apply-plan {plan_path} --json-out {tmp_path / 'apply-plan-results-verify.json'}"
    )
    assert (
        plan["provider_apply_plan_verification"]["verify_command"]
        == "python scripts/external_gate_handoff.py "
        f"--verify-provider-apply-plan {plan_path} --json-out {tmp_path / 'apply-plan-verify.json'}"
    )
    assert (
        plan["provider_apply_plan_verification"]["require_ready_command"]
        == "python scripts/external_gate_handoff.py "
        f"--verify-provider-apply-plan {plan_path} --require-ready-to-apply "
        f"--json-out {tmp_path / 'apply-plan-require-ready.json'}"
    )
    assert plan["post_apply_completion_evidence"]["required"] is True
    assert (
        plan["post_apply_completion_evidence"]["success_condition"]
        == "post_apply_evidence_gate.ok=true and evidence_manifest_verification.ok=true and "
        "post_apply_promotion_receipt.ok=true"
    )
    assert (
        plan["post_apply_completion_evidence"]["aggregate_command"]
        == "python scripts/external_release_gate.py "
        f"--provider-template-dir {tmp_path / 'providers'} --target all "
        "--json-out var/external-release-gate-post-apply-all.json"
    )
    assert plan["post_apply_completion_evidence"]["promotion_gate_json_out"] == "var/post-apply-evidence-gate.json"
    assert (
        plan["post_apply_completion_evidence"]["promotion_manifest_json_out"]
        == "var/post-apply-evidence-manifest.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_manifest_verify_json_out"]
        == "var/post-apply-evidence-manifest-verify.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_json_out"]
        == "var/post-apply-promotion-receipt.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_verify_json_out"]
        == "var/post-apply-promotion-receipt-verify.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_require_go_json_out"]
        == "var/post-apply-promotion-receipt-require-go.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_gate_command"]
        == "python scripts/post_apply_evidence_gate.py "
        "--external-gate-json var/external-release-gate-post-apply-all.json "
        "--json-out var/post-apply-evidence-gate.json "
        "--manifest-out var/post-apply-evidence-manifest.json "
        "--verify-manifest-out var/post-apply-evidence-manifest-verify.json "
        "--promotion-receipt-out var/post-apply-promotion-receipt.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_single_command"]
        == plan["post_apply_completion_evidence"]["promotion_gate_command"]
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_manifest_verify_command"]
        == "python scripts/post_apply_evidence_gate.py "
        "--verify-manifest var/post-apply-evidence-manifest.json "
        "--json-out var/post-apply-evidence-manifest-verify.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_verify_command"]
        == "python scripts/post_apply_evidence_gate.py "
        "--verify-promotion-receipt var/post-apply-promotion-receipt.json "
        "--json-out var/post-apply-promotion-receipt-verify.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_require_go_command"]
        == "python scripts/post_apply_evidence_gate.py "
        "--verify-promotion-receipt var/post-apply-promotion-receipt.json "
        "--require-go --json-out var/post-apply-promotion-receipt-require-go.json"
    )
    assert plan["post_apply_completion_evidence"]["provider_json_outputs"] == {
        "railway": "var/external-release-gate-post-apply-railway.json"
    }
    assert provider["commands"][0]["command"] == "railway variable set FIREBASE_SERVICE_ACCOUNT_JSON --stdin"
    assert provider["post_apply_verify_commands"] == [
        "python scripts/external_release_gate.py "
        f"--provider-template-dir {tmp_path / 'providers'} --target railway "
        "--json-out var/external-release-gate-post-apply-railway.json"
    ]
    assert (
        provider["commands"][0]["powershell_command"]
        == "Get-Content -Raw '<private-values/FIREBASE_SERVICE_ACCOUNT_JSON.txt>' | railway variable set FIREBASE_SERVICE_ACCOUNT_JSON --stdin"
    )
    assert (
        provider["commands"][0]["posix_command"]
        == "railway variable set FIREBASE_SERVICE_ACCOUNT_JSON --stdin < <private-values/FIREBASE_SERVICE_ACCOUNT_JSON.txt>"
    )
    assert "super-secret" not in json.dumps(plan)
    assert "Stage: `fill_provider_templates`" in markdown
    assert "Completion marker: `external_release_gate.ok=true`" in markdown
    assert "Provider Apply Plan Verification" in markdown
    assert "apply-plan-verify.json" in markdown
    assert "apply-plan-require-ready.json" in markdown
    assert "--verify-provider-apply-plan" in markdown
    assert "--require-ready-to-apply" in markdown
    assert "Provider Apply Results Verification" in markdown
    assert "apply-plan-results.json" in markdown
    assert "apply-plan-results-template.json" in markdown
    assert "apply-plan-results-verify.json" in markdown
    assert "--provider-apply-results-template-from-plan" in markdown
    assert "--verify-provider-apply-results" in markdown
    assert "Post-Apply Evidence" in markdown
    assert "external-release-gate-post-apply-all.json" in markdown
    assert "external-release-gate-post-apply-railway.json" in markdown
    assert "post_apply_evidence_gate.py" in markdown
    assert "post-apply-evidence-gate.json" in markdown
    assert "post-apply-evidence-manifest.json" in markdown
    assert "post-apply-evidence-manifest-verify.json" in markdown
    assert "post-apply-promotion-receipt.json" in markdown
    assert "post-apply-promotion-receipt-verify.json" in markdown
    assert "post-apply-promotion-receipt-require-go.json" in markdown
    assert "--verify-manifest-out var/post-apply-evidence-manifest-verify.json" in markdown
    assert "--promotion-receipt-out var/post-apply-promotion-receipt.json" in markdown
    assert "--verify-manifest var/post-apply-evidence-manifest.json" in markdown
    assert "--verify-promotion-receipt var/post-apply-promotion-receipt.json" in markdown
    assert "--require-go --json-out var/post-apply-promotion-receipt-require-go.json" in markdown
    assert "PowerShell: `Get-Content -Raw '<private-values/FIREBASE_SERVICE_ACCOUNT_JSON.txt>'" in markdown
    assert "POSIX: `railway variable set FIREBASE_SERVICE_ACCOUNT_JSON --stdin" in markdown


def test_external_gate_handoff_apply_plan_detects_filled_templates_without_leaking_values(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")

    plan = external_gate_handoff.provider_apply_plan_payload(payload, paths)
    serialized = json.dumps(plan)

    assert plan["ready_provider_count"] == 1
    assert plan["provider_template_index"]["safe_to_commit"] is False
    assert plan["provider_template_index"]["populated_key_count"] == 2
    assert plan["operator_status"]["stage"] == "apply_provider_values"
    assert plan["operator_status"]["ready_to_apply"] is True
    assert plan["operator_status"]["blocked_provider_count"] == 0
    assert plan["operator_status"]["provider_templates_safe_to_commit"] is False
    assert plan["operator_status"]["apply_plan_safe_to_commit"] is True
    assert plan["operator_status"]["private_template_values_present"] is True
    assert plan["operator_status"]["completion_marker"] == "external_release_gate.ok=true"
    assert "external_release_gate.py" in plan["operator_status"]["next_required_action"]
    assert plan["post_apply_completion_evidence"]["aggregate_json_out"] == "var/external-release-gate-post-apply-all.json"
    assert (
        plan["post_apply_completion_evidence"]["promotion_manifest_json_out"]
        == "var/post-apply-evidence-manifest.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_manifest_verify_json_out"]
        == "var/post-apply-evidence-manifest-verify.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_json_out"]
        == "var/post-apply-promotion-receipt.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_verify_json_out"]
        == "var/post-apply-promotion-receipt-verify.json"
    )
    assert (
        plan["post_apply_completion_evidence"]["promotion_receipt_require_go_json_out"]
        == "var/post-apply-promotion-receipt-require-go.json"
    )
    assert plan["providers"][0]["ready_to_apply"] is True
    assert plan["providers"][0]["env_keys"] == ["FIREBASE_SERVICE_ACCOUNT_JSON", "PINATA_JWT"]
    assert plan["providers"][0]["blank_key_count"] == 0
    assert "super-secret" not in serialized
    assert "jwt-secret" not in serialized


def test_external_gate_handoff_provider_apply_plan_verifier_accepts_blank_templates_without_ready_requirement(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    plan_path = tmp_path / "apply-plan.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)

    verification = external_gate_handoff.verify_provider_apply_plan(plan_path)

    assert verification["ok"] is True
    assert verification["ready_to_apply"] is False
    assert verification["operator_stage"] == "fill_provider_templates"
    assert verification["summary"]["provider_count"] == 1
    assert verification["summary"]["ready_provider_count"] == 0
    assert verification["summary"]["blocked_provider_count"] == 1
    assert verification["summary"]["provider_failure_count"] == 0
    assert verification["summary"]["secret_marker_count"] == 0


def test_external_gate_handoff_provider_apply_plan_verifier_require_ready_blocks_blank_templates(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    plan_path = tmp_path / "apply-plan.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)

    verification = external_gate_handoff.verify_provider_apply_plan(plan_path, require_ready_to_apply=True)

    assert verification["ok"] is False
    assert verification["ready_to_apply"] is False
    assert "provider apply plan must be ready_to_apply" in verification["failures"]
    assert verification["summary"]["provider_failure_count"] == 1
    assert "provider template has blank values" in verification["providers"][0]["failures"]


def test_external_gate_handoff_provider_apply_plan_verifier_accepts_ready_private_templates_without_leaking_values(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")
    plan_path = tmp_path / "apply-plan.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)

    verification = external_gate_handoff.verify_provider_apply_plan(plan_path, require_ready_to_apply=True)
    serialized = json.dumps(verification)

    assert verification["ok"] is True
    assert verification["ready_to_apply"] is True
    assert verification["operator_stage"] == "apply_provider_values"
    assert verification["summary"]["ready_provider_count"] == 1
    assert verification["summary"]["blocked_provider_count"] == 0
    assert "super-secret" not in serialized
    assert "jwt-secret" not in serialized


def test_external_gate_handoff_provider_apply_plan_verifier_detects_template_drift(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    plan_path = tmp_path / "apply-plan.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")

    verification = external_gate_handoff.verify_provider_apply_plan(plan_path)

    assert verification["ok"] is False
    assert verification["summary"]["provider_failure_count"] == 1
    assert "provider template populated_key_count does not match apply plan" in verification["providers"][0]["failures"]


def test_external_gate_handoff_provider_apply_results_template_is_redacted(tmp_path: Path) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")
    plan_path = tmp_path / "apply-plan.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    template = external_gate_handoff.provider_apply_results_template_payload(plan, plan_path=plan_path)
    serialized = json.dumps(template)

    assert template["ok"] is False
    assert template["provider_apply_plan_json"] == str(plan_path)
    assert template["command_count"] == 2
    assert {item["status"] for item in template["results"]} == {"pending"}
    assert {item["exit_code"] for item in template["results"]} == {None}
    assert "super-secret" not in serialized
    assert "jwt-secret" not in serialized


def test_external_gate_handoff_provider_apply_results_verifier_accepts_successful_redacted_results(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")
    plan_path = tmp_path / "apply-plan.json"
    results_path = tmp_path / "apply-results.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    template = external_gate_handoff.provider_apply_results_template_payload(plan, plan_path=plan_path)
    for item in template["results"]:
        item["status"] = "success"
        item["exit_code"] = 0
        item["stdout_excerpt"] = "applied"
    template["ok"] = True
    results_path.write_text(json.dumps(template), encoding="utf-8")

    verification = external_gate_handoff.verify_provider_apply_results(results_path, plan_path=plan_path)
    serialized = json.dumps(verification)

    assert verification["ok"] is True
    assert verification["all_commands_succeeded"] is True
    assert verification["summary"]["command_failure_count"] == 0
    assert verification["summary"]["missing_command_count"] == 0
    assert "super-secret" not in serialized
    assert "jwt-secret" not in serialized


def test_external_gate_handoff_provider_apply_results_verifier_accepts_powershell_bom_and_path_separators(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")
    plan_path = tmp_path / "apply-plan.json"
    results_path = tmp_path / "apply-results.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    template = external_gate_handoff.provider_apply_results_template_payload(plan, plan_path=plan_path)
    template["provider_apply_plan_json"] = str(plan_path).replace("\\", "/")
    for item in template["results"]:
        item["status"] = "success"
        item["exit_code"] = 0
    results_path.write_text(json.dumps(template), encoding="utf-8-sig")

    verification = external_gate_handoff.verify_provider_apply_results(results_path, plan_path=plan_path)

    assert verification["ok"] is True
    assert verification["all_commands_succeeded"] is True


def test_external_gate_handoff_provider_apply_results_verifier_blocks_failed_or_missing_results(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")
    plan_path = tmp_path / "apply-plan.json"
    results_path = tmp_path / "apply-results.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    template = external_gate_handoff.provider_apply_results_template_payload(plan, plan_path=plan_path)
    template["results"] = template["results"][:1]
    template["results"][0]["status"] = "failure"
    template["results"][0]["exit_code"] = 1
    template["ok"] = False
    results_path.write_text(json.dumps(template), encoding="utf-8")

    verification = external_gate_handoff.verify_provider_apply_results(results_path, plan_path=plan_path)

    assert verification["ok"] is False
    assert verification["all_commands_succeeded"] is False
    assert "provider apply results are missing expected commands" in verification["failures"]
    assert verification["summary"]["missing_command_count"] == 1
    assert verification["summary"]["command_failure_count"] == 2


def test_external_gate_handoff_provider_apply_results_verifier_blocks_secret_shaped_output(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")
    plan_path = tmp_path / "apply-plan.json"
    results_path = tmp_path / "apply-results.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    template = external_gate_handoff.provider_apply_results_template_payload(plan, plan_path=plan_path)
    for item in template["results"]:
        item["status"] = "success"
        item["exit_code"] = 0
    template["results"][0]["stderr_excerpt"] = "token=ghp_abc123"
    results_path.write_text(json.dumps(template), encoding="utf-8")

    verification = external_gate_handoff.verify_provider_apply_results(results_path, plan_path=plan_path)

    assert verification["ok"] is False
    assert verification["summary"]["secret_marker_count"] >= 1
    assert "provider apply results contain secret-shaped markers" in verification["failures"]
    assert "provider command stderr_excerpt contains secret-shaped markers" in verification["commands"][0]["failures"]


def test_external_gate_handoff_provider_apply_commands_are_shell_specific() -> None:
    github = external_gate_handoff._provider_apply_commands("github", "var/providers/github.env", ["GITLEAKS_LICENSE"])
    vercel = external_gate_handoff._provider_apply_commands("vercel", "var/providers/vercel.env", ["VITE_API_BASE_URL"])

    assert github[0]["powershell_command"] == "gh secret set --env-file 'var/providers/github.env'"
    assert github[0]["posix_command"] == "gh secret set --env-file var/providers/github.env"
    assert (
        vercel[0]["powershell_command"]
        == "Get-Content -Raw '<private-values/VITE_API_BASE_URL.txt>' | vercel env add VITE_API_BASE_URL production"
    )
    assert vercel[0]["posix_command"] == "vercel env add VITE_API_BASE_URL production < <private-values/VITE_API_BASE_URL.txt>"
    assert "VITE_API_BASE_URL=" not in json.dumps(vercel)


def test_external_gate_handoff_cli_requires_template_dir_for_index(capsys) -> None:
    rc = external_gate_handoff.main(
        [
            "--external-gate-json",
            "missing.json",
            "--provider-template-index-out",
            "index.json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "require --provider-template-dir" in captured.err


def test_external_gate_handoff_cli_verifies_provider_apply_plan_and_can_require_ready(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    plan_path = tmp_path / "apply-plan.json"
    verify_path = tmp_path / "apply-plan-verify.json"
    require_ready_path = tmp_path / "apply-plan-require-ready.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)

    rc = external_gate_handoff.main(
        [
            "--verify-provider-apply-plan",
            str(plan_path),
            "--json-out",
            str(verify_path),
        ]
    )
    require_ready_rc = external_gate_handoff.main(
        [
            "--verify-provider-apply-plan",
            str(plan_path),
            "--require-ready-to-apply",
            "--json-out",
            str(require_ready_path),
        ]
    )

    verification = json.loads(verify_path.read_text(encoding="utf-8"))
    require_ready = json.loads(require_ready_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert verification["ok"] is True
    assert verification["ready_to_apply"] is False
    assert require_ready_rc == 1
    assert require_ready["ok"] is False
    assert "provider apply plan must be ready_to_apply" in require_ready["failures"]


def test_external_gate_handoff_cli_writes_and_verifies_provider_apply_results_template(
    tmp_path: Path,
) -> None:
    payload = external_gate_handoff.build_handoff_payload(gate_payload(), evidence_path="var/gate.json")
    paths = external_gate_handoff.write_provider_templates(tmp_path / "providers", payload)
    paths["railway"].write_text("FIREBASE_SERVICE_ACCOUNT_JSON=super-secret\nPINATA_JWT=jwt-secret\n", encoding="utf-8")
    plan_path = tmp_path / "apply-plan.json"
    template_path = tmp_path / "apply-results-template.json"
    verify_path = tmp_path / "apply-results-verify.json"
    external_gate_handoff.write_provider_apply_plan(plan_path, payload, paths)

    template_rc = external_gate_handoff.main(
        [
            "--provider-apply-results-template-from-plan",
            str(plan_path),
            "--json-out",
            str(template_path),
        ]
    )
    template = json.loads(template_path.read_text(encoding="utf-8"))
    for item in template["results"]:
        item["status"] = "success"
        item["exit_code"] = 0
        item["stdout_excerpt"] = "applied"
    template["ok"] = True
    template_path.write_text(json.dumps(template), encoding="utf-8")
    verify_rc = external_gate_handoff.main(
        [
            "--verify-provider-apply-results",
            str(template_path),
            "--provider-apply-plan",
            str(plan_path),
            "--json-out",
            str(verify_path),
        ]
    )

    verification = json.loads(verify_path.read_text(encoding="utf-8"))
    assert template_rc == 0
    assert verify_rc == 0
    assert verification["ok"] is True
    assert verification["all_commands_succeeded"] is True


def test_external_gate_handoff_cli_requires_plan_for_apply_results(capsys) -> None:
    rc = external_gate_handoff.main(["--verify-provider-apply-results", "results.json"])
    captured = capsys.readouterr()

    assert rc == 2
    assert "requires --provider-apply-plan" in captured.err


def test_external_gate_handoff_cli_rejects_require_ready_without_apply_plan(capsys) -> None:
    rc = external_gate_handoff.main(["--require-ready-to-apply"])
    captured = capsys.readouterr()

    assert rc == 2
    assert "requires --verify-provider-apply-plan" in captured.err


def test_external_gate_handoff_load_rejects_non_gate_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 1, "ok": True}), encoding="utf-8")

    with pytest.raises(ValueError, match="child evidence"):
        external_gate_handoff.load_external_gate_payload(path)
