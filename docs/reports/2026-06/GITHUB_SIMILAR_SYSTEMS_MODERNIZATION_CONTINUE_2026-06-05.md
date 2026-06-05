# GitHub Similar Systems Modernization Radar - 2026-06-04

## Summary

- Sources reviewed: 30
- Adoption counts: adopted=1, partially_adopted=29, watch=0
- Generated at: `2026-06-05T05:05:00+09:00`

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
  - `CrewAI flows production multi agent orchestration control plane`
  - `OpenAI Agents SDK sandbox agents guardrails sessions tracing`
  - `browser-use persistent browser automation AI agents CLI`
  - `Pydantic AI type-safe agent framework evals OpenTelemetry`
  - `HumanLayer coding agents human-in-the-loop control plane`
  - `Microsoft Agent Framework multi-agent workflows MCP A2A GitHub`
  - `Agno agent framework memory teams observability GitHub`
  - `Vercel AI SDK TypeScript agents tools AI Gateway GitHub`
  - `AutoGPT platform continuous agents workflow marketplace GitHub`
  - `Flowise low-code agent workflow builder GitHub`
  - `OpenHands autonomous coding agent SDK CLI local GUI GitHub`
  - `AutoGen multi-agent conversation framework GitHub`
  - `Google ADK code-first agent development kit GitHub`
  - `LlamaIndex document agent workflow orchestration GitHub`
  - `Strands Agents MCP OpenTelemetry multi-agent SDK GitHub`
  - `Haystack production LLM orchestration agent workflows GitHub`
  - `Mastra TypeScript AI agent framework GitHub`
  - `MCP Agent LastMile workflow patterns GitHub`

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
  - operator approval boundary for side-effecting workflow gates
  - launch matrix execution across declared workflows
  - duplicate deterministic gate reuse inside matrix execution
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
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_SAFETY_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Declarative launch workflow inventory, dry-run command planning, bounded quality-gate execution, targeted gate selection, side-effect approval skips, matrix execution across declared workflows, and duplicate deterministic gate reuse are adopted; live central runtime orchestration remains deliberate future work.

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
  - explicit approval before side-effecting gate execution
  - matrix verification before hosted orchestration
  - reuse of deterministic gate results to lower repeated workflow cost
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
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_SAFETY_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Bounded workflow quality-gate execution, targeted gate selection, side-effect approval skips, matrix execution, and deterministic gate reuse are adopted through existing project CLIs and smoke gates. Full stateful LangGraph-style runtime orchestration, durable agent memory, human approval UI, and hosted deployment remain future-scoped until the operator owns those runtime policies.

### crewAIInc/crewAI

- URL: https://github.com/crewAIInc/crewAI
- Category: `multi-agent-flow-control`
- Adoption status: `partially_adopted`
- Why similar: CrewAI combines autonomous crews with production-oriented Flows, tracing, control-plane concepts, and precise workflow control that map to the local launch workflow matrix without requiring a hosted agent platform.
- Observed patterns:
  - production-oriented flows for precise multi-step control
  - balance autonomy with deterministic workflow control
  - centralized monitoring and workflow visibility
  - controlled launch matrix before broad autonomous agent runtime
  - reuse of deterministic flow checks to reduce repeated launch-control cost
  - workflow evidence that separates deterministic gates from credential-bound or side-effecting actions
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
  - `next-actions.md`
- Gap: CrewAI-style flow control is partially adopted through a safe, deterministic launch matrix over repo-owned workflow gates plus duplicate deterministic gate reuse. A live CrewAI runtime, hosted control plane, tracing platform, and autonomous crew deployment remain future-scoped until operator-owned credentials and runtime policies exist.

### openai/openai-agents-python

