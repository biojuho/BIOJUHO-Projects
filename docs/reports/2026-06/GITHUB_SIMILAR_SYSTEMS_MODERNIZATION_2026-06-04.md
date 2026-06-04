# GitHub Similar Systems Modernization Radar - 2026-06-04

## Summary

- Sources reviewed: 6
- Adoption counts: adopted=1, partially_adopted=4, watch=1
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
- Adoption status: `partially_adopted`
- Why similar: Production MCP framework with transport, auth, tooling, docs, and testing patterns relevant to local MCP projects.
- Observed patterns:
  - production MCP server composition and transport options
  - uv-first Python installation and upgrade workflow
  - LLM-readable documentation surface
- Local evidence:
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/stdio.ts`
  - `mcp/canva-mcp/tests`
  - `docs/MCP_HEALTH_CHECK.md`
- Gap: Python MCP services can evaluate FastMCP-style composition when the next MCP expansion is scoped.

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
  - `ops/scripts/workspace_smoke_report.py`
  - `apps/desci-platform/scripts/product_smoke.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `docs/QUALITY_GATE.md`
- Gap: MCP-specific trace metrics are not yet first-class in the workspace smoke schema.

### evalstate/fast-agent

- URL: https://github.com/evalstate/fast-agent
- Category: `agent-workflow-runtime`
- Adoption status: `partially_adopted`
- Why similar: Agent workflow runtime with MCP server composition, provider flexibility, workflow patterns, and tested glue code.
- Observed patterns:
  - declarative agent workflows and MCP server assignment
  - provider abstraction across OpenAI, Anthropic, Google, and local backends
  - token and tool-use tracking for agent runs
- Local evidence:
  - `packages/shared/harness/core.py`
  - `packages/shared/harness/adapters/native.py`
  - `packages/shared/harness/token_tracker.py`
  - `packages/shared/tests/test_workflow_trace.py`
- Gap: The shared harness has runtime pieces, but no single manifest that declares agent workflows for every app.

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
  - `ops/scripts/release_approval_check.py`
  - `docs/reports/2026-05/RELEASE_APPROVAL_WORKSPACE_2026-05-28.json`
  - `next-actions.md`
- Gap: No remaining structural gap for deterministic quality gates; future work should keep evidence current.

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
  - `docs/MCP_HEALTH_CHECK.md`
- Gap: The workspace does not yet publish MCP tools as OpenAPI endpoints; keep this as an interoperability option.

### Uninen/devserver-mcp

- URL: https://github.com/Uninen/devserver-mcp
- Category: `devserver-observability`
- Adoption status: `partially_adopted`
- Why similar: MCP-driven development server manager with process monitoring, log visibility, and Playwright automation.
- Observed patterns:
  - multiple local service process monitoring
  - browser automation as a first-class workflow capability
  - operator-facing runtime status
- Local evidence:
  - `ops/references/dev_server_targets.json`
  - `ops/scripts/dev_server_status.py`
  - `tests/test_dev_server_status.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `ops/scripts/workspace_smoke_report.py`
  - `docs/QUALITY_GATE.md`
- Gap: The workspace now has a manifest-backed live dev-server readiness probe; start-stop orchestration and log tailing remain future scoped work.

## Operating Decision

Keep the default smoke gate deterministic and offline. Use this radar as a supplemental, source-backed modernization contract; promote a gap into the default gate only after it has a local, repeatable check.
