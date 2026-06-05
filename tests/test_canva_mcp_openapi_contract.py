from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "canva_mcp_openapi_contract.py"
TOOLS_PATH = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "tools.ts"
SERVER_PATH = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "server.ts"
SCHEMAS_PATH = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "schemas.ts"


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
    search_tool = next(tool for tool in tools if tool["name"] == "search-designs")
    upload_tool = next(tool for tool in tools if tool["name"] == "upload-asset-from-url")
    assert search_tool["openai_meta_keys"] == [
        "openai/outputTemplate",
        "openai/toolInvocation/invoking",
        "openai/toolInvocation/invoked",
        "openai/widgetAccessible",
        "openai/resultCanProduceWidget",
    ]
    assert upload_tool["openai_meta_keys"] == [
        "openai/widgetAccessible",
        "openai/toolInvocation/invoking",
        "openai/toolInvocation/invoked",
    ]


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
    assert "openAiMetaKeys" in spec["components"]["schemas"]["CanvaMcpTool"]["required"]
    assert spec["x-mcp-tools"][1]["openAiMetaKeys"] == tools[1]["openai_meta_keys"]
    assert summary["tool_count"] == 20
    assert summary["destructive_count"] == 1
    assert summary["openai_meta_tool_count"] == 4


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
    assert summary["openai_meta_tool_count"] == 4
    assert "Canva MCP OpenAPI Interop Contract" in markdown
    assert "Tools with OpenAI namespaced metadata: 4" in markdown
    assert "openai/outputTemplate" in markdown
    assert "`commit-editing-transaction` (destructive)" in markdown


def test_openapi_validation_rejects_enum_drift() -> None:
    contract = load_contract_module()
    tools = contract.parse_tools(TOOLS_PATH)
    spec = contract.build_openapi(tools)
    spec["components"]["schemas"]["CanvaMcpToolName"]["enum"] = ["search-designs"]

    errors = contract.validate_openapi(spec, tools)

    assert "CanvaMcpToolName enum must match parsed tool order" in errors


def test_openapi_validation_rejects_openai_namespace_metadata_drift() -> None:
    contract = load_contract_module()
    tools = contract.parse_tools(TOOLS_PATH)
    spec = contract.build_openapi(tools)
    spec["x-mcp-tools"][1]["openAiMetaKeys"] = []

    errors = contract.validate_openapi(spec, tools)

    assert "x-mcp-tools must preserve OpenAI namespaced metadata keys" in errors


def test_canva_mcp_server_exposes_read_only_metadata_routes() -> None:
    server = SERVER_PATH.read_text(encoding="utf-8")

    assert '"/openapi.json"' in server
    assert '"/tools"' in server
    assert "buildOpenApiContract" in server
    assert "canvaToolSummaries" in server
    assert "canvaOpenAiMeta" in server
    assert "openAiMeta" in server
    assert "openAiMetaKeys" in server
    assert '"openai/outputTemplate"' in TOOLS_PATH.read_text(encoding="utf-8")
    assert '"http://127.0.0.1:5176"' in server
    assert "getOpenApiToolCallName" in server
    assert "openapi_tool_execution_disabled" in server
    assert '"501"' in server


def test_canva_continuation_tools_keep_schema_description_and_server_propagation() -> None:
    contract = load_contract_module()
    tools = {tool["name"]: tool for tool in contract.parse_tools(TOOLS_PATH)}
    schemas = SCHEMAS_PATH.read_text(encoding="utf-8")
    server = SERVER_PATH.read_text(encoding="utf-8")
    continuation_tools = {
        "search-designs": ("searchDesignsSchema", "searchDesignsParser"),
        "list-folder-items": ("listFolderItemsSchema", "listFolderItemsParser"),
        "list-comments": ("listCommentsSchema", "listCommentsParser"),
        "list-replies": ("listRepliesSchema", "listRepliesParser"),
    }

    for tool_name, (schema_name, parser_name) in continuation_tools.items():
        assert "continuation" in tools[tool_name]["description"].lower()
        assert f"export const {schema_name}" in schemas
        assert f"export const {parser_name}" in schemas
        assert f"{parser_name} = z.object" in schemas

    assert schemas.count("continuation: {") >= len(continuation_tools)
    assert schemas.count("continuation: z.string().optional()") >= len(continuation_tools)
    assert server.count('params.append("continuation", args.continuation)') >= len(continuation_tools)
    assert "structuredContent: { query: args.query, designs: data.items || [], continuation: data.continuation }" in server
