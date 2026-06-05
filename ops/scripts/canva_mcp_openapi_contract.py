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
DEFAULT_TOOLS = WORKSPACE_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "tools.ts"
OPENAI_META_KEY_PATTERN = re.compile(r'"(openai/[^"]+)"\s*:')


def extract_tool_blocks(source: str) -> list[str]:
    tools_start = source.find("export const tools")
    if tools_start < 0:
        raise ValueError("could not find exported tools array")
    resources_start = source.find("//", tools_start + 1)
    while resources_start > 0 and "Resources" not in source[resources_start : resources_start + 120]:
        resources_start = source.find("//", resources_start + 1)
    body = source[tools_start:resources_start] if resources_start > 0 else source[tools_start:]
    blocks = re.findall(r"\{\s*name:\s*\"[^\"]+\".*?\n\s*\},", body, flags=re.DOTALL)
    if not blocks:
        raise ValueError("could not parse any tool blocks")
    return blocks


def extract_widget_meta_keys(source: str) -> list[str]:
    widget_start = source.find("export function widgetMeta")
    if widget_start < 0:
        return []
    widget_end = source.find("//", widget_start + 1)
    body = source[widget_start:widget_end] if widget_end > 0 else source[widget_start:]
    return _openai_meta_keys_from_text(body)


def parse_tools(path: Path = DEFAULT_TOOLS) -> list[dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    widget_meta_keys = extract_widget_meta_keys(source)
    tools: list[dict[str, Any]] = []
    for block in extract_tool_blocks(source):
        name_match = re.search(r"name:\s*\"([^\"]+)\"", block)
        if not name_match:
            continue
        description_match = re.search(r"description:\s*(?:`(?P<template>.*?)`|\"(?P<double>.*?)\"|'(?P<single>.*?)')", block, re.DOTALL)
        schema_match = re.search(r"inputSchema:\s*([A-Za-z0-9_]+)Schema", block)
        read_only = "readOnlyHint: true" in block
        destructive = "destructiveHint: true" in block
        description = ""
        if description_match:
            description = next(group for group in description_match.groups() if group is not None)
            description = " ".join(description.split())
        openai_meta_keys = _openai_meta_keys_for_block(block, widget_meta_keys)
        tools.append(
            {
                "name": name_match.group(1),
                "description": description,
                "schema_ref": f"{schema_match.group(1)}Schema" if schema_match else "",
                "read_only": read_only,
                "destructive": destructive,
                "openai_meta_keys": openai_meta_keys,
            }
        )
    if not tools:
        raise ValueError("tools array did not contain parseable tools")
    return tools


def _openai_meta_keys_for_block(block: str, widget_meta_keys: list[str]) -> list[str]:
    keys = _openai_meta_keys_from_text(block)
    if "_meta: widgetMeta(" in block:
        keys.extend(widget_meta_keys)
    return list(dict.fromkeys(keys))


def _openai_meta_keys_from_text(text: str) -> list[str]:
    return list(dict.fromkeys(OPENAI_META_KEY_PATTERN.findall(text)))


def build_openapi(tools: list[dict[str, Any]]) -> dict[str, Any]:
    tool_names = [tool["name"] for tool in tools]
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Canva MCP OpenAPI Interop Contract",
            "version": "2026-06-04",
            "description": "Offline OpenAPI-compatible contract for the Canva MCP tool surface. This does not expose a live HTTP proxy by itself.",
        },
        "servers": [
            {
                "url": "http://localhost:8001/openapi-proxy",
                "description": "Placeholder local proxy URL for future MCP-to-OpenAPI runtime exposure.",
            }
        ],
        "paths": {
            "/tools": {
                "get": {
                    "summary": "List Canva MCP tools",
                    "operationId": "listCanvaMcpTools",
                    "responses": {
                        "200": {
                            "description": "Available Canva MCP tools",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "tools": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/CanvaMcpTool"},
                                            }
                                        },
                                        "required": ["tools"],
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/tools/{toolName}/call": {
                "post": {
                    "summary": "Call a Canva MCP tool through an OpenAPI-compatible proxy",
                    "operationId": "callCanvaMcpTool",
                    "parameters": [
                        {
                            "name": "toolName",
                            "in": "path",
                            "required": True,
                            "schema": {"$ref": "#/components/schemas/CanvaMcpToolName"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"arguments": {"type": "object", "additionalProperties": True}},
                                    "required": ["arguments"],
                                    "additionalProperties": False,
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "MCP tool result envelope",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "toolName": {"$ref": "#/components/schemas/CanvaMcpToolName"},
                                            "result": {"type": "object", "additionalProperties": True},
                                        },
                                        "required": ["toolName", "result"],
                                    }
                                }
                            },
                        },
                        "401": {"description": "Canva OAuth is missing or expired"},
                        "502": {"description": "MCP server or Canva API call failed"},
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "CanvaMcpToolName": {"type": "string", "enum": tool_names},
                "CanvaMcpTool": {
                    "type": "object",
                    "properties": {
                        "name": {"$ref": "#/components/schemas/CanvaMcpToolName"},
                        "description": {"type": "string"},
                        "schemaRef": {"type": "string"},
                        "readOnly": {"type": "boolean"},
                        "destructive": {"type": "boolean"},
                        "openAiMetaKeys": {
                            "type": "array",
                            "items": {"type": "string", "pattern": "^openai/"},
                        },
                    },
                    "required": [
                        "name",
                        "description",
                        "schemaRef",
                        "readOnly",
                        "destructive",
                        "openAiMetaKeys",
                    ],
                },
            }
        },
        "x-generated-at": generated_at,
        "x-mcp-tools": [
            {
                "name": tool["name"],
                "description": tool["description"],
                "schemaRef": tool["schema_ref"],
                "readOnly": tool["read_only"],
                "destructive": tool["destructive"],
                "openAiMetaKeys": tool["openai_meta_keys"],
            }
            for tool in tools
        ],
    }


