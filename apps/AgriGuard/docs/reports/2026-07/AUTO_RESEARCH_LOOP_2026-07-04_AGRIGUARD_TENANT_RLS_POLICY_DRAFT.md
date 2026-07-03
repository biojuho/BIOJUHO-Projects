# AutoResearch Loop - AgriGuard Tenant RLS Policy Draft

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: tenant RLS request context, reviewable policy draft, and live PostgreSQL smoke verifier
- External context: PostgreSQL row security semantics and role-bypass behavior

## Source-Backed Rationale

PostgreSQL row security policies filter or allow rows per command, default-deny when no policy applies after RLS is enabled, and are bypassed by superusers or roles with `BYPASSRLS`. AgriGuard therefore needs two controls before promoting RLS to a migration:

- request-scoped tenant settings that policies can read safely,
- a live smoke that refuses to treat a superuser/BYPASSRLS role as tenant-isolation proof.

Primary source: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>

## Adopted Change

- Added `backend/tenant_rls.py` with `apply_tenant_rls_context`, setting:
  - `app.current_owner_ids`
  - `app.is_global_operator`
- Added a delimiter guard so malformed owner keys containing `,` are omitted instead of expanding into multiple owner IDs in the session setting.
- Added `get_tenant_rls_db` to `backend/dependencies.py` for later protected-route adoption while keeping current routes unchanged.
- Added `backend/scripts/render_rls_policy_draft.py` to render JSON, SQL, and Markdown policy drafts for:
  - `products`
  - `sensor_devices`
  - `qr_tokens`
  - `tracking_events`
  - `certificates`
- Kept `qr_scan_events` deferred pending a durable audit-event ownership model.
- Added `backend/scripts/verify_tenant_rls_postgres.py`, which creates a temporary PostgreSQL RLS table and checks no-context denial, tenant isolation, transaction-local reset, and global-operator access when run with a non-bypass role.
- Moved auth initialization warnings to stderr so RLS CLI stdout remains valid SQL or Markdown.

## Evidence

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/backend/auth.py' 'apps/AgriGuard/backend/dependencies.py' 'apps/AgriGuard/backend/tenant_rls.py' 'apps/AgriGuard/backend/scripts/render_rls_policy_draft.py' 'apps/AgriGuard/backend/scripts/verify_tenant_rls_postgres.py' 'apps/AgriGuard/backend/tests/test_tenant_rls.py' 'apps/AgriGuard/backend/tests/test_rls_policy_draft.py' 'apps/AgriGuard/backend/tests/test_tenant_rls_postgres_smoke.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_tenant_rls.py tests/test_rls_policy_draft.py tests/test_tenant_rls_postgres_smoke.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-tenant-rls'
```

Result: `13 passed in 9.42s`.

### Policy Draft Artifacts

Artifact directory: `D:\AI project\var\agriguard-tenant-rls-2026-07-04`

```powershell
python scripts/render_rls_policy_draft.py --force-rls --json-out D:\AI project\var\agriguard-tenant-rls-2026-07-04\policy-draft.json --sql-out D:\AI project\var\agriguard-tenant-rls-2026-07-04\policy-draft.sql --markdown-out D:\AI project\var\agriguard-tenant-rls-2026-07-04\policy-draft.md
```

Result: exit code `0`.

Key evidence:

- stdout first line: `-- AgriGuard PostgreSQL RLS policy draft.`
- stderr first line: Firebase service-account warning, now separated from SQL stdout
- `force_rls`: `true`
- policy count: `5`
- deferred table: `qr_scan_events`

### Configured PostgreSQL Live Smoke

```powershell
python scripts/verify_tenant_rls_postgres.py --require-live --json-out D:\AI project\var\agriguard-tenant-rls-2026-07-04\configured-tenant-rls-smoke.json --markdown-out D:\AI project\var\agriguard-tenant-rls-2026-07-04\configured-tenant-rls-smoke.md
```

Result: native exit code `1`.

Machine-readable result:

```json
{
  "status": "blocked",
  "reason": "Current PostgreSQL role bypasses RLS; use a non-superuser role without BYPASSRLS.",
  "role": {
    "database_name": "agriguard",
    "role_name": "agriguard",
    "is_superuser": true,
    "has_bypassrls": true
  }
}
```

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-tenant-rls-policy-draft.json
```

Result: `passed=5, failed=0, total=5` in `6m4s`.

Slowest checks:

- `agriguard backend tests`: `389 passed, 2 warnings in 315.95s`
- `agriguard frontend lint`: pass
- `agriguard frontend build`: pass
- `agriguard contracts tests`: `26 passing`
- `agriguard contracts compile`: pass

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-tenant-rls-policy-draft.json`

## Current Launch State

Local RLS context, draft rendering, and verifier behavior are green. Live tenant-isolation proof remains blocked by deployment role configuration: the configured PostgreSQL role is a superuser and has `BYPASSRLS`, so it cannot be used as RLS proof. Create/use a non-superuser application role without `BYPASSRLS`, then rerun the live smoke with `--require-live`.
