# AutoResearch Remaining Gap Audit - 2026-06-04

## Scope

This audit records the state after the 2026-06-04 AutoResearch adoption cycle on branch `feat/observability-gateway-2026-05`.

Latest pushed commits in this slice:

- 2026-06-05 GitHub agent-platform expansion slice: expanded the
  modernization radar from `17` to `22` live GitHub repositories by adding
  Microsoft Agent Framework, Agno, Vercel AI SDK, AutoGPT, and Flowise as
  source-backed comparison projects.
- 2026-06-05 source snapshot recency gate slice: added generic
  `json_freshness` validation to the completion audit so old GitHub
  external-source snapshots stop satisfying launch readiness after the
  configured freshness window.
- 2026-06-05 GitHub source expansion slice: expanded the modernization radar
  from `13` to `17` live GitHub repositories by adding OpenAI Agents SDK,
  Browser Use, Pydantic AI, and HumanLayer as source-backed comparison
  projects.
- 2026-06-05 agent workflow gate-matrix reuse slice: optimized the
  all-workflows matrix by reusing duplicate deterministic gate results while
  preserving per-workflow evidence.
- 2026-06-05 agent workflow gate-matrix slice: adopted safe
  `--all-workflows --execute --max-gates 1` matrix evidence across all six
  declared active workflows.
- 2026-06-05 agent workflow gate-safety slice: adopted targeted gate
  selection and default skips for side-effecting gates unless the operator
  supplies `--allow-side-effect-gates`.
- 2026-06-05 agent workflow gate-runner slice: adopted bounded execution
  of declared workflow quality gates through existing project CLIs while
  leaving stateful autonomous orchestration future-scoped.
- 2026-06-05 MCP service runtime-smoke slice: adopted an official MCP
  Python SDK-backed stdio initialize/tools-list smoke for repo-local MCP
  services.
- 2026-06-05 collector-handoff slice: adopted an OpenTelemetry Collector
  handoff manifest and validator for real MCP smoke OTLP JSONL artifacts.
- 2026-06-05 policy-tool slice: adopted `get_devserver_policy` and
  `microsoft/mcp-gateway` radar evidence.
- `0746be7 chore(canva): clear npm audit findings`
- `554e935 feat(canva): harden widget preview browser smoke`
- `5542450 docs(ops): add agriguard browser smoke proof`
- `dcac1d6 docs(ops): add dashboard browser smoke proof`
- `fb5e41f feat(ops): add dev server browser smoke`
- `e161361 docs(ops): add playwright mcp radar source`
- `bed8e0c feat(ops): add workspace smoke check timeout`
- `1f049c6 chore(ops): run completion audit pre-push`
- `93bd931 docs(ops): audit browser json evidence`
- `0019feb feat(desci): write browser smoke json evidence`
- `22ebc1a feat(ops): add mcp runtime subprocess smoke`
- `2bc90cd fix(desci): initialize auth fallback loading`
- `08442fe fix(desci): harden local auth and cors`
- `961b50c docs(ops): add pre-push gate to completion audit`
- `329406c chore(ops): include mcp runtime in pre-push smoke`
- `434c172 feat(ops): add dev server mcp runtime`
- `494f172 feat(ops): add autoresearch completion audit`
- `26b2a44 feat(skill): require autoresearch completion audits`
- `dccaad4 docs(ops): record agriguard click proof`
- `dc6590f docs(ops): record dashboard click proof`
- `02bfcea feat(ops): add dev server mcp contract`
- `3983c4f feat(ops): export mcp smoke otlp spans`
- `84ce8fc feat(ops): add agent workflow dry run plans`
- `c4442da feat(ops): add mcp service manifest`
- `cd199f1 feat(ops): add dev server status table`
- `4e6f182 feat(ops): export mcp smoke traces`
- `01d8fe6 feat(mcp): guard canva openapi calls`
- `8278c09 feat(mcp): expose canva openapi metadata`

## Adopted Source-Backed Variants

