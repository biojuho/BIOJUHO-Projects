# AutoResearch Loop 2026-07-04 AgriGuard Launch Env Template Validation

## Objective

Add a shape-only launch env validator so an operator can check the generated dotenv template before retrying compose preflight. The validator must fail closed on placeholders, missing launch keys, and forbidden auth flags without printing secrets.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/validate_launch_env_template.py`
- `apps/AgriGuard/backend/tests/test_validate_launch_env_template.py`
- `apps/AgriGuard/scripts/launch_env_preflight.py`
- `apps/AgriGuard/backend/tests/test_launch_env_preflight.py`

The `launch_env_preflight.py` change is limited to accepting UTF-8 BOM dotenv files, which was exposed by the Windows-generated synthetic env fixture.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Modernization radar: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: the compose launch wrapper emits an operator env template, but there is no deterministic check that placeholders or sample domains were replaced before a retry.
- Variant: add a standalone validator that reads one dotenv file exactly, redacts all values, and reports `ready_for_preflight`.
- Primary KPI: generated placeholder template fails while a placeholder-free shape-valid env passes.
- Guardrails: no secret values in JSON/Markdown, no compose startup from invalid env, canonical AgriGuard smoke remains green.

## Variant Evidence

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q`
  - Result: `81 passed in 1.10s`
- Fail-closed launch artifact refresh:
  - `python apps/AgriGuard/scripts/launch_compose.py --run-browser-smoke --json-out var\agriguard-launch-env-shape-validation-preflight.json --launch-report-json var\agriguard-compose-launch-shape-validation-report.json --operator-packet-json var\agriguard-launch-shape-validation-packet.json --operator-packet-markdown var\agriguard-launch-shape-validation-packet.md --operator-env-template var\agriguard-launch-shape-validation.env.template`
  - Expected result: exit code `1`, `stop_reason=preflight_failed`, Docker and compose config checks passed, compose was not run, operator env template was emitted.
- Generated template validation:
  - `python apps/AgriGuard/scripts/validate_launch_env_template.py --env-file var\agriguard-launch-shape-validation.env.template --json-out var\agriguard-launch-env-template-validation-placeholder.json --markdown-out var\agriguard-launch-env-template-validation-placeholder.md`
  - Expected result: exit code `1`, `status=fail`, `placeholder_count=6`, `ready_for_preflight=false`.
- Shape-safe synthetic env validation:
  - `python apps/AgriGuard/scripts/validate_launch_env_template.py --env-file var\agriguard-launch-shape-validation-filled.env --json-out var\agriguard-launch-env-template-validation-filled.json --markdown-out var\agriguard-launch-env-template-validation-filled.md`
  - Result: exit code `0`, `status=pass`, `placeholder_count=0`, `ready_for_preflight=true`.
- Canonical AgriGuard smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-env-validation.json`
  - Result: `status=complete`, `passed=5`, `failed=0`; backend subcheck reported `517 passed, 2 warnings`.

## Decision

Adopt the variant. It adds a bounded operator check between packet generation and compose preflight retry, catches the generated template placeholders/sample domains, handles Windows UTF-8 BOM env files, and preserves fail-closed launch behavior.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until an operator provides production values outside the repo:

- `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` pointing to a real Firebase Admin service-account JSON
- strong `AGRIGUARD_SECRET_KEY`
- stable strong `AGRIGUARD_QR_TOKEN_PEPPER`
- HTTPS `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`
- production `AGRIGUARD_ALLOWED_ORIGINS`
- strong `AGRIGUARD_DB_PASSWORD` or `AGRIGUARD_DATABASE_URL`

## Next Cycle

Add the validator command to the operator-facing packet or compose launch dry-run output so the intended retry order is explicit: fill env file, run shape validator, run strict preflight, then run compose/browser smoke.
