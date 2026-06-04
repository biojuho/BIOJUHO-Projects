from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "dev_server_mcp_runtime.py"


def load_runtime_module():
    spec = importlib.util.spec_from_file_location("dev_server_mcp_runtime", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tools_list_exposes_contract_tool_names() -> None:
    runtime = load_runtime_module()

    response = runtime.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response["result"]["tools"]
    assert {tool["name"] for tool in response["result"]["tools"]} == {
        "get_devserver_statuses",
        "start_server",
        "stop_server",
        "get_devserver_logs",
    }
    start_tool = next(tool for tool in response["result"]["tools"] if tool["name"] == "start_server")
    assert "target_id" in start_tool["inputSchema"]["required"]


def test_status_tool_returns_read_only_manifest_report() -> None:
    runtime = load_runtime_module()

    def fake_fetcher(url: str, timeout: float) -> tuple[int, int, str, None]:
        assert url == "http://127.0.0.1:8080/api/quality_overview"
        assert timeout == 0.5
        return 200, 7, "qa_grades daily_production", None

    result = runtime.execute_tool(
        "get_devserver_statuses",
        {"target_ids": ["dashboard-api"], "timeout_seconds": 0.5},
        status_fetcher=fake_fetcher,
    )

    assert result["schema_version"] == 1
    assert result["summary"] == {"total": 1, "ready": 1, "unready": 0}
    assert result["targets"][0]["id"] == "dashboard-api"
    assert result["targets"][0]["ok"] is True


def test_mutating_tool_returns_mcp_error_until_env_opt_in() -> None:
    runtime = load_runtime_module()

    response = runtime.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "start_server", "arguments": {"target_id": "dashboard-api"}},
        }
    )

    result = response["result"]
    payload = result["structuredContent"]
    assert result["isError"] is True
    assert payload["status"] == "process_mutation_disabled"
    assert payload["enable_env"] == "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION"


def test_stop_tool_uses_control_when_explicitly_enabled(monkeypatch, tmp_path: Path) -> None:
    runtime = load_runtime_module()
    calls: list[dict[str, Any]] = []

    def fake_stop_target(target_id: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"target_id": target_id, **kwargs})
        return {"schema_version": 1, "target_id": target_id, "status": "stopped"}

    monkeypatch.setattr(runtime.control, "stop_target", fake_stop_target)

    result = runtime.execute_tool(
        "stop_server",
        {"target_id": "dashboard-api", "include_dependencies": False, "timeout_seconds": 1},
        allow_process_mutation=True,
        state_dir=tmp_path,
    )

    assert result == {"schema_version": 1, "target_id": "dashboard-api", "status": "stopped"}
    assert calls == [
        {
            "target_id": "dashboard-api",
            "state_dir": tmp_path,
            "timeout": 1.0,
            "include_dependencies": False,
        }
    ]


def test_once_line_handler_returns_initialize_response() -> None:
    runtime = load_runtime_module()
    response = runtime.handle_line(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "initialize"}))

    assert response["result"]["capabilities"] == {"tools": {}}
    assert response["result"]["serverInfo"]["name"] == "local-dev-server-runtime"


def test_line_handler_tolerates_powershell_utf8_bom() -> None:
    runtime = load_runtime_module()
    request = "\ufeff" + json.dumps({"jsonrpc": "2.0", "id": 4, "method": "ping"})

    response = runtime.handle_line(request)

    assert response == {"jsonrpc": "2.0", "id": 4, "result": {}}
