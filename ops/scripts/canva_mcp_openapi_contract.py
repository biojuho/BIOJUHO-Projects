#!/usr/bin/env python3
"""Generate a static OpenAPI contract for the Canva MCP tool registry."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_TOOLS_SOURCE = WORKSPACE_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "tools.ts"


def load_tools_source(path: Path = DEFAULT_TOOLS_SOURCE) -> str:
    return path.read_text(encoding="utf-8")


def extract_tools(source_text: str) -> list[dict[str, Any]]:
    array_body = _extract_tools_array_body(source_text)
    tools: list[dict[str, Any]] = []
    for block in _split_top_level_objects(array_body):
        name = _extract_string_property(block, "name")
        if not name:
            continue
        description = _extract_string_property(block, "description") or f"Call Canva MCP tool {name}."
        input_schema, input_schema_source = _extract_input_schema(block)
        annotations = _extract_annotations(block)
        tools.append(
            {
                "name": name,
                "description": " ".join(description.split()),
                "input_schema": input_schema,
                "input_schema_source": input_schema_source,
                "annotations": annotations,
            }
        )
    if not tools:
        raise ValueError("no Canva MCP tools found in tools source")
    return tools


def build_openapi_contract(
    tools: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
    server_url: str = "http://localhost:8000",
    auth_mode: str = "both",
) -> dict[str, Any]:
    if auth_mode not in {"api-key", "bearer", "both"}:
        raise ValueError("auth_mode must be one of: api-key, bearer, both")
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    paths: dict[str, Any] = {}
    schema_refs: set[str] = set()
    security_requirements = _security_requirements(auth_mode)

    for tool in tools:
        schema = tool["input_schema"]
        schema_ref = _schema_ref_name(schema)
        if schema_ref:
            schema_refs.add(schema_ref)
        path = f"/{tool['name']}"
        paths[path] = {
            "post": {
                "operationId": f"call_{_operation_id(tool['name'])}",
                "summary": f"Call {tool['name']}",
                "description": tool["description"],
                "security": security_requirements,
                "x-mcp-tool-name": tool["name"],
                "x-mcp-input-schema-source": tool["input_schema_source"],
                "x-mcp-annotations": tool["annotations"],
                "requestBody": {
                    "required": _schema_requires_body(schema),
                    "content": {
                        "application/json": {
                            "schema": schema,
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "MCP tool call result",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/McpToolResult"}
                            }
                        },
                    },
                    "401": {"description": "Missing or invalid authorization"},
                    "500": {"description": "MCP tool execution failed"},
                },
            }
        }

    schemas = {
        "McpToolResult": {
            "type": "object",
            "description": "Raw MCP tool result payload returned by the proxy.",
            "additionalProperties": True,
        }
    }
    for schema_ref in sorted(schema_refs):
        schemas[schema_ref] = {
            "type": "object",
            "description": f"Schema referenced by Canva MCP tools.ts as {schema_ref}.",
            "additionalProperties": True,
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Canva MCP OpenAPI Contract",
            "version": "2026-06-05",
            "description": "Static OpenAPI contract derived from the tracked Canva MCP tool registry.",
            "x-generated-at": generated_at,
        },
        "servers": [
            {
                "url": server_url,
                "description": "mcpo-compatible proxy base URL for Canva MCP tools.",
            }
        ],
        "security": security_requirements,
        "paths": dict(sorted(paths.items())),
        "components": {
            "securitySchemes": _security_schemes(auth_mode),
            "schemas": schemas,
        },
    }


def summarize_contract(contract: dict[str, Any]) -> dict[str, Any]:
    operations = [
        operation
        for path_item in contract["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict)
    ]
    read_only = sum(1 for operation in operations if operation["x-mcp-annotations"].get("readOnlyHint") is True)
    destructive = sum(
        1 for operation in operations if operation["x-mcp-annotations"].get("destructiveHint") is True
    )
    schema_refs = sorted(
        schema_name
        for schema_name in contract["components"]["schemas"]
        if schema_name != "McpToolResult"
    )
    return {
        "openapi": contract["openapi"],
        "title": contract["info"]["title"],
        "generated_at": contract["info"]["x-generated-at"],
        "security_schemes": sorted(contract["components"]["securitySchemes"]),
        "tool_count": len(operations),
        "read_only_count": read_only,
        "destructive_count": destructive,
        "schema_ref_count": len(schema_refs),
        "schema_refs": schema_refs,
        "paths": sorted(contract["paths"]),
    }


def format_markdown(contract: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        "# Canva MCP OpenAPI Contract - 2026-06-05",
        "",
        "## Summary",
        "",
        f"- OpenAPI: `{summary['openapi']}`",
        f"- Tools: {summary['tool_count']}",
        f"- Read-only tools: {summary['read_only_count']}",
        f"- Destructive tools: {summary['destructive_count']}",
        f"- Schema refs: {summary['schema_ref_count']}",
        f"- Generated at: `{summary['generated_at']}`",
        "",
        "## Paths",
        "",
    ]
    lines.extend(f"- `{path}`" for path in summary["paths"])
    lines.extend(["", "## Security", ""])
    if "BearerAuth" in summary["security_schemes"]:
        lines.append("- Bearer auth header: `Authorization: Bearer <token>`")
    if "ApiKeyAuth" in summary["security_schemes"]:
        lines.append("- API key header: `X-API-Key`")
    lines.append("")
    return "\n".join(lines)


def run(
    *,
    tools_source: Path = DEFAULT_TOOLS_SOURCE,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    server_url: str = "http://localhost:8000",
    auth_mode: str = "both",
) -> dict[str, Any]:
    tools = extract_tools(load_tools_source(tools_source))
    contract = build_openapi_contract(tools, server_url=server_url, auth_mode=auth_mode)
    summary = summarize_contract(contract)
    if json_out is not None:
        _write_text_atomic(json_out, json.dumps(contract, indent=2, sort_keys=True) + "\n")
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(contract, summary))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Canva MCP OpenAPI contract from tools.ts.")
    parser.add_argument("--tools-source", type=Path, default=DEFAULT_TOOLS_SOURCE)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--server-url", default="http://localhost:8000")
    parser.add_argument("--auth-mode", choices=["api-key", "bearer", "both"], default="both")
    args = parser.parse_args(argv)
    try:
        summary = run(
            tools_source=args.tools_source,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
            server_url=args.server_url,
            auth_mode=args.auth_mode,
        )
    except (OSError, ValueError) as exc:
        print(f"canva mcp openapi contract failed: {exc}", file=sys.stderr)
        return 1
    print(f"canva mcp openapi contract valid: {summary['tool_count']} tools")
    return 0


def _security_requirements(auth_mode: str) -> list[dict[str, list[Any]]]:
    requirements: list[dict[str, list[Any]]] = []
    if auth_mode in {"bearer", "both"}:
        requirements.append({"BearerAuth": []})
    if auth_mode in {"api-key", "both"}:
        requirements.append({"ApiKeyAuth": []})
    return requirements


def _security_schemes(auth_mode: str) -> dict[str, dict[str, Any]]:
    schemes: dict[str, dict[str, Any]] = {}
    if auth_mode in {"bearer", "both"}:
        schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
        }
    if auth_mode in {"api-key", "both"}:
        schemes["ApiKeyAuth"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    return schemes


def _extract_tools_array_body(source_text: str) -> str:
    marker = "export const tools"
    marker_index = source_text.find(marker)
    if marker_index < 0:
        raise ValueError("tools export not found")
    equals_index = source_text.find("=", marker_index)
    if equals_index < 0:
        raise ValueError("tools array assignment not found")
    start = source_text.find("[", equals_index)
    if start < 0:
        raise ValueError("tools array start not found")
    end = _find_matching(source_text, start, "[", "]")
    return source_text[start + 1 : end]


def _split_top_level_objects(array_body: str) -> list[str]:
    blocks: list[str] = []
    start: int | None = None
    depth = 0
    index = 0
    while index < len(array_body):
        char = array_body[index]
        if char in {'"', "'", "`"}:
            index = _skip_string(array_body, index, char)
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(array_body[start : index + 1])
                start = None
        index += 1
    return blocks


def _extract_string_property(block: str, property_name: str) -> str | None:
    match = re.search(rf"\b{re.escape(property_name)}\s*:\s*([\"'`])", block)
    if not match:
        return None
    quote = match.group(1)
    value_start = match.end()
    value_end = _skip_string(block, match.start(1), quote) - 1
    return block[value_start:value_end]


def _extract_input_schema(block: str) -> tuple[dict[str, Any], str]:
    identifier_match = re.search(r"\binputSchema\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s+as\s+any", block)
    if identifier_match:
        schema_name = identifier_match.group(1)
        return {"$ref": f"#/components/schemas/{schema_name}"}, schema_name

    inline_match = re.search(r"\binputSchema\s*:\s*\{", block)
    if inline_match:
        return {"type": "object", "properties": {}, "additionalProperties": False}, "inline-object"

    return {"type": "object", "properties": {}, "additionalProperties": True}, "unknown"


def _extract_annotations(block: str) -> dict[str, bool]:
    annotations = {
        "destructiveHint": False,
        "openWorldHint": False,
        "readOnlyHint": False,
    }
    annotation_match = re.search(r"\bannotations\s*:\s*\{", block)
    if not annotation_match:
        return annotations
    start = annotation_match.end() - 1
    end = _find_matching(block, start, "{", "}")
    annotation_body = block[start + 1 : end]
    for key in annotations:
        value_match = re.search(rf"\b{key}\s*:\s*(true|false)", annotation_body)
        if value_match:
            annotations[key] = value_match.group(1) == "true"
    return annotations


def _schema_requires_body(schema: dict[str, Any]) -> bool:
    if "$ref" in schema:
        return True
    properties = schema.get("properties")
    if isinstance(properties, dict) and properties:
        return True
    return bool(schema.get("required"))


def _schema_ref_name(schema: dict[str, Any]) -> str | None:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/components/schemas/"):
        return None
    return ref.rsplit("/", 1)[-1]


def _operation_id(tool_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", tool_name).strip("_")


def _find_matching(text: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char in {'"', "'", "`"}:
            index = _skip_string(text, index, char)
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError(f"matching {close_char!r} not found")


def _skip_string(text: str, start: int, quote: str) -> int:
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index + 1
        index += 1
    raise ValueError("unterminated string literal")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
