# AutoResearch MCP Service Inventory - 2026-06-05

## Source Signal

- Upstream: `PrefectHQ/fastmcp`
- URL: https://github.com/PrefectHQ/fastmcp
- Pattern adopted: MCP services should have explicit, versioned composition metadata for servers, transports, auth boundaries, entrypoints, and verification evidence.

## A/B Contract

- Baseline: the workspace had multiple MCP service directories and smoke checks, but no single tracked inventory declaring service composition across Canva, DeSci research, Telegram, GitHub, and NotebookLM surfaces.
- Variant: add a schema v1 MCP service inventory plus a validator/generator that rejects untracked local-only path references.
- Primary KPI: make MCP service composition auditable from one manifest while preventing stale or local-only evidence references.
- Guardrails: do not modify dirty MCP implementation files; reference tracked files only; keep the existing `mcp` smoke scope as the runtime gate.
- Decision: accepted. The manifest covers five MCP services and validates all entrypoints/evidence against tracked repo paths.

## Changes

- `ops/references/mcp_services.json`
  - Declares five services: `canva-mcp`, `desci-research-mcp`, `telegram-mcp`, `github-mcp`, and `notebooklm-mcp`.
  - Records language, status, transport modes, auth boundary, entrypoints, smoke checks, and evidence.
- `ops/scripts/mcp_service_inventory.py`
  - Validates schema, ids, statuses, languages, transports, smoke scopes, repo-relative paths, path existence, and git tracking.
  - Writes JSON and markdown summaries.
- `tests/test_mcp_service_inventory.py`
  - Covers current manifest validity, CLI output, unsafe/missing/untracked paths, duplicate ids, and unsupported transports.
- `docs/reports/2026-06/MCP_SERVICE_INVENTORY_2026-06-05.md`
  - Generated operator-readable service summary.
- `ops/references/github_modernization_sources.json` and generated modernization radar markdown
  - Marks the `PrefectHQ/fastmcp` structural service-composition gap as adopted.

## Verification

- `python ops\scripts\mcp_service_inventory.py --json-out var\mcp-service-inventory-2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SERVICE_INVENTORY_2026-06-05.md`
  - Passed: `5 services`.
- `python -m py_compile ops\scripts\mcp_service_inventory.py`
  - Passed.
- `python -m pytest tests\test_mcp_service_inventory.py -q`
  - Passed `4/4`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-mcp-service-inventory-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed.
  - Summary: `6 sources, adopted=4, partially_adopted=1, watch=1`.

## Notes

- This is a control-plane inventory. Live MCP health probing remains covered by the existing MCP smoke path and can be wired directly to this manifest in a later cycle.
