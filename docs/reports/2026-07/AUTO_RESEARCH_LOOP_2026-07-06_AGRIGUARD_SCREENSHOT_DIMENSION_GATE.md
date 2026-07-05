# AutoResearch Loop: AgriGuard Screenshot Dimension Gate

- Date: 2026-07-06
- Scope: AgriGuard aggregate browser-smoke evidence gate
- Loop input: continue after fixing admin viewport screenshots; make the aggregate launch smoke fail automatically if desktop/mobile screenshot evidence regresses.

## External Source Basis

- Veritas AutoResearch/SelfEvolve source baseline refreshed earlier in this cycle:
  - `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Observed `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Browser automation sources checked earlier in this cycle:
  - `https://github.com/microsoft/playwright-mcp`
  - `https://github.com/hummer98/e2e-mcp-server`
  - `https://github.com/Uninen/devserver-mcp`
- Adopted pattern: launch evidence should be machine-checked, not only manually inspected. Screenshot artifacts must have the intended viewport dimensions for the product path being exercised.

## A/B Decision

- Baseline A: aggregate browser smoke only enforced screenshot dimensions in `--mobile` mode.
  - Desktop aggregate smoke could pass even if a child route wrote a misleading full-page screenshot.
- Variant B: aggregate browser smoke enforces expected dimensions per step.
  - Desktop operator/admin paths are expected to produce `1440x960` viewport screenshots.
  - QR consumer paths remain intentionally mobile-sized at `390x844`, even in a desktop aggregate run.
  - Mobile aggregate runs still require `390x844` screenshots for every step.
- Decision: ship Variant B. It turns the screenshot evidence rule into a deterministic gate and preserves the intentional mobile-only QR verification paths.

## Changed Files

- `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - Added `DESKTOP_SCREENSHOT_DIMENSIONS`.
  - Added `MOBILE_ONLY_SCREENSHOT_STEPS`.
  - Added `expected_screenshot_dimensions_for_step()` and wired it into each child step.
- `apps/AgriGuard/backend/tests/test_smoke.py`
  - Added a regression test for step-specific screenshot dimensions.

## Verification

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests\test_smoke.py -q -k "screenshot_dimensions or step_dimensions or viewport_screenshots_for_fixed_nav"`
  - Passed: `3` tests, `44` deselected.
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-desktop-dimension-gate-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-desktop-dimension-gate-2026-07-06 --timeout-ms 30000 --include-unavailable-check`
  - Passed: `7/7` steps, `159/159` checks, `19/19` screenshots, no dimension failures.
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-mobile-dimension-gate-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-mobile-dimension-gate-2026-07-06 --timeout-ms 30000 --mobile --include-unavailable-check`
  - Passed: `7/7` steps, `166/166` checks, `19/19` screenshots, no dimension failures.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Passed: `5/5` checks.
- `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Passed: `9/9` checks.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-dimension-gate-2026-07-06.json`
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Operator action: `set_firebase_service_account_file`
  - Blocking preflight error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Current Launch State

The aggregate browser-smoke suite now fails closed on desktop and mobile screenshot dimension regressions while preserving intentional mobile QR verification flows. Local verification is green. Production compose launch remains intentionally blocked until the operator provides a real Firebase Admin service account JSON outside the repository and reruns strict preflight.
