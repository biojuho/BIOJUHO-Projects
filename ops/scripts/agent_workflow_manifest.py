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
ALLOWED_SMOKE_SCOPES = {"all", "workspace", "desci", "agriguard", "mcp", "getdaytrends", "cie", "manual"}
ALLOWED_LAUNCH_STATUSES = {"active", "manual", "watch"}
CWD_SUFFIX_RE = re.compile(r"\s+\(cwd=([^)]+)\)$")
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
REQUIRED_ROLE_POLICY_FIELDS = {
    "source_signal",
    "source_url",
    "allowed_agent_roles",
    "review_allowed_roles",
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
    role_policy = _validate_role_policy(payload.get("role_policy"), errors)
    allowed_agent_roles = set(role_policy["allowed_agent_roles"]) if role_policy else set()

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
        agent_roles = _validate_string_list(workflow.get("agent_roles"), f"{prefix}.agent_roles", errors)
        if allowed_agent_roles:
            for role_index, role in enumerate(agent_roles):
                if role not in allowed_agent_roles:
                    errors.append(
                        f"{prefix}.agent_roles[{role_index}] must be declared in role_policy.allowed_agent_roles"
                    )
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
    role_policy = payload["role_policy"]
    scope_counts = Counter(workflow["smoke_scope"] for workflow in workflows)
    status_counts = Counter(workflow["launch_status"] for workflow in workflows)
    mcp_counts = Counter(server for workflow in workflows for server in workflow["mcp_servers"])
    return {
        "schema_version": payload["schema_version"],
        "generated_at": payload["generated_at"],
        "workflow_count": len(workflows),
        "allowed_agent_role_count": len(role_policy["allowed_agent_roles"]),
        "review_allowed_roles": role_policy["review_allowed_roles"],
        "role_policy_source_signal": role_policy["source_signal"],
        "role_policy_source_url": role_policy["source_url"],
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
        "## Role Policy",
        "",
        f"- Source signal: {summary['role_policy_source_signal']}",
        f"- Source URL: {summary['role_policy_source_url']}",
        f"- Allowed agent roles: {summary['allowed_agent_role_count']}",
        f"- Review allowed roles: {', '.join(summary['review_allowed_roles'])}",
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


def build_workflow_plan(payload: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    workflows = {workflow["id"]: workflow for workflow in payload["workflows"]}
    if workflow_id not in workflows:
        raise ValueError(f"unknown workflow id: {workflow_id}")
    workflow = workflows[workflow_id]
    steps: list[dict[str, Any]] = []
    for index, entrypoint in enumerate(workflow["entrypoints"], start=1):
        steps.append(
            {
                "phase": "entrypoint",
                "index": index,
                "action": "inspect",
                "path": entrypoint,
                "dry_run": True,
            }
        )
    for index, gate in enumerate(workflow["quality_gates"], start=1):
        command, cwd = split_quality_gate_command(gate)
        steps.append(
            {
                "phase": "quality_gate",
                "index": index,
                "action": "run",
                "command": command,
                "cwd": cwd,
                "dry_run": True,
            }
        )
    for index, evidence in enumerate(workflow["evidence"], start=1):
        steps.append(
            {
                "phase": "evidence",
                "index": index,
                "action": "review",
                "path": evidence,
                "dry_run": True,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "execution_mode": "dry_run",
        "will_execute": False,
        "workflow": {
            "id": workflow["id"],
            "project": workflow["project"],
            "goal": workflow["goal"],
            "launch_status": workflow["launch_status"],
            "smoke_scope": workflow["smoke_scope"],
            "agent_roles": workflow["agent_roles"],
            "mcp_servers": workflow["mcp_servers"],
        },
        "steps": steps,
    }


def format_workflow_plan_markdown(plan: dict[str, Any]) -> str:
    workflow = plan["workflow"]
    lines = [
        f"# Agent Workflow Dry-Run Plan - {workflow['id']}",
        "",
        f"- Generated at: `{plan['generated_at']}`",
        f"- Execution mode: `{plan['execution_mode']}`",
        f"- Will execute: `{str(plan['will_execute']).lower()}`",
        f"- Project: `{workflow['project']}`",
        f"- Launch status: `{workflow['launch_status']}`",
        f"- Smoke scope: `{workflow['smoke_scope']}`",
        f"- Agent roles: `{', '.join(workflow['agent_roles'])}`",
        f"- MCP servers: `{', '.join(workflow['mcp_servers'])}`",
        "",
        "## Steps",
        "",
    ]
    for step in plan["steps"]:
        lines.append(f"### {step['phase']} {step['index']}")
        if step["phase"] == "quality_gate":
            lines.append(f"- Action: `{step['action']}`")
            lines.append(f"- CWD: `{step['cwd']}`")
            lines.append(f"- Command: `{step['command']}`")
        else:
            lines.append(f"- Action: `{step['action']}`")
            lines.append(f"- Path: `{step['path']}`")
        lines.append("- Dry run: `true`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def split_quality_gate_command(value: str) -> tuple[str, str]:
    match = CWD_SUFFIX_RE.search(value)
    if not match:
        return value, "."
    return value[: match.start()].strip(), match.group(1).strip()


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
    parser.add_argument("--workflow-plan", help="Render a dry-run plan for the given workflow id")
    parser.add_argument("--plan-json-out", type=Path)
    parser.add_argument("--plan-markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = load_manifest(args.manifest)
        errors = validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
        if errors:
            raise ValueError("\n".join(errors))
        summary = summarize_manifest(payload)
        if args.json_out is not None:
            _write_json_atomic(args.json_out, summary)
        if args.markdown_out is not None:
            _write_text_atomic(args.markdown_out, format_markdown(payload, summary))
        if args.workflow_plan:
            plan = build_workflow_plan(payload, args.workflow_plan)
            if args.plan_json_out is not None:
                _write_json_atomic(args.plan_json_out, plan)
            if args.plan_markdown_out is not None:
                _write_text_atomic(args.plan_markdown_out, format_workflow_plan_markdown(plan))
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


def _validate_role_policy(value: Any, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append("role_policy must be an object")
        return None
    missing = REQUIRED_ROLE_POLICY_FIELDS - set(value)
    for field in sorted(missing):
        errors.append(f"role_policy.{field} is required")
    source_signal = _require_string(value.get("source_signal"), "role_policy.source_signal", errors)
    source_url = _require_string(value.get("source_url"), "role_policy.source_url", errors)
    if source_url and not source_url.startswith("https://github.com/"):
        errors.append("role_policy.source_url must be a GitHub HTTPS URL")
    allowed_agent_roles = _validate_string_list(
        value.get("allowed_agent_roles"),
        "role_policy.allowed_agent_roles",
        errors,
        unique=True,
    )
    review_allowed_roles = _validate_string_list(
        value.get("review_allowed_roles"),
        "role_policy.review_allowed_roles",
        errors,
        unique=True,
    )
    if review_allowed_roles and "maintain" not in review_allowed_roles:
        errors.append("role_policy.review_allowed_roles must include maintain")
    if not source_signal or not source_url or not allowed_agent_roles or not review_allowed_roles:
        return None
    return {
        "source_signal": source_signal,
        "source_url": source_url,
        "allowed_agent_roles": allowed_agent_roles,
        "review_allowed_roles": review_allowed_roles,
    }


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _validate_string_list(value: Any, field: str, errors: list[str], *, unique: bool = False) -> list[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty array")
        return []
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _require_string(item, f"{field}[{index}]", errors)
        if not text:
            continue
        if unique and text in seen:
            errors.append(f"{field}[{index}] must be unique")
        seen.add(text)
        result.append(text)
    return result


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
