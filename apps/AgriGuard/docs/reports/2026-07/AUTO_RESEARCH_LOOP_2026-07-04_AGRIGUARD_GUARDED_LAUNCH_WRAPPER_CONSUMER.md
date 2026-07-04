# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Wrapper Consumer

## Objective

Attach the compact guarded-launch handoff consumer output to the wrapper `--emit-handoff` path so one operator command produces detailed launch evidence and the minimal release-gate view.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_WRAPPER_CONSUMER.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: `--emit-handoff` writes detailed handoff and validation artifacts, but the compact consumer view still needs a separate command.
- Variant: make `run_guarded_launch.py --emit-handoff` also run `consume_guarded_launch_handoff.py` and write `<prefix>-handoff.consumer.json`.
- Primary KPI: one placeholder wrapper run emits a clean compact consumer view with `env_shape_blocked`; one shape-safe fake-Firebase run emits `preflight_blocked` with action id `set_firebase_service_account_file`.
- Guardrails: clean blocked consumer views do not mask the launch exit code; stale validation/hash errors still fail the wrapper; dry-run exposes both handoff and consumer commands.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `51 passed in 1.76s`
- Placeholder one-run consumer:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-wrapper-emit-consumer-placeholder --emit-handoff --status-json-out var\agriguard-guarded-launch-wrapper-emit-consumer-placeholder-status.json`
  - Expected result: exit code `1`, consumer status `fail`, `blocker_class=env_shape_blocked`, `validation_status=pass`, `validation_matches_handoff=true`, `errors=[]`.
- Shape-safe fake-Firebase one-run consumer:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-shape-validation-filled.env --output-prefix agriguard-guarded-launch-wrapper-emit-consumer-filled --emit-handoff --status-json-out var\agriguard-guarded-launch-wrapper-emit-consumer-filled-status.json`
  - Expected result: exit code `1`, consumer status `fail`, `blocker_class=preflight_blocked`, action id `set_firebase_service_account_file`, `validation_status=pass`, `validation_matches_handoff=true`, `errors=[]`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-wrapper-consumer.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `554 passed, 2 warnings`.

## Decision

Adopt the variant. The guarded-launch wrapper now produces both detailed operator handoff evidence and the compact release-gate consumer output in one run.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Surface the one-command guarded-launch wrapper in the operator packet safe rerun commands so blocked operators get the full evidence-producing command by default.
