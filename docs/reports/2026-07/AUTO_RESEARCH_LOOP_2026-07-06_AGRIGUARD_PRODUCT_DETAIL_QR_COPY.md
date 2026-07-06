# Auto Research Loop - AgriGuard Product Detail QR Copy

Date: 2026-07-06

## Source Refresh

- Upstream reference refresh: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Current upstream `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar refresh:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-product-detail-qr-copy-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_PRODUCT_DETAIL_QR_COPY_2026-07-06.md`
  - Result: valid radar with 8 sources, 8 adopted, 0 partially adopted, 0 watch.

## Finding

The product detail page displayed the public verify label below the QR image, but only the product ID had a copy action. Operators who open a batch detail page after registration still had to manually select the public verify label before printing, sharing, or checking it.

## Change

- Added a compact copy icon to the product detail QR card.
- The action copies `product.qr_code` and falls back to the product ID when no public label is present.
- Added accessible copied/failure state via the button label and title.
- Added component coverage for copying the public verify label from the QR card.
- Extended `product_detail_browser_smoke.py` to require the QR-label copy action in the first mobile viewport and click it through to copied state.
- Updated the backend smoke expectation for the product-detail mobile first-viewport contract.

## Verification

- `npm.cmd test -- ProductDetail.test.jsx`
  - Result: 1 file passed, 9 tests passed.
- `npx.cmd eslint src/components/ProductDetail.jsx src/components/ProductDetail.test.jsx`
  - Result: passed.
- `python -m py_compile apps/AgriGuard/scripts/product_detail_browser_smoke.py`
  - Result: passed.
- Product detail mobile browser smoke through the same-origin Vite `/api` proxy:
  - Evidence: `var/agriguard-product-detail-qr-copy-mobile-2026-07-06.json`
  - Screenshots: `var/agriguard-product-detail-qr-copy-mobile-2026-07-06/`
  - Result: pass, 28 checks, 0 failed.
  - QR copy checks passed: `public_verify_label_copy_action_first_viewport`, `public_verify_label_copy_action_visible`, `public_verify_label_copy_action_enabled`, `public_verify_label_copy_action_copied_state`.
- Full frontend test suite:
  - `npm.cmd test -- --run`
  - Result: 18 files passed, 96 tests passed.
- Backend smoke:
  - `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`
  - Result: 56 passed.
- Workspace smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-product-detail-qr-copy.json`
  - Result: complete, 5/5 passed, 0 unexpected failures.

## Remaining Launch Blocker

Strict launch readiness is still externally blocked until a real Firebase Admin service-account file is present for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. This change does not weaken that gate.
