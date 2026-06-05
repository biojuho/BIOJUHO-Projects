# Agent Workflow Manifest - 2026-06-04

## Summary

- Workflows declared: 6
- Launch status counts: active=6
- Smoke scope counts: agriguard=1, desci=1, getdaytrends=1, mcp=2, workspace=1
- MCP server counts: canva-local=1, notion=2, playwright=6
- Generated at: `2026-06-04T20:27:50+09:00`

## Source Context

- Source: evalstate/fast-agent (https://github.com/evalstate/fast-agent)
- Adopted pattern: Declarative agent workflow inventory with MCP/server assignments, provider/runtime notes, and repeatable quality gates.

## Role Policy

- Source signal: strands-agents/harness-sdk fix: add maintain role to auto-strands-review allowed-roles (#2633)
- Source URL: https://github.com/strands-agents/harness-sdk/commit/050ab14955a4ee0adf7b2b21df0124b6c094630a
- Allowed agent roles: 15
- Review allowed roles: triage, write, maintain, admin

## Workflows

### dailynews-x-ops

- Project: `automation/DailyNews`
- Launch status: `active`
- Smoke scope: `mcp`
- Goal: Build ranked X/Twitter conversation packs and operator actions from DailyNews content intelligence.
- Agent roles: content-operator, conversation-ranker, x-publisher
- MCP servers: notion, playwright
- Entrypoints:
  - `automation/DailyNews/src/antigravity_mcp/cli_ops.py`
  - `automation/DailyNews/src/antigravity_mcp/tooling/ops_tools.py`
- Quality gates:
  - `python ops/scripts/run_workspace_smoke.py --scope mcp`
  - `python -m pytest tests/unit -q (cwd=automation/DailyNews)`
- Evidence:
  - `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_METRICS_2026-06-04.md`

### getdaytrends-operator-run

- Project: `automation/getdaytrends`
- Launch status: `active`
- Smoke scope: `getdaytrends`
- Goal: Collect trends, generate platform-ready content, and verify scheduler/operator readiness.
- Agent roles: trend-collector, content-generator, operator
- MCP servers: notion, playwright
- Entrypoints:
  - `automation/getdaytrends/main.py`
  - `automation/getdaytrends/run_scheduled_getdaytrends.ps1`
- Quality gates:
  - `python ops/scripts/run_workspace_smoke.py --scope getdaytrends`
  - `python -m pytest -c pytest.ini tests -q (cwd=automation/getdaytrends)`
- Evidence:
  - `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_2026-06-04.md`

### desci-launch-readiness

- Project: `apps/desci-platform`
- Launch status: `active`
- Smoke scope: `desci`
- Goal: Operate grant discovery, readiness scoring, browser smoke, and managed dev-server proof for DeSci launch paths.
- Agent roles: grant-analyst, browser-qa, release-operator
- MCP servers: playwright
- Entrypoints:
  - `apps/desci-platform/backend/main.py`
  - `apps/desci-platform/frontend/src/App.jsx`
  - `apps/desci-platform/scripts/browser_smoke.py`
- Quality gates:
  - `python ops/scripts/run_workspace_smoke.py --scope desci`
  - `python ops/scripts/dev_server_control.py start --target desci-frontend --wait-ready`
- Evidence:
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BROWSER_PASS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_DEV_SERVER_CONTROL_2026-06-04.md`

### agriguard-qr-product-verification

- Project: `apps/AgriGuard`
- Launch status: `active`
- Smoke scope: `agriguard`
- Goal: Verify QR visitor safety, product detail read-only mode, scan analytics, and product browser flow.
- Agent roles: product-qa, browser-qa, supply-chain-operator
- MCP servers: playwright
- Entrypoints:
  - `apps/AgriGuard/backend/main.py`
  - `apps/AgriGuard/frontend/src/App.jsx`
  - `apps/AgriGuard/frontend/src/components/QRReader.jsx`
  - `apps/AgriGuard/frontend/src/components/ProductDetail.jsx`
- Quality gates:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard`
  - `python -m pytest tests -q (cwd=apps/AgriGuard/backend)`
- Evidence:
  - `docs/reports/2026-06/AUTO_RESEARCH_AGRIGUARD_QR_PRODUCT_2026-06-04.md`

### canva-widget-oauth-preview

- Project: `mcp/canva-mcp`
- Launch status: `active`
- Smoke scope: `mcp`
- Goal: Run Canva widget preview, auth boundary checks, and MCP tool surface verification.
- Agent roles: mcp-operator, widget-qa, oauth-operator
- MCP servers: canva-local, playwright
- Entrypoints:
  - `mcp/canva-mcp/src/server/tools.ts`
  - `mcp/canva-mcp/src/server/auth.ts`
  - `mcp/canva-mcp/src/dev/preview.tsx`
- Quality gates:
  - `python ops/scripts/run_workspace_smoke.py --scope mcp`
  - `npm.cmd run dev:preview -- --host 127.0.0.1 --port 5176 --strictPort (cwd=mcp/canva-mcp)`
- Evidence:
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_WIDGET_PASS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_OAUTH_BOUNDARY_2026-06-04.md`

### workspace-quality-dashboard

- Project: `apps/dashboard`
- Launch status: `active`
- Smoke scope: `workspace`
- Goal: Surface workspace quality, smoke, dev-server readiness, and MCP trace evidence for operators.
- Agent roles: quality-operator, browser-qa, release-operator
- MCP servers: playwright
- Entrypoints:
  - `apps/dashboard/api.py`
  - `apps/dashboard/routers/gdt.py`
  - `apps/dashboard/src/components/QualityPanel.jsx`
- Quality gates:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace`
  - `npm.cmd run test -- src/App.test.jsx (cwd=apps/dashboard)`
- Evidence:
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_DEV_SERVER_READINESS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_METRICS_2026-06-04.md`

## Operating Decision

Keep this manifest declarative. Promote a workflow to runtime orchestration only after the listed quality gates are repeatable and the evidence paths remain current.
