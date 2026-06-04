# AutoResearch: Final All-Scope Smoke

Date: 2026-06-04

## Scope

This report records a clean-worktree monolithic launch-gate run after the
source-backed AutoResearch adoption slices through commit `de44114`.

Command:

```powershell
python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-final-2026-06-04.json --mcp-trace-out var\workspace-smoke-all-final-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-all-final-2026-06-04.otlp.jsonl
```

## Result

- Durable JSON summary: `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_FINAL_2026-06-04.json`
- Status: `complete`
- Summary: `total=25`, `completed=25`, `passed=25`, `failed=0`,
  `remaining=0`
- Duration: `1070.688s`
- Clean-worktree npm preflight installed dependencies for:
  `apps\dashboard`,
  `apps\desci-platform\frontend`,
  `apps\desci-platform\contracts`,
  `apps\AgriGuard\frontend`,
  `apps\AgriGuard\contracts`

## Scope Summary

- `workspace`: `6/6 PASS`, `102.771s`
- `desci`: `7/7 PASS`, `483.4s`
- `agriguard`: `5/5 PASS`, `157.564s`
- `mcp`: `3/3 PASS`, `74.388s`
- `getdaytrends`: `2/2 PASS`, `223.871s`
- `cie`: `2/2 PASS`, `28.171s`

## Slowest Checks

- `desci backend smoke`: `249.278s`
- `getdaytrends tests`: `221.431s`
- `desci frontend unit tests`: `126.868s`
- `agriguard backend tests`: `92.98s`
- `DailyNews unit tests`: `73.505s`
- `desci contracts compile`: `37.612s`
- `desci frontend lint`: `28.928s`
- `cie tests`: `26.546s`

## Trace Evidence

- Raw JSON report generated during the clean worktree run:
  `var\workspace-smoke-all-final-2026-06-04.json`
- Raw MCP trace events generated during the clean worktree run:
  `var\workspace-smoke-all-final-2026-06-04.trace.jsonl`, with `3`
  `workspace_smoke.mcp_check` events
- Raw MCP OTLP export generated during the clean worktree run:
  `var\workspace-smoke-all-final-2026-06-04.otlp.jsonl`, with `1`
  `resourceSpans` line containing `3` spans
- The durable repo-owned summary is
  `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_FINAL_2026-06-04.json`.
- MCP command kinds: `compileall=2`, `pytest=1`

## Post-Rebase Focused Validation

After the all-scope run completed, the remote branch advanced to `dccaad4` with
dev-server MCP contract and click-proof documentation. Those commits did not
change the all-scope smoke definitions or dependency manifests, so the final
report commit was rebased and the new focused surface was validated:

- `python -m py_compile ops\scripts\dev_server_mcp_contract.py ops\scripts\dev_server_status.py ops\scripts\dev_server_control.py`
  -> PASS
- `python -m pytest tests\test_dev_server_mcp_contract.py tests\test_dev_server_status.py tests\test_dev_server_control.py tests\test_github_modernization_radar.py -q -p no:cacheprovider`
  -> `28 passed`

## Decision

The branch has a clean-worktree all-scope proof through `de44114`. If later
commits touch runtime code, smoke definitions, dependency manifests, or tests,
rerun `--scope all`; docs-only/report-only commits can inherit this proof with
a focused validation note.
