# AutoResearch: Current-Tip All-Scope Smoke

Date: 2026-06-04

## Scope

This report records the latest all-scope launch gate plus focused companion
proofs after the DeSci Firebase/CORS browser fix, the DeSci auth fallback
loading lint fix, the remote AutoResearch completion-audit plus dev-server MCP
runtime/subprocess smoke, DeSci browser JSON evidence, workspace smoke
check-timeout, Playwright MCP radar source, dev-server browser smoke proof
slices, and the Canva widget-preview browser/audit hardening slices.

- Smoke run commit for the all-scope command: `d7f2403`
- Latest evidence commits included: `0746be7`, `554e935`, `5542450`, `dcac1d6`,
  `fb5e41f`, `e161361`, `bed8e0c`, `1f049c6`, `0019feb`, `22ebc1a`,
  `2bc90cd`
- Companion proof commits after the all-scope run: `0746be7` and `554e935`
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

## Companion Evidence

The all-scope smoke command does not cover `mcp\canva-mcp`, so the newer Canva
commits are carried here as focused companion proof instead of being counted as
part of the `25/25` all-scope command:

- `554e935`: `canva-widget-preview` manifest-backed browser smoke passed
  `1/1` with `0` failures; report:
  `docs\reports\2026-06\AUTO_RESEARCH_CANVA_GENERIC_BROWSER_SMOKE_2026-06-04.md`;
  durable JSON:
  `docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.json`
- `0746be7`: Canva MCP npm audit cleanup resolved the browser-smoke install
  path to `0` vulnerabilities and kept `npm run build` green; report:
  `docs\reports\2026-06\AUTO_RESEARCH_CANVA_NPM_AUDIT_2026-06-04.md`;
  durable JSON:
  `docs\reports\2026-06\CANVA_NPM_AUDIT_2026-06-04.json`

## Hook Note

After rebasing over `0746be7`, the repo-owned `ops\hooks\pre-push` includes
dev-server browser smoke tests, dev-server MCP runtime subprocess smoke, and
AutoResearch completion audit. Running `python ops\hooks\install_hooks.py`
should refresh the installed common hook at `D:\AI project\.git\hooks\pre-push`
before pushing this final evidence refresh.

## Decision

The branch has current-tip all-scope launch proof after the DeSci auth/CORS
fixes, DeSci browser JSON evidence, dev-server MCP subprocess smoke,
completion-audit pre-push gate, workspace smoke check-timeout, Playwright MCP
radar source, and dev-server browser smoke proof slices. The newer Canva
widget-preview and npm-audit changes have separate focused companion proof
because they are outside the all-scope runner. Future commits that touch
runtime code, smoke definitions, dependency manifests, test contracts, or
launch-critical documentation should refresh either the all-scope gate or the
appropriate focused companion proof before a release claim.
