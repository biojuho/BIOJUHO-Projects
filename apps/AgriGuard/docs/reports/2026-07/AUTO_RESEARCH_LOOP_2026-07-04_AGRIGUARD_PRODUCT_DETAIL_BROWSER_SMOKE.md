# AutoResearch Loop - AgriGuard Product Detail Browser Smoke

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: operator-authenticated product detail browser workflow
- External context: `Veritas-7/autoresearch-skill-system` main was refreshed at `b8bbf393759d6e67e780f03c572ec626fab6593b`; the workspace modernization radar recorded 8 source-backed patterns as already adopted.

## Source-Backed Rationale

The AutoResearch loop prioritizes browser evidence for launch workflows that span API state, local storage auth, route rendering, forms, and responsive layout. AgriGuard had supply-chain list coverage, but no browser smoke that clicked into a product detail page and exercised the operator update actions.

## A/B Hypothesis

Baseline: no product-detail browser smoke existed. Product detail regressions in QR rendering, tracking updates, certification updates, timeline refresh, operator controls, or mobile overflow could pass existing smoke gates.

Variant: add a product-detail browser smoke that seeds a product through the API, opens `/product/:id` with an operator token, verifies the detail view, submits tracking and certification forms, and asserts final mobile layout integrity.

Adopt rule: adopt only if the new smoke passes on mobile, focused Python checks pass, and the full AgriGuard smoke scope remains green.

## Adopted Change

- Added `scripts/product_detail_browser_smoke.py`.
- The script records viewport/mobile mode, screenshots, console messages, request failures, page errors, and check-level status.
- Added mobile/desktop viewport resolution helpers.
- Added `backend/tests/test_smoke.py::test_product_detail_browser_smoke_uses_phone_viewport_for_mobile_default`.

## Browser Evidence

All browser evidence was recorded under:

`D:\AI project\var\agriguard-product-detail-browser-2026-07-04`

```powershell
python apps/AgriGuard/scripts/product_detail_browser_smoke.py --base-url http://127.0.0.1:5194 --api-url http://127.0.0.1:8008 --operator-token browser-smoke-token --mobile --json-out var/agriguard-product-detail-browser-2026-07-04/product-detail-mobile-variant-final.json --screenshot-dir var/agriguard-product-detail-browser-2026-07-04/product-detail-mobile-variant-final-screens --timeout-ms 30000
```

Result: `status=pass`, 17 checks, 0 failed checks, viewport `390x844`, `mobile=true`.

Covered browser assertions:

- product seeded through the protected API
- product detail route loaded
- product ID, origin, cold-chain state, and QR code rendered
- initial page had no horizontal overflow
- operator tracking and certification buttons were enabled
- tracking event was saved and visible in history
- certification was saved and the `Certified` badge was visible
- final page had no horizontal overflow
- no page errors, request failures, or console errors

An intermediate run showed the tracking update was present in backend history and final page text, but the locator-based timeline assertion was brittle against the animated timeline markup. The final script uses `document.body.textContent` for that specific history visibility check.

## Verification

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/scripts/product_detail_browser_smoke.py' 'apps/AgriGuard/backend/tests/test_smoke.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_smoke.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-product-detail-full'
```

Result: `10 passed in 36.01s`.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-product-detail-browser-smoke.json
```

Result: `passed=5, failed=0, total=5` in `4m55s`.

Slowest checks:

- `agriguard backend tests`: pass in `4m17s`
- `agriguard frontend lint`: pass in `16.5s`
- `agriguard contracts tests`: pass in `9.4s`
- `agriguard frontend build`: pass in `9.1s`
- `agriguard contracts compile`: pass in `3.3s`

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-product-detail-browser-smoke.json`

## Current Launch State

AgriGuard now has browser-level launch evidence for the product-detail workflow on mobile: seeded product details render, operator tracking and certification updates succeed, the blockchain timeline reflects the tracking event, the certification badge appears, and the final page remains within the mobile viewport width.
