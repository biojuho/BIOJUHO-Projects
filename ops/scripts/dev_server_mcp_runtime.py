from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, TextIO

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
MUTATION_ENV = "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dev_server_control as control  # noqa: E402
import dev_server_mcp_contract as contract_builder  # noqa: E402
import dev_server_status as status_probe  # noqa: E402


class ToolExecutionError(Exception):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get("message", payload.get("status", "tool execution failed"))))
        self.payload = payload


def load_contract() -> dict[str, Any]:
    payload = contract_builder.load_validated_manifest()
    return contract_builder.build_contract(payload)


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for tool in load_contract()["tools"]
    ]


def execute_tool(
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    allow_process_mutation: bool | None = None,
    state_dir: Path = control.DEFAULT_STATE_DIR,
    status_fetcher: status_probe.FetchFn | None = None,
) -> dict[str, Any]:
    args = dict(arguments or {})
    allow_mutation = process_mutation_allowed() if allow_process_mutation is None else allow_process_mutation
    payload = contract_builder.load_validated_manifest()

    if name == "get_devserver_statuses":
        _reject_unknown_arguments(
            args,
            {
                "target_ids",
                "timeout_seconds",
                "wait_ready",
                "wait_timeout_seconds",
                "poll_interval_seconds",
            },
        )
        target_ids = _target_ids(args.get("target_ids"))
        timeout = _float_arg(args, "timeout_seconds", 2.0, minimum=0.1)
        wait_ready = _bool_arg(args, "wait_ready", False)
        if wait_ready:
            return status_probe.wait_for_ready(
                payload,
                target_ids=target_ids,
                timeout=timeout,
                wait_timeout=_float_arg(args, "wait_timeout_seconds", 30.0),
                poll_interval=_float_arg(args, "poll_interval_seconds", 1.0),
                fetcher=status_fetcher,
            )
        return status_probe.build_report(payload, target_ids=target_ids, timeout=timeout, fetcher=status_fetcher)

    if name == "get_devserver_logs":
        _reject_unknown_arguments(args, {"target_id", "lines"})
        target_id = _required_target_id(payload, args)
        return control.tail_target(target_id, state_dir=state_dir, lines=_int_arg(args, "lines", 80, maximum=1000))

    if name == "start_server":
        _reject_unknown_arguments(
            args,
            {
                "target_id",
                "wait_ready",
                "wait_timeout_seconds",
                "poll_interval_seconds",
                "timeout_seconds",
                "start_dependencies",
                "reuse_ready",
                "append_logs",
            },
        )
        target_id = _required_target_id(payload, args)
        _require_process_mutation(name, allow_mutation)
        return control.start_target(
            payload,
            target_id,
            state_dir=state_dir,
            wait_ready=_bool_arg(args, "wait_ready", True),
            wait_timeout=_float_arg(args, "wait_timeout_seconds", 90.0),
            poll_interval=_float_arg(args, "poll_interval_seconds", 2.0),
            timeout=_float_arg(args, "timeout_seconds", 3.0, minimum=0.1),
            start_dependencies=_bool_arg(args, "start_dependencies", True),
            reuse_ready=_bool_arg(args, "reuse_ready", True),
            append_logs=_bool_arg(args, "append_logs", False),
        )

    if name == "stop_server":
        _reject_unknown_arguments(args, {"target_id", "include_dependencies", "timeout_seconds"})
        target_id = _required_target_id(payload, args)
        _require_process_mutation(name, allow_mutation)
        return control.stop_target(
            target_id,
            state_dir=state_dir,
            timeout=_float_arg(args, "timeout_seconds", 10.0),
            include_dependencies=_bool_arg(args, "include_dependencies", True),
        )

    raise ToolExecutionError(
        {
            "schema_version": 1,
            "status": "unknown_tool",
            "tool": name,
            "message": f"unknown dev-server MCP tool: {name}",
        }
    )


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return _jsonrpc_error(request_id, -32600, "invalid JSON-RPC request")
    if request_id is None and method.startswith("notifications/"):
        return None
    if method == "initialize":
        return _jsonrpc_success(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "local-dev-server-runtime", "version": "1.0.0"},
            },
        )
    if method == "ping":
        return _jsonrpc_success(request_id, {})
    if method == "tools/list":
        return _jsonrpc_success(request_id, {"tools": list_tools()})
    if method == "tools/call":
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _jsonrpc_error(request_id, -32602, "tools/call params must be an object")
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return _jsonrpc_error(request_id, -32602, "tools/call params.name must be a non-empty string")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _jsonrpc_error(request_id, -32602, "tools/call params.arguments must be an object")
        try:
            result = execute_tool(name, arguments)
        except ToolExecutionError as exc:
            return _jsonrpc_success(request_id, _tool_result(exc.payload, is_error=True))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            return _jsonrpc_success(
                request_id,
                _tool_result(
                    {
                        "schema_version": 1,
                        "status": "tool_error",
                        "tool": name,
                        "message": str(exc),
                    },
                    is_error=True,
                ),
            )
        return _jsonrpc_success(request_id, _tool_result(result, is_error=False))
    return _jsonrpc_error(request_id, -32601, f"method not found: {method}")


