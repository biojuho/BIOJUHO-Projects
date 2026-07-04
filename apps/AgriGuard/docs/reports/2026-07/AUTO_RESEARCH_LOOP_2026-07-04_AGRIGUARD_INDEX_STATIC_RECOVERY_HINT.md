# AutoResearch Loop 2026-07-04 AgriGuard Index Static Recovery Hint

## Objective

Add a recovery action and wrapper command to artifact-index JSON and Markdown when required guarded-launch evidence is missing or packet validation drifts.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_INDEX_STATIC_RECOVERY_HINT.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: failed artifact-index Markdown identifies missing roles and validation drift, but does not name the wrapper command that regenerates the evidence set.
- Variant: failed indexes include `recovery_action` and `recovery_command`; passing indexes keep those fields null and render `Recovery command: -`.
- Primary KPI: a live partial index with a fresh prefix renders the guarded wrapper command with `--emit-handoff`, the selected output prefix, and no `--dry-run`.
- Guardrails: no README edits, no secret values, no launch execution changes, and no weakening of index pass/fail criteria.

## Variant Evidence

- Focused artifact-index tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q`
  - Result: `5 passed in 0.46s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `65 passed in 2.43s`
- Live partial index:
  - `python apps/AgriGuard/scripts/index_guarded_launch_artifacts.py --output-prefix agriguard-guarded-launch-static-recovery-hint --json-out var\agriguard-guarded-launch-static-recovery-hint-artifact-index.json --markdown-out var\agriguard-guarded-launch-static-recovery-hint-artifact-index.md --exit-zero-on-fail`
  - Result: `status=fail`, missing required roles are `launch_report_json`, `handoff_json`, `handoff_markdown`, `handoff_validation_json`, and `handoff_consumer_json`; recovery command includes `--emit-handoff`, omits `--dry-run`, and preserves prefix `agriguard-guarded-launch-static-recovery-hint`.
- Live Markdown check:
  - `Select-String -Path var\agriguard-guarded-launch-static-recovery-hint-artifact-index.md -Pattern 'Status|Missing required roles|Recovery action|Recovery command'`
  - Result: Markdown shows `Status: fail`, missing required roles, the recovery action, and the guarded wrapper command.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-index-static-recovery-hint.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `568 passed, 2 warnings`.

## Decision

Adopt the variant. Failed artifact-index evidence is now self-recovering: the static Markdown names the wrapper command needed to regenerate the guarded-launch evidence set.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a recovery-command status check to the artifact-index JSON so automation can assert the recovery command is present on failures and absent on passes.
