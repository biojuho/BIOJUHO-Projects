# AutoResearch Loop - AgriGuard Ready Gate Path Override - 2026-07-06

## Objective

Ensure `run_guarded_launch.py --status-only` reports the explicitly selected ready-gate JSON path when `--handoff-ready-gate-json-out` is provided, instead of falling back to a stale ready-gate path from an existing artifact index.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READY_GATE_PATH_OVERRIDE_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/run_guarded_launch.py`
  - Adds an explicit `ready_gate_json` input to `_build_status_view`.
  - Lets a provided `--handoff-ready-gate-json-out` override the artifact-index `ready_gate_json` path.
  - Preserves existing artifact-index path behavior when no explicit ready-gate override is supplied.
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Adds a regression where an artifact index points at a stale ready-gate file and the CLI override points at the selected file.
  - Keeps existing custom-index and live-ready-gate tests passing.

## Verification

- Focused guarded-launch status tests:
  - Result: `3 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Result: `30 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-ready-gate-path-override.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

Status-only ready-gate check:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate-current-override-2026-07-06.json --handoff-ready-gate-json-out var\agriguard-guarded-launch-ready-gate-current-check-2026-07-06.json
```

- Result: exit `1`, expected because strict readiness still fails closed.
- Status JSON: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`
- Ready-gate path: `D:\AI project\var\agriguard-guarded-launch-ready-gate-current-check-2026-07-06.json`
- Firebase blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Current Launch State

Status-only ready-gate views now honor the explicit ready-gate path. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
