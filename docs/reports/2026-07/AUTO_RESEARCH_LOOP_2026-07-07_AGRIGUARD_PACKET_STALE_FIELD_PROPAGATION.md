# AutoResearch Loop: AgriGuard Packet Stale-Field Propagation

- Date: 2026-07-07 KST
- Scope: AgriGuard operator packet and launch readiness summary
- Owned code paths:
  - `apps/AgriGuard/scripts/render_launch_operator_packet.py`
  - `apps/AgriGuard/scripts/summarize_launch_readiness.py`
  - `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - `apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_PACKET_STALE_FIELD_PROPAGATION.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_PACKET_STALE_FIELD_PROPAGATION_2026-07-07.md`

## Objective

Continue aligning AgriGuard launch-readiness surfaces after the artifact-index stale timestamp gate. The compact status and handoff consumer now expose stale generated-at roles, but the operator packet and launch readiness summary still dropped those fields from `artifact_index_readiness_summary` and `reports.operator_packet`.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- Relevant adopted pattern: source-backed fail-closed machine-readable status propagation from the AutoResearch/agent-readiness comparison set, especially durable status archives and completion audits.

## A/B Hypothesis

- Baseline: operator packet and readiness summary show artifact-index status/blocker/metadata, but omit stale generated-at roles/details.
- Variant: propagate `stale_generated_at_roles` and `stale_generated_at_details` through operator packet JSON, operator packet Markdown, readiness summary JSON, and readiness summary Markdown.
- Primary KPI: a stale artifact index selected by the packet renderer appears as `ready_gate_json` in both packet and readiness summary stale-role fields.
- Guardrails: clean refreshed artifacts keep empty stale arrays, existing recovery/status metadata remains unchanged, and canonical AgriGuard smoke passes.
- Decision rule: adopt only if clean and seeded-stale live probes both produce expected fields and tests/smoke pass.

## Baseline Evidence

Live inspection of current artifacts showed:

- `var/agriguard-guarded-launch-operator-packet.json`
  - `guarded_launch_evidence.artifact_index_readiness_summary` included `missing_generated_at_roles`
  - `stale_generated_at_roles`: absent
  - `stale_generated_at_details`: absent
- `var/agriguard-guarded-launch-readiness-summary.json`
  - `reports.operator_packet.artifact_index_status`: `pass`
  - `reports.operator_packet.artifact_index_stale_generated_at_roles`: absent

## Variant Evidence

Implemented propagation:

- `render_launch_operator_packet.py`
  - Added stale roles/details to `_artifact_index_readiness_summary`.
  - Added `Stale generated_at roles` to operator packet Markdown.
- `summarize_launch_readiness.py`
  - Added stale roles/details from packet artifact-index readiness summary to `reports.operator_packet`.
  - Added stale generated-at role line to readiness Markdown.
- Tests now assert non-empty stale propagation from artifact index to packet and readiness summary.

Clean current artifact proof:

- Command: `python apps\AgriGuard\scripts\render_launch_operator_packet.py ... --guarded-output-dir var --guarded-output-prefix agriguard-guarded-launch --exit-zero-on-blocked`
- Command: `python apps\AgriGuard\scripts\summarize_launch_readiness.py ... --operator-packet-json var\agriguard-operator-packet-stale-fields-clean-2026-07-07.json --exit-zero-on-blocked`
- Result:
  - Packet `artifact_index.status`: `pass`
  - Packet `stale_generated_at_roles`: `[]`
  - Readiness summary `artifact_index.status`: `pass`
  - Readiness summary `artifact_index_stale_generated_at_roles`: `[]`

Seeded stale-index proof:

- Seeded scratch artifact index: copied `var\agriguard-guarded-launch-artifact-index-ready-gate-freshness-before-refresh-2026-07-07.json` to `var\agriguard-stale-artifact-index-packet-propagation-2026-07-07\stale-prop-artifact-index.json`.
- Rendered operator packet with `--guarded-output-dir var\agriguard-stale-artifact-index-packet-propagation-2026-07-07 --guarded-output-prefix stale-prop`.
- Summarized readiness from that packet.
- Result:
  - Packet `artifact_index.status`: `fail`
  - Packet `artifact_index.blocker_class`: `artifact_index_blocked`
  - Packet `stale_generated_at_roles`: `["ready_gate_json"]`
  - Readiness summary `artifact_index.status`: `fail`
  - Readiness summary `artifact_index_stale_generated_at_roles`: `["ready_gate_json"]`
  - Stale detail preserved `minimum_role=handoff_consumer_json`.

## Verification Commands

- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_launch_compose_script.py -q`
  - Result: 42 passed
- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: 100 passed
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-packet-stale-field-propagation-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_PACKET_STALE_FIELD_PROPAGATION_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-packet-stale-field-propagation.json`
  - Result: `status=complete`, passed=5, failed=0, total=5

## Decision

Adopted. Operator-facing packet and readiness summary surfaces now preserve stale artifact-index freshness diagnostics without weakening the Firebase service-account blocker.

## Remaining Blocker

Launch remains externally blocked by the missing real Firebase Admin service account file for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue by checking whether launch-compose child report summaries should preserve stale artifact-index fields when operator packet generation is embedded in compose/preflight failure handling.
