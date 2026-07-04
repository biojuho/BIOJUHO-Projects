# AutoResearch Loop 2026-07-04 AgriGuard Index Recovery Command Status

## Objective

Add an explicit recovery-command status to artifact-index JSON and Markdown so automation can assert failed indexes include a recovery command while passing indexes do not require one.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_INDEX_RECOVERY_COMMAND_STATUS.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: artifact-index JSON includes a recovery command on failures, but automation must infer whether command presence is correct for the index status.
- Variant: add `recovery_command_status=not_required` for passing indexes, `pass` for failed indexes with a recovery command, and `fail` for failed indexes without one.
- Primary KPI: live failed and passing indexes report `pass` and `not_required` respectively, with Markdown rendering the same status.
- Guardrails: no README edits, no secret values, no launch execution changes, and no changes to index pass/fail criteria.

## Variant Evidence

- Focused artifact-index tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q`
  - Result: `5 passed in 1.01s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `65 passed in 3.43s`
- Live failed/passing index check:
  - Refreshed failed prefix `agriguard-guarded-launch-static-recovery-status` and passing prefix `agriguard-guarded-launch-wrapper-env-shape-readiness`.
  - Result: failed index reports `status=fail`, `recovery_command_status=pass`, `recovery_command` present; passing index reports `status=pass`, `recovery_command_status=not_required`, `recovery_command` absent.
- Live Markdown check:
  - `Select-String -Path var\agriguard-guarded-launch-static-recovery-status-artifact-index.md,var\agriguard-guarded-launch-wrapper-env-shape-readiness-artifact-index.md -Pattern 'Status|Recovery command status|Recovery command'`
  - Result: failed Markdown shows `Recovery command status: pass`; passing Markdown shows `Recovery command status: not_required` and `Recovery command: -`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-index-recovery-command-status.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `568 passed, 2 warnings`.

## Decision

Adopt the variant. Artifact-index consumers can now assert recovery-command health directly instead of inferring it from status and command presence.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Surface `recovery_command_status` through wrapper dry-run readiness summaries so command-health status is visible before opening the artifact index.
