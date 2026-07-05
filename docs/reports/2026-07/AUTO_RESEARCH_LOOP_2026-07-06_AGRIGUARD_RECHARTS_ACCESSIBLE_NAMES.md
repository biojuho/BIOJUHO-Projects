# AgriGuard AutoResearch Loop: Recharts Accessible Names

Date: 2026-07-06

## Source Basis

- Veritas source check: `https://github.com/Veritas-7/autoresearch-skill-system.git` `HEAD/main` = `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Recharts accessibility wiki: `https://github.com/recharts/recharts/wiki/Recharts-and-accessibility`
- Recharts accessibility story source: `https://github.com/recharts/recharts/blob/main/storybook/stories/API/Accessibility.mdx`
- Local installed Recharts 3.8.1 source confirmed `accessibilityLayer` defaults to true and the root SVG uses `role="application"` plus `tabIndex=0`; chart `title` and `desc` props are rendered into SVG `<title>` and `<desc>`.

## A/B Hypothesis

- Baseline: route smoke checked unlabeled form fields and unnamed standard controls, but did not treat tabbable Recharts SVGs as interactive. A keyboard probe found Cold-Chain charts focusing unnamed `svg.recharts-surface` elements.
- Variant: keep Recharts keyboard access enabled and add explicit chart `title`/`desc` values for Dashboard and Cold-Chain charts. Extend nav smoke to include `svg[tabindex]` in the unnamed-interactive gate and to derive names from SVG `<title>` or `<desc>`.
- Decision rule: adopt only if focused tests, production build, fresh-server browser smoke, full desktop/mobile launch smoke, AgriGuard smoke, and workspace smoke pass.

## Adopted Changes

- `ColdChainMonitor.jsx`: named the Temperature and Humidity Recharts line charts with useful descriptions.
- `Dashboard.jsx`: named the tracking-status bar chart and product-origin pie chart.
- `nav_browser_smoke.py`: now treats tabbable SVGs as interactive controls and accepts non-empty SVG `title` or `desc` as the accessible name.
- `ColdChainMonitor.test.jsx`: preserves Recharts chart title/description props in the mock and asserts the two chart names/descriptions.

## Evidence

- Focused tests:
  - `npm run test -- ColdChainMonitor.test.jsx`: 1 file passed, 5 tests passed.
  - `npm run test -- Dashboard.test.jsx`: 1 file passed, 5 tests passed.
  - `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests\test_smoke.py -q -k "nav_browser_smoke"`: 4 passed, 44 deselected.
- Production build: `npm run build:lts`
  - Result: pass.
- Production-preview DOM probe on `http://127.0.0.1:5194/cold-chain`:
  - Temperature chart: `role=application`, `tabIndex=0`, `title=Temperature timeline chart`.
  - Humidity chart: `role=application`, `tabIndex=0`, `title=Humidity timeline chart`.
- Fresh dev server DOM probe on `http://127.0.0.1:5195/cold-chain`:
  - Recharts SVG titles: `Temperature timeline chart`, `Humidity timeline chart`.
- Mobile nav smoke with tabbable-SVG gate:
  - `python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5195 --operator-token browser-smoke-token --click-nav --json-out var\agriguard-nav-mobile-chart-a11y-dev-2026-07-06.json --screenshot-dir var\agriguard-nav-mobile-chart-a11y-dev-2026-07-06 --timeout-ms 30000 --mobile`
  - Result: 58/58 PASS.
  - Dashboard, registry, supply_chain, qr_tokens, sensors, cold_chain, and scanner all reported `unnamedInteractive=[]`.
- Full desktop browser smoke:
  - `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5195 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-desktop-chart-a11y-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-desktop-chart-a11y-2026-07-06 --timeout-ms 30000 --include-unavailable-check`
  - Result: 7/7 steps passed, 166/166 checks passed, 19/19 screenshot artifacts passed.
- Full mobile browser smoke:
  - `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5195 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-mobile-chart-a11y-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-mobile-chart-a11y-2026-07-06 --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 173/173 checks passed, 19/19 screenshot artifacts passed.
- AgriGuard smoke: `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Result: 5/5 passed.
- Workspace smoke: `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Result: 9/9 passed.

## Launch Status

- Guarded launch status command:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-chart-a11y-2026-07-06.json`
- Result: `status=blocked`, `blocker_class=preflight_blocked`.
- Remaining blocker is external/operator-owned: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
- Operator action ID remains `set_firebase_service_account_file`.
