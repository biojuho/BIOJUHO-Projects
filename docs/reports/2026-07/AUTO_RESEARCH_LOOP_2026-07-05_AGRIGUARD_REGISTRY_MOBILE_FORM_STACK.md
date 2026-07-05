# AutoResearch Loop: AgriGuard Registry Mobile Form Stack

Date: 2026-07-05
Scope: AgriGuard frontend registry mobile form
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch-readiness polish through browser-visible mobile form quality. The Crop Registry form forced paired fields into two columns on a 390px mobile viewport, compressing inputs and wrapping the `Requires Cold Chain` checkbox label.

## Source-Backed Pattern

The loop follows the local AutoResearch/Karpathy workflow and the refreshed upstream source reference:

- `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Verified `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Applied pattern: inspect the live screenshot, measure the DOM state, implement the smallest responsive contract change, then verify with focused tests plus browser and workspace smoke.

## Baseline

Artifacts:

- Metrics: `var/agriguard-registry-mobile-form-baseline.json`
- Screenshot: `var/agriguard-registry-mobile-form-baseline/registry-mobile-form-baseline.png`
- Original smoke screenshot: `var/agriguard-browser-smoke-suite-dashboard-kpi-status-stack/nav-screens/registry.png`

Baseline measurement on `/registry` at `390x844`:

- Document scroll width: `390`
- First paired row grid: `134px 134px`
- Second paired row grid: `134px 134px`
- Category control width: `134px`
- Origin control width: `134px`
- Harvest date control width: `134px`
- Cold-chain label height: `40px`
- Cold-chain parent width: `134px`

User impact: the mobile form looked cramped, the date input was narrow, and the cold-chain checkbox label wrapped into two lines.

## A/B Decision

Chosen variant: mobile-first single-column field groups, with two columns restored at `sm`.

- Field grids: `grid grid-cols-1 gap-6 sm:grid-cols-2`
- Cold-chain row: no mobile top offset, `sm:mt-8` only
- Cold-chain label text: `whitespace-nowrap`

Rejected alternative: smaller text or tighter gaps. The actual issue was the unconditional two-column contract, not the label copy length.

## Implementation

Files changed:

- `apps/AgriGuard/frontend/src/components/ProductRegistry.jsx`
- `apps/AgriGuard/frontend/src/components/ProductRegistry.test.jsx`

Behavioral contract added:

- `registry-product-origin-grid` asserts mobile one-column and `sm` two-column behavior.
- `registry-harvest-chain-grid` asserts mobile one-column behavior.
- `registry-cold-chain-control` keeps the desktop alignment offset without applying it on mobile.

## Variant Evidence

Artifacts:

- Metrics: `var/agriguard-registry-mobile-form-stack.json`
- Screenshot: `var/agriguard-registry-mobile-form-stack/registry-mobile-form-stack.png`
- Browser suite: `var/agriguard-browser-smoke-suite-registry-mobile-form-stack.json`
- Browser screenshots: `var/agriguard-browser-smoke-suite-registry-mobile-form-stack/`
- AgriGuard smoke: `var/workspace-smoke-agriguard-registry-mobile-form-stack.json`
- Workspace smoke: `var/workspace-smoke-registry-mobile-form-stack.json`

Post-change measurement on `/registry` at `390x844`:

- Document scroll width: `390`
- Product/origin grid: `292px`
- Harvest/chain grid: `292px`
- Category control width: `292px`
- Origin control width: `292px`
- Harvest date control width: `292px`
- Cold-chain label height: `20px`
- Cold-chain label white-space: `nowrap`
- Cold-chain mobile margin top: `0px`

The form now presents full-width mobile controls and a one-line cold-chain checkbox label without horizontal overflow.

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- ProductRegistry
```

Result: `1` test file passed, `1` test passed.

Mobile browser smoke:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-registry-mobile-form-stack.json --output-dir var\agriguard-browser-smoke-suite-registry-mobile-form-stack --timeout-ms 30000
```

Result: `6/6` steps, `135/135` checks, `18/18` screenshot artifacts.

AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-registry-mobile-form-stack.json
```

Result: `5/5` checks.

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-registry-mobile-form-stack.json
```

Result: `9/9` checks.

## Remaining Blocker

Local product hardening remains green. Production launch readiness is still externally blocked on operator-provided Firebase Admin/service-account configuration for protected admin paths.
