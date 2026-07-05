# AutoResearch Loop: AgriGuard Sensor Anonymous Token Guard

Date: 2026-07-05

## Source Check

- Skill used: `AutoResearch Karpathy Loop`
- External pattern check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Verified source revision: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Target

The Sensor Devices admin page correctly blocked anonymous protected actions, but it also fired multiple protected read requests on first load when no operator token was saved. The missing-token screenshot showed repeated `Authorization header missing` messages before the user made an explicit protected action.

## A/B Result

Baseline, before variant:

- Anonymous Sensor Devices page loaded with no operator token.
- Protected read calls fired automatically.
- Screenshot showed repeated `Authorization header missing` messages in the status area.

Variant, after local auto-load guard:

- Before explicit protected action:
  - `Authorization header missing` count: `0`
  - Local token-required notice count: `1`
  - No-token saved notice count: `1`
  - Page width: `scrollWidth=390`, `viewportWidth=390`
- After explicit anonymous register attempt:
  - `Authorization header missing` count: `1`
  - Local token-required notice count: `1`
  - Horizontal overflow: `false`

The page now avoids duplicate initial backend errors while preserving the smoke-verified 401 behavior for explicit protected actions.

## Implementation

- Added a local protected auto-load notice: `Save an operator bearer token to load protected sensor data.`
- Guarded initial Sensor Devices protected reads behind `hasSavedOperatorToken`.
- Preserved explicit protected action calls so anonymous operators still receive the backend 401 response.
- Added a focused unit test verifying no protected read calls happen on anonymous initial load.

## Evidence

- Focused test: `npm.cmd run test -- SensorDeviceManager`
  - Result: `1 passed`, `19 passed`
- Anonymous browser probe screenshot: `var\agriguard-sensor-anonymous-token-guard\sensor-devices-anonymous-guard.png`
- Mobile browser suite: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-sensor-anonymous-token-guard.json --output-dir var\agriguard-browser-smoke-suite-sensor-anonymous-token-guard --timeout-ms 30000`
  - Result: `6 / 6` steps, `135 / 135` checks, `18 / 18` screenshots
- AgriGuard smoke: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-sensor-anonymous-token-guard.json`
  - Result: `5 / 5`
- Workspace smoke: `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-sensor-anonymous-token-guard.json`
  - Result: `9 / 9`

## Remaining External Blocker

This loop improves local launch readiness. Protected production operator paths still require the real Firebase Admin/service-account/operator token configuration before a production launch can be called complete.
