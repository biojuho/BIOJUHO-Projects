# AutoResearch MCP Service Runtime Launch Failure Guard

Date: 2026-06-05

## Source Signal

- Repository: `agno-agi/agno`
- Commit signal: `7595e14` `fix: prevent MCP connection failures from crashing agents (#8112)`
- Adjacent signal: `5749e44` `fix: replace blocking time.sleep with await asyncio.sleep in _async_create_collection_and_scope (#8158)`
- Source links:
  - https://github.com/agno-agi/agno/commit/7595e14
  - https://github.com/agno-agi/agno/commit/5749e44
- Local mapping: `ops/scripts/mcp_service_runtime_smoke.py` probes repo-local stdio MCP services. A subprocess launch or cwd failure should be represented as one failed service result, not as an uncaught Python exception that aborts the whole smoke path.

## A/B Contract

- Baseline: timeout failures already became structured service failures, but `OSError` from `subprocess.run` could still escape `run_service_smoke`.
- Variant: convert launch/cwd `OSError` into the same structured failed service shape used by timeout failures.
- Primary KPI: MCP runtime smoke keeps producing actionable service-level evidence when one MCP process cannot start.
- Guardrails: no manifest change, no successful-service behavior change, no credentialed calls, and no change to the overall fail-fast policy when a report contains failed services.
- Decision rule: adopt if focused runtime-smoke tests pass and the real eligible services still initialize and list tools.

## Result

- Adopted variant: yes.
- Added `build_failed_service_result` so timeout and launch failures share one report shape.
- Added `test_run_service_smoke_converts_launch_error_to_failed_service`.
- Launch failures now emit `runtime launch failed: ...` in the service-level `errors` list.
- Changed paths:
  - `ops/scripts/mcp_service_runtime_smoke.py`
  - `tests/test_mcp_service_runtime_smoke.py`
  - `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_LAUNCH_FAILURE_GUARD_2026-06-05.json`
  - `docs/reports/2026-06/MCP_SERVICE_RUNTIME_SMOKE_LAUNCH_FAILURE_GUARD_2026-06-05.md`

## Verification

```text
python -m pytest tests\test_mcp_service_runtime_smoke.py -q --tb=line
6 passed in 0.83s
```

```text
python ops\scripts\mcp_service_runtime_smoke.py --json-out docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_LAUNCH_FAILURE_GUARD_2026-06-05.json --markdown-out docs\reports\2026-06\MCP_SERVICE_RUNTIME_SMOKE_LAUNCH_FAILURE_GUARD_2026-06-05.md --timeout 25
mcp service runtime smoke valid: 3 checked, 3 passed, 39 tools
```

## Freshness

- Pushed proof commit: `f03c27c`.
- `current_tip_freshness_gate`: `f03c27c` is the active proof baseline for `origin/feat/observability-gateway-2026-05`; this cycle changes the MCP runtime smoke guard, its tests, and evidence artifacts after that proof.
- `protected_path_freshness`: no changed protected paths after proof.
- Audit marker: `global_objective_complete=false`.

## Next Cycle

- Continue the overflow review with `crewAIInc/crewAI` or the next repository that exposes a source signal directly mapped to launch evidence.
- If a future MCP smoke adds HTTP/SSE services, apply the same service-level failure shape to transport setup failures.
