# MCP Service Expected Tools Guard

Generated at: `2026-06-05T10:55:00+09:00`

## Source Signal

- Repository: `mastra-ai/mastra`
- Commit: `57879dd`
- Subject: `fix(server): merge dynamically created tools with bundler-discovered tools (#17535)`
- Source URL: https://github.com/mastra-ai/mastra/commit/57879dd
- Local interpretation: the upstream `/api/tools` fix prevents one tool source from hiding another. Locally, the analogous failure mode is an MCP service still meeting a minimum tool count while a named runtime tool disappears from `tools/list`.

## A/B Contract

- Variant A: Keep the MCP service smoke at `expected_min_tools` only.
- Variant B: Add manifest-level `expected_tools` and fail the runtime smoke when any named expected tool is absent.
- Adopted: Variant B.
- Reason: Minimum counts catch broad startup failures, but they do not prove the merged runtime inventory still contains each declared capability. The named-tool guard is a narrow regression check that preserves existing count checks while making silent tool-source drops visible.

## Local Changes

- `ops/references/mcp_service_manifest.json`
  - Added `expected_tools` inventories for `dailynews-antigravity`, `desci-research`, and `telegram-bot`.
- `ops/scripts/mcp_service_manifest.py`
  - Validates optional expected tool lists and surfaces expected runtime tool counts in manifest summaries.
- `ops/scripts/mcp_service_runtime_smoke.py`
  - Records `expected_tools` and `missing_expected_tools`, and fails if any expected tool is missing from `tools/list`.
- `tests/test_mcp_service_runtime_smoke.py`
  - Adds a missing expected tool regression test.

## Verification

- `python -m pytest tests\test_mcp_service_manifest.py tests\test_mcp_service_runtime_smoke.py -q`
  - `11 passed`
- `python ops\scripts\mcp_service_manifest.py --json-out var\mcp-service-manifest-expected-tools.json --markdown-out var\mcp-service-manifest-expected-tools.md`
  - valid: `4` services, `fastmcp=3`
- `python ops\scripts\mcp_service_runtime_smoke.py --json-out docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_EXPECTED_TOOLS_2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_EXPECTED_TOOLS_2026-06-05.md --timeout 30`
  - valid: `3` checked, `3` passed, `39` tools
  - `missing_expected_tools=[]` for all checked services
- `python -m pytest tests\test_mcp_service_manifest.py tests\test_mcp_service_runtime_smoke.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q`
  - `30 passed`
- `python ops\scripts\autoresearch_completion_audit.py --json-out var\autoresearch-mcp-expected-tools-completion.json --markdown-out var\autoresearch-mcp-expected-tools-completion.md`
  - valid `54` criteria
- `python ops\scripts\autoresearch_objective_coverage.py --json-out var\autoresearch-mcp-expected-tools-objective.json --markdown-out var\autoresearch-mcp-expected-tools-objective.md`
  - valid `7` requirements

## Freshness Baseline

- Pushed proof commit: `9df96e1`.
- Post-push completion audit initially failed against the prior current-tip baseline because `ops/references/mcp_service_manifest.json`, `ops/scripts/mcp_service_manifest.py`, and `tests/test_mcp_service_manifest.py` changed in the product commit.
- `current_tip_freshness_gate` now uses `9df96e1`, and the MCP service manifest validator files are explicitly classified as audit evidence paths.

## Boundaries

- This does not call credential-gated Telegram delivery tools.
- The Canva MCP service remains non-stdio in this runtime smoke and is covered by its TypeScript build/OpenAPI/browser/click guards.
- `global_objective_complete=false`.
