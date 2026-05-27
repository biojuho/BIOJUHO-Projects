# Devlog: Desci Platform (BioLinker)

## 2026-05-20 (workspace smoke debt closure)

### 1. Frontend dependency environment restored
- Repaired the active smoke blockers by restoring `node_modules` for
  `apps/dashboard` and `apps/AgriGuard/frontend` from their existing lockfiles.
- Kept the change environment-only: incidental `package-lock.json` and
  `.coverage` changes from install/smoke runs were reverted.

### 2. Validation
- Workspace smoke now passes: `6/6`.
- AgriGuard smoke now passes: `5/5`.
- Same-session checks confirmed DeSci, getdaytrends, MCP, and CIE were already
  passing after network-enabled rechecks removed sandbox false positives.
- Evidence JSON:
  - `var\tmp\workspace_smoke_workspace_fixed_2026-05-20.json`
  - `var\tmp\workspace_smoke_agriguard_fixed_2026-05-20.json`

## 2026-05-20 (VC directory: data → DB → API → UI)

### 1. Single source of truth for VC dataset
- Extracted the curated KR + global biotech VC list (54 firms) out of
  `services/vc_crawler.py` into `backend/data/vcs_seed.json`. The crawler now
  loads from JSON via `lru_cache`, preserving the `VCCrawler.fetch_vc_list()`
  contract so `smart_matcher`, `agent_graph`, and existing tests keep working
  with no rewiring.

### 2. Relational schema + repository
- Added Supabase migration `0002_vc_firms.sql` (additive — new table only).
  Schema mirrors the `VCFirm` Pydantic model, with GIN indexes on
  `portfolio_keywords` and `preferred_stages` for fast filter queries.
- Built `services/vc_repository.py` with two interchangeable backends:
  - `MemoryVCRepository` reads the JSON seed (used in smoke/local).
  - `PostgresVCRepository` uses `asyncpg` against the `vc_firms` table when
    `DATABASE_URL` is set.
  - Selection is automatic; missing `asyncpg` falls back to memory gracefully.

### 3. Public HTTP surface
- New `routers/vcs.py` registered in `main.py`:
  - `GET /vcs` — list with `country`/`stage`/`keyword`/`limit` filters.
  - `GET /vcs/{vc_id}` — single firm lookup (404 on miss).
  - `GET /vcs/meta/backend` — diagnostic for runtime backend selection.
- Rate-limited via the existing `slowapi` limiter.

### 4. Operator seed flow
- `backend/scripts/seed_vcs.py` is the production-ready upsert script:
  `DATABASE_URL=... python scripts/seed_vcs.py [--dry-run] [--truncate]`.
  Idempotent (`on conflict do update`), runs in a transaction, prints
  pre/post row counts.

### 5. Frontend investor directory
- New public page `frontend/src/components/Investors.jsx` mounted at
  `/investors` (no auth required — boosts discovery + signup conversion).
  Filters by country, preferred stage, and free-text keyword across name,
  thesis, and portfolio keywords. Calls `GET /vcs?limit=500` once and
  filters client-side.

### 6. Validation
- Backend: `109 passed in 22.15s` (17 new VC repo/router tests, no
  regression in agent_graph wiring or any other suite).
- Frontend: `68 passed in 93.12s` Vitest, ESLint clean, `tsc --noEmit`
  clean, production build succeeded (new `Investors-*.js` chunk emitted).

## 2026-05-16 (launch control finalization)

### 1. Operator launch control
- Added `GET /launch` as an operator-facing decision endpoint on top of `/ready`.
- The endpoint summarizes subsystem readiness into `go`, `go-with-watch`, or `no-go`, with blocker counts, readiness scores, and remediation-focused next actions.
- Kept `/ready` as the lower-level subsystem report so product UI, smoke scripts, and operators can share the same source of truth.

### 2. Product smoke and release gate reporting
- Extended `scripts/product_smoke.py` to validate `/launch` alongside `/health` and `/ready`.
- Made strict smoke fail on `release_decision=no-go`, giving demos and production handoffs a clear stop signal.
- Added `--continue-on-failure` and richer JSON summaries to `scripts/release_gate.py` so failed release runs can still produce a complete operator report.

### 3. Documentation polish
- Replaced the DeSci README with a clean launch-oriented overview that explains system shape, quick start, launch control, release gate usage, production environment requirements, and key APIs.
- Updated the operations runbook to document the `/launch` decision model and JSON release gate flow.

### 4. Validation
- Backend API regression suite passed: `20 passed`.
- Targeted release gate tests passed: `7 passed`.
- Contract runtime-config tests passed: `10 passed`.
- Release gate dry-run confirmed the new flags and JSON output path behavior.

## 2026-05-15 (workspace contract gate hardening and docs alignment)

### 1. Workspace contract quality gate
- Promoted contract regression checks into the default workspace smoke matrix for both `desci-platform` and `AgriGuard`.
- The workspace gate now validates contract compile plus contract tests, not just frontend/backend health.