- URL: https://github.com/openai/openai-agents-python
- Category: `openai-agent-runtime-sdk`
- Adoption status: `partially_adopted`
- Why similar: OpenAI's Agents SDK is a lightweight framework for multi-agent workflows with tools, handoffs, guardrails, human-in-the-loop, sessions, tracing, and sandbox agents that map directly to the local AutoResearch loop and launch workflow gates.
- Observed patterns:
  - multi-agent workflow framework with tools and handoffs
  - guardrails as explicit input and output validation
  - human-in-the-loop mechanisms across agent runs
  - sessions for long-running conversation history
  - tracing for debugging and optimizing agent workflows
  - sandbox agents for filesystem and command execution over long-horizon tasks
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `ops/scripts/autoresearch_completion_audit.py`
  - `tests/test_agent_workflow_manifest.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `tests/test_autoresearch_completion_audit.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_SAFETY_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_GITHUB_SOURCE_FRESHNESS_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Local AutoResearch workflows now cover tools-as-gates, side-effect guardrails, deterministic matrix execution, source freshness, and completion audits. Full OpenAI Agents SDK runtime adoption, hosted tracing, sessions, sandbox-agent execution, and human-in-the-loop UI remain future-scoped until a concrete runtime owner and credential policy are selected.

### browser-use/browser-use

- URL: https://github.com/browser-use/browser-use
- Category: `browser-agent-automation`
- Adoption status: `partially_adopted`
- Why similar: Browser Use focuses on making websites accessible to AI agents through browser automation, CLI state/click/type/screenshot flows, custom tools, and production browser considerations that match the user's computer-use app-click QA requirement.
- Observed patterns:
  - agent-accessible browser automation for real websites
  - CLI browser state, click, type, screenshot, and persistent session commands
  - custom tools to extend browser-agent capabilities
  - cloud or profile-backed browser sessions for authenticated flows
  - benchmarked real-world browser tasks for product QA
- Local evidence:
  - `ops/references/dev_server_browser_checks.json`
  - `ops/scripts/dev_server_browser_smoke.py`
  - `tests/test_dev_server_browser_smoke.py`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `tests/test_desci_browser_smoke.py`
  - `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DESCI_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_AGRIGUARD_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CLICK_REFRESH_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGRIGUARD_LIVE_NAV_CLICK_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_FIREBASE_CORS_BROWSER_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_GENERIC_BROWSER_SMOKE_2026-06-04.md`
- Gap: Deterministic app-click browser smokes are adopted across launch-critical local surfaces. A persistent browser-agent CLI, authenticated browser-profile reuse, cloud browser execution, and task-benchmark harness remain future-scoped until a specific app workflow needs them.

### pydantic/pydantic-ai

- URL: https://github.com/pydantic/pydantic-ai
- Category: `typed-agent-framework`
- Adoption status: `partially_adopted`
- Why similar: Pydantic AI emphasizes type-safe production-grade agent workflows, broad provider support, OpenTelemetry-style observability, evals, and composable capabilities, matching the local structured harness, smoke evidence, and completion-audit direction.
- Observed patterns:
  - type-safe agent framework for production workflows
  - model-agnostic provider abstraction
  - observability with OpenTelemetry-compatible tracing
  - systematic evals and monitoring for agent performance
  - composable capabilities that bundle tools, hooks, and instructions
- Local evidence:
  - `packages/shared/harness/core.py`
  - `packages/shared/harness/adapters/native.py`
  - `packages/shared/harness/token_tracker.py`
  - `packages/shared/harness/tests/test_harness.py`
  - `ops/scripts/run_workspace_smoke.py`
  - `ops/scripts/mcp_otel_collector_handoff.py`
  - `tests/test_mcp_otel_collector_handoff.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_FILE_EXPORT_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_TOOL_2026-06-04.md`
  - `docs/QUALITY_GATE.md`
- Gap: Structured harness, token tracking, deterministic smokes, OTLP-shaped evidence, and completion audits are adopted. A full Pydantic AI runtime, Logfire integration, typed agent result schemas, and provider abstraction migration remain future-scoped until a concrete agent application is selected.

### humanlayer/humanlayer

