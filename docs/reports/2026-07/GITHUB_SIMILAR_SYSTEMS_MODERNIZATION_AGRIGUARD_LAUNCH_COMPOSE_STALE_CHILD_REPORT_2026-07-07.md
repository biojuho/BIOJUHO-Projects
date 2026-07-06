# GitHub Similar Systems Modernization Radar - 2026-06-11

## Summary

- Sources reviewed: 8
- Adoption counts: adopted=8, partially_adopted=0, watch=0
- Local evidence tracking: all 103 paths exist and are git-tracked
- Generated at: `2026-06-11T19:02:02+09:00`
- Rendered at: `2026-07-06T16:02:40.937269+00:00`
- Latest commit refresh: 8 GitHub HEAD refs checked at `2026-07-06T16:02:35.254426+00:00`; updated=6, failed=0, review_required=6

## Search Context

- Objective: Search GitHub for systems similar to this AI workspace and map current patterns into local modernization evidence.
- Queries:
  - `MCP server Python FastAPI monorepo agents workflow smoke tests`
  - `AI agent workflow automation monorepo quality gate`
  - `multi agent orchestration quality gates TDD Codex Claude Gemini`
  - `dev server MCP Playwright workflow automation`
  - `Codex AutoResearch skill self improvement harness stop file watchdog A/B`
  - `AI agent readiness GitHub CI quality gate JSON dashboard`

## Refresh Review Queue

