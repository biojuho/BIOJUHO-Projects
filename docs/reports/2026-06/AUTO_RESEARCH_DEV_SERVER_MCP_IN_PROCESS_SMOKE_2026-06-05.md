# Dev-Server MCP In-Process Smoke Guard

Generated at: `2026-06-05T11:34:00+09:00`

## Source Signal

- Repository: `modelcontextprotocol/python-sdk`
- Commit: `19fe9fa`
- Subject: `Run StreamableHTTP transport tests in process instead of over sockets (#2767)`
- Source URL: https://github.com/modelcontextprotocol/python-sdk/commit/19fe9fa
- Local interpretation: transport smoke tests should have a deterministic in-process path when the goal is protocol validation rather than process-launch coverage.

## A/B Contract

- Variant A: Validate the dev-server MCP runtime only through the subprocess smoke path.
- Variant B: Keep subprocess as the default product smoke, and add an explicit `in-process` execution mode that drives `dev_server_mcp_runtime.serve()` through in-memory stdio.
- Adopted: Variant B.
- Decision rule: adopt only if the in-process mode returns the same six-response protocol flow, tool inventory, mutation guard, unknown-tool error, and post-error logs response without regressing the subprocess smoke path.

## Local Changes

- `ops/scripts/dev_server_mcp_runtime_smoke.py`
  - Adds `--execution-mode subprocess|in-process`, defaulting to `subprocess`.
  - Factors runtime execution into subprocess and in-process adapters.
  - Records `execution_mode` in JSON and Markdown reports.
- `tests/test_dev_server_mcp_runtime_smoke.py`
  - Proves the default subprocess report records `execution_mode=subprocess`.
  - Proves `execution_mode=in-process` returns six responses, five tools, the mutation guard, the unknown-tool error, and post-error logs continuity.

## Verification

- `python -m pytest tests\test_dev_server_mcp_runtime_smoke.py -q`
  - `3 passed`
- `python -m py_compile ops\scripts\dev_server_mcp_runtime_smoke.py`
  - passed
- `python ops\scripts\dev_server_mcp_runtime_smoke.py --execution-mode in-process --json-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_IN_PROCESS_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_MCP_RUNTIME_SMOKE_IN_PROCESS_2026-06-05.md`
  - valid: `6` requests, `5` tools, `mutation_guard=process_mutation_disabled`
  - `execution_mode=in-process`
- `global_objective_complete=false`
