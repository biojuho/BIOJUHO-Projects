# Canva MCP SDK Floor Guard

Generated at: `2026-06-05T10:45:00+09:00`

## Source Signal

- Repository: `microsoft/agent-framework`
- Commit: `bbccb7c28c86a0c2712d65e367fa8029065294eb`
- Subject: `.NET: Bump ModelContextProtocol from 1.1.0 to 1.2.0 (#3956) (#6239)`
- Source URL: https://github.com/microsoft/agent-framework/commit/bbccb7c28c86a0c2712d65e367fa8029065294eb
- Local registry check: `npm view @modelcontextprotocol/sdk version` returned `1.29.0`.

## A/B Contract

- Variant A: Leave Canva MCP `package.json` at the old `@modelcontextprotocol/sdk` floor `^1.0.4` while the lockfile resolves `1.29.0`.
- Variant B: Raise the manifest and package-lock root dependency floor to `^1.29.0` and add a regression test tying the declared floor to the resolved lockfile version.
- Adopted: Variant B.
- Reason: The upstream MCP dependency bump is a small package-hygiene signal. Locally, the runtime already uses `1.29.0`; the safer adoption is to make the current locked Model Context Protocol SDK floor explicit in the manifest and prevent future lock regeneration from drifting back to an old MCP SDK range.

## Local Changes

- `mcp/canva-mcp/package.json`
  - `@modelcontextprotocol/sdk`: `^1.0.4` -> `^1.29.0`
- `mcp/canva-mcp/package-lock.json`
  - Root dependency range now matches `^1.29.0`.
  - Resolved package remains `node_modules/@modelcontextprotocol/sdk` version `1.29.0`.
- `tests/test_canva_mcp_openapi_contract.py`
  - Added `test_canva_mcp_manifest_tracks_current_mcp_sdk_floor`.

## Verification

- `cmd /c "npm view @modelcontextprotocol/sdk version"`
  - `1.29.0`
- `cmd /c "npm ci --prefix mcp\canva-mcp --dry-run"`
  - package and lockfile are synchronized
- `python -m pytest tests\test_canva_mcp_openapi_contract.py -q`
  - `8 passed`
- `cmd /c "npm --prefix mcp\canva-mcp run typecheck"`
  - passed
- `cmd /c "npm --prefix mcp\canva-mcp run build"`
  - passed
- `python ops\scripts\dev_server_browser_smoke.py --target canva-widget-preview --timeout 30 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_MCP_SDK_FLOOR_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_MCP_SDK_FLOOR_2026-06-05.md`
  - pass: `1/1` route, failed=`0`
- `python ops\scripts\canva_widget_click_smoke.py --json-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_MCP_SDK_FLOOR_2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_MCP_SDK_FLOOR_2026-06-05.md`
  - pass: `8/8` actions, failed=`0`
- `python ops\scripts\dev_server_status.py --target canva-widget-preview --format table`
  - final state: `UNREADY` after stop

## Freshness Baseline

- Pushed proof commit: `0b2ba45`.
- Post-push completion audit failed against the prior protected-path baseline because `mcp/canva-mcp/package.json` and `mcp/canva-mcp/package-lock.json` changed in the product commit.
- `current_tip_freshness_gate` and `direct_browser_qa_freshness_gate` now use `0b2ba45`, so the protected-path diff after the proof baseline is empty.

## Boundaries

- This does not claim live Canva OAuth or OpenAPI tool execution.
- npm audit still reports one existing moderate issue; this cycle intentionally avoids a broader dependency-audit rewrite.
- `global_objective_complete=false`.
