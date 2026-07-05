# AgriGuard QR Public First Viewport

Date: 2026-07-05

## Loop

- Baseline: `qr_path_browser_smoke.py` verified the public QR journey content and overflow behavior, but did not fail if key public proof cards dropped below the first mobile viewport.
- Variant shipped: the QR path smoke now measures the valid public verification page and fails mobile-sized runs unless Origin, Batch, Temperature, and Last verified cards are fully visible in the first viewport.
- Scope: verifier-only hardening; the current UI already met the target.

## Browser Evidence

Standalone command:

```powershell
python apps\AgriGuard\scripts\qr_path_browser_smoke.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var\agriguard-qr-path-public-first-viewport.json --screenshot-dir var\agriguard-qr-path-public-first-viewport-screens --timeout-ms 30000
```

Result: 26/26 passed.

Measured public summary cards:

| Target | Visible height | Visible ratio | Rect top-bottom |
| --- | ---: | ---: | --- |
| Origin | 66 px | 1.000 | 363-429 |
| Batch | 66 px | 1.000 | 441-507 |
| Temperature | 86 px | 1.000 | 519-605 |
| Last verified | 66 px | 1.000 | 617-683 |

Full suite command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-qr-public-first-viewport.json --output-dir var\agriguard-browser-smoke-suite-qr-public-first-viewport --timeout-ms 30000
```

Result: 6/6 steps, 146/146 checks, 18/18 screenshots.

## Verification

- `python -m py_compile apps\AgriGuard\scripts\qr_path_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-qr-public-first-viewport"`: 41 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-qr-public-first-viewport.json`: complete, 5/5 passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-qr-public-first-viewport.json`: complete, 9/9 passed.

## Decision

Adopted. The public QR path now has a measured first-viewport proof-density gate for the mobile consumer view.
