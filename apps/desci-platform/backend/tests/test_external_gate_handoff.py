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
    assert provider["blank_key_count"] == 2
    assert provider["commands"][0]["command"] == "railway variable set FIREBASE_SERVICE_ACCOUNT_JSON --stdin"
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
    assert plan["providers"][0]["ready_to_apply"] is True
    assert plan["providers"][0]["blank_key_count"] == 0
    assert "super-secret" not in serialized
    assert "jwt-secret" not in serialized


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


def test_external_gate_handoff_load_rejects_non_gate_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 1, "ok": True}), encoding="utf-8")

    with pytest.raises(ValueError, match="child evidence"):
        external_gate_handoff.load_external_gate_payload(path)