- URL: https://github.com/humanlayer/humanlayer
- Category: `human-in-loop-coding-agents`
- Adoption status: `partially_adopted`
- Why similar: HumanLayer targets AI coding agents in complex codebases, human-in-the-loop control, parallel coding sessions, and agent control-plane ideas that match the user's continuous Codex self-improvement loop without requiring live hosted execution.
- Observed patterns:
  - human-in-the-loop control for coding agents
  - parallel AI coding sessions and worktree-oriented workflows
  - context engineering for complex codebases
  - agent control-plane concepts for long-running work
  - explicit separation between open-source SDK and hosted/team workflow layers
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_SAFETY_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_REMAINING_GAP_AUDIT_2026-06-04.md`
  - `next-actions.md`
- Gap: Human-checkpoint-style side-effect skips, worktree-safe commit/push loops, durable next-action capture, and matrix quality gates are adopted. A hosted agent control plane, remote workers, multi-session UI, and live approval workflow remain future-scoped until operator-owned runtime policy exists.

### microsoft/agent-framework

- URL: https://github.com/microsoft/agent-framework
- Category: `enterprise-agent-framework`
- Adoption status: `partially_adopted`
- Why similar: Microsoft Agent Framework is the current Microsoft agent-workflow source for multi-agent orchestration, MCP/A2A interop, observability, and production agent runtime patterns that map to the local safe workflow-gate runner without requiring a hosted runtime switch.
- Observed patterns:
  - current Microsoft agent framework successor path instead of maintenance-mode AutoGen
  - multi-agent orchestration with explicit workflow boundaries
  - MCP and A2A interoperability as first-class agent runtime concerns
  - observable production agent execution
  - Python and .NET SDK boundaries for operator-owned runtime adoption
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_runtime_smoke.py`
  - `tests/test_mcp_service_runtime_smoke.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
  - `docs/QUALITY_GATE.md`
- Gap: Multi-agent workflow declarations, safe gate execution, MCP service runtime smoke, and observability handoff evidence are locally adopted. A live Microsoft Agent Framework runtime, A2A deployment, and SDK-level orchestration remain future-scoped until a concrete runtime owner and hosting policy exist.

### agno-agi/agno

- URL: https://github.com/agno-agi/agno
- Category: `full-stack-agent-platform`
- Adoption status: `partially_adopted`
- Why similar: Agno provides a full-stack agent platform with agents, teams, workflows, memory, knowledge, tool use, and observability patterns relevant to the local self-improving AutoResearch loop.
- Observed patterns:
  - agent teams and workflow abstractions
  - memory and knowledge as explicit runtime surfaces
  - observability and evaluation as product-readiness signals
  - tool-use integration for production assistants
  - separation between local framework adoption and hosted agent platform operation
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `ops/scripts/autoresearch_completion_audit.py`
  - `tests/test_autoresearch_completion_audit.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SOURCE_SNAPSHOT_FRESHNESS_2026-06-05.md`
  - `next-actions.md`
- Gap: The local loop adopts deterministic workflow gates, completion audits, and durable next-action memory. Agno-style persistent memory stores, hosted agent platform, team UI, and long-running runtime deployment remain future-scoped until operator-owned storage and approval policies are selected.

### vercel/ai

- URL: https://github.com/vercel/ai
- Category: `typescript-ai-app-toolkit`
- Adoption status: `partially_adopted`
- Why similar: Vercel AI SDK is a primary TypeScript toolkit for AI applications, agent tool calls, streaming UI, provider abstraction, and AI Gateway patterns that are relevant to the dashboard and TypeScript MCP surfaces.
- Observed patterns:
  - provider abstraction for AI app surfaces
  - tool calling and agent loop support for product workflows
  - streaming UI and app-router friendly AI UX patterns
  - AI Gateway and runtime deployment as separate production concerns
  - TypeScript-first ergonomics for frontend-facing AI features
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `ops/scripts/dev_server_browser_smoke.py`
  - `tests/test_dev_server_browser_smoke.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CLICK_REFRESH_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_GENERIC_BROWSER_SMOKE_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_POLICY_TOOL_2026-06-05.md`
- Gap: TypeScript app and MCP tool surfaces are browser-smoked and policy-gated locally. Vercel AI SDK runtime migration, streaming chat UX, AI Gateway deployment, and hosted frontend AI runtime remain future-scoped until a concrete user-facing AI feature is selected.

### Significant-Gravitas/AutoGPT

- URL: https://github.com/Significant-Gravitas/AutoGPT
- Category: `continuous-agent-platform`
- Adoption status: `partially_adopted`
- Why similar: AutoGPT is a long-running autonomous agent platform with workflow, marketplace, and deployment patterns related to the user's request for a continuous self-improving product loop.
- Observed patterns:
  - continuous agent workflow execution
  - agent platform packaging and deployment boundaries
  - marketplace-style reusable agent components
  - human operator oversight before broad autonomy
  - durable run evidence for long-running loops
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/autoresearch_completion_contract.json`
  - `ops/scripts/autoresearch_completion_audit.py`
  - `tests/test_autoresearch_completion_audit.py`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_SOURCE_SNAPSHOT_FRESHNESS_GATE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `next-actions.md`
