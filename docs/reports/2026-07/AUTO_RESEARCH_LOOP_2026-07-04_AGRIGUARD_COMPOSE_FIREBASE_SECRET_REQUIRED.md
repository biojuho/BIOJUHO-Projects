# AutoResearch Loop: AgriGuard Compose Firebase Secret Required

Date: 2026-07-04

## Objective

Align Docker Compose with the AgriGuard launch preflight contract: a Firebase
Admin service-account JSON must be supplied through an explicit outside-repo
host path, not a repo-local default.

## Scope and Owned Paths

- `apps/AgriGuard/docker-compose.yml`
- `apps/AgriGuard/backend/tests/test_cors_origins.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_COMPOSE_FIREBASE_SECRET_REQUIRED.md`

## External Sources Checked

- Firebase Admin SDK setup: https://firebase.google.com/docs/admin/setup
  - Source basis: server runtimes need a Firebase Admin credential source for
    service-account authentication.
- Google Cloud IAM service-account key best practices:
  https://docs.cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys
  - Source basis: service-account keys are sensitive long-lived credentials and
    should not be checked into source repositories.
- Veritas AutoResearch source repository:
  https://github.com/Veritas-7/autoresearch-skill-system
  - Observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis and Decision Rule

- Baseline: Docker Compose mounted the backend Firebase secret from
  `${AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE:-./backend/firebase-service-account.json}`.
  This default contradicted the newer preflight rule that real Firebase
  service-account keys must live outside the repository.
- Variant: remove the repo-local fallback and use Docker Compose required
  variable interpolation for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
- Primary KPI: `docker compose config` fails when the Firebase host-path
  variable is absent, and renders when it is explicitly set.
- Guardrails: backend compose contract tests pass, canonical AgriGuard smoke
  remains green, and browser screenshot artifact gates remain green.
- Decision rule: adopt only if compose fails closed without the variable,
  passes with an explicit outside-repo file path, and no smoke/browser
  guardrail regresses.

## Variant Evidence

`apps/AgriGuard/docker-compose.yml` now uses:

`file: ${AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE:?Set AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE to an outside-repo Firebase service account JSON}`

The compose contract test now asserts:

- backend still reads `/run/secrets/agriguard_firebase_service_account`
- backend service still mounts `agriguard_firebase_service_account`
- compose uses required interpolation for
  `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`
- the old `./backend/firebase-service-account.json` fallback is absent

## Verification Commands

- `python -m ruff check apps/AgriGuard/backend/tests/test_cors_origins.py`
  - Result: pass
- `python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py::test_agriguard_compose_mounts_firebase_credentials_as_secret -q`
  - Result: `1 passed`
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet` with
  `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` set to a temp outside-repo JSON path
  - Result: pass
- `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet` without
  `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`
  - Result: expected fail with required-variable error
- `python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q`
  - Result: `33 passed`
- `python apps/AgriGuard/scripts/launch_env_preflight.py --check-docker --json-out var\agriguard-launch-env-preflight-compose-requires-firebase.json`
  - Result: expected fail; Docker daemon reachable, compose config fails closed
    because `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` is missing.
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-compose-firebase-secret-required.json`
  - Result: `passed=5, failed=0, total=5`
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-compose-firebase-secret-required.json --output-dir var\agriguard-browser-smoke-suite-compose-firebase-secret-required --timeout-ms 120000`
  - Result: `passed=6, failed=0, checks_passed=135, screenshot_artifacts_total=18, screenshot_artifacts_failed=0`

## Adopt/Reject Decision

Adopted.

The variant removes the last repo-local Firebase compose default and makes the
compose layer fail closed in the same direction as strict launch preflight.

## Remaining Blocker

AgriGuard remains externally blocked until an operator supplies a real Firebase
service-account JSON file outside the repository and sets
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` to that path.

## Next Cycle

Once the real outside-repo Firebase credential is available, run strict
preflight with `--check-docker`, then guarded launch and authenticated browser
smoke.
