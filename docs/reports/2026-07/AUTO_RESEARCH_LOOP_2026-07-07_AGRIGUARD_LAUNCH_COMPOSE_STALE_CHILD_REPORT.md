# AutoResearch Loop: AgriGuard Launch-Compose Stale Child Report

- Date: 2026-07-07 KST
- Scope: AgriGuard launch-compose child report summarization
- Owned code paths:
  - `apps/AgriGuard/scripts/launch_compose.py`
  - `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_LAUNCH_COMPOSE_STALE_CHILD_REPORT.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_LAUNCH_COMPOSE_STALE_CHILD_REPORT_2026-07-07.md`

## Objective

Close the next evidence-chain gap after packet/readiness stale-field propagation. Launch-compose child reports summarized operator packets but dropped `artifact_index_stale_generated_at_roles` and `artifact_index_stale_generated_at_details`, so a preflight failure report could still hide stale artifact-index diagnostics even when the packet itself preserved them.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- Relevant adopted pattern: machine-readable child-report propagation and fail-closed status surfaces from the source-backed agent readiness comparison set.

## A/B Hypothesis

- Baseline: launch-compose child report exposes artifact-index status/blocker/metadata, but omits stale generated-at roles/details.
- Variant: include stale generated-at roles/details in `_summarize_operator_packet_json`.
- Primary KPI: a launch-compose preflight failure seeded with a stale artifact index exposes `child_reports.operator_packet.artifact_index_stale_generated_at_roles=["ready_gate_json"]`.
- Guardrails: existing child-report shape remains stable, preflight blocker classification remains unchanged, and canonical AgriGuard smoke passes.
- Decision rule: adopt only if targeted tests, combined guarded-launch tests, live scratch launch-compose proof, and canonical smoke pass.

## Baseline Evidence

Live launch report inspection before the patch:

- `var/agriguard-guarded-launch-launch-report.json`
  - `status=fail`
  - `stage=preflight`
  - `child_reports.operator_packet.artifact_index_status=pass`
  - `child_reports.operator_packet.artifact_index_blocker_class=ready`
  - `child_reports.operator_packet.artifact_index_stale_generated_at_roles`: absent
  - `child_reports.operator_packet.artifact_index_stale_generated_at_details`: absent

## Variant Evidence

Implemented propagation:

- Added `_dict_list` normalization in `launch_compose.py`.
- Added `artifact_index_stale_generated_at_roles` and `artifact_index_stale_generated_at_details` to `_summarize_operator_packet_json`.
- Updated launch-compose tests for both non-empty stale roles and empty defaults.

Live scratch launch-compose proof:

- Seeded scratch artifact index:
  - `var\agriguard-launch-compose-stale-child-report-2026-07-07\stale-compose-artifact-index.json`
  - source: `var\agriguard-guarded-launch-artifact-index-ready-gate-freshness-before-refresh-2026-07-07.json`
- Command: `python apps\AgriGuard\scripts\launch_compose.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --json-out var\agriguard-launch-compose-stale-child-report-2026-07-07\launch-preflight.json --launch-report-json var\agriguard-launch-compose-stale-child-report-2026-07-07\launch-report.json --operator-packet-json var\agriguard-launch-compose-stale-child-report-2026-07-07\operator-packet.json --operator-packet-markdown var\agriguard-launch-compose-stale-child-report-2026-07-07\operator-packet.md --operator-env-template var\agriguard-launch-compose-stale-child-report-2026-07-07\operator.env.template --readiness-summary-json var\agriguard-launch-compose-stale-child-report-2026-07-07\readiness-summary.json --readiness-summary-markdown var\agriguard-launch-compose-stale-child-report-2026-07-07\readiness-summary.md --validate-env-file-shape --env-validation-json-out var\agriguard-launch-compose-stale-child-report-2026-07-07\env-validation.json --env-validation-markdown-out var\agriguard-launch-compose-stale-child-report-2026-07-07\env-validation.md --guarded-output-dir var\agriguard-launch-compose-stale-child-report-2026-07-07 --guarded-output-prefix stale-compose`
- Result:
  - exit code `1`, expected from missing Firebase credentials
  - launch `status=fail`
  - launch `blocker_class=preflight_blocked`
  - launch `stage=preflight`
  - `child_reports.operator_packet.artifact_index_status=fail`
  - `child_reports.operator_packet.artifact_index_blocker_class=artifact_index_blocked`
  - `child_reports.operator_packet.artifact_index_stale_generated_at_roles=["ready_gate_json"]`
  - stale detail preserved `minimum_role=handoff_consumer_json`

## Verification Commands

- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py -q`
  - Result: 18 passed
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: 100 passed
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-launch-compose-stale-child-report-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_LAUNCH_COMPOSE_STALE_CHILD_REPORT_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-compose-stale-child-report.json`
  - Result: `status=complete`, passed=5, failed=0, total=5

## Decision

Adopted. Launch-compose child reports now preserve stale artifact-index diagnostics across the same failure path that stops before compose.

## Remaining Blocker

Launch remains externally blocked by the missing real Firebase Admin service account file for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue by checking whether the default live guarded-launch artifacts should be regenerated end-to-end after all stale-field propagation changes, while preserving the expected Firebase preflight blocker.
