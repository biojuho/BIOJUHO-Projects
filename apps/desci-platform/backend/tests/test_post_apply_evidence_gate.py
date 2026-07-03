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


def test_post_apply_evidence_manifest_records_gate_and_report_hashes(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    source = external_gate_payload()
    external_path.write_text(json.dumps(source), encoding="utf-8")
    payload = post_apply_evidence_gate.validate_post_apply_payload(source, evidence_path=external_path)
    post_apply_evidence_gate.write_json_report(report_path, payload)

    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=external_path,
        gate_payload=payload,
        gate_report_path=report_path,
    )
    artifacts = {item["role"]: item for item in manifest["artifacts"]}

    assert manifest["ok"] is True
    assert manifest["promotion_gate"]["ok"] is True
    assert manifest["artifact_count"] == 2
    assert manifest["missing_required_count"] == 0
    assert manifest["secret_marker_count"] == 0
    assert set(artifacts) == {"external_gate_json", "post_apply_evidence_gate_json"}
    assert artifacts["external_gate_json"]["exists"] is True
    assert artifacts["external_gate_json"]["bytes"] > 0
    assert len(artifacts["external_gate_json"]["sha256"]) == 64
    assert artifacts["post_apply_evidence_gate_json"]["exists"] is True
    assert len(artifacts["post_apply_evidence_gate_json"]["sha256"]) == 64


def test_post_apply_evidence_manifest_fails_for_missing_or_secret_artifacts(tmp_path: Path) -> None:
    unsafe_log = tmp_path / "unsafe.log"
    unsafe_log.write_text("token=ghp_abc123", encoding="utf-8")

    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=tmp_path / "missing-external-gate.json",
        gate_payload={"ok": True},
        extra_artifacts=[{"path": unsafe_log, "role": "operator_log"}],
    )
    artifacts = {item["role"]: item for item in manifest["artifacts"]}

    assert manifest["ok"] is False
    assert manifest["missing_required_count"] == 1
    assert manifest["secret_marker_count"] >= 1
    assert artifacts["external_gate_json"]["exists"] is False
    assert artifacts["operator_log"]["ok"] is False
    assert "github_token" in artifacts["operator_log"]["secret_marker_names"]


