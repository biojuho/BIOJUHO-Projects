# AutoResearch Loop - AgriGuard Supply Chain Browser Smoke

Date: 2026-07-03

## Objective

Use the AutoResearch Karpathy loop to move AgriGuard closer to launch readiness with source-backed improvement, A/B evidence, browser verification, and a repository smoke gate.

## External Sources Checked

- Veritas-7/autoresearch-skill-system latest HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: 8 sources checked, 6 updated, 0 failures, 8 adopted sources
- Radar JSON: `var/github-modernization-radar-auto-research.json`
- Radar Markdown: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-03.md`
- Rolldown manual code splitting reference: https://rolldown.rs/in-depth/manual-code-splitting

## A/B Result

Command:

```powershell
python apps/AgriGuard/scripts/ab_test_qr_page.py --json-out var/agriguard-qr-page-ab-auto-research.json --output docs/reports/2026-07/AGRIGUARD_QR_PAGE_AB_AUTO_RESEARCH_2026-07-03.md
```

Decision: adopt variant B, guided verification.

- Dataset: built-in sample, 20 sessions
- Verification success: A `0.60`, B `0.90`, relative lift `+50%`
- Median time to verify: A `20.00s`, B `12.95s`
- Invalid error rate: A `0.40`, B `0.10`
- Evidence JSON: `var/agriguard-qr-page-ab-auto-research.json`

## Adopted Change

1. Added a Playwright browser smoke for the supply-chain operator flow:
   `apps/AgriGuard/scripts/supply_chain_browser_smoke.py`
2. Added explicit local-only operator role support for the dev auth fallback:
   `DEV_AUTH_FALLBACK_ROLE=operator`
3. Added regression coverage for the explicit fallback role and Firebase role claim preservation.
4. Updated Rolldown splitting config with `includeDependenciesRecursively: false` so Recharts chunks are not pulled into the main entry through recursive manual chunk dependencies.
5. Documented the browser smoke and local-only auth fallback usage.

## Browser Evidence

Final command used a canonical app path, isolated SQLite smoke database, explicit local dev auth fallback, and production preview bundle.

Result: `19/19 PASS`

- URL: `http://127.0.0.1:5174/supply-chain?smoke=preview`
- Initial range: `Showing 1-20 of 500 products`
- Next range: `Showing 21-40 of 500 products`
- Search range: `Showing 1-1 of 1 products`
- Product API responses: 3 successful `/products/page` responses
- Legacy unpaginated endpoint: 0 uses
- Console warnings/errors: 0
- Page errors: 0
- Screenshot: `var/agriguard-supply-chain-browser-smoke-auto-research.png`
- JSON: `var/agriguard-supply-chain-browser-smoke-auto-research.json`

## Verification

```powershell
python -m pytest tests/test_auth_security.py -q
npm run build:lts
npm run lint
npm run check:bundle
python -m compileall -q scripts\supply_chain_browser_smoke.py
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-auto-research.json
```

Results:

- Auth targeted tests: `6 passed`
- Frontend build: passed
- Frontend lint: passed
- Bundle check: passed, max chunk `177.35KB`, entry under `260KB`
- Browser smoke: `19/19 PASS`
- Workspace AgriGuard smoke: `5/5 PASS`
- Workspace backend tests inside smoke: `377 passed, 2 warnings`
- Workspace contracts tests inside smoke: `26 passing`

## Notes

- Use canonical path `D:\AI project\apps\AgriGuard` for Vite build/preview. The alias path `D:\AI project\AgriGuard` can trigger a Rolldown HTML asset path failure.
- The local dev auth fallback remains fail-closed by default. The role is granted only when `ALLOW_DEV_AUTH_FALLBACK=true` and `DEV_AUTH_FALLBACK_ROLE` is explicitly set.
- Current browser smoke uses a seeded local SQLite database and a local preview bundle. It proves the operator supply-chain path locally, not external hosting.
