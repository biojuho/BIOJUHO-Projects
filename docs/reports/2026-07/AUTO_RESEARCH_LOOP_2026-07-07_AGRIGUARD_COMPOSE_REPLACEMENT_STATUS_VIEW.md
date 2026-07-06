# AutoResearch Loop: AgriGuard Compose Replacement Status View

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch readiness/status/handoff guard visibility
- Owned code paths:
  - `apps/AgriGuard/scripts/summarize_launch_readiness.py`
  - `apps/AgriGuard/scripts/run_guarded_launch.py`
  - `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
  - `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
  - `apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
  - `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_COMPOSE_REPLACEMENT_STATUS_VIEW.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_COMPOSE_REPLACEMENT_STATUS_VIEW_2026-07-07.md`

## Objective

The previous cycle made `compose_replacement_guard` explicit in `launch_compose.py` dry-run and launch-report artifacts. This cycle carries the same fail-closed replacement policy into the higher-level operator surfaces so a guarded-launch status check or handoff does not require opening the raw launch report.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: machine-readable launch safety evidence should propagate through status, handoff, and consumer schema surfaces instead of remaining only in the producer report.

## A/B Hypothesis

- Baseline: `launch_compose.py` reports the safe replacement policy, but `summarize_launch_readiness.py`, `run_guarded_launch.py --status-only`, and handoff markdown do not expose it.
- Variant: copy `launch.compose_replacement_guard` into readiness summaries and guarded-launch status views, render the key guard signals in readiness/handoff markdown, and extend the closed handoff schema.
- Primary KPI: a current guarded-launch status view exposes `launch.compose_replacement_guard.current_runtime_action_before_preflight=none` and `compose_runs_only_after_preflight_passes=true`.
- Guardrails: no change to compose execution order, no raw secret exposure, and focused plus aggregate launch tests remain green.

## Variant Evidence

Implemented:

- `summarize_launch_readiness.py` now copies `compose_replacement_guard` from the launch report into `reports.launch`.
- Readiness markdown renders:
  - `Compose replacement action before preflight`
  - `Compose replacement requires strict preflight`
  - `Compose runs only after preflight passes`
- `run_guarded_launch.py --status-only` now exposes the same guard under `launch.compose_replacement_guard`.
- `render_guarded_launch_handoff.py` renders the same three guard signals in handoff markdown.
- `guarded_launch_handoff.schema.json` accepts the closed guard object in `status_view.launch`.

Current readiness-summary proof from the existing failed safe-replace preflight:

```powershell
python apps\AgriGuard\scripts\summarize_launch_readiness.py --app-root apps\AgriGuard --launch-report-json var\agriguard-safe-replace-launch-report.json --env-validation-json var\agriguard-compose-replacement-status-view-missing-env-validation.json --operator-packet-json var\agriguard-safe-replace-operator-packet.json --json-out var\agriguard-compose-replacement-status-view-readiness-summary.json --markdown-out var\agriguard-compose-replacement-status-view-readiness-summary.md --exit-zero-on-blocked
```

Result:

- `status=blocked`
- `blocker_class=preflight_blocked`
- `reports.launch.compose_replacement_guard.current_runtime_action_before_preflight=none`
- `reports.launch.compose_replacement_guard.compose_replacement_requires_strict_preflight=true`
- `reports.launch.compose_replacement_guard.compose_runs_only_after_preflight_passes=true`

Current guarded-launch status proof from the same prefix:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-safe-replace --status-only --status-json-out var\agriguard-compose-replacement-status-view-status.json
```

Result:

- top-level `status=fail` because the selected prefix has no matching readiness-summary artifact
- `blocker_class=preflight_blocked`
- `launch.status=fail`
- `launch.stage=preflight`
- `launch.stop_reason=preflight_failed`
- `launch.compose_replacement_guard.current_runtime_action_before_preflight=none`
- `launch.compose_replacement_guard.compose_runs_only_after_preflight_passes=true`
- `operator_action_ids=["set_firebase_service_account_file"]`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\summarize_launch_readiness.py apps\AgriGuard\scripts\run_guarded_launch.py apps\AgriGuard\scripts\render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py -q`
  - Result: 44 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 107 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-compose-replacement-status-view.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-compose-replacement-status-view.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_COMPOSE_REPLACEMENT_STATUS_VIEW_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The compose replacement safety policy now reaches the readiness summary, guarded-launch status view, handoff markdown, and handoff schema without changing runtime replacement behavior.

## Remaining Blockers

- The running default Docker backend on `8002` remains stale.
- Current compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
