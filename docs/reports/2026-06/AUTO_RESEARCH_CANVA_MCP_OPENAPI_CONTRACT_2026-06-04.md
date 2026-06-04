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
- Added read-only runtime metadata endpoints to `mcp/canva-mcp/src/server/server.ts`:
  - `GET /openapi.json`
  - `GET /tools`
- Added the actual local Canva widget preview origins to the server CORS allowlist:
  - `http://localhost:5176`
  - `http://127.0.0.1:5176`
- Added `mcp/canva-mcp/src/types/css.d.ts` and `.gitignore` exception so the package typecheck handles CSS side-effect imports.
- Added `ignoreDeprecations: "6.0"` to `mcp/canva-mcp/tsconfig.build.json` so the server build remains valid under TypeScript 6.
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
  - `5 passed`
- `python -m compileall -q ops\scripts\canva_mcp_openapi_contract.py`
  - passed
- `npm.cmd run typecheck` in `mcp/canva-mcp`
  - passed
- `npm.cmd run build:server` in `mcp/canva-mcp`
  - passed
- Live server proof:
  - Started `npm.cmd run dev` in `mcp/canva-mcp`
  - `GET http://127.0.0.1:8001/openapi.json` returned `openapi=3.1.0`, `20` tool enum entries, and `20` `x-mcp-tools`
  - `GET http://127.0.0.1:8001/tools` returned `20` tools
  - `OPTIONS http://127.0.0.1:8001/openapi.json` with origin `http://127.0.0.1:5176` returned `204` and `Access-Control-Allow-Origin=http://127.0.0.1:5176`
  - Evidence: `var/canva-mcp-openapi-live-proof-2026-06-04.json`
  - Server stopped with `0` remaining listeners on port `8001`

## Remaining Gap

This is a live read-only metadata surface plus an offline OpenAPI contract, not a live MCP-to-OpenAPI execution proxy. Runtime tool execution through OpenAPI should wait until Canva OAuth and proxy authentication behavior are verified with real credentials.
