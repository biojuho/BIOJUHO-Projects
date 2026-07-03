# AgriGuard AutoResearch Loop - launch environment preflight

Date: 2026-07-04

## Source-backed observation

The broad AgriGuard smoke still imports the backend with no `SECRET_KEY` and records the expected insecure-default warning. Runtime startup remains compatible for local tests, but launch operations need a fail-closed preflight that blocks missing or placeholder secrets before production use.

## Adopted variant

- Added `apps/AgriGuard/scripts/launch_env_preflight.py`.
- The preflight fails when `AGRIGUARD_SECRET_KEY`/`SECRET_KEY` is missing, placeholder-like, or shorter than 32 characters.
- The preflight also rejects launch-unsafe `AUTO_CREATE_SCHEMA=true`, SQLite database URLs, and wildcard allowed origins.
- The CLI defaults to compose runtime semantics, so host `DATABASE_URL`, `AUTO_CREATE_SCHEMA`, and `ALLOWED_ORIGINS` are ignored unless `AGRIGUARD_DATABASE_URL`, `AGRIGUARD_AUTO_CREATE_SCHEMA`, or `AGRIGUARD_ALLOWED_ORIGINS` is explicitly set; `--runtime direct` validates direct backend launches against the generic backend env names.
- Compose launch requires app-scoped `AGRIGUARD_SECRET_KEY` by default; `--allow-generic-secret-key` is available for local checks that intentionally accept generic `SECRET_KEY`.
- Direct backend launch validates `SECRET_KEY`, because `AGRIGUARD_SECRET_KEY` is only bridged by compose.
- Later QR token hardening requires app-scoped `AGRIGUARD_QR_TOKEN_PEPPER` for compose launch and direct `QR_TOKEN_PEPPER` for direct backend launch.
- Later public QR URL hardening requires app-scoped `AGRIGUARD_PUBLIC_VERIFY_BASE_URL` for compose launch and direct `PUBLIC_VERIFY_BASE_URL` for direct backend launch.
- Missing explicit allowed origins fail closed by default; `--allow-runtime-default-origins` is available for local checks that intentionally accept runtime defaults.
- `--check-docker` adds Docker daemon reachability and compose config validation for launch startup readiness.
- Added focused tests for missing, placeholder, short, unsafe, passing, and env-file override cases.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-launch-env-preflight-runtime"` (`8 passed`)
- Pass: CLI with strong `AGRIGUARD_SECRET_KEY`, PostgreSQL URL, scoped allowed origin, and `AUTO_CREATE_SCHEMA=false` returned status `pass`.
- Pass: CLI with `AGRIGUARD_SECRET_KEY=change_me` returned exit code `1` and status `fail`.
- Pass: CLI with `--runtime direct`, strong secret, PostgreSQL URL, scoped allowed origin, and `AUTO_CREATE_SCHEMA=false` returned status `pass`.
- Superseded current-state note: later strict QR-token-pepper and public-URL hardening now blocks current compose-mode launch preflight until `AGRIGUARD_QR_TOKEN_PEPPER` and `AGRIGUARD_PUBLIC_VERIFY_BASE_URL` are set.
