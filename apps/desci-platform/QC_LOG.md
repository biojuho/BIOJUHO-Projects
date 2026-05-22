# DSCI QC Log

## 2026-05-16

### Scope
- DeSci launch-control finalization
- Runtime smoke alignment with operator go/no-go semantics
- Release gate report hardening and documentation cleanup

### Changes
- Added `GET /launch` to `backend/main.py` to convert `/ready` checks into an operator decision: `go`, `go-with-watch`, or `no-go`.
- Included readiness score, blocker count, warning count, launch blockers, and remediation-oriented next actions in the launch-control payload.
- Extended `scripts/product_smoke.py` so runtime smoke validates `/launch` and strict mode fails on a `no-go` release decision.
- Added `--continue-on-failure` to `scripts/release_gate.py` so operators can collect a full failure inventory instead of stopping at the first failed step.
- Expanded JSON release-gate reports with generated timestamp, total duration, pass/fail/skip counts, and failed-step summary.
- Rewrote `README.md` into a clean launch-oriented product and operations guide.
- Updated `OPERATIONS_RUNBOOK.md` to mention `/launch`, strict smoke expectations, and JSON release-gate reporting.

### Files
- `backend/main.py`
- `backend/tests/test_api_endpoints.py`
- `backend/tests/test_release_gate.py`
- `scripts/product_smoke.py`
- `scripts/release_gate.py`
- `README.md`
- `OPERATIONS_RUNBOOK.md`

### Verification
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py -q`
- `python -m pytest apps/desci-platform/backend/tests/test_api_endpoints.py::test_launch_control_returns_operator_decision apps/desci-platform/backend/tests/test_api_endpoints.py::test_launch_control_is_no_go_when_required_check_fails apps/desci-platform/backend/tests/test_release_gate.py -q`
- `python -m py_compile apps/desci-platform/scripts/product_smoke.py apps/desci-platform/scripts/release_gate.py`
- `npm run test:config` in `apps/desci-platform/contracts`
- `python scripts/release_gate.py --dry-run --skip-compose --skip-frontend --skip-contracts --json-out NUL` in `apps/desci-platform`

### Result
- Backend API regression suite passed: `20 passed`.
- Targeted launch-control and release-gate suite passed: `7 passed`.
- Contract runtime-config suite passed: `10 passed`.
- Release gate dry-run confirmed the new reporting and control flags without leaving a generated report in the worktree.

### Remaining Risks
- Full release gate was not rerun in this recording pass because the request was to record the completed work.
- Production launch still depends on real secrets, managed services, deployed contract addresses, and a strict smoke run returning a non-`no-go` launch decision.

## 2026-05-15

### Scope
- Workspace contract regression gate hardening across DeSci and AgriGuard
- Hardhat runtime configuration safety checks for deployment and verification flows
- Documentation alignment after backend path unification and contract gate expansion

### Changes
- Added `desci contracts compile`, `desci contracts tests`, `agriguard contracts compile`, and `agriguard contracts tests` to `ops/scripts/run_workspace_smoke.py`.
- Extended `tests/test_workspace_smoke.py`, `docs/QUALITY_GATE.md`, and the smoke skill project matrix so the new contract checks are treated as first-class workspace gates.
- Hardened `apps/desci-platform/contracts/hardhat.config.js` with shared runtime validation for remote signer requirements, private key normalization, and explorer API-key validation.
- Added matching runtime-config helpers and config tests for `apps/AgriGuard/contracts`, and updated its Hardhat tests to the Hardhat 3 `network.create()` style with explicit custom-error assertions.
- Updated `apps/desci-platform/README.md`, `apps/desci-platform/DEPLOYMENT_GUIDE.md`, `apps/desci-platform/STACK_ALIGNMENT.md`, and `apps/AgriGuard/README.md` so contract checks and current backend paths match the live workspace layout.

### Files
- `ops/scripts/run_workspace_smoke.py`
- `tests/test_workspace_smoke.py`
- `docs/QUALITY_GATE.md`
- `.agents/skills/multi-project-smoke-check/references/project-matrix.md`
- `apps/desci-platform/contracts/hardhat.config.js`
- `apps/desci-platform/contracts/config/runtime-config.js`
- `apps/desci-platform/contracts/tests/runtime-config.test.js`
- `apps/desci-platform/contracts/package.json`
- `apps/desci-platform/contracts/.env.example`
- `apps/AgriGuard/contracts/hardhat.config.js`
- `apps/AgriGuard/contracts/config/runtime-config.js`
- `apps/AgriGuard/contracts/tests/runtime-config.test.js`
- `apps/AgriGuard/contracts/test/AgriGuard.test.js`
- `apps/desci-platform/README.md`
- `apps/desci-platform/DEPLOYMENT_GUIDE.md`
- `apps/desci-platform/STACK_ALIGNMENT.md`
- `apps/AgriGuard/README.md`

### Verification
- `npm run test` in `apps/desci-platform/contracts`
- `npm run test` in `apps/AgriGuard/contracts`
- `python -m pytest tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_release_gate.py -q`
- `python ops/scripts/run_workspace_smoke.py --scope desci`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard`
- `python ops/scripts/run_workspace_smoke.py --scope all --json-out var/workspace-smoke-2026-05-15-final-all.json`

