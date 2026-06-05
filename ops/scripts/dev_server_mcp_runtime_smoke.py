from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
RUNTIME_SCRIPT = WORKSPACE_ROOT / "ops" / "scripts" / "dev_server_mcp_runtime.py"
EXPECTED_TOOLS = {
    "get_devserver_statuses",
    "get_devserver_policy",
    "start_server",
    "stop_server",
    "get_devserver_logs",
}


def build_requests() -> list[dict[str, Any]]:
    return [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_devserver_policy",
                "arguments": {},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "start_server",
                "arguments": {"target_id": "dashboard-api", "wait_ready": False},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "missing_tool",
                "arguments": {},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_devserver_logs",
                "arguments": {"target_id": "dashboard-api", "lines": 0},
            },
        },
    ]


def run_smoke(*, timeout_seconds: float = 10.0, python_exe: str = sys.executable) -> dict[str, Any]:
    requests = build_requests()
    process = subprocess.run(
        [python_exe, str(RUNTIME_SCRIPT)],
        cwd=WORKSPACE_ROOT,
        input="\n".join(json.dumps(request, separators=(",", ":")) for request in requests) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    raw_lines = [line for line in process.stdout.splitlines() if line.strip()]
    responses = _parse_responses(raw_lines)
    errors = validate_responses(responses, process.returncode, process.stderr)
    summary = summarize_responses(responses)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass" if not errors else "fail",
        "runtime": "ops/scripts/dev_server_mcp_runtime.py",
        "request_count": len(requests),
        "response_count": len(responses),
        "process_returncode": process.returncode,
        "stderr": process.stderr.strip(),
        "summary": summary,
        "errors": errors,
    }


def validate_responses(responses: list[dict[str, Any]], returncode: int, stderr: str) -> list[str]:
    errors: list[str] = []
    if returncode != 0:
        errors.append(f"runtime exited with return code {returncode}")
    if stderr.strip():
        errors.append("runtime wrote to stderr")
    if len(responses) != 6:
        errors.append(f"expected 6 responses, got {len(responses)}")
        return errors

    for expected_id, response in enumerate(responses, start=1):
        if response.get("jsonrpc") != "2.0":
            errors.append(f"response {expected_id} jsonrpc must be 2.0")
        if response.get("id") != expected_id:
            errors.append(f"response {expected_id} id mismatch")
        if "error" in response:
            errors.append(f"response {expected_id} returned JSON-RPC error: {response['error']}")

    initialize = _result(responses[0])
    if initialize.get("serverInfo", {}).get("name") != "local-dev-server-runtime":
        errors.append("initialize response must identify local-dev-server-runtime")
    if initialize.get("capabilities") != {"tools": {}}:
        errors.append("initialize response must advertise tools capability")

    tools = _tools_from_response(responses[1])
    if tools != EXPECTED_TOOLS:
        errors.append(f"tools/list mismatch: {sorted(tools)}")

    policy_result = _result(responses[2])
    policy_payload = policy_result.get("structuredContent", {})
    if policy_result.get("isError") is not False:
        errors.append("get_devserver_policy must succeed without process mutation")
    if policy_payload.get("runtime_status") != "local_stdio_runtime":
        errors.append("get_devserver_policy runtime_status mismatch")
    if policy_payload.get("process_mutation", {}).get("default") != "disabled":
        errors.append("get_devserver_policy process mutation default mismatch")
    if policy_payload.get("non_local_control", {}).get("status") != "unsupported":
        errors.append("get_devserver_policy non-local control status mismatch")

    start_result = _result(responses[3])
    start_payload = start_result.get("structuredContent", {})
    if start_result.get("isError") is not True:
        errors.append("start_server must return an MCP tool error when mutation is disabled")
    if start_payload.get("status") != "process_mutation_disabled":
        errors.append("start_server mutation guard status mismatch")
    if start_payload.get("enable_env") != "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION":
        errors.append("start_server mutation guard env mismatch")

    unknown_tool_result = _result(responses[4])
    unknown_tool_payload = unknown_tool_result.get("structuredContent", {})
    if unknown_tool_result.get("isError") is not True:
        errors.append("unknown tools/call must return an MCP tool error")
    if unknown_tool_payload.get("status") != "unknown_tool":
        errors.append("unknown tools/call status mismatch")

    logs_result = _result(responses[5])
    logs_payload = logs_result.get("structuredContent", {})
    if logs_result.get("isError") is not False:
        errors.append("get_devserver_logs must succeed after a prior MCP tool error")
    if logs_payload.get("schema_version") != 1:
        errors.append("get_devserver_logs payload schema_version must be 1")
    if logs_payload.get("target_id") != "dashboard-api":
        errors.append("get_devserver_logs target_id mismatch")
    return errors


