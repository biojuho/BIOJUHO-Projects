# AutoResearch: Current-Tip All-Scope Smoke

Date: 2026-06-04

## Scope

This report records the current remote-head launch gate after the DeSci
Firebase/CORS browser fix, the DeSci auth fallback loading lint fix, and the
remote AutoResearch completion-audit plus dev-server MCP runtime/subprocess
smoke and DeSci browser JSON evidence slices.

- Smoke run commit: `f18eafb`
- Latest runtime/code/evidence commits included: `1f049c6`, `0019feb`,
  `22ebc1a`, `2bc90cd`
- Branch: `feat/observability-gateway-2026-05`
- Latest repo-owned pre-push gate: `42 passed` plus subprocess smoke and
  completion audit

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-current-tip-post-browser-json-2026-06-04.json --mcp-trace-out var\workspace-smoke-all-current-tip-post-browser-json-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-all-current-tip-post-browser-json-2026-06-04.otlp.jsonl
```

## Result

- Durable JSON summary: `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_CURRENT_TIP_2026-06-04.json`
- Status: `complete`
- Summary: `total=25`, `completed=25`, `passed=25`, `failed=0`,
  `remaining=0`
- Duration: `593.724s`

## Scope Summary

- `workspace`: `6/6 PASS`, `93.808s`
- `desci`: `7/7 PASS`, `215.396s`
- `agriguard`: `5/5 PASS`, `85.397s`
- `mcp`: `3/3 PASS`, `79.375s`
- `getdaytrends`: `2/2 PASS`, `81.105s`
- `cie`: `2/2 PASS`, `38.2s`

## Slowest Checks

- `desci frontend unit tests`: `105.25s`
- `getdaytrends tests`: `80.406s`
- `DailyNews unit tests`: `78.549s`
- `cie tests`: `37.779s`
- `shared package tests`: `33.273s`
- `desci frontend lint`: `32.338s`
- `desci backend smoke`: `28.097s`
- `agriguard backend tests`: `27.857s`

## Trace Evidence

- Raw JSON report generated during the current-tip run:
  `var\workspace-smoke-all-current-tip-post-browser-json-2026-06-04.json`
- Raw MCP trace events:
  `var\workspace-smoke-all-current-tip-post-browser-json-2026-06-04.trace.jsonl`,
  with `3` `workspace_smoke.mcp_check` events
- Raw MCP OTLP export:
  `var\workspace-smoke-all-current-tip-post-browser-json-2026-06-04.otlp.jsonl`,
  with `1` `resourceSpans` line containing `3` spans
- MCP command kinds: `compileall=2`, `pytest=1`

## Hook Note

After rebasing over `1f049c6`, the repo-owned `ops\hooks\pre-push` includes the
dev-server MCP runtime subprocess smoke and AutoResearch completion audit.
Running `python ops\hooks\install_hooks.py` refreshed the installed common hook
at `D:\AI project\.git\hooks\pre-push` before this final smoke refresh.

## Decision

The branch has current-tip all-scope launch proof after the DeSci auth/CORS
fixes, DeSci browser JSON evidence, dev-server MCP subprocess smoke, and
completion-audit pre-push gate slices. Future commits that touch runtime code,
smoke definitions, dependency manifests, test contracts, or launch-critical
documentation should refresh this proof before a release claim.
