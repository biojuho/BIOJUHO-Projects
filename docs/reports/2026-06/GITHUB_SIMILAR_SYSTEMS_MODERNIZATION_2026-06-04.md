# GitHub Similar Systems Modernization Radar - 2026-06-04

## Summary

- Sources reviewed: 6
- Adoption counts: adopted=1, partially_adopted=5, watch=0
- Generated at: `2026-06-04T21:35:16+09:00`

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
- Adoption status: `partially_adopted`
- Why similar: Production MCP framework with transport, auth, tooling, docs, and testing patterns relevant to local MCP projects.
- Observed patterns:
  - production MCP server composition and transport options
  - repo-local MCP service manifest for composition planning
  - uv-first Python installation and upgrade workflow
  - LLM-readable documentation surface
- Local evidence:
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_manifest.py`
  - `tests/test_mcp_service_manifest.py`
  - `docs/reports/2026-06/MCP_SERVICE_MANIFEST_2026-06-04.json`
  - `docs/reports/2026-06/MCP_SERVICE_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_MANIFEST_2026-06-04.md`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `mcp/canva-mcp/src/server/auth.ts`
  - `ops/scripts/check_mcp_health.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_OAUTH_BOUNDARY_2026-06-04.md`
- Gap: Validated MCP service inventory is adopted for FastMCP-style composition planning; runtime composition adapters and transport switching remain future-scoped until the next MCP expansion needs them.

### lastmile-ai/mcp-eval

- URL: https://github.com/lastmile-ai/mcp-eval
- Category: `mcp-agent-evaluation`
- Adoption status: `partially_adopted`
- Why similar: MCP eval framework focused on real agent-to-server tests, observability, reports, and CI-friendly regression detection.
- Observed patterns:
  - real environment tests instead of mocks for agent tool paths
  - schema-level trace metrics for MCP smoke evidence
  - standalone JSONL trace exports for external consumers
  - OpenTelemetry Protocol file-exporter shaped local span export
  - OpenTelemetry-backed observability and performance signals
  - JSON and HTML evidence suitable for CI
- Local evidence:
  - `ops/scripts/run_workspace_smoke.py`
  - `tests/test_smoke_report_readers.py`
  - `apps/desci-platform/scripts/product_smoke.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `apps/dashboard/routers/gdt.py`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_METRICS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_FILE_EXPORT_2026-06-04.md`
  - `docs/QUALITY_GATE.md`
- Gap: Schema-level MCP smoke trace metrics, dashboard surfacing, standalone JSONL trace export, and local OTLP file-exporter shaped span export are adopted; live OpenTelemetry SDK or collector shipping remains manual or scheduled.

### evalstate/fast-agent

- URL: https://github.com/evalstate/fast-agent
- Category: `agent-workflow-runtime`
- Adoption status: `partially_adopted`
- Why similar: Agent workflow runtime with MCP server composition, provider flexibility, workflow patterns, and tested glue code.
- Observed patterns:
  - declarative agent workflows and MCP server assignment
  - repo-level launch workflow inventory
  - dry-run workflow plans with ordered inspect, run, and evidence steps
  - provider abstraction across OpenAI, Anthropic, Google, and local backends
  - token and tool-use tracking for agent runs
- Local evidence:
  - `packages/shared/harness/core.py`
  - `packages/shared/harness/adapters/native.py`
  - `packages/shared/harness/token_tracker.py`
  - `packages/shared/harness/tests/test_harness.py`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `tests/test_agent_workflow_manifest.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
- Gap: Declarative launch workflow inventory and dry-run command planning are adopted; live central runtime orchestration remains deliberate future work.

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
  - `tests/test_workspace_smoke.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_2026-06-04.md`
  - `next-actions.md`
- Gap: No remaining structural gap for deterministic quality gates; future work should keep evidence current.

### open-webui/mcpo

- URL: https://github.com/open-webui/mcpo
- Category: `mcp-openapi-interop`
- Adoption status: `partially_adopted`
- Why similar: MCP-to-OpenAPI proxy pattern that makes MCP tools available through standard HTTP/OpenAPI contracts.
- Observed patterns:
  - OpenAPI-compatible HTTP exposure for MCP tools
  - offline OpenAPI contract for MCP tool inventory
  - read-only runtime OpenAPI metadata endpoints
  - explicit disabled execution response for OpenAPI call attempts
  - tool-level docs and interoperability with non-MCP clients
  - API-key protected proxy operation
- Local evidence:
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `mcp/canva-mcp/src/server/auth.ts`
  - `mcp/canva-mcp/src/types/css.d.ts`
  - `mcp/canva-mcp/tsconfig.build.json`
  - `mcp/canva-mcp/assets/preview.js`
  - `ops/scripts/check_mcp_health.py`
  - `ops/scripts/canva_mcp_openapi_contract.py`
  - `tests/test_canva_mcp_openapi_contract.py`
  - `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.json`
  - `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_WIDGET_PASS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.md`
- Gap: Canva MCP OpenAPI/tool metadata endpoints, offline contract generation, and explicit disabled execution responses are adopted; live OpenAPI tool execution proxy remains future-scoped until OAuth and proxy authentication are verified.

### Uninen/devserver-mcp

- URL: https://github.com/Uninen/devserver-mcp
- Category: `devserver-observability`
- Adoption status: `partially_adopted`
- Why similar: MCP-driven development server manager with process monitoring, log visibility, and Playwright automation.
- Observed patterns:
  - multiple local service process monitoring
  - manifest-backed start, stop, status, and log tailing
  - terminal table view for operator status checks
  - browser automation as a first-class workflow capability
  - contract-only MCP tool definitions for dev-server status, start, stop, and logs
  - operator-facing runtime status
- Local evidence:
  - `ops/references/dev_server_targets.json`
  - `ops/scripts/dev_server_status.py`
  - `ops/scripts/dev_server_control.py`
  - `ops/scripts/dev_server_mcp_contract.py`
  - `tests/test_dev_server_status.py`
  - `tests/test_dev_server_control.py`
  - `tests/test_dev_server_mcp_contract.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `ops/scripts/run_workspace_smoke.py`
  - `docs/QUALITY_GATE.md`
  - `docs/guides/dev-server-control.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_CONTRACT_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CLICK_REFRESH_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_CONTROL_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_GROUP_STOP_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_DEV_SERVER_READINESS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_TABLE_STATUS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_WORKSPACE_SMOKE_TIMEOUT_TREE_2026-06-04.md`
- Gap: CLI manifest-backed start, stop, status, tail, dashboard readiness, terminal table status, timeout-tree cleanup, and contract-only MCP tool definitions are adopted; live MCP runtime or TUI exposure remains watch-scoped until an authenticated process-control boundary is needed.

## Operating Decision

Keep the default smoke gate deterministic and offline. Use this radar as a supplemental, source-backed modernization contract; promote a gap into the default gate only after it has a local, repeatable check.
