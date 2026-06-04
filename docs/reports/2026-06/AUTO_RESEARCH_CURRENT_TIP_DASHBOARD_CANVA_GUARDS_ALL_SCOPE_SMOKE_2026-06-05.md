# Current Tip Dashboard Canva Guards All-Scope Smoke

## Scope

- Current remote tip: `9c86c89`
- Included recent guarded changes: Dashboard Operator Checklist browser-text guard, Canva click-smoke pre-push guard, Canva accessible widget controls, and the dashboard operator checklist product surface.
- Smoke command: `python ops\scripts\run_workspace_smoke.py --scope all --json-out docs\reports\2026-06\WORKSPACE_SMOKE_ALL_CURRENT_TIP_DASHBOARD_CANVA_GUARDS_2026-06-05.json --mcp-trace-out var\workspace-smoke-all-current-tip-dashboard-canva-guards-2026-06-05.trace.jsonl --mcp-otel-out var\workspace-smoke-all-current-tip-dashboard-canva-guards-2026-06-05.otlp.jsonl`

## Result

- status=complete
- total=25
- passed=25
- failed=0
- duration=557.185s
- MCP trace events: `3`
- OTLP lines: `1`

## Freshness

- `current_tip_freshness_gate` baseline: `9c86c89`
- `protected_path_freshness` baseline: `9c86c89`
- no changed protected paths after the all-scope proof baseline at the time this evidence commit was prepared.
- Latest guard push evidence included `145 passed` in the pre-push suite.
- `global_objective_complete=false`

## Residual Blockers

- Canva OAuth/OpenAPI execution still requires operator credentials and user consent.
- GitHub high-volume source refresh still needs `GITHUB_TOKEN` or `GH_TOKEN`.
- Telegram delivery still needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- OTLP collector shipping and hosted runtime/tracing remain operator-owned runtime choices.