| Repo | Status | Category | Local review targets | Compare |
| --- | --- | --- | --- | --- |
| PrefectHQ/fastmcp | `updated` | `production-mcp-framework` | `ops/references/mcp_services.json`<br>`ops/scripts/mcp_service_inventory.py`<br>`ops/scripts/check_mcp_health.py`<br>`tests/test_mcp_service_inventory.py`<br>`docs/reports/2026-06/MCP_SERVICE_INVENTORY_2026-06-05.md` | [compare](https://github.com/PrefectHQ/fastmcp/compare/3b8538e2422a1c43fdb69661c610de7985b785f2...1eedd1f6f1402d9b93a6c8197bfe3106c7292894) |
| evalstate/fast-agent | `updated` | `agent-workflow-runtime` | `ops/references/agent_workflows.json`<br>`ops/scripts/agent_workflow_manifest.py`<br>`tests/test_agent_workflow_manifest.py`<br>`docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-05.md`<br>`packages/shared/harness/core.py` | [compare](https://github.com/evalstate/fast-agent/compare/6d3a8519807fbbffd84e81c44da7e5cc62cab11e...e5eb112135c38c2ef4c56222820a962fae21314a) |
| Veritas-7/autoresearch-skill-system | `updated` | `autoresearch-skill-evolution` | `.agents/skills/auto-research-karpathy/SKILL.md`<br>`.agents/skills/auto-research-karpathy/references/source-backed-patterns.md`<br>`.agents/skills/auto-research-karpathy/references/workspace-loop.md`<br>`.agents/skills/auto-research-karpathy/examples/self-improvement-cycle.yaml`<br>`.agents/skills/auto-research-karpathy/scripts/validate_skill.py` | [compare](https://github.com/Veritas-7/autoresearch-skill-system/compare/a72f83aa766ed588c43436090ecabc0945ab8b7b...b8bbf393759d6e67e780f03c572ec626fab6593b) |
| kodustech/agent-readiness | `updated` | `agent-readiness-gate` | `ops/scripts/run_workspace_smoke.py`<br>`.github/workflows/workspace-smoke.yml`<br>`ops/scripts/github_modernization_radar.py`<br>`tests/test_github_modernization_radar.py`<br>`docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md` | [compare](https://github.com/kodustech/agent-readiness/compare/aedf9bbebfce162aadbf9c2f5647c15a3fafd657...6cb41fa749c0f601ec2803238e7d2e3b956f8076) |
| dsifry/metaswarm | `updated` | `agentic-sdlc-quality-gates` | `ops/scripts/run_workspace_smoke.py`<br>`ops/scripts/github_modernization_radar.py`<br>`tests/test_workspace_smoke.py`<br>`tests/test_github_modernization_radar.py`<br>`docs/QUALITY_GATE.md` | [compare](https://github.com/dsifry/metaswarm/compare/398be78231bc1c57b147869c5c80696003e95f31...33d39f776f7fe29098dcf048955756a237e8cb40) |
| Uninen/devserver-mcp | `updated` | `devserver-observability` | `ops/references/dev_server_targets.json`<br>`ops/scripts/dev_server_status.py`<br>`ops/scripts/dev_server_control.py`<br>`tests/test_dev_server_status.py`<br>`tests/test_dev_server_control.py` | [compare](https://github.com/Uninen/devserver-mcp/compare/e443bcb42c25cdb11d3f8351d5d23d58fb29769b...5f62b28d948d86a9ac1f803ecebf9926caa5cc77) |


## Source Mapping

### PrefectHQ/fastmcp

- URL: https://github.com/PrefectHQ/fastmcp
- Category: `production-mcp-framework`
- Adoption status: `adopted`
- Why similar: Production MCP framework with transport, auth, tooling, docs, and testing patterns relevant to local MCP projects.
- Latest observed commit: `1eedd1f6f1402d9b93a6c8197bfe3106c7292894`
- Observed patterns:
  - production MCP server composition and transport options
  - uv-first Python installation and upgrade workflow
  - LLM-readable documentation surface
- Local evidence:
  - `ops/references/mcp_services.json`
  - `ops/scripts/mcp_service_inventory.py`
  - `ops/scripts/check_mcp_health.py`
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
- Gap: No remaining structural gap for tracked MCP service inventory, stdio/http transport entrypoints, composition metadata, and Codex MCP config health coverage. Current bridge evidence now links inventory to MCP health reports; the remaining operational gap is stabilizing nested live MCP probes when codex exec child processes terminate early.

### lastmile-ai/mcp-eval

- URL: https://github.com/lastmile-ai/mcp-eval
- Category: `mcp-agent-evaluation`
- Adoption status: `adopted`
- Why similar: MCP eval framework focused on real agent-to-server tests, observability, reports, and CI-friendly regression detection.
- Latest observed commit: `7c0f4d1072d0deb6a36a178312c83023cdd96b69`
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
  - `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_MARKDOWN_REPORT_2026-06-05.md`
  - `docs/reports/2026-06/MCP_SMOKE_TRACE_METRICS_2026-06-05.html`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_HTML_REPORT_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_USAGE_METRICS_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_SPAN_TREE_2026-06-05.md`
  - `docs/reports/2026-06/MCP_SMOKE_TRACE_OTEL_2026-06-05.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_OTEL_EXPORT_2026-06-05.md`
  - `docs/reports/2026-06/MCP_SMOKE_TRACE_OTEL_SUBMIT_2026-06-05.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_OTEL_SUBMIT_2026-06-05.md`
  - `automation/DailyNews/src/antigravity_mcp/integrations/llm/client_wrapper.py`
  - `tests/test_dailynews_llm_usage_sidecar.py`
  - `tests/test_workspace_smoke_usage_sidecar.py`
  - `docs/reports/2026-06/WORKSPACE_SMOKE_USAGE_SIDECAR_2026-06-05.json`
  - `docs/reports/2026-06/MCP_SMOKE_TRACE_USAGE_SIDECAR_2026-06-05.json`
  - `docs/reports/2026-06/MCP_SMOKE_TRACE_USAGE_SIDECAR_2026-06-05.md`
  - `docs/reports/2026-06/MCP_SMOKE_TRACE_USAGE_SIDECAR_OTEL_2026-06-05.json`
  - `docs/reports/2026-06/AUTO_RESEARCH_MCP_TRACE_LIVE_USAGE_EMISSION_2026-06-05.md`
- Gap: No remaining structural gap for MCP eval-style evidence: real smoke checks, token/cost sidecar emission, trace usage summaries, ordered span trees, Markdown/HTML handoff reports, OTEL-style JSON export, and opt-in local collector submission are tracked; future work can expand sidecar emission to wrappers that bypass the DailyNews LLM client.

### evalstate/fast-agent

- URL: https://github.com/evalstate/fast-agent
- Category: `agent-workflow-runtime`
- Adoption status: `adopted`
- Why similar: Agent workflow runtime with MCP server composition, provider flexibility, workflow patterns, and tested glue code.
- Latest observed commit: `e5eb112135c38c2ef4c56222820a962fae21314a`
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

### Veritas-7/autoresearch-skill-system

- URL: https://github.com/Veritas-7/autoresearch-skill-system
- Category: `autoresearch-skill-evolution`
- Adoption status: `adopted`
- Why similar: Codex-first AutoResearch skill and self-improvement harness with bounded continuous operation, A/B adoption, source-backed archives, and completion audits.
- Latest observed commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Observed patterns:
  - same-sample A/B checks before adoption
  - continuous mode controlled by stop-file, lock, watchdog, and status evidence
  - fail-closed durable archives and completion audits before trusting a harness update
- Local evidence:
  - `.agents/skills/auto-research-karpathy/SKILL.md`
  - `.agents/skills/auto-research-karpathy/references/source-backed-patterns.md`
  - `.agents/skills/auto-research-karpathy/references/workspace-loop.md`
  - `.agents/skills/auto-research-karpathy/examples/self-improvement-cycle.yaml`
  - `.agents/skills/auto-research-karpathy/scripts/validate_skill.py`
  - `tests/test_auto_research_karpathy_skill.py`
  - `ops/references/github_modernization_sources.json`
  - `ops/scripts/github_modernization_radar.py`
  - `tests/test_github_modernization_radar.py`
- Gap: No remaining structural gap for local AutoResearch skill guidance: the named source repo is tracked as a first-class modernization source, continuous-mode safety semantics are documented, and the local validator/radar tests cover the contract; future work can build a Windows-native managed runner if product scope requires background execution.

### kodustech/agent-readiness

- URL: https://github.com/kodustech/agent-readiness
- Category: `agent-readiness-gate`
- Adoption status: `adopted`
- Why similar: Open-source codebase readiness checker for autonomous AI coding agents with pillars for linting, testing, documentation, dev environment, CI/CD, code health, and security.
- Latest observed commit: `6cb41fa749c0f601ec2803238e7d2e3b956f8076`
- Observed patterns:
  - multi-pillar readiness scoring for autonomous coding agents
  - CI/CD gating with minimum maturity thresholds
  - JSON and dashboard evidence for operator-facing readiness review
- Local evidence:
  - `ops/scripts/run_workspace_smoke.py`
  - `.github/workflows/workspace-smoke.yml`
  - `ops/scripts/github_modernization_radar.py`
  - `tests/test_github_modernization_radar.py`
  - `docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - `docs/QUALITY_GATE.md`
  - `apps/desci-platform/scripts/browser_smoke.py`
  - `next-actions.md`
  - `HANDOFF.md`
- Gap: No remaining structural gap for source-backed readiness mapping: local workspace smoke, CI quality workflow, browser smoke, radar validation, durable handoff, and next-action surfaces are tracked; current AutoResearch status now also emits a first-class numerical readiness score, with commit-bound promotion left to the next tracked evidence sweep.

### dsifry/metaswarm

- URL: https://github.com/dsifry/metaswarm
- Category: `agentic-sdlc-quality-gates`
- Adoption status: `adopted`
- Why similar: Agentic SDLC framework organized around spec-driven execution, TDD enforcement, review gates, and durable learning records.
- Latest observed commit: `33d39f776f7fe29098dcf048955756a237e8cb40`
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
- Adoption status: `adopted`
- Why similar: MCP-to-OpenAPI proxy pattern that makes MCP tools available through standard HTTP/OpenAPI contracts.
- Latest observed commit: `788ff92e5288a899a743a252edd5748f4ad4ab1f`
- Observed patterns:
  - OpenAPI-compatible HTTP exposure for MCP tools
  - tool-level docs and interoperability with non-MCP clients
  - API-key protected proxy operation
- Local evidence:
  - `mcp/canva-mcp/src/server/tools.ts`
  - `mcp/canva-mcp/src/server/auth.ts`
  - `ops/scripts/canva_mcp_openapi_contract.py`
  - `tests/test_canva_mcp_openapi_contract.py`
  - `ops/scripts/canva_mcp_proxy_readiness.py`
  - `tests/test_canva_mcp_proxy_readiness.py`
  - `ops/scripts/canva_mcp_proxy_live_smoke.py`
  - `tests/test_canva_mcp_proxy_live_smoke.py`
  - `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.json`
  - `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_OPENAPI_CONTRACT_2026-06-05.md`
  - `docs/reports/2026-06/CANVA_MCP_PROXY_READINESS_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_PROXY_READINESS_2026-06-05.md`
  - `docs/reports/2026-06/CANVA_MCP_PROXY_LIVE_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_PROXY_LIVE_SMOKE_2026-06-05.md`
  - `docs/reports/2026-06/AUTO_RESEARCH_CANVA_AUTH_SCHEME_ALIGNMENT_2026-06-05.md`
  - `mcp/canva-mcp/assets/preview.js`
  - `ops/references/mcp_services.json`
- Gap: No remaining structural gap for local Canva MCP OpenAPI interop: static contract, readiness gate, live strict-auth proxy smoke, docs probe, and unauthenticated rejection are tracked; future work can add scheduled smoke coverage or production hosting.

### Uninen/devserver-mcp

- URL: https://github.com/Uninen/devserver-mcp
- Category: `devserver-observability`
- Adoption status: `adopted`
- Why similar: MCP-driven development server manager with process monitoring, log visibility, and Playwright automation.
- Latest observed commit: `5f62b28d948d86a9ac1f803ecebf9926caa5cc77`
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
