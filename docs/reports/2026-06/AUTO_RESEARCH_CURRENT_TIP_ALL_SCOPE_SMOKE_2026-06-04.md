# AutoResearch: Current-Tip All-Scope Smoke

Date: 2026-06-04

## Scope

This report records the current remote-head launch gate after the DeSci
Firebase/CORS browser fix, the DeSci auth fallback loading lint fix, and the
remote AutoResearch completion-audit plus dev-server MCP runtime/subprocess
smoke slices.

- Smoke run commit: `4c09968` after rebasing over remote `22ebc1a`
- Latest runtime/code commits included: `22ebc1a`, `2bc90cd`
- Branch: `feat/observability-gateway-2026-05`
- Latest repo-owned pre-push gate: `38 passed` plus subprocess smoke

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-current-tip-post-mcp-subprocess-2026-06-04.json --mcp-trace-out var\workspace-smoke-all-current-tip-post-mcp-subprocess-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-all-current-tip-post-mcp-subprocess-2026-06-04.otlp.jsonl
```

## Result

- Durable JSON summary: `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_CURRENT_TIP_2026-06-04.json`
- Status: `complete`
- Summary: `total=25`, `completed=25`, `passed=25`, `failed=0`,
  `remaining=0`
- Duration: `798.968s`

## Scope Summary

- `workspace`: `6/6 PASS`, `141.323s`
- `desci`: `7/7 PASS`, `284.782s`
- `agriguard`: `5/5 PASS`, `141.619s`
- `mcp`: `3/3 PASS`, `91.949s`
- `getdaytrends`: `2/2 PASS`, `96.722s`
- `cie`: `2/2 PASS`, `42.07s`

## Slowest Checks

- `desci frontend unit tests`: `141.53s`
- `getdaytrends tests`: `95.771s`
- `DailyNews unit tests`: `91.292s`
- `desci frontend lint`: `45.063s`
- `cie tests`: `41.572s`
- `agriguard frontend lint`: `40.191s`
- `agriguard frontend build`: `37.25s`
- `desci backend smoke`: `37.184s`

## Trace Evidence

- Raw JSON report generated during the current-tip run:
  `var\workspace-smoke-all-current-tip-post-mcp-subprocess-2026-06-04.json`
- Raw MCP trace events:
  `var\workspace-smoke-all-current-tip-post-mcp-subprocess-2026-06-04.trace.jsonl`,
  with `3` `workspace_smoke.mcp_check` events
- Raw MCP OTLP export:
  `var\workspace-smoke-all-current-tip-post-mcp-subprocess-2026-06-04.otlp.jsonl`,
  with `1` `resourceSpans` line containing `3` spans
- MCP command kinds: `compileall=2`, `pytest=1`

## Hook Note

After rebasing over `22ebc1a`, the repo-owned `ops\hooks\pre-push` includes
`tests\test_dev_server_mcp_runtime_smoke.py` and
`ops\scripts\dev_server_mcp_runtime_smoke.py`. Running
`python ops\hooks\install_hooks.py` refreshed the installed common hook at
`D:\AI project\.git\hooks\pre-push` before this final smoke refresh.

## Decision

The branch has current-tip all-scope launch proof after the DeSci auth/CORS
fixes and the dev-server MCP subprocess smoke slice. Future commits that touch
runtime code, smoke definitions, dependency manifests, test contracts, or
launch-critical documentation should refresh this proof before a release claim.
