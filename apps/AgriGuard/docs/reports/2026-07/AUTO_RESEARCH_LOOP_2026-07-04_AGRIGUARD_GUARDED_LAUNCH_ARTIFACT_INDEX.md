# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Artifact Index

## Objective

Add a compact artifact index for guarded-launch output prefixes so operators can verify status, launch, handoff, validation, consumer, packet, and env-validation artifacts from one JSON.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_ARTIFACT_INDEX.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: after one guarded wrapper run, operators still need to list files manually to confirm which artifacts were produced for the blocker stage.
- Variant: add `index_guarded_launch_artifacts.py`, which records existence, size, and SHA-256 for expected prefix artifacts and fails if required handoff, validation, consumer, launch, or explicitly requested status artifacts are missing.
- Primary KPI: live filled and placeholder one-run prefixes both index with `status=pass`, no missing required roles, and correct blocker/stage metadata.
- Guardrails: optional artifacts remain visible but do not fail stages where they are not expected, such as preflight/operator-packet files after env-shape validation stops early.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `55 passed in 1.88s`
- Filled-prefix live index:
  - `python apps/AgriGuard/scripts/index_guarded_launch_artifacts.py --output-prefix agriguard-guarded-launch-wrapper-emit-consumer-filled --status-json var\agriguard-guarded-launch-wrapper-emit-consumer-filled-status.json --json-out var\agriguard-guarded-launch-wrapper-emit-consumer-filled-artifact-index.json`
  - Expected result: exit code `0`, index `status=pass`, `missing_required_roles=[]`, `consumer_blocker_class=preflight_blocked`, `launch_stage=preflight`, validation `pass`.
- Placeholder-prefix live index:
  - `python apps/AgriGuard/scripts/index_guarded_launch_artifacts.py --output-prefix agriguard-guarded-launch-wrapper-emit-consumer-placeholder --status-json var\agriguard-guarded-launch-wrapper-emit-consumer-placeholder-status.json --json-out var\agriguard-guarded-launch-wrapper-emit-consumer-placeholder-artifact-index.json`
  - Expected result: exit code `0`, index `status=pass`, `missing_required_roles=[]`, `consumer_blocker_class=env_shape_blocked`, `launch_stage=env_shape_validation`, validation `pass`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-artifact-index.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `558 passed, 2 warnings`.

## Decision

Adopt the variant. A guarded-launch retry now has a compact artifact inventory for both complete evidence and stage-specific missing optional outputs.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Attach the artifact index to the wrapper `--emit-handoff` path so one operator command also writes the inventory for the generated evidence set.
