# AutoResearch Loop: AgriGuard QR KPI Dashboard

Date: 2026-07-03

## Scope

Added an operator-facing QR KPI surface for launch readiness:

- Backend KPI endpoints:
  - `GET /qr-events/kpis`
  - `GET /qr-events/kpis/trend`
- Consumer scan success, daily scan progress, and 7-day timezone-aware trend metrics.
- Query indexes for KPI reads over QR scan events.
- Dashboard KPI strip with reporting-day timezone selection and retained local preference.
- Focused backend and frontend tests for KPI math, empty data, timezone boundaries, invalid timezone rejection, render state, and refetch behavior.

## Source-Backed Rationale

The loop used public QR, IoT, and traceability implementations as adoption signals for making scan conversion and verification visibility first-class operational metrics:

- https://github.com/ZeelMaliwal/Mqtt_dashboard
- https://github.com/htlabs-xyz/cardano-iot-example/blob/master/iot5-qr-code-traceability/ARCHITECTURE.md
- https://github.com/Sonia068/IoT-Smart-Agriculture-Monitoring-System
- https://github.com/somdipdey/FoodSQRBlock-Digitizing-Food-Supply-Chain-Using-Blockchain-And-QR-Code
- https://github.com/tuxxin/qr-track
- https://github.com/lakshmipravallika19145/smart_Qr_management_system
- https://github.com/htlabs-xyz/cardano-iot-example
- https://github.com/johnwalicki/IoT-AssetTracking-Perishable-Network-Blockchain

## Evidence

- `python -m py_compile backend/tests/test_qr_kpi_routes.py backend/routers/qr_events.py` passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests/test_qr_kpi_routes.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-qr-kpis"`: 4 passed, 1 Starlette deprecation warning.
- `npm run test -- Dashboard`: 1 file passed, 2 tests passed.
- `npm run lint`: passed.
- `npm run build:lts`: passed.
- `npm run check:bundle`: passed, max chunk below 500 KB and entry below 260 KB.
- Desktop browser smoke: `python scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5174 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-qr-kpis.json --screenshot-dir var/agriguard-nav-browser-smoke-qr-kpis-screens --timeout-ms 30000`: 47/47 passed.
- Mobile direct-route browser smoke: `python scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5174 --operator-token browser-smoke-token --mobile --json-out var/agriguard-nav-browser-smoke-qr-kpis-mobile.json --screenshot-dir var/agriguard-nav-browser-smoke-qr-kpis-mobile-screens --timeout-ms 30000`: 47/47 passed.
- Workspace smoke: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-qr-kpis.json`: 5/5 passed, including 385 backend tests and 26 contract tests.

## Notes

- The desktop browser smoke explicitly asserted `Consumer QR KPIs`, captured screenshots, and checked no horizontal overflow.
- The mobile direct-route browser smoke covered the KPI trend grid on a mobile viewport. A click-navigation mobile smoke attempt exceeded the shell timeout before producing JSON, so direct-route mobile evidence is the retained mobile proof for this loop.
- The restored default production build was rerun after the temporary browser-smoke build that targeted `VITE_API_URL=http://127.0.0.1:8102`.
