# AutoResearch Loop: AgriGuard Supply-Chain Mobile Heading Compact

Date: 2026-07-05
Scope: AgriGuard supply-chain mobile heading
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch-readiness polish on the operator-facing traceability path. The Supply Chain mobile page used a `text-3xl` H1 at 390px width, which wrapped `Supply Chain Overview` into two large lines and consumed extra first-viewport space before the search and first product card.

## Source-Backed Pattern

The loop follows the local AutoResearch/Karpathy workflow and the refreshed upstream source reference:

- `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Verified `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Applied pattern: measure the current mobile viewport, apply the smallest responsive text-scale change, verify with focused tests plus browser/workspace smoke, and record evidence.

## Baseline

Artifacts:

- Metrics: `var/agriguard-supply-chain-mobile-heading-baseline.json`
- Screenshot: `var/agriguard-supply-chain-mobile-heading-baseline/supply-chain-heading-baseline.png`
- Original smoke screenshot: `var/agriguard-browser-smoke-suite-cold-chain-stat-health-span/nav-screens/supply_chain.png`

Baseline measurement on `/supply-chain` at `390x844`:

- Document scroll width: `390`
- Heading text: `Supply Chain Overview`
- Heading class: `text-3xl ...`
- Heading width: `294px`
- Heading height: `72px`
- Font size: `30px`
- Line height: `36px`

User impact: the page title wrapped to two lines, reducing the first viewport available for search, pagination, and the first product card.

## A/B Decision

Chosen variant: use dashboard-style responsive heading scale.

- Mobile H1: `text-2xl leading-tight`
- Desktop/small breakpoint: `sm:text-3xl`
- H1 exposes `data-testid="supply-chain-heading"` for focused coverage.

Rejected alternative: changing the page copy. The label is clear and expected; the issue was mobile type scale.

## Implementation

Files changed:

- `apps/AgriGuard/frontend/src/components/SupplyChain.jsx`
- `apps/AgriGuard/frontend/src/components/SupplyChain.test.jsx`

Behavioral contract added:

- `supply-chain-heading` asserts `text-2xl` and `sm:text-3xl`.

## Variant Evidence

Artifacts:

- Metrics: `var/agriguard-supply-chain-mobile-heading-compact.json`
- Screenshot: `var/agriguard-supply-chain-mobile-heading-compact/supply-chain-heading-compact.png`
- Browser suite: `var/agriguard-browser-smoke-suite-supply-chain-heading-compact.json`
- Browser screenshots: `var/agriguard-browser-smoke-suite-supply-chain-heading-compact/`
- AgriGuard smoke: `var/workspace-smoke-agriguard-supply-chain-heading-compact.json`
- Workspace smoke: `var/workspace-smoke-supply-chain-heading-compact.json`

Post-change measurement on `/supply-chain` at `390x844`:

- Document scroll width: `390`
- Heading class: `max-w-full text-2xl ... sm:text-3xl`
- Heading width: `294px`
- Heading height: `30px`
- Font size: `24px`
- Line height: `30px`

The first viewport now shows a one-line heading, supporting copy, search, pagination, and a larger portion of the first product card without horizontal overflow.

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- SupplyChain
```

Result: `1` test file passed, `3` tests passed.

Mobile browser smoke:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-supply-chain-heading-compact.json --output-dir var\agriguard-browser-smoke-suite-supply-chain-heading-compact --timeout-ms 30000
```

Result: `6/6` steps, `135/135` checks, `18/18` screenshot artifacts.

AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-supply-chain-heading-compact.json
```

Result: `5/5` checks.

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-supply-chain-heading-compact.json
```

Result: `9/9` checks.

## Remaining Blocker

Local product hardening remains green. Production launch readiness is still externally blocked on operator-provided Firebase Admin/service-account configuration for protected admin paths.
