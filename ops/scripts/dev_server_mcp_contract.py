from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_MANIFEST = WORKSPACE_ROOT / "ops" / "references" / "dev_server_targets.json"
SOURCE_URL = "https://github.com/Uninen/devserver-mcp"
GATEWAY_SOURCE_URL = "https://github.com/microsoft/mcp-gateway"
OBSERVED_SOURCE_TOOLS = [
    "start_server",
    "stop_server",
    "get_devserver_statuses",
    "get_devserver_logs",
]
LOCAL_POLICY_TOOL = "get_devserver_policy"
REQUIRED_TOOL_NAMES = set(OBSERVED_SOURCE_TOOLS) | {LOCAL_POLICY_TOOL}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dev_server_status as status_probe  # noqa: E402


def load_validated_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = status_probe.load_manifest(path)
    errors = status_probe.validate_manifest(payload, workspace_root=WORKSPACE_ROOT)
    if errors:
        raise ValueError("\n".join(errors))
    return payload


def build_contract(payload: dict[str, Any]) -> dict[str, Any]:
    targets = status_probe.select_targets(payload)
    target_ids = [target["id"] for target in targets]
    compact_targets = [
        {
            "id": target["id"],
            "label": target["label"],
            "project": target["project"],
            "kind": target["kind"],
            "url": target["url"],
            "depends_on": target.get("depends_on", []),
            "smoke_scope": target.get("smoke_scope"),
            "tags": target.get("tags", []),
        }
        for target in targets
    ]
    tools = [
        build_status_tool(target_ids),
        build_policy_tool(),
        build_start_tool(target_ids),
        build_stop_tool(target_ids),
        build_logs_tool(target_ids),
    ]
    safety_counts = Counter(tool["safety"] for tool in tools)
    policy = build_operator_policy(tools)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "repo": "Uninen/devserver-mcp",
            "url": SOURCE_URL,
            "observed_tools": OBSERVED_SOURCE_TOOLS,
            "observed_pattern": "MCP tools for dev-server start, stop, status, logs, and browser-assisted workflows.",
            "companion_sources": [
                {
                    "repo": "microsoft/mcp-gateway",
                    "url": GATEWAY_SOURCE_URL,
                    "observed_pattern": "MCP routing, authorization, lifecycle management, and observability policy are first-class gateway concerns.",
                }
            ],
        },
        "runtime": {
            "status": "local_stdio_runtime",
            "entrypoint": "python ops/scripts/dev_server_mcp_runtime.py",
            "process_mutation_default": "disabled",
            "process_mutation_enable_env": "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION",
            "reason": "A local stdio runtime exposes the contract. Read-only tools are enabled by default; start/stop require an explicit local environment opt-in.",
        },
        "operator_policy": policy,
        "local_cli": {
            "status_script": "ops/scripts/dev_server_status.py",
            "control_script": "ops/scripts/dev_server_control.py",
            "manifest": "ops/references/dev_server_targets.json",
        },
        "summary": {
            "target_count": len(targets),
            "tool_count": len(tools),
            "read_only_tools": safety_counts.get("read_only", 0),
            "process_mutating_tools": safety_counts.get("process_mutating", 0),
        },
        "targets": compact_targets,
        "tools": tools,
    }


def build_operator_policy(tools: list[dict[str, Any]]) -> dict[str, Any]:
    read_only_tools = sorted(tool["name"] for tool in tools if tool["safety"] == "read_only")
    process_mutating_tools = sorted(tool["name"] for tool in tools if tool["safety"] == "process_mutating")
    return {
        "schema_version": 1,
        "runtime_status": "local_stdio_runtime",
        "transport": "stdio",
        "network_exposure": "none",
        "local_only": True,
        "non_local_control": {
            "status": "unsupported",
            "reason": "The dev-server MCP runtime is intentionally stdio-only. Non-local process control needs a separate operator-owned authentication and gateway policy.",
        },
        "process_mutation": {
            "default": "disabled",
            "enable_env": "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION",
            "read_only_tools": read_only_tools,
            "process_mutating_tools": process_mutating_tools,
        },
        "source_patterns": [
            {
                "repo": "Uninen/devserver-mcp",
                "url": SOURCE_URL,
                "pattern": "Expose status, logs, start, and stop as MCP tools for local development servers.",
            },
            {
                "repo": "microsoft/mcp-gateway",
                "url": GATEWAY_SOURCE_URL,
                "pattern": "Keep routing, authorization, lifecycle management, and observability policy explicit before widening MCP server exposure.",
            },
        ],
    }