def validate_openapi(spec: dict[str, Any], tools: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if spec.get("openapi") != "3.1.0":
        errors.append("openapi must be 3.1.0")
    paths = spec.get("paths")
    if not isinstance(paths, dict) or "/tools" not in paths or "/tools/{toolName}/call" not in paths:
        errors.append("spec must define /tools and /tools/{toolName}/call")
    tool_enum = (
        spec.get("components", {})
        .get("schemas", {})
        .get("CanvaMcpToolName", {})
        .get("enum", [])
    )
    expected_names = [tool["name"] for tool in tools]
    if tool_enum != expected_names:
        errors.append("CanvaMcpToolName enum must match parsed tool order")
    extension = spec.get("x-mcp-tools")
    if not isinstance(extension, list) or len(extension) != len(tools):
        errors.append("x-mcp-tools must include every parsed MCP tool")
    elif [
        item.get("openAiMetaKeys")
        for item in extension
    ] != [tool["openai_meta_keys"] for tool in tools]:
        errors.append("x-mcp-tools must preserve OpenAI namespaced metadata keys")
    return errors


def summarize(tools: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    openai_meta_keys = sorted({key for tool in tools for key in tool["openai_meta_keys"]})
    return {
        "schema_version": 1,
        "generated_at": spec["x-generated-at"],
        "tool_count": len(tools),
        "read_only_count": sum(1 for tool in tools if tool["read_only"]),
        "destructive_count": sum(1 for tool in tools if tool["destructive"]),
        "openai_meta_tool_count": sum(1 for tool in tools if tool["openai_meta_keys"]),
        "openai_meta_keys": openai_meta_keys,
        "paths": sorted(spec["paths"]),
        "tools": tools,
    }


def format_markdown(summary: dict[str, Any], spec_path: Path | None) -> str:
    lines = [
        "# Canva MCP OpenAPI Interop Contract - 2026-06-04",
        "",
        "## Summary",
        "",
        f"- Tools parsed: {summary['tool_count']}",
        f"- Read-only tools: {summary['read_only_count']}",
        f"- Destructive tools: {summary['destructive_count']}",
        f"- Tools with OpenAI namespaced metadata: {summary['openai_meta_tool_count']}",
        f"- OpenAI metadata keys: {', '.join(summary['openai_meta_keys']) or 'none'}",
        f"- Paths: {', '.join(summary['paths'])}",
        f"- Generated at: `{summary['generated_at']}`",
    ]
    if spec_path is not None:
        lines.append(f"- OpenAPI JSON: `{spec_path.as_posix()}`")
    lines.extend(["", "## Tool Surface", ""])
    for tool in summary["tools"]:
        flags = []
        if tool["read_only"]:
            flags.append("read-only")
        if tool["destructive"]:
            flags.append("destructive")
        flag_text = ", ".join(flags) if flags else "write-capable"
        meta_text = ", ".join(tool["openai_meta_keys"]) if tool["openai_meta_keys"] else "none"
        lines.append(f"- `{tool['name']}` ({flag_text}); OpenAI metadata: {meta_text}")
    lines.extend(
        [
            "",
            "## Operating Decision",
            "",
            "This is an offline interoperability contract. It records the OpenAPI shape a future MCP-to-OpenAPI proxy must satisfy, but it does not claim that a live HTTP proxy is deployed.",
            "",
        ]
    )
    return "\n".join(lines)


def run(tools_path: Path, *, openapi_out: Path | None = None, summary_out: Path | None = None, markdown_out: Path | None = None) -> dict[str, Any]:
    tools = parse_tools(tools_path)
    spec = build_openapi(tools)
    errors = validate_openapi(spec, tools)
    if errors:
        raise ValueError("\n".join(errors))
    summary = summarize(tools, spec)
    if openapi_out is not None:
        _write_json_atomic(openapi_out, spec)
    if summary_out is not None:
        _write_json_atomic(summary_out, summary)
    if markdown_out is not None:
        _write_text_atomic(markdown_out, format_markdown(summary, openapi_out))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an OpenAPI-compatible contract for Canva MCP tools.")
    parser.add_argument("--tools", type=Path, default=DEFAULT_TOOLS)
    parser.add_argument("--openapi-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run(args.tools, openapi_out=args.openapi_out, summary_out=args.summary_out, markdown_out=args.markdown_out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"canva MCP OpenAPI contract failed: {exc}", file=sys.stderr)
        return 1
    print(
        "canva MCP OpenAPI contract valid: "
        f"{summary['tool_count']} tools, read_only={summary['read_only_count']}, destructive={summary['destructive_count']}"
    )
    return 0


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
