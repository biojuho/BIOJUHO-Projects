# AutoResearch Loop 2026-07-04 AgriGuard Launch Compose Env Shape Guard

## Objective

Add an optional `launch_compose.py` guard that validates a supplied operator env file before strict launch preflight. The default no-env launch path remains unchanged.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: operators can run `launch_compose.py --env-file ...`, but strict preflight is the first fail-closed gate.
- Variant: add `--validate-env-file-shape`, requiring exactly one `--env-file`, and stop before strict preflight when the shape validator fails.
- Primary KPI: placeholder env stops at `env_shape_validation`; shape-safe env advances to strict preflight.
- Guardrails: default launch command remains unchanged, failed validation never runs preflight or compose, canonical AgriGuard smoke remains green.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q`
  - Result: `23 passed in 0.73s`
- Guarded placeholder launch:
  - `python apps/AgriGuard/scripts/launch_compose.py --env-file var\agriguard-launch-operator.env.template --validate-env-file-shape --env-validation-json-out var\agriguard-launch-compose-guard-placeholder-validation.json --env-validation-markdown-out var\agriguard-launch-compose-guard-placeholder-validation.md --json-out var\agriguard-launch-compose-guard-placeholder-preflight.json --launch-report-json var\agriguard-compose-launch-guard-placeholder-report.json --run-browser-smoke`
  - Expected result: exit code `1`, `stage=env_shape_validation`, `stop_reason=env_shape_validation_failed`, results only `env_validation`, strict preflight not run.
- Guarded shape-safe launch:
  - `python apps/AgriGuard/scripts/launch_compose.py --env-file var\agriguard-launch-shape-validation-filled.env --validate-env-file-shape --env-validation-json-out var\agriguard-launch-compose-guard-filled-validation.json --env-validation-markdown-out var\agriguard-launch-compose-guard-filled-validation.md --json-out var\agriguard-launch-compose-guard-filled-preflight.json --launch-report-json var\agriguard-compose-launch-guard-filled-report.json --operator-packet-json var\agriguard-launch-compose-guard-filled-packet.json --operator-packet-markdown var\agriguard-launch-compose-guard-filled-packet.md --operator-env-template var\agriguard-launch-compose-guard-filled.env.template --run-browser-smoke`
  - Expected result: exit code `1`, `env_validation.ready_for_preflight=true`, strict preflight ran, Docker checks passed, preflight failed only on fake `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist`, compose was not run.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-compose-env-shape-guard.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `521 passed, 2 warnings`.

## Decision

Adopt the variant. `launch_compose.py` can now enforce the shape validator before strict preflight when an operator supplies a candidate env file, while the default path still starts at strict preflight.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until an operator supplies a real Firebase Admin service-account JSON outside the repo and production-strength secret, pepper, URL, origins, and database credentials.

## Next Cycle

Document the operator retry sequence in `apps/AgriGuard/README.md` so the launch command examples show the validator-first path for filled env files.