def build_status_tool(target_ids: list[str]) -> dict[str, Any]:
    return {
        "name": "get_devserver_statuses",
        "description": "Return readiness status for all or selected local development server targets.",
        "safety": "read_only",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "target_ids": {
                    "type": "array",
                    "items": {"type": "string", "enum": target_ids},
                    "uniqueItems": True,
                    "description": "Optional target ids to probe. Omit to probe every configured target.",
                },
                "timeout_seconds": {"type": "number", "minimum": 0.1, "default": 2.0},
                "wait_ready": {"type": "boolean", "default": False},
                "wait_timeout_seconds": {"type": "number", "minimum": 0.0, "default": 30.0},
                "poll_interval_seconds": {"type": "number", "minimum": 0.0, "default": 1.0},
            },
        },
        "command_template": ["python", "ops/scripts/dev_server_status.py", "--format", "json"],
        "argument_mapping": {
            "target_ids": {"repeat_flag": "--target"},
            "timeout_seconds": {"flag": "--timeout"},
            "wait_ready": {"flag": "--wait-ready", "when_true": True},
            "wait_timeout_seconds": {"flag": "--wait-timeout"},
            "poll_interval_seconds": {"flag": "--poll-interval"},
        },
        "output_contract": "dev_server_status schema_version=1 JSON report",
    }


def build_policy_tool() -> dict[str, Any]:
    return {
        "name": LOCAL_POLICY_TOOL,
        "description": "Return the local dev-server MCP runtime access, process-mutation, and non-local-control policy.",
        "safety": "read_only",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
        "command_template": ["python", "ops/scripts/dev_server_mcp_runtime.py", "--policy"],
        "argument_mapping": {},
        "output_contract": "operator_policy schema_version=1 JSON policy",
    }


def build_start_tool(target_ids: list[str]) -> dict[str, Any]:
    return {
        "name": "start_server",
        "description": "Start a configured local development server target, optionally waiting for readiness.",
        "safety": "process_mutating",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target_id"],
            "properties": {
                "target_id": {"type": "string", "enum": target_ids},
                "wait_ready": {"type": "boolean", "default": True},
                "wait_timeout_seconds": {"type": "number", "minimum": 0.0, "default": 90.0},
                "poll_interval_seconds": {"type": "number", "minimum": 0.0, "default": 2.0},
                "timeout_seconds": {"type": "number", "minimum": 0.1, "default": 3.0},
                "start_dependencies": {"type": "boolean", "default": True},
                "reuse_ready": {"type": "boolean", "default": True},
                "append_logs": {"type": "boolean", "default": False},
            },
        },
        "command_template": ["python", "ops/scripts/dev_server_control.py", "start", "--target", "{target_id}"],
        "argument_mapping": {
            "target_id": {"flag": "--target", "required": True},
            "wait_ready": {"flag": "--wait-ready", "when_true": True},
            "wait_timeout_seconds": {"flag": "--wait-timeout"},
            "poll_interval_seconds": {"flag": "--poll-interval"},
            "timeout_seconds": {"flag": "--timeout"},
            "start_dependencies": {"flag": "--no-start-dependencies", "when_false": True},
            "reuse_ready": {"flag": "--no-reuse-ready", "when_false": True},
            "append_logs": {"flag": "--append-logs", "when_true": True},
        },
        "output_contract": "dev_server_control start JSON state when --json-out is supplied",
    }


def build_stop_tool(target_ids: list[str]) -> dict[str, Any]:
    return {
        "name": "stop_server",
        "description": "Stop a managed local development server target, optionally stopping recorded dependencies.",
        "safety": "process_mutating",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target_id"],
            "properties": {
                "target_id": {"type": "string", "enum": target_ids},
                "include_dependencies": {"type": "boolean", "default": True},
                "timeout_seconds": {"type": "number", "minimum": 0.0, "default": 10.0},
            },
        },
        "command_template": ["python", "ops/scripts/dev_server_control.py", "stop", "--target", "{target_id}"],
        "argument_mapping": {
            "target_id": {"flag": "--target", "required": True},
            "include_dependencies": {"flag": "--include-dependencies", "when_true": True},
            "timeout_seconds": {"flag": "--timeout"},
        },
        "output_contract": "dev_server_control stop JSON state when --json-out is supplied",
    }


def build_logs_tool(target_ids: list[str]) -> dict[str, Any]:
    return {
        "name": "get_devserver_logs",
        "description": "Return recent stdout and stderr lines for a managed local development server target.",
        "safety": "read_only",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target_id"],
            "properties": {
                "target_id": {"type": "string", "enum": target_ids},
                "lines": {"type": "integer", "minimum": 0, "maximum": 1000, "default": 80},
            },
        },
        "command_template": ["python", "ops/scripts/dev_server_control.py", "tail", "--target", "{target_id}"],
        "argument_mapping": {
            "target_id": {"flag": "--target", "required": True},
            "lines": {"flag": "--lines"},
        },
        "output_contract": "dev_server_control tail JSON logs when --json-out is supplied",
    }


