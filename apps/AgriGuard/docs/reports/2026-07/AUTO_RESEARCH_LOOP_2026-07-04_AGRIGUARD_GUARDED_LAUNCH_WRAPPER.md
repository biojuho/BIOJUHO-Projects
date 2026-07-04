# AutoResearch Loop 2026-07-04 AgriGuard Guarded Launch Wrapper

## Objective

Add an operator-facing wrapper command that runs the canonical guarded compose launch with env-shape validation, strict preflight, operator-packet output, readiness-summary output, and browser smoke wired to stable artifact paths.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_GUARDED_LAUNCH_WRAPPER.md`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: operators must manually assemble a long `launch_compose.py` command to combine env-shape validation, packet output, readiness summary, and browser smoke.
- Variant: add `run_guarded_launch.py` as a thin wrapper with stable artifact names and expose it as the second safe rerun command in the operator packet, immediately after env-template validation.
- Primary KPI: wrapper dry-run emits the complete delegated command; placeholder env exits with `env_shape_blocked`; shape-safe fake-Firebase env exits with `preflight_blocked` and action id `set_firebase_service_account_file`.
- Guardrails: wrapper does not reinterpret launch results, returns the delegated exit code, supports browser-smoke opt-out only by explicit flag, and keeps lower-level preflight/launch commands available for diagnostics.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q`
  - Result: `29 passed in 0.97s`
- Wrapper dry-run:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-wrapper-placeholder --dry-run`
  - Expected result: exit code `0`, delegated command includes `launch_compose.py`, `--validate-env-file-shape`, readiness-summary outputs, operator-packet outputs, and `--run-browser-smoke`.
- Placeholder wrapper run:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-wrapper-placeholder`
  - Expected result: exit code `1`, `stage=env_shape_validation`, results `env_validation,readiness_summary`, attached `blocker_class=env_shape_blocked`.
- Shape-safe fake-Firebase wrapper run:
  - `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-shape-validation-filled.env --output-prefix agriguard-guarded-launch-wrapper-filled`
  - Expected result: exit code `1`, `stage=preflight`, results `env_validation,preflight,operator_packet,readiness_summary`, attached `blocker_class=preflight_blocked`, operator action id `set_firebase_service_account_file`.
- Live packet refresh:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-guarded-launch-wrapper-filled-preflight.json --json-out var\agriguard-guarded-launch-wrapper-filled-operator-packet-refreshed.json --markdown-out var\agriguard-guarded-launch-wrapper-filled-operator-packet-refreshed.md --env-template-out var\agriguard-guarded-launch-wrapper-filled-refreshed.env.template`
  - Expected result: exit code `1`, packet status `blocked`, safe rerun commands include `validate_launch_env_template.py` followed by `run_guarded_launch.py`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-guarded-launch-wrapper.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `532 passed, 2 warnings`.

## Decision

Adopt the variant. Operators now get a single guarded retry command from the packet, while agents and diagnostics can still call the lower-level validator, preflight, or compose launcher directly.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until the operator supplies a real Firebase Admin service-account JSON outside the repo plus production-strength secret, pepper, public verify URL, allowed origins, and database credentials.

## Next Cycle

Add a compact wrapper status view that reads a guarded-launch output prefix and prints the latest launch stage, blocker class, and operator action IDs without requiring operators to inspect multiple JSON files.
