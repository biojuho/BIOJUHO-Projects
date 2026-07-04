# AutoResearch Loop 2026-07-04 AgriGuard Dry Run Recovery Command Status

## Objective

Surface artifact-index `recovery_command_status` in guarded-launch dry-run readiness summaries so command-health status is visible without opening the index JSON or Markdown.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_DRY_RUN_RECOVERY_COMMAND_STATUS.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: dry-run readiness summaries show artifact-index status and readiness actions, but not the recovery-command status added to the index.
- Variant: copy `recovery_command_status` from artifact-index JSON into `artifact_index_readiness_summary`.
- Primary KPI: live dry-run against a passing prefix reports `recovery_command_status=not_required`; live dry-run against a missing prefix keeps status null and still carries the missing-index command.
- Guardrails: no README edits, no secret values, no launch execution changes, and no changes to delegated launch or evidence gates.

## Variant Evidence

- Focused wrapper dry-run tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: `15 passed in 0.68s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `65 passed in 2.40s`
- Live dry-run check:
  - Checked prefix `agriguard-guarded-launch-wrapper-env-shape-readiness` and fresh missing prefix `agriguard-guarded-launch-dry-run-recovery-status-missing`.
  - Result: passing prefix reports `found=true`, `recovery_command_status=not_required`; missing prefix reports `found=false`, null recovery status, and a present missing-index command.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dry-run-recovery-command-status.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `568 passed, 2 warnings`.

## Decision

Adopt the variant. Wrapper dry-run output now carries the same recovery-command health state as the artifact index when the index exists.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Mirror `recovery_command_status` into operator packet readiness summaries so packet, dry-run, and artifact-index surfaces stay aligned.
