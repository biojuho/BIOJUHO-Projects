# AutoResearch: GitHub Agent Runtime Source Expansion

## Objective

Expand the GitHub modernization radar beyond the existing `22` sources so the
launch-hardening loop continues to compare against major current agent runtime,
coding-agent, MCP-agent, document-agent, TypeScript-agent, and production LLM
orchestration projects.

## Sources Checked

Primary GitHub references:

- https://github.com/OpenHands/OpenHands
- https://github.com/microsoft/autogen
- https://github.com/google/adk-python
- https://github.com/run-llama/llama_index
- https://github.com/strands-agents/harness-sdk
- https://github.com/deepset-ai/haystack
- https://github.com/mastra-ai/mastra
- https://github.com/lastmile-ai/mcp-agent

## A/B Contract

- Baseline: keep the radar at `22` repositories and rely on already-mapped MCP,
  browser automation, workflow matrix, source freshness, and credential-boundary
  sources.
- Variant: add the eight repositories above, map each to existing local
  evidence, regenerate the radar report, refresh live GitHub metadata, and
  require the expanded count in the completion contract.
- Primary KPI: source coverage increases from `22` to `30` while every local
  evidence path validates and live source freshness returns `30/30` pass.
- Guardrails: do not claim hosted autonomous coding agents, ADK deployment,
  AutoGen runtime migration, LlamaIndex ingestion/OCR runtime, Strands cloud
  deployment, Haystack pipeline runtime, Mastra runtime migration, or MCP Agent
  long-running server operation as locally adopted.
- Decision rule: adopt only if focused radar/source tests pass, live GitHub
  freshness passes for all `30` sources, completion audit remains valid, and
  the pre-push-equivalent suite has no regression.

## Result

Adopted as supplemental source-backed research evidence.

- Radar validator: `30` sources, `adopted=1`, `partially_adopted=29`,
  `watch=0`
- Focused radar/source tests: `9 passed`
- Focused source/radar/audit tests: `20 passed`
- Focused credential/completion guardrail tests: `21 passed`
- Pre-push-equivalent pytest suite: `99 passed`
- Live GitHub source freshness: `30` sources, `30` passed, `0` failed
- Newest upstream `pushed_at`: `2026-06-04T18:53:13Z` from
  `mastra-ai/mastra`
- New source snapshot generated at: `2026-06-04T18:54:22.968302+00:00`
- Runtime probes:
  - external credential handoff check: `5` boundaries,
    `status=operator_action_required`, `missing_required_env=5`
  - dev-server MCP runtime smoke: `5` requests, `5` tools,
    `mutation_guard=process_mutation_disabled`
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - workspace-quality-dashboard dry-run: selected `1`
  - desci-launch-readiness side-effect safety check: selected `1`, skipped `1`
  - all-workflows matrix dry-run: workflows `6`, selected `6`
- Hook installer guardrail:
  - pre-push hook install now normalizes shell hook line endings to LF before
    writing into Git's common hooks directory
  - `tests/test_pre_push_hook.py`: `2 passed`
  - `python -m py_compile ops\hooks\install_hooks.py`: passed
- Completion audit: `23` criteria, `cycle_evidence_ready=true`,
  `global_objective_complete=false`

## Decision Boundary

The expanded radar improves external coverage for the user's ongoing
AutoResearch loop. Runtime adoption remains deliberate: hosted agent GUIs,
agent deployment engines, cloud runtimes, persistent browser profiles,
retrieval/memory backends, and long-running autonomous agent servers stay
future-scoped until a concrete product workflow and operator-owned credential
policy exist.
