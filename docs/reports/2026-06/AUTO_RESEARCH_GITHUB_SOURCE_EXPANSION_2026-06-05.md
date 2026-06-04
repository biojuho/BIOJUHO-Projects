# AutoResearch: GitHub Source Expansion

## Objective

Expand the GitHub modernization radar beyond the existing 13-source set so the
AutoResearch loop keeps discovering relevant agent, browser-automation,
typed-evals, and human-in-the-loop projects instead of only refreshing known
sources.

## Sources Checked

- `openai/openai-agents-python`: multi-agent workflows, tools, handoffs,
  guardrails, human-in-the-loop, sessions, tracing, and sandbox agents.
- `browser-use/browser-use`: agent-accessible browser automation, persistent
  browser CLI, custom browser tools, and production browser-session concerns.
- `pydantic/pydantic-ai`: type-safe agent workflows, provider abstraction,
  evals, composable capabilities, and OpenTelemetry-compatible observability.
- `humanlayer/humanlayer`: AI coding agents for complex codebases,
  human-in-the-loop control, parallel sessions, and control-plane concepts.

Primary GitHub references:

- https://github.com/openai/openai-agents-python
- https://github.com/browser-use/browser-use
- https://github.com/pydantic/pydantic-ai
- https://github.com/humanlayer/humanlayer

## A/B Contract

- Baseline: keep the modernization radar at `13` repositories and only refresh
  metadata for already-known sources.
- Variant: add the four live primary GitHub repositories above, map each to
  existing local evidence, rerun the radar validator, rerun live GitHub source
  freshness, and require the expanded source count in the completion contract.
- Primary KPI: radar source coverage increases from `13` to `17` while every
  local evidence path validates and live freshness returns `17/17` pass.
- Guardrails: keep the default smoke gate deterministic and offline; do not
  claim full runtime adoption for hosted agent/browser/control-plane features.
- Decision rule: adopt only if focused radar/source tests pass, live freshness
  passes for all sources, and completion audit stays valid.

## Result

Adopted.

- Radar validator: `17` sources, `adopted=1`, `partially_adopted=16`,
  `watch=0`
- Focused source/radar tests: `8 passed`
- Focused source/radar/audit tests after browser-QA freshness integration:
  `16 passed`
- Pre-push-equivalent pytest suite after browser-QA freshness integration:
  `84 passed`
- Live GitHub source freshness: `17` sources, `17` passed, `0` failed
- Newest upstream `pushed_at`: `2026-06-04T17:23:41Z`
- Script compile passed for:
  - `ops\scripts\github_modernization_radar.py`
  - `ops\scripts\github_source_freshness.py`
  - `ops\scripts\autoresearch_completion_audit.py`
- Hook-equivalent runtime probes passed:
  - dev-server MCP runtime smoke: `5` requests, `5` tools,
    `process_mutation_disabled`
  - MCP service runtime smoke: retry passed with `3` checked, `3` passed,
    `39` tools after one transient missing `tools/list` response
  - single workflow dry-run: selected `1`
  - side-effect safety execute: selected `1`, skipped `1`
  - all-workflow matrix dry-run: `6` workflows, selected `6`
  - completion audit: `18` criteria,
    `cycle_evidence_ready=true`, `global_objective_complete=false`

## Changed Evidence

- `ops\references\github_modernization_sources.json`
- `docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
- `docs\reports\2026-06\GITHUB_SOURCE_FRESHNESS_2026-06-05.json`
- `docs\reports\2026-06\GITHUB_SOURCE_FRESHNESS_2026-06-05.md`
- `tests\test_github_modernization_radar.py`
- `tests\test_github_source_freshness.py`

## Decision

The expanded radar is adopted as supplemental live research evidence. The
remaining gaps for hosted agent runtime, persistent browser-agent sessions,
typed agent runtime migration, and human-in-the-loop control-plane UI remain
future-scoped until a concrete runtime owner and credential policy are selected.
