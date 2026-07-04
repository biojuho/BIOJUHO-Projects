# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Ready Gate

## Objective

Add a fail-closed readiness gate to `run_guarded_launch.py` so automation can require a guarded-launch output prefix to be ready before treating compose launch evidence as passing.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_READY_GATE.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: `--status-only` prints a compact view, but automation must parse it and decide whether blocked evidence should fail a release gate.
- Variant: add `--require-ready`, which exits nonzero unless the selected prefix resolves to `status=ready` and `blocker_class=ready`.
- Primary KPI: existing blocked wrapper prefixes still print status JSON but exit nonzero under `--require-ready`.
- Guardrails: a passing launch report without a readiness-summary JSON is normalized to `ready`, because summaries are emitted on failed stages; normal launch delegation still returns the child exit code unless the ready gate detects inconsistent evidence.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `35 passed in 1.01s`
- Placeholder prefix ready gate:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-wrapper-placeholder --status-only --require-ready --status-json-out var\agriguard-guarded-launch-wrapper-placeholder-require-ready.json`
  - Expected result: exit code `1`, status JSON written with `status=blocked`, `blocker_class=env_shape_blocked`, launch stage `env_shape_validation`.
- Shape-safe fake-Firebase prefix ready gate:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-wrapper-filled --status-only --require-ready --status-json-out var\agriguard-guarded-launch-wrapper-filled-require-ready.json`
  - Expected result: exit code `1`, status JSON written with `status=blocked`, `blocker_class=preflight_blocked`, operator action id `set_firebase_service_account_file`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-require-ready.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `538 passed, 2 warnings`.

## Decision

Adopt the variant. Release scripts can now call the guarded-launch wrapper status view as a fail-closed gate without duplicating status parsing logic.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Expose the ready gate in a higher-level launch evidence handoff so the latest wrapper status, ready-gate result, and external blocker are visible in one operator artifact.