- `PrefectHQ/fastmcp`: adopted a validated MCP service manifest for composition planning plus stdio runtime initialize/tools-list evidence.
- `modelcontextprotocol/python-sdk`: adopted official MCP Python SDK runtime
  readiness patterns for stdio FastMCP services.
- `lastmile-ai/mcp-eval`: adopted MCP smoke schema metrics, dashboard surfacing, standalone JSONL trace export, local OTLP file-exporter shaped span export, and validated collector handoff evidence.
- `open-telemetry/opentelemetry-collector`: adopted an operator-owned
  collector handoff contract and validator for real MCP smoke OTLP artifacts.
- `evalstate/fast-agent`: adopted launch workflow inventory, dry-run command
  plans, bounded quality-gate execution, targeted gate selection, and
  side-effect approval skips, and safe matrix execution across active
  workflows with duplicate deterministic gate reuse.
- `langchain-ai/langgraph`: adopted the conservative local equivalent of
  stateful workflow orchestration by executing declared gates through existing
  project CLIs and adding an explicit human-checkpoint-style side-effect
  override before any full runtime, memory, human approval UI, or hosted
  deployment adoption.
- `crewAIInc/crewAI`: adopted the local launch-control equivalent of
  production flow orchestration by verifying every active workflow through a
  deterministic matrix and reusing duplicate deterministic gates while keeping
  autonomous crews/control-plane deployment future-scoped.
- `dsifry/metaswarm`: deterministic quality gates and durable next-action capture are structurally adopted.
- `modelcontextprotocol/inspector`: adopted a repo-owned stdio subprocess smoke for `initialize`, `tools/list`, guarded `tools/call`, and read-only log calls.
- `open-webui/mcpo`: adopted Canva MCP offline OpenAPI contract, live read-only metadata endpoints, and explicit disabled execution responses.
- `microsoft/playwright-mcp`: adopted deterministic browser smoke and app-click evidence across DeSci, dashboard, AgriGuard, and Canva widget preview surfaces.
- `microsoft/mcp-gateway`: adopted machine-readable local-only dev-server MCP
  policy introspection for runtime status, stdio transport, no network
  exposure, unsupported non-local control, and process-mutation defaults.
- `Uninen/devserver-mcp`: adopted manifest-backed start/stop/status/tail, dashboard readiness, terminal table status, timeout-tree cleanup, checked MCP tool definitions, and a local stdio MCP runtime with process mutation opt-in.
- `openai/openai-agents-python`: partially adopted through AutoResearch
  workflow gates, side-effect guardrails, completion audits, source freshness,
  and deterministic launch matrices; hosted Agents SDK runtime, tracing,
  sessions, and sandbox-agent execution remain future-scoped.
- `browser-use/browser-use`: partially adopted through deterministic browser
  smoke and app-click evidence across launch-critical surfaces; persistent
  browser-agent CLI, authenticated browser-profile reuse, and cloud browser
  execution remain future-scoped.
- `pydantic/pydantic-ai`: partially adopted through structured harness,
  token tracking, deterministic smokes, OTLP-shaped evidence, and completion
  audits; full typed agent runtime and Logfire/provider migration remain
  future-scoped.
- `humanlayer/humanlayer`: partially adopted through human-checkpoint-style
  side-effect skips, worktree-safe commit/push loops, durable next-action
  capture, and matrix quality gates; hosted control plane and multi-session UI
  remain future-scoped.
- `microsoft/agent-framework`: partially adopted through declared workflow
  gates, MCP runtime smoke, and observability handoff evidence; live Microsoft
  Agent Framework runtime, A2A deployment, and SDK-level orchestration remain
  future-scoped.
- `agno-agi/agno`: partially adopted through the deterministic AutoResearch
  loop, workflow gates, completion audits, and durable next-action capture;
  persistent memory stores, hosted agent platform, team UI, and long-running
  runtime deployment remain future-scoped.
- `vercel/ai`: partially adopted through browser-smoked dashboard and
  TypeScript MCP tool surfaces plus provider/tool policy evidence; Vercel AI
  SDK runtime migration, streaming chat UX, AI Gateway deployment, and hosted
  frontend AI runtime remain future-scoped.
