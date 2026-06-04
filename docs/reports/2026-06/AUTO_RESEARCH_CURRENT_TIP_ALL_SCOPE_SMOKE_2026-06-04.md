# AutoResearch: Current-Tip All-Scope Smoke

Date: 2026-06-04

## Scope

This report records the current remote-head launch gate after the DeSci
Firebase/CORS browser fix, the DeSci auth fallback loading lint fix, and the
remote AutoResearch completion-audit plus dev-server MCP runtime/subprocess
smoke, DeSci browser JSON evidence, workspace smoke check-timeout, and
Playwright MCP radar source slices.

- Smoke run commit: `02ccfbb`
- Latest runtime/code/evidence commits included: `e161361`, `bed8e0c`,
  `1f049c6`, `0019feb`, `22ebc1a`, `2bc90cd`
- Branch: `feat/observability-gateway-2026-05`
- Latest repo-owned pre-push gate: `42 passed` plus subprocess smoke and
  completion audit

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-current-tip-post-timeout-radar-2026-06-04.json --mcp-trace-out var\workspace-smoke-all-current-tip-post-timeout-radar-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-all-current-tip-post-timeout-radar-2026-06-04.otlp.jsonl
```

## Result

- Durable JSON summary: `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_CURRENT_TIP_2026-06-04.json`
- Status: `complete`
- Summary: `total=25`, `completed=25`, `passed=25`, `failed=0`,
  `remaining=0`
- Duration: `603.734s`

## Scope Summary

- `workspace`: `6/6 PASS`, `86.76s`
- `desci`: `7/7 PASS`, `215.868s`
- `agriguard`: `5/5 PASS`, `88.472s`
- `mcp`: `3/3 PASS`, `84.864s`
- `getdaytrends`: `2/2 PASS`, `86.976s`
- `cie`: `2/2 PASS`, `40.299s`

## Slowest Checks

- `desci frontend unit tests`: `114.391s`
- `getdaytrends tests`: `86.312s`
- `DailyNews unit tests`: `83.881s`
- `cie tests`: `39.899s`
- `shared package tests`: `32.894s`
- `agriguard backend tests`: `29.305s`
- `desci backend smoke`: `28.485s`
- `desci frontend build`: `26.007s`

## Trace Evidence

- Raw JSON report generated during the current-tip run:
  `var\workspace-smoke-all-current-tip-post-timeout-radar-2026-06-04.json`
- Raw MCP trace events:
  `var\workspace-smoke-all-current-tip-post-timeout-radar-2026-06-04.trace.jsonl`,
  with `3` `workspace_smoke.mcp_check` events
- Raw MCP OTLP export:
  `var\workspace-smoke-all-current-tip-post-timeout-radar-2026-06-04.otlp.jsonl`,
  with `1` `resourceSpans` line containing `3` spans
- MCP command kinds: `compileall=2`, `pytest=1`

## Hook Note

After rebasing over `1f049c6`, the repo-owned `ops\hooks\pre-push` includes the
dev-server MCP runtime subprocess smoke and AutoResearch completion audit.
Running `python ops\hooks\install_hooks.py` refreshed the installed common hook
at `D:\AI project\.git\hooks\pre-push` before this final smoke refresh.

## Decision

The branch has current-tip all-scope launch proof after the DeSci auth/CORS
fixes, DeSci browser JSON evidence, dev-server MCP subprocess smoke,
completion-audit pre-push gate, workspace smoke check-timeout, and Playwright
MCP radar source slices. Future commits that touch runtime code, smoke
definitions, dependency manifests, test contracts, or launch-critical
documentation should refresh this proof before a release claim.
