# AutoResearch Loop 2026-07-04 AgriGuard Index Recovery Status Note

## Objective

Add a recovery-command note to artifact-index JSON and Markdown when an index fails and emits a recovery command.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_INDEX_RECOVERY_STATUS_NOTE.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: failed artifact indexes expose `recovery_command_status=pass` and a recovery command, but do not explain why the command is present.
- Variant: add `recovery_command_note` for failed indexes with a recovery command, and render it in Markdown; passing indexes keep the note null and render `-`.
- Primary KPI: live failed and passing indexes report the note only for the failed index.
- Guardrails: no README edits, no secret values, no launch execution changes, and no changes to index pass/fail criteria.

## Variant Evidence

- Focused artifact-index tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q`
  - Result: `5 passed in 0.44s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `67 passed in 2.50s`
- Live failed/passing index check:
  - Refreshed failed prefix `agriguard-guarded-launch-static-recovery-note` and passing prefix `agriguard-guarded-launch-wrapper-env-shape-readiness`.
  - Result: failed index reports `status=fail`, `recovery_command_status=pass`, `recovery_command_note=Recovery command is present because this artifact index did not meet pass criteria.`; passing index reports `status=pass`, `recovery_command_status=not_required`, and null recovery note.
- Live Markdown check:
  - `Select-String -Path var\agriguard-guarded-launch-static-recovery-note-artifact-index.md,var\agriguard-guarded-launch-wrapper-env-shape-readiness-artifact-index.md -Pattern 'Status|Recovery command status|Recovery command note|Recovery command'`
  - Result: failed Markdown shows the recovery-command note; passing Markdown shows `Recovery command note: -`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-index-recovery-note.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `570 passed, 2 warnings`.

## Decision

Adopt the variant. Static artifact-index evidence now explains recovery-command presence on failed indexes while keeping passing indexes clean.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a machine-readable recovery-summary object that groups recovery action, status, note, and command for downstream consumers.
