# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Wrapper Handoff

## Objective

Wire guarded-launch handoff generation into `run_guarded_launch.py` so one operator run can emit launch status, handoff, ready-gate, and handoff-validation artifacts.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_WRAPPER_HANDOFF.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: operators must run the guarded launch and then separately render/validate the handoff for the same output prefix.
- Variant: add `--emit-handoff` and explicit handoff output flags to `run_guarded_launch.py`; after the delegated launch, the wrapper runs the handoff renderer with `--exit-zero-on-blocked` so blocked handoffs do not mask the launch exit code, while validation failures still fail the wrapper.
- Primary KPI: one placeholder run emits status, handoff, ready-gate, and validation artifacts with `env_shape_blocked`; one shape-safe fake-Firebase run emits the same artifact set with `preflight_blocked` and action id `set_firebase_service_account_file`.
- Guardrails: wrapper still preserves launch failure exit code, handoff validation failure returns nonzero, and dry-run exposes the handoff command before execution.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `45 passed in 1.54s`
- Placeholder one-run handoff:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-wrapper-emit-handoff-placeholder --emit-handoff --status-json-out var\agriguard-guarded-launch-wrapper-emit-handoff-placeholder-status.json`
  - Expected result: exit code `1`, status `blocked`, `blocker_class=env_shape_blocked`, handoff `status=blocked`, ready gate `fail`, validation `pass`, launch stage `env_shape_validation`.
- Shape-safe fake-Firebase one-run handoff:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-shape-validation-filled.env --output-prefix agriguard-guarded-launch-wrapper-emit-handoff-filled --emit-handoff --status-json-out var\agriguard-guarded-launch-wrapper-emit-handoff-filled-status.json`
  - Expected result: exit code `1`, status `blocked`, `blocker_class=preflight_blocked`, action id `set_firebase_service_account_file`, handoff ready gate `fail`, validation `pass`, launch stage `preflight`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-wrapper-handoff.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `548 passed, 2 warnings`.

## Decision

Adopt the variant. The guarded-launch wrapper can now produce the complete operator evidence chain for a launch attempt in one command.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a release-facing consumer that reads the wrapper handoff plus validation report and emits a minimal pass/fail view for higher-level gates.
