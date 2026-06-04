# AutoResearch Dev-Server MCP Contract - 2026-06-04

## Source-Backed Candidate

- Source: `Uninen/devserver-mcp` (`https://github.com/Uninen/devserver-mcp`)
- Source pattern: MCP tools for `start_server`, `stop_server`, `get_devserver_statuses`, and `get_devserver_logs`, plus operator-facing dev-server and browser automation workflows.
- Local constraint: do not claim live MCP runtime exposure until a server lifecycle and authentication boundary are implemented.

## A/B Contract

- Baseline: local dev-server status/control exists as CLI scripts, but a future MCP runtime has no checked tool-name, argument, target enum, or output contract.
- Variant: generate a deterministic MCP tool contract from `ops/references/dev_server_targets.json` while keeping runtime status `contract_only`.
- Primary KPI: every manifest target is represented in the MCP input enum for status, start, stop, and logs.
- Guardrails: no shell separators in command templates, process-mutating tools are explicitly labeled, and existing dev-server control/status tests still pass.
- Decision: adopted. The contract gives agents a stable tool surface without adding a live process boundary prematurely.

## Adopted Changes

- Added `ops/scripts/dev_server_mcp_contract.py`.
- Added `tests/test_dev_server_mcp_contract.py`.
- Generated:
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.json`
  - `docs/reports/2026-06/DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.md`
- Updated `docs/guides/dev-server-control.md` with the contract generation path.
- Updated the GitHub modernization radar so the `Uninen/devserver-mcp` gap is live runtime/TUI exposure only.

## Verification

- `python -m pytest tests\test_dev_server_mcp_contract.py -q -p no:cacheprovider`
  - `3 passed`
- `python -m compileall -q ops\scripts\dev_server_mcp_contract.py`
  - passed
- `python -m pytest tests\test_dev_server_mcp_contract.py tests\test_dev_server_status.py tests\test_dev_server_control.py -q -p no:cacheprovider`
  - `24 passed`
- `python ops\scripts\dev_server_mcp_contract.py --json-out docs\reports\2026-06\DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.json --markdown-out docs\reports\2026-06\DEV_SERVER_MCP_TOOL_CONTRACT_2026-06-04.md`
  - valid
  - `4` tools
  - `7` targets
  - runtime status `contract_only`

## Remaining Gap

Live MCP runtime/TUI exposure remains future-scoped. The next step should only create a running MCP endpoint after the operator has a concrete need for process-control tool calls and an explicit authentication boundary.