- Gap: The local AutoResearch loop is continuous, evidence-backed, and commit/push oriented, but broad AutoGPT-style hosted platform deployment, marketplace packaging, and unattended autonomous execution remain future-scoped behind deterministic gates and explicit operator ownership.

### FlowiseAI/Flowise

- URL: https://github.com/FlowiseAI/Flowise
- Category: `low-code-agent-workflow-builder`
- Adoption status: `partially_adopted`
- Why similar: Flowise is a visual low-code builder for AI agents, workflows, and tool integrations; it is relevant to the local dashboard, dev-server control, and workflow manifest surfaces even though a visual builder is not yet adopted.
- Observed patterns:
  - visual workflow builder for agents and tools
  - operator-facing workflow inspection
  - template-style reusable agent flows
  - separation between builder UI and execution runtime
  - browser-verified UX as a launch-readiness concern
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `ops/scripts/dev_server_control.py`
  - `ops/scripts/dev_server_browser_smoke.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `tests/test_dev_server_browser_smoke.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CLICK_REFRESH_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_DEV_SERVER_READINESS_2026-06-04.md`
- Gap: Dashboard quality panels, workflow manifests, and browser-smoked operator surfaces are adopted. A Flowise-style visual agent builder, template marketplace, and runtime graph editor remain future-scoped until a concrete operator UX requirement is selected.

### dsifry/metaswarm

- URL: https://github.com/dsifry/metaswarm
- Category: `agentic-sdlc-quality-gates`
- Adoption status: `adopted`
- Why similar: Agentic SDLC framework organized around spec-driven execution, TDD enforcement, review gates, and durable learning records.
- Observed patterns:
  - quality gates before PR and release handoff
  - structured multi-phase work records
  - durable learning and next-action capture
  - matrix-style independent verification before trusting agent workflow reports
  - optimized reuse of repeated deterministic gates while preserving evidence
- Local evidence:
  - `ops/scripts/run_workspace_smoke.py`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_workspace_smoke.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
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

### OpenHands/OpenHands

- URL: https://github.com/OpenHands/OpenHands
- Category: `autonomous-coding-agent-platform`
- Adoption status: `partially_adopted`
- Why similar: OpenHands combines a software-agent SDK, CLI, REST API, local GUI, cloud deployment, and enterprise controls for AI-driven development, directly matching the user's Codex computer-use and self-improving launch-loop objective.
- Observed patterns:
  - software-agent SDK and CLI as separable operator surfaces
  - local GUI plus REST API for inspecting agent work
  - cloud and enterprise deployment boundaries with RBAC and permissions
  - skills and evaluation infrastructure as durable agent scaffolding
  - clear licensing boundary between open core and enterprise-only features
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
  - `ops/references/autoresearch_completion_contract.json`
  - `next-actions.md`
- Gap: Local AutoResearch skills, deterministic workflow gates, completion audits, and durable next-action capture are adopted. A hosted OpenHands-style agent GUI, RBAC layer, and cloud deployment remain future-scoped until the operator selects credentials, tenancy, and approval policy.

### microsoft/autogen

- URL: https://github.com/microsoft/autogen
- Category: `multi-agent-conversation-framework`
- Adoption status: `partially_adopted`
- Why similar: AutoGen provides autonomous and human-assisted multi-agent application patterns, useful as a comparison point for bounded AutoResearch loops and side-effect approvals.
- Observed patterns:
  - multi-agent collaboration around tasks and tools
  - human-assisted operation before risky actions
  - web browsing, code execution, and file-handling capabilities in agent teams
  - migration pressure toward Microsoft Agent Framework as the newer runtime
  - explicit separation between framework capability and local safety policy
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_SAFETY_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
- Gap: Bounded multi-agent gate execution and human-checkpoint-style side-effect skips are adopted. AutoGen runtime migration, autonomous web/code execution teams, and persistent conversation state remain future-scoped while Microsoft Agent Framework is the primary Microsoft successor source.

### google/adk-python

- URL: https://github.com/google/adk-python
- Category: `code-first-agent-development-kit`
- Adoption status: `partially_adopted`
- Why similar: Google ADK is a code-first Python toolkit for building, evaluating, and deploying agents with flexibility and control, matching the workspace's preference for repo-owned scripts and deterministic quality gates.
- Observed patterns:
  - agent logic and tools defined directly in Python
  - evaluation and deployment concerns treated as first-class
  - versioned code-first workflows instead of chat-only plans
  - local quality gates before deployment claims
  - credential and hosted-runtime choices separated from local proofs
- Local evidence:
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_manifest.py`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `tests/test_agent_workflow_manifest.py`
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_RUNNER_2026-06-05.md`
  - `ops/references/external_credential_boundaries.json`
- Gap: Code-first workflow manifests, Python gate execution, and credential-boundary tracking are adopted. ADK runtime deployment, hosted Agent Engine integration, and provider-specific credentials remain future-scoped.

### run-llama/llama_index

- URL: https://github.com/run-llama/llama_index
- Category: `document-agent-workflow-platform`
- Adoption status: `partially_adopted`
- Why similar: LlamaIndex focuses on document agents, workflows, and data-grounded application orchestration, relevant to the repo's DeSci and research-heavy launch surfaces.
- Observed patterns:
  - document-agent and OCR-oriented data workflows
  - retrieval and workflow steps kept inspectable
  - async workflow orchestration for agent applications
  - agent code focused on orchestration, business logic, and review
  - runtime durability and identity concerns treated as separate adoption choices
- Local evidence:
  - `apps/desci-platform`
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_FIREBASE_CORS_BROWSER_2026-06-04.md`
  - `docs/reports/2026-06/DESCI_BROWSER_SMOKE_JSON_EVIDENCE_2026-06-04.json`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
