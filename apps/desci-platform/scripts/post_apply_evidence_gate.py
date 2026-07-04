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
    "private_assignment": re.compile(
        r"(?im)^[^\S\r\n]*(?!#).*?(token|secret|password|private[_-]?key)"
        r"[^\S\r\n]*[:=][^\S\r\n]*[^\s\"']+"
    ),
    "credential_url": re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|redis|amqp)://[^@\s\"']+:[^@\s\"']+@"),
}

PROMOTION_RECEIPT_SUCCESS_CONDITION = (
    "post_apply_evidence_gate.ok=true and evidence_manifest.ok=true and "
    "evidence_manifest_verification.ok=true"
)
PROMOTION_RECEIPT_CHECK_KEYS = (
    "post_apply_evidence_gate",
    "evidence_manifest",
    "evidence_manifest_verification",
)
PROMOTION_RECEIPT_ARTIFACT_FIELDS = (
    ("external_gate_json", "external_gate_json"),
    ("post_apply_evidence_gate_json", "post_apply_evidence_gate_json"),
    ("evidence_manifest_json", "evidence_manifest_json"),
    ("evidence_manifest_verification_json", "evidence_manifest_verification_json"),
)


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


def _provider_blockers(provider_payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for check in _as_list(provider_payload.get("failed_checks")):
        if not isinstance(check, dict):
            continue
        blockers.append(
            {
                "provider": str(check.get("provider") or "").strip().lower(),
                "id": str(check.get("id") or ""),
                "command": str(check.get("command") or "").strip(),
                "failure_reason": str(check.get("failure_reason") or "unknown"),
                "docs_url": str(check.get("docs_url") or "").strip(),
                "remediation": str(check.get("remediation") or "").strip(),
                "project_context_missing": check.get("project_context_missing") is True,
            }
        )
    return blockers


def validate_post_apply_payload(payload: dict[str, Any], *, evidence_path: str | Path) -> dict[str, Any]:
    summary = _as_dict(payload.get("summary"))
    deploy_payload = _as_dict(payload.get("deploy_readiness"))
    provider_payload = _as_dict(payload.get("provider_preflight"))
    markers = secret_marker_names(payload)
    provider_blockers = _provider_blockers(provider_payload)
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
    provider_missing_cli_count = int(summary.get("provider_missing_cli_count") or 0)
    provider_auth_context_missing_count = int(summary.get("provider_auth_context_missing_count") or 0)
    provider_project_context_missing_count = int(summary.get("provider_project_context_missing_count") or 0)
    if provider_missing_cli_count != 0:
        failures.append("summary.provider_missing_cli_count must be 0")
    if provider_auth_context_missing_count != 0:
        failures.append("summary.provider_auth_context_missing_count must be 0")
    if provider_project_context_missing_count != 0:
        failures.append("summary.provider_project_context_missing_count must be 0")
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
            "provider_check_count": int(summary.get("provider_check_count") or 0),
            "provider_missing_cli_count": provider_missing_cli_count,
            "provider_auth_context_missing_count": provider_auth_context_missing_count,
            "provider_project_context_missing_count": provider_project_context_missing_count,
            "provider_blocker_count": len(provider_blockers),
            "failed_surface_count": int(summary.get("failed_surface_count") or 0),
            "provider_ready": provider_ready,
            "provider_count": provider_count,
            "secret_marker_count": len(markers),
        },
        "secret_marker_names": markers,
        "provider_blockers": provider_blockers,
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


def load_promotion_receipt(path: str | Path) -> dict[str, Any]:
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


