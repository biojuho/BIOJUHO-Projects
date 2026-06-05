from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "ops" / "scripts" / "canva_mcp_openapi_contract.py"
TOOLS_SOURCE = PROJECT_ROOT / "mcp" / "canva-mcp" / "src" / "server" / "tools.ts"


def load_contract_module():
    spec = importlib.util.spec_from_file_location("canva_mcp_openapi_contract", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fixture_tools_generate_api_key_protected_openapi_paths() -> None:
    contract_module = load_contract_module()
    tools = contract_module.extract_tools(
        """
        export const tools: Tool[] = [
          {
            name: "search-designs",
            description: "Search Canva designs.",
            inputSchema: searchDesignsSchema as any,
            annotations: {
              destructiveHint: false,
              openWorldHint: false,
              readOnlyHint: true,
            },
          },
          {
            name: "authenticate",
            description: `Create an OAuth URL.`,
            inputSchema: {
              type: "object",
              properties: {},
              additionalProperties: false,
            } as any,
            annotations: {
              destructiveHint: false,
              openWorldHint: false,
              readOnlyHint: true,
            },
          },
        ];
        """
    )

    contract = contract_module.build_openapi_contract(tools, generated_at="2026-06-05T00:00:00+00:00")
    summary = contract_module.summarize_contract(contract)

    assert summary["tool_count"] == 2
    assert summary["read_only_count"] == 2
    assert summary["destructive_count"] == 0
    assert contract["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"
    assert sorted(contract["paths"]) == ["/authenticate", "/search-designs"]
    assert contract["paths"]["/search-designs"]["post"]["operationId"] == "call_search_designs"
    assert contract["paths"]["/search-designs"]["post"]["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/searchDesignsSchema"
    }
    assert contract["paths"]["/authenticate"]["post"]["requestBody"]["required"] is False


def test_current_canva_tools_generate_expected_contract_surface() -> None:
    contract_module = load_contract_module()
    tools = contract_module.extract_tools(contract_module.load_tools_source(TOOLS_SOURCE))
    contract = contract_module.build_openapi_contract(tools, generated_at="2026-06-05T00:00:00+00:00")
    summary = contract_module.summarize_contract(contract)

    assert summary["tool_count"] >= 20
    assert "/auth-status" in contract["paths"]
    assert "/authenticate" in contract["paths"]
    assert "/search-designs" in contract["paths"]
    assert "/commit-editing-transaction" in contract["paths"]
    assert contract["paths"]["/commit-editing-transaction"]["post"]["x-mcp-annotations"]["destructiveHint"] is True
    assert summary["schema_ref_count"] >= 15


def test_cli_writes_contract_json_and_markdown(tmp_path: Path) -> None:
    json_out = tmp_path / "contract.json"
    markdown_out = tmp_path / "contract.md"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--tools-source",
            str(TOOLS_SOURCE),
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "canva mcp openapi contract valid" in completed.stdout
    contract = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert contract["openapi"] == "3.1.0"
    assert "/generate-design" in contract["paths"]
    assert "Canva MCP OpenAPI Contract" in markdown
