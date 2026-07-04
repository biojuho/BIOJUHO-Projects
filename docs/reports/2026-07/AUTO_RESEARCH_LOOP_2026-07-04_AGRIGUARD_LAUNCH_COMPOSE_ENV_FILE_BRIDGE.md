# AutoResearch Loop: AgriGuard Launch Compose Env-File Bridge

Date: 2026-07-04

## Objective

Keep the guarded compose launcher compatible with the stricter Firebase compose
secret contract. If an operator provides `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`
through `--env-file`, the launcher must pass that env-file value into
`docker compose up`.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_LAUNCH_COMPOSE_ENV_FILE_BRIDGE.md`

## External Sources Checked

- Firebase Admin SDK setup: https://firebase.google.com/docs/admin/setup
  - Source basis: Firebase Admin credentials must be available to the server
    runtime.
- Google Cloud IAM service-account key best practices:
  https://docs.cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys
  - Source basis: service-account keys should stay outside source repositories.
- Veritas AutoResearch source repository:
  https://github.com/Veritas-7/autoresearch-skill-system
  - Observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: `launch_compose.py` passed `--env-file` to strict preflight, but
  called `docker compose up` without a subprocess environment built from that
  env file. After requiring `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` in
  compose interpolation, a valid env-file launch could fail at the compose step.
- Variant: parse supplied dotenv files in launcher process, overlay the parent
  process environment in the same order as preflight, and pass the resulting
  environment to the `docker compose up` subprocess.
- Primary KPI: a value supplied in `--env-file` is present in the compose
  subprocess environment.
- Guardrails: command logs do not include secret values, launch-compose tests
  remain green, canonical AgriGuard smoke remains green, and browser screenshot
  artifact gates remain green.
- Decision rule: adopt only if the env-file bridge is covered by a regression
  test and all relevant smoke gates pass.

## Variant Evidence

`launch_compose.py` now:

- parses dotenv files with UTF-8 BOM tolerance and optional single/double quotes
- builds a compose subprocess env from supplied env files plus `os.environ`
- passes that env only to `docker compose up`
- keeps launch reports command-based, so secret values are not serialized

The regression test writes:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=C:/secure/firebase-service-account.json`

and verifies that value reaches the compose subprocess environment.

## Verification Commands

- `python -m ruff check apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/backend/tests/test_launch_compose_script.py`
  - Result: pass
- `python -m py_compile apps/AgriGuard/scripts/launch_compose.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py -q`
  - Result: `17 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-compose-env-file-to-compose.json`
  - Result: `passed=5, failed=0, total=5`
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-launch-compose-env-file-to-compose.json --output-dir var\agriguard-browser-smoke-suite-launch-compose-env-file-to-compose --timeout-ms 120000`
  - Result: `passed=6, failed=0, checks_passed=135, screenshot_artifacts_total=18, screenshot_artifacts_failed=0`

## Adopt/Reject Decision

Adopted.

The launcher now carries the validated operator env-file values through to the
compose process while preserving redacted command/report behavior.

## Remaining Blocker

AgriGuard still requires a real Firebase service-account JSON file outside the
repository. Local launch plumbing is aligned, but the credential itself is still
operator-provided external state.

## Next Cycle

When the credential exists, run `launch_compose.py --env-file <operator.env>
--run-browser-smoke` so preflight, compose interpolation, service startup, and
browser smoke all exercise the same outside-repo Firebase path.
