# AgriGuard AutoResearch Loop - QR token pepper preflight

Date: 2026-07-04

## Source-backed observation

AgriGuard QR label tokens are stored as hashes derived from `QR_TOKEN_PEPPER`. The compose runtime did not explicitly bridge that value from the app-scoped launch environment, and the launch preflight did not require an independent pepper. That allowed a launch check to miss a token-hash stability risk or silently fall back to the auth secret/default pepper path.

## Adopted variant

- Compose now passes `QR_TOKEN_PEPPER=${AGRIGUARD_QR_TOKEN_PEPPER:-${QR_TOKEN_PEPPER:-}}` to the backend container.
- Compose launch preflight requires strong, non-placeholder `AGRIGUARD_QR_TOKEN_PEPPER` by default.
- Direct backend preflight validates the actual `QR_TOKEN_PEPPER` name used by direct Python startup.
- `--allow-generic-qr-token-pepper` is available for local compose checks that intentionally accept generic `QR_TOKEN_PEPPER`.
- The app-level `.env.example` now exposes app-scoped compose launch keys, while direct backend aliases remain available for local non-compose runs.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-qr-pepper-preflight-only"` (`30 passed`, 2 warnings)
- Pass: `uv run --project apps/AgriGuard/backend python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-qr-pepper-cors"` (`28 passed`, 1 warning)
- Pass: synthetic app-scoped launch env wrote `var/agriguard-launch-env-preflight-qr-pepper-pass.json` with status `pass`.
- Pass: `docker compose -f apps/AgriGuard/docker-compose.yml config --quiet`.
- Expected fail-closed: current strict preflight wrote `var/agriguard-launch-env-preflight-qr-pepper-current.json` with status `fail` because app-scoped launch values are not fully set.
- Expected fail-closed: current strict `--check-docker` preflight wrote `var/agriguard-launch-env-preflight-qr-pepper-docker-current.json` with four launch blockers: missing app-scoped secret, missing `AGRIGUARD_QR_TOKEN_PEPPER`, missing `AGRIGUARD_ALLOWED_ORIGINS`, and unavailable Docker daemon.
