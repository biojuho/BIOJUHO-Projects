from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "mcp_service_manifest.json"
ALLOWED_LANGUAGES = {"python", "typescript"}
ALLOWED_TRANSPORTS = {"stdio", "sse", "http-metadata"}
SERVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
PYTHON_TOOL_RE = re.compile(r"@(?:mcp|server)\.tool\(")
TYPESCRIPT_TOOL_RE = re.compile(r"\bname:\s*[\"'][a-z0-9][a-z0-9_-]*[\"']")


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
        service_id = _require_string(service.get("id"), f"{prefix}.id", errors)
        if service_id:
            if not SERVICE_ID_RE.match(service_id):
                errors.append(f"{prefix}.id must use lowercase letters, numbers, hyphens, or underscores")
            if service_id in seen_ids:
                errors.append(f"{prefix}.id must be unique")
            seen_ids.add(service_id)
        _require_string(service.get("name"), f"{prefix}.name", errors)
        _require_string(service.get("project"), f"{prefix}.project", errors)
        language = _require_string(service.get("language"), f"{prefix}.language", errors)
        if language and language not in ALLOWED_LANGUAGES:
            errors.append(f"{prefix}.language must be one of {', '.join(sorted(ALLOWED_LANGUAGES))}")
        framework = _require_string(service.get("framework"), f"{prefix}.framework", errors)
        source_path = _validate_repo_file(service.get("source_path"), f"{prefix}.source_path", workspace_root, errors)
        tool_source_path = _validate_optional_repo_file(
            service.get("tool_source_path"), f"{prefix}.tool_source_path", workspace_root, errors
        )
        _validate_repo_dir(service.get("cwd"), f"{prefix}.cwd", workspace_root, errors)
        _validate_string_list(service.get("command"), f"{prefix}.command", errors, non_empty=True)
        _validate_string_list(service.get("domains"), f"{prefix}.domains", errors, non_empty=True)
        _validate_string_list(service.get("required_env"), f"{prefix}.required_env", errors)
        _validate_string_list(service.get("smoke_checks"), f"{prefix}.smoke_checks", errors, non_empty=True)
        expected_tools = _validate_string_list(
            service.get("expected_tools", []), f"{prefix}.expected_tools", errors
        )
        if len(expected_tools) != len(set(expected_tools)):
            errors.append(f"{prefix}.expected_tools must not contain duplicates")
        transports = _validate_string_list(service.get("transports"), f"{prefix}.transports", errors, non_empty=True)
        for transport in transports:
            if transport not in ALLOWED_TRANSPORTS:
                errors.append(f"{prefix}.transports contains unknown transport: {transport}")
        expected_min_tools = service.get("expected_min_tools")
        if isinstance(expected_min_tools, bool) or not isinstance(expected_min_tools, int) or expected_min_tools < 0:
            errors.append(f"{prefix}.expected_min_tools must be a non-negative integer")
        elif source_path is not None:
            detected = detect_tool_count(tool_source_path or source_path, language)
            if detected < expected_min_tools:
                errors.append(f"{prefix}.expected_min_tools exceeds detected tool count: {detected}")
        if framework == "FastMCP" and source_path is not None:
            source_text = source_path.read_text(encoding="utf-8", errors="replace")
            if "FastMCP" not in source_text:
                errors.append(f"{prefix}.source_path must contain FastMCP")

    return errors