- `Significant-Gravitas/AutoGPT`: partially adopted through continuous,
  evidence-backed, commit/push-oriented AutoResearch cycles; hosted platform
  deployment, marketplace packaging, and unattended autonomous execution remain
  future-scoped.
- `FlowiseAI/Flowise`: partially adopted through dashboard quality panels,
  workflow manifests, dev-server control, and browser-smoked operator surfaces;
  a visual agent builder, template marketplace, and runtime graph editor remain
  future-scoped.
- Canva widget-preview browser smoke: adopted deterministic inline SVG preview
  thumbnails and shared manifest evidence so `canva-widget-preview` is covered
  by direct browser proof.
- Canva MCP npm audit cleanup: adopted patched `wrangler`, `miniflare`, `ws`,
  and `qs` lock state so the local browser-smoke install path reports `0`
  vulnerabilities.

## Remaining Gaps

These are intentionally not promoted to live runtime changes in this cycle:

- FastMCP shared composition adapters and transport switching:
  - Status: future-scoped
  - Reason: the service inventory and stdio runtime initialize/tools-list
    smoke now exist for eligible local services; a shared adapter or
    Streamable HTTP/SSE transport switch should wait for a concrete MCP
    expansion target.
- Live OpenTelemetry SDK or collector shipping:
  - Status: future-scoped
  - Reason: local OTLP file-exporter shaped span output and an executable
    collector handoff validator now exist; live SDK or collector shipping
    should still wait for operator-owned endpoint, credential, retention,
    sampling, and retry policy.
- Live central agent workflow orchestration:
  - Status: future-scoped
  - Reason: declarative workflow inventory, dry-run plans, bounded execution
    of selected quality gates, targeted gate selection, and default skips for
    side-effecting gates, and a safe launch matrix over all active workflows
    now exist; duplicate deterministic gate reuse reduces repeated launch-gate
    cost without hiding evidence. Full stateful orchestration, durable agent
    memory, human approval UI, and hosted deployment should stay behind
    existing project CLIs and smoke/dev-server gates until execution ownership
    is clear.
- Canva OpenAPI tool execution proxy:
  - Status: external-auth blocked
  - Reason: metadata and disabled-call boundary are live; actual execution should wait for verified Canva OAuth credentials plus proxy authentication behavior.
- Dev-server TUI exposure and network-facing non-local authentication:
  - Status: future-scoped
  - Reason: a local stdio MCP runtime now exposes a read-only
    `get_devserver_policy` tool for current local-only policy; full TUI
    exposure or a network-facing gateway/authentication layer should wait for
    an operator-owned boundary.

## Verification

- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-agent-platform-expansion-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - valid
  - `22` sources
  - `adopted=1`
  - `partially_adopted=21`
  - `watch=0`
