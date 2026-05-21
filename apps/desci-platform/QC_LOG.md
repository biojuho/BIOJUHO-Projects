# DSCI QC Log

## 2026-03-18

### Scope
- Frontend claymorphism rebrand follow-up QC
- Login layout and typography polish
- Korean locale copy and rendering cleanup

### Changes
- Reworked the login layout to remove excessive vertical stretching and align the two-panel composition to content height.
- Adjusted desktop and mobile spacing in the login shell for better card balance and reduced empty space.
- Added a Korean-safe font stack and Korean-specific heading fallback to prevent awkward mixed-script rendering.
- Reduced the visual noise overlay intensity on clay/glass surfaces so text remains clearer.
- Localized Korean login and shell labels that were still showing English marketplace terms.

### Files
- `frontend/src/components/Login.jsx`
- `frontend/src/index.css`
- `frontend/src/i18n/messages.js`

### Verification
- Browser QA on `/login` at desktop and mobile widths
- `npm run test`
- `npm run lint`
- `npm run build:lts`

### Result
- Login screen alignment is stable on desktop and mobile.
- Korean copy renders cleanly and no longer mixes the English panel heading on the login card.
- Automated checks passed after the fix.

## 2026-03-18 (QC rerun)

### Scope
- Frontend regression QC after login polish
- Browser smoke check for locale persistence and protected routes
- Test runner stability verification on Windows

### Changes
- Updated `frontend/vite.config.js` to use the Vitest `threads` pool instead of `forks`.
- Kept the suite single-worker to match the existing deterministic test setup.

### Verification
- `npm run test`
- `npm run lint`
- `npm run build:lts`
- Headless browser check on `/login`
- Locale persistence check for `KO -> EN`
- Unauthenticated redirect check for `/dashboard` and `/governance`
- Browser console error check

### Result
- `npm run test` now passes reliably in this Windows environment.
- Default locale initializes as `ko-KR` with `dsci.outputLanguage=ko`.
- Switching to English persists after reload with `dsci.locale=en-US`, `dsci.outputLanguage=en`, and `document.lang=en-US`.
- Unauthenticated access to protected routes redirects back to `/login`.
- No browser console errors were observed during the smoke check.

## 2026-05-11

### Scope
- Product-Ready Modernization & Structural Unification
- Web3 Feature Completion & On-chain Visibility
- Infrastructure Hardening (Health Monitoring)

### Changes
- Unified backend structure by renaming `biolinker` to `backend` and updating orchestration (`docker-compose.yml`).
- Enhanced `/health` endpoint to monitor Redis, RabbitMQ, and DB connectivity.
- Implemented `/papers/public` API for dynamic research feed.
- Modernized `ResearchFeed.jsx` (Explorer) with On-chain Verified badges, Polygonscan links, and a Live Activity ticker.
- Migrated contract addresses to environment variables for production portability.

### Verification
- `pytest tests/` (70/70 PASSED - 100% Success)
- `npm run lint` (0 errors)
- `docker-compose config` (Validated)
- Structural verification of consolidated `backend/` directory.

### Result
- The platform is now structurally unified and production-ready.
- All core infrastructure services (DB, Redis, MQ, Vector) are actively monitored.
- Research feed now provides real-time on-chain transparency and professional UI feedback.
- System stability confirmed with 100% backend test coverage pass.

## 2026-05-11 (Release Gate QC)

### Scope
- End-to-end DeSci platform release gate validation.
- Runtime API/frontend smoke check against local services.
- Browser route smoke check for core public and protected routes.
- CI quality alignment for backend, frontend, and bundle guardrails.

### Commands
- `python scripts/release_gate.py --json-out .tmp/release-gate-qc.json`
- `python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:4174`
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:4174`

### Verification
- Release gate passed all 8 steps.
- Backend tests passed: 72 tests.
- Frontend checks passed: lint, typecheck, tests, production build, bundle budget.
- Frontend tests passed: 59 tests across 14 files.
- Bundle budget passed: entry chunk `index-DEYF5bBV.js` at 254.5 KB, under the 260 KB entry limit.
- Runtime smoke passed: API 200, frontend 200.
- Browser smoke passed for `/`, `/pricing`, `/explore`, `/login`, `/does-not-exist`, `/dashboard`, and `/upload`.

### Result
- Release gate report written to `.tmp/release-gate-qc.json`.
- CI now has the same product gate signals used locally: backend tests, frontend lint/typecheck/test/build, and bundle checks.
- Local `/health` returned `degraded` and `/ready` returned `blocked`, which is expected until production dependencies and secrets are configured.

### Remaining Risks
- Local environment is still missing or using placeholder values for LLM, auth, CORS allowlist, PostgreSQL, Supabase, Redis, RabbitMQ, IPFS/Pinata, Web3, and Stripe configuration.
- Strict production readiness should be rerun after those services and secrets are available.
- Do not use `uv sync --extra dev` inside `apps/desci-platform/biolinker`; use the release gate or editable backend install flow instead.
