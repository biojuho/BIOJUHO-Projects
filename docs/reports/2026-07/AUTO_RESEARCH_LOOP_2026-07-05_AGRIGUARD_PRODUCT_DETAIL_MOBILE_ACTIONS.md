# AgriGuard Product Detail Mobile Actions

Date: 2026-07-05

## Loop

- Baseline measurement on `390x844`: product proof was visible, but operator actions started below the first viewport (`Add Tracking Event` top 1050 px, `Add Certification` top 1098 px).
- Variant shipped: compacted the product evidence tiles into a three-column mobile row and moved operator actions above the description inside the product detail card.
- Verifier shipped: `product_detail_browser_smoke.py` now fails mobile runs if the product QR, `Add Tracking Event`, or `Add Certification` is not visible in the first viewport.

## Browser Evidence

Standalone command:

```powershell
python apps\AgriGuard\scripts\product_detail_browser_smoke.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-product-detail-mobile-actions-compact.json --screenshot-dir var\agriguard-product-detail-mobile-actions-compact-screens --timeout-ms 30000
```

Result: pass, 22/22 checks.

Measured affordances:

| Target | Visible height | Visible ratio | Rect top-bottom |
| --- | ---: | ---: | --- |
| Product verification QR | 192 px | 1.000 | 337-529 |
| Add Tracking Event | 36 px | 1.000 | 736-772 |
| Add Certification | 36 px | 1.000 | 780-816 |

Full suite command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-product-detail-mobile-actions.json --output-dir var\agriguard-browser-smoke-suite-product-detail-mobile-actions --timeout-ms 30000
```

Result: 6/6 steps, 142/142 checks, 18/18 screenshots.

## Verification

- `npm.cmd run test -- ProductDetail`: 1 file passed, 7 tests passed.
- `python -m py_compile apps\AgriGuard\scripts\product_detail_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-product-detail-mobile-actions"`: 40 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-product-detail-mobile-actions.json`: complete, 5/5 passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-product-detail-mobile-actions.json`: complete, 9/9 passed.

## Decision

Adopted. Field operators can now reach product-detail update actions from the first mobile viewport without losing QR/proof visibility, and the browser suite guards that contract.