def serve(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        response = handle_line(line)
        if response is None:
            continue
        stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        stdout.flush()
    return 0


def handle_line(line: str) -> dict[str, Any] | None:
    line = line.lstrip("\ufeff")
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return _jsonrpc_error(None, -32700, f"parse error: {exc.msg}")
    if not isinstance(request, dict):
        return _jsonrpc_error(None, -32600, "invalid JSON-RPC request")
    return handle_request(request)


def process_mutation_allowed() -> bool:
    return os.environ.get(MUTATION_ENV, "").strip().lower() in TRUTHY_ENV_VALUES


def _tool_result(payload: dict[str, Any], *, is_error: bool) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, indent=2, ensure_ascii=False),
            }
        ],
        "structuredContent": payload,
        "isError": is_error,
    }


def _require_process_mutation(tool_name: str, allowed: bool) -> None:
    if allowed:
        return
    raise ToolExecutionError(
        {
            "schema_version": 1,
            "status": "process_mutation_disabled",
            "tool": tool_name,
            "enable_env": MUTATION_ENV,
            "message": f"{tool_name} is disabled until {MUTATION_ENV}=true is set in the local environment.",
        }
    )


def _required_target_id(payload: dict[str, Any], args: dict[str, Any]) -> str:
    value = args.get("target_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("target_id must be a non-empty string")
    target_id = value.strip()
    status_probe.select_targets(payload, [target_id])
    return target_id


def _target_ids(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("target_ids must be an array of non-empty strings")
    return [item.strip() for item in value]


def _reject_unknown_arguments(args: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(args) - allowed)
    if unknown:
        raise ValueError(f"unsupported argument(s): {', '.join(unknown)}")


def _bool_arg(args: dict[str, Any], key: str, default: bool) -> bool:
    value = args.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _float_arg(args: dict[str, Any], key: str, default: float, *, minimum: float = 0.0) -> float:
    value = args.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    if float(value) < minimum:
        raise ValueError(f"{key} must be at least {minimum}")
    return float(value)


def _int_arg(args: dict[str, Any], key: str, default: int, *, maximum: int | None = None) -> int:
    value = args.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value < 0:
        raise ValueError(f"{key} must be non-negative")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} must be at most {maximum}")
    return value


def _jsonrpc_success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Run the local dev-server MCP stdio runtime.")
    parser.add_argument("--once", action="store_true", help="Read one JSON-RPC request from stdin, write one response, and exit.")
    args = parser.parse_args(argv)
    if args.once:
        line = sys.stdin.readline()
        if not line:
            return 0
        response = handle_line(line.strip())
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