- GitHub agent-platform source expansion verification:
  - added `microsoft/agent-framework`, `agno-agi/agno`, `vercel/ai`,
    `Significant-Gravitas/AutoGPT`, and `FlowiseAI/Flowise`
  - focused radar/source tests passed `8/8`
  - focused source/radar/audit tests passed `18/18`
  - live GitHub source freshness passed `22/22` sources with `0` failures
  - newest upstream `pushed_at` in the refreshed snapshot was
    `2026-06-04T17:42:15Z`
  - completion audit reports `19` criteria with
    `cycle_evidence_ready=true` and `global_objective_complete=false`
  - generated evidence:
    `docs\reports\2026-06\AUTO_RESEARCH_GITHUB_AGENT_PLATFORM_EXPANSION_2026-06-05.md`,
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_AGENT_PLATFORM_EXPANSION_2026-06-05.json`,
    and
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_AGENT_PLATFORM_EXPANSION_2026-06-05.md`
- GitHub source freshness verification:
  - `ops\scripts\github_source_freshness.py` checks the live GitHub REST API
    metadata for every repo in `ops\references\github_modernization_sources.json`
  - live snapshot passed `22/22` sources with `0` failures
  - newest upstream `pushed_at` in the snapshot was `2026-06-04T17:42:15Z`
  - snapshot generated at `2026-06-04T17:44:09.050004+00:00`
  - focused source-freshness tests passed `4/4`
  - pre-push-equivalent suite passed `86/86`
  - installed pre-push dry-run ran `86/86` plus runtime probes and completion
    audit
  - completion audit now reports `19` criteria with
    `cycle_evidence_ready=true` and `global_objective_complete=false`
  - generated evidence:
    `docs\reports\2026-06\AUTO_RESEARCH_GITHUB_SOURCE_FRESHNESS_2026-06-05.md`,
    `docs\reports\2026-06\GITHUB_SOURCE_FRESHNESS_2026-06-05.json`
    `docs\reports\2026-06\GITHUB_SOURCE_FRESHNESS_2026-06-05.md`,
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_GITHUB_SOURCE_FRESHNESS_2026-06-05.json`,
    and
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_GITHUB_SOURCE_FRESHNESS_2026-06-05.md`
- Source snapshot recency gate verification:
  - `ops\scripts\autoresearch_completion_audit.py` now validates optional
    `json_freshness` evidence by parsing JSON evidence, checking
    `status=pass`, validating the configured timestamp field, rejecting future
    timestamps, and rejecting snapshots older than the configured window
  - `github_source_snapshot_recency_gate` requires
    `docs\reports\2026-06\GITHUB_SOURCE_FRESHNESS_2026-06-05.json`
    to keep `status=pass` and `generated_at` within `72` hours
  - focused audit tests passed `11/11`
  - focused source/radar/audit suite passed `19/19`
  - pre-push-equivalent suite passed `87/87`
  - runtime probes passed for dev-server MCP runtime, MCP service runtime,
    single-workflow dry-run, side-effect safety skip, and matrix dry-run
  - completion audit now reports `19` criteria with
    `cycle_evidence_ready=true` and `global_objective_complete=false`
  - generated evidence:
    `docs\reports\2026-06\AUTO_RESEARCH_SOURCE_SNAPSHOT_FRESHNESS_GATE_2026-06-05.md`,
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SOURCE_SNAPSHOT_FRESHNESS_2026-06-05.json`,
    and
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SOURCE_SNAPSHOT_FRESHNESS_2026-06-05.md`
- Browser QA freshness gate verification:
  - `ops\scripts\autoresearch_completion_audit.py` now validates
    `protected_path_freshness` evidence for launch-critical browser/app paths
  - proof baseline `f53eb69` is an ancestor of
    `origin/feat/observability-gateway-2026-05`
  - protected path diff from `f53eb69` to the active remote is empty for
    dashboard, DeSci, AgriGuard, Canva widget preview, dev-server browser
    manifests/scripts, and browser-smoke tests
  - focused audit tests passed `8/8`
  - pre-push-equivalent suite passed `80/80`
  - completion audit now reports `18` criteria with
    `cycle_evidence_ready=true` and `global_objective_complete=false`
  - generated evidence:
    `docs\reports\2026-06\AUTO_RESEARCH_BROWSER_QA_FRESHNESS_GATE_2026-06-05.md`,
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_BROWSER_QA_FRESHNESS_2026-06-05.json`,
    and
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_BROWSER_QA_FRESHNESS_2026-06-05.md`
- Current-tip matrix-reuse all-scope launch gate:
  - current branch tip `77cc93d`
  - `python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-matrix-reuse-tip-2026-06-05.json --mcp-trace-out var\workspace-smoke-all-matrix-reuse-tip-2026-06-05.trace.jsonl --mcp-otel-out var\workspace-smoke-all-matrix-reuse-tip-2026-06-05.otlp.jsonl`
  - `25/25 PASS` in `598.448s`
  - scope summary: workspace `6/6`, desci `7/7`, agriguard `5/5`, MCP
    `3/3`, getdaytrends `2/2`, CIE `2/2`
  - MCP trace emitted `3` events and OTLP emitted `1` `resourceSpans` line
    with `3` spans
  - durable evidence:
    `docs\reports\2026-06\AUTO_RESEARCH_MATRIX_REUSE_TIP_ALL_SCOPE_SMOKE_2026-06-05.md`,
    `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_MATRIX_REUSE_TIP_2026-06-05.json`,
    `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_MATRIX_REUSE_TIP_2026-06-05.trace.jsonl`,
    and
    `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_MATRIX_REUSE_TIP_2026-06-05.otlp.jsonl`
