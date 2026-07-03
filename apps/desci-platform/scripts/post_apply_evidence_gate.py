#!/usr/bin/env python3
"""Validate DeSci post-apply external release gate evidence before launch promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evidence_io import write_json_atomic

SECRET_PATTERNS = {
    "stripe_secret_key": re.compile(r"sk_(?:live|test)_[A-Za-z0-9_/-]+"),
    "stripe_webhook_secret": re.compile(r"whsec_[A-Za-z0-9_/-]+"),
    "github_token": re.compile(r"(?:github_pat|gh[pousr])_[A-Za-z0-9_/-]+"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]+"),
    "private_assignment": re.compile(r"(?i)(token|secret|password|private[_-]?key)\s*[:=]\s*\S+"),
    "credential_url": re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|redis|amqp)://[^@\s\"']+:[^@\s\"']+@"),
}


def secret_marker_names_in_text(serialized: str) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(serialized)]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_external_gate_payload(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def secret_marker_names(payload: dict[str, Any]) -> list[str]:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return secret_marker_names_in_text(serialized)


def validate_post_apply_payload(payload: dict[str, Any], *, evidence_path: str | Path) -> dict[str, Any]:
    summary = _as_dict(payload.get("summary"))
    deploy_payload = _as_dict(payload.get("deploy_readiness"))
    provider_payload = _as_dict(payload.get("provider_preflight"))
    markers = secret_marker_names(payload)
    failures: list[str] = []

    if payload.get("schema_version") != 1:
        failures.append("external gate evidence must be schema_version=1")
    if payload.get("ok") is not True:
        failures.append("external gate ok must be true")
    if _as_list(payload.get("failed_surfaces")):
        failures.append("external gate failed_surfaces must be empty")
    if int(summary.get("deploy_failed") or 0) != 0:
        failures.append("summary.deploy_failed must be 0")
    if int(summary.get("provider_failed_checks") or 0) != 0:
        failures.append("summary.provider_failed_checks must be 0")
    if int(summary.get("failed_surface_count") or 0) != 0:
        failures.append("summary.failed_surface_count must be 0")
    provider_count = int(summary.get("provider_count") or 0)
    provider_ready = int(summary.get("provider_ready") or 0)
    if provider_count <= 0:
        failures.append("summary.provider_count must be greater than 0 for aggregate post-apply evidence")
    if provider_ready != provider_count:
        failures.append("summary.provider_ready must equal summary.provider_count")
    if deploy_payload.get("ok") is not True:
        failures.append("deploy_readiness.ok must be true")
    if provider_payload.get("ok") is not True:
        failures.append("provider_preflight.ok must be true")
    if markers:
        failures.append("external gate evidence contains secret-shaped markers")

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not failures,
        "external_gate_json": str(evidence_path),
        "success_condition": "external_release_gate.ok=true",
        "summary": {
            "failure_count": len(failures),
            "deploy_failed": int(summary.get("deploy_failed") or 0),
            "provider_failed_checks": int(summary.get("provider_failed_checks") or 0),
            "failed_surface_count": int(summary.get("failed_surface_count") or 0),
            "provider_ready": provider_ready,
            "provider_count": provider_count,
            "secret_marker_count": len(markers),
        },
        "secret_marker_names": markers,
        "failures": failures,
    }


def write_json_report(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_json_atomic(path, payload, trailing_newline=True)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _file_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def evidence_artifact_entry(path: str | Path, *, role: str, required: bool = True) -> dict[str, Any]:
    artifact_path = Path(path)
    entry: dict[str, Any] = {
        "role": role,
        "path": str(path),
        "required": required,
        "exists": artifact_path.exists(),
        "bytes": 0,
        "sha256": "",
        "secret_marker_names": [],
        "secret_marker_count": 0,
        "read_error": "",
        "ok": False,
    }
    if not entry["exists"]:
        entry["ok"] = not required
        return entry

    try:
        raw = artifact_path.read_bytes()
    except OSError as exc:
        entry["read_error"] = str(exc)
        return entry
    markers = secret_marker_names_in_text(raw.decode("utf-8", errors="ignore"))
    entry.update(
        {
            "bytes": len(raw),
            "sha256": _file_sha256(raw),
            "secret_marker_names": markers,
            "secret_marker_count": len(markers),
            "ok": len(markers) == 0,
        }
    )
    return entry


def build_evidence_manifest(
    *,
    external_gate_path: str | Path,
    gate_payload: dict[str, Any],
    gate_report_path: str | Path | None = None,
    extra_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    artifacts = [
        evidence_artifact_entry(external_gate_path, role="external_gate_json"),
    ]
    if gate_report_path:
        artifacts.append(evidence_artifact_entry(gate_report_path, role="post_apply_evidence_gate_json"))
    for artifact in extra_artifacts or []:
        path = artifact.get("path")
        if not path:
            continue
        artifacts.append(
            evidence_artifact_entry(
                path,
                role=str(artifact.get("role") or "extra_artifact"),
                required=artifact.get("required") is not False,
            )
        )

    missing_required_count = sum(
        1 for item in artifacts if item.get("required") is True and item.get("exists") is not True
    )
    secret_marker_count = sum(int(item.get("secret_marker_count") or 0) for item in artifacts)
    failed_artifact_count = sum(1 for item in artifacts if item.get("ok") is not True)
    promotion_gate_ok = gate_payload.get("ok") is True
    ok = promotion_gate_ok and missing_required_count == 0 and secret_marker_count == 0 and failed_artifact_count == 0
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": ok,
        "success_condition": "post_apply_evidence_gate.ok=true and evidence_manifest.ok=true",
        "promotion_gate": {
            "condition": "post_apply_evidence_gate.ok=true",
            "ok": promotion_gate_ok,
            "external_gate_json": str(external_gate_path),
            "gate_report_json": str(gate_report_path or ""),
        },
        "artifact_count": len(artifacts),
        "missing_required_count": missing_required_count,
        "secret_marker_count": secret_marker_count,
        "failed_artifact_count": failed_artifact_count,
        "artifacts": artifacts,
    }


def load_evidence_manifest(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _resolve_manifest_artifact_path(path: str, artifact_root: str | Path) -> Path:
    artifact_path = Path(path)
    if artifact_path.is_absolute():
        return artifact_path
    return Path(artifact_root) / artifact_path


def _verify_manifest_artifact(artifact: dict[str, Any], *, artifact_root: str | Path) -> dict[str, Any]:
    role = str(artifact.get("role") or "")
    expected_path = str(artifact.get("path") or "")
    required = artifact.get("required") is not False
    resolved_path = _resolve_manifest_artifact_path(expected_path, artifact_root)
    current = (
        evidence_artifact_entry(resolved_path, role=role, required=required)
        if expected_path
        else evidence_artifact_entry("__missing_manifest_artifact_path__", role=role, required=required)
    )
    failures: list[str] = []

    expected_exists = artifact.get("exists") is True
    if not expected_path:
        failures.append("artifact path is required")
    if not role:
        failures.append("artifact role is required")
    if artifact.get("ok") is not True:
        failures.append("manifest artifact ok must be true")
    if artifact.get("secret_marker_count") not in {0, None}:
        failures.append("manifest artifact secret_marker_count must be 0")
    if expected_exists != current["exists"]:
        failures.append("artifact exists state changed")
    if required and current["exists"] is not True:
        failures.append("required artifact is missing")
    if current.get("read_error"):
        failures.append("artifact could not be read")
    if expected_exists and current["exists"]:
        if int(artifact.get("bytes") or 0) != int(current.get("bytes") or 0):
            failures.append("artifact byte size mismatch")
        if str(artifact.get("sha256") or "") != str(current.get("sha256") or ""):
            failures.append("artifact sha256 mismatch")
    if int(current.get("secret_marker_count") or 0) != 0:
        failures.append("artifact contains secret-shaped markers")

    return {
        "role": role,
        "path": expected_path,
        "resolved_path": str(resolved_path),
        "required": required,
        "ok": not failures,
        "expected_exists": expected_exists,
        "current_exists": current["exists"],
        "expected_bytes": int(artifact.get("bytes") or 0),
        "current_bytes": int(current.get("bytes") or 0),
        "expected_sha256": str(artifact.get("sha256") or ""),
        "current_sha256": str(current.get("sha256") or ""),
        "secret_marker_names": current.get("secret_marker_names") or [],
        "secret_marker_count": int(current.get("secret_marker_count") or 0),
        "failures": failures,
    }


def verify_evidence_manifest(
    manifest_path: str | Path,
    *,
    artifact_root: str | Path = ".",
) -> dict[str, Any]:
    manifest = load_evidence_manifest(manifest_path)
    artifacts = [item for item in _as_list(manifest.get("artifacts")) if isinstance(item, dict)]
    promotion_gate = _as_dict(manifest.get("promotion_gate"))
    checked_artifacts = [
        _verify_manifest_artifact(artifact, artifact_root=artifact_root)
        for artifact in artifacts
    ]
    failures: list[str] = []

    if manifest.get("schema_version") != 1:
        failures.append("evidence manifest must be schema_version=1")
    if manifest.get("ok") is not True:
        failures.append("evidence manifest ok must be true")
    if promotion_gate.get("ok") is not True:
        failures.append("promotion gate ok must be true")
    if int(manifest.get("artifact_count") or 0) != len(artifacts):
        failures.append("manifest artifact_count must match artifacts length")

    artifact_failure_count = sum(1 for item in checked_artifacts if item.get("ok") is not True)
    missing_required_count = sum(
        1 for item in checked_artifacts if item.get("required") is True and item.get("current_exists") is not True
    )
    digest_mismatch_count = sum(
        1 for item in checked_artifacts if "artifact sha256 mismatch" in _as_list(item.get("failures"))
    )
    secret_marker_count = sum(int(item.get("secret_marker_count") or 0) for item in checked_artifacts)

    return {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "ok": not failures and artifact_failure_count == 0,
        "manifest_json": str(manifest_path),
        "artifact_root": str(artifact_root),
        "manifest_ok": manifest.get("ok") is True,
        "promotion_gate_ok": promotion_gate.get("ok") is True,
        "summary": {
            "failure_count": len(failures),
            "artifact_count": len(artifacts),
            "checked_artifact_count": len(checked_artifacts),
            "artifact_failure_count": artifact_failure_count,
            "missing_required_count": missing_required_count,
            "digest_mismatch_count": digest_mismatch_count,
            "secret_marker_count": secret_marker_count,
        },
        "failures": failures,
        "artifacts": checked_artifacts,
    }


def print_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[post-apply-evidence-gate] ok={payload.get('ok')}")
    print(
        "[post-apply-evidence-gate] "
        f"failures={summary.get('failure_count')} "
        f"provider_ready={summary.get('provider_ready')}/{summary.get('provider_count')} "
        f"deploy_failed={summary.get('deploy_failed')} "
        f"provider_failed_checks={summary.get('provider_failed_checks')}"
    )
    for failure in _as_list(payload.get("failures")):
        print(f"  - {failure}")


def print_manifest_verification_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[post-apply-evidence-manifest] ok={payload.get('ok')}")
    print(
        "[post-apply-evidence-manifest] "
        f"manifest_ok={payload.get('manifest_ok')} "
        f"promotion_gate_ok={payload.get('promotion_gate_ok')} "
        f"artifact_failures={summary.get('artifact_failure_count')} "
        f"digest_mismatches={summary.get('digest_mismatch_count')} "
        f"missing_required={summary.get('missing_required_count')} "
        f"secret_markers={summary.get('secret_marker_count')}"
    )
    for failure in _as_list(payload.get("failures")):
        print(f"  - {failure}")
    for artifact in _as_list(payload.get("artifacts")):
        if isinstance(artifact, dict) and artifact.get("ok") is not True:
            role = artifact.get("role") or "artifact"
            for failure in _as_list(artifact.get("failures")):
                print(f"  - {role}: {failure}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DeSci post-apply external gate JSON evidence.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--external-gate-json", help="Path to external_release_gate.py JSON evidence.")
    source.add_argument("--verify-manifest", help="Path to a post-apply evidence manifest to verify.")
    parser.add_argument("--artifact-root", default=".", help="Root used to resolve relative artifact paths in verify mode.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation JSON.")
    parser.add_argument("--json-out", help="Write machine-readable validation JSON.")
    parser.add_argument("--manifest-out", help="Write a hash manifest for the post-apply evidence artifacts.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.verify_manifest:
        try:
            verification = verify_evidence_manifest(args.verify_manifest, artifact_root=args.artifact_root)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            verification = {
                "schema_version": 1,
                "generated_at": _utc_now(),
                "ok": False,
                "manifest_json": str(args.verify_manifest),
                "artifact_root": str(args.artifact_root),
                "manifest_ok": False,
                "promotion_gate_ok": False,
                "summary": {
                    "failure_count": 1,
                    "artifact_count": 0,
                    "checked_artifact_count": 0,
                    "artifact_failure_count": 0,
                    "missing_required_count": 0,
                    "digest_mismatch_count": 0,
                    "secret_marker_count": 0,
                },
                "failures": [str(exc)],
                "artifacts": [],
            }
        if args.json:
            print(json.dumps(verification, indent=2))
        else:
            print_manifest_verification_report(verification)
        if args.json_out:
            write_json_report(args.json_out, verification)
            print(f"[post-apply-evidence-manifest] json written: {args.json_out}")
        return 0 if verification["ok"] else 1

    evidence_path = Path(args.external_gate_json)
    try:
        payload = validate_post_apply_payload(load_external_gate_payload(evidence_path), evidence_path=evidence_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "ok": False,
            "external_gate_json": str(evidence_path),
            "success_condition": "external_release_gate.ok=true",
            "summary": {
                "failure_count": 1,
                "deploy_failed": 0,
                "provider_failed_checks": 0,
                "failed_surface_count": 0,
                "provider_ready": 0,
                "provider_count": 0,
                "secret_marker_count": 0,
            },
            "secret_marker_names": [],
            "failures": [str(exc)],
        }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_report(payload)
    if args.json_out:
        write_json_report(args.json_out, payload)
        print(f"[post-apply-evidence-gate] json written: {args.json_out}")
    manifest: dict[str, Any] | None = None
    if args.manifest_out:
        manifest = build_evidence_manifest(
            external_gate_path=evidence_path,
            gate_payload=payload,
            gate_report_path=args.json_out,
        )
        write_json_report(args.manifest_out, manifest)
        print(f"[post-apply-evidence-gate] manifest written: {args.manifest_out}")
    return 0 if payload["ok"] and (manifest is None or manifest["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())
