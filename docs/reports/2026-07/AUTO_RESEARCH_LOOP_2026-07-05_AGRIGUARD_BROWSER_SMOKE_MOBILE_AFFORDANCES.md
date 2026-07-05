# AgriGuard Browser Smoke Mobile Affordances

Date: 2026-07-05

## Loop

- Source refresh: `Veritas-7/autoresearch-skill-system` main/HEAD verified at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Baseline: mobile browser smoke proved route rendering, nav closure, overflow, and screenshots, but did not fail if launch-critical controls slipped below the first mobile viewport.
- Variant shipped: `apps/AgriGuard/scripts/nav_browser_smoke.py` now adds route-specific mobile first-viewport affordance checks for:
  - `/registry`: `Register Harvest` CTA fully visible.
  - `/scan`: `Verify code` CTA fully visible.
  - `/cold-chain`: `Temperature Timeline` card exposes at least 220 px.
  - `/qr-tokens`: `Product QR tokens` card exposes at least 220 px.
- Guard test: `apps/AgriGuard/backend/tests/test_smoke.py::test_nav_browser_smoke_tracks_mobile_first_viewport_affordances`.

## Browser Evidence

Command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-mobile-affordance-checks.json --output-dir var\agriguard-browser-smoke-suite-mobile-affordance-checks --timeout-ms 30000
```

Result: 6/6 steps, 139/139 checks, 18/18 screenshots.

Measured mobile affordances from `var/agriguard-browser-smoke-suite-mobile-affordance-checks/nav.json`:

| Route | Check | Visible height | Visible ratio | Rect top-bottom |
| --- | --- | ---: | ---: | --- |
| `/registry` | `register_harvest_cta_first_viewport` | 40 px | 1.000 | 775-815 |
| `/scan` | `verify_code_cta_first_viewport` | 36 px | 1.000 | 797-833 |
| `/cold-chain` | `temperature_timeline_card_first_viewport` | 256 px | 0.670 | 588-970 |
| `/qr-tokens` | `product_qr_tokens_card_first_viewport` | 242 px | 0.631 | 602-986 |

## Verification

- `python -m py_compile apps\AgriGuard\scripts\nav_browser_smoke.py apps\AgriGuard\backend\tests\test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-nav-affordances"`: 39 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-mobile-affordance-checks.json`: complete, 5/5 passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-mobile-affordance-checks.json`: complete, 9/9 passed.

## Decision

Adopted. The browser smoke suite now fails closed on the mobile affordances that were improved in the previous UI loops, so future launch checks catch first-viewport regressions instead of relying on manual screenshot review.
