# AgriGuard Admin Viewport Screenshots

Date: 2026-07-05

## Loop

- Baseline: after enabling mobile admin smoke, screenshots for `admin_routes_browser_smoke.py` still used full-page capture. On mobile pages with fixed navigation, full-page images can show fixed UI in misleading positions and make evidence harder to inspect.
- Variant shipped: admin browser smoke keeps desktop full-page screenshots, but captures mobile screenshots as the actual `390x844` viewport.
- Guard test: `test_admin_routes_browser_smoke_uses_viewport_screenshots_on_mobile` locks mobile `full_page=False` and desktop `full_page=True`.

## Browser Evidence

Standalone command:

```powershell
python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --mobile --json-out var\agriguard-admin-routes-mobile-viewport-screens.json --screenshot-dir var\agriguard-admin-routes-mobile-viewport-screens --timeout-ms 30000
```

Result: pass.

Mobile screenshots are viewport-sized:

| Screenshot | Size |
| --- | --- |
| `qr-tokens-missing-token.png` | 390x844 |
| `qr-tokens.png` | 390x844 |
| `sensor-devices-missing-token.png` | 390x844 |
| `sensor-devices.png` | 390x844 |

Full suite command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-admin-viewport-screens.json --output-dir var\agriguard-browser-smoke-suite-admin-viewport-screens --timeout-ms 30000
```

Result: 6/6 steps, 150/150 checks, 18/18 screenshots.

## Verification

- `python -m py_compile apps\AgriGuard\scripts\admin_routes_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-admin-viewport-screens"`: 43 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-admin-viewport-screens.json`: complete, 5/5 passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-admin-viewport-screens.json`: complete, 9/9 passed.

## Decision

Adopted. Mobile admin screenshots now reflect the actual operator viewport while desktop evidence keeps full-page coverage.
