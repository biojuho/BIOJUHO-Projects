# AgriGuard Auto-Research Loop - Product ID Copy

Date: 2026-07-06

## Source Refresh

- External source refresh: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` returned `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Modernization radar: `var/github-modernization-radar-auto-research-agriguard-continue-2-2026-07-06.json` and `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUE_2_2026-07-06.md`.
- Radar status: 8 sources valid, 8 adopted, 0 partially adopted, 0 watch.

## Visual Finding

The mobile product detail card showed the product ID as a bare long identifier without a direct copy action.

- Baseline screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-timeline-labels-mobile/product-detail-screens/product-detail-initial.png`.
- Operators investigating QR scans or support cases had to manually select or transcribe the product ID.

## Change

- Added a compact copy-ID icon button beside the selectable product ID in `apps/AgriGuard/frontend/src/components/ProductDetail.jsx`.
- Kept the product ID wrapped and selectable for manual inspection.
- Preserved the mobile first viewport by using an icon button and changing the operator action strip to a two-column mobile grid.
- Updated `apps/AgriGuard/scripts/product_detail_browser_smoke.py` to require the product ID copy action in the mobile first viewport.
- Extended `apps/AgriGuard/frontend/src/components/ProductDetail.test.jsx` to cover clipboard behavior and the mobile action strip layout.
- Updated `apps/AgriGuard/backend/tests/test_smoke.py` for the new browser-smoke target.

## Implementation Note

An intermediate browser smoke caught the first version as a mobile layout regression:

- Failed JSON: `var/agriguard-product-detail-id-copy-mobile-2026-07-06.json`.
- Cause: a full-width `Copy ID` button pushed `Add Certification` below the 390x844 first viewport.
- Final fix: use an aria-labelled icon button and two-column operator actions.

## Verification

- `npm.cmd test -- ProductDetail.test.jsx`: 1 file, 8 tests passed.
- `npx.cmd eslint src/components/ProductDetail.jsx src/components/ProductDetail.test.jsx`: passed.
- Product detail mobile browser smoke: `var/agriguard-product-detail-id-copy-mobile-2026-07-06.json`, 24 checks passed, 0 failed.
- After screenshot: `var/agriguard-product-detail-id-copy-mobile-2026-07-06/product-detail-initial.png`.
- Full frontend suite: `npm.cmd test -- --run`, 18 files, 94 tests passed.
- Smoke-script tests: `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`, 56 tests passed.
- Desktop aggregate browser smoke: `var/agriguard-browser-smoke-suite-2026-07-06-product-id-copy-desktop.json`, 7/7 steps, 168/168 checks, 19/19 screenshots passed.
- Mobile aggregate browser smoke: `var/agriguard-browser-smoke-suite-2026-07-06-product-id-copy-mobile.json`, 7/7 steps, 183/183 checks, 19/19 screenshots passed.
- Workspace smoke: `var/workspace-smoke-agriguard-2026-07-06-product-id-copy.json`, 5/5 checks passed.

## Remaining Launch Blocker

Strict guarded launch is still externally blocked by the missing Firebase Admin service-account file:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
