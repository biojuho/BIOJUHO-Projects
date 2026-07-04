# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Handoff Auto Validation

## Objective

Integrate guarded-launch handoff validation into the handoff renderer so generated handoff artifacts automatically point to and produce their validation report.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_HANDOFF_AUTO_VALIDATION.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the validator exists, but operators must run it separately and manually associate the validation report with the handoff.
- Variant: `render_guarded_launch_handoff.py` embeds a validation pointer/command and writes the validation report by default after rendering.
- Primary KPI: live filled and placeholder handoffs remain blocked as expected, while their auto-written validation reports pass and are referenced from the handoff JSON.
- Guardrails: validation failure exits with the validator failure code, blocked handoffs still exit nonzero after validation passes, and `--skip-validation` remains available only for diagnostics.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `42 passed in 1.29s`
- Filled-prefix live handoff render:
  - `python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --output-prefix agriguard-guarded-launch-wrapper-filled --ready-gate-json var\agriguard-guarded-launch-wrapper-filled-ready-gate-from-handoff.json --json-out var\agriguard-guarded-launch-wrapper-filled-handoff.json --markdown-out var\agriguard-guarded-launch-wrapper-filled-handoff.md --validation-json-out var\agriguard-guarded-launch-wrapper-filled-handoff.validation.json`
  - Expected result: exit code `1`, handoff `status=blocked`, ready gate `fail`, validation `status=pass`, validation pointer present.
- Placeholder-prefix live handoff render:
  - `python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --output-prefix agriguard-guarded-launch-wrapper-placeholder --ready-gate-json var\agriguard-guarded-launch-wrapper-placeholder-ready-gate-from-handoff.json --json-out var\agriguard-guarded-launch-wrapper-placeholder-handoff.json --markdown-out var\agriguard-guarded-launch-wrapper-placeholder-handoff.md --validation-json-out var\agriguard-guarded-launch-wrapper-placeholder-handoff.validation.json`
  - Expected result: exit code `1`, handoff `status=blocked`, ready gate `fail`, validation `status=pass`, validation pointer present.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-handoff-auto-validation.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `545 passed, 2 warnings`.

## Decision

Adopt the variant. The handoff renderer now emits a self-describing, schema-validated handoff artifact by default.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Wire the guarded-launch handoff into a single wrapper command so a launch attempt can optionally emit status, handoff, and handoff validation artifacts in one operator run.
