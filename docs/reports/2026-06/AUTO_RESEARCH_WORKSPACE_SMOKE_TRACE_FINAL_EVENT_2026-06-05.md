# AutoResearch Workspace Smoke Trace Final Event

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Source signal: `google/adk-python` commit `cd81f7b`, `fix(streaming): Ensure final partial=False frame is always yielded`.
- Source link: https://github.com/google/adk-python/commit/cd81f7bde91df78d6cece539a6f98dda2aa8c9c0

## A/B Contract

- Baseline: `--mcp-trace-out` emitted one `workspace_smoke.mcp_check` JSONL row
  per completed MCP check. Consumers could infer completion from file close, but
  the stream had no explicit terminal frame.
- Variant: append one `workspace_smoke.mcp_trace_complete` row to every MCP
  trace export. The terminal row records `partial=false`, completed/passed/
  failed counts, elapsed seconds, checked units, and command kinds.
- Primary KPI: JSONL trace consumers can stop on an explicit final event instead
  of waiting for more MCP check rows.
- Guardrails: existing per-check event names and fields remain unchanged; OTLP
  export shape remains unchanged; non-MCP runs emit a zero-count terminal row
  when `--mcp-trace-out` is requested.
- Decision rule: adopt only if workspace-smoke tests pass, the script compiles,
  and a real MCP-scope smoke writes the final `partial=false` event.

## Result

- Adopted variant: yes.
- Added `build_mcp_trace_complete_event()` to generate the terminal frame.
- `write_mcp_trace_export()` now drains per-check rows plus the terminal row, so
  a handler that consumes only the first event cannot drop the final event.
- `docs/QUALITY_GATE.md` documents both the check event and final event schemas.

## Changed Paths

- `ops/scripts/run_workspace_smoke.py`
- `tests/test_workspace_smoke.py`
- `docs/QUALITY_GATE.md`

## Verification

- `python -m pytest tests\test_workspace_smoke.py -q`
  - Passed: `33`.
- `python -m py_compile ops\scripts\run_workspace_smoke.py`
  - Passed.
- `python ops\scripts\run_workspace_smoke.py --scope mcp --json-out var\workspace-smoke-mcp-trace-final-event-2026-06-05.json --mcp-trace-out var\workspace-smoke-mcp-trace-final-event-2026-06-05.trace.jsonl`
  - Passed: `3`.
  - Failed: `0`.
  - JSONL rows: `4`.
  - Final event: `workspace_smoke.mcp_trace_complete`.
  - Final marker: `partial=false`.

## Next Cycle

- Continue reviewing live GitHub commit digest entries for small launch-risk
  reductions that add verifiable product or operator evidence.

## Audit Marker

- `global_objective_complete=false`
