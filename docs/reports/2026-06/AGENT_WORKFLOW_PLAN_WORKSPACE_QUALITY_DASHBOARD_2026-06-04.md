# Agent Workflow Dry-Run Plan - workspace-quality-dashboard

- Generated at: `2026-06-04T21:08:55.833281+09:00`
- Execution mode: `dry_run`
- Will execute: `false`
- Project: `apps/dashboard`
- Launch status: `active`
- Smoke scope: `workspace`
- Agent roles: `quality-operator, browser-qa, release-operator`
- MCP servers: `playwright`

## Steps

### entrypoint 1
- Action: `inspect`
- Path: `apps/dashboard/api.py`
- Dry run: `true`

### entrypoint 2
- Action: `inspect`
- Path: `apps/dashboard/routers/gdt.py`
- Dry run: `true`

### entrypoint 3
- Action: `inspect`
- Path: `apps/dashboard/src/components/QualityPanel.jsx`
- Dry run: `true`

### quality_gate 1
- Action: `run`
- CWD: `.`
- Command: `python ops/scripts/run_workspace_smoke.py --scope workspace`
- Dry run: `true`

### quality_gate 2
- Action: `run`
- CWD: `apps/dashboard`
- Command: `npm.cmd run test -- src/App.test.jsx`
- Dry run: `true`

### evidence 1
- Action: `review`
- Path: `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_DEV_SERVER_READINESS_2026-06-04.md`
- Dry run: `true`

### evidence 2
- Action: `review`
- Path: `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_METRICS_2026-06-04.md`
- Dry run: `true`
