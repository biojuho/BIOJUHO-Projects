# AutoResearch Canva Proxy Readiness - 2026-06-05

## Source Signal

- Upstream: `open-webui/mcpo`
- URL: https://github.com/open-webui/mcpo
- Pattern adopted: before exposing MCP tools through a live OpenAPI proxy, validate stdio transport, generated server build, OpenAPI/API-key contract, and operator command shape.

## A/B Contract

- Baseline: Canva MCP had a tracked static OpenAPI contract, but no deterministic check that the local stdio build and API-key proxy prerequisites were ready.
- Variant: add a local readiness script and tracked report for a `mcpo`-style Canva MCP proxy command.
- Primary KPI: make the live-proxy preflight status auditable before starting a network service.
- Guardrails: do not start a proxy server, do not add a runtime dependency on `mcpo`, do not store the API key value, and keep the static OpenAPI contract as the source of truth.
- Decision: accepted. The variant gives operators a repeatable readiness gate while leaving live proxy/docs smoke as the next step.

## Changes

- `ops/scripts/canva_mcp_proxy_readiness.py`
  - Validates `tools.ts`, `stdio.ts`, generated `dist/server/stdio.js`, the tracked OpenAPI contract, API-key env configuration, API-key security scheme, and OpenAPI/tool-path sync.
  - Emits JSON and Markdown readiness reports.
  - Prints the build command, proxy command, docs URL, and OpenAPI URL without exposing a secret value.
- `tests/test_canva_mcp_proxy_readiness.py`
  - Covers matching fixtures, stale-contract detection, missing API-key/security detection, and CLI JSON+Markdown output.
- `docs/reports/2026-06/CANVA_MCP_PROXY_READINESS_2026-06-05.md`
  - Tracks the generated local readiness report.
- `ops/references/github_modernization_sources.json`
  - Records the readiness script/report as local evidence for the `open-webui/mcpo` source row.

## Verification

- `python -m py_compile ops\scripts\canva_mcp_proxy_readiness.py`
  - Passed.
- `python -m pytest tests\test_canva_mcp_proxy_readiness.py -q --tb=line -p no:cacheprovider`
  - Passed `3/3`.
- `$env:CANVA_MCP_PROXY_API_KEY='local-readiness-check'; python ops\scripts\canva_mcp_proxy_readiness.py --json-out var\canva-mcp-proxy-readiness-2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_MCP_PROXY_READINESS_2026-06-05.md`
  - Passed.
  - Readiness summary: `ok=true`, `tool_count=22`, `openapi_path_count=22`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-canva-proxy-readiness-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=4`, `partially_adopted=2`, `watch=0`.

## Notes

- The proxy command recorded by the readiness report is `uvx mcpo --port 8000 --api-key <CANVA_MCP_PROXY_API_KEY> -- node dist/server/stdio.js` from cwd `mcp/canva-mcp`.
- This does not claim that a live proxy or interactive docs endpoint has been started and clicked.
