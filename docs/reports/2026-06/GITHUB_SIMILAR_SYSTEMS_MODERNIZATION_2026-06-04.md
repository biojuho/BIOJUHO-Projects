# GitHub Similar Systems Modernization Radar - 2026-06-04

## Summary

- Sources reviewed: 12
- Adoption counts: adopted=1, partially_adopted=11, watch=0
- Generated at: `2026-06-05T01:18:00+09:00`

## Search Context

- Objective: Search GitHub for systems similar to this AI workspace and map current patterns into local modernization evidence.
- Queries:
  - `MCP server Python FastAPI monorepo agents workflow smoke tests`
  - `MCP Python SDK FastMCP stdio tools/list streamable HTTP`
  - `AI agent workflow automation monorepo quality gate`
  - `multi agent orchestration quality gates TDD Codex Claude Gemini`
  - `OpenTelemetry Collector OTLP file exporter trace pipeline`
  - `dev server MCP Playwright workflow automation`
  - `MCP inspector CLI tools/list tools/call stdio automation`
  - `Playwright MCP browser automation accessibility snapshots`
  - `MCP gateway routing authorization lifecycle management`
  - `stateful agent workflow quality gates LangGraph durable execution human in the loop`

## Source Mapping

### PrefectHQ/fastmcp

- URL: https://github.com/PrefectHQ/fastmcp
- Category: `production-mcp-framework`
- Adoption status: `partially_adopted`
- Why similar: Production MCP framework with transport, auth, tooling, docs, and testing patterns relevant to local MCP projects.
- Observed patterns:
  - production MCP server composition and transport options
  - repo-local MCP service manifest for composition planning
  - runtime initialize and tools/list checks for stdio services
  - uv-first Python installation and upgrade workflow
  - LLM-readable documentation surface
- Local evidence:
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_manifest.py`
  - `ops/scripts/mcp_service_runtime_smoke.py`
  - `tests/test_mcp_service_manifest.py`
  - `tests/test_mcp_service_runtime_smoke.py`
  - `docs/reports/2026-06/MCP_SERVICE_MANIFEST_2026-06-04.json`
  - `docs/reports/2026-06/MCP_SERVICE_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.json`
  - `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `mcp/canva-mcp/src/server/auth.ts`
  - `ops/scripts/check_mcp_health.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_OAUTH_BOUNDARY_2026-06-04.md`
- Gap: Validated MCP service inventory and stdio runtime initialize/tools-list smoke are adopted for FastMCP-style composition planning; shared composition adapters and transport switching remain future-scoped until the next MCP expansion needs them.

### modelcontextprotocol/python-sdk

- URL: https://github.com/modelcontextprotocol/python-sdk
- Category: `official-mcp-python-sdk`
- Adoption status: `partially_adopted`
- Why similar: Official Python SDK for MCP clients and servers with FastMCP, stdio, SSE, Streamable HTTP, direct execution, and inspector testing patterns that match the repo-local Python MCP services.
- Observed patterns:
  - FastMCP as the Python server interface
  - standard stdio, SSE, and Streamable HTTP transports
  - initialize and tools/list as runtime readiness signals
  - direct server execution for local development
  - inspector-compatible tool discovery before agent use
- Local evidence:
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_manifest.py`
  - `ops/scripts/mcp_service_runtime_smoke.py`
  - `tests/test_mcp_service_manifest.py`
  - `tests/test_mcp_service_runtime_smoke.py`
  - `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.json`
  - `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Local stdio FastMCP services now prove initialize and tools/list readiness through a shared runtime smoke. Streamable HTTP/SSE transport switching and a shared hosted adapter remain future-scoped until a concrete non-stdio service expansion is selected.

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
  - validated collector handoff contract before live collector shipping
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
  - `ops/references/mcp_otel_collector_handoff.json`
  - `ops/scripts/mcp_otel_collector_handoff.py`
  - `tests/test_mcp_otel_collector_handoff.py`
  - `docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.json`
  - `docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Schema-level MCP smoke trace metrics, dashboard surfacing, standalone JSONL trace export, local OTLP file-exporter shaped span export, and the collector handoff validator are adopted; live OpenTelemetry SDK or collector shipping remains operator-owned future work.

### open-telemetry/opentelemetry-collector

- URL: https://github.com/open-telemetry/opentelemetry-collector
- Category: `otel-collector-observability`
- Adoption status: `partially_adopted`
- Why similar: Vendor-neutral telemetry collection, processing, and export is the closest upstream pattern for turning local smoke OTLP JSONL into an operator-owned observability pipeline.
- Observed patterns:
  - collector deployment as a separate operational component
  - explicit receiver, processor, exporter, connector, and extension policy
  - OTLP as a handoff boundary between local instrumentation and downstream systems
  - operator-owned endpoint, credential, retention, and retry decisions
  - local validation before live collector shipping
- Local evidence:
  - `ops/references/mcp_otel_collector_handoff.json`
  - `ops/scripts/mcp_otel_collector_handoff.py`
  - `tests/test_mcp_otel_collector_handoff.py`
  - `docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.json`
  - `docs/reports/2026-06/MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Collector handoff validation is adopted for real MCP smoke OTLP artifacts. Live collector deployment, OTLP endpoint credentials, retention, sampling, and retry policy remain future-scoped until the operator owns those runtime choices.

