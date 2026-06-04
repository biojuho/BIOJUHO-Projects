# AutoResearch Canva MCP OpenAPI Contract - 2026-06-04

## Source-Backed Candidate

- Source: `open-webui/mcpo` (`https://github.com/open-webui/mcpo`)
- Radar gap: the workspace did not publish MCP tools as OpenAPI endpoints.
- Local constraint: do not claim a live HTTP proxy before OAuth/runtime behavior is verified.

## Adopted Variant

- Added `ops/scripts/canva_mcp_openapi_contract.py`.
- The generator parses `mcp/canva-mcp/src/server/tools.ts` and writes an OpenAPI-compatible offline contract:
  - `GET /tools`
  - `POST /tools/{toolName}/call`
  - `CanvaMcpToolName` enum matching the parsed MCP tool order
  - `x-mcp-tools` extension with read-only/destructive metadata
- Generated:
  - `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.json`
  - `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.md`
- Added `tests/test_canva_mcp_openapi_contract.py`.

## Verification

- `python ops\scripts\canva_mcp_openapi_contract.py --openapi-out docs\reports\2026-06\CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.json --summary-out var\canva-mcp-openapi-contract-2026-06-04.json --markdown-out docs\reports\2026-06\CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.md`
  - `20` Canva MCP tools parsed
  - `9` read-only tools
  - `1` destructive tool
- `python -m pytest tests\test_canva_mcp_openapi_contract.py -q -p no:cacheprovider`
  - `4 passed`
- `python -m compileall -q ops\scripts\canva_mcp_openapi_contract.py`
  - passed

## Remaining Gap

This is an offline OpenAPI contract, not a live MCP-to-OpenAPI proxy. Runtime exposure should wait until Canva OAuth and proxy authentication behavior are verified with real credentials.
