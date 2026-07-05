# AutoResearch Loop: AgriGuard Product Detail Mobile Summary

Date: 2026-07-05

## Source Check

- Skill used: `AutoResearch Karpathy Loop`
- External pattern check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Verified source revision: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Target

The Product Detail page preserved QR readability, but the mobile top card used desktop padding and section gaps. On a 390 x 844 viewport, Harvest Date was only partially visible below the fold.

## A/B Result

Baseline, before variant:

- Viewport: `390 x 844`
- Page width: `scrollWidth=390`
- Top product card: `top=144`, `bottom=1170`, `height=1026`
- QR card: `top=376`, `bottom=642`, `height=266`, `width=292`
- Origin card: `top=707`, `bottom=783`, `height=76`
- Harvest card: `top=807`, `bottom=883`, `height=76`
- Harvest Date fully visible: `false`

Variant, after compact mobile top card:

- Viewport: `390 x 844`
- Page width: `scrollWidth=390`
- Top product card: `top=144`, `bottom=1018`, `height=874`
- QR card: `top=332`, `bottom=590`, `height=258`, `width=324`
- Origin card: `top=631`, `bottom=699`, `height=68`
- Harvest card: `top=711`, `bottom=779`, `height=68`
- Cold Chain card: `top=791`, `bottom=859`, `height=68`
- Harvest Date fully visible: `true`
- Cold Chain visible in first viewport: `true`
- Horizontal overflow: `false`

The top card became 152 px shorter while the QR itself kept the same rendered size.

## Implementation

- Reduced Product Detail top card padding on mobile and restored desktop padding at `sm`.
- Reduced mobile gap around the QR panel and evidence grid.
- Reduced mobile padding inside the traceability evidence cards.
- Added explicit test IDs for the product card content, QR card content, and evidence grid.
- Added focused unit assertions for the mobile spacing contract.

## Evidence

- Focused test: `npm.cmd run test -- ProductDetail`
  - Result: `1 passed`, `7 passed`
- Measurement screenshot: `var\agriguard-product-detail-mobile-compact-summary\product-detail-compact-summary.png`
- Mobile browser suite: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-product-detail-mobile-compact-summary.json --output-dir var\agriguard-browser-smoke-suite-product-detail-mobile-compact-summary --timeout-ms 30000`
  - Result: `6 / 6` steps, `135 / 135` checks, `18 / 18` screenshots
- AgriGuard smoke: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-product-detail-mobile-compact-summary.json`
  - Result: `5 / 5`
- Workspace smoke: `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-product-detail-mobile-compact-summary.json`
  - Result: `9 / 9`

## Remaining External Blocker

This loop improves local launch readiness. Protected production operator paths still require the real Firebase Admin/service-account/operator token configuration before a production launch can be called complete.
