# AutoResearch Loop - AgriGuard Tenant RLS Route Wiring

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: protected-route adoption of the tenant RLS DB dependency
- External context: PostgreSQL RLS policies are only meaningful when request/session settings are applied before protected queries run.

## Source-Backed Rationale

PostgreSQL row security evaluates policy expressions for normal row access, and rows are denied when enabled RLS has no applicable policy approval. AgriGuard's policy draft reads transaction-local settings, so protected routes need to establish those settings before running tenant-scoped database queries.

Primary source: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>

## Adopted Change

- Switched authenticated product routes from `get_db` to `get_tenant_rls_db`.
- Switched QR-token admin routes from `get_db` to `get_tenant_rls_db`.
- Switched sensor-device admin routes from `get_db` to `get_tenant_rls_db`.
- Left public consumer verification and QR telemetry routes unchanged because `qr_scan_events` RLS remains deferred.
- Kept a module-level `get_db = get_tenant_rls_db` compatibility alias in each switched router so existing FastAPI dependency overrides and local tests continue to target the same callable object.
- Added `backend/tests/test_tenant_rls_route_wiring.py`, an AST guard that fails if the three protected routers regress back to `Depends(get_db)`.

## Evidence

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/backend/routers/products.py' 'apps/AgriGuard/backend/routers/qr_tokens_admin.py' 'apps/AgriGuard/backend/routers/sensor_devices_admin.py' 'apps/AgriGuard/backend/tests/test_tenant_rls_route_wiring.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_tenant_rls_route_wiring.py tests/test_product_and_qr_routes.py tests/test_sensor_devices_admin.py tests/test_tenant_rls.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-tenant-rls-route-wiring'
```

Result: `76 passed, 1 warning in 11.29s`.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-tenant-rls-route-wiring.json
```

Result: `passed=5, failed=0, total=5` in `5m45s`.

Slowest checks:

- `agriguard backend tests`: `390 passed, 2 warnings in 298.19s`
- `agriguard frontend lint`: pass
- `agriguard frontend build`: pass
- `agriguard contracts tests`: `26 passing`
- `agriguard contracts compile`: pass

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-tenant-rls-route-wiring.json`

## Current Launch State

The main tenant-owned protected API surfaces now set tenant RLS context before database access. Remaining RLS rollout blockers are still external/schema-operational: the configured PostgreSQL role bypasses RLS, and `qr_scan_events` remains deferred until its audit-event ownership model is promoted into a safe policy.
