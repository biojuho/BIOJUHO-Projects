# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Wrapper Index

## Objective

Attach the guarded-launch artifact index to the wrapper `--emit-handoff` path so one operator run writes the detailed handoff, compact consumer view, and artifact inventory.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_WRAPPER_INDEX.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the artifact index exists but still needs a separate command after `run_guarded_launch.py --emit-handoff`.
- Variant: make the wrapper run `index_guarded_launch_artifacts.py` after handoff validation and compact consumer generation.
- Primary KPI: one placeholder and one shape-safe fake-Firebase wrapper run each produce passing artifact indexes with no missing required roles and correct blocker classes.
- Guardrails: artifact-index failure propagates through the wrapper, optional stage-specific artifacts stay optional, and launch failure remains the final exit code when evidence generation succeeds.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `56 passed in 2.05s`
- Placeholder one-run index:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-wrapper-emit-index-placeholder --emit-handoff --status-json-out var\agriguard-guarded-launch-wrapper-emit-index-placeholder-status.json`
  - Expected result: exit code `1`, artifact index `status=pass`, `missing_required_roles=[]`, `consumer_blocker_class=env_shape_blocked`, launch stage `env_shape_validation`.
- Shape-safe fake-Firebase one-run index:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-shape-validation-filled.env --output-prefix agriguard-guarded-launch-wrapper-emit-index-filled --emit-handoff --status-json-out var\agriguard-guarded-launch-wrapper-emit-index-filled-status.json`
  - Expected result: exit code `1`, artifact index `status=pass`, `missing_required_roles=[]`, `consumer_blocker_class=preflight_blocked`, launch stage `preflight`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-wrapper-index.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `559 passed, 2 warnings`.

## Decision

Adopt the variant. The one-command guarded-launch retry now emits the complete operator evidence set and its artifact inventory.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a small README or packet note for the artifact index role without disturbing unrelated README edits.
