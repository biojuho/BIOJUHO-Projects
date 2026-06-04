# AutoResearch MCP Service Manifest - 2026-06-04

## Source-Backed Candidate

- Source: `PrefectHQ/fastmcp` (`https://github.com/PrefectHQ/fastmcp`)
- Radar gap: Python MCP services existed in the repo, but there was no shared service inventory for composition, transport planning, launch commands, or smoke evidence.
- Local constraint: adopt a manifest and validator first; do not rework runtime service composition until there is a concrete expansion target.

## Adopted Variant

- Added `ops/references/mcp_service_manifest.json`.
- Added `ops/scripts/mcp_service_manifest.py`.
- Added `tests/test_mcp_service_manifest.py`.
- Generated:
  - `docs/reports/2026-06/MCP_SERVICE_MANIFEST_2026-06-04.json`
  - `docs/reports/2026-06/MCP_SERVICE_MANIFEST_2026-06-04.md`

The manifest records:

- `dailynews-antigravity`: Python `FastMCP`, stdio, `26` detected tools
- `desci-research`: Python `FastMCP`, stdio, `6` detected tools
- `telegram-bot`: Python `FastMCP`, stdio, `7` detected tools
- `canva-local`: TypeScript `MCP SDK`, SSE plus HTTP metadata, `20` detected tools

## Verification

- `python -m pytest tests\test_mcp_service_manifest.py -q -p no:cacheprovider`
  - `4 passed`
- `python -m compileall -q ops\scripts\mcp_service_manifest.py`
  - passed
- `python ops\scripts\mcp_service_manifest.py --json-out docs\reports\2026-06\MCP_SERVICE_MANIFEST_2026-06-04.json --markdown-out docs\reports\2026-06\MCP_SERVICE_MANIFEST_2026-06-04.md`
  - valid
  - `4` services
  - `3` FastMCP services
  - languages: `{"python": 3, "typescript": 1}`
  - transports: `{"http-metadata": 1, "sse": 1, "stdio": 3}`

## Remaining Gap

The repo now has a validated MCP service composition inventory. Runtime composition adapters, transport switching, and shared FastMCP deployment orchestration remain future-scoped until the next MCP expansion needs them.
