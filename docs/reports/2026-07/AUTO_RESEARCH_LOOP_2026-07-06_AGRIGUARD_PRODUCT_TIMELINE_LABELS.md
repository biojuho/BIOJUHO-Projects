# AgriGuard Auto-Research Loop - Product Timeline Labels

Date: 2026-07-06

## Source Refresh

- External source refresh: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` returned `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Modernization radar: `var/github-modernization-radar-auto-research-agriguard-continue-2-2026-07-06.json` and `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUE_2_2026-07-06.md`.
- Radar status: 8 sources valid, 8 adopted, 0 partially adopted, 0 watch.

## Visual Finding

The mobile product detail route exposed chain event internals in the operator timeline:

- Baseline screenshot: `var/agriguard-browser-smoke-suite-2026-07-06-coldchain-empty-state-mobile/product-detail-screens/product-detail-final.png`.
- The event card rendered raw values such as `IN_TRANSIT` and an ISO timestamp (`2026-07-05T23:47:51...+00:00`) under a localized event date.
- This made the chain evidence feel like backend data instead of an operator-facing launch workflow.

## Change

- Added product timeline formatters in `apps/AgriGuard/frontend/src/components/ProductTimeline.jsx`.
- Rendered history action/status enums as readable labels, including `REGISTER`/`REGISTERED` as `Registered` and `IN_TRANSIT` as `In Transit`.
- Localized timestamp-like timeline data values with `toLocaleString('ko-KR')`.
- Preserved selectable monospace formatting for machine identifiers such as handler IDs and transaction hashes.
- Updated `apps/AgriGuard/scripts/product_detail_browser_smoke.py` so browser evidence asserts the human label and fails if the raw tracking status leaks back into the timeline.
- Extended `apps/AgriGuard/frontend/src/components/ProductDetail.test.jsx` to cover raw enum and ISO timestamp formatting.

## Verification

- `npm.cmd test -- ProductDetail.test.jsx`: 1 file, 7 tests passed.
- `npx.cmd eslint src/components/ProductTimeline.jsx src/components/ProductDetail.test.jsx`: passed.
- Product detail mobile browser smoke: `var/agriguard-product-detail-timeline-labels-mobile-2026-07-06.json`, 23 checks passed, 0 failed.
- After screenshot: `var/agriguard-product-detail-timeline-labels-mobile-2026-07-06/product-detail-final.png`.
- Full frontend suite: `npm.cmd test -- --run`, 18 files, 93 tests passed.
- Smoke-script tests: `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`, 56 tests passed.
- Desktop aggregate browser smoke: `var/agriguard-browser-smoke-suite-2026-07-06-timeline-labels-desktop.json`, 7/7 steps, 168/168 checks, 19/19 screenshots passed.
- Mobile aggregate browser smoke: `var/agriguard-browser-smoke-suite-2026-07-06-timeline-labels-mobile.json`, 7/7 steps, 182/182 checks, 19/19 screenshots passed.
- Workspace smoke: `var/workspace-smoke-agriguard-2026-07-06-timeline-labels.json`, 5/5 checks passed.

## Remaining Launch Blocker

Strict guarded launch is still externally blocked by the missing Firebase Admin service-account file:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