def summarize_responses(responses: list[dict[str, Any]]) -> dict[str, Any]:
    tools = _tools_from_response(responses[1]) if len(responses) > 1 else set()
    policy_payload = _result(responses[2]).get("structuredContent", {}) if len(responses) > 2 else {}
    mutation_payload = _result(responses[3]).get("structuredContent", {}) if len(responses) > 3 else {}
    unknown_tool_payload = _result(responses[4]).get("structuredContent", {}) if len(responses) > 4 else {}
    logs_payload = _result(responses[5]).get("structuredContent", {}) if len(responses) > 5 else {}
    return {
        "tool_count": len(tools),
        "tools": sorted(tools),
        "policy_runtime_status": policy_payload.get("runtime_status"),
        "policy_non_local_control": policy_payload.get("non_local_control", {}).get("status"),
        "policy_process_mutation_default": policy_payload.get("process_mutation", {}).get("default"),
        "mutation_guard_status": mutation_payload.get("status"),
        "mutation_guard_env": mutation_payload.get("enable_env"),
        "unknown_tool_error_status": unknown_tool_payload.get("status"),
        "post_error_logs_target_id": logs_payload.get("target_id"),
        "logs_target_id": logs_payload.get("target_id"),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    details = summary["summary"]
    lines = [
        "# Dev-Server MCP Runtime Smoke",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Status: `{summary['status']}`",
        f"- Runtime: `{summary['runtime']}`",
        f"- Requests: `{summary['request_count']}`",
        f"- Responses: `{summary['response_count']}`",
        f"- Tools: `{details['tool_count']}`",
        f"- Policy runtime: `{details.get('policy_runtime_status')}`",
        f"- Non-local control: `{details.get('policy_non_local_control')}`",
        f"- Policy process mutation default: `{details.get('policy_process_mutation_default')}`",
        f"- Mutation guard: `{details.get('mutation_guard_status')}` via `{details.get('mutation_guard_env')}`",
        f"- Unknown tool error: `{details.get('unknown_tool_error_status')}`",
        f"- Post-error log target: `{details.get('post_error_logs_target_id')}`",
        f"- Log target: `{details.get('logs_target_id')}`",
        "",
        "## Tools",
        "",
    ]
    lines.extend(f"- `{tool}`" for tool in details["tools"])
    lines.extend(["", "## Errors", ""])
    if summary["errors"]:
        lines.extend(f"- {error}" for error in summary["errors"])
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _parse_responses(raw_lines: list[str]) -> list[dict[str, Any]]:
    responses = []
    for index, line in enumerate(raw_lines, start=1):
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            responses.append({"jsonrpc": "2.0", "id": index, "error": {"code": -32700, "message": exc.msg}})
            continue
        responses.append(response if isinstance(response, dict) else {"jsonrpc": "2.0", "id": index, "error": {}})
    return responses


def _result(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    return result if isinstance(result, dict) else {}


def _tools_from_response(response: dict[str, Any]) -> set[str]:
    result = _result(response)
    tools = result.get("tools", [])
    if not isinstance(tools, list):
        return set()
    return {tool["name"] for tool in tools if isinstance(tool, dict) and isinstance(tool.get("name"), str)}


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the local dev-server MCP stdio runtime.")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    try:
        summary = run_smoke(timeout_seconds=args.timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"dev-server MCP runtime smoke failed: {exc}", file=sys.stderr)
        return 1
    if args.json_out:
        write_json_atomic(args.json_out, summary)
    if args.markdown_out:
        write_text_atomic(args.markdown_out, render_markdown(summary))
    if summary["errors"]:
        print("dev-server MCP runtime smoke failed:", file=sys.stderr)
        for error in summary["errors"]:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "dev-server MCP runtime smoke valid: "
        f"{summary['request_count']} requests, "
        f"{summary['summary']['tool_count']} tools, "
        f"mutation_guard={summary['summary']['mutation_guard_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
