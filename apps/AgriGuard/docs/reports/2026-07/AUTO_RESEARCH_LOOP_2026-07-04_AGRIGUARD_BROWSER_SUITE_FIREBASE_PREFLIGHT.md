# AgriGuard AutoResearch Loop - browser suite and Firebase preflight

Date: 2026-07-04

## Objective

Turn the repeated AgriGuard browser-click smoke sequence into one aggregate
operator command and make the launch preflight catch the auth blocker exposed by
the live Docker-backed app.

## Scope and owned paths

- `scripts/run_browser_smoke_suite.py`
- `scripts/launch_env_preflight.py`
- `backend/tests/test_smoke.py`
- `backend/tests/test_launch_env_preflight.py`

## A/B hypothesis and decision rule

Baseline: browser launch evidence required running five separate scripts by
hand. The strict preflight rejected dev auth toggles, but it did not require
Firebase Admin credentials, so a compose backend could run with launch fallback
disabled while every authenticated operator path returned 503.

Variant:

- Add a suite runner that executes the existing live-backend browser smokes and
  writes one aggregate JSON report with redacted operator-token command logs.
- Keep the backend-unavailable consumer smoke as explicit opt-in because it
  requires a different service state.
- Add strict launch preflight coverage for `GOOGLE_APPLICATION_CREDENTIALS`,
  with an explicit local-diagnostic override.

Adopt only if focused tests and canonical AgriGuard smoke pass, and if the live
browser suite records the current auth blocker instead of hiding it.

## Evidence

- Pass: `python -m py_compile scripts/launch_env_preflight.py scripts/run_browser_smoke_suite.py backend/tests/test_launch_env_preflight.py backend/tests/test_smoke.py`
- Pass: `python -m pytest backend/tests/test_launch_env_preflight.py backend/tests/test_smoke.py -q --basetemp "..\var\tmp\pytest-agriguard-firebase-suite"` (`79 passed`)
- Pass: `python scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --dry-run --json-out "..\var\agriguard-browser-suite-firebase-dry-run.json" --output-dir "..\var\agriguard-browser-suite-firebase-dry-run"` (`5` planned steps)
- Expected fail-closed: `python scripts/launch_env_preflight.py --check-docker --json-out "..\var\agriguard-launch-env-preflight-firebase-current.json"` wrote status `fail` with Docker daemon and compose config passing, plus these launch blockers:
  - `GOOGLE_APPLICATION_CREDENTIALS`
  - `AGRIGUARD_SECRET_KEY`
  - `AGRIGUARD_QR_TOKEN_PEPPER`
  - `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`
  - `AGRIGUARD_ALLOWED_ORIGINS`
- Current live browser evidence: `python scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out "..\var\agriguard-browser-suite-firebase-current.json" --output-dir "..\var\agriguard-browser-suite-firebase-current" --timeout-ms 30000` recorded `passed=1`, `failed=4`, `checks_passed=67`, `checks_failed=4`.
- The failed authenticated child smokes hit `HTTP 503` with `Firebase authentication is not configured.` while seeding product data.
- Pass: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out "var\workspace-smoke-agriguard-firebase-browser-suite.json"` (`passed=5`, `failed=0`, `total=5`)

## Decision

Adopt the aggregate browser suite runner and the Firebase credential preflight
guard. The product is not launch-ready in the current Docker-backed state
because authenticated operator flows cannot run without Firebase Admin
credentials.

## Current launch blocker

Docker is ready. Compose config is valid. Remaining launch inputs are operator
or deployment-secret work:

- Provide a Firebase Admin service account file and set `GOOGLE_APPLICATION_CREDENTIALS` for the backend container.
- Generate and store `AGRIGUARD_SECRET_KEY` and `AGRIGUARD_QR_TOKEN_PEPPER` outside git.
- Set real HTTPS `AGRIGUARD_PUBLIC_VERIFY_BASE_URL` and launch-grade `AGRIGUARD_ALLOWED_ORIGINS`.

Do not enable `ALLOW_DEV_AUTH_FALLBACK` or `ALLOW_TEST_BYPASS` to pass launch
preflight; those are intentionally rejected for launch.

## Next cycle

After the Firebase credential and app-scoped launch values are supplied, rerun:

```powershell
python apps/AgriGuard/scripts/launch_env_preflight.py --check-docker --json-out var/agriguard-launch-env-preflight.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var/agriguard-browser-smoke-suite.json
```
