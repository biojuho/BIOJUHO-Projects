# AutoResearch Loop - AgriGuard Product Timeline Wrap

Date: 2026-07-05

## Objective

Continue public launch-readiness hardening for AgriGuard by improving the mobile product detail timeline after a QR scan opens a product history page.

## Source Pattern

- External reference checked this loop: `Veritas-7/autoresearch-skill-system`
- Refreshed upstream commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local skill used: `D:\AI project\.agents\skills\auto-research-karpathy\SKILL.md`

## Baseline

The product detail route passed browser smoke, but mobile inspection showed two issues in the blockchain history card:

- Long metadata values used `truncate`, hiding route and handler evidence.
- The footer rendered `Verify Link` as a pointer-styled `span` with no `href`.

Baseline evidence:

- Screenshot: `var\agriguard-browser-smoke-suite-coldchain-stat-wrap\product-detail-screens\product-detail-final.png`
- DOM metrics: `var\agriguard-product-timeline-mobile-baseline.json`
- `TX` line baseline: `white-space=nowrap`, `overflow=hidden`, `text-overflow=ellipsis`
- Fake verify control baseline: `SPAN`, text `Verify Link`, `href=null`, `cursor=pointer`

This was a launch-readiness issue because the post-scan detail page is public proof-of-origin UI. It should not hide evidence fields or imply an external verifier link where no explorer URL exists.

## A/B Decision

- Variant A: keep truncating long timeline values and keep the non-functional `Verify Link` span.
- Variant B: wrap/select timeline values and TX hashes on mobile, render a real `Verify link` anchor only when an explorer URL exists, otherwise render non-clickable `TX recorded` status.

Adopted Variant B.

Implementation details:

- `apps/AgriGuard/frontend/src/components/ProductTimeline.jsx`
  - Adopted the current ProductTimeline card/timeline presentation as the tested product-detail surface for this cycle.
  - Replaced metadata `truncate` values with wrapping/selectable values.
  - Changed the TX footer to wrap and remain selectable.
  - Removed fake clickable `Verify Link` when no explorer URL is present.
  - Added optional support for `block.explorer_url` or `data.explorer_url`.
- `apps/AgriGuard/frontend/src/components/ProductDetail.test.jsx`
  - Added assertions that metadata and TX values use wrapping classes instead of truncation.
  - Added coverage for no-explorer `TX recorded` status.
  - Added coverage that an explorer URL renders a real anchor.

## Adopted Variant Evidence

Live mobile proof:

- Metrics JSON: `var\agriguard-product-timeline-mobile-footer.json`
- Screenshot: `var\agriguard-product-timeline-mobile-footer\timeline-mobile-wrapped-fields.png`

Observed metrics:

- `viewportWidth`: `390`
- `documentScrollWidth`: `390`
- sampled `timeline-data-value-*` entries: `whiteSpace=normal`, `overflow=visible`, `textOverflow=clip`
- `txClass`: `min-w-0 break-all text-[10px] font-mono text-slate-500 select-all group-hover:text-slate-400 transition-colors`
- `txWhiteSpace`: `normal`
- `txOverflow`: `visible`
- `txTextOverflow`: `clip`
- `statusText`: `TX recorded`
- `verifyLinkTextCount`: `0`

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- ProductDetail
```

Result:

- `1 passed`
- `7 passed`

Mobile browser suite:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-product-timeline-wrap.json --output-dir var\agriguard-browser-smoke-suite-product-timeline-wrap --timeout-ms 30000
```

Result:

- `6/6` flows passed
- `135/135` checks passed
- `18/18` screenshot artifacts passed

Canonical AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-product-timeline-wrap.json
```

Result:

- `5/5` checks passed
- elapsed `5m58s`

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-product-timeline-wrap.json
```

Result:

- `9/9` checks passed
- elapsed `2m45s`

## Remaining External Blocker

Local product hardening and verification are green for this loop. Full launch readiness still remains externally blocked on the Firebase Admin service account / operator token environment needed for production-grade protected admin paths.
