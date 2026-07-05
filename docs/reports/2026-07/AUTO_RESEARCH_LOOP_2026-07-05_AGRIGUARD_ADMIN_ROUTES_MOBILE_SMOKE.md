# AgriGuard Admin Routes Mobile Smoke

Date: 2026-07-05

## Loop

- External source refresh: `Veritas-7/autoresearch-skill-system` main/HEAD observed at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Baseline: `run_browser_smoke_suite.py --mobile` passed mobile mode to dashboard, nav, supply-chain, and product-detail children, but the authenticated `admin_routes_browser_smoke.py` child still hard-coded `1440x960`.
- Variant shipped: `admin_routes_browser_smoke.py` now supports `--mobile` and `--viewport`, records viewport metadata, and adds no-horizontal-overflow checks for missing-token and authenticated QR-token/sensor routes.
- Suite wiring: `run_browser_smoke_suite.py --mobile` now passes `--mobile` to the admin routes child.

## Browser Evidence

Standalone command:

```powershell
python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --mobile --json-out var\agriguard-admin-routes-mobile-smoke.json --screenshot-dir var\agriguard-admin-routes-mobile-smoke-screens --timeout-ms 30000
```

Result: pass, 16/16 checks, viewport `390x844`.

Recorded widths:

| Path | Scroll width | Client width | Scroll height |
| --- | ---: | ---: | ---: |
| QR tokens missing token | 390 | 390 | 1097 |
| Sensor devices missing token | 390 | 390 | 4210 |
| Authenticated QR tokens | 390 | 390 | 2443 |
| Authenticated sensor devices | 390 | 390 | 6300 |

Full suite command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-admin-mobile.json --output-dir var\agriguard-browser-smoke-suite-admin-mobile --timeout-ms 30000
```

Result: 6/6 steps, 150/150 checks, 18/18 screenshots.

## Verification

- `python -m py_compile apps\AgriGuard\scripts\admin_routes_browser_smoke.py apps\AgriGuard\scripts\run_browser_smoke_suite.py apps\AgriGuard\backend\tests\test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-admin-mobile-smoke"`: 42 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-admin-mobile.json`: complete, 5/5 passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-admin-mobile.json`: complete, 9/9 passed.

## Decision

Adopted. The aggregate mobile browser suite now actually exercises authenticated QR-token and sensor admin workflows at phone dimensions instead of relying on desktop-only evidence.