- Gap: Research-heavy DeSci browser proof and workflow gates are adopted. LlamaIndex-specific ingestion, OCR, AgentWorkflow runtime migration, and external document-provider credentials remain future-scoped until a concrete research-data workflow requires them.

### strands-agents/harness-sdk

- URL: https://github.com/strands-agents/harness-sdk
- Category: `model-driven-agent-sdk`
- Adoption status: `partially_adopted`
- Why similar: Strands Agents emphasizes model-agnostic agents, MCP, multi-agent patterns, deployment options, and OpenTelemetry, aligning with the workspace's MCP runtime and OTLP handoff work.
- Observed patterns:
  - model-agnostic provider abstraction
  - native MCP support for agent tools
  - multi-agent graph, swarm, and workflow patterns
  - OpenTelemetry observability for production agents
  - deployment choices spanning local, container, and cloud runtimes
- Local evidence:
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_runtime_smoke.py`
  - `ops/scripts/run_workspace_smoke.py`
  - `ops/scripts/mcp_otel_collector_handoff.py`
  - `tests/test_mcp_service_runtime_smoke.py`
  - `tests/test_mcp_otel_collector_handoff.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
- Gap: MCP initialize/tools-list smoke and OTLP handoff validation are adopted. Strands runtime migration, model-provider abstraction, live cloud deployment, and SDK-native multi-agent graphs remain future-scoped until a concrete hosted runtime is selected.

