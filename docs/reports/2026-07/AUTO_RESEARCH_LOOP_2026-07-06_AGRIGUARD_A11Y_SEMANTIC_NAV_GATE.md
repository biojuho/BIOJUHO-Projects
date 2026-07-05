# AgriGuard AutoResearch Loop: Accessibility Semantic Nav Gate

Date: 2026-07-06

## External Source Refresh

- Veritas source check: `https://github.com/Veritas-7/autoresearch-skill-system.git` `HEAD/main` = `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Microsoft Playwright MCP source: `https://github.com/microsoft/playwright-mcp`
- Playwright ARIA snapshot source: `https://github.com/microsoft/playwright.dev/blob/main/dotnet/docs/aria-snapshots.mdx`
- Playwright accessibility testing source: `https://playwright.dev/docs/accessibility-testing`

## A/B Hypothesis

- Baseline: keep route smoke focused on visible expected text, horizontal overflow, screenshots, nav state, and console/request errors. This passed previous browser checks but allowed a visible placeholder-only Supply Chain search field and a Scanner route with no `h1`.
- Variant: require each launch route to expose a `main` landmark, a `nav` landmark, at least one `h1`, no duplicate IDs, no visible unnamed interactive controls, and no visible unlabeled form fields.
- Decision rule: adopt the variant only if component tests, backend helper tests, production build, mobile click-nav smoke, full desktop/mobile browser suites, AgriGuard smoke, and workspace smoke all pass.

## Adopted Changes

- `SupplyChain.jsx`: added a real visually hidden label and stable `id` for the Supply Chain search field.
- `QRReader.jsx`: promoted `Scan Product QR` from `h2` to the route-level `h1`.
- `nav_browser_smoke.py`: added route semantic metrics and a `*_semantic_accessibility` check for each launch route.
- Regression coverage:
  - `SupplyChain.test.jsx` asserts the search field is reachable by label.
  - `QRReader.test.jsx` asserts the scanner page title is a level-1 heading.
  - `test_smoke.py` asserts the nav smoke semantic gate fails closed for missing landmarks/headings, duplicate IDs, unnamed controls, and unlabeled fields.

## Evidence

- Focused frontend tests: `npm run test -- SupplyChain.test.jsx QRReader.test.jsx`
  - Result: 2 files passed, 17 tests passed.
- Focused backend smoke helper tests:
  - `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests\test_smoke.py -q -k "nav_browser_smoke"`
  - Result: 4 passed, 44 deselected.
- Frontend production build: `npm run build:lts`
  - Result: pass.
- Mobile click-nav smoke with semantic gate:
  - `python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5174 --operator-token browser-smoke-token --click-nav --json-out var\agriguard-nav-mobile-a11y-2026-07-06.json --screenshot-dir var\agriguard-nav-mobile-a11y-2026-07-06 --timeout-ms 30000 --mobile`
  - Result: 58/58 PASS.
  - Route semantic checks: dashboard, registry, supply_chain, qr_tokens, sensors, cold_chain, and scanner all reported `hasMain=true`, `hasNav=true`, `h1Count=1`, `duplicateIds=[]`, `unlabeledFields=[]`, and `unnamedInteractive=[]`.
- Full desktop browser smoke:
  - `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-desktop-a11y-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-desktop-a11y-2026-07-06 --timeout-ms 30000 --include-unavailable-check`
  - Result: 7/7 steps passed, 166/166 checks passed, 19/19 screenshot artifacts passed.
- Full mobile browser smoke:
  - `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-mobile-a11y-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-mobile-a11y-2026-07-06 --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 173/173 checks passed, 19/19 screenshot artifacts passed.
- AgriGuard smoke: `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Result: 5/5 passed.
- Workspace smoke: `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Result: 9/9 passed.

## Launch Status

- Guarded launch status command:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-a11y-2026-07-06.json`
- Result: `status=blocked`, `blocker_class=preflight_blocked`.
- Remaining blocker is external/operator-owned: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
- Operator action ID remains `set_firebase_service_account_file`.
