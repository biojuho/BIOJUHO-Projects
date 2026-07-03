from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import post_apply_evidence_gate  # noqa: E402


def external_gate_payload(*, ok: bool = True) -> dict[str, object]:
    return {
        "schema_version": 1,
        "ok": ok,
        "targets": ["railway", "vercel", "amoy", "github"],
        "provider_targets": ["railway", "vercel", "github"],
        "failed_surfaces": [] if ok else ["provider_preflight"],
        "summary": {
            "deploy_failed": 0,
            "deploy_warnings": 0,
            "provider_ready": 3 if ok else 2,
            "provider_count": 3,
            "provider_failed_checks": 0 if ok else 1,
            "failed_surface_count": 0 if ok else 1,
        },
        "deploy_readiness": {"ok": True},
        "provider_preflight": {"ok": ok},
    }


def test_post_apply_evidence_gate_accepts_ready_external_gate() -> None:
    payload = post_apply_evidence_gate.validate_post_apply_payload(
        external_gate_payload(),
        evidence_path="var/external-release-gate-post-apply-all.json",
    )

    assert payload["ok"] is True
    assert payload["summary"]["failure_count"] == 0
    assert payload["summary"]["provider_ready"] == 3
    assert payload["summary"]["provider_count"] == 3
    assert payload["failures"] == []


def test_post_apply_evidence_gate_fails_closed_for_incomplete_provider_evidence() -> None:
    payload = post_apply_evidence_gate.validate_post_apply_payload(
        external_gate_payload(ok=False),
        evidence_path="var/external-release-gate-post-apply-all.json",
    )

    assert payload["ok"] is False
    assert payload["summary"]["provider_failed_checks"] == 1
    assert "external gate ok must be true" in payload["failures"]
    assert "provider_preflight.ok must be true" in payload["failures"]
    assert "summary.provider_ready must equal summary.provider_count" in payload["failures"]


def test_post_apply_evidence_gate_fails_closed_for_secret_shaped_evidence() -> None:
    source = external_gate_payload()
    source["debug"] = "token=ghp_abc123"

    payload = post_apply_evidence_gate.validate_post_apply_payload(
        source,
        evidence_path="var/external-release-gate-post-apply-all.json",
    )

    assert payload["ok"] is False
    assert payload["summary"]["secret_marker_count"] >= 1
    assert "github_token" in payload["secret_marker_names"]
    assert "external gate evidence contains secret-shaped markers" in payload["failures"]


def test_post_apply_evidence_gate_writes_json_report_atomically(tmp_path: Path) -> None:
    output = tmp_path / "post-apply-gate.json"
    payload = post_apply_evidence_gate.validate_post_apply_payload(
        external_gate_payload(),
        evidence_path="var/external-release-gate-post-apply-all.json",
    )

    post_apply_evidence_gate.write_json_report(output, payload)

    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert written["ok"] is True
    assert not (tmp_path / "post-apply-gate.json.tmp").exists()


def test_post_apply_evidence_gate_cli_reports_missing_json(tmp_path: Path) -> None:
    output = tmp_path / "gate.json"
    missing = tmp_path / "missing.json"

    rc = post_apply_evidence_gate.main(
        [
            "--external-gate-json",
            str(missing),
            "--json-out",
            str(output),
        ]
    )

    written = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 1
    assert written["ok"] is False
    assert written["summary"]["failure_count"] == 1