- Agent workflow gate-matrix verification:
  - real matrix command selected first deterministic gates for all `6`
    workflows and returned `passed_workflows=6`, `selected_gates=6`,
    `passed_gates=6`, `failed_gates=0`, `skipped_gates=0`
  - elapsed seconds `1161.195`
  - focused workflow/radar/audit suite passed `30/30`
  - pre-push-equivalent test suite passed `72/72`
  - hook script checks passed: dev-server MCP runtime smoke, MCP service
    runtime smoke, single-workflow dry-run, side-effect safety check, matrix
    dry-run, and completion audit
  - covered workflow IDs: `dailynews-x-ops`, `getdaytrends-operator-run`,
    `desci-launch-readiness`, `agriguard-qr-product-verification`,
    `canva-widget-oauth-preview`, and `workspace-quality-dashboard`
  - generated evidence:
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.json`
    and
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_SAFE_FIRST_GATES_2026-06-05.md`
- Current-tip freshness gate verification:
  - `ops\scripts\autoresearch_completion_audit.py` now validates optional
    `git_freshness` evidence by checking proof-commit ancestry and changed
    paths after the proof commit
  - configured proof commit `39d6a82` is an ancestor of
    `origin/feat/observability-gateway-2026-05`
  - allowed post-proof paths are limited to reports, `next-actions.md`, the
    completion contract, the completion-audit script, and its tests
  - focused audit tests passed `6/6`
  - pre-push-equivalent test suite passed `74/74`, and the hook runtime
    probes passed for dev-server MCP runtime, MCP service runtime, single
    workflow dry-run, side-effect safety skip, and matrix dry-run
  - completion audit now reports `15` criteria with
    `cycle_evidence_ready=true` and `global_objective_complete=false`
  - generated evidence:
    `docs\reports\2026-06\AUTO_RESEARCH_CURRENT_TIP_FRESHNESS_GATE_2026-06-05.md`,
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_TIP_FRESHNESS_2026-06-05.json`,
    and
    `docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_TIP_FRESHNESS_2026-06-05.md`
- Current-tip workflow matrix all-scope launch gate:
  - current branch tip `39d6a82`
  - fast gate passed: hook-equivalent pytest suite `72/72`, dev-server MCP
    runtime smoke, MCP service runtime smoke, single workflow dry-run,
    side-effect safety skip, matrix dry-run, and completion audit with `14`
    criteria
  - `python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-workflow-matrix-tip-2026-06-05.json --mcp-trace-out var\workspace-smoke-all-workflow-matrix-tip-2026-06-05.trace.jsonl --mcp-otel-out var\workspace-smoke-all-workflow-matrix-tip-2026-06-05.otlp.jsonl`
  - `25/25 PASS` in `601.252s`
  - scope summary: workspace `6/6`, desci `7/7`, agriguard `5/5`, MCP
    `3/3`, getdaytrends `2/2`, CIE `2/2`
  - MCP trace emitted `3` events and OTLP emitted `1` `resourceSpans` line
    with `3` spans
  - durable evidence:
    `docs\reports\2026-06\AUTO_RESEARCH_WORKFLOW_MATRIX_TIP_ALL_SCOPE_SMOKE_2026-06-05.md`,
    `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_WORKFLOW_MATRIX_TIP_2026-06-05.json`,
    `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_WORKFLOW_MATRIX_TIP_2026-06-05.trace.jsonl`,
    and
    `docs\reports\2026-06\WORKSPACE_SMOKE_ALL_WORKFLOW_MATRIX_TIP_2026-06-05.otlp.jsonl`
- Agent workflow gate-matrix reuse verification:
  - optimized matrix command selected all `6` workflows, passed `5` unique
    deterministic gates, reused `1` duplicate MCP gate, and failed `0`
  - elapsed seconds improved from `1161.195` to `834.845`, a `326.350s`
    reduction, about `28.1%`
  - merged focused workflow/radar/audit suite passed `32/32`
  - merged pre-push-equivalent test suite passed `74/74`
  - merged completion audit reports `16` criteria with
    `cycle_evidence_ready=true` and `global_objective_complete=false`
  - reused gate: `canva-widget-oauth-preview` reused the earlier
    `dailynews-x-ops` MCP smoke result
  - generated evidence:
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.json`
    and
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_REUSE_SAFE_FIRST_GATES_2026-06-05.md`
- Agent workflow gate-runner verification:
  - `tests\test_agent_workflow_gate_runner.py` passed `11/11`
  - focused workflow/radar/audit suite passed `26/26`
  - pre-push-equivalent test suite passed `68/68`
  - hook script checks passed: dev-server MCP runtime smoke, MCP service
    runtime smoke, agent workflow gate-runner dry-run, agent workflow
    side-effect safety check, and completion audit
  - `ops\scripts\agent_workflow_gate_runner.py` compiled
  - real `workspace-quality-dashboard` gate execution selected `1` gate,
    passed `1`, failed `0`, and nested workspace smoke returned `6/6 PASS`
  - real targeted `desci-launch-readiness` gate `2` safety proof selected `1`
    gate, passed `0`, failed `0`, and skipped `1` side-effecting gate
  - generated evidence:
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.json`
    and
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_RUN_WORKSPACE_QUALITY_DASHBOARD_2026-06-05.md`
  - generated safety evidence:
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.json`
    and
    `docs\reports\2026-06\AGENT_WORKFLOW_GATE_SAFETY_DESCI_GATE2_2026-06-05.md`