def _verify_receipt_artifact(
    receipt: dict[str, Any],
    *,
    role: str,
    field_name: str,
    artifact_root: str | Path,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path_value = str(receipt.get(field_name) or "")
    failures: list[str] = []
    payload: dict[str, Any] | None = None

    if not path_value:
        return (
            {
                "role": role,
                "field": field_name,
                "path": "",
                "resolved_path": "",
                "required": True,
                "exists": False,
                "bytes": 0,
                "sha256": "",
                "secret_marker_names": [],
                "secret_marker_count": 0,
                "ok": False,
                "failures": ["receipt artifact path is required"],
            },
            None,
        )

    resolved_path = _resolve_manifest_artifact_path(path_value, artifact_root)
    entry = evidence_artifact_entry(resolved_path, role=role, required=True)
    if entry.get("exists") is not True:
        failures.append("receipt artifact is missing")
    if entry.get("read_error"):
        failures.append("receipt artifact could not be read")
    if int(entry.get("secret_marker_count") or 0) != 0:
        failures.append("receipt artifact contains secret-shaped markers")
    if entry.get("exists") is True and not entry.get("read_error"):
        try:
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                failures.append("receipt artifact must contain a JSON object")
                payload = None
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"receipt artifact JSON could not be loaded: {exc}")

    entry.update(
        {
            "field": field_name,
            "path": path_value,
            "resolved_path": str(resolved_path),
            "failures": failures,
            "ok": not failures,
        }
    )
    return entry, payload


def verify_promotion_receipt(
    receipt_path: str | Path,
    *,
    artifact_root: str | Path = ".",
    require_go: bool = False,
) -> dict[str, Any]:
    receipt = load_promotion_receipt(receipt_path)
    summary = _as_dict(receipt.get("summary"))
    checks = _as_dict(receipt.get("checks"))
    blocking_reasons = [str(item) for item in _as_list(receipt.get("blocking_reasons")) if str(item)]
    receipt_ok = receipt.get("ok") is True
    expected_ok = all(checks.get(key) is True for key in PROMOTION_RECEIPT_CHECK_KEYS)
    failures: list[str] = []

    if receipt.get("schema_version") != 1:
        failures.append("promotion receipt must be schema_version=1")
    if secret_marker_names(receipt):
        failures.append("promotion receipt contains secret-shaped markers")
    for key in PROMOTION_RECEIPT_CHECK_KEYS:
        if not isinstance(checks.get(key), bool):
            failures.append(f"promotion receipt check {key} must be a boolean")
    if receipt_ok != expected_ok:
        failures.append("promotion receipt ok must equal all receipt checks")
    if receipt.get("release_decision") != ("go" if receipt_ok else "no-go"):
        failures.append("promotion receipt release_decision does not match ok")
    if receipt.get("operator_phase") != (
        "post_apply_launch_ready" if receipt_ok else "post_apply_launch_blocked"
    ):
        failures.append("promotion receipt operator_phase does not match ok")
    if receipt.get("success_condition") != PROMOTION_RECEIPT_SUCCESS_CONDITION:
        failures.append("promotion receipt success_condition is not recognized")
    if int(summary.get("blocking_reason_count") or 0) != len(blocking_reasons):
        failures.append("promotion receipt blocking_reason_count does not match blocking_reasons length")
    if receipt_ok and blocking_reasons:
        failures.append("go promotion receipt must not include blocking_reasons")
    if not receipt_ok and not blocking_reasons:
        failures.append("no-go promotion receipt must include blocking_reasons")
    if require_go and not receipt_ok:
        failures.append("promotion receipt ok must be true")

    artifacts: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    for role, field_name in PROMOTION_RECEIPT_ARTIFACT_FIELDS:
        entry, payload = _verify_receipt_artifact(
            receipt,
            role=role,
            field_name=field_name,
            artifact_root=artifact_root,
        )
        artifacts.append(entry)
        if payload is not None:
            payloads[role] = payload

    gate_payload = _as_dict(payloads.get("post_apply_evidence_gate_json"))
    if gate_payload:
        gate_ok = gate_payload.get("ok") is True
        if checks.get("post_apply_evidence_gate") is not gate_ok:
            failures.append("receipt check post_apply_evidence_gate does not match gate artifact")
        if int(summary.get("gate_failure_count") or 0) != int(
            _as_dict(gate_payload.get("summary")).get("failure_count") or 0
        ):
            failures.append("promotion receipt gate_failure_count does not match gate artifact")

    manifest_payload = _as_dict(payloads.get("evidence_manifest_json"))
    if manifest_payload:
        manifest_ok = manifest_payload.get("ok") is True
        if checks.get("evidence_manifest") is not manifest_ok:
            failures.append("receipt check evidence_manifest does not match manifest artifact")
        if int(summary.get("manifest_artifact_count") or 0) != int(
            manifest_payload.get("artifact_count") or 0
        ):
            failures.append("promotion receipt manifest_artifact_count does not match manifest artifact")

    verification_payload = _as_dict(payloads.get("evidence_manifest_verification_json"))
    if verification_payload:
        verification_summary = _as_dict(verification_payload.get("summary"))
        verification_ok = verification_payload.get("ok") is True
        if checks.get("evidence_manifest_verification") is not verification_ok:
            failures.append(
                "receipt check evidence_manifest_verification does not match verification artifact"
            )
        expected_counts = {
            "verification_artifact_failure_count": "artifact_failure_count",
            "verification_digest_mismatch_count": "digest_mismatch_count",
            "verification_secret_marker_count": "secret_marker_count",
        }
        for receipt_key, verification_key in expected_counts.items():
            if int(summary.get(receipt_key) or 0) != int(verification_summary.get(verification_key) or 0):
                failures.append(f"promotion receipt {receipt_key} does not match verification artifact")

    artifact_failure_count = sum(1 for artifact in artifacts if artifact.get("ok") is not True)
    artifact_secret_marker_count = sum(int(artifact.get("secret_marker_count") or 0) for artifact in artifacts)
    return {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "ok": not failures and artifact_failure_count == 0,
        "promotion_receipt_json": str(receipt_path),
        "artifact_root": str(artifact_root),
        "require_go": require_go,
        "promotion_receipt_ok": receipt_ok,
        "release_decision": receipt.get("release_decision"),
        "operator_phase": receipt.get("operator_phase"),
        "summary": {
            "failure_count": len(failures),
            "artifact_count": len(artifacts),
            "artifact_failure_count": artifact_failure_count,
            "artifact_secret_marker_count": artifact_secret_marker_count,
            "blocking_reason_count": len(blocking_reasons),
        },
        "blocking_reasons": blocking_reasons,
        "failures": failures,
        "artifacts": artifacts,
    }


