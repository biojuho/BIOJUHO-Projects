# AutoResearch Loop: AgriGuard Dashboard KPI Status Stack

Date: 2026-07-05
Scope: AgriGuard frontend dashboard mobile polish
Branch: `feat/shared-llm-modernization-2026-06-19`

## Objective

Continue launch-readiness hardening with a small browser-visible improvement. The prior mobile dashboard proof showed the QR KPI warning badges wrapping `Below target` across two lines on narrow viewports, which made the KPI cards harder to scan.

## Source-Backed Pattern

The loop follows the local AutoResearch/Karpathy workflow and the refreshed upstream source reference:

- `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Verified `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Applied pattern: measure a visible UX defect, change the smallest component contract, verify with focused tests plus browser smoke, and record durable evidence.

## Baseline

Evidence inspected:

- Screenshot: `var/agriguard-browser-smoke-suite-dashboard-mobile-header/nav-screens/dashboard.png`
- Route: `http://127.0.0.1:5176/`
- Viewport: `393x851`
- Document scroll width: `393`

Pre-change browser measurement:

- `Below target` badge count: `2`
- Badge heights: `38px`, `38px`
- Badge white-space: `normal`
- Badge classes lacked `whitespace-nowrap` and `shrink-0`

User impact: both amber KPI status badges rendered as two-line pills inside already dense mobile metric cards.

## A/B Decision

Chosen variant: stack each KPI card's mobile summary row and keep desktop as a row.

- Mobile summary wrapper: `flex flex-col items-start gap-3`
- Desktop summary wrapper: `sm:flex-row sm:items-center sm:justify-between`
- Status badge: `whitespace-nowrap shrink-0`

Rejected alternative: only adding `whitespace-nowrap` to the badge. The card header was too narrow for the title/value block and status pill to reliably share one row, so a row-only layout could trade text wrapping for cramped alignment.

## Implementation

Files changed:

- `apps/AgriGuard/frontend/src/components/dashboard/Dashboard.jsx`
- `apps/AgriGuard/frontend/src/components/dashboard/Dashboard.test.jsx`

Behavioral contract added:

- `qr-kpi-scan-success-summary` and `qr-kpi-daily-scan-summary` expose the mobile/desktop flex contract.
- `qr-kpi-scan-success-status` and `qr-kpi-daily-scan-status` expose no-wrap, non-shrinking status badges.

## Variant Evidence

Artifacts:

- Metrics: `var/agriguard-dashboard-mobile-kpi-status-stack.json`
- Screenshot: `var/agriguard-dashboard-mobile-kpi-status-stack/dashboard-kpi-status-mobile.png`
- Browser suite: `var/agriguard-browser-smoke-suite-dashboard-kpi-status-stack.json`
- Browser screenshots: `var/agriguard-browser-smoke-suite-dashboard-kpi-status-stack/`
- AgriGuard smoke: `var/workspace-smoke-agriguard-dashboard-kpi-status-stack.json`
- Workspace smoke: `var/workspace-smoke-dashboard-kpi-status-stack.json`

Post-change browser measurement:

- Viewport width: `393`
- Document scroll width: `393`
- Scan summary flex direction: `column`
- Daily summary flex direction: `column`
- Scan status: `117px x 22px`, `white-space: nowrap`, `flex-shrink: 0`
- Daily status: `117px x 22px`, `white-space: nowrap`, `flex-shrink: 0`

The mobile screenshot now shows each amber `Below target` pill as a single-line status below the KPI value without introducing horizontal overflow.

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- Dashboard
```

Result: `1` test file passed, `4` tests passed.

Mobile browser smoke:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-dashboard-kpi-status-stack.json --output-dir var\agriguard-browser-smoke-suite-dashboard-kpi-status-stack --timeout-ms 30000
```

Result: `6/6` steps, `135/135` checks, `18/18` screenshot artifacts.

AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dashboard-kpi-status-stack.json
```

Result: `5/5` checks.

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-dashboard-kpi-status-stack.json
```

Result: `9/9` checks.

## Remaining Blocker

Local product hardening remains green. Production launch readiness is still externally blocked on operator-provided Firebase Admin/service-account configuration for protected admin paths.
