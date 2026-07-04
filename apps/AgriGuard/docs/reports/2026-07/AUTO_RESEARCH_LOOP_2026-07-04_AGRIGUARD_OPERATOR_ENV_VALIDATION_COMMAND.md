# AutoResearch Loop 2026-07-04 AgriGuard Operator Env Validation Command

## Objective

Expose the launch env shape validator in the operator-facing packet so the retry order is explicit: fill the env template, validate it, run strict preflight, then retry compose/browser smoke.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: operator packet listed preflight and compose rerun commands, but did not advertise the new shape-only env validator.
- Variant: add the validator as safe rerun command `0` and mirror it in `operator_env_template.validation_command`.
- Primary KPI: packet JSON and Markdown make the validator-first retry order machine-readable and human-readable.
- Guardrails: packet redaction still hides sensitive assignments, generated template remains placeholder-only, AgriGuard smoke stays green.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py -q`
  - Result: `10 passed in 0.52s`
- Live operator packet render:
  - `python apps/AgriGuard/scripts/render_launch_operator_packet.py --preflight-json var\agriguard-launch-env-shape-validation-preflight.json --json-out var\agriguard-launch-operator-command-packet.json --markdown-out var\agriguard-launch-operator-command-packet.md --env-template-out var\agriguard-launch-operator.env.template --exit-zero-on-blocked`
  - Result: `status=blocked`, `safe_rerun_commands[0]` starts with `python apps/AgriGuard/scripts/validate_launch_env_template.py`, and `operator_env_template.validation_command` matches command `0`.
- Live command execution:
  - `python apps/AgriGuard/scripts/validate_launch_env_template.py --env-file var\agriguard-launch-operator.env.template --json-out var\agriguard-launch-operator-command-validation.json --markdown-out var\agriguard-launch-operator-command-validation.md`
  - Expected result: exit code `1`, `status=fail`, `placeholder_count=6`, `ready_for_preflight=false`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-env-validation-command.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `517 passed, 2 warnings`.

## Decision

Adopt the variant. The packet now carries a validator-first retry command that aligns the operator packet with the launch env validation artifact added in the prior cycle.

## Remaining Launch Blocker

Real compose/browser launch is still externally blocked until an operator supplies the production Firebase service-account file, strong app secret, stable QR pepper, HTTPS public verify URL, production allowed origins, and strong database credentials.

## Next Cycle

Add an optional `launch_compose.py` preflight guard that validates supplied `--env-file` inputs before invoking strict preflight, while keeping the default no-env path unchanged.