- Pre-push hooks on the latest pushed slices passed:
  - `47 passed` plus MCP subprocess smoke and completion audit after `0746be7`
  - `47 passed` plus MCP subprocess smoke and completion audit after `554e935`
  - `36 passed` after `2bc90cd`
  - `36 passed` after `961b50c`
  - `27 passed` after `dccaad4`
  - `27 passed` after `dc6590f`
  - `27 passed` after `02bfcea`
  - `27 passed` after `3983c4f`
  - `25 passed` after `84ce8fc`
  - `25 passed` after `c4442da`
  - `25 passed` after `cd199f1`
- OTLP span export verification:
  - expanded focused tests `56 passed`
  - final MCP smoke `3/3 PASS`
  - final OTLP file `var\workspace-smoke-mcp-otel-file-export-final-2026-06-04.otlp.jsonl`
    contained `1` `resourceSpans` line with `3` spans
- OTLP collector handoff verification:
  - `tests\test_mcp_otel_collector_handoff.py` passed `4/4`
  - real MCP smoke wrote
    `var\workspace-smoke-mcp-otel-handoff-2026-06-05.otlp.jsonl`
    after `3/3 PASS`
  - `ops\scripts\mcp_otel_collector_handoff.py` validated that file with
    `status=pass`, `line_count=1`, `resource_span_count=1`, and
    `span_count=3`
  - generated evidence:
    `docs\reports\2026-06\MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.json`
    and
    `docs\reports\2026-06\MCP_OTEL_COLLECTOR_HANDOFF_2026-06-05.md`
- MCP service runtime smoke verification:
  - `tests\test_mcp_service_runtime_smoke.py` passed `5/5`
  - `ops\scripts\mcp_service_runtime_smoke.py` passed against the real
    repo-local stdio MCP services
  - runtime smoke checked `3` services, passed `3`, skipped `1` non-stdio
    service, and listed `39` tools
  - generated evidence:
    `docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.json`
    and
    `docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_2026-06-05.md`
- Dev-server MCP contract verification:
  - `tests\test_dev_server_mcp_contract.py` `3 passed`
  - dev-server contract/status/control tests `24 passed`
  - contract generation emits `4` tools across `7` targets with runtime status `local_stdio_runtime`
