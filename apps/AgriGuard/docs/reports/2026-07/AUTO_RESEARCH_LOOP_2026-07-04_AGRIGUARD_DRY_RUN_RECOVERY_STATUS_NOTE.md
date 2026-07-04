# AutoResearch Loop 2026-07-04 AgriGuard Dry Run Recovery Status Note

## Objective

Add the deferred artifact-index recovery-status note to guarded-launch dry-run readiness summaries.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_DRY_RUN_RECOVERY_STATUS_NOTE.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: wrapper dry-run readiness summaries report null `recovery_command_status` for a missing selected artifact index, but do not explain why the status is unavailable.
- Variant: add `recovery_command_note` with the same deferred-status explanation used by the operator packet and handoff surfaces.
- Primary KPI: live dry-run with a fresh prefix reports `found=false`, null recovery status, the explanatory note, and a missing-index command that excludes `--dry-run`.
- Guardrails: no README edits, no secret values, no launch execution changes, and no changes to delegated launch or evidence gates.

## Variant Evidence

- Focused wrapper dry-run tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: `15 passed in 0.65s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `67 passed in 2.86s`
- Live dry-run check:
  - `$json = python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-dry-run-recovery-note --emit-handoff --dry-run | ConvertFrom-Json`
  - Result: `artifact_index_readiness_summary.found=false`, `recovery_command_status=null`, `recovery_command_note=Artifact index recovery status is resolved after the guarded wrapper emits the artifact index.`, missing-index command present, and `--dry-run` absent from that command.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dry-run-recovery-note.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `570 passed, 2 warnings`.

## Decision

Adopt the variant. Wrapper dry-run output now explains deferred artifact-index recovery status consistently with the packet and handoff surfaces.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add `recovery_command_note` to artifact-index JSON/Markdown when a failed index carries a recovery command, so static evidence also explains the command-health state.
