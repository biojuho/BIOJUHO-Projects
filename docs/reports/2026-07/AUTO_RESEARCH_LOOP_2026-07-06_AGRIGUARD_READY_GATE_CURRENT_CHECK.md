# AutoResearch Loop - AgriGuard Ready Gate Current Check - 2026-07-06

## Objective

Make `run_guarded_launch.py --status-only --require-ready` JSON self-contained by exposing the current ready-gate result even when the status view also references a prior ready-gate artifact.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READY_GATE_CURRENT_CHECK_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/run_guarded_launch.py`
  - Adds `ready_gate.current_status` to the compact status view.
  - Adds `ready_gate.current_blocker_class` to show the current computed blocker independently of any referenced ready-gate artifact.
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
  - Requires the new current ready-gate fields under `status_view.ready_gate`.
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Covers custom ready-gate paths and live ready-gate file-state views with the new current-check fields.

## Verification

- Focused ready-gate/schema subset:
  - Result: `8 passed`
- Full launch/handoff suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Result: `175 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-ready-gate-current-check.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

Ready-gate status command:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --artifact-index-json-out var\agriguard-guarded-launch-artifact-index.json --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate-current-check-2026-07-06.json
```

- Result: exit `1` as expected for the current blocked launch path.
- Status JSON: `status=blocked`, `blocker_class=preflight_blocked`, `generated_at=2026-07-06T13:32:39Z`
- Referenced ready-gate artifact: `ready_gate.status=blocked`
- Current ready-gate check: `ready_gate.current_status=fail`, `ready_gate.current_blocker_class=preflight_blocked`
- Preflight blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Handoff validation:

```powershell
python apps\AgriGuard\scripts\render_guarded_launch_handoff.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --ready-gate-json var\agriguard-guarded-launch-ready-gate-current-check-2026-07-06.json --json-out var\agriguard-guarded-launch-handoff-ready-gate-current-check-2026-07-06.json --markdown-out var\agriguard-guarded-launch-handoff-ready-gate-current-check-2026-07-06.md --validation-json-out var\agriguard-guarded-launch-handoff-ready-gate-current-check-2026-07-06.validation.json --exit-zero-on-blocked
```

- Result: exit `0`
- Validation: `status=pass`, `blocker_class=ready`, `errors=[]`, `generated_at=2026-07-06T13:32:48Z`

## Current Launch State

The ready-gate JSON now carries a current gate result and the existing referenced ready-gate artifact state. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
