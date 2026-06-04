# AutoResearch: Current-Tip All-Scope Smoke

Date: 2026-06-04

## Scope

This report records the current remote-head launch gate after the DeSci
Firebase/CORS browser fix, the DeSci auth fallback loading lint fix, and the
remote AutoResearch completion-audit plus dev-server MCP runtime slices.

- Worktree commit: `2bc90cd`
- Branch: `feat/observability-gateway-2026-05`
- Pre-push gate for the code slice: `36 passed`

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-current-tip-2bc90cd-2026-06-04.json --mcp-trace-out var\workspace-smoke-all-current-tip-2bc90cd-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-all-current-tip-2bc90cd-2026-06-04.otlp.jsonl
```

## Result

- Durable JSON summary: `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_CURRENT_TIP_2026-06-04.json`
- Status: `complete`
- Summary: `total=25`, `completed=25`, `passed=25`, `failed=0`,
  `remaining=0`
- Duration: `616.259s`

## Scope Summary

- `workspace`: `6/6 PASS`, `86.348s`
- `desci`: `7/7 PASS`, `220.403s`
- `agriguard`: `5/5 PASS`, `89.547s`
- `mcp`: `3/3 PASS`, `83.133s`
- `getdaytrends`: `2/2 PASS`, `85.827s`
- `cie`: `2/2 PASS`, `49.833s`

## Slowest Checks

- `desci frontend unit tests`: `113.14s`
- `getdaytrends tests`: `85.195s`
- `DailyNews unit tests`: `82.417s`
- `cie tests`: `49.337s`
- `shared package tests`: `32.288s`
- `desci frontend lint`: `28.997s`
- `desci backend smoke`: `28.874s`
- `agriguard backend tests`: `28.215s`

## Trace Evidence

- Raw JSON report generated during the current-tip run:
  `var\workspace-smoke-all-current-tip-2bc90cd-2026-06-04.json`
- Raw MCP trace events:
  `var\workspace-smoke-all-current-tip-2bc90cd-2026-06-04.trace.jsonl`,
  with `3` `workspace_smoke.mcp_check` events
- Raw MCP OTLP export:
  `var\workspace-smoke-all-current-tip-2bc90cd-2026-06-04.otlp.jsonl`,
  with `1` `resourceSpans` line containing `3` spans
- MCP command kinds: `compileall=2`, `pytest=1`

## Hook Note

The first push attempt after rebasing over the remote completion-audit slice was
blocked by a stale installed hook in `D:\AI project\.git\hooks\pre-push` that
still referenced `tests/test_dev_server_mcp_runtime_smoke.py`. The repo-owned
`ops\hooks\pre-push` at `HEAD` did not reference that missing file. Running
`python ops\hooks\install_hooks.py` refreshed the installed hook from the
repo-owned source, and the subsequent push gate passed with `36 passed`.

## Decision

The branch has current-tip all-scope launch proof through `2bc90cd`. Future
commits that touch runtime code, smoke definitions, dependency manifests, test
contracts, or launch-critical documentation should refresh this proof before a
release claim.
