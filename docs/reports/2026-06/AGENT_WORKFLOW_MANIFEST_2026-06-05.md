# Agent Workflow Manifest - 2026-06-05

## Summary

- Workflows: 5
- Status counts: active=5
- Smoke scopes: desci=1, getdaytrends=1, mcp=2, workspace=1
- Providers: canva=1, google=1, local=5, openai=3
- Generated at: `2026-06-05T17:30:00+09:00`

## Workflows

### getdaytrends-content-loop

- Label: getdaytrends Content Loop
- Project: `getdaytrends`
- Status: `active`
- Smoke scope: `getdaytrends`
- Objective: Collect trends, analyze context, and generate operator-ready content artifacts.
- Providers: `openai`, `local`
- MCP servers: `none`
- Tools: `workspace-smoke`, `scheduler-json`, `content-qa`
- Entrypoints:
  - `automation/getdaytrends/main.py`
  - `automation/getdaytrends/run_scheduled_getdaytrends.ps1`
- Evidence:
  - `automation/getdaytrends/tests/test_main.py`
  - `automation/getdaytrends/QC_LOG.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_KARPATHY_SKILL_2026-06-04.md`

### dailynews-x-ops-loop

- Label: DailyNews X Ops Loop
- Project: `DailyNews`
- Status: `active`
- Smoke scope: `mcp`
- Objective: Build ranked discussion-ready X operations artifacts and verify the content tooling path.
- Providers: `openai`, `local`
- MCP servers: `none`
- Tools: `ops-doctor`, `x-conversation-pack`, `workspace-smoke`
- Entrypoints:
  - `automation/DailyNews/src/antigravity_mcp/cli_ops.py`
  - `automation/DailyNews/src/antigravity_mcp/tooling/ops_tools.py`
- Evidence:
  - `automation/DailyNews/tests/unit/test_tooling_content_ops.py`
  - `automation/DailyNews/devlog.md`
  - `docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`

### canva-mcp-widget-ops

- Label: Canva MCP Widget Ops
- Project: `canva-mcp`
- Status: `active`
- Smoke scope: `mcp`
- Objective: Expose Canva OAuth, tool inventory, and widget flows through MCP stdio and browser preview checks.
- Providers: `canva`, `local`
- MCP servers: `canva-local`
- Tools: `mcp-list-tools`, `widget-preview`, `oauth-doctor`
- Entrypoints:
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/stdio.ts`
- Evidence:
  - `mcp/canva-mcp/tests/stdio-auth.test.mjs`
  - `mcp/canva-mcp/tests/tool-inventory.test.mjs`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_TOOL_INVENTORY_GUARD_2026-06-05.md`

### desci-grant-readiness-agent

- Label: DeSci Grant Readiness Agent
- Project: `desci-platform`
- Status: `active`
- Smoke scope: `desci`
- Objective: Coordinate research asset ingestion, grant readiness, worker dispatch, and product smoke evidence.
- Providers: `openai`, `google`, `local`
- MCP servers: `none`
- Tools: `product-smoke`, `release-gate`, `worker-dispatch`
- Entrypoints:
  - `apps/desci-platform/backend/services/agent_service.py`
  - `apps/desci-platform/scripts/product_smoke.py`
- Evidence:
  - `apps/desci-platform/backend/tests/test_worker.py`
  - `apps/desci-platform/QC_LOG.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_DEV_SERVER_CONTROL_2026-06-04.md`

### workspace-quality-operator

- Label: Workspace Quality Operator
- Project: `dashboard`
- Status: `active`
- Smoke scope: `workspace`
- Objective: Aggregate workspace quality, smoke evidence, and dev-server readiness for operator review.
- Providers: `local`
- MCP servers: `none`
- Tools: `workspace-smoke`, `dev-server-status`, `quality-dashboard`
- Entrypoints:
  - `apps/dashboard/api.py`
  - `ops/scripts/run_workspace_smoke.py`
- Evidence:
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `tests/test_dashboard_api.py`
  - `ops/references/dev_server_targets.json`
