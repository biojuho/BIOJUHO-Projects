# AutoResearch: MCP Long-Running Task Capability Guard

## Objective

Make the MCP service runtime smoke fail visibly if a service advertises a
long-running tool without also advertising task lifecycle capability.

## Source Signal

- Source: `microsoft/agent-framework`
- Commit: `bf4ad48cf24c8eb86c994cc62e3e2848a926887d`
- URL: `https://github.com/microsoft/agent-framework/commit/bf4ad48cf24c8eb86c994cc62e3e2848a926887d`
- Relevant signal: `Python: MCP long-running task support in Python`.
- Local interpretation: the upstream change routes tools with
  `execution.taskSupport == "required"` through task lifecycle handling and
  documents the submit-versus-track reconnect boundary. Locally, the matching
  safety seam is runtime smoke evidence that a long-running MCP tool is not
  silently accepted as an ordinary one unless the service advertises `tasks`.

## A/B Contract

- Baseline: `mcp_service_runtime_smoke.py` verified initialization,
  `tools/list`, minimum tool count, and named expected tools. It did not inspect
  tool `execution.taskSupport` metadata.
- Variant: detect tools with `execution.taskSupport == "required"`, record them
  in JSON/Markdown, and fail the service smoke unless the initialize capability
  map includes `tasks`.
- Primary KPI: a future long-running MCP tool cannot pass runtime smoke without
  task lifecycle capability evidence.
- Guardrails: do not change stdio service launch, normal `tools/list` behavior,
  credential boundaries, or current service pass/fail status.
- Decision: adopted.

## Implementation

- `ops/scripts/mcp_service_runtime_smoke.py`
  - Adds `long_running_tool_names()`.
  - Records `long_running_tool_count`, `long_running_tools`, and
    `task_capability_advertised` per checked service.
  - Fails validation when required long-running tools appear without a `tasks`
    initialize capability.
  - Adds report summary and Markdown lines for task-capable services and
    long-running tools.
- `tests/test_mcp_service_runtime_smoke.py`
  - Proves a required long-running tool fails without `tasks`.
  - Proves the same tool passes when initialize capabilities include `tasks`.
  - Locks current ordinary-tool reports to `long_running_tool_count == 0`.

## Verification

- `python -m pytest tests\test_mcp_service_runtime_smoke.py -q`
  - `9 passed`
- `python -m py_compile ops\scripts\mcp_service_runtime_smoke.py`
  - passed
- `python ops\scripts\mcp_service_runtime_smoke.py --json-out var\mcp-service-runtime-long-running-task-smoke.json --markdown-out var\mcp-service-runtime-long-running-task-smoke.md --timeout 20`
  - checked services: `3`
  - passed services: `3`
  - total tools listed: `39`
  - task-capable services: `0`
  - long-running tools listed: `0`

## Remaining Boundary

This cycle hardens MCP runtime evidence for future long-running tools. It does
not implement long-running MCP execution in local services and does not remove
operator-owned credential/runtime boundaries.

global_objective_complete=false
