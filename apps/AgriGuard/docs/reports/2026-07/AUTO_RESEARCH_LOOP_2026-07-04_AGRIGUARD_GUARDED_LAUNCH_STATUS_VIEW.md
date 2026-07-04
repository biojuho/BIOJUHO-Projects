# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Status View

## Objective

Add a compact status view to `run_guarded_launch.py` so operators can inspect a guarded-launch output prefix without opening the launch report, readiness summary, and operator packet separately.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_STATUS_VIEW.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: after a guarded launch, operators must inspect several JSON files to find the latest stage, blocker class, and action IDs.
- Variant: add `--status-only` for read-only prefix inspection and `--status-json-out` for writing the same compact view after a delegated launch run.
- Primary KPI: existing placeholder and shape-safe fake-Firebase prefixes classify as `env_shape_blocked` and `preflight_blocked`, respectively, with the filled-prefix Firebase action ID preserved.
- Guardrails: status view is read-only unless an explicit `--status-json-out` path is provided, secrets remain omitted, and normal wrapper launch delegation still returns the child exit code.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `32 passed in 1.04s`
- Placeholder prefix status view:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-wrapper-placeholder --status-only --status-json-out var\agriguard-guarded-launch-wrapper-placeholder-status.json`
  - Expected result: exit code `0`, `status=blocked`, `blocker_class=env_shape_blocked`, launch stage `env_shape_validation`, results `env_validation,readiness_summary`.
- Shape-safe fake-Firebase prefix status view:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-wrapper-filled --status-only --status-json-out var\agriguard-guarded-launch-wrapper-filled-status.json`
  - Expected result: exit code `0`, `status=blocked`, `blocker_class=preflight_blocked`, launch stage `preflight`, operator action id `set_firebase_service_account_file`.
- Post-run status JSON:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-wrapper-status-after-run-placeholder --status-json-out var\agriguard-guarded-launch-wrapper-status-after-run-placeholder-status.json`
  - Expected result: exit code `1`, status JSON written with `status=blocked`, `blocker_class=env_shape_blocked`, launch stage `env_shape_validation`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-status-view.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `535 passed, 2 warnings`.

## Decision

Adopt the variant. The guarded-launch wrapper now has a compact read-only status view for operator triage and can emit the same status JSON after a delegated launch attempt.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a fail-closed status gate for automation that can require a guarded-launch prefix to be `ready` before release scripts treat compose launch evidence as passing.
