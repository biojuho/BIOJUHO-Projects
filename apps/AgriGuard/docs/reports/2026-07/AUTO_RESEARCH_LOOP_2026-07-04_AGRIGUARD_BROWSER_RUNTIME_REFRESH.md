# AutoResearch Loop - AgriGuard Browser Runtime Refresh

## Objective

Recover the real AgriGuard browser-smoke runtime after the aggregate suite
started failing against a stale backend container, then prove the QR, product,
admin, supply-chain, and mobile navigation paths against the live frontend and
backend.

## Scope and Owned Paths

- `apps/AgriGuard/backend/alembic/versions/0005_add_qr_scan_event_kpi_indexes.py`
- `apps/AgriGuard/backend/alembic/versions/0006_add_sensor_device_owner_scope.py`
- `apps/AgriGuard/backend/auth.py`
- `apps/AgriGuard/docker-compose.yml`
- `apps/AgriGuard/backend/tests/test_smoke.py`
- `apps/AgriGuard/backend/tests/test_auth_security.py`
- `apps/AgriGuard/backend/tests/test_cors_origins.py`
- AgriGuard cycle reports that record the active Alembic revision ids.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## A/B Hypothesis and Decision Rule

- Baseline: keep using the rebuilt backend image without changing code.
- Variant: shorten over-length Alembic revision ids, guard the revision-id
  length in tests, treat non-file Firebase credential paths as unconfigured
  instead of crashing, and pass dev-auth fallback flags through compose with a
  fail-closed default.
- Primary KPI: aggregate browser smoke must pass against the live frontend and
  backend.
- Guardrails: focused migration/auth/compose tests must pass, backend OpenAPI
  must expose all browser-smoke routes, production defaults must keep
  `ALLOW_DEV_AUTH_FALLBACK=false`.

## Baseline Evidence

- Rebuilt Docker backend initially failed at PostgreSQL migration time because
  Alembic's `version_num` column is `VARCHAR(32)` and revisions
  `0005_add_qr_scan_event_kpi_indexes` / `0006_add_sensor_device_owner_scope`
  were 34 characters.
- After the migration-id fix, the backend reached Alembic head but crashed on
  Firebase initialization when the missing compose secret mounted as a directory
  at `/run/secrets/agriguard_firebase_service_account`.
- Before rebuild, the aggregate browser-smoke precheck failed because the stale
  OpenAPI surface did not include `/qr-events/kpis`,
  `/qr-events/kpis/trend`, `/qr-tokens/products/{product_id}`,
  `/sensor-devices`, or `/sensor-devices/{sensor_id}`.

## Variant Evidence

- Shortened active Alembic ids to `0005_qr_kpi_indexes` and
  `0006_sensor_owner_scope`; added a regression test that all revision ids fit
  Postgres/Alembic's 32-character version column.
- `auth.py` now checks `os.path.isfile()` before Firebase certificate loading,
  so a missing Docker secret mount logs a warning and leaves auth fail-closed
  unless the explicit dev fallback is enabled.
- `docker-compose.yml` now passes `ALLOW_DEV_AUTH_FALLBACK` and
  `DEV_AUTH_FALLBACK_ROLE` through with disabled defaults, allowing local
  browser smoke to opt in through process environment only.
- Docker backend rebuilt with an ephemeral local DB password override matching
  the existing Postgres volume and explicit local dev-auth fallback. Credential
  values were not recorded.
- Backend health after rebuild: `State=running`, `Health=healthy`.
- OpenAPI after rebuild contained all required browser-smoke paths.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_auth_security.py apps/AgriGuard/backend/tests/test_cors_origins.py::test_agriguard_compose_mounts_firebase_credentials_as_secret apps/AgriGuard/backend/tests/test_cors_origins.py::test_agriguard_compose_exposes_dev_auth_fallback_as_disabled_opt_in apps/AgriGuard/backend/tests/test_smoke.py::test_run_migrations_script_applies_head_revision apps/AgriGuard/backend/tests/test_smoke.py::test_alembic_revision_ids_fit_postgres_version_column -q
```

Result: `11 passed, 1 warning in 39.98s`.

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-after-backend-rebuild.json --output-dir var\agriguard-browser-smoke-suite-after-backend-rebuild --timeout-ms 30000
```

Result: `status=pass`, `passed=5`, `failed=0`, `checks_passed=121`,
`checks_failed=0`, `prechecks_passed=1`, `prechecks_failed=0`.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-browser-runtime-refresh.json
```

Result: `passed=5`, `failed=0`, `total=5`; backend tests passed in the
canonical smoke run.

## Decision

Adopt the variant. It removes the Postgres-only migration failure, keeps
Firebase auth fail-closed for launch, and restores the real browser-smoke path
against the live local runtime.

## Next Cycle

Commit only the owned patch, push it, then continue launch hardening on the
next highest-value runtime or operator handoff gap.
