# AutoResearch Loop: AgriGuard Browser Precheck Status View

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch compact status JSON
- Owned code paths:
  - `apps/AgriGuard/scripts/run_guarded_launch.py`
  - `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_BROWSER_PRECHECK_STATUS_VIEW.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_PRECHECK_STATUS_VIEW_2026-07-07.md`

## Objective

Mirror the artifact-index `launch_browser_smoke` evidence into the compact guarded-launch status view. The previous cycle preserved browser precheck failures in the artifact index and operator packet, but status-only JSON consumers still had to look under `readiness_summary.browser_smoke` instead of the `artifact_index` block they already use for evidence health.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- Relevant adopted pattern: compact machine-readable status views should mirror critical failure evidence from the authoritative artifact rather than forcing consumers to infer across sibling summaries.

## A/B Hypothesis

- Baseline: `artifact_index.launch_browser_smoke` exists in the artifact index, while status-only output omits it from the compact `artifact_index` block.
- Variant: normalize the artifact-index browser-smoke object with the existing status-view browser-smoke shape and include it only when the artifact index carries that field.
- Primary KPI: live `--status-only` output exposes `artifact_index.launch_browser_smoke` with path/status/precheck fields.
- Guardrails: old artifact indexes without `launch_browser_smoke` keep their current shape, dry-run artifact-index summaries remain compatible, and guarded-launch tests plus workspace smoke remain green.

## Variant Evidence

Implemented:

- Added `_artifact_index_browser_smoke_status_view` in `run_guarded_launch.py`.
- `artifact_index.launch_browser_smoke` is now included in status-only output when the artifact index contains `launch_browser_smoke`.
- Dry-run `artifact_index_readiness_summary` also mirrors the same normalized browser-smoke object.

Live status-only proof after regenerating guarded-launch artifacts:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --status-only --env-file var\agriguard-launch-operator.missing-firebase.env --status-json-out var\agriguard-guarded-launch-status-only-browser-index-live.json
```

Result:

- `status=blocked`
- `blocker_class=preflight_blocked`
- `artifact_index.launch_browser_smoke.found=false`
- `artifact_index.launch_browser_smoke.path=var/agriguard-browser-smoke-suite-compose-launch.json`

The `found=false` result is correct for the current environment because strict launch preflight still stops at the missing Firebase service-account file before browser smoke can run.

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\run_guarded_launch.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 33 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 102 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-browser-precheck-status-view.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-browser-precheck-status-view-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_PRECHECK_STATUS_VIEW_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The compact guarded-launch status view now carries artifact-index browser-smoke evidence without forcing consumers to inspect separate readiness-summary branches.

## Remaining Blockers

- The default live target on `5174/8002` is still stale for public verify cache headers until the backend/proxy is restarted or rebuilt.
- Launch remains externally blocked by the missing real Firebase Admin service-account file at `C:\secure\missing-firebase-service-account.json` for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue toward the launch boundary: once the real Firebase service-account file is supplied, rerun guarded launch and the full browser smoke so the public verify cache-header precheck can validate the compose/browser runtime.
