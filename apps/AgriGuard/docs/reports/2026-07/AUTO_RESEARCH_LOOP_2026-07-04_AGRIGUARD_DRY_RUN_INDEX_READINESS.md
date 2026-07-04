# AutoResearch Loop 2026-07-04 AgriGuard Dry Run Index Readiness

## Objective

Expose the indexed guarded-launch readiness action summary in wrapper dry-run output so operators can see the next env-shape repair step without opening the full artifact index.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_DRY_RUN_INDEX_READINESS.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: `run_guarded_launch.py --dry-run --emit-handoff` shows the planned commands and artifact paths, but operators still need to open the artifact-index JSON or Markdown to see the indexed readiness action summary.
- Variant: dry-run output reads the selected prefix's artifact-index JSON when present and emits `artifact_index_readiness_summary` with action IDs, env readiness, placeholder count, packet preflight status, and packet-validation status.
- Primary KPI: live dry-run against the env-shape readiness prefix reports `operator_action_ids=["fix_env_shape_validation"]`, env validation readiness `false`, placeholder count `6`, and packet preflight status `env_shape_blocked`.
- Guardrails: no README edits, no secret values, no launch execution changes, no changes to fail-closed launch or evidence gates.

## Variant Evidence

- Focused wrapper dry-run tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q`
  - Result: `14 passed in 0.69s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `62 passed in 2.61s`
- Live dry-run check:
  - `$json = python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-wrapper-env-shape-readiness --emit-handoff --dry-run | ConvertFrom-Json`
  - Result: `artifact_index_readiness_summary.found=true`, `status=pass`, `consumer_packet_validation_status=pass`, `operator_action_ids=["fix_env_shape_validation"]`, `env_validation_ready_for_preflight=false`, `env_validation_placeholder_count=6`, `operator_packet_preflight_status=env_shape_blocked`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dry-run-index-readiness.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `565 passed, 2 warnings`.

## Decision

Adopt the variant. The wrapper dry-run plan now surfaces the indexed readiness action status for the selected guarded-launch prefix while preserving launch execution and fail-closed evidence behavior.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Mirror the artifact-index readiness summary into the operator packet guarded-launch evidence section so the saved packet and the wrapper dry-run expose the same compact repair status.
