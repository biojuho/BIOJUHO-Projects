# AutoResearch Canva Proxy Live Smoke - 2026-06-05

## Source Signal

- Upstream: `open-webui/mcpo`
- URL: https://github.com/open-webui/mcpo
- Pattern adopted: expose an MCP stdio server through a live OpenAPI HTTP proxy with API-key authentication and interactive docs.

## A/B Contract

- Baseline: Canva MCP had a static OpenAPI contract and preflight readiness gate, but no live proof that `mcpo` could serve docs/OpenAPI against the local stdio server.
- Variant: add and run a live smoke that builds Canva MCP, starts `uvx mcpo` with `--strict-auth`, probes authenticated docs/OpenAPI, verifies unauthenticated rejection, checks required tool paths, and stops the process tree.
- Primary KPI: convert the `open-webui/mcpo` radar row from readiness-only to local live interop evidence.
- Guardrails: redact API-key values, use a free localhost port, avoid persistent background processes, and keep generated JSON under `var/`.
- Decision: accepted. The `open-webui/mcpo` source row is promoted to `adopted` for local Canva MCP interop.

## Changes

- `ops/scripts/canva_mcp_proxy_live_smoke.py`
  - Runs `npm run build:server`.
  - Starts `uvx mcpo --strict-auth -- node dist/server/stdio.js` on a free localhost port.
  - Uses `Authorization: Bearer <redacted>` for authenticated probes.
  - Verifies `/openapi.json`, `/docs`, unauthenticated `401`, and required OpenAPI paths.
  - Captures stdout/stderr tails and stops the Windows process tree, including reparented stdio descendants.
- `tests/test_canva_mcp_proxy_live_smoke.py`
  - Covers Bearer-auth probing, unauthenticated rejection, missing required paths, Markdown redaction, and descendant PID traversal.
- `docs/reports/2026-06/CANVA_MCP_PROXY_LIVE_SMOKE_2026-06-05.md`
  - Tracks the generated live smoke report.
- `ops/references/github_modernization_sources.json`
  - Promotes `open-webui/mcpo` to `adopted`.

## Verification

- `cmd /c "uvx mcpo --help"`
  - Passed and confirmed `--api-key` plus `--strict-auth`.
- Manual live probe with `Authorization: Bearer local-live-smoke-key`
  - Passed: authenticated `/docs` and `/openapi.json` returned `200`; unauthenticated `/openapi.json` returned `401`.
- `python -m py_compile ops\scripts\canva_mcp_proxy_live_smoke.py`
  - Passed.
- `python -m pytest tests\test_canva_mcp_proxy_live_smoke.py -q --tb=line -p no:cacheprovider`
  - Passed `4/4`.
- `$env:CANVA_MCP_PROXY_API_KEY='local-live-smoke-key'; python ops\scripts\canva_mcp_proxy_live_smoke.py --json-out var\canva-mcp-proxy-live-smoke-2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_MCP_PROXY_LIVE_SMOKE_2026-06-05.md --timeout-seconds 90`
  - Passed.
  - Summary: `5/5` checks passed, OpenAPI path count `22`.
  - Process cleanup: no remaining `mcpo` or `dist/server/stdio.js` process after the hardened cleanup run.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-canva-proxy-live-smoke-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=5`, `partially_adopted=1`, `watch=0`.

## Notes

- The script records Bearer auth because the current `mcpo` runtime enforces `Authorization: Bearer <api-key>` or Basic auth for strict-auth routes.
- The static local contract still uses `X-API-Key` as the future-facing contract for a first-party proxy. The live `mcpo` smoke records the actual runtime auth shape separately.
