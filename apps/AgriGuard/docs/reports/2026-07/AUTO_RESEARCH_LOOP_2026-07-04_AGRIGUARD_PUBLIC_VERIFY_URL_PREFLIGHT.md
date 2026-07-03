# AgriGuard AutoResearch Loop - public verify URL preflight

Date: 2026-07-04

## Source-backed observation

AgriGuard product creation builds consumer QR label URLs from `PUBLIC_VERIFY_BASE_URL`. The compose runtime did not explicitly bridge that value from an app-scoped launch variable, and the launch preflight did not require a launch-grade public web base URL. That could leave new product labels on the legacy `agri://` scheme or on a local/insecure URL during launch.

## Adopted variant

- Compose now passes `PUBLIC_VERIFY_BASE_URL=${AGRIGUARD_PUBLIC_VERIFY_BASE_URL:-${PUBLIC_VERIFY_BASE_URL:-}}` to the backend container.
- Compose launch preflight requires `AGRIGUARD_PUBLIC_VERIFY_BASE_URL` by default.
- Direct backend preflight validates direct `PUBLIC_VERIFY_BASE_URL`.
- Strict launch validation requires an `https://` base URL with no path, params, query, fragment, or local host.
- Local diagnostics can explicitly opt into generic compose `PUBLIC_VERIFY_BASE_URL`, local verify hosts, or the legacy `agri://` QR scheme.
- The app-level `.env.example` and README launch preflight checklist now include the app-scoped public verify URL.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-public-url-preflight"` (`38 passed`, 2 warnings)
- Pass: `uv run --project apps/AgriGuard/backend python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-public-url-cors"` (`29 passed`, 1 warning)
- Pass: synthetic app-scoped launch env wrote `var/agriguard-launch-env-preflight-public-url-pass.json` with status `pass`.
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`.
- Expected fail-closed: current strict preflight wrote `var/agriguard-launch-env-preflight-public-url-current.json` with status `fail` because app-scoped launch values are not fully set.
- Expected fail-closed: current strict `--check-docker` preflight wrote `var/agriguard-launch-env-preflight-public-url-docker-current.json` with five launch blockers: missing app-scoped secret, missing `AGRIGUARD_QR_TOKEN_PEPPER`, missing `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`, missing `AGRIGUARD_ALLOWED_ORIGINS`, and unavailable Docker daemon.