### 2. Hardhat runtime safety
- Added explicit runtime config validation around signer requirements, private-key normalization, and explorer API-key expectations for remote verification flows.
- Bound those rules to executable config tests so `npm run test` catches configuration regressions before Solidity tests run.

### 3. AgriGuard contract stabilization
- Repaired the AgriGuard Hardhat 3 test setup by switching to `network.create()` and replacing deprecated revert matchers with explicit custom-error assertions.
- Mirrored the DeSci contract safety model in AgriGuard so both projects now share the same deployment guardrails.

### 4. Documentation cleanup
- Updated DeSci README and deployment docs to use the live `backend/` structure instead of the legacy `biolinker/` path in operational commands.
- Added contract compile/test commands and `--scope desci` smoke guidance to the docs so operator instructions match the automated quality gate.

## 2026-05-15 (release hardening and governance alignment)

### 1. Contracts and governance
- Hardened the Hardhat 3 configuration for safer environment handling, build profiles, and verification flows.
- Enabled `ERC20Votes` on `DeSciToken` so governance uses historical vote checkpoints instead of live balances.
- Updated `DeSciDAO` quorum and state handling to use snapshot-based voting power and clearer proposal lifecycle states.
- Added shared deployment helpers and smoke deployment scripts for the token, NFT, and DAO contracts.

### 2. Backend and operations
- Expanded the local release gate to include contract build, contract tests, and contract deployment smoke checks.
- Updated environment diagnostics and readiness checks to understand `MOCK_MODE` and optional DAO contract wiring.
- Hardened RabbitMQ and worker startup so lean environments without `pika` degrade safely instead of failing at import time.
- Replaced the placeholder worker TODO path with explicit job routing for notice collection, paper indexing, matching, and proposal generation.

### 3. Frontend product surface
- Fixed governance proposal state mapping so queued and executed states match the on-chain enum.
- Normalized governance vote formatting for large integer payloads and only show vote actions while proposals are active.
- Removed the remaining React 19 lint warnings across product screens by tightening initial-load and effect synchronization patterns.
- Kept pricing, upload, notices, readiness, and my-lab flows behaviorally stable while improving lint safety.

### 4. Validation
- Full local release gate passed, including Docker Compose validation, backend tests, frontend lint/typecheck/tests/build/bundle checks, contract tests, and contract deployment smoke.
- Frontend lint is now clean with zero warnings in the current tree.
- Backend regression coverage was extended for env doctor, release gate, readiness, and worker dispatch behavior.

## 2026-02-06 (플랫폼 확장)

### 1. 핵심 기능 구현 (MVP)
- **인증 시스템**: Firebase Auth 연동 (Google 로그인, 이메일 가입).
- **BioLinker 엔진**: `analyzer.py`를 통해 RFP 공고문과 기업 프로필의 적합도를 분석하는 AI 로직 구현.
- **크롤러 모듈**: KDDF, NTIS 공고 수집을 위한 기본 구조 (`models.py`, `crawler.py`) 설계.

### 2. 플랫폼 기능 확장 (DeSci Features)
- **연구 논문 업로드 (`/upload`)**:
  - IPFS(Pinata) 연동을 위한 백엔드/프론트엔드 구현.
  - PDF 업로드 시 `Paper` 데이터 모델 생성 및 보상 트리거.
- **토큰 경제 시스템 (`/wallet`)**:
  - Web3 기반 `DeSciToken` 보상 로직 설계 (Mock 모드 지원).
  - 지갑 페이지에서 잔액 및 보상 내역 조회 기능 추가.
- **내 연구실 (`/mylab`)**:
  - 연구자 대시보드 `MyLab.jsx` 신규 개발.
  - 내 연구 목록 및 심사 상태(보상 여부) 확인 기능 구현.

### 3. 기술 스택
- **Backend**: FastAPI, Web3.py, Aiohttp, LangChain
- **Frontend**: React (Vite), TailwindCSS, Firebase SDK
- **Blockchain**: Ethereum Sepolia (Prepared for Deployment), IPFS (Pinata)

## 2026-05-19 (frontend dependency refresh)

### 1. Dependency upgrades
- Refreshed `apps/desci-platform/frontend` to current npm wanted versions for Vite, React Query, React Router, Framer Motion, Lucide, and Rollup WASM support.
- Kept ESLint 10 out of this batch because it is a major migration and npm still reports the current 9.x line as wanted.
- Preserved runtime dependency placement for product imports after npm initially tried to move them into `devDependencies`.

### 2. Validation
- Frontend lint, typecheck, Vitest, and production build all passed.
- Full local release gate passed all 12 steps, including backend tests, frontend bundle guard, contract tests, and contract deployment smoke.
- JSON release report written to `var/release-gate-after-frontend-upgrades.json`.
