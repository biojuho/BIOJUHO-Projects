# AutoResearch Loop - AgriGuard Mobile Click Navigation

Date: 2026-07-03

## Objective

Continue AgriGuard launch hardening with a real browser/computer-use path. This cycle targeted mobile navigation because comparable agri traceability and cold-chain systems emphasize QR verification, farm-to-consumer traceability, and mobile-accessible operational dashboards.

## External Sources Checked

- Veritas-7/autoresearch-skill-system latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local radar refresh: `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-03.md`
  - result: `8 sources`, `adopted=8`, `watch=0`
- Comparable GitHub/source patterns reviewed:
  - `https://github.com/polesskiy-dev/iot-cold-chain-monitoring-system`
  - `https://github.com/hyperledger-foodtraze/foodtraze-network`
  - `https://github.com/usnistgov/SCT4AFM`
  - `https://github.com/vendkura/Sup-Prod-Track`
  - `https://github.com/somdipdey/FoodSQRBlock-Digitizing-Food-Supply-Chain-Using-Blockchain-And-QR-Code`

## A/B Contract

- Baseline: current production preview, mobile viewport `390x844`, open the hamburger menu and click every launch route.
- Variant: scoped CSS layout guard in `apps/AgriGuard/frontend/src/index.css` plus mobile click mode in `apps/AgriGuard/scripts/nav_browser_smoke.py`.
- Primary KPI: mobile clicked routes passing without blank content, page errors, console warnings/errors, request failures, or actionable horizontal overflow.
- Guardrails: desktop route smoke, production build, lint, bundle policy, and `agriguard` workspace smoke must stay green.
- Decision rule: adopt only if mobile clicked route pass count improves and guardrails do not regress.

## Baseline Evidence

Artifact:

- `var/agriguard-mobile-click-recon.json`
- `var/agriguard-mobile-click-recon-screens/`

Result:

- Mobile clicked routes: `3/7` passed.
- Failures:
  - Dashboard: minor viewport/clientWidth mismatch in overflow metric.
  - Sensors: `scrollWidth=899`, `clientWidth=390`.
  - Cold-Chain and Scanner could not be reached after Sensors because the widened document shell shifted the fixed nav hit target.
- Page errors: `0`
- Console warnings/errors: `0`
- Request failures: `0`

## Adopted Variant

Changed paths:

- `apps/AgriGuard/frontend/src/index.css`
- `apps/AgriGuard/scripts/nav_browser_smoke.py`

Implementation:

- Added a scoped `main` layout rule so nested app grids/flex children and `pre` blocks cannot widen the mobile document shell through min-content sizing.
- Extended `nav_browser_smoke.py` with:
  - `--viewport WIDTHxHEIGHT`
  - `--mobile`
  - `--click-nav`
  - route labels for real navigation clicks
  - nav width/menu-state metrics
  - mobile-aware overflow comparison using `max(clientWidth, viewportWidth)`

## Variant Evidence

Artifacts:

- `var/agriguard-mobile-click-browser-smoke.json`
- `var/agriguard-mobile-click-browser-smoke-screens/`
- `var/agriguard-desktop-nav-browser-smoke-mobile-cycle.json`
- `var/agriguard-desktop-nav-browser-smoke-mobile-cycle-screens/`
- `var/workspace-smoke-agriguard-mobile-click-nav.json`

Results:

- Mobile click nav smoke:
  - command: `python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5174 --operator-token dev-token --viewport 390x844 --mobile --click-nav --json-out var\agriguard-mobile-click-browser-smoke.json --screenshot-dir var\agriguard-mobile-click-browser-smoke-screens`
  - result: `47/47 PASS`
  - routes: Dashboard, Registry, Supply Chain, QR Tokens, Sensors, Cold-Chain, Scanner
  - page errors: `0`
  - console warnings/errors: `0`
  - request failures: `0`
  - Sensors after fix: `scrollWidth=390`, `clientWidth=390`
- Desktop direct-route smoke:
  - result: `47/47 PASS`
- Frontend:
  - `npm run build:lts`: PASS
  - `npm run lint`: PASS
  - `npm run check:bundle`: PASS
  - largest chunk: `CartesianChart-*.js`, about `315 KB`, below `500 KB` policy
- Workspace smoke:
  - command: `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-mobile-click-nav.json`
  - result: `5/5 PASS`
  - checks: frontend lint, frontend build, contracts compile, contracts tests, backend tests

## Decision

Adopted. The variant improved the mobile clicked route pass rate from `3/7` to `7/7` and all guardrails passed.

## Next Cycle

The next high-value launch loop should exercise the QR verification/scanner path on mobile, including camera-unavailable fallback behavior, token input/manual verification, and consumer trust-copy readability.