### evalstate/fast-agent

- URL: https://github.com/evalstate/fast-agent
- Category: `agent-workflow-runtime`
- Adoption status: `partially_adopted`
- Why similar: Agent workflow runtime with MCP server composition, provider flexibility, workflow patterns, and tested glue code.
- Observed patterns:
  - declarative agent workflows and MCP server assignment
  - repo-level launch workflow inventory
  - dry-run workflow plans with ordered inspect, run, and evidence steps
  - bounded workflow gate execution through declared quality gates
  - CLI-first agent workflow verification before autonomous runtime
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
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Declarative launch workflow inventory, dry-run command planning, and bounded quality-gate execution are adopted; live central runtime orchestration remains deliberate future work.

### langchain-ai/langgraph

- URL: https://github.com/langchain-ai/langgraph
- Category: `stateful-agent-orchestration`
- Adoption status: `partially_adopted`
- Why similar: Stateful agent orchestration framework for long-running workflows, durable execution, memory, and human-in-the-loop control that maps to the local agent workflow gap without requiring a premature hosted runtime.
- Observed patterns:
  - stateful workflow orchestration for long-running agents
  - durable execution as a runtime boundary
  - human-in-the-loop checkpoints before irreversible work
  - memory and state persistence for agent workflows
  - bounded quality-gate execution before adopting full orchestration
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `tests/test_agent_workflow_manifest.py`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Bounded workflow quality-gate execution is adopted through existing project CLIs and smoke gates. Full stateful LangGraph-style runtime orchestration, durable agent memory, human approval checkpoints, and hosted deployment remain future-scoped until the operator owns those runtime policies.

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

### modelcontextprotocol/inspector

- URL: https://github.com/modelcontextprotocol/inspector
- Category: `mcp-runtime-inspection`
- Adoption status: `partially_adopted`
- Why similar: Official MCP developer tool for testing and debugging MCP servers through UI and CLI modes.
- Observed patterns:
  - CLI mode for programmatic MCP server interaction
  - tools/list checks for runtime tool discovery
  - tools/call checks for runtime behavior validation
  - stdio transport support for local MCP subprocesses
  - scriptable feedback loops for MCP server development
- Local evidence:
  - `ops/scripts/dev_server_mcp_runtime.py`
  - `ops/scripts/dev_server_mcp_runtime_smoke.py`
  - `tests/test_dev_server_mcp_runtime.py`
  - `tests/test_dev_server_mcp_runtime_smoke.py`
  - `ops/hooks/pre-push`
  - `docs/guides/dev-server-control.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_SUBPROCESS_SMOKE_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_POLICY_TOOL_2026-06-05.md`
- Gap: Local subprocess smoke now validates initialize, tools/list, tools/call, get_devserver_policy, and the mutation guard. Full visual inspector or hosted TUI exposure remains future-scoped.

### microsoft/mcp-gateway

- URL: https://github.com/microsoft/mcp-gateway
- Category: `mcp-gateway-management`
- Adoption status: `partially_adopted`
- Why similar: MCP Gateway is a management and reverse-proxy layer for MCP servers with routing, authorization, lifecycle, telemetry, and observability concerns that match the local non-local-control policy gap.
- Observed patterns:
  - session-aware MCP server routing
  - authorization and access-control policy before wider MCP exposure
  - MCP server lifecycle management
  - telemetry and observability as gateway-level concerns
  - clear separation between local runtime behavior and network-facing control
