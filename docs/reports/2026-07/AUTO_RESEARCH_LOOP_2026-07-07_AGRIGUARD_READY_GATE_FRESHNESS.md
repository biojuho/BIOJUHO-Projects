# AutoResearch Loop: AgriGuard Ready-Gate Freshness

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch artifact index and handoff readiness evidence
- Owned code paths:
  - `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
  - `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_READY_GATE_FRESHNESS.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READY_GATE_FRESHNESS_2026-07-07.md`

## Objective

Continue AgriGuard launch hardening with a source-backed, fail-closed AutoResearch cycle. The specific target was stale machine-readable ready-gate evidence: the artifact index was allowed to pass while `ready_gate_json` existed but was older than the current handoff consumer artifact.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- Latest commit refresh: 8 GitHub HEAD refs checked; updated=6, failed=0, review_required=6.
- Relevant adopted pattern: `Veritas-7/autoresearch-skill-system` continuous mode keeps machine-readable status, durable archives, and fail-closed completion audits. Latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## A/B Hypothesis

- Baseline: keep the existing artifact index behavior, where any existing `ready_gate_json` only needs a non-empty `generated_at`.
- Variant: if `ready_gate_json` exists, require its `generated_at` to be at least as fresh as `handoff_consumer_json`.
- Primary KPI: stale ready-gate evidence is detected as `status=fail` before an operator trusts the index.
- Guardrails: fresh or absent optional ready-gate artifacts must not break valid indexes; existing command metadata and recovery command checks must remain intact.
- Decision rule: adopt the variant only if the stale live artifact set fails before refresh, passes after the ready-gate command refreshes it, and all targeted and canonical AgriGuard tests pass.

## Baseline Evidence

Pre-patch live inspection showed the gap:

- `var/agriguard-guarded-launch-artifact-index.json`: `status=pass`, `blocker_class=ready`
- `handoff_consumer_json.generated_at`: `2026-07-06T15:20:59Z`
- `ready_gate_json.generated_at`: `2026-07-06T12:52:04Z`
- The index did not expose a stale generated-at role, so stale ready-gate evidence could remain inside a ready artifact index.

## Variant Evidence

Implemented generated-at ordering in the artifact index:

- Added `GENERATED_AT_ORDER_RULES` for `ready_gate_json -> handoff_consumer_json`.
- Added stale timestamp parsing and `stale_generated_at_details`.
- Added `stale_generated_at_roles` to JSON and Markdown output.
- Included `stale_generated_at_roles` in index pass/fail criteria.
- Added a regression where stale `ready_gate_json` fails with `blocker_class=artifact_index_blocked`.

Live pre-refresh proof after the patch:

- Command: `python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-artifact-index-ready-gate-freshness-before-refresh-2026-07-07.json --markdown-out var\agriguard-guarded-launch-artifact-index-ready-gate-freshness-before-refresh-2026-07-07.md --exit-zero-on-fail`
- Result: `status=fail`, `blocker_class=artifact_index_blocked`
- `stale_generated_at_roles`: `["ready_gate_json"]`
- `ready_gate_json.generated_at`: `2026-07-06T12:52:04Z`
- `handoff_consumer_json.generated_at`: `2026-07-06T15:20:59Z`
- `recovery_command_status`: `pass`

Ready-gate refresh proof:

- Command: `python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate.json`
- Result: exit code `1`, expected because real Firebase Admin credentials are not present.
- Refreshed `ready_gate_json.generated_at`: `2026-07-06T15:31:46Z`
- Status remained `blocked`, `blocker_class=preflight_blocked`.

Post-refresh index proof:

- Command: `python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-artifact-index.json --markdown-out var\agriguard-guarded-launch-artifact-index.md`
- Result: `status=pass`, `blocker_class=ready`
- `stale_generated_at_roles`: `[]`
- `missing_generated_at_roles`: `[]`
- `consumer_command_metadata_status`: `pass`

## Verification Commands

- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q`
  - Result: 13 passed
- `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: 57 passed
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-ready-gate-freshness-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READY_GATE_FRESHNESS_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-ready-gate-freshness.json`
  - Result: `status=complete`, passed=5, failed=0, total=5

## Decision

Adopted. The variant fixes a real stale-evidence gap, fails closed on the live stale artifact set, recovers after the existing ready-gate command refreshes the artifact, and keeps the canonical AgriGuard smoke green.

## Remaining Blocker

Launch is still externally blocked by the missing real Firebase Admin service account JSON referenced by the local operator env path. The local guarded-launch and artifact-index evidence now classifies and preserves that blocker instead of presenting stale ready-gate evidence as current.

## Next Cycle

Continue launch hardening around the next real mismatch in the guarded-launch evidence chain. A likely next check is whether the ready-gate status JSON should expose the exact operator action and credential path summary in the compact status view without leaking secrets.