- Dev-server MCP runtime verification:
  - focused dev-server/radar/completion suite `38 passed`
  - PowerShell piped JSON-RPC `tools/list` smoke returned the four checked tools
  - contract generation emitted `4` tools across `7` targets with runtime status `local_stdio_runtime`
  - `start_server` and `stop_server` remain disabled by default unless `DEV_SERVER_MCP_ALLOW_PROCESS_MUTATION=true`
- Dev-server MCP subprocess smoke verification:
  - `ops\scripts\dev_server_mcp_runtime_smoke.py` returned `4` requests, `4` tools, and `mutation_guard=process_mutation_disabled`
  - focused MCP/radar/audit suite `19 passed`
  - installed pre-push dry-run ran `38 passed` plus subprocess smoke
- Dev-server MCP policy verification:
  - `get_devserver_policy` is listed by `tools/list`
  - subprocess smoke now returns `5` requests, `5` tools, and
    `mutation_guard=process_mutation_disabled`
  - policy payload reports `runtime_status=local_stdio_runtime`,
    `network_exposure=none`, `non_local_control.status=unsupported`, and
    `process_mutation.default=disabled`
  - focused contract/runtime/smoke tests passed `12/12`
- Dashboard live browser-click verification:
  - `apps\dashboard` build passed
  - dashboard Vitest `8 passed`
  - manifest-backed dashboard stack reached `2/2 READY`
  - Chromium clicked the refresh button and verified `WORKSPACE SMOKE`, `DEV SERVERS`, and `2/2 READY` with zero console/page/request failures
  - managed dashboard stack stopped and final status returned `0/2 READY`
- AgriGuard live browser-click verification:
  - `agriguard-api` and `agriguard-frontend` status returned `2/2 READY`
  - Chromium clicked through home, `Registry`, `Supply Chain`, and `Scanner`
  - route checks verified `/registry`, `/supply-chain`, and `/scan` with zero console/page/request failures
  - AgriGuard frontend build passed and full Vitest completed with `29 passed`
- DeSci live browser remediation:
  - Firebase config fallback restored public route rendering without real Firebase credentials
  - backend CORS now admits the manifest DeSci frontend origin `http://127.0.0.1:5175`
  - browser smoke returned `7/7 OK`
  - live click proof covered home, explore search, and pricing with zero console/page/request failures
  - auth fallback loading now avoids the React hook set-state-in-effect lint warning
  - focused/full frontend tests, lint, backend API tests, build/typecheck, and DeSci canonical smoke passed
- Canva widget browser proof:
  - generic browser smoke returned `1/1 PASS` for `canva-widget-preview`
  - preview/mock widget data now uses deterministic inline SVG thumbnails instead of remote marketplace image requests
  - completion audit includes `DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.json` as direct app-click/browser evidence
- Canva npm audit cleanup:
  - `wrangler` resolves to `4.98.0`
  - lockfile resolves `miniflare@4.20260603.0`, `ws@8.20.1`, and `qs@6.15.2`
  - `CANVA_NPM_AUDIT_2026-06-04.json` records `0` vulnerabilities
- Current-tip all-scope launch gate:
  - `python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.json --mcp-trace-out var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.trace.jsonl --mcp-otel-out var\workspace-smoke-all-current-tip-post-dev-browser-smoke-2026-06-04.otlp.jsonl`
  - `25/25 PASS` in `660.688s`
  - MCP trace emitted `3` events and OTLP emitted `1` `resourceSpans` line with `3` spans
- Canva companion proof after the all-scope run:
  - `dev_server_browser_smoke.py --target canva-widget-preview` passed `1/1`
    with `0` failures
  - durable JSON:
    `docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_CANVA_2026-06-04.json`
  - `npm audit --json` reported `0` vulnerabilities and Canva `npm run build`
    passed
  - durable audit JSON:
    `docs\reports\2026-06\CANVA_NPM_AUDIT_2026-06-04.json`
  - these are focused companion proofs because `mcp\canva-mcp` is outside
    `run_workspace_smoke.py --scope all`

## Decision

The remaining items are not current implementation blockers. Treat them as explicit future work unless the user supplies external credentials, asks for a live runtime orchestrator, or scopes a concrete MCP adapter/collector/dev-server TUI or non-local authentication build.