- Local evidence:
  - `ops/scripts/dev_server_mcp_contract.py`
  - `ops/scripts/dev_server_mcp_runtime.py`
  - `ops/scripts/dev_server_mcp_runtime_smoke.py`
  - `tests/test_dev_server_mcp_contract.py`
  - `tests/test_dev_server_mcp_runtime.py`
  - `tests/test_dev_server_mcp_runtime_smoke.py`
  - `docs/guides/dev-server-control.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_POLICY_TOOL_2026-06-05.md`
- Gap: Local dev-server MCP policy introspection is adopted with stdio-only, no-network-exposure, local-only, and process-mutation-disabled defaults. A real network-facing gateway, authorization layer, or TUI remains future-scoped until an operator-owned access policy exists.

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

### microsoft/playwright-mcp

- URL: https://github.com/microsoft/playwright-mcp
- Category: `mcp-browser-automation`
- Adoption status: `partially_adopted`
- Why similar: Official Playwright MCP server for browser automation through structured page state, relevant to app-click QA and agent-driven UI inspection.
- Observed patterns:
  - browser automation through structured accessibility snapshots
  - agent-friendly app interaction without screenshot-only reasoning
  - CLI and skill workflows for token-efficient coding agents
  - optional browser capabilities such as vision, PDF, and DevTools
  - repeatable exploratory automation for long-running app QA loops
- Local evidence:
  - `ops/references/dev_server_browser_checks.json`
  - `ops/scripts/dev_server_browser_smoke.py`
  - `tests/test_dev_server_browser_smoke.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `tests/test_desci_browser_smoke.py`
  - `docs/reports/2026-06/DESCI_BROWSER_SMOKE_JSON_EVIDENCE_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DESCI_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_BROWSER_SMOKE_JSON_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CLICK_REFRESH_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGRIGUARD_LIVE_NAV_CLICK_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_GENERIC_BROWSER_SMOKE_2026-06-04.md`
  - `docs/QUALITY_GATE.md`
- Gap: Playwright browser automation is adopted through deterministic CLI smoke scripts and app-click evidence; a persistent MCP browser server remains future-scoped unless a workflow needs long-lived browser context or richer page-state introspection.

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
  - checked MCP tool definitions for dev-server status, start, stop, and logs
  - local stdio runtime for read-only operator status, policy, and logs
  - explicit opt-in boundary for process-mutating tool calls
  - machine-readable local-only and non-local-control policy
  - operator-facing runtime status
- Local evidence:
  - `ops/references/dev_server_targets.json`
  - `ops/references/dev_server_browser_checks.json`
  - `ops/scripts/dev_server_status.py`
  - `ops/scripts/dev_server_control.py`
  - `ops/scripts/dev_server_browser_smoke.py`
  - `ops/scripts/dev_server_mcp_contract.py`
  - `ops/scripts/dev_server_mcp_runtime.py`
  - `tests/test_dev_server_status.py`
  - `tests/test_dev_server_control.py`
  - `tests/test_dev_server_browser_smoke.py`
  - `tests/test_dev_server_mcp_contract.py`
  - `tests/test_dev_server_mcp_runtime.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `ops/scripts/run_workspace_smoke.py`
  - `docs/QUALITY_GATE.md`
  - `docs/guides/dev-server-control.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-05.md`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_CONTRACT_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_RUNTIME_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_POLICY_TOOL_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CLICK_REFRESH_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGRIGUARD_LIVE_NAV_CLICK_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_FIREBASE_CORS_BROWSER_2026-06-04.md`
  - `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_GENERIC_BROWSER_SMOKE_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_CONTROL_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_GROUP_STOP_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_DEV_SERVER_READINESS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_TABLE_STATUS_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_WORKSPACE_SMOKE_TIMEOUT_TREE_2026-06-04.md`
- Gap: CLI manifest-backed start, stop, status, tail, dashboard readiness, terminal table status, timeout-tree cleanup, checked MCP tool definitions, a local stdio MCP runtime, and read-only policy introspection are adopted. Full TUI exposure and a network-facing non-local authentication layer remain future-scoped; process mutation is available only through explicit local environment opt-in.

## Operating Decision

Keep the default smoke gate deterministic and offline. Use this radar as a supplemental, source-backed modernization contract; promote a gap into the default gate only after it has a local, repeatable check.