def validate_contract(contract: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != 1 or isinstance(contract.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    tools = contract.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("tools must be a non-empty array")
        return errors

    target_ids = [target["id"] for target in status_probe.select_targets(payload)]
    target_id_set = set(target_ids)
    names: list[str] = []
    for index, tool in enumerate(tools):
        prefix = f"tools[{index}]"
        if not isinstance(tool, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"{prefix}.name must be a non-empty string")
        else:
            names.append(name)
        if tool.get("safety") not in {"read_only", "process_mutating"}:
            errors.append(f"{prefix}.safety must be read_only or process_mutating")
        input_schema = tool.get("inputSchema")
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            errors.append(f"{prefix}.inputSchema must be an object schema")
        else:
            properties = input_schema.get("properties", {})
            if not isinstance(properties, dict):
                errors.append(f"{prefix}.inputSchema.properties must be an object")
            target_property = properties.get("target_id")
            if target_property is not None:
                enum = target_property.get("enum") if isinstance(target_property, dict) else None
                if set(enum or []) != target_id_set:
                    errors.append(f"{prefix}.inputSchema.properties.target_id.enum must match manifest targets")
            target_ids_property = properties.get("target_ids")
            if target_ids_property is not None:
                items = target_ids_property.get("items", {}) if isinstance(target_ids_property, dict) else {}
                enum = items.get("enum") if isinstance(items, dict) else None
                if set(enum or []) != target_id_set:
                    errors.append(f"{prefix}.inputSchema.properties.target_ids.items.enum must match manifest targets")
        command_template = tool.get("command_template")
        if not isinstance(command_template, list) or not command_template:
            errors.append(f"{prefix}.command_template must be a non-empty array")
        else:
            for item_index, item in enumerate(command_template):
                if not isinstance(item, str) or not item:
                    errors.append(f"{prefix}.command_template[{item_index}] must be a non-empty string")
                elif any(separator in item for separator in ("&&", "||", ";")):
                    errors.append(f"{prefix}.command_template[{item_index}] must not include shell separators")

    duplicate_names = [name for name, count in Counter(names).items() if count > 1]
    for name in duplicate_names:
        errors.append(f"tool name must be unique: {name}")
    missing = sorted(REQUIRED_TOOL_NAMES - set(names))
    for name in missing:
        errors.append(f"required source tool missing: {name}")
    return errors


def render_markdown(contract: dict[str, Any]) -> str:
    summary = contract["summary"]
    lines = [
        "# Dev-Server MCP Tool Contract",
        "",
        f"- Generated at: `{contract['generated_at']}`",
        f"- Source: `{contract['source']['repo']}` ({contract['source']['url']})",
        f"- Runtime status: `{contract['runtime']['status']}`",
        f"- Targets: `{summary['target_count']}`",
        f"- Tools: `{summary['tool_count']}`",
        f"- Read-only tools: `{summary['read_only_tools']}`",
        f"- Process-mutating tools: `{summary['process_mutating_tools']}`",
        "",
        "## Tools",
        "",
    ]
    for tool in contract["tools"]:
        required = tool["inputSchema"].get("required", [])
        lines.extend(
            [
                f"### {tool['name']}",
                "",
                f"- Safety: `{tool['safety']}`",
                f"- Required inputs: `{', '.join(required) if required else 'none'}`",
                f"- Command template: `{' '.join(tool['command_template'])}`",
                f"- Output contract: {tool['output_contract']}",
                "",
            ]
        )
    lines.extend(["## Targets", ""])
    for target in contract["targets"]:
        lines.extend(
            [
                f"- `{target['id']}`: {target['label']} ({target['project']}/{target['kind']})",
            ]
        )
    lines.extend(
        [
            "",
            "## Operator Policy",
            "",
            f"- Transport: `{contract['operator_policy']['transport']}`",
            f"- Network exposure: `{contract['operator_policy']['network_exposure']}`",
            f"- Non-local control: `{contract['operator_policy']['non_local_control']['status']}`",
            f"- Process mutation default: `{contract['operator_policy']['process_mutation']['default']}`",
            "",
            "## Boundary",
            "",
            "A local stdio runtime is available at `python ops/scripts/dev_server_mcp_runtime.py`.",
            "Read-only status, policy, and log tools are enabled by default. Process-mutating start/stop tools require `DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION=true` in the local environment.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


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
    parser = argparse.ArgumentParser(description="Generate a dev-server MCP tool contract from local targets.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = load_validated_manifest(args.manifest)
        contract = build_contract(payload)
        errors = validate_contract(contract, payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"dev-server MCP contract failed: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("dev-server MCP contract invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if args.json_out:
        write_json_atomic(args.json_out, contract)
    if args.markdown_out:
        write_text_atomic(args.markdown_out, render_markdown(contract))
    print(
        "dev-server MCP contract valid: "
        f"{contract['summary']['tool_count']} tools, "
        f"{contract['summary']['target_count']} targets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
