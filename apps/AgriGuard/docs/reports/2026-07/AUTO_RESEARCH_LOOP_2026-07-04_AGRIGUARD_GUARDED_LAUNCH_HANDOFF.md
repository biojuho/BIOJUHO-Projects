# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Handoff

## Objective

Expose the guarded-launch status view and ready-gate result in one operator handoff artifact, including the current external blocker and safe operator commands.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_HANDOFF.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: operators can run `run_guarded_launch.py --status-only --require-ready`, but the status, gate, external blocker, and commands are not captured together.
- Variant: add `render_guarded_launch_handoff.py` to write JSON/Markdown with `status_view`, `ready_gate`, `external_blocker`, and operator command argv entries.
- Primary KPI: filled fake-Firebase prefix emits a handoff with `ready_gate=fail`, `blocker_class=preflight_blocked`, and action id `set_firebase_service_account_file`; placeholder prefix emits `env_shape_blocked`.
- Guardrails: secrets remain omitted, blocked handoffs exit nonzero by default, and the ready-gate command is preserved as argv rather than an interpolated shell string.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `38 passed in 1.80s`
- Filled-prefix live handoff:
  - `python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --output-prefix agriguard-guarded-launch-wrapper-filled --ready-gate-json var\agriguard-guarded-launch-wrapper-filled-ready-gate-from-handoff.json --json-out var\agriguard-guarded-launch-wrapper-filled-handoff.json --markdown-out var\agriguard-guarded-launch-wrapper-filled-handoff.md`
  - Expected result: exit code `1`, `status=blocked`, `ready_gate.status=fail`, `ready_gate.exit_code=1`, `blocker_class=preflight_blocked`, action id `set_firebase_service_account_file`, launch stage `preflight`.
- Placeholder-prefix live handoff:
  - `python apps/AgriGuard/scripts/render_guarded_launch_handoff.py --output-prefix agriguard-guarded-launch-wrapper-placeholder --ready-gate-json var\agriguard-guarded-launch-wrapper-placeholder-ready-gate-from-handoff.json --json-out var\agriguard-guarded-launch-wrapper-placeholder-handoff.json --markdown-out var\agriguard-guarded-launch-wrapper-placeholder-handoff.md`
  - Expected result: exit code `1`, `status=blocked`, `ready_gate.status=fail`, `blocker_class=env_shape_blocked`, launch stage `env_shape_validation`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-handoff.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `541 passed, 2 warnings`.

## Decision

Adopt the variant. Operators and release automation can now consume one handoff artifact for the selected guarded-launch prefix instead of manually correlating the status view, ready gate, and operator packet.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add schema validation for the guarded-launch handoff so downstream automation can fail closed on shape drift before trusting handoff fields.
