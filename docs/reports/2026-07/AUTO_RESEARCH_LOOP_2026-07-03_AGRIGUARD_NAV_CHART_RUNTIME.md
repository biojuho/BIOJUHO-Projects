# AutoResearch Loop - AgriGuard Nav Chart Runtime

Date: 2026-07-03

## Scope

- Target: `apps/AgriGuard`
- Loop input: browser route reconnaissance found production-preview blank screens on chart-backed launch routes.
- Source refresh context: current AutoResearch source radar remained on the latest known upstream snapshot, and local remediation focused on the repo-owned Vite/Rolldown runtime surface.

## Baseline Failure

Evidence:

- `var/agriguard-nav-browser-recon.json`
- `var/agriguard-nav-chart-focused-current.json`
- `var/agriguard-nav-chart-focused-current-screens/dashboard.png`
- `var/agriguard-nav-chart-focused-current-screens/cold_chain.png`

Observed failure:

- Dashboard `/` rendered an empty body.
- Cold-Chain `/cold-chain` rendered an empty body.
- Browser page errors: `Cannot read properties of undefined (reading 'allowDataOverflow')`.
- The built assets contained cyclic chart vendor chunks, including `vendor-charts-*` chunks importing each other and one chart chunk importing the Dashboard route chunk.

## Fix

- Removed the manual Recharts/chart utility vendor groups from `apps/AgriGuard/frontend/vite.config.js`.
- Kept route-level splitting and existing React/vendor groups, but allowed Rolldown to keep the chart runtime in its natural route graph.
- Raised `chunkSizeWarningLimit` to `500`, matching `scripts/check-bundle-size.mjs` policy. The resulting chart chunk is intentional and still below the enforced max.
- Added `apps/AgriGuard/scripts/nav_browser_smoke.py` so the seven launch navigation routes are checked for:
  - expected visible content
  - nonblank body text
  - no horizontal overflow
  - no page errors
  - no console warnings/errors
  - no actionable request failures
  - screenshots for each route

## Verification

Commands:

```powershell
python -m compileall -q apps\AgriGuard\scripts\nav_browser_smoke.py
python apps\AgriGuard\scripts\nav_browser_smoke.py --help
cd apps\AgriGuard\frontend
npm run build:lts
npm run lint
npm run check:bundle
```

Browser evidence used an isolated backend and preview build:

```powershell
$env:VITE_API_URL='http://127.0.0.1:8102'; npm run build:lts
python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5174 --operator-token dev-token --json-out var\agriguard-nav-browser-smoke-chart-runtime.json --screenshot-dir var\agriguard-nav-browser-smoke-chart-runtime-screens
```

Results:

- `npm run build:lts`: PASS
- `npm run lint`: PASS
- `npm run check:bundle`: PASS
  - largest JS chunk: `CartesianChart-*.js`, about 315 KB
  - max chunk policy: 500 KB
- `nav_browser_smoke.py`: `40/40 PASS`
  - routes: Dashboard `/`, Registry `/registry`, Supply Chain `/supply-chain`, QR Tokens `/qr-tokens`, Sensors `/sensor-devices`, Cold-Chain `/cold-chain`, Scanner `/scan`
  - page errors: 0
  - console warnings/errors: 0
  - request failures: 0
  - horizontal overflow failures: 0
- Workspace smoke:
  - command: `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-nav-chart-runtime.json`
  - result: `5/5 PASS`
  - checks: frontend lint, frontend build, contracts compile, contracts tests, backend tests

Artifacts:

- `var/agriguard-nav-browser-smoke-chart-runtime.json`
- `var/agriguard-nav-browser-smoke-chart-runtime-screens/`
- `var/workspace-smoke-agriguard-nav-chart-runtime.json`

## Residual Risk

- The chart runtime is now intentionally consolidated into a larger `CartesianChart` chunk. The bundle checker keeps this bounded, and the route smoke catches blank-screen regressions.
- This loop verified local production-preview behavior. External deployment state was not changed in this cycle.
