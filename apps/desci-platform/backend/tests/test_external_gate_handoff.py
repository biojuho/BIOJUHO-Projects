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
    assert railway["required_env"] == ["FIREBASE_SERVICE_ACCOUNT_JSON", "PINATA_JWT"]
    assert vercel["failed"] == 2
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


def test_external_gate_handoff_load_rejects_non_gate_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 1, "ok": True}), encoding="utf-8")

    with pytest.raises(ValueError, match="child evidence"):
        external_gate_handoff.load_external_gate_payload(path)