def test_post_apply_evidence_gate_cli_writes_report_and_manifest(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    external_path.write_text(json.dumps(external_gate_payload()), encoding="utf-8")

    rc = post_apply_evidence_gate.main(
        [
            "--external-gate-json",
            str(external_path),
            "--json-out",
            str(report_path),
            "--manifest-out",
            str(manifest_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    roles = {item["role"] for item in manifest["artifacts"]}
    assert rc == 0
    assert report["ok"] is True
    assert manifest["ok"] is True
    assert roles == {"external_gate_json", "post_apply_evidence_gate_json"}


def test_post_apply_evidence_gate_cli_writes_manifest_verification_in_one_promotion_command(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    verify_path = tmp_path / "post-apply-manifest-verify.json"
    external_path.write_text(json.dumps(external_gate_payload()), encoding="utf-8")

    rc = post_apply_evidence_gate.main(
        [
            "--external-gate-json",
            str(external_path),
            "--json-out",
            str(report_path),
            "--manifest-out",
            str(manifest_path),
            "--verify-manifest-out",
            str(verify_path),
        ]
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verification = json.loads(verify_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["ok"] is True
    assert manifest["ok"] is True
    assert verification["ok"] is True
    assert verification["manifest_json"] == str(manifest_path)
    assert verification["summary"]["digest_mismatch_count"] == 0


def test_post_apply_promotion_receipt_accepts_complete_ready_evidence(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    verify_path = tmp_path / "post-apply-manifest-verify.json"
    source = external_gate_payload()
    external_path.write_text(json.dumps(source), encoding="utf-8")
    payload = post_apply_evidence_gate.validate_post_apply_payload(source, evidence_path=external_path)
    post_apply_evidence_gate.write_json_report(report_path, payload)
    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=external_path,
        gate_payload=payload,
        gate_report_path=report_path,
    )
    post_apply_evidence_gate.write_json_report(manifest_path, manifest)
    verification = post_apply_evidence_gate.verify_evidence_manifest(manifest_path)
    post_apply_evidence_gate.write_json_report(verify_path, verification)

    receipt = post_apply_evidence_gate.build_promotion_receipt(
        gate_payload=payload,
        external_gate_path=external_path,
        gate_report_path=report_path,
        manifest_payload=manifest,
        manifest_path=manifest_path,
        verification_payload=verification,
        verification_path=verify_path,
    )

    assert receipt["ok"] is True
    assert receipt["release_decision"] == "go"
    assert receipt["operator_phase"] == "post_apply_launch_ready"
    assert receipt["checks"] == {
        "post_apply_evidence_gate": True,
        "evidence_manifest": True,
        "evidence_manifest_verification": True,
    }
    assert receipt["post_apply_evidence_gate_json"] == str(report_path)
    assert receipt["evidence_manifest_json"] == str(manifest_path)
    assert receipt["evidence_manifest_verification_json"] == str(verify_path)
    assert receipt["summary"]["manifest_artifact_count"] == 2
    assert receipt["blocking_reasons"] == []


def test_post_apply_promotion_receipt_blocks_no_go_without_artifact_failures(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    verify_path = tmp_path / "post-apply-manifest-verify.json"
    source = external_gate_payload(ok=False)
    external_path.write_text(json.dumps(source), encoding="utf-8")
    payload = post_apply_evidence_gate.validate_post_apply_payload(source, evidence_path=external_path)
    post_apply_evidence_gate.write_json_report(report_path, payload)
    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=external_path,
        gate_payload=payload,
        gate_report_path=report_path,
    )
    post_apply_evidence_gate.write_json_report(manifest_path, manifest)
    verification = post_apply_evidence_gate.verify_evidence_manifest(manifest_path)
    post_apply_evidence_gate.write_json_report(verify_path, verification)

    receipt = post_apply_evidence_gate.build_promotion_receipt(
        gate_payload=payload,
        external_gate_path=external_path,
        gate_report_path=report_path,
        manifest_payload=manifest,
        manifest_path=manifest_path,
        verification_payload=verification,
        verification_path=verify_path,
    )

    assert receipt["ok"] is False
    assert receipt["release_decision"] == "no-go"
    assert receipt["operator_phase"] == "post_apply_launch_blocked"
    assert receipt["checks"] == {
        "post_apply_evidence_gate": False,
        "evidence_manifest": False,
        "evidence_manifest_verification": False,
    }
    assert receipt["summary"]["verification_artifact_failure_count"] == 0
    assert receipt["summary"]["verification_digest_mismatch_count"] == 0
    assert receipt["summary"]["verification_secret_marker_count"] == 0
    assert "external gate ok must be true" in receipt["blocking_reasons"]
    assert "evidence_manifest.ok must be true" in receipt["blocking_reasons"]


def test_post_apply_evidence_gate_cli_writes_complete_promotion_receipt(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    verify_path = tmp_path / "post-apply-manifest-verify.json"
    receipt_path = tmp_path / "post-apply-promotion-receipt.json"
    external_path.write_text(json.dumps(external_gate_payload()), encoding="utf-8")

    rc = post_apply_evidence_gate.main(
        [
            "--external-gate-json",
            str(external_path),
            "--json-out",
            str(report_path),
            "--manifest-out",
            str(manifest_path),
            "--verify-manifest-out",
            str(verify_path),
            "--promotion-receipt-out",
            str(receipt_path),
        ]
    )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert receipt["ok"] is True
    assert receipt["release_decision"] == "go"
    assert receipt["checks"]["post_apply_evidence_gate"] is True
    assert receipt["checks"]["evidence_manifest"] is True
    assert receipt["checks"]["evidence_manifest_verification"] is True
    assert receipt["summary"]["blocking_reason_count"] == 0


def test_post_apply_evidence_gate_cli_requires_all_outputs_for_promotion_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    external_path = tmp_path / "external-gate.json"
    external_path.write_text(json.dumps(external_gate_payload()), encoding="utf-8")

    rc = post_apply_evidence_gate.main(
        [
            "--external-gate-json",
            str(external_path),
            "--json-out",
            str(tmp_path / "post-apply-gate.json"),
            "--promotion-receipt-out",
            str(tmp_path / "post-apply-promotion-receipt.json"),
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "requires --json-out, --manifest-out, and --verify-manifest-out" in captured.err


def test_post_apply_evidence_gate_cli_requires_manifest_for_inline_verification(
    tmp_path: Path,
    capsys,
) -> None:
    external_path = tmp_path / "external-gate.json"
    external_path.write_text(json.dumps(external_gate_payload()), encoding="utf-8")

    rc = post_apply_evidence_gate.main(
        [
            "--external-gate-json",
            str(external_path),
            "--verify-manifest-out",
            str(tmp_path / "post-apply-manifest-verify.json"),
        ]
    )
    captured = capsys.readouterr()

    assert rc == 2
    assert "requires --manifest-out" in captured.err


def test_post_apply_evidence_manifest_verifier_accepts_intact_artifacts(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    source = external_gate_payload()
    external_path.write_text(json.dumps(source), encoding="utf-8")
    payload = post_apply_evidence_gate.validate_post_apply_payload(source, evidence_path=external_path)
    post_apply_evidence_gate.write_json_report(report_path, payload)
    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=external_path,
        gate_payload=payload,
        gate_report_path=report_path,
    )
    post_apply_evidence_gate.write_json_report(manifest_path, manifest)

    verification = post_apply_evidence_gate.verify_evidence_manifest(manifest_path)

    assert verification["ok"] is True
    assert verification["manifest_ok"] is True
    assert verification["promotion_gate_ok"] is True
    assert verification["summary"]["checked_artifact_count"] == 2
    assert verification["summary"]["artifact_failure_count"] == 0
    assert verification["summary"]["digest_mismatch_count"] == 0
    assert verification["summary"]["secret_marker_count"] == 0


def test_post_apply_evidence_manifest_verifier_fails_for_tampered_artifact(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    source = external_gate_payload()
    external_path.write_text(json.dumps(source), encoding="utf-8")
    payload = post_apply_evidence_gate.validate_post_apply_payload(source, evidence_path=external_path)
    post_apply_evidence_gate.write_json_report(report_path, payload)
    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=external_path,
        gate_payload=payload,
        gate_report_path=report_path,
    )
    post_apply_evidence_gate.write_json_report(manifest_path, manifest)
    external_path.write_text(json.dumps({**source, "debug": "tampered"}), encoding="utf-8")

    verification = post_apply_evidence_gate.verify_evidence_manifest(manifest_path)
    external_artifact = next(item for item in verification["artifacts"] if item["role"] == "external_gate_json")

    assert verification["ok"] is False
    assert verification["summary"]["artifact_failure_count"] == 1
    assert verification["summary"]["digest_mismatch_count"] == 1
    assert "artifact sha256 mismatch" in external_artifact["failures"]


def test_post_apply_evidence_manifest_verifier_fails_for_malformed_artifact_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "post-apply-manifest.json"
    post_apply_evidence_gate.write_json_report(
        manifest_path,
        {
            "schema_version": 1,
            "ok": True,
            "promotion_gate": {"ok": True},
            "artifact_count": 1,
            "artifacts": [
                {
                    "role": "external_gate_json",
                    "path": "",
                    "required": True,
                    "exists": True,
                    "bytes": 1,
                    "sha256": "0" * 64,
                    "secret_marker_count": 0,
                    "ok": True,
                }
            ],
        },
    )

    verification = post_apply_evidence_gate.verify_evidence_manifest(manifest_path)
    artifact = verification["artifacts"][0]

    assert verification["ok"] is False
    assert artifact["ok"] is False
    assert "artifact path is required" in artifact["failures"]
    assert "required artifact is missing" in artifact["failures"]


def test_post_apply_evidence_manifest_verifier_keeps_no_go_manifest_blocked(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    source = external_gate_payload(ok=False)
    external_path.write_text(json.dumps(source), encoding="utf-8")
    payload = post_apply_evidence_gate.validate_post_apply_payload(source, evidence_path=external_path)
    post_apply_evidence_gate.write_json_report(report_path, payload)
    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=external_path,
        gate_payload=payload,
        gate_report_path=report_path,
    )
    post_apply_evidence_gate.write_json_report(manifest_path, manifest)

    verification = post_apply_evidence_gate.verify_evidence_manifest(manifest_path)

    assert manifest["ok"] is False
    assert verification["ok"] is False
    assert verification["summary"]["artifact_failure_count"] == 0
    assert "evidence manifest ok must be true" in verification["failures"]
    assert "promotion gate ok must be true" in verification["failures"]


def test_post_apply_evidence_gate_cli_verifies_manifest(tmp_path: Path) -> None:
    external_path = tmp_path / "external-gate.json"
    report_path = tmp_path / "post-apply-gate.json"
    manifest_path = tmp_path / "post-apply-manifest.json"
    verify_path = tmp_path / "post-apply-manifest-verify.json"
    source = external_gate_payload()
    external_path.write_text(json.dumps(source), encoding="utf-8")
    payload = post_apply_evidence_gate.validate_post_apply_payload(source, evidence_path=external_path)
    post_apply_evidence_gate.write_json_report(report_path, payload)
    manifest = post_apply_evidence_gate.build_evidence_manifest(
        external_gate_path=external_path,
        gate_payload=payload,
        gate_report_path=report_path,
    )
    post_apply_evidence_gate.write_json_report(manifest_path, manifest)

    rc = post_apply_evidence_gate.main(
        [
            "--verify-manifest",
            str(manifest_path),
            "--json-out",
            str(verify_path),
        ]
    )

    written = json.loads(verify_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert written["ok"] is True
    assert written["summary"]["digest_mismatch_count"] == 0


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
