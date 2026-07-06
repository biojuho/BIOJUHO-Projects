# AutoResearch Loop: AgriGuard Status Stale-Field Propagation

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch compact status, handoff schema, handoff Markdown, and consumer view
- Owned code paths:
  - `apps/AgriGuard/scripts/run_guarded_launch.py`
  - `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
  - `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
  - `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
  - `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
  - `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_STATUS_STALE_FIELD_PROPAGATION.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_STATUS_STALE_FIELD_PROPAGATION_2026-07-07.md`

## Objective

Keep the compact guarded-launch operator surfaces aligned with the new artifact-index stale timestamp contract. The previous cycle added `stale_generated_at_roles` and `stale_generated_at_details` to the artifact index, but the status-only view, handoff schema, handoff Markdown, and consumer output did not all expose that signal.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- Relevant adopted pattern: fail-closed machine-readable status and durable audit surfaces from `Veritas-7/autoresearch-skill-system`; latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## A/B Hypothesis

- Baseline: artifact index emits stale generated-at fields, but `run_guarded_launch.py --status-only` and handoff/consumer surfaces omit them.
- Variant: propagate `stale_generated_at_roles` and `stale_generated_at_details` through compact status, handoff schema validation, handoff Markdown, and consumer JSON.
- Primary KPI: a stale artifact index selected by `--status-only` exposes `artifact_index.stale_generated_at_roles=["ready_gate_json"]`.
- Guardrails: clean refreshed artifacts still show empty stale fields, handoff validation accepts the schema, and canonical AgriGuard smoke remains green.
- Decision rule: adopt only if live stale and clean probes both produce the expected machine-readable fields and tests/smoke pass.

## Baseline Evidence

Live ready-gate inspection after the freshness patch showed the compact status carried operator action and credential details, but not stale artifact-index fields:

- `operator_action_ids`: `["set_firebase_service_account_file"]`
- `operator_packet.preflight_checks.firebase_credentials_source`: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`
- `operator_packet.preflight_checks.firebase_credentials_resolved_path`: `C:\secure\missing-firebase-service-account.json`
- `artifact_index` keys did not include `stale_generated_at_roles` or `stale_generated_at_details`.

## Variant Evidence

Implemented propagation and contract updates:

- Added `_dict_list` normalization in `run_guarded_launch.py`.
- Added `artifact_index.stale_generated_at_roles` and `artifact_index.stale_generated_at_details` to compact status.
- Added the same stale fields to `artifact_index_readiness_summary`.
- Updated `guarded_launch_handoff.schema.json` so handoff validation accepts and requires the new status fields.
- Added handoff Markdown line: `Artifact index stale generated_at roles`.
- Added consumer JSON fields `artifact_index_stale_generated_at_roles` and `artifact_index_stale_generated_at_details`.
- Added focused regression coverage for non-empty stale propagation.

Live clean status proof:

- Command: `python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --status-only --status-json-out var\agriguard-guarded-launch-status-stale-field-propagation-2026-07-07.json`
- Result: exit code `0`, `status=blocked`, `blocker_class=preflight_blocked`
- `artifact_index.status`: `pass`
- `artifact_index.stale_generated_at_roles`: `[]`
- `artifact_index.stale_generated_at_details`: `[]`
- Firebase blocker remained explicit at `C:\secure\missing-firebase-service-account.json`.

Live stale-index propagation proof:

- Command: `python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --artifact-index-json-out var\agriguard-guarded-launch-artifact-index-ready-gate-freshness-before-refresh-2026-07-07.json --status-only --status-json-out var\agriguard-guarded-launch-status-stale-index-propagation-2026-07-07.json`
- Result: exit code `0`, top-level `status=blocked`, `blocker_class=preflight_blocked`
- `artifact_index.status`: `fail`
- `artifact_index.blocker_class`: `artifact_index_blocked`
- `artifact_index.stale_generated_at_roles`: `["ready_gate_json"]`
- `artifact_index.stale_generated_at_details[0].minimum_role`: `handoff_consumer_json`

## Verification Commands

- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: 32 passed
- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: 58 passed
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-status-stale-field-propagation-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_STATUS_STALE_FIELD_PROPAGATION_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-stale-field-propagation.json`
  - Result: `status=complete`, passed=5, failed=0, total=5

## Decision

Adopted. The variant makes stale artifact-index freshness visible in the compact status, handoff, Markdown, and consumer views without changing the underlying Firebase blocker classification.

## Remaining Blocker

Launch remains externally blocked by the missing real Firebase Admin service account file for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. The local evidence chain now exposes both credential blocker details and artifact-index stale timestamp diagnostics.

## Next Cycle

Continue by inspecting the next mismatch in the live guarded-launch evidence chain. A likely target is whether stale generated-at details should be included in the operator packet readiness summary when artifact-index recovery is required.
