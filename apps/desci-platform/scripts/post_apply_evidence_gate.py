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
        "ok": False,
    }
    if not entry["exists"]:
        entry["ok"] = not required
        return entry

    raw = artifact_path.read_bytes()
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DeSci post-apply external gate JSON evidence.")
    parser.add_argument("--external-gate-json", required=True, help="Path to external_release_gate.py JSON evidence.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation JSON.")
    parser.add_argument("--json-out", help="Write machine-readable validation JSON.")
    parser.add_argument("--manifest-out", help="Write a hash manifest for the post-apply evidence artifacts.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
