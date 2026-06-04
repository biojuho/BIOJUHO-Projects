# AutoResearch: Current-Tip All-Scope Smoke

Date: 2026-06-04

## Scope

This report records the current remote-head launch gate after the DeSci
Firebase/CORS browser fix, the DeSci auth fallback loading lint fix, and the
remote AutoResearch completion-audit plus dev-server MCP runtime/subprocess
smoke, DeSci browser JSON evidence, workspace smoke check-timeout, Playwright
MCP radar source, and dev-server browser smoke proof slices.

- Smoke run commit: `d7f2403`
- Latest runtime/code/evidence commits included: `5542450`, `dcac1d6`,
  `fb5e41f`, `e161361`, `bed8e0c`, `1f049c6`, `0019feb`, `22ebc1a`,
  `2bc90cd`
- Branch: `feat/observability-gateway-2026-05`
- Latest repo-owned pre-push gate includes dev-server browser smoke tests,
  subprocess smoke, and completion audit

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.json --mcp-trace-out var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.otlp.jsonl
```

## Result

- Durable JSON summary: `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_CURRENT_TIP_2026-06-04.json`
- Status: `complete`
- Summary: `total=25`, `completed=25`, `passed=25`, `failed=0`,
  `remaining=0`
- Duration: `660.688s`

## Scope Summary

- `workspace`: `6/6 PASS`, `114.349s`
- `desci`: `7/7 PASS`, `217.743s`
- `agriguard`: `5/5 PASS`, `113.633s`
- `mcp`: `3/3 PASS`, `88.225s`
- `getdaytrends`: `2/2 PASS`, `86.567s`
- `cie`: `2/2 PASS`, `39.665s`

## Slowest Checks

- `desci frontend unit tests`: `107.939s`
- `DailyNews unit tests`: `87.227s`
- `getdaytrends tests`: `85.711s`
- `cie tests`: `39.049s`
- `shared package tests`: `32.754s`
- `agriguard frontend build`: `32.48s`
- `desci frontend lint`: `32.183s`
- `agriguard backend tests`: `31.816s`

## Trace Evidence

- Raw JSON report generated during the current-tip run:
  `var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.json`
- Raw MCP trace events:
  `var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.trace.jsonl`,
  with `3` `workspace_smoke.mcp_check` events
- Raw MCP OTLP export:
  `var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.otlp.jsonl`,
  with `1` `resourceSpans` line containing `3` spans
- MCP command kinds: `compileall=2`, `pytest=1`

## Hook Note

After rebasing over `5542450`, the repo-owned `ops\hooks\pre-push` includes
dev-server browser smoke tests, dev-server MCP runtime subprocess smoke, and
AutoResearch completion audit. Running `python ops\hooks\install_hooks.py`
refreshed the installed common hook at `D:\AI project\.git\hooks\pre-push`
before this final smoke refresh.

## Decision

The branch has current-tip all-scope launch proof after the DeSci auth/CORS
fixes, DeSci browser JSON evidence, dev-server MCP subprocess smoke,
completion-audit pre-push gate, workspace smoke check-timeout, Playwright MCP
radar source, and dev-server browser smoke proof slices. Future commits that
touch runtime code, smoke definitions, dependency manifests, test contracts, or
launch-critical documentation should refresh this proof before a release claim.
