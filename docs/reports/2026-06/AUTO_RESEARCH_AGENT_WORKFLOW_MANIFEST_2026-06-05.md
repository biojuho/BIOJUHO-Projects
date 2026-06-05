# AutoResearch Agent Workflow Manifest - 2026-06-05

## Source Signal

- Upstream: `evalstate/fast-agent`
- URL: https://github.com/evalstate/fast-agent
- Pattern adopted: declarative agent/workflow configuration should describe workflows, providers, MCP connections, and testable entrypoints as versioned artifacts.

## A/B Contract

- Baseline: shared harness modules had provider, token, audit, and workflow-trace pieces, but the workspace lacked one operator-readable manifest declaring app-level agent workflows.
- Variant: add a schema v1 `agent_workflows.json` manifest plus a validator/generator that emits machine and markdown summaries.
- Primary KPI: make app agent workflows discoverable and regression-checkable without reading each project independently.
- Guardrails: do not modify the dirty shared harness runtime files; validate only existing repo-relative entrypoints and evidence.
- Decision: accepted. The manifest covers five active workflows and validates against real workspace paths.

## Changes

- `ops/references/agent_workflows.json`
  - Declares five active workflows: getdaytrends content loop, DailyNews X ops, Canva MCP widget ops, DeSci grant readiness, and workspace quality operator.
  - Maps each workflow to entrypoints, providers, MCP servers, tools, smoke scope, and evidence.
- `ops/scripts/agent_workflow_manifest.py`
  - Validates schema, ids, timestamps, statuses, smoke scopes, providers, repo-relative entrypoints, and evidence paths.
  - Writes JSON and markdown summaries.
- `tests/test_agent_workflow_manifest.py`
  - Covers current manifest validity, CLI output, unsafe paths, duplicate ids, and unsupported providers.
- `docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-05.md`
  - Generated operator-readable workflow summary.
- `ops/references/github_modernization_sources.json` and generated modernization radar markdown
  - Marks the `evalstate/fast-agent` structural manifest gap as adopted.

## Verification

- `python ops\scripts\agent_workflow_manifest.py --json-out var\agent-workflow-manifest-2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_MANIFEST_2026-06-05.md`
  - Passed: `5 workflows`.
- `python -m py_compile ops\scripts\agent_workflow_manifest.py`
  - Passed.
- `python -m pytest tests\test_agent_workflow_manifest.py -q`
  - Passed `4/4`.
- `python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-agent-workflow-2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md`
  - Passed.
  - Summary: `6 sources, adopted=3, partially_adopted=2, watch=1`.

## Notes

- This is a declarative control-plane improvement. Runtime orchestration can consume this manifest in a later scoped cycle.
