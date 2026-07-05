# AutoResearch Loop: AgriGuard Admin Viewport Evidence

- Date: 2026-07-06
- Scope: AgriGuard browser-smoke evidence quality, admin QR/sensor routes
- Loop input: continue launch hardening after mobile UI fixes, refresh source-backed browser automation patterns, inspect desktop click-through evidence, A/B test the next highest-value improvement, verify, commit, and push.

## External Source Refresh

- Veritas AutoResearch/SelfEvolve source baseline refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- Observed `main`/`HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Browser automation sources checked:
  - `https://github.com/microsoft/playwright-mcp`
  - `https://github.com/hummer98/e2e-mcp-server`
  - `https://github.com/Uninen/devserver-mcp`
- Adopted pattern for this loop: browser evidence should be deterministic and readable by an agent or operator; screenshots that misrepresent fixed-header pages are weak launch evidence.

## A/B Decision

- Baseline A: keep `admin_routes_browser_smoke.py` desktop screenshots as `full_page=True`.
  - Desktop smoke passed, but `var/agriguard-browser-smoke-suite-desktop-autoresearch-2026-07-06/admin-routes-screens/qr-tokens.png` burned the fixed nav into the middle of the full-page artifact after the reissue-result scroll.
  - The artifact was misleading: the product path was usable, but the evidence screenshot looked like content was covered.
- Variant B: capture admin-route screenshots as viewport screenshots for both desktop and mobile.
  - This matches the rest of the AgriGuard browser-smoke scripts, which already use viewport screenshots.
  - The post-fix desktop QR-token artifact keeps the fixed nav at the top of the viewport and keeps the reissue result visible.
- Decision: ship Variant B. It improves launch evidence quality without changing product runtime behavior.

## Changed Files

- `apps/AgriGuard/scripts/admin_routes_browser_smoke.py`
  - Changed admin-route screenshot capture to always use `full_page=False`.
  - Added a short code comment explaining the fixed-navigation evidence issue.
- `apps/AgriGuard/backend/tests/test_smoke.py`
  - Updated the screenshot helper contract test to assert viewport capture for both mobile and desktop.

## Verification

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests\test_smoke.py -q -k admin_routes_browser_smoke_uses_viewport_screenshots_for_fixed_nav`
  - Passed: `1` test, `45` deselected.
- `python apps\AgriGuard\scripts\admin_routes_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token browser-smoke-token --json-out var\agriguard-admin-routes-desktop-viewport-evidence-2026-07-06.json --screenshot-dir var\agriguard-admin-routes-desktop-viewport-evidence-2026-07-06 --timeout-ms 30000`
  - Passed.
  - Post-fix artifact: `var/agriguard-admin-routes-desktop-viewport-evidence-2026-07-06/qr-tokens.png`.
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-desktop-viewport-evidence-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-desktop-viewport-evidence-2026-07-06 --timeout-ms 30000 --include-unavailable-check`
  - Passed: `7/7` steps, `159/159` checks, `19/19` screenshots.
- `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-mobile-viewport-evidence-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-mobile-viewport-evidence-2026-07-06 --timeout-ms 30000 --mobile --include-unavailable-check`
  - Passed: `7/7` steps, `166/166` checks, `19/19` screenshots.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Passed: `5/5` checks.
- `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Passed: `9/9` checks.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-viewport-evidence-2026-07-06.json`
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Operator action: `set_firebase_service_account_file`
  - Blocking preflight error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Current Launch State

Admin-route browser evidence is now consistent and less misleading across desktop and mobile. Local verification is green. Production compose launch remains intentionally blocked until the operator provides a real Firebase Admin service account JSON outside the repository and reruns strict preflight.
