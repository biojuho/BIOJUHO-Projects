from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "agent_workflows.json"
ALLOWED_SMOKE_SCOPES = {"all", "workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie", "manual"}
ALLOWED_LAUNCH_STATUSES = {"active", "manual", "watch"}
REQUIRED_WORKFLOW_FIELDS = {
    "id",
    "project",
    "goal",
    "agent_roles",
    "mcp_servers",
    "entrypoints",
    "quality_gates",
    "smoke_scope",
    "evidence",
    "launch_status",
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
    _validate_source_context(payload.get("source_context"), errors)

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
            if workflow_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(workflow_id)
        _require_string(workflow.get("project"), f"{prefix}.project", errors)
        _require_string(workflow.get("goal"), f"{prefix}.goal", errors)
        _validate_string_list(workflow.get("agent_roles"), f"{prefix}.agent_roles", errors)
        _validate_string_list(workflow.get("mcp_servers"), f"{prefix}.mcp_servers", errors)
        _validate_string_list(workflow.get("quality_gates"), f"{prefix}.quality_gates", errors)
        smoke_scope = _require_string(workflow.get("smoke_scope"), f"{prefix}.smoke_scope", errors)
        if smoke_scope and smoke_scope not in ALLOWED_SMOKE_SCOPES:
            errors.append(f"{prefix}.smoke_scope must be one of {', '.join(sorted(ALLOWED_SMOKE_SCOPES))}")
        launch_status = _require_string(workflow.get("launch_status"), f"{prefix}.launch_status", errors)
        if launch_status and launch_status not in ALLOWED_LAUNCH_STATUSES:
            errors.append(f"{prefix}.launch_status must be active, manual, or watch")
        _validate_paths(workflow.get("entrypoints"), f"{prefix}.entrypoints", workspace_root, errors)
        _validate_paths(workflow.get("evidence"), f"{prefix}.evidence", workspace_root, errors)
    return errors


def summarize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    workflows = payload["workflows"]
    scope_counts = Counter(workflow["smoke_scope"] for workflow in workflows)
    status_counts = Counter(workflow["launch_status"] for workflow in workflows)
    mcp_counts = Counter(server for workflow in workflows for server in workflow["mcp_servers"])
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "workflow_count": len(workflows),
        "smoke_scope_counts": dict(sorted(scope_counts.items())),
        "launch_status_counts": dict(sorted(status_counts.items())),
        "mcp_server_counts": dict(sorted(mcp_counts.items())),
        "workflows": [
            {
                "id": workflow["id"],
                "project": workflow["project"],
                "smoke_scope": workflow["smoke_scope"],
                "launch_status": workflow["launch_status"],
                "entrypoint_count": len(workflow["entrypoints"]),
                "quality_gate_count": len(workflow["quality_gates"]),
                "evidence_count": len(workflow["evidence"]),
                "mcp_servers": workflow["mcp_servers"],
            }
            for workflow in workflows
        ],
    }


def format_markdown(payload: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        "# Agent Workflow Manifest - 2026-06-04",
        "",
        "## Summary",
        "",
        f"- Workflows declared: {summary['workflow_count']}",
        f"- Launch status counts: {_format_counts(summary['launch_status_counts'])}",
        f"- Smoke scope counts: {_format_counts(summary['smoke_scope_counts'])}",
        f"- MCP server counts: {_format_counts(summary['mcp_server_counts'])}",
        f"- Generated at: `{summary['generated_at']}`",
        "",
        "## Source Context",
        "",
        f"- Source: {payload['source_context']['repo']} ({payload['source_context']['url']})",
        f"- Adopted pattern: {payload['source_context']['adopted_pattern']}",
        "",
        "## Workflows",
        "",
    ]
    for workflow in payload["workflows"]:
        lines.extend(
            [
                f"### {workflow['id']}",
                "",
                f"- Project: `{workflow['project']}`",
                f"- Launch status: `{workflow['launch_status']}`",
                f"- Smoke scope: `{workflow['smoke_scope']}`",
                f"- Goal: {workflow['goal']}",
                f"- Agent roles: {', '.join(workflow['agent_roles'])}",
                f"- MCP servers: {', '.join(workflow['mcp_servers'])}",
                "- Entrypoints:",
            ]
        )
        lines.extend(f"  - `{path}`" for path in workflow["entrypoints"])
        lines.append("- Quality gates:")
        lines.extend(f"  - `{gate}`" for gate in workflow["quality_gates"])
        lines.append("- Evidence:")
        lines.extend(f"  - `{path}`" for path in workflow["evidence"])
        lines.append("")
    lines.extend(
        [
            "## Operating Decision",
            "",
            "Keep this manifest declarative. Promote a workflow to runtime orchestration only after the listed quality gates are repeatable and the evidence paths remain current.",
            "",
        ]
    )
    return "\n".join(lines)


def run(manifest_path: Path, *, json_out: Path | None = None, markdown_out: Path | None = None) -> dict[str, Any]:
    payload = load_manifest(manifest_path)
    errors = validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    summary = summarize_manifest(payload)
    if json_out is not None:
        _write_json_atomic(json_out, summary)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(payload, summary))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate launch-critical agent workflow declarations.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run(args.manifest, json_out=args.json_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"agent workflow manifest failed: {exc}", file=sys.stderr)
        return 1
    print(
        "agent workflow manifest valid: "
        f"{summary['workflow_count']} workflows, launch statuses={_format_counts(summary['launch_status_counts'])}"
    )
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


def _validate_source_context(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("source_context must be an object")
        return
    _require_string(value.get("repo"), "source_context.repo", errors)
    url = _require_string(value.get("url"), "source_context.url", errors)
    if url and not url.startswith("https://github.com/"):
        errors.append("source_context.url must be a GitHub HTTPS URL")
    _require_string(value.get("adopted_pattern"), "source_context.adopted_pattern", errors)


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _validate_string_list(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")


def _validate_paths(value: Any, field: str, workspace_root: Path, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return
    for index, item in enumerate(value):
        path_field = f"{field}[{index}]"
        path_value = _require_string(item, path_field, errors)
        if not path_value:
            continue
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
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "-"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
