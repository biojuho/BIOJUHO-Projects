# AutoResearch Loop 2026-07-04 AgriGuard Status Readiness Action

## Objective

Add compact readiness action fields to `run_guarded_launch.py --status-only` so operators can see env-shape repair status without opening readiness JSON.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_STATUS_READINESS_ACTION.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: status-only includes top-level action IDs and readiness next actions, but not the compact env validation fields added to readiness Markdown.
- Variant: add readiness-summary action IDs, env readiness, placeholder count, and operator packet preflight status to the status-only JSON and handoff schema.
- Primary KPI: live status-only view reports `operator_action_ids=fix_env_shape_validation`, `env_validation_ready_for_preflight=false`, `env_validation_placeholder_count=6`, and `operator_packet_preflight_status=env_shape_blocked`.
- Guardrails: no README edits, no secret values, no launch execution changes, no schema weakening.

## Variant Evidence

- Focused wrapper/handoff schema tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py -q`
  - Result: `21 passed in 1.45s`
- Guarded-launch packet suite:
  - `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `62 passed in 3.02s`
- Live status-only check:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-wrapper-env-shape-readiness --status-only`
  - Result: exit code `0`, `status=blocked`, `blocker_class=env_shape_blocked`, top-level `operator_action_ids=["fix_env_shape_validation"]`, readiness `operator_action_ids=["fix_env_shape_validation"]`, `env_validation_ready_for_preflight=false`, `env_validation_placeholder_count=6`, `operator_packet_preflight_status=env_shape_blocked`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-readiness-action.json`
  - Result: `status=complete`, `total=5`, `passed=5`, `failed=0`; backend subcheck reported `565 passed, 2 warnings`.

## Decision

Adopt the variant. The status-only view now exposes the same compact env-shape repair signal as readiness Markdown and remains schema-compatible for guarded-launch handoffs.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add these status-only readiness fields to the handoff Markdown packet-validation section so the human handoff mirrors the compact status JSON.
