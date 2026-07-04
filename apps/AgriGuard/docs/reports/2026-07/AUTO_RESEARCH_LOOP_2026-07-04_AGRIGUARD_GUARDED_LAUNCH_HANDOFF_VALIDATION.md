# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Handoff Validation

## Objective

Add schema validation for the guarded-launch handoff so downstream automation can fail closed on shape drift before trusting handoff status, ready-gate, or blocker fields.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/scripts/validate_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_HANDOFF_VALIDATION.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: guarded-launch handoff JSON is useful, but downstream automation has no checked-in shape contract.
- Variant: add a JSON Schema subset plus `validate_guarded_launch_handoff.py`, producing a validation report with handoff and schema SHA-256 hashes.
- Primary KPI: live filled and placeholder handoff artifacts both validate with `status=pass`, and intentional shape drift fails in tests.
- Guardrails: validator reads only JSON artifacts, does not expose secrets, and exits with a dedicated validation failure code on malformed or schema-drifting handoffs.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `42 passed in 1.30s`
- Filled-prefix live validation:
  - `python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-guarded-launch-wrapper-filled-handoff.json --json-out var\agriguard-guarded-launch-wrapper-filled-handoff.validation.json`
  - Expected result: exit code `0`, validation `status=pass`, `errors=[]`, handoff and schema hashes present.
- Placeholder-prefix live validation:
  - `python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-guarded-launch-wrapper-placeholder-handoff.json --json-out var\agriguard-guarded-launch-wrapper-placeholder-handoff.validation.json`
  - Expected result: exit code `0`, validation `status=pass`, `errors=[]`, handoff and schema hashes present.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-handoff-validation.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `545 passed, 2 warnings`.

## Decision

Adopt the variant. The guarded-launch handoff now has a checked-in schema and a fail-closed validator suitable for downstream automation.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Integrate handoff validation into the handoff renderer so generated handoff artifacts can include or point to their validation report automatically.
