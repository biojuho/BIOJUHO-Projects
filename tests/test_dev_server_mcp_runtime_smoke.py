from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "dev_server_mcp_runtime_smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("dev_server_mcp_runtime_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_subprocess_smoke_passes(tmp_path: Path) -> None:
    smoke = load_smoke_module()
    json_out = tmp_path / "mcp-runtime-smoke.json"
    markdown_out = tmp_path / "mcp-runtime-smoke.md"

    result = smoke.main(["--json-out", str(json_out), "--markdown-out", str(markdown_out), "--timeout", "10"])

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert payload["status"] == "pass"
    assert payload["execution_mode"] == "subprocess"
    assert payload["request_count"] == 6
    assert payload["summary"]["tool_count"] == 5
    assert payload["summary"]["policy_runtime_status"] == "local_stdio_runtime"
    assert payload["summary"]["policy_non_local_control"] == "unsupported"
    assert payload["summary"]["policy_process_mutation_default"] == "disabled"
    assert payload["summary"]["mutation_guard_status"] == "process_mutation_disabled"
    assert payload["summary"]["unknown_tool_error_status"] == "unknown_tool"
    assert payload["summary"]["post_error_logs_target_id"] == "dashboard-api"
    assert "Dev-Server MCP Runtime Smoke" in markdown
    assert "Execution mode: `subprocess`" in markdown
    assert "Unknown tool error" in markdown
    assert "Post-error log target" in markdown
    assert "start_server" in markdown
    assert "get_devserver_policy" in markdown


def test_runtime_in_process_smoke_uses_same_protocol_flow() -> None:
    smoke = load_smoke_module()

    payload = smoke.run_smoke(execution_mode="in-process")

    assert payload["status"] == "pass"
    assert payload["execution_mode"] == "in-process"
    assert payload["request_count"] == 6
    assert payload["response_count"] == 6
    assert payload["process_returncode"] == 0
    assert payload["summary"]["tools"] == [
        "get_devserver_logs",
        "get_devserver_policy",
        "get_devserver_statuses",
        "start_server",
        "stop_server",
    ]
    assert payload["summary"]["mutation_guard_status"] == "process_mutation_disabled"
    assert payload["summary"]["unknown_tool_error_status"] == "unknown_tool"
    assert payload["summary"]["post_error_logs_target_id"] == "dashboard-api"
    assert payload["errors"] == []


def test_validator_rejects_missing_tool() -> None:
    smoke = load_smoke_module()
    responses = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"serverInfo": {"name": "local-dev-server-runtime"}, "capabilities": {"tools": {}}},
        },
        {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "start_server"}]}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "result": {
                "isError": False,
                "structuredContent": {
                    "runtime_status": "local_stdio_runtime",
                    "process_mutation": {"default": "disabled"},
                    "non_local_control": {"status": "unsupported"},
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "result": {
                "isError": True,
                "structuredContent": {
                    "status": "process_mutation_disabled",
                    "enable_env": "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "result": {
                "isError": True,
                "structuredContent": {"status": "unknown_tool"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 6,
            "result": {
                "isError": False,
                "structuredContent": {"schema_version": 1, "target_id": "dashboard-api"},
            },
        },
    ]

    errors = smoke.validate_responses(responses, 0, "")

    assert any("tools/list mismatch" in error for error in errors)
