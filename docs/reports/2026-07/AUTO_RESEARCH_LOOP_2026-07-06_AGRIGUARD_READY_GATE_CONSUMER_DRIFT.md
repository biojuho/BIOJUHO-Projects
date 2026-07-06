# AutoResearch Loop - AgriGuard Ready Gate Consumer Drift - 2026-07-06

## Objective

Make the guarded-launch handoff consumer compare the handoff-level ready gate against the status-view current ready-gate result, and surface both values in consumer JSON.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READY_GATE_CONSUMER_DRIFT_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
  - Emits `status_view_ready_gate_current_status`.
  - Emits `status_view_ready_gate_current_blocker_class`.
  - Adds semantic drift errors when handoff `ready_gate.status` or `ready_gate.blocker_class` diverge from the status-view current ready-gate result.
- `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
  - Covers clean ready and blocked consumer views with the new current ready-gate fields.
  - Covers drift detection when a blocked handoff is tampered to report a passing ready gate.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
  - Result: `9 passed`
- Full launch/handoff suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Result: `175 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-ready-gate-consumer-drift.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

Consumer command:

```powershell
python apps\AgriGuard\scripts\consume_guarded_launch_handoff.py var\agriguard-guarded-launch-handoff-ready-gate-current-check-2026-07-06.json --validation-json var\agriguard-guarded-launch-handoff-ready-gate-current-check-2026-07-06.validation.json --json-out var\agriguard-guarded-launch-handoff-ready-gate-consumer-drift-2026-07-06.consumer.json --exit-zero-on-blocked
```

- Result: exit `0`
- Consumer JSON: `status=fail`, `blocker_class=preflight_blocked`, `validation_status=pass`, `errors=[]`
- Handoff ready gate: `ready_gate_status=fail`
- Status-view current ready gate: `status_view_ready_gate_current_status=fail`, `status_view_ready_gate_current_blocker_class=preflight_blocked`

## Current Launch State

The handoff consumer now detects ready-gate semantic drift between handoff and status-view evidence. The current live consumer evidence is cleanly blocked only by preflight, and real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
