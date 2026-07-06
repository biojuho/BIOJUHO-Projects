# AutoResearch Loop: AgriGuard End-to-End Ready-Gate Refresh

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch wrapper artifact freshness
- Owned code paths:
  - `apps/AgriGuard/scripts/run_guarded_launch.py`
  - `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_END_TO_END_READY_GATE_REFRESH.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_END_TO_END_READY_GATE_REFRESH_2026-07-07.md`

## Objective

Close the live default guarded-launch gap left after stale ready-gate checks were added to the artifact index. The wrapper regenerated handoff and consumer artifacts, then ran the artifact index against an older default ready-gate JSON. The final index failed with `stale_generated_at_roles=["ready_gate_json"]`, even though the only real launch blocker remained the missing Firebase Admin service-account file.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- Relevant adopted pattern: readiness gates should repair generated local status views before surfacing a final fail-closed machine-readable report.

## A/B Hypothesis

- Baseline: the wrapper treats a stale default ready-gate index failure as a terminal post-launch failure.
- Variant: when the failed artifact index reports that the only generated-at problem is `ready_gate_json`, write a fresh self-referential ready-gate status JSON and rerun the index once.
- Primary KPI: default live guarded-launch artifacts end with `artifact-index.status=pass` and empty stale roles while the command still exits `1` for the expected Firebase preflight blocker.
- Guardrails: unrelated artifact-index failures do not get hidden, packet/readiness/launch projections clear stale role fields, and canonical AgriGuard smoke stays green.
- Decision rule: adopt only if focused wrapper tests, combined guarded-launch tests, live guarded-launch proof, radar, and AgriGuard smoke pass.

## Baseline Evidence

Live default wrapper before the patch:

- Command: `python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --status-json-out var\agriguard-guarded-launch-status.json --emit-handoff`
- Result:
  - exit code `1`
  - launch `status=fail`, `blocker_class=preflight_blocked`, `stage=preflight`
  - final artifact index `status=fail`, `blocker_class=artifact_index_blocked`
  - final artifact index `stale_generated_at_roles=["ready_gate_json"]`
  - status JSON propagated `artifact_index.stale_generated_at_roles=["ready_gate_json"]`

## Variant Evidence

Implemented wrapper recovery:

- Added `_artifact_index_ready_gate_refresh_applicable` to only classify ready-gate-only generated-at failures as recoverable.
- Added `_run_artifact_index_command` to write a current ready-gate status view and rerun the index once.
- Routed all guarded-launch artifact-index execution points through the recovery helper.
- Extended wrapper projection refreshes so old `artifact_index_stale_generated_at_roles` and `artifact_index_stale_generated_at_details` fields are overwritten, including with empty lists.

Live default wrapper after the patch:

- Command: `python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --status-json-out var\agriguard-guarded-launch-status.json --emit-handoff`
- Log: `var\agriguard-guarded-launch-end-to-end-ready-gate-refresh-2026-07-07.log`
- Result:
  - exit code `1`, expected from missing Firebase credentials
  - launch `status=fail`, `blocker_class=preflight_blocked`, `stage=preflight`
  - launch child operator packet `artifact_index_status=pass`
  - launch child operator packet `artifact_index_stale_generated_at_roles=[]`
  - operator packet evidence `artifact_index_readiness_summary.status=pass`
  - operator packet evidence `stale_generated_at_roles=[]`
  - readiness summary operator packet `artifact_index_status=pass`
  - readiness summary operator packet `artifact_index_stale_generated_at_roles=[]`
  - final artifact index `status=pass`, `blocker_class=ready`, `stale_generated_at_roles=[]`
  - status JSON `artifact_index.status=pass`, `artifact_index.stale_generated_at_roles=[]`
  - index artifact timestamps: `handoff_consumer_json=2026-07-06T16:16:14Z`, `ready_gate_json=2026-07-06T16:16:14Z`

## Verification Commands

- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: 33 passed
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: 101 passed
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-end-to-end-ready-gate-refresh-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_END_TO_END_READY_GATE_REFRESH_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-end-to-end-ready-gate-refresh.json`
  - Result: `status=complete`, passed=5, failed=0, total=5

## Decision

Adopted. The default guarded-launch path now repairs the generated ready-gate artifact before final artifact-index classification, and all downstream machine-readable surfaces agree that artifact freshness is clean.

## Remaining Blocker

Launch remains externally blocked by the missing real Firebase Admin service-account file at `C:\secure\missing-firebase-service-account.json` for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue launch hardening by looking for the next mismatch between live guarded-launch artifacts and operator-facing recovery commands, while preserving the expected Firebase preflight block until real credentials are provided.
