# AutoResearch Loop - AgriGuard Preflight Compose Env File Bridge

Date: 2026-07-05

## Objective

Make the guarded AgriGuard launch preflight use the same effective environment
for Docker Compose validation that the launch command uses, so an operator can
run `launch_env_preflight.py --env-file ... --check-docker` with
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` supplied from an outside-repo env file.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/launch_env_preflight.py`
- `apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_PREFLIGHT_COMPOSE_ENV_FILE_BRIDGE.md`

## External Sources Checked

- Docker Compose variable interpolation documentation:
  `https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/`
- Docker Compose environment-variable precedence documentation:
  `https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/`
- Docker Compose secrets documentation:
  `https://docs.docker.com/compose/how-tos/use-secrets/`
- Veritas AutoResearch source:
  `https://github.com/Veritas-7/autoresearch-skill-system`
  - Latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

Baseline: `build_effective_env()` loaded `--env-file` values for launch
validation, but `check_docker_readiness()` invoked `docker compose config` without
passing that effective env. Because `docker-compose.yml` now requires
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, strict preflight could fail Compose
interpolation even after the env file was loaded and validated.

Variant: pass the effective preflight env into the Compose config subprocess
while leaving `docker info` on the ordinary process environment.

Primary KPI: real guarded preflight with `--env-file --check-docker` succeeds
when the Firebase service-account path is outside the repository.

Decision rule: adopt only if focused tests, real Docker Compose config,
canonical AgriGuard smoke, and browser click smoke all pass.

## Adopted Variant

Adopted. `_run_preflight_command()` now accepts an optional env mapping,
`check_docker_readiness()` forwards it only to `docker compose config`, and
`build_launch_report()` passes the already validated effective env into Docker
readiness checks.

Regression coverage now asserts that Compose config receives
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and other effective env-file values,
while `docker info` remains unchanged.

## Verification

- `python -m ruff check apps/AgriGuard/scripts/launch_env_preflight.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py`
  - Result: pass
- `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q`
  - Result: `65 passed`
- `python apps/AgriGuard/scripts/launch_env_preflight.py --env-file var\agriguard-preflight-compose-env-file-bridge.env --check-docker --json-out var\agriguard-launch-env-preflight-compose-env-file-bridge.json`
  - Result: pass
  - Docker daemon: `29.2.1`
  - Compose config: pass
  - Firebase credential path: disposable outside-repo JSON used only for
    preflight shape and Compose interpolation proof
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-preflight-compose-env-file-bridge.json`
  - Result: `passed=5, failed=0`
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-preflight-compose-env-file-bridge.json --output-dir var\agriguard-browser-smoke-suite-preflight-compose-env-file-bridge --timeout-ms 120000`
  - Result: `passed=6, failed=0, checks_passed=135, screenshots_passed=18`

## Commit And Push Status

This report is part of the implementation commit for the cycle:
`Pass AgriGuard preflight env file to compose config`.

Push target: `origin feat/shared-llm-modernization-2026-06-19`.

## Remaining Blocker

The product launch path still requires a real operator-provided Firebase service
account JSON outside the repository. The disposable JSON used in this cycle
proves preflight and Compose interpolation only; it is not a production
credential and does not unblock Firebase Admin authentication.

## Next Cycle

Once a real outside-repo Firebase service-account JSON is available, run the
full guarded launch preflight against the real env file, then run the compose
startup path and browser suite against that launched stack before declaring the
AgriGuard launch gate clear.
