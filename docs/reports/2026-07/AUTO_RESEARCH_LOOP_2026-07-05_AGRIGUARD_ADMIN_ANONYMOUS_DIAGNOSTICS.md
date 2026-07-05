# AgriGuard Admin Anonymous Diagnostics

Date: 2026-07-05

## Loop

- Baseline: `admin_routes_browser_smoke.py` attached console, request-failure, and page-error diagnostics only to the authenticated admin page. The anonymous missing-token QR-token and sensor probes were exercised, but their browser diagnostics were not captured.
- Variant shipped: shared diagnostics now attach to both anonymous and authenticated Playwright pages.
- Expected-noise rule: the two deliberate missing-token probes are expected to emit browser console `401 (Unauthorized)` resource errors; the smoke now records exactly two expected auth console messages while still failing unexpected console errors.

## Browser Evidence

Standalone command:

```powershell
python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --mobile --json-out var\agriguard-admin-routes-mobile-diagnostics-fixed.json --screenshot-dir var\agriguard-admin-routes-mobile-diagnostics-fixed-screens --timeout-ms 30000
```

Result: pass, 17/17 checks.

Diagnostics:

- `expected_missing_auth_console_errors`: 2 expected `401 (Unauthorized)` console messages.
- `no_console_errors`: passed with `[]` unexpected console errors.
- `no_request_failures`: passed.
- `no_page_errors`: passed.

Full suite command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-admin-diagnostics.json --output-dir var\agriguard-browser-smoke-suite-admin-diagnostics --timeout-ms 30000
```

Result: 6/6 steps, 151/151 checks, 18/18 screenshots, no screenshot dimension failures.

## Verification

- `python -m py_compile apps\AgriGuard\scripts\admin_routes_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-admin-diagnostics-fixed"`: 46 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-admin-diagnostics.json`: complete, 5/5 passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-admin-diagnostics.json`: complete, 9/9 passed.

## Decision

Adopted. Missing-token admin routes now have the same browser diagnostics as authenticated routes, with expected auth-denial console output explicitly classified instead of silently ignored.
