# AutoResearch Agent Workflow State Snapshot Guard

## Objective

Adopt the `run-llama/llama_index` workflow state-isolation signal in the local
agent workflow gate runner so report snapshots cannot leak mutable manifest state
back into the loaded workflow payload.

## Source Signal

- Repository: `run-llama/llama_index`
- Source PR: `https://github.com/run-llama/llama_index/pull/21780`
- Source commit: `https://github.com/run-llama/llama_index/pull/21780/commits/a3fb9c3`
- Upstream signal: `fix(workflow): deep copy initial_state to prevent mutation leaks across runs`
- Local mapping: agent workflow reports should snapshot manifest-derived nested
  state before returning it to callers or writing artifacts.

## A/B Contract

- Baseline: `build_report()` copied `source_context`, `agent_roles`,
  `mcp_servers`, and gate result objects by reference. A caller that mutated a
  returned report could also mutate the in-memory manifest workflow or result
  object used to produce the report.
- Variant: deep-copy manifest-derived nested state and gate result payloads when
  constructing workflow and matrix reports.
- Primary KPI: a regression test mutates the returned report and proves the
  original manifest payload, workflow roles, MCP servers, and source gate result
  remain unchanged.
- Guardrails: CLI output shape, matrix reuse behavior, UTC timestamps, skipped
  side-effect gates, and dry-run behavior remain unchanged.
- Decision: adopted. The variant turns report objects into isolated snapshots
  without changing the manifest schema or workflow execution semantics.

## Changed Files

- `ops/scripts/agent_workflow_gate_runner.py`
  - Uses `copy.deepcopy()` for `source_context`, workflow role/server lists,
    gate results, and matrix workflow reports.
- `tests/test_agent_workflow_gate_runner.py`
  - Adds `test_report_snapshots_do_not_mutate_manifest_nested_state`.
- `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_STATE_SNAPSHOT_2026-06-05.json`
  - Durable matrix dry-run artifact for `6` workflows and `6` selected gates.
- `docs/reports/2026-06/AGENT_WORKFLOW_GATE_MATRIX_STATE_SNAPSHOT_2026-06-05.md`
  - Human-readable matrix dry-run evidence.

## Verification

- `python -m pytest tests\test_agent_workflow_gate_runner.py -q --tb=line`
  - `17 passed`
- `python -m py_compile ops\scripts\agent_workflow_gate_runner.py`
  - passed
- `python ops\scripts\agent_workflow_gate_runner.py --all-workflows --max-gates 1 --json-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_STATE_SNAPSHOT_2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_MATRIX_STATE_SNAPSHOT_2026-06-05.md`
  - `workflows=6`
  - `mode=dry_run`
  - `selected=6`
  - `reused=0`
- `current_tip_freshness_gate`
  - proof baseline: `1191bf6`
  - allowed post-proof paths include the agent workflow runner, its tests, and
    this report.
- `global_objective_complete=false`

## Remaining Boundary

This cycle prevents report-state mutation leaks in local workflow evidence only.
The open-ended AutoResearch loop and credential-gated launch blockers remain
active.
