# AutoResearch Loop: AgriGuard Status Normalized Launch-Only Failure

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch status classification
- Owned code paths:
  - `apps/AgriGuard/scripts/run_guarded_launch.py`
  - `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_STATUS_NORMALIZED_LAUNCH_ONLY_FAILURE.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_STATUS_NORMALIZED_LAUNCH_ONLY_FAILURE_2026-07-07.md`

## Objective

When a guarded-launch status view has a failed launch report but no matching readiness-summary artifact, it previously returned top-level `status=fail` while also classifying `blocker_class=preflight_blocked`. Operators and automation should see a normalized top-level blocked state while the raw launch failure remains visible under `launch.status`.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: status APIs should expose an operator-level state and preserve raw child status separately.

## A/B Hypothesis

- Baseline: launch-only preflight failure reports top-level `status=fail`, `blocker_class=preflight_blocked`, and `launch.status=fail`.
- Variant: if the launch report is classifiable as a blocker, report top-level `status=blocked` while preserving `launch.status=fail`.
- Primary KPI: current `agriguard-safe-replace` status-only output reports `status=blocked`, `blocker_class=preflight_blocked`, and `launch.status=fail`.
- Guardrails: ready detection remains `status=ready` and `blocker_class=ready`; raw launch status remains unchanged; launch/handoff suites stay green.

## Variant Evidence

Implemented:

- `run_guarded_launch._build_status_view` now computes launch and operator-packet blocker classes once.
- If no readiness summary exists and the launch report has a classifiable blocker, top-level status becomes `blocked`.
- Raw launch status remains under `launch.status`.

Current status proof:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-safe-replace --status-only --status-json-out var\agriguard-status-normalized-launch-only-failure.json
```

Result:

- top-level `status=blocked`
- top-level `blocker_class=preflight_blocked`
- `launch.status=fail`
- `launch.stage=preflight`
- `launch.stop_reason=preflight_failed`
- `operator_action_ids=["set_firebase_service_account_file"]`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\run_guarded_launch.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 33 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 107 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-normalized-launch-only-failure.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-status-normalized-launch-only-failure.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_STATUS_NORMALIZED_LAUNCH_ONLY_FAILURE_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. Guarded-launch status now separates operator-level blocked state from raw launch failure details.

## Remaining Blockers

- The running default Docker backend on `8002` remains stale.
- Current compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
