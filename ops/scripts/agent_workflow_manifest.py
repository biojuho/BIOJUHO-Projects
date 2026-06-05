#!/usr/bin/env python3
"""Validate and summarize declarative agent workflow mappings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "agent_workflows.json"

ALLOWED_STATUSES = {"active", "candidate", "retired"}
ALLOWED_SMOKE_SCOPES = {"workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie"}
ALLOWED_PROVIDERS = {"openai", "google", "canva", "local"}
WORKFLOW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REQUIRED_WORKFLOW_FIELDS = {
    "id",
    "label",
    "project",
    "status",
    "objective",
    "entrypoints",
    "providers",
    "mcp_servers",
    "tools",
    "smoke_scope",
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

    workflows = payload.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        errors.append("workflows must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    for index, workflow in enumerate(workflows):
        prefix = f"workflows[{index}]"
        if not isinstance(workflow, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_WORKFLOW_FIELDS - set(workflow)
        for field in sorted(missing):
            errors.append(f"{prefix}.{field} is required")

        workflow_id = _require_string(workflow.get("id"), f"{prefix}.id", errors)
        if workflow_id:
            if not WORKFLOW_ID_RE.match(workflow_id):
                errors.append(f"{prefix}.id must use lowercase letters, numbers, hyphens, or underscores")
            if workflow_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(workflow_id)

        _require_string(workflow.get("label"), f"{prefix}.label", errors)
        _require_string(workflow.get("project"), f"{prefix}.project", errors)
        _require_string(workflow.get("objective"), f"{prefix}.objective", errors)
        status = _require_string(workflow.get("status"), f"{prefix}.status", errors)
        if status and status not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.status must be active, candidate, or retired")
        smoke_scope = _require_string(workflow.get("smoke_scope"), f"{prefix}.smoke_scope", errors)
        if smoke_scope and smoke_scope not in ALLOWED_SMOKE_SCOPES:
            errors.append(f"{prefix}.smoke_scope must be a known smoke scope")

        _validate_paths(workflow.get("entrypoints"), f"{prefix}.entrypoints", workspace_root, errors)
        _validate_paths(workflow.get("evidence"), f"{prefix}.evidence", workspace_root, errors)
        _validate_provider_list(workflow.get("providers"), f"{prefix}.providers", errors)
        _validate_string_list(workflow.get("mcp_servers"), f"{prefix}.mcp_servers", errors, allow_empty=True)
        _validate_string_list(workflow.get("tools"), f"{prefix}.tools", errors)

    return errors


def summarize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    workflows = payload["workflows"]
    status_counts = Counter(workflow["status"] for workflow in workflows)
    smoke_scope_counts = Counter(workflow["smoke_scope"] for workflow in workflows)
    provider_counts = Counter(provider for workflow in workflows for provider in workflow["providers"])
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "workflow_count": len(workflows),
        "status_counts": dict(sorted(status_counts.items())),
        "smoke_scope_counts": dict(sorted(smoke_scope_counts.items())),
        "provider_counts": dict(sorted(provider_counts.items())),
        "workflows": [
            {
                "id": workflow["id"],
                "project": workflow["project"],
                "status": workflow["status"],
                "smoke_scope": workflow["smoke_scope"],
                "provider_count": len(workflow["providers"]),
                "mcp_server_count": len(workflow["mcp_servers"]),
                "tool_count": len(workflow["tools"]),
                "evidence_count": len(workflow["evidence"]),
            }
            for workflow in workflows
        ],
    }


def format_markdown(payload: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        "# Agent Workflow Manifest - 2026-06-05",
        "",
        "## Summary",
        "",
        f"- Workflows: {summary['workflow_count']}",
        f"- Status counts: {_format_counts(summary['status_counts'])}",
        f"- Smoke scopes: {_format_counts(summary['smoke_scope_counts'])}",
        f"- Providers: {_format_counts(summary['provider_counts'])}",
        f"- Generated at: `{summary['generated_at']}`",
        "",
        "## Workflows",
        "",
    ]
    for workflow in payload["workflows"]:
        lines.extend(
            [
                f"### {workflow['id']}",
                "",
                f"- Label: {workflow['label']}",
                f"- Project: `{workflow['project']}`",
                f"- Status: `{workflow['status']}`",
                f"- Smoke scope: `{workflow['smoke_scope']}`",
                f"- Objective: {workflow['objective']}",
                f"- Providers: {', '.join(f'`{provider}`' for provider in workflow['providers'])}",
                f"- MCP servers: {_format_optional_list(workflow['mcp_servers'])}",
                f"- Tools: {', '.join(f'`{tool}`' for tool in workflow['tools'])}",
                "- Entrypoints:",
            ]
        )
        lines.extend(f"  - `{path}`" for path in workflow["entrypoints"])
        lines.append("- Evidence:")
        lines.extend(f"  - `{path}`" for path in workflow["evidence"])
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
    parser = argparse.ArgumentParser(description="Validate and summarize agent workflow manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run(args.manifest, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"agent workflow manifest failed: {exc}", file=sys.stderr)
        return 1
    print(f"agent workflow manifest valid: {summary['workflow_count']} workflows")
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


def _validate_provider_list(value: Any, field: str, errors: list[str]) -> None:
    providers = _validate_string_list(value, field, errors)
    for provider in providers:
        if provider not in ALLOWED_PROVIDERS:
            errors.append(f"{field} contains unsupported provider: {provider}")


def _validate_string_list(value: Any, field: str, errors: list[str], *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        errors.append(f"{field} must be a {'possibly empty ' if allow_empty else ''}array")
        return []
    valid_items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        valid_items.append(item.strip())
    return valid_items


def _validate_paths(value: Any, field: str, workspace_root: Path, errors: list[str]) -> None:
    paths = _validate_string_list(value, field, errors)
    for index, path_value in enumerate(paths):
        path_field = f"{field}[{index}]"
        if not _is_repo_relative(path_value):
            errors.append(f"{path_field} must be a repo-relative path")
            continue
        if not (workspace_root / path_value).exists():
            errors.append(f"{path_field} must exist in the workspace")


def _is_repo_relative(value: str) -> bool:
    normalized = value.replace("\\", "/").strip()
    if not normalized or normalized in {".", ".."}:
        return False
    if normalized.startswith("/") or normalized.startswith("../"):
        return False
    if "/../" in f"/{normalized}/":
        return False
    return not Path(value).is_absolute()


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _format_optional_list(values: list[str]) -> str:
    if not values:
        return "`none`"
    return ", ".join(f"`{value}`" for value in values)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
