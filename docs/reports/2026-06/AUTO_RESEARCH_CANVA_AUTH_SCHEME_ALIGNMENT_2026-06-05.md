# AutoResearch Canva Auth Scheme Alignment - 2026-06-05

## Source Signal

- Upstream: `open-webui/mcpo`
- URL: https://github.com/open-webui/mcpo
- Local runtime evidence: `mcpo --strict-auth` accepts `Authorization: Bearer <api-key>` and rejects unauthenticated `/openapi.json` with `401`.

## A/B Contract

- Baseline: the static Canva MCP OpenAPI contract advertised `X-API-Key`, while the live `mcpo` smoke proved Bearer auth is the runtime auth header.
- Variant: make the static contract expose both `BearerAuth` and `ApiKeyAuth`, and make readiness validate both.
- Primary KPI: remove auth-scheme ambiguity for non-MCP clients and operators moving from static contract to live `mcpo` smoke.
- Guardrails: preserve `X-API-Key` for a first-party proxy contract, do not store secret values, and keep live smoke Bearer redaction.
- Decision: accepted. The contract now records the live `mcpo` Bearer scheme and the local API-key header scheme.

## Changes

- `ops/scripts/canva_mcp_openapi_contract.py`
  - Adds `BearerAuth` support.
  - Defaults to `auth_mode=both`.
  - Adds `--auth-mode api-key|bearer|both`.
  - Emits both top-level and operation-level security requirements.
- `tests/test_canva_mcp_openapi_contract.py`
  - Verifies both security schemes and Markdown security output.
- `ops/scripts/canva_mcp_proxy_readiness.py`
  - Validates both `BearerAuth` and `X-API-Key`.
  - Updates the operator proxy command to include `--strict-auth`.
- `tests/test_canva_mcp_proxy_readiness.py`
  - Updates fixtures and command expectations for both auth schemes.
- `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.json`
  - Regenerated with `BearerAuth` plus `ApiKeyAuth`.
- `docs/reports/2026-06/CANVA_MCP_PROXY_READINESS_2026-06-05.md`
  - Regenerated with `contract-auth-security=true` and the strict-auth command.

## Verification

- `python -m py_compile ops\scripts\canva_mcp_openapi_contract.py ops\scripts\canva_mcp_proxy_readiness.py`
  - Passed.
- `python -m pytest tests\test_canva_mcp_openapi_contract.py tests\test_canva_mcp_proxy_readiness.py -q --tb=line -p no:cacheprovider`
  - Passed `6/6`.
- `python ops\scripts\canva_mcp_openapi_contract.py --json-out docs\reports\2026-06\CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.md`
  - Passed.
- `$env:CANVA_MCP_PROXY_API_KEY='local-readiness-check'; python ops\scripts\canva_mcp_proxy_readiness.py --json-out var\canva-mcp-proxy-readiness-2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_MCP_PROXY_READINESS_2026-06-05.md`
  - Passed.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-canva-auth-scheme-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed with counts `adopted=5`, `partially_adopted=1`, `watch=0`.

## Notes

- The live smoke remains the source of truth for actual `mcpo` runtime auth. The static contract now gives clients both supported local paths without hiding the runtime Bearer requirement.
