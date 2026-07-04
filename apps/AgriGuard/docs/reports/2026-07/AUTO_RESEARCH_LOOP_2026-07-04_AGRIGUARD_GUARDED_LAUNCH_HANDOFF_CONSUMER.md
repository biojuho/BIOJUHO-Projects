# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Handoff Consumer

## Objective

Add a release-facing consumer for guarded-launch handoff artifacts that emits a minimal pass/fail view after verifying the handoff validation report still matches the current handoff hash.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_HANDOFF_CONSUMER.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: higher-level gates can read the handoff and validation report, but must duplicate hash, validation, ready-gate, and blocker parsing logic.
- Variant: add `consume_guarded_launch_handoff.py`, which revalidates the current handoff shape, checks validation status, verifies `handoff_sha256`, and emits a compact pass/fail view.
- Primary KPI: current filled and placeholder handoffs both fail closed with `validation_matches_handoff=true`, no consumer errors, and their respective blocker classes.
- Guardrails: ready handoffs must have `handoff_status=ready` and `ready_gate_status=pass`; stale validation hashes fail even if the handoff still has valid JSON shape.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `49 passed in 1.80s`
- Filled-prefix live consumer:
  - `python apps/AgriGuard/scripts/consume_guarded_launch_handoff.py var\agriguard-guarded-launch-wrapper-emit-handoff-filled-handoff.json --validation-json var\agriguard-guarded-launch-wrapper-emit-handoff-filled-handoff.validation.json --json-out var\agriguard-guarded-launch-wrapper-emit-handoff-filled-consumer.json`
  - Expected result: exit code `1`, compact status `fail`, `handoff_status=blocked`, `ready_gate_status=fail`, `blocker_class=preflight_blocked`, action id `set_firebase_service_account_file`, `validation_status=pass`, `validation_matches_handoff=true`, `errors=[]`.
- Placeholder-prefix live consumer:
  - `python apps/AgriGuard/scripts/consume_guarded_launch_handoff.py var\agriguard-guarded-launch-wrapper-emit-handoff-placeholder-handoff.json --validation-json var\agriguard-guarded-launch-wrapper-emit-handoff-placeholder-handoff.validation.json --json-out var\agriguard-guarded-launch-wrapper-emit-handoff-placeholder-consumer.json`
  - Expected result: exit code `1`, compact status `fail`, `handoff_status=blocked`, `ready_gate_status=fail`, `blocker_class=env_shape_blocked`, `validation_status=pass`, `validation_matches_handoff=true`, `errors=[]`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-handoff-consumer.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `552 passed, 2 warnings`.

## Decision

Adopt the variant. Higher-level release gates can now consume one compact guarded-launch handoff view without reimplementing handoff validation and blocker parsing.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Attach the compact guarded-launch handoff consumer output to the wrapper `--emit-handoff` path so one operator command can produce both the detailed handoff and the minimal release-gate view.
