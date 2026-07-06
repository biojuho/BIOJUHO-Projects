# AutoResearch Loop - AgriGuard Health Endpoint - 2026-07-06

## Scope

Close the local health-probe gap where `/health` was already excluded from rate limiting but returned `404 Not Found`. The compose healthcheck still intentionally probes `/`, but `/health` now works for local operators, smoke harnesses, and external uptime probes.

## Changes

- Added a shared dashboard health payload helper.
- Kept the existing `/` health contract unchanged.
- Added `/health` as an alias for the same health payload.
- Added a full-app regression test that verifies `/health` is mounted and does not emit rate-limit headers.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_health_route.py -q`: `1` passed, with the existing insecure-dev `SECRET_KEY` warning.
- `python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py::test_agriguard_backend_healthcheck_uses_api_root_not_docs_ui -q`: `1` passed, with the existing insecure-dev `SECRET_KEY` warning.
- `python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py::test_backend_sets_baseline_security_headers_on_api_responses -q`: `1` passed, with the existing insecure-dev `SECRET_KEY` warning.
- `python -m pytest apps/AgriGuard/backend/tests/test_dashboard_routes.py::test_read_root -q`: `1` passed.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Remaining Blocker

Strict launch remains externally blocked until `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a real Firebase Admin service-account file.
