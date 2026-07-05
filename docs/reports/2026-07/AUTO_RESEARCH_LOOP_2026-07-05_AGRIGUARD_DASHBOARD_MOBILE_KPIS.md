# AutoResearch Loop: AgriGuard Dashboard Mobile KPIs

Date: 2026-07-05

## Source Check

- Skill used: `AutoResearch Karpathy Loop`
- External pattern check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Verified source revision: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Target

The Dashboard mobile first viewport showed the Consumer QR KPI strip, but the strip was narrow and tall because the page used desktop padding and the KPI cards used desktop card spacing on mobile. The 7-day trend was only barely visible.

## A/B Result

Baseline, before variant:

- Viewport: approximately `393 x 851`
- Page width: `scrollWidth=393`
- KPI strip: `top=208`, `bottom=879`, `height=671`, `width=294`
- QR scan success card: `height=176`
- Consumer scans today card: `height=180`
- 7-day trend: `top=727`, `bottom=854`, `height=127`
- Trend visible height: `124 px`

Variant, after compact mobile KPI spacing:

- Viewport: `390 x 844`
- Page width: `scrollWidth=390`
- KPI strip: `top=184`, `bottom=763`, `height=579`, `width=326`
- QR scan success card: `height=152`
- Consumer scans today card: `height=152`
- 7-day trend: `top=623`, `bottom=746`, `height=123`
- Trend visible height: `123 px`
- Horizontal overflow: `false`

The KPI strip became 32 px wider, 92 px shorter, and the complete 7-day trend section is visible inside the first mobile viewport.

## Implementation

- Changed Dashboard page padding to mobile-first `px-4 py-5` with desktop spacing restored at `sm`.
- Reduced mobile vertical gaps in the Dashboard KPI area.
- Reduced mobile card padding and value type size for Consumer QR KPI cards.
- Preserved desktop card spacing and typography at larger breakpoints.
- Added a focused unit assertion for the mobile Dashboard page spacing contract.

## Evidence

- Focused test: `npm.cmd run test -- Dashboard`
  - Result: `1 passed`, `4 passed`
- Measurement screenshot: `var\agriguard-dashboard-mobile-compact-kpis\dashboard-compact-kpis.png`
- Mobile browser suite: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-dashboard-mobile-compact-kpis.json --output-dir var\agriguard-browser-smoke-suite-dashboard-mobile-compact-kpis --timeout-ms 30000`
  - Result: `6 / 6` steps, `135 / 135` checks, `18 / 18` screenshots
- AgriGuard smoke: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dashboard-mobile-compact-kpis.json`
  - Result: `5 / 5`
- Workspace smoke: `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-dashboard-mobile-compact-kpis.json`
  - Result: `9 / 9`

## Remaining External Blocker

This loop improves local launch readiness. Protected production operator paths still require the real Firebase Admin/service-account/operator token configuration before a production launch can be called complete.
