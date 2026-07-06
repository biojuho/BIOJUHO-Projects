# AutoResearch Loop: AgriGuard Compose Replacement Guard

- Date: 2026-07-07 KST
- Scope: AgriGuard launch-compose runtime replacement safety
- Owned code paths:
  - `apps/AgriGuard/scripts/launch_compose.py`
  - `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_COMPOSE_REPLACEMENT_GUARD.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`

## Objective

Make the safe replacement policy for the stale Docker runtime explicit in launch artifacts. `launch_compose.py` already ran env-shape validation and strict preflight before `docker compose up`, but the dry-run and failed-launch JSON required operators to infer that the current runtime would not be touched before those gates passed.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: bounded continuous launch automation should make stop/replacement policy machine-readable and fail closed before destructive runtime actions.

## A/B Hypothesis

- Baseline: dry-run output includes preflight and compose commands, but the safety invariant is implicit.
- Variant: add `compose_replacement_guard` to dry-run plans and launch reports.
- Primary KPI: operators and automation can read that current runtime action before preflight is `none` and compose runs only after preflight passes.
- Guardrails: launch command order remains unchanged, preflight failures still do not run compose, and guarded-launch tests plus AgriGuard smoke remain green.

## Variant Evidence

Implemented:

- Added `compose_replacement_guard` to `launch_compose.py`.
- Fields:
  - `current_runtime_action_before_preflight=none`
  - `compose_replacement_requires_env_shape_validation`
  - `compose_replacement_requires_strict_preflight=true`
  - `compose_runs_only_after_preflight_passes=true`
  - blocked stop reasons for env-shape and strict preflight failures

Dry-run proof:

```powershell
python apps\AgriGuard\scripts\launch_compose.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --validate-env-file-shape --json-out var\agriguard-safe-replace-dry-run-preflight.json --dry-run
```

Result:

- `status=dry_run`
- `compose_replacement_guard.current_runtime_action_before_preflight=none`
- `compose_replacement_guard.compose_runs_only_after_preflight_passes=true`

Current missing-Firebase failure proof:

```powershell
python apps\AgriGuard\scripts\launch_compose.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --validate-env-file-shape --json-out var\agriguard-safe-replace-preflight.json --launch-report-json var\agriguard-safe-replace-launch-report.json --operator-packet-json var\agriguard-safe-replace-operator-packet.json --operator-packet-markdown var\agriguard-safe-replace-operator-packet.md --operator-env-template var\agriguard-safe-replace-operator.env.template
```

Result:

- `status=fail`
- `stage=preflight`
- `stop_reason=preflight_failed`
- result names: `env_validation`, `preflight`, `operator_packet`
- `compose_replacement_guard.current_runtime_action_before_preflight=none`
- `compose_replacement_guard.compose_runs_only_after_preflight_passes=true`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\launch_compose.py apps\AgriGuard\backend\tests\test_launch_compose_script.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py -q`
  - Result: 18 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 102 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-compose-replacement-guard.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-compose-replacement-guard-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The launch-compose runtime replacement policy is now explicit and machine-readable without changing the existing fail-closed command order.

## Remaining Blockers

- The running default Docker backend on `8002` remains stale.
- Current compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue by surfacing `compose_replacement_guard` through the higher-level guarded-launch status, handoff, and operator packet artifacts so the same safety policy is visible from the wrapper entry point.
