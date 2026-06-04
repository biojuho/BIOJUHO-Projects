from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "canva_mcp_openapi_contract.py"
TOOLS_PATH = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "tools.ts"
SERVER_PATH = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "server.ts"


def load_contract_module():
    spec = importlib.util.spec_from_file_location("canva_mcp_openapi_contract", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parses_current_canva_mcp_tools() -> None:
    contract = load_contract_module()

    tools = contract.parse_tools(TOOLS_PATH)

    assert len(tools) == 20
    assert tools[0]["name"] == "upload-asset-from-url"
    assert {tool["name"] for tool in tools} >= {
        "search-designs",
        "generate-design",
        "start-editing-transaction",
        "commit-editing-transaction",
    }
    assert sum(1 for tool in tools if tool["read_only"]) == 9
    assert [tool["name"] for tool in tools if tool["destructive"]] == ["commit-editing-transaction"]


def test_openapi_contract_matches_parsed_tool_surface() -> None:
    contract = load_contract_module()
    tools = contract.parse_tools(TOOLS_PATH)
    spec = contract.build_openapi(tools)

    errors = contract.validate_openapi(spec, tools)
    summary = contract.summarize(tools, spec)

    assert errors == []
    assert spec["openapi"] == "3.1.0"
    assert sorted(spec["paths"]) == ["/tools", "/tools/{toolName}/call"]
    assert spec["components"]["schemas"]["CanvaMcpToolName"]["enum"] == [tool["name"] for tool in tools]
    assert summary["tool_count"] == 20
    assert summary["destructive_count"] == 1


def test_cli_writes_openapi_summary_and_markdown(tmp_path: Path) -> None:
    contract = load_contract_module()
    openapi_out = tmp_path / "openapi.json"
    summary_out = tmp_path / "summary.json"
    markdown_out = tmp_path / "contract.md"

    result = contract.main(
        [
            "--tools",
            str(TOOLS_PATH),
            "--openapi-out",
            str(openapi_out),
            "--summary-out",
            str(summary_out),
            "--markdown-out",
            str(markdown_out),
        ]
    )

    spec = json.loads(openapi_out.read_text(encoding="utf-8"))
    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert result == 0
    assert spec["components"]["schemas"]["CanvaMcpToolName"]["enum"][0] == "upload-asset-from-url"
    assert summary["read_only_count"] == 9
    assert "Canva MCP OpenAPI Interop Contract" in markdown
    assert "`commit-editing-transaction` (destructive)" in markdown


def test_openapi_validation_rejects_enum_drift() -> None:
    contract = load_contract_module()
    tools = contract.parse_tools(TOOLS_PATH)
    spec = contract.build_openapi(tools)
    spec["components"]["schemas"]["CanvaMcpToolName"]["enum"] = ["search-designs"]

    errors = contract.validate_openapi(spec, tools)

    assert "CanvaMcpToolName enum must match parsed tool order" in errors


def test_canva_mcp_server_exposes_read_only_metadata_routes() -> None:
    server = SERVER_PATH.read_text(encoding="utf-8")

    assert '"/openapi.json"' in server
    assert '"/tools"' in server
    assert "buildOpenApiContract" in server
    assert "canvaToolSummaries" in server
    assert '"http://127.0.0.1:5176"' in server
    assert "getOpenApiToolCallName" in server
    assert "openapi_tool_execution_disabled" in server
    assert '"501"' in server
