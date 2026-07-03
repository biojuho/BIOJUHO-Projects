# AgriGuard Product Paging and Visibility - AutoResearch Loop

Date: 2026-07-03

## Decision

Adopt server-side product paging, owner-scoped product visibility, and QR-token issuance at product creation.

This is the operator-facing counterpart to the QR admin surfaces: Supply Chain should not render every product client-side, regular users should not see or mutate other owners' products, and newly created products should receive non-guessable public QR label tokens instead of product IDs.

## Product Work

- Added `/products/page` with page metadata and search over product ID, name, and origin.
- Scoped product list, detail, history, tracking, and certification routes through owner visibility unless the user has a global operator role.
- Blocked regular users from creating products for another owner.
- Issued hashed QR tokens on product creation and stored public label URLs using `PUBLIC_VERIFY_BASE_URL` when configured.
- Updated Supply Chain to consume paginated backend data, reset search to page 1, and keep status flow rendering stable.
- Added focused backend and frontend tests for paging, owner visibility, QR issuance, and Supply Chain pagination.

## Verification

- `uv run ... pytest tests/test_product_visibility_and_paging.py -q`: 4 passed, 1 warning.
- `npm run test -- SupplyChain`: 1 file passed, 3 tests passed.
- `npm run lint`: passed.
- `npm run build:lts`: passed.
- `npm run check:bundle`: passed, max chunk under threshold.
- Browser nav smoke against `VITE_API_URL=http://127.0.0.1:8102`: 47/47 passed, `var/agriguard-nav-browser-smoke-product-paging.json`.
- Workspace smoke `--scope agriguard`: 5/5 passed, `var/workspace-smoke-agriguard-product-paging.json`.

## Notes

- QR KPI schemas/tests remain separate dirty-tree work and were intentionally not staged here.
- The default frontend build was restored after the smoke-backend browser build.