### deepset-ai/haystack

- URL: https://github.com/deepset-ai/haystack
- Category: `production-llm-orchestration`
- Adoption status: `partially_adopted`
- Why similar: Haystack is a production-oriented LLM orchestration framework with modular pipelines, agent workflows, retrieval, routing, memory, and debugging visibility, relevant to product-ready research and dashboard workflows.
- Observed patterns:
  - modular pipeline and agent workflow composition
  - explicit routing, retrieval, memory, and generation stages
  - inspectable decisions for debugging and optimization
  - production-grade orchestration without hiding credentials
  - separation of pipeline design from runtime deployment
- Local evidence:
  - `apps/desci-platform`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `ops/scripts/run_workspace_smoke.py`
  - `ops/references/agent_workflows.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CREDENTIAL_BOUNDARIES_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CREDENTIAL_BOUNDARIES_TIP_ALL_SCOPE_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DESCI_FIREBASE_CORS_BROWSER_2026-06-04.md`
- Gap: Dashboard quality visibility, DeSci browser proof, and deterministic workflow smoke are adopted. Haystack pipeline runtime, retrieval/memory backend selection, and hosted production orchestration remain future-scoped.

### mastra-ai/mastra

- URL: https://github.com/mastra-ai/mastra
- Category: `typescript-agent-application-framework`
- Adoption status: `partially_adopted`
- Why similar: Mastra is a TypeScript framework for AI-powered applications and agents, matching the dashboard and Canva TypeScript surfaces that need browser-visible, operator-facing behavior.
- Observed patterns:
  - TypeScript-first agent application structure
  - operator-facing agent workflows and UI surfaces
  - tool and runtime boundaries in application code
  - modern frontend integration for AI products
  - dual-license or hosted-runtime boundaries kept explicit
- Local evidence:
  - `apps/dashboard/src/App.jsx`
  - `apps/dashboard/src/components/QualityPanel.jsx`
  - `mcp/canva-mcp/src/server/server.ts`
  - `mcp/canva-mcp/src/server/tools.ts`
  - `ops/references/dev_server_browser_checks.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_DASHBOARD_CREDENTIAL_BOUNDARIES_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.md`
- Gap: TypeScript dashboard and Canva MCP tool surfaces are adopted with browser smoke and explicit execution boundaries. Mastra runtime migration, TypeScript-native agent workflows, and hosted deployment remain future-scoped.

### lastmile-ai/mcp-agent

- URL: https://github.com/lastmile-ai/mcp-agent
- Category: `mcp-agent-workflow-framework`
- Adoption status: `partially_adopted`
- Why similar: MCP Agent builds composable agents around Model Context Protocol and workflow patterns, directly matching the repo-local MCP service manifest, runtime smoke, and workflow gate matrix.
- Observed patterns:
  - MCP-native agent workflows
  - composable workflow patterns around tool servers
  - server discovery before agent execution
  - observability and controls for agent tool use
  - secret handling kept out of source control
- Local evidence:
  - `ops/references/mcp_service_manifest.json`
  - `ops/scripts/mcp_service_runtime_smoke.py`
  - `ops/scripts/dev_server_mcp_runtime_smoke.py`
  - `ops/references/agent_workflows.json`
  - `ops/scripts/agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_DEV_SERVER_MCP_POLICY_TOOL_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_AGENT_WORKFLOW_GATE_MATRIX_REUSE_2026-06-05.md`
- Gap: MCP service discovery, stdio runtime smoke, dev-server MCP policy, and workflow gate matrices are adopted. MCP Agent runtime migration and long-running agent server operation remain future-scoped pending hosted runtime and credential choices.

## Operating Decision

Keep the default smoke gate deterministic and offline. Use this radar as a supplemental, source-backed modernization contract; promote a gap into the default gate only after it has a local, repeatable check.