### Result
- Contract regression checks are now part of the default workspace smoke matrix for both DeSci and AgriGuard.
- DeSci contract tests now cover runtime config validation before Hardhat test execution.
- AgriGuard contract tests were repaired for Hardhat 3 and now pass under the same gate model.
- Full workspace smoke passed with `25/25 PASS`.

### Remaining Risks
- `apps/desci-platform/README.md`, `DEPLOYMENT_GUIDE.md`, and `STACK_ALIGNMENT.md` still contain older product naming (`BioLinker`) in descriptive text even though the operational paths are now aligned.
- Runtime validation protects local and CI usage, but actual remote deployment and explorer verification still depend on valid secrets and funded testnet wallets in the target environment.

### Scope
- Release hardening follow-up after contract, backend, and frontend improvements
- Governance state alignment between on-chain enum values and frontend rendering
- Local release gate expansion to include contract smoke validation

### Changes
- Added contract build, test, and smoke deployment steps to `scripts/release_gate.py`.
- Added `deploy:smoke:core` and `deploy:smoke:nft` scripts under `contracts/package.json`.
- Updated env doctor and `/ready` checks to treat `MOCK_MODE` and DAO contract wiring as first-class Web3 readiness signals.
- Hardened RabbitMQ imports and worker dispatch handling so lean environments without `pika` no longer fail during module import.
- Fixed governance UI state mapping for `Queued` and `Executed`, normalized large vote-count rendering, and limited vote actions to active proposals.
- Removed the remaining React 19 lint warnings across `AssetManager`, `BioLinker`, `Governance`, `Notices`, `PricingPage`, `ProductReadinessPanel`, `UploadPaper`, and `useMyLab`.

### Files
- `scripts/release_gate.py`
- `scripts/env_doctor.py`
- `contracts/package.json`
- `backend/main.py`
- `backend/services/rabbitmq_bus.py`
- `backend/services/web3_service.py`
- `backend/worker.py`
- `backend/tests/test_api_endpoints.py`
- `backend/tests/test_env_doctor.py`
- `backend/tests/test_release_gate.py`
- `backend/tests/test_worker.py`
- `frontend/src/components/AssetManager.jsx`
- `frontend/src/components/BioLinker.jsx`
- `frontend/src/components/Governance.jsx`
- `frontend/src/components/Notices.jsx`
- `frontend/src/components/PricingPage.jsx`
- `frontend/src/components/ProductReadinessPanel.jsx`
- `frontend/src/components/UploadPaper.jsx`
- `frontend/src/hooks/useMyLab.js`

### Verification
- `python scripts/release_gate.py`
- `docker compose config --quiet`
- `python -m pytest apps/desci-platform/backend/tests/test_release_gate.py apps/desci-platform/backend/tests/test_env_doctor.py apps/desci-platform/backend/tests/test_api_endpoints.py apps/desci-platform/backend/tests/test_worker.py -q`
- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build:lts`
- `npm run check:bundle`

### Result
- Full release gate passed with 12 steps, including contract smoke validation.
- Backend targeted regression suite passed: 31 tests.
- Full backend suite passed through the gate: 89 tests.
- Frontend checks passed: lint, typecheck, tests, production build, and bundle budget.
- Frontend tests passed: 61 tests across 15 files.
- Contract suite passed: 77 tests, plus local smoke deployment for core contracts and NFT contract.

### Remaining Risks
- Local env doctor still reports recommended warnings for missing production secrets and managed services such as Firebase auth credentials, PostgreSQL, Supabase, Redis, RabbitMQ, Pinata, and Stripe.
- Static analysis with `slither` has still not been run in this environment because the tool is not installed.

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
