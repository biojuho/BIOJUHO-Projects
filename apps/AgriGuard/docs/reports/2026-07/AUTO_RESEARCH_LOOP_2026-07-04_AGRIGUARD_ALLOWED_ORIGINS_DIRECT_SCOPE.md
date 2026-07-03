# AgriGuard AutoResearch Loop - direct allowed origins scope

Date: 2026-07-04

## Source-backed observation

Direct backend startup reads `ALLOWED_ORIGINS`, while compose bridges `AGRIGUARD_ALLOWED_ORIGINS` into backend `ALLOWED_ORIGINS`. The launch preflight had already scoped secrets, QR pepper, public verify URL, and database URL by runtime, but direct mode still accepted app-scoped `AGRIGUARD_ALLOWED_ORIGINS`. That could overstate readiness for a direct backend launch.

## Adopted variant

- Compose launch preflight now fails explicitly when only generic `ALLOWED_ORIGINS` is present.
- Direct backend launch preflight now validates only direct `ALLOWED_ORIGINS`.
- Direct backend launch preflight now fails explicitly when only `AGRIGUARD_ALLOWED_ORIGINS` is present.
- Missing-origin messages remain runtime-specific, and the local default-origin escape hatch still applies only to truly missing origins.

## Verification

- Pass: `python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py`
- Pass: `uv run --isolated --no-project --with pytest>=8.0 python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-origin-scope-preflight"` (`49 passed`, 2 warnings)
- Pass: isolated direct-mode env with direct `ALLOWED_ORIGINS` wrote `var/agriguard-launch-env-preflight-origin-scope-direct-pass.json` with status `pass`.
- Expected fail-closed: isolated direct-mode env with only `AGRIGUARD_ALLOWED_ORIGINS` wrote `var/agriguard-launch-env-preflight-origin-scope-direct-fail.json` with status `fail`.
- Expected fail-closed: current strict compose preflight wrote `var/agriguard-launch-env-preflight-origin-scope-current.json` with status `fail`; it now reports that generic `ALLOWED_ORIGINS` is not sufficient for compose launch.
