# AutoResearch MCP Trace Metrics - 2026-06-04

## Source-Backed Candidate

- Source: `lastmile-ai/mcp-eval` (`https://github.com/lastmile-ai/mcp-eval`)
- Radar gap: MCP-specific trace metrics were not first-class in the workspace smoke schema.
- Local constraint: the default smoke gate must stay deterministic and offline.

## Adopted Variant

- Added `scope_summary` to `ops/scripts/run_workspace_smoke.py` JSON reports.
- Added `mcp_trace` to the same JSON schema with MCP counts, elapsed time, checked units, command kinds, and per-check status.
- Passed `scope_summary` and `mcp_trace` through `/api/quality_overview`.
- Added a compact `MCP Trace` section to the dashboard Quality panel.
- Updated `docs/QUALITY_GATE.md` so the new fields are part of the documented schema contract.

## Verification

- `python -m pytest tests\test_workspace_smoke.py tests\test_smoke_report_readers.py tests\test_dashboard_api.py::TestQualityOverview::test_includes_workspace_smoke_slowest_checks -q -p no:cacheprovider`
  - `22 passed`
- `npm.cmd run test -- src/App.test.jsx`
  - `1` test file, `6` tests passed
- `python ops\scripts\run_workspace_smoke.py --scope mcp --json-out var\workspace-smoke-mcp-trace-metrics-2026-06-04.json`
  - `3/3` MCP checks passed
  - `mcp_trace.enabled=true`
  - `mcp_trace.command_kinds={"compileall": 2, "pytest": 1}`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-mcp-trace-2026-06-04.json`
  - `6/6` workspace checks passed
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-mcp-trace-final-2026-06-04.json`
  - `6/6` workspace checks passed after the dashboard fallback change
- Managed dashboard proof:
  - Start: `python ops\scripts\dev_server_control.py --json-out var\dashboard-mcp-trace-start-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90`
  - Status: `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --wait-ready --wait-timeout 30 --json-out var\dashboard-mcp-trace-status-2026-06-04.json`
  - Browser proof: `var/dashboard-mcp-trace-panel-2026-06-04.png`
  - Browser result: `Workspace Smoke=1`, `MCP Trace=1`, `3/3 PASS` badges=`2`, `DailyNews unit tests` rows=`2`, `pytest=1`, console issues=`0`, page errors=`0`, failed requests=`0`
  - Stop: `python ops\scripts\dev_server_control.py --json-out var\dashboard-mcp-trace-stop-2026-06-04.json stop --target dashboard-frontend --include-dependencies`
  - Final status: `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --json-out var\dashboard-mcp-trace-status-after-stop-2026-06-04.json` returned `0/2 ready`
- Fallback dashboard proof after a newer workspace-only smoke report:
  - Start: `python ops\scripts\dev_server_control.py --json-out var\dashboard-mcp-trace-fallback-start-2026-06-04.json start --target dashboard-frontend --wait-ready --wait-timeout 90`
  - Status: `python ops\scripts\dev_server_status.py --target dashboard-api --target dashboard-frontend --wait-ready --wait-timeout 30 --json-out var\dashboard-mcp-trace-fallback-status-2026-06-04.json`
  - Browser proof: `var/dashboard-mcp-trace-fallback-panel-2026-06-04.png`
  - Browser result: `Workspace Smoke=1`, `MCP Trace=1`, workspace `6/6 PASS=1`, MCP `3/3 PASS=1`, `DailyNews unit tests=1`, `pytest=1`, console issues=`0`, page errors=`0`, failed requests=`0`
  - Stop plus final status returned `0/2 ready`

## Remaining Gap

External live MCP trace export and OpenTelemetry-style spans are still outside the deterministic default smoke gate. Keep those in manual or scheduled MCP health workflows until they have a repeatable local contract.
