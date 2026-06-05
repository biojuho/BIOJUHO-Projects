# AutoResearch Canva Search Continuation Action

- Date: 2026-06-05
- Source repo: `mastra-ai/mastra`
- Source commit: `b3e9781a93a18e8e492849040016ddf239c00d9c`
- Source signal: `fix(client-js): keep client tools for signal continuations (#17593)`
- Source URL: https://github.com/mastra-ai/mastra/commit/b3e9781a93a18e8e492849040016ddf239c00d9c
- Local product commit: `cf229e73c22ce2fa5687448d2040e4a03dd68a09`
- Local status: adopted
- Global objective complete: `false`

## Source Signal

Mastra fixed subscribed client-tool continuations so browser client tools remain available across continuation runs instead of losing tool context after the initial run id changes.

## A/B Contract

- A: Keep the Canva search widget's continuation token as passive structured content. The server can return `continuation`, but the widget gives the operator no direct way to request the next page or preserve the `search-designs` tool context.
- B: Render a continuation action when a token exists and post a `canva-load-more` message that carries `toolName: search-designs`, the original query, and the continuation token as resumable tool arguments.

Decision: adopted B. It converts the existing token into an explicit operator action and preserves the tool context needed by the host/client to continue the search flow.

## Local Changes

- `mcp/canva-mcp/src/components/canva-search-designs.tsx`
  - Adds a guarded "Load more" button when `continuation` exists.
  - Posts `canva-load-more` with `toolName: search-designs`, `query`, and `continuation` in `arguments`.
- `ops/scripts/canva_widget_click_smoke.py`
  - Adds a `load-more-click` action and renders continuation ids in captured message summaries.
- `tests/test_canva_mcp_openapi_contract.py`
  - Locks the widget load-more action and resumable tool context in source.
- `tests/test_canva_widget_click_smoke.py`
  - Locks the continuation message identity in click-smoke Markdown output.
- `mcp/canva-mcp/assets/`
  - Rebuilt generated widget assets so the stdio/server runtime serves the new control.

## Verification

- `python -m pytest tests\test_canva_mcp_openapi_contract.py tests\test_canva_widget_click_smoke.py -q` -> `15 passed`
- `cmd /c npm run typecheck` in `mcp\canva-mcp` -> passed
- `cmd /c npm run build` in `mcp\canva-mcp` -> passed
- `python ops\scripts\canva_widget_click_smoke.py --json-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_LOAD_MORE_2026-06-05.json --markdown-out docs\reports\2026-06\CANVA_WIDGET_CLICK_SMOKE_LOAD_MORE_2026-06-05.md` -> `pass: 9/9 actions`, `canva-load-more` captured with `next_page_token_xyz`
- `git push origin HEAD:feat/observability-gateway-2026-05` for product commit `cf229e73c22ce2fa5687448d2040e4a03dd68a09` -> pre-push passed `250` Python tests plus dashboard, Canva, MCP, workflow, and AutoResearch gates
- `python -m pytest tests\test_canva_mcp_openapi_contract.py tests\test_canva_widget_click_smoke.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q` -> `34 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-canva-search-continuation-action-2026-06-05.json` -> `6/6 passed`
- `python ops\scripts\autoresearch_completion_audit.py` -> `87 criteria`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py` -> `7 requirements`, `global_objective_complete=false`

## Completion State

- `protected_path_freshness` proof baseline: `cf229e73c22ce2fa5687448d2040e4a03dd68a09`
- `global_objective_complete=false`
