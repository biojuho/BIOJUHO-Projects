# Dashboard Falsy Credential Metadata Guard

Generated at: `2026-06-05T10:55:00+09:00`

## Source Signal

- Repository: `deepset-ai/haystack`
- Pull request: `https://github.com/deepset-ai/haystack/pull/11412`
- Merge commit: `https://github.com/deepset-ai/haystack/commit/dd5efef`
- Upstream signal: `meta_fields_to_embed` used truthiness checks that dropped
  valid metadata values such as `0`, `False`, and empty strings. The upstream
  patch changed those guards to skip only absent or explicit `None` values.

## Local Mapping

The dashboard credential-boundary API normalizes redacted operator reports into
the `/api/quality_overview` payload. That surface should preserve meaningful
falsy operator metadata from checked-in JSON artifacts instead of replacing it
with fallback labels or counts.

## A/B Contract

- Baseline: dashboard credential-boundary normalization mixed truthiness
  fallbacks with explicit defaults. In particular, the next-unblock title used a
  truthiness fallback, so an intentionally empty title could be replaced by the
  boundary id.
- Variant: add helper-based field normalization that falls back only when a
  value is missing or `None`, then apply it to credential boundary, live plan,
  next-unblock, and operator-checklist metadata.
- Primary KPI: `/api/quality_overview` preserves `0`, `False`, and empty string
  values in a synthetic credential report fixture.
- Guardrails: existing dashboard credential-boundary API fixtures still pass,
  the live dashboard route still renders the existing operator checklist, and no
  credential values are emitted.
- Decision: adopted.

## Changed Files

- `apps/dashboard/routers/gdt.py`
  - Adds `_present_value`, `_text_field`, `_int_field`, and `_bool_field`.
  - Applies the helpers to credential boundary, live plan, next-unblock, and
    operator-checklist response construction.
- `tests/test_dashboard_api.py`
  - Adds `test_preserves_falsy_credential_metadata_values`.
- `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_FALSY_METADATA_2026-06-05.*`
  - Dashboard browser smoke artifact for the real Quality panel route.

## Verification

- `python -m pytest tests\test_dashboard_api.py -q --tb=line`
  - `52 passed`
- `python -m py_compile apps\dashboard\routers\gdt.py`
  - passed
- `git diff --check -- apps\dashboard\routers\gdt.py tests\test_dashboard_api.py`
  - passed with only the expected Windows CRLF warnings
- `python ops\scripts\dev_server_control.py start --target dashboard-frontend --wait-ready`
  - `dev server ready: dashboard-frontend`
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --timeout 45 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_FALSY_METADATA_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_FALSY_METADATA_2026-06-05.md`
  - pass: `1/1` route, failed=`0`

## Notes

- The first browser-smoke attempt failed because the dashboard API dependency
  was not running; after starting the managed dashboard target, the same smoke
  passed and overwrote the failure artifact.
- `global_objective_complete=false`
