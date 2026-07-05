# AutoResearch Loop: AgriGuard Dashboard Status Labels

Date: 2026-07-05

## Source Check

- Skill used: `AutoResearch Karpathy Loop`
- External pattern check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Verified source revision: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Target

The mobile Dashboard status distribution chart used raw backend status labels for the Y axis. Long values such as `QualityCheckPassed`, `DeliveredtoWarehouse`, and `IN_TRANSIT` wrapped or consumed too much label space on mobile.

## A/B Result

Baseline, before variant:

- Raw labels included `QualityCheckPassed`, `DeliveredtoWarehouse`, and `IN_TRANSIT`.
- Long tick labels wrapped into 42 px high SVG ticks for `QualityCheckPassed` and `DeliveredtoWarehouse`.

Variant, after compact display labels:

- Display labels include `In Transit`, `Harvested`, `Planted`, `QC`, `Warehouse`, and `Delivered`.
- Max SVG tick height: `16 px`
- Long raw labels present in chart ticks: `false`
- Horizontal overflow: `false`

The chart now keeps all observed mobile status ticks on one line while preserving the raw status names in chart data.

## Implementation

- Added `formatDashboardStatusLabel` for display-only status axis labels.
- Added compact aliases for common backend status variants.
- Changed the Recharts Y axis to use `label` while retaining `name` in the chart data.
- Added a focused unit test for compact status label formatting.

## Evidence

- Focused test: `npm.cmd run test -- Dashboard`
  - Result: `1 passed`, `5 passed`
- Measurement screenshot: `var\agriguard-dashboard-mobile-status-labels\dashboard-status-labels.png`
- Mobile browser suite: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-dashboard-status-labels.json --output-dir var\agriguard-browser-smoke-suite-dashboard-status-labels --timeout-ms 30000`
  - Result: `6 / 6` steps, `135 / 135` checks, `18 / 18` screenshots
- AgriGuard smoke: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-dashboard-status-labels.json`
  - Result: `5 / 5`
- Workspace smoke: `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-dashboard-status-labels.json`
  - Result: `9 / 9`

## Remaining External Blocker

This loop improves local launch readiness. Protected production operator paths still require the real Firebase Admin/service-account/operator token configuration before a production launch can be called complete.