def _promotion_blocking_reasons(
    *,
    gate_payload: dict[str, Any],
    manifest_payload: dict[str, Any] | None,
    verification_payload: dict[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    if gate_payload.get("ok") is not True:
        gate_failures = [str(item) for item in _as_list(gate_payload.get("failures")) if str(item)]
        reasons.extend(gate_failures or ["post_apply_evidence_gate.ok must be true"])
        for blocker in _as_list(gate_payload.get("provider_blockers")):
            if not isinstance(blocker, dict):
                continue
            provider = str(blocker.get("provider") or "provider")
            command = str(blocker.get("command") or "").strip()
            failure_reason = str(blocker.get("failure_reason") or "unknown")
            remediation = str(blocker.get("remediation") or "").strip()
            docs_url = str(blocker.get("docs_url") or "").strip()
            command_label = f" {command}" if command else ""
            reason = f"provider_preflight {provider}{command_label}: {failure_reason}"
            if blocker.get("project_context_missing") is True:
                reason = f"{reason}; project_context=missing"
            if remediation:
                reason = f"{reason}; next={remediation}"
            elif docs_url:
                reason = f"{reason}; docs={docs_url}"
            reasons.append(reason)

    if manifest_payload is None:
        reasons.append("evidence manifest was not generated")
    elif manifest_payload.get("ok") is not True:
        reasons.append("evidence_manifest.ok must be true")

    if verification_payload is None:
        reasons.append("evidence manifest verification was not generated")
    else:
        reasons.extend(
            str(item) for item in _as_list(verification_payload.get("failures")) if str(item)
        )
        for artifact in _as_list(verification_payload.get("artifacts")):
            if not isinstance(artifact, dict) or artifact.get("ok") is True:
                continue
            role = str(artifact.get("role") or "artifact")
            for failure in _as_list(artifact.get("failures")):
                if str(failure):
                    reasons.append(f"{role}: {failure}")
    return reasons


def build_promotion_receipt(
    *,
    gate_payload: dict[str, Any],
    external_gate_path: str | Path,
    gate_report_path: str | Path | None = None,
    manifest_payload: dict[str, Any] | None = None,
    manifest_path: str | Path | None = None,
    verification_payload: dict[str, Any] | None = None,
    verification_path: str | Path | None = None,
) -> dict[str, Any]:
    gate_summary = _as_dict(gate_payload.get("summary"))
    verification_summary = _as_dict(verification_payload.get("summary") if verification_payload else {})
    gate_ok = gate_payload.get("ok") is True
    manifest_ok = manifest_payload is not None and manifest_payload.get("ok") is True
    verification_ok = verification_payload is not None and verification_payload.get("ok") is True
    ok = gate_ok and manifest_ok and verification_ok
    blocking_reasons = _promotion_blocking_reasons(
        gate_payload=gate_payload,
        manifest_payload=manifest_payload,
        verification_payload=verification_payload,
    )

    return {
        "schema_version": 1,
        "generated_at": _utc_now(),
        "ok": ok,
        "release_decision": "go" if ok else "no-go",
        "operator_phase": "post_apply_launch_ready" if ok else "post_apply_launch_blocked",
        "success_condition": PROMOTION_RECEIPT_SUCCESS_CONDITION,
        "external_gate_json": str(external_gate_path),
        "post_apply_evidence_gate_json": str(gate_report_path or ""),
        "evidence_manifest_json": str(manifest_path or ""),
        "evidence_manifest_verification_json": str(verification_path or ""),
        "checks": {
            "post_apply_evidence_gate": gate_ok,
            "evidence_manifest": manifest_ok,
            "evidence_manifest_verification": verification_ok,
        },
        "summary": {
            "blocking_reason_count": len(blocking_reasons),
            "gate_failure_count": int(gate_summary.get("failure_count") or 0),
            "manifest_artifact_count": int(manifest_payload.get("artifact_count") or 0)
            if manifest_payload
            else 0,
            "verification_artifact_failure_count": int(
                verification_summary.get("artifact_failure_count") or 0
            ),
            "verification_digest_mismatch_count": int(
                verification_summary.get("digest_mismatch_count") or 0
            ),
            "verification_secret_marker_count": int(
                verification_summary.get("secret_marker_count") or 0
            ),
        },
        "blocking_reasons": blocking_reasons,
    }


def print_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[post-apply-evidence-gate] ok={payload.get('ok')}")
    print(
        "[post-apply-evidence-gate] "
        f"failures={summary.get('failure_count')} "
        f"provider_ready={summary.get('provider_ready')}/{summary.get('provider_count')} "
        f"deploy_failed={summary.get('deploy_failed')} "
        f"provider_failed_checks={summary.get('provider_failed_checks')} "
        f"provider_checks={summary.get('provider_check_count')} "
        f"missing_cli={summary.get('provider_missing_cli_count')} "
        f"auth_context_missing={summary.get('provider_auth_context_missing_count')} "
        f"project_context_missing={summary.get('provider_project_context_missing_count')} "
        f"provider_blockers={summary.get('provider_blocker_count')}"
    )
    for failure in _as_list(payload.get("failures")):
        print(f"  - {failure}")
    for blocker in _as_list(payload.get("provider_blockers")):
        if not isinstance(blocker, dict):
            continue
        provider = blocker.get("provider")
        command = blocker.get("command")
        reason = blocker.get("failure_reason")
        docs_url = blocker.get("docs_url")
        remediation = blocker.get("remediation")
        details = f"  - provider_blocker {provider} {command}: {reason}"
        if blocker.get("project_context_missing") is True:
            details = f"{details} project_context=missing"
        if docs_url:
            details = f"{details} docs={docs_url}"
        if remediation:
            details = f"{details} next={remediation}"
        print(details)


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


def print_promotion_receipt_verification_report(payload: dict[str, Any]) -> None:
    summary = _as_dict(payload.get("summary"))
    print(f"[post-apply-promotion-receipt] ok={payload.get('ok')}")
    print(
        "[post-apply-promotion-receipt] "
        f"receipt_ok={payload.get('promotion_receipt_ok')} "
        f"decision={payload.get('release_decision')} "
        f"require_go={payload.get('require_go')} "
        f"artifact_failures={summary.get('artifact_failure_count')} "
        f"secret_markers={summary.get('artifact_secret_marker_count')} "
        f"failures={summary.get('failure_count')}"
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
    source.add_argument("--verify-promotion-receipt", help="Path to a post-apply promotion receipt to verify.")
    parser.add_argument("--artifact-root", default=".", help="Root used to resolve relative artifact paths in verify mode.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation JSON.")
    parser.add_argument("--json-out", help="Write machine-readable validation JSON.")
    parser.add_argument("--manifest-out", help="Write a hash manifest for the post-apply evidence artifacts.")
    parser.add_argument("--verify-manifest-out", help="Write verification JSON for the generated evidence manifest.")
    parser.add_argument(
        "--promotion-receipt-out",
        help="Write a compact launch promotion receipt for the generated post-apply artifacts.",
    )
    parser.add_argument(
        "--require-go",
        action="store_true",
        help="In --verify-promotion-receipt mode, fail unless the receipt is a launch go decision.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.require_go and not args.verify_promotion_receipt:
        print(
            "[post-apply-evidence-gate] --require-go requires --verify-promotion-receipt",
            file=sys.stderr,
        )
        return 2
    if args.verify_manifest:
        if args.promotion_receipt_out:
            print(
                "[post-apply-evidence-gate] --promotion-receipt-out requires --external-gate-json mode",
                file=sys.stderr,
            )
            return 2
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

    if args.verify_promotion_receipt:
        if args.promotion_receipt_out:
            print(
                "[post-apply-evidence-gate] --promotion-receipt-out requires --external-gate-json mode",
                file=sys.stderr,
            )
            return 2
        try:
            receipt_verification = verify_promotion_receipt(
                args.verify_promotion_receipt,
                artifact_root=args.artifact_root,
                require_go=args.require_go,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            receipt_verification = {
                "schema_version": 1,
                "generated_at": _utc_now(),
                "ok": False,
                "promotion_receipt_json": str(args.verify_promotion_receipt),
                "artifact_root": str(args.artifact_root),
                "require_go": args.require_go,
                "promotion_receipt_ok": False,
                "release_decision": "",
                "operator_phase": "",
                "summary": {
                    "failure_count": 1,
                    "artifact_count": 0,
                    "artifact_failure_count": 0,
                    "artifact_secret_marker_count": 0,
                    "blocking_reason_count": 0,
                },
                "failures": [str(exc)],
                "artifacts": [],
            }
        if args.json:
            print(json.dumps(receipt_verification, indent=2))
        else:
            print_promotion_receipt_verification_report(receipt_verification)
        if args.json_out:
            write_json_report(args.json_out, receipt_verification)
            print(f"[post-apply-promotion-receipt] json written: {args.json_out}")
        return 0 if receipt_verification["ok"] else 1

    evidence_path = Path(args.external_gate_json)
    if args.verify_manifest_out and not args.manifest_out:
        print(
            "[post-apply-evidence-gate] --verify-manifest-out requires --manifest-out",
            file=sys.stderr,
        )
        return 2
    if args.promotion_receipt_out and not (args.json_out and args.manifest_out and args.verify_manifest_out):
        print(
            "[post-apply-evidence-gate] "
            "--promotion-receipt-out requires --json-out, --manifest-out, and --verify-manifest-out",
            file=sys.stderr,
        )
        return 2
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
    verification: dict[str, Any] | None = None
    if args.verify_manifest_out and args.manifest_out:
        verification = verify_evidence_manifest(args.manifest_out, artifact_root=args.artifact_root)
        write_json_report(args.verify_manifest_out, verification)
        print(f"[post-apply-evidence-manifest] json written: {args.verify_manifest_out}")
    receipt: dict[str, Any] | None = None
    if args.promotion_receipt_out:
        receipt = build_promotion_receipt(
            gate_payload=payload,
            external_gate_path=evidence_path,
            gate_report_path=args.json_out,
            manifest_payload=manifest,
            manifest_path=args.manifest_out,
            verification_payload=verification,
            verification_path=args.verify_manifest_out,
        )
        write_json_report(args.promotion_receipt_out, receipt)
        print(f"[post-apply-promotion] receipt written: {args.promotion_receipt_out}")
    return (
        0
        if payload["ok"]
        and (manifest is None or manifest["ok"])
        and (verification is None or verification["ok"])
        and (receipt is None or receipt["ok"])
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
