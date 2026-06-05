# AutoResearch Canva OpenAPI Contract - 2026-06-05

## Source Signal

- Upstream: `open-webui/mcpo`
- URL: https://github.com/open-webui/mcpo
- Pattern adopted: expose MCP tools through standard HTTP/OpenAPI contracts with API-key protected access and generated tool documentation.

## A/B Contract

- Baseline: the modernization radar kept `open-webui/mcpo` as `watch` because Canva MCP did not publish any OpenAPI-compatible tool contract.
- Variant: generate a deterministic static OpenAPI 3.1 contract from the tracked Canva MCP `tools.ts` registry.
- Primary KPI: make the Canva MCP tool surface inspectable by non-MCP clients and future `mcpo`-style proxy work.
- Guardrails: do not start a live proxy, do not depend on generated `dist/`, and keep the output deterministic from tracked source files.
- Decision: accepted. This moves the `open-webui/mcpo` row from `watch` to `partially_adopted`; a live API-key protected proxy endpoint remains future work.

## Changes

- `ops/scripts/canva_mcp_openapi_contract.py`
  - Extracts tool names, descriptions, schema references, and MCP annotations from `mcp/canva-mcp/src/server/tools.ts`.
  - Emits OpenAPI 3.1 paths with one `POST /{tool-name}` operation per MCP tool.
  - Adds `X-API-Key` security, generic MCP result responses, and `x-mcp-*` extensions for annotations and schema provenance.
- `tests/test_canva_mcp_openapi_contract.py`
  - Covers fixture parsing, API-key security, schema refs, destructive/read-only annotations, current Canva tool coverage, and CLI output.
- `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.json`
  - Generated OpenAPI contract.
- `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.md`
  - Operator summary of the generated contract.
- `ops/references/github_modernization_sources.json`
  - Promotes `open-webui/mcpo` to `partially_adopted` and records the new static-contract evidence.

## Verification

- `python -m py_compile ops\scripts\canva_mcp_openapi_contract.py`
  - Passed.
- `python -m pytest tests\test_canva_mcp_openapi_contract.py -q`
  - Passed `3/3`.
- `python ops\scripts\canva_mcp_openapi_contract.py --json-out docs\reports\2026-06\CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.md`
  - Passed.
  - Contract summary: `tools=22`, `read_only=11`, `destructive=1`, `schema_refs=20`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-canva-openapi-contract-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=4`, `partially_adopted=2`, `watch=0`.

## Notes

- This is a static contract, not a running OpenAPI proxy.
- The next `mcpo` step is a live local proxy or handler that serves this contract and forwards requests to the stdio/SSE MCP transport.
