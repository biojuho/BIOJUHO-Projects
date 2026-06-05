#!/usr/bin/env python3
"""Validate and summarize tracked MCP service inventory."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "mcp_services.json"

SERVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ALLOWED_STATUSES = {"active", "candidate", "retired"}
ALLOWED_LANGUAGES = {"python", "typescript", "external"}
ALLOWED_TRANSPORTS = {"stdio", "http-sse", "streamable-http", "cli"}
ALLOWED_SMOKE_SCOPES = {"workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie"}
REQUIRED_SERVICE_FIELDS = {
    "id",
    "label",
    "project",
    "status",
    "language",
    "transport_modes",
    "auth_boundary",
    "entrypoints",
    "smoke_scope",
    "smoke_checks",
    "evidence",
}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def validate_manifest(payload: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1 or isinstance(payload.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    _validate_timestamp(payload.get("generated_at"), errors)
    _require_string(payload.get("description"), "description", errors)

    services = payload.get("services")
    if not isinstance(services, list) or not services:
        errors.append("services must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    for index, service in enumerate(services):
        prefix = f"services[{index}]"
        if not isinstance(service, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_SERVICE_FIELDS - set(service)
        for field in sorted(missing):
            errors.append(f"{prefix}.{field} is required")

        service_id = _require_string(service.get("id"), f"{prefix}.id", errors)
        if service_id:
            if not SERVICE_ID_RE.match(service_id):
                errors.append(f"{prefix}.id must use lowercase letters, numbers, hyphens, or underscores")
            if service_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(service_id)

        _require_string(service.get("label"), f"{prefix}.label", errors)
        _require_string(service.get("project"), f"{prefix}.project", errors)
        _require_string(service.get("auth_boundary"), f"{prefix}.auth_boundary", errors)

        status = _require_string(service.get("status"), f"{prefix}.status", errors)
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be active, candidate, or retired")
        language = _require_string(service.get("language"), f"{prefix}.language", errors)
        if language and language not in ALLOWED_LANGUAGES:
            errors.append(f"{prefix}.language must be python, typescript, or external")
        smoke_scope = _require_string(service.get("smoke_scope"), f"{prefix}.smoke_scope", errors)
        if smoke_scope and smoke_scope not in ALLOWED_SMOKE_SCOPES:
            errors.append(f"{prefix}.smoke_scope must be a known smoke scope")

        _validate_choice_list(service.get("transport_modes"), f"{prefix}.transport_modes", ALLOWED_TRANSPORTS, errors)
        _validate_string_list(service.get("smoke_checks"), f"{prefix}.smoke_checks", errors)
        _validate_tracked_paths(service.get("entrypoints"), f"{prefix}.entrypoints", workspace_root, errors)
        _validate_tracked_paths(service.get("evidence"), f"{prefix}.evidence", workspace_root, errors)

    return errors


def summarize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    services = payload["services"]
    status_counts = Counter(service["status"] for service in services)
    language_counts = Counter(service["language"] for service in services)
    transport_counts = Counter(transport for service in services for transport in service["transport_modes"])
    auth_counts = Counter(service["auth_boundary"] for service in services)
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "service_count": len(services),
        "status_counts": dict(sorted(status_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "transport_counts": dict(sorted(transport_counts.items())),
        "auth_boundary_counts": dict(sorted(auth_counts.items())),
        "services": [
            {
                "id": service["id"],
                "project": service["project"],
                "status": service["status"],
                "language": service["language"],
                "transport_modes": service["transport_modes"],
                "smoke_scope": service["smoke_scope"],
                "smoke_check_count": len(service["smoke_checks"]),
                "entrypoint_count": len(service["entrypoints"]),
                "evidence_count": len(service["evidence"]),
            }
            for service in services
        ],
    }


def format_markdown(payload: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        "# MCP Service Inventory - 2026-06-05",
        "",
        "## Summary",
        "",
        f"- Services: {summary['service_count']}",
        f"- Status counts: {_format_counts(summary['status_counts'])}",
        f"- Languages: {_format_counts(summary['language_counts'])}",
        f"- Transports: {_format_counts(summary['transport_counts'])}",
        f"- Auth boundaries: {_format_counts(summary['auth_boundary_counts'])}",
        f"- Generated at: `{summary['generated_at']}`",
        "",
        "## Services",
        "",
    ]
    for service in payload["services"]:
        lines.extend(
            [
                f"### {service['id']}",
                "",
                f"- Label: {service['label']}",
                f"- Project: `{service['project']}`",
                f"- Status: `{service['status']}`",
                f"- Language: `{service['language']}`",
                f"- Transport modes: {', '.join(f'`{mode}`' for mode in service['transport_modes'])}",
                f"- Auth boundary: `{service['auth_boundary']}`",
                f"- Smoke scope: `{service['smoke_scope']}`",
                f"- Smoke checks: {', '.join(f'`{check}`' for check in service['smoke_checks'])}",
                "- Entrypoints:",
            ]
        )
        lines.extend(f"  - `{path}`" for path in service["entrypoints"])
        lines.append("- Evidence:")
        lines.extend(f"  - `{path}`" for path in service["evidence"])
        lines.append("")
    return "\n".join(lines)


def run(manifest_path: Path, *, json_out: Path | None = None, markdown_out: Path | None = None) -> dict[str, Any]:
    payload = load_manifest(manifest_path)
    errors = validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    summary = summarize_manifest(payload)
    if json_out is not None:
        _write_text_atomic(json_out, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(payload, summary))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and summarize tracked MCP service inventory.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run(args.manifest, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"mcp service inventory failed: {exc}", file=sys.stderr)
        return 1
    print(f"mcp service inventory valid: {summary['service_count']} services")
    return 0


def _validate_timestamp(value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append("generated_at must be a non-empty ISO timestamp")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append("generated_at must be parseable as ISO datetime")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append("generated_at must include a timezone offset")


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _validate_string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return []
    valid_items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        valid_items.append(item.strip())
    return valid_items


def _validate_choice_list(value: Any, field: str, allowed: set[str], errors: list[str]) -> None:
    for item in _validate_string_list(value, field, errors):
        if item not in allowed:
            errors.append(f"{field} contains unsupported value: {item}")


def _validate_tracked_paths(value: Any, field: str, workspace_root: Path, errors: list[str]) -> None:
    paths = _validate_string_list(value, field, errors)
    for index, path_value in enumerate(paths):
        path_field = f"{field}[{index}]"
        if not _is_repo_relative(path_value):
            errors.append(f"{path_field} must be a repo-relative path")
            continue
        if not (workspace_root / path_value).exists():
            errors.append(f"{path_field} must exist in the workspace")
            continue
        if not _is_git_tracked(workspace_root, path_value):
            errors.append(f"{path_field} must be tracked in git")


def _is_repo_relative(value: str) -> bool:
    normalized = value.replace("\\", "/").strip()
    if not normalized or normalized in {".", ".."}:
        return False
    if normalized.startswith("/") or normalized.startswith("../"):
        return False
    if "/../" in f"/{normalized}/":
        return False
    return not Path(value).is_absolute()


def _is_git_tracked(workspace_root: Path, path_value: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(workspace_root), "ls-files", "--error-unmatch", "--", path_value],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
