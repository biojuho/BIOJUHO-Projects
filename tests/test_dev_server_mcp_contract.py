from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "dev_server_mcp_contract.py"
MANIFEST_PATH = PROJECT_ROOT / "ops" / "references" / "dev_server_targets.json"


def load_contract_module():
    spec = importlib.util.spec_from_file_location("dev_server_mcp_contract", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_contract_matches_manifest_targets() -> None:
    contract_module = load_contract_module()
    payload = contract_module.load_validated_manifest(MANIFEST_PATH)

    contract = contract_module.build_contract(payload)
    errors = contract_module.validate_contract(contract, payload)

    target_ids = {target["id"] for target in payload["targets"]}
    assert errors == []
    assert contract["runtime"]["status"] == "local_stdio_runtime"
    assert contract["runtime"]["entrypoint"] == "python ops/scripts/dev_server_mcp_runtime.py"
    assert contract["runtime"]["process_mutation_enable_env"] == "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION"
    assert contract["summary"] == {
        "target_count": 7,
        "tool_count": 4,
        "read_only_tools": 2,
        "process_mutating_tools": 2,
    }
    assert {tool["name"] for tool in contract["tools"]} == {
        "start_server",
        "stop_server",
        "get_devserver_statuses",
        "get_devserver_logs",
    }
    for tool in contract["tools"]:
        properties = tool["inputSchema"]["properties"]
        if "target_id" in properties:
            assert set(properties["target_id"]["enum"]) == target_ids
        if "target_ids" in properties:
            assert set(properties["target_ids"]["items"]["enum"]) == target_ids


def test_contract_validation_rejects_target_enum_drift() -> None:
    contract_module = load_contract_module()
    payload = contract_module.load_validated_manifest(MANIFEST_PATH)
    contract = contract_module.build_contract(payload)
    start_tool = next(tool for tool in contract["tools"] if tool["name"] == "start_server")
    start_tool["inputSchema"]["properties"]["target_id"]["enum"] = ["dashboard-api"]

    errors = contract_module.validate_contract(contract, payload)

    assert "tools[1].inputSchema.properties.target_id.enum must match manifest targets" in errors


def test_cli_writes_contract_outputs(tmp_path: Path) -> None:
    contract_module = load_contract_module()
    json_out = tmp_path / "dev-server-mcp-contract.json"
    markdown_out = tmp_path / "dev-server-mcp-contract.md"

    result = contract_module.main(
        ["--manifest", str(MANIFEST_PATH), "--json-out", str(json_out), "--markdown-out", str(markdown_out)]
    )

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert payload["source"]["repo"] == "Uninen/devserver-mcp"
    assert payload["summary"]["tool_count"] == 4
    assert payload["summary"]["target_count"] == 7
    assert "Dev-Server MCP Tool Contract" in markdown
    assert "start_server" in markdown
    assert "local_stdio_runtime" in markdown
    assert "DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION" in markdown
