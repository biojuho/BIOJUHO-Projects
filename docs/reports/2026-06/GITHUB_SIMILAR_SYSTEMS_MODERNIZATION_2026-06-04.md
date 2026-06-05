# GitHub Similar Systems Modernization Radar - 2026-06-04

## Summary

- Sources reviewed: 6
- Adoption counts: adopted=4, partially_adopted=1, watch=1
- Generated at: `2026-06-04T12:25:00+09:00`

## Search Context

- Objective: Search GitHub for systems similar to this AI workspace and map current patterns into local modernization evidence.
- Queries:
  - `MCP server Python FastAPI monorepo agents workflow smoke tests`
  - `AI agent workflow automation monorepo quality gate`
  - `multi agent orchestration quality gates TDD Codex Claude Gemini`
  - `dev server MCP Playwright workflow automation`

## Source Mapping

### PrefectHQ/fastmcp

- URL: https://github.com/PrefectHQ/fastmcp
- Category: `production-mcp-framework`
- Adoption status: `adopted`
- Why similar: Production MCP framework with transport, auth, tooling, docs, and testing patterns relevant to local MCP projects.
- Observed patterns:
  - production MCP server composition and transport options
  - uv-first Python installation and upgrade workflow
  - LLM-readable documentation surface
- Local evidence:
  - `ops/references/mcp_services.json`
  - `ops/scripts/mcp_service_inventory.py`
  - `tests/test_mcp_service_inventory.py`
  - `docs/reports/2026-06/MCP_SERVICE_INVENTORY_2026-06-05.md`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/stdio.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `mcp/canva-mcp/tests/tool-inventory.test.mjs`
  - `mcp/canva-mcp/tests/stdio-auth.test.mjs`
  - `mcp/desci-research-mcp/server.py`
  - `mcp/telegram-mcp/server.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_STDIO_AUTH_CONTRACT_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
- Gap: No remaining structural gap for tracked MCP service inventory, stdio/http transport entrypoints, and composition metadata; future work can connect the inventory to live MCP health probes.

### lastmile-ai/mcp-eval

- URL: https://github.com/lastmile-ai/mcp-eval
- Category: `mcp-agent-evaluation`
- Adoption status: `partially_adopted`
- Why similar: MCP eval framework focused on real agent-to-server tests, observability, reports, and CI-friendly regression detection.
- Observed patterns:
  - real environment tests instead of mocks for agent tool paths
  - OpenTelemetry-backed observability and performance signals
  - JSON and HTML evidence suitable for CI
- Local evidence:
  - `ops/scripts/run_workspace_smoke.py`
  - `ops/scripts/mcp_smoke_trace_metrics.py`
  - `tests/test_mcp_smoke_trace_metrics.py`
  - `apps/desci-platform/scripts/product_smoke.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `docs/QUALITY_GATE.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_DEPTH_METRICS_2026-06-05.md`
- Gap: MCP smoke trace metrics now derive deterministic offline timing and path-depth signals from existing smoke artifacts; full OpenTelemetry span trees, token/cost metrics, and cross-step causality remain future scoped work.

### evalstate/fast-agent

- URL: https://github.com/evalstate/fast-agent
- Category: `agent-workflow-runtime`
- Adoption status: `adopted`
- Why similar: Agent workflow runtime with MCP server composition, provider flexibility, workflow patterns, and tested glue code.
- Observed patterns:
  - declarative agent workflows and MCP server assignment
  - provider abstraction across OpenAI, Anthropic, Google, and local backends
  - token and tool-use tracking for agent runs
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `tests/test_agent_workflow_manifest.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-05.md`
  - `packages/shared/harness/core.py`
  - `packages/shared/harness/adapters/native.py`
  - `packages/shared/harness/token_tracker.py`
  - `packages/shared/telemetry/workflow_trace.py`
- Gap: No remaining structural gap for declaring app-level agent workflows; future work can wire the manifest directly into runtime orchestration.

### dsifry/metaswarm

- URL: https://github.com/dsifry/metaswarm
- Category: `agentic-sdlc-quality-gates`
- Adoption status: `adopted`
- Why similar: Agentic SDLC framework organized around spec-driven execution, TDD enforcement, review gates, and durable learning records.
- Observed patterns:
  - quality gates before PR and release handoff
  - structured multi-phase work records
  - durable learning and next-action capture
- Local evidence:
  - `ops/scripts/run_workspace_smoke.py`
  - `ops/scripts/github_modernization_radar.py`
  - `tests/test_workspace_smoke.py`
  - `tests/test_github_modernization_radar.py`
  - `docs/QUALITY_GATE.md`
  - `next-actions.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_RADAR_TRACKED_EVIDENCE_GUARD_2026-06-05.md`
- Gap: No remaining structural gap for deterministic quality gates and tracked evidence manifests; future work should keep evidence current.

### open-webui/mcpo

- URL: https://github.com/open-webui/mcpo
- Category: `mcp-openapi-interop`
- Adoption status: `watch`
- Why similar: MCP-to-OpenAPI proxy pattern that makes MCP tools available through standard HTTP/OpenAPI contracts.
- Observed patterns:
  - OpenAPI-compatible HTTP exposure for MCP tools
  - tool-level docs and interoperability with non-MCP clients
  - API-key protected proxy operation
- Local evidence:
  - `mcp/canva-mcp/src/server/tools.ts`
  - `mcp/canva-mcp/src/server/auth.ts`
  - `mcp/canva-mcp/assets/preview.js`
  - `ops/references/mcp_services.json`
- Gap: The workspace does not yet publish MCP tools as OpenAPI endpoints; keep this as an interoperability option.

### Uninen/devserver-mcp

- URL: https://github.com/Uninen/devserver-mcp
- Category: `devserver-observability`
- Adoption status: `adopted`
- Why similar: MCP-driven development server manager with process monitoring, log visibility, and Playwright automation.
- Observed patterns:
  - multiple local service process monitoring
  - browser automation as a first-class workflow capability
  - operator-facing runtime status
- Local evidence:
  - `ops/references/dev_server_targets.json`
  - `ops/scripts/dev_server_status.py`
  - `ops/scripts/dev_server_control.py`
  - `tests/test_dev_server_status.py`
  - `tests/test_dev_server_control.py`
  - `docs/guides/dev-server-control.md`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `tests/test_workspace_smoke.py`
  - `docs/QUALITY_GATE.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_CONTROL_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_RUNBOOK_2026-06-04.md`
- Gap: No remaining structural gap for manifest-backed dev-server readiness, dependency-aware start-stop, log tailing, and operator runbook coverage; keep browser evidence current as target apps change.

## Operating Decision

Keep the default smoke gate deterministic and offline. Use this radar as a supplemental, source-backed modernization contract; promote a gap into the default gate only after it has a local, repeatable check.
