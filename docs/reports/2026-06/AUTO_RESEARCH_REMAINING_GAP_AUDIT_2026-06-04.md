# AutoResearch Remaining Gap Audit - 2026-06-04

## Scope

This audit records the state after the 2026-06-04 AutoResearch adoption cycle on branch `feat/observability-gateway-2026-05`.

Latest pushed commits in this slice:

- `dccaad4 docs(ops): record agriguard click proof`
- `dc6590f docs(ops): record dashboard click proof`
- `02bfcea feat(ops): add dev server mcp contract`
- `3983c4f feat(ops): export mcp smoke otlp spans`
- `84ce8fc feat(ops): add agent workflow dry run plans`
- `c4442da feat(ops): add mcp service manifest`
- `cd199f1 feat(ops): add dev server status table`
- `4e6f182 feat(ops): export mcp smoke traces`
- `01d8fe6 feat(mcp): guard canva openapi calls`
- `8278c09 feat(mcp): expose canva openapi metadata`

## Adopted Source-Backed Variants

- `PrefectHQ/fastmcp`: adopted a validated MCP service manifest for composition planning.
- `lastmile-ai/mcp-eval`: adopted MCP smoke schema metrics, dashboard surfacing, standalone JSONL trace export, and local OTLP file-exporter shaped span export.
- `evalstate/fast-agent`: adopted launch workflow inventory plus dry-run command plans.
- `dsifry/metaswarm`: deterministic quality gates and durable next-action capture are structurally adopted.
- `open-webui/mcpo`: adopted Canva MCP offline OpenAPI contract, live read-only metadata endpoints, and explicit disabled execution responses.
- `Uninen/devserver-mcp`: adopted manifest-backed start/stop/status/tail, dashboard readiness, terminal table status, timeout-tree cleanup, checked MCP tool definitions, and a local stdio MCP runtime with process mutation opt-in.

## Remaining Gaps

These are intentionally not promoted to live runtime changes in this cycle:

- FastMCP runtime composition adapters and transport switching:
  - Status: future-scoped
  - Reason: the service inventory now exists; a runtime adapter should wait for a concrete MCP expansion target.
- Live OpenTelemetry SDK or collector shipping:
  - Status: future-scoped
  - Reason: local OTLP file-exporter shaped span output now exists; live SDK or collector shipping should wait for an operator-owned collector contract.
- Live central agent workflow orchestration:
  - Status: future-scoped
  - Reason: dry-run plans exist; live orchestration should stay behind existing project CLIs and smoke/dev-server gates until execution ownership is clear.
- Canva OpenAPI tool execution proxy:
  - Status: external-auth blocked
  - Reason: metadata and disabled-call boundary are live; actual execution should wait for verified Canva OAuth credentials plus proxy authentication behavior.
- Dev-server TUI exposure and non-local authentication policy:
  - Status: future-scoped
  - Reason: a local stdio MCP runtime now exists for the checked tool contract; full TUI exposure or non-local process-control authentication should wait for an operator-owned boundary.

## Verification

- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-agent-workflow-plan-2026-06-04.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - valid
  - `6` sources
  - `adopted=1`
  - `partially_adopted=5`
  - `watch=0`
- Pre-push hooks on the latest pushed slices passed:
  - `27 passed` after `dccaad4`
  - `27 passed` after `dc6590f`
  - `27 passed` after `02bfcea`
  - `27 passed` after `3983c4f`
  - `25 passed` after `84ce8fc`
  - `25 passed` after `c4442da`
  - `25 passed` after `cd199f1`
- OTLP span export verification:
  - expanded focused tests `56 passed`
  - final MCP smoke `3/3 PASS`
  - final OTLP file `var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.otlp.jsonl`
    contained `1` `resourceSpans` line with `3` spans
- Dev-server MCP contract verification:
  - `tests\test_dev_server_mcp_contract.py` `3 passed`
  - dev-server contract/status/control tests `24 passed`
  - contract generation emits `4` tools across `7` targets with runtime status `local_stdio_runtime`
- Dev-server MCP runtime verification:
  - focused dev-server/radar/completion suite `38 passed`
  - PowerShell piped JSON-RPC `tools/list` smoke returned the four checked tools
  - contract generation emitted `4` tools across `7` targets with runtime status `local_stdio_runtime`
  - `start_server` and `stop_server` remain disabled by default unless `DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION=true`
- Dashboard live browser-click verification:
  - `apps\dashboard` build passed
  - dashboard Vitest `8 passed`
  - manifest-backed dashboard stack reached `2/2 READY`
  - Chromium clicked the refresh button and verified `WORKSPACE SMOKE`, `DEV SERVERS`, and `2/2 READY` with zero console/page/request failures
  - managed dashboard stack stopped and final status returned `0/2 READY`
- AgriGuard live browser-click verification:
  - `agriguard-api` and `agriguard-frontend` status returned `2/2 READY`
  - Chromium clicked through home, `Registry`, `Supply Chain`, and `Scanner`
  - route checks verified `/registry`, `/supply-chain`, and `/scan` with zero console/page/request failures
  - AgriGuard frontend build passed and full Vitest completed with `29 passed`
- DeSci live browser remediation:
  - Firebase config fallback restored public route rendering without real Firebase credentials
  - backend CORS now admits the manifest DeSci frontend origin `http://127.0.0.1:5175`
  - browser smoke returned `7/7 OK`
  - live click proof covered home, explore search, and pricing with zero console/page/request failures
  - focused/full frontend tests, backend API tests, build/typecheck, and DeSci canonical smoke passed

## Decision

The remaining items are not current implementation blockers. Treat them as explicit future work unless the user supplies external credentials, asks for a live runtime orchestrator, or scopes a concrete MCP adapter/collector/dev-server TUI or non-local authentication build.