def build_summary(payload: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> dict[str, Any]:
    services = payload["services"]
    languages = Counter(str(service["language"]) for service in services)
    frameworks = Counter(str(service["framework"]) for service in services)
    transports = Counter(transport for service in services for transport in service["transports"])
    service_rows = []
    for service in services:
        source_path = workspace_root / service.get("tool_source_path", service["source_path"])
        service_rows.append(
            {
                "id": service["id"],
                "name": service["name"],
                "project": service["project"],
                "language": service["language"],
                "framework": service["framework"],
                "transports": service["transports"],
                "tool_count_detected": detect_tool_count(source_path, service["language"]),
                "expected_tools_count": len(service.get("expected_tools", [])),
                "required_env_count": len(service.get("required_env", [])),
                "smoke_checks": service["smoke_checks"],
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_generated_at": payload["generated_at"],
        "summary": {
            "total_services": len(services),
            "fastmcp_services": frameworks.get("FastMCP", 0),
            "languages": dict(sorted(languages.items())),
            "frameworks": dict(sorted(frameworks.items())),
            "transports": dict(sorted(transports.items())),
        },
        "services": service_rows,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# MCP Service Manifest",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Manifest generated at: `{summary['manifest_generated_at']}`",
        f"- Total services: `{summary['summary']['total_services']}`",
        f"- FastMCP services: `{summary['summary']['fastmcp_services']}`",
        f"- Languages: `{json.dumps(summary['summary']['languages'], ensure_ascii=False, sort_keys=True)}`",
        f"- Frameworks: `{json.dumps(summary['summary']['frameworks'], ensure_ascii=False, sort_keys=True)}`",
        f"- Transports: `{json.dumps(summary['summary']['transports'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Services",
        "",
    ]
    for service in summary["services"]:
        lines.extend(
            [
                f"### {service['id']}",
                "",
                f"- Name: {service['name']}",
                f"- Project: `{service['project']}`",
                f"- Language/framework: `{service['language']}` / `{service['framework']}`",
                f"- Transports: `{', '.join(service['transports'])}`",
                f"- Detected tools: `{service['tool_count_detected']}`",
                f"- Expected runtime tools: `{service['expected_tools_count']}`",
                f"- Required env count: `{service['required_env_count']}`",
                f"- Smoke checks: `{', '.join(service['smoke_checks'])}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def detect_tool_count(source_path: Path, language: str) -> int:
    text = source_path.read_text(encoding="utf-8", errors="replace")
    if language == "python":
        return len(PYTHON_TOOL_RE.findall(text))
    if language == "typescript":
        return len(TYPESCRIPT_TOOL_RE.findall(text))
    return 0


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and summarize repo-local MCP service composition.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = load_manifest(args.manifest)
        errors = validate_manifest(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"mcp service manifest failed: {exc}")
        return 1
    if errors:
        print("mcp service manifest invalid:")
        for error in errors:
            print(f"- {error}")
        return 1

    summary = build_summary(payload)
    if args.json_out:
        write_json_atomic(args.json_out, summary)
    if args.markdown_out:
        write_text_atomic(args.markdown_out, render_markdown(summary))

    print(
        "mcp service manifest valid: "
        f"{summary['summary']['total_services']} services, "
        f"fastmcp={summary['summary']['fastmcp_services']}"
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


def _require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _validate_repo_file(value: Any, field: str, workspace_root: Path, errors: list[str]) -> Path | None:
    path_value = _require_string(value, field, errors)
    if not path_value:
        return None
    if not _is_repo_relative(path_value):
        errors.append(f"{field} must be a repo-relative path")
        return None
    path = workspace_root / path_value
    if not path.is_file():
        errors.append(f"{field} must exist as a file in the workspace")
        return None
    return path


def _validate_optional_repo_file(value: Any, field: str, workspace_root: Path, errors: list[str]) -> Path | None:
    if value is None:
        return None
    return _validate_repo_file(value, field, workspace_root, errors)


def _validate_repo_dir(value: Any, field: str, workspace_root: Path, errors: list[str]) -> Path | None:
    path_value = _require_string(value, field, errors)
    if not path_value:
        return None
    if not _is_repo_relative(path_value):
        errors.append(f"{field} must be a repo-relative path")
        return None
    path = workspace_root / path_value
    if not path.is_dir():
        errors.append(f"{field} must exist as a directory in the workspace")
        return None
    return path


def _validate_string_list(
    value: Any,
    field: str,
    errors: list[str],
    *,
    non_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return []
    if non_empty and not value:
        errors.append(f"{field} must be a non-empty array")
        return []
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        items.append(item.strip())
    return items


def _is_repo_relative(value: str) -> bool:
    normalized = value.replace("\\", "/").strip()
    if not normalized or normalized in {".", ".."}:
        return normalized == "."
    path = Path(normalized)
    return not path.is_absolute() and ".." not in path.parts


if __name__ == "__main__":
    raise SystemExit(main())
