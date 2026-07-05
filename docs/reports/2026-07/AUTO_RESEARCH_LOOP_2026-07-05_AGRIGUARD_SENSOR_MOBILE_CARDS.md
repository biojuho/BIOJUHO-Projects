# AutoResearch Loop - AgriGuard Sensor Mobile Cards

Date: 2026-07-05

## Objective

Continue launch-readiness hardening for AgriGuard by finding a product-facing mobile usability gap, testing a concrete variant, and preserving evidence that the adopted change is better than the baseline.

## Source Pattern

- External reference checked this loop: `Veritas-7/autoresearch-skill-system`
- Refreshed upstream commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local skill used: `D:\AI project\.agents\skills\auto-research-karpathy\SKILL.md`

## Baseline

The Sensor Device Registry route passed navigation smoke checks, but live mobile inspection showed the registered-sensors table still depended on a desktop-width table surface:

- Baseline screenshot: `var\agriguard-sensor-mobile-scroll-inspection\registered-sensors.png`
- Baseline table class: `w-full min-w-[940px] border-collapse text-left text-sm`
- Baseline issue: mobile users saw only the left columns; the owner, zone, battery, and `Edit` / `Disable` controls were off-screen inside a horizontal table.

This was a launch-readiness problem because the sensor registry is an operator workflow, and mobile operators need to inspect and act on a registered sensor without discovering a horizontal scroll affordance.

## A/B Decision

- Variant A: keep the 940px table and rely on horizontal scroll.
- Variant B: keep one semantic row source but switch small screens to stacked, labeled rows with full-width action buttons.

Adopted Variant B.

Implementation details:

- `apps/AgriGuard/frontend/src/components/SensorDeviceManager.jsx`
  - Replaced the unconditional mobile `min-w-[940px]` registered-sensors table with `md:min-w-[940px]`.
  - Kept desktop columns at `md` and above.
  - Rendered each small-screen row as a stacked bordered row with labels for sensor, state, owner, zone, interval, last seen, battery, and actions.
  - Made `Edit` and `Disable` / `Reactivate` full-width on small screens.
- `apps/AgriGuard/frontend/src/components/SensorDeviceManager.test.jsx`
  - Added a regression test for the mobile-first registered-sensor row layout and visible row actions.

## Adopted Variant Evidence

Live mobile proof against the current Vite server:

- Metrics JSON: `var\agriguard-sensor-mobile-action-card-inspection.json`
- Screenshot, row top: `var\agriguard-sensor-mobile-action-card-inspection\registered-sensors-mobile-actions.png`
- Screenshot, actions visible: `var\agriguard-sensor-mobile-action-card-inspection\registered-sensors-mobile-actions-visible.png`

Observed metrics:

- `viewportWidth`: `390`
- `documentScrollWidth`: `390`
- `tableWidth`: `244`
- `rowWidth`: `244`
- `actionsLabelVisible`: `true`
- `Edit` button: `left=90`, `right=300`, `width=210`, `visibleInViewport=true`
- `Disable` button: `left=90`, `right=300`, `width=210`, `visibleInViewport=true`

## Verification

Focused frontend test:

```powershell
npm.cmd run test -- SensorDeviceManager
```

Result:

- `1 passed`
- `17 passed`

Mobile browser suite:

```powershell
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-sensor-mobile-cards.json --output-dir var\agriguard-browser-smoke-suite-sensor-mobile-cards --timeout-ms 30000
```

Result:

- `6/6` flows passed
- `135/135` checks passed
- `18/18` screenshot artifacts passed

Canonical AgriGuard smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-sensor-mobile-cards.json
```

Result:

- `5/5` checks passed
- elapsed `6m17s`

Workspace smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-sensor-mobile-cards.json
```

Result:

- `9/9` checks passed
- elapsed `2m57s`

## Remaining External Blocker

Local product hardening and verification are green for this loop. Full launch readiness still remains externally blocked on the Firebase Admin service account / operator token environment needed for production-grade protected admin paths.
