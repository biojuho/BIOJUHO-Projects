# AgriGuard AutoResearch Loop - Firebase credential packaging guard

Date: 2026-07-04

## Objective

Reduce the risk that a Firebase Admin service-account JSON file is accidentally
committed or baked into the backend Docker image while resolving the launch auth
blocker.

## Scope and owned paths

- `.gitignore`
- `backend/.dockerignore`
- `backend/tests/test_cors_origins.py`

## Secret-hygiene pass

The secret-hygiene skill recommends `scripts/scan_secrets.py`, but that helper
is not present in this AgriGuard checkout or the immediate parent script
directory. This cycle used targeted packaging safeguards instead.

## A/B hypothesis and decision rule

Baseline: `backend/.dockerignore` excluded `.env` and local runtime/test
artifacts, but not Firebase service-account JSON names. The app root also did
not have an AgriGuard-local ignore rule for those credential filenames.

Variant:

- Exclude `firebase-service-account*.json`, `*service-account*.json`, and
  `serviceAccountKey.json` from the backend Docker build context.
- Add an AgriGuard-local `.gitignore` for the matching backend credential paths.
- Extend the existing Dockerignore contract test.

Adopt only if the focused Docker/context test, compose config, and canonical
AgriGuard smoke pass.

## Evidence

- Pass: `python -m py_compile backend/tests/test_cors_origins.py`
- Pass: `python -m pytest backend/tests/test_cors_origins.py -q --basetemp "..\var\tmp\pytest-agriguard-firebase-dockerignore"` (`29 passed`, `1 warning`)
- Pass: `docker compose config --quiet`
- Pass: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-firebase-secret-hygiene.json"` (`passed=5`, `failed=0`, `total=5`)

## Decision

Adopt the credential packaging guard. Operators still need to provide Firebase
Admin credentials for launch, but those credentials should be mounted or
injected by the deployment environment, not committed into the app or copied
into the backend image by accident.

## Current launch blocker

This does not remove the Firebase launch blocker. The Docker-backed browser
suite still needs a real `GOOGLE_APPLICATION_CREDENTIALS` path available inside
the backend container before authenticated product, QR-token, and sensor-admin
flows can pass.
