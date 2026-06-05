# AutoResearch Workspace Smoke Trace Drain Guard

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Source signal: `pydantic/pydantic-ai` commit `49f62a386041`,
  `Fix incomplete streamed response when event_stream_handler doesn't consume the stream (#5771)`.
- Source link: https://github.com/pydantic/pydantic-ai/commit/49f62a386041abd6e0d960dd629c3b4fe28eac63

## A/B Contract

- Baseline: `write_mcp_trace_export()` wrote all generated MCP trace events,
  but there was no reusable contract for future event-stream observers. A
  future handler could inspect the stream and accidentally become responsible
  for consuming every event before trace evidence was finalized.
- Variant: add `drain_mcp_trace_events()` and route the JSONL writer through
  it. Optional handlers can consume none or only a prefix of the event stream;
  after a normal return, the exporter drains the remaining events and writes the
  full JSONL evidence.
- Primary KPI: all MCP trace events are preserved even when an observer returns
  without consuming the event stream.
- Guardrails: exceptions still interrupt the write path; CLI behavior remains
  unchanged when no handler is provided.
- Decision rule: adopt only if the workspace smoke trace tests and
  AutoResearch audits pass.

## Result

- Adopted variant: yes.
- `drain_mcp_trace_events()` now drains remaining MCP events after a handler
  returns normally.
- `write_mcp_trace_export()` accepts an optional `event_stream_handler` for
  tests/future observers while preserving current CLI behavior.
- `tests/test_workspace_smoke.py` covers handlers that ignore the stream and
  handlers that consume only the first event.

## Changed Paths

- `ops/scripts/run_workspace_smoke.py`
- `tests/test_workspace_smoke.py`
- `ops/references/autoresearch_completion_contract.json`
- `ops/references/autoresearch_objective_requirements.json`

## Verification

- `python -m pytest tests/test_workspace_smoke.py -q`
  - Passed: `31`.

## Post-Push Freshness

- Pushed proof commit: `07c0eb9`.
- `current_tip_freshness_gate`: `07c0eb9` is the active proof baseline for
  `origin/feat/observability-gateway-2026-05`.
- `protected_path_freshness`: no changed protected paths after proof.
- Audit marker: `global_objective_complete=false`.

## Next Cycle

- Continue reviewing top-8 source digest candidates, especially
  `pydantic/pydantic-ai` file-input consistency and `OpenHands/OpenHands`
  timestamp/runtime identity signals.
