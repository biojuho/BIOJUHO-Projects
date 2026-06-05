# AutoResearch Canva Stdio Auth Contract - 2026-06-05

## Source Signal

- Upstream: `PrefectHQ/fastmcp`
- URL: https://github.com/PrefectHQ/fastmcp
- Pattern adopted: production MCP services need explicit transport entrypoints, authentication lifecycle handling, generated tool schemas, and client-visible verification.

## A/B Contract

- Baseline: the committed Canva tool inventory test expected `auth-status`, `authenticate`, and `dist/server/stdio.js`, but the corresponding stdio entrypoint and auth helper tools were still local-only.
- Variant: track the stdio entrypoint, auth helper tools, token-store-backed status behavior, callback-server startup for stdio, and regression tests.
- Primary KPI: make a clean checkout able to build the Canva MCP server and verify the stdio tool/auth inventory without relying on dirty local files.
- Guardrails: do not stage the broad Canva package/lock dependency-update noise or generated widget assets.
- Decision: accepted. The committed server, stdio entrypoint, and tests now describe the same runtime surface.

## Changes

- `mcp/canva-mcp/src/server/tools.ts`
  - Adds `auth-status` and `authenticate` to the exported tool registry.
- `mcp/canva-mcp/src/server/auth.ts`
  - Adds file-backed token session loading when `TOKEN_STORE=file`.
  - Filters mock or incomplete token sessions from auth status.
  - Exposes redirect URI and mock-token helpers for server-side auth checks.
- `mcp/canva-mcp/src/server/server.ts`
  - Exports `createCanvaServer` and `startCanvaHttpServer`.
  - Handles auth helper tool calls before Canva API authentication is required.
  - Normalizes bearer-token headers and avoids persisting unusable header-only sessions.
  - Allows stdio mode to start a quiet OAuth callback server.
- `mcp/canva-mcp/src/server/stdio.ts`
  - Adds the tracked stdio MCP entrypoint.
- `mcp/canva-mcp/tests/stdio-auth.test.mjs`
  - Covers auth URL generation, callback port contention, file token persistence, and shared callback state.
- `ops/references/mcp_services.json`
  - Adds the stdio entrypoint and auth test to Canva MCP tracked evidence.

## Verification

- `cmd /c npm run build:server` in `mcp/canva-mcp`
  - Passed.
- `cmd /c node --test tests/tool-inventory.test.mjs tests/stdio-auth.test.mjs` in `mcp/canva-mcp`
  - Passed `6/6`.
- `python ops\scripts\mcp_service_inventory.py --json-out var\mcp-service-inventory-canva-stdio-auth-2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SERVICE_INVENTORY_2026-06-05.md`
  - Passed.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-canva-stdio-auth-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=4`, `partially_adopted=1`, `watch=1`.
- `python -m pytest tests\test_mcp_service_inventory.py tests\test_github_modernization_radar.py tests\test_workspace_smoke.py -q --tb=line -p no:cacheprovider`
  - Passed `37/37`.

## Notes

- The package/lock dependency-update diff and generated widget assets remain unstaged.
- This does not add OpenAPI publication yet. It makes the committed MCP transport/auth baseline coherent before the `open-webui/mcpo` interop work.
