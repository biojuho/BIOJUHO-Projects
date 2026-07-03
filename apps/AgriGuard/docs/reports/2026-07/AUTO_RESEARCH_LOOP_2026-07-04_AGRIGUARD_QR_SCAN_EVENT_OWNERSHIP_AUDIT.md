# AutoResearch Loop - AgriGuard QR Scan Event Ownership Audit

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: QR scan-event tenant ownership readiness before PostgreSQL RLS rollout
- External context: Veritas AutoResearch `main` at `b8bbf393759d6e67e780f03c572ec626fab6593b`; GitHub modernization radar refreshed with 8 adopted sources.

## Source-Backed Rationale

PostgreSQL row security evaluates policy expressions per row, and when row security is enabled without an applicable policy it defaults to deny. For `qr_scan_events`, that means launch readiness needs a deterministic way to classify each row as tenant-owned, intentionally global diagnostic telemetry, or blocked for RLS policy rollout.

Primary source: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>

## Adopted Change

- Added `backend/scripts/report_qr_scan_event_ownership.py`.
- Added `backend/tests/test_qr_scan_event_ownership_report.py`.
- Classifies each QR scan event through:
  - `product_id -> products.owner_id`
  - `sensor_id -> sensor_devices.owner_id`
  - `metadata_json.owner_id`
  - public diagnostic scan-failure allow-list
- Flags unresolved tenant/admin rows, conflicting owner candidates, and invalid metadata as blocked for `qr_scan_events` RLS.
- Added `--fail-on-blocked` for release automation that should fail only when an event truly blocks RLS, while preserving stricter `--fail-on-unresolved`, `--fail-on-conflict`, and `--fail-on-invalid-metadata` gates.
- Added fail-closed SQLAlchemy handling so missing schema or query failures return exit code `2` without a traceback.

## Evidence

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/backend/scripts/report_qr_scan_event_ownership.py' 'apps/AgriGuard/backend/tests/test_qr_scan_event_ownership_report.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_qr_scan_event_ownership_report.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-qr-event-ownership'
```

Result: `6 passed in 56.13s`.

### Fixture CLI Evidence

Artifact directory: `D:\AI project\var\agriguard-qr-scan-event-ownership-2026-07-04`

```powershell
python scripts/report_qr_scan_event_ownership.py --json-out D:\AI project\var\agriguard-qr-scan-event-ownership-2026-07-04\fixture-ownership.json --markdown-out D:\AI project\var\agriguard-qr-scan-event-ownership-2026-07-04\fixture-ownership.md --fail-on-blocked
```

Result: exit code `0`.

Key JSON evidence:

```json
{
  "status": "pass",
  "total_events": 3,
  "owned_event_count": 2,
  "unresolved_event_count": 1,
  "global_diagnostic_event_count": 1,
  "blocked_event_count": 0,
  "rls_visibility_counts": {
    "global_diagnostic": 1,
    "tenant_owned": 2
  }
}
```

### Configured Database Evidence

```powershell
python scripts/report_qr_scan_event_ownership.py --json-out D:\AI project\var\agriguard-qr-scan-event-ownership-2026-07-04\configured-ownership.json --markdown-out D:\AI project\var\agriguard-qr-scan-event-ownership-2026-07-04\configured-ownership.md --fail-on-blocked
```

Result: native exit code `2`.

Fail-closed stderr:

```text
QR scan event ownership report failed: database schema is not ready or query failed: relation "sensor_devices" does not exist
```

No configured-DB JSON report was written because the configured PostgreSQL target does not yet expose the required `sensor_devices` table.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-qr-scan-event-ownership.json
```

Result: `passed=5, failed=0, total=5` in `4m35s`.

Slowest checks:

- `agriguard backend tests`: `388 passed, 2 warnings in 223.27s`
- `agriguard frontend lint`: pass
- `agriguard frontend build`: pass
- `agriguard contracts tests`: `26 passing`
- `agriguard contracts compile`: pass

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-qr-scan-event-ownership.json`

## Current Launch State

Local audit implementation is green and release-gateable against a complete schema. The configured database remains blocked on PostgreSQL schema readiness; apply/verify the AgriGuard migration chain before using this audit as live RLS rollout evidence.
