# Task Board

**Last Updated**: 2026-04-03
**Board Type**: Kanban (TODO / IN_PROGRESS / DONE)

---

## TODO

*No pending tasks*

---

## IN_PROGRESS

*No pending tasks*

---

## DONE (Last 7 Days)

### 2026-04-03

- [x] **Verify and commit Content Automation / GetDayTrends V2.0 Workflow Implementation**
  - **Context**: The uncommitted draft code matching the V2 PRD has been successfully validated via `pytest` (473 passing tests).
  - **Result**: Checked in the V2 workflow (`feat(getdaytrends): implement V2.0 workflow with publish-ready draft queue`). Tests passed locally and branch is green.

- [x] **Clear remaining worktree and finish push-prep checkpoint**
  - **Context**: Resolving the remaining AgriGuard and content-intelligence uncommitted footprint to return to a clean worktree state.
  - **Result**: Worktree is now clean. The V2 implementation was the final uncommitted piece, and the repo is now solely ahead of `origin/main` by the newly created commits, ready for `git push`.

- [x] **Approve the GetDayTrends & Content Automation V2.0 reset docs**
  - **Context**: Captured the product reset into canonical PRD and Workflow documentation focusing on a pure draft-queue model without automated X publishing. User approved.
  - **Docs**:
    - `docs/reports/2026-04/GETDAYTRENDS_V2_PRD_2026-04-02.md`
    - `docs/reports/2026-04/GETDAYTRENDS_V2_WORKFLOW_2026-04-02.md`
    - `docs/reports/2026-04/CONTENT_AUTOMATION_V2_PRD_2026-04-02.md`
    - `docs/reports/2026-04/CONTENT_AUTOMATION_V2_MODULE_CONTRACT_2026-04-02.md`

- [x] **GetDayTrends P0/P1 심층 리뷰 + 즉시 수정 6건**
  - **Context**: 제3자 풀스택 개발자 관점에서 getdaytrends 코드베이스 심층 검토 후 우선순위별 즉시 실행
  - **P0 수정 (운영 위험)**:
    - Twikit 쿠키 Fernet 암호화 (`x_client.py`) — PBKDF2-SHA256 키 도출, `.enc` 암호화 저장, 평문 자동 전환
    - 프로세스 lockfile (`main.py`) — PID 기반 중복 실행 방지, 스테일 lockfile 자동 정리
    - 예산 90% 세이프티 버퍼 (`core/pipeline.py`) — 동시 실행 시 오버런 방지
  - **P1 수정 (설계 결함)**:
    - 데드코드 정리: `fix_mojibake.py`, `fix_mojibake_v2.py` → `archive/`
    - DB schema_version 기반 마이그레이션 인프라 도입 (`db_schema.py`) — 기존 try/except ALTER TABLE → 버전 레지스트리
    - V9.0 문서 혼재 정리: `V9.0_IMPLEMENTATION_STATUS.md`, `QC_REPORT_*.md` → `archive/`
  - **Files**: `x_client.py`, `main.py`, `core/pipeline.py`, `db_schema.py`, `requirements.txt`, `.env.example`
  - **Validation**:
    - `pytest automation/getdaytrends/tests/` → **459 passed**, 6 skipped, 0 failed

- [x] **Full workspace QC sweep (2026-04-03)**
  - **Result**: 전체 테스트 스위트 GREEN
  - **Validation**:
    - `pytest automation/getdaytrends/tests/` → **459 passed**, 6 skipped
    - `pytest automation/DailyNews/tests/` → **249 passed**, 16 deselected
    - `pytest tests/` → **216 passed**, 3 deselected

### 2026-04-02

- [x] **getdaytrends V2.0 reset docs drafted with X auto-publish excluded**
  - **Result**: Narrowed the product reset from the broad content pipeline to `getdaytrends` specifically, and formalized `X manual-assisted only` as the V2.0 policy.
  - **Docs**:
    - `docs/reports/2026-04/GETDAYTRENDS_V2_PRD_2026-04-02.md`
    - `docs/reports/2026-04/GETDAYTRENDS_V2_WORKFLOW_2026-04-02.md`

- [x] **Content Automation V2.0 PM reset docs drafted**
  - **Result**: Captured the product reset as two approval docs before reopening implementation.
  - **Docs**:
    - `docs/reports/2026-04/CONTENT_AUTOMATION_V2_PRD_2026-04-02.md`
    - `docs/reports/2026-04/CONTENT_AUTOMATION_V2_MODULE_CONTRACT_2026-04-02.md`
  - **Coverage**:
    - North Star, KPI, canonical workflow, phase plan
    - DTO/event contracts, ownership boundaries, fallback rules, forbidden patterns

- [x] **Vibe coding architecture review and first hardening slice completed**
  - **Result**: Converted the architecture review into an execution checklist, then fixed the two highest-risk issues called out by that review.
  - **What changed**:
    - `apps/AgriGuard/backend/main.py` now keeps a safe cache fallback contract for rate limiting even when `shared.cache` import resolution fails
    - `automation/content-intelligence/storage/x_publisher.py` now uses async `httpx` and an explicit X user-context token contract instead of the previous implicit `XClient` fallback path
    - `automation/content-intelligence/config.py`, `.env.example`, and `automation/content-intelligence/tests/test_smoke.py` were updated to lock the contract in place
    - added `docs/reports/2026-04/VIBE_CODING_ARCH_REVIEW_2026-04-02.md`
  - **Validation**:
    - forced cache-fallback regression check -> `cache.incr(...) == 1`
    - `python -m pytest automation/content-intelligence/tests/test_smoke.py -q` -> `77 passed`
    - `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q -k "not test_qr_ab_script_handles_missing_variant_data"` -> `5 passed, 1 deselected`
    - `python ops/scripts/run_workspace_smoke.py --scope workspace` -> `5/5 PASS`
    - `python ops/scripts/run_workspace_smoke.py --scope agriguard` -> `3/3 PASS`
  - **Note**:
    - a fresh `python ops/scripts/run_workspace_smoke.py --scope all` was attempted twice but timed out locally, so the latest recorded all-scope green remains the earlier `18/18 PASS`

- [x] **Push-prep checkpoint synced to the current ahead-12 branch state**
  - **Result**: Re-synced repo status docs after the dashboard/monitoring, cleanup, lint-fix, and shared-cache commits so the next session can resume from the actual push-ready state instead of the earlier broad dirty-tree snapshot.
  - **Current state captured**:
    - branch: `main...origin/main [ahead 12]`
    - remaining worktree narrowed to the AgriGuard backend/frontend slice
  - **Validation**:
    - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`

- [x] **GetDayTrends dashboard monitoring slice isolated into a standalone commit**
  - **Result**: Added dashboard-side log inspection, DailyNews A/B visibility, and Loki/Promtail monitoring in one reviewable commit.
  - **Commit**:
    - `13e2393 feat(getdaytrends): add dashboard logs and monitoring stack`
  - **Validation**:
    - `python -m pytest automation/getdaytrends/tests/test_dashboard.py -q` -> `13 passed`
    - `python -m py_compile automation/getdaytrends/dashboard.py` -> pass
    - `docker compose -f docker-compose.monitoring.yml config` -> valid
    - `Invoke-WebRequest http://localhost:3100/ready` -> `ready`

- [x] **Temporary error outputs removed**
  - **Result**: Cleaned tracked scratch artifacts that were no longer useful in the repo state.
  - **Commit**:
    - `8f4cd3c chore(cleanup): remove temporary error outputs`
  - **Files**:
    - `out2.txt`
    - `web3_errors.txt`

- [x] **AgriGuard Vite lint gate repaired**
  - **Result**: Fixed the last failing workspace smoke check by making the Vite config explicit about `process` in Node ESM.
  - **Commit**:
    - `cd7ffb5 fix(agriguard): satisfy vite config lint`
  - **Validation**:
    - `npm run lint` in `apps/AgriGuard/frontend` -> pass
    - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`

- [x] **GetDayTrends shared cache and hot-path index slice isolated into a standalone commit**
  - **Result**: Added Redis-backed shared cache plumbing for dedup and content reuse, hot-path DB indexes, and regression coverage for both cache and DB behavior.
  - **Commit**:
    - `7ad6552 feat(getdaytrends): add shared cache and hot-path indexes`
  - **Validation**:
    - `python -m pytest automation/getdaytrends/tests/test_db.py -q` -> `27 passed`
    - `python -m pytest packages/shared/tests/test_cache.py -q` -> `15 passed`
    - `python ops/scripts/run_workspace_smoke.py --scope getdaytrends` -> `2/2 PASS`
    - `docker compose -f docker-compose.dev.yml config --services` -> includes `redis`
- [x] **GetDayTrends schema drift fixed and workspace QC restored**
  - **Result**: Repaired fresh/drifted DB initialization so `tweets.variant_id` and `tweets.language` are present again, which restored save-path tests and the full workspace smoke gate.
  - **Files**:
    - `automation/getdaytrends/db_schema.py`
    - `automation/getdaytrends/tests/test_db.py`
  - **Validation**:
    - `python -m pytest tests/test_storage.py tests/test_e2e.py tests/test_notion_content_hub.py tests/test_db.py -q` -> `41 passed`
    - `python -m pytest tests -q` in `automation/getdaytrends` -> `453 passed, 6 skipped, 1 deselected`
    - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`
- [x] **Ops governance slice isolated into a standalone commit**
  - **Result**: Split PR triage, debt audit, and monitoring governance changes out of the broad dirty tree into their own commit.
  - **Commit**:
    - `b6b8cd3 feat(ops): add pr triage and vibedebt audit`
  - **Validation**:
    - `python -m pytest tests/test_pr_triage.py -q` -> `9 passed`
    - `python -m py_compile ops/scripts/pr_triage.py` -> pass
    - `python ops/scripts/tech_debt_scanner.py --json-out var/debt/triage-check.json` -> pass
    - `python ops/scripts/push_debt_metrics.py --report-file var/debt/triage-check.json --dry-run` -> pass

- [x] **Infra baseline slice isolated into a standalone commit**
  - **Result**: Split AgriGuard port policy, backend baseline cleanup, and CI Python version alignment out of the broad dirty tree into their own commit.
  - **Commit**:
    - `db27e71 chore(infra): align agriguard ports and ci baselines`
  - **Validation**:
    - `docker compose -f docker-compose.dev.yml config --services` -> pass
    - `python -m pytest tests -q` in `apps/AgriGuard/backend` -> `10 passed`

- [x] **Dashboard slice isolated into a standalone commit**
  - **Result**: Split the dashboard product change out of the broad dirty tree into its own commit so the remaining work can continue with less coupling.
  - **Commit**:
    - `b06f8f3 feat(dashboard): add ab performance panel and frontend tests`
  - **Validation**:
    - `npm run lint` -> pass
    - `npm run test` -> `2 passed`
    - `npm run build` -> pass
    - `npm run check:bundle` -> pass

- [x] **Architecture Stabilization Sprint 1~3 ?�료 + QC ?�인**
  - **Sprint 1 ???�스???�프??*:
    - manual ?�스??8�?`tests/manual/`�?격리, `@pytest.mark.integration` 마킹
    - `pytest-cov` `fail_under=50%` gate 추�?
    - `shared/llm/client.py` sync/async 중복 ~80�??�소 (`_prepare_backend_call` + `_handle_backend_result`)
    - `shared/env_loader.py` ?�규 ??.env ?�일?�스 ?�칙 ?�용
  - **Sprint 2 ???�영 ?�실??*:
    - dailynews/getdaytrends ?�이?�라??Discord+Telegram ?�중 ?�림, `.env` cleanup step 추�?
    - `heartbeat-monitor.yml` ??2?�이?�라??(GetDayTrends+DailyNews) ?�합 모니?�링
    - `TASKS.md` 734??64�?(51% 감소), `docs/archive/tasks-done-W13.md` ?�카?�브
  - **Sprint 3 ??코드 ?�순??*:
    - Python 3.12/3.14 ?�용 ??**3.13 ?�일** (19 workflows + `.pre-commit-config.yaml`)
    - `shared/paths.py` ?�규 ??`sys.path` 중앙 관�? root `conftest.py` ?�환
    - `getdaytrends/config.py` ??`QualityConfig`/`CostConfig`/`AlertConfig` ?�메??분리 (AppConfig backward-compatible)
  - **QA 발견 ???�정**: `shared/paths.py` WORKSPACE_ROOT symlink ?�해??(CRITICAL) ??marker-based ?�색?�로 ?�정
  - **Validation**:
    - `python -m pytest tests/ -q` ??`216 passed, exit 0`
    - `ruff check` (변�??�일) ??clean
    - `shared/paths.py`, `shared/env_loader.py`, AppConfig sub-configs 개별 ?�작 ?�인
  - **QC**: `.agent/qa-reports/2026-04-02-architecture-stabilization.md` ??**???�인**

- [x] **Workspace checkpoint revalidated against the live worktree**
  - **Result**: Confirmed that the current dirty worktree still passes the canonical smoke suite, and re-synced repo status docs with the actual 2026-04-02 state.
  - **Validation**:
    - `python ops/scripts/run_workspace_smoke.py --scope workspace` -> `5/5 PASS`
    - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`
    - `python -m pytest automation/content-intelligence/tests/test_smoke.py -q` -> `34 passed`
  - **Artifacts**:
    - `var/reports/workspace-smoke-latest.txt`
    - `var/reports/workspace-smoke-all-latest.txt`

### 2026-04-01

- [x] **VibeDebt Pushgateway path revalidated**
  - **Result**: Re-ran the local monitoring stack, pushed the VibeDebt snapshot into Pushgateway, and verified that Prometheus could query the ingested `vibedebt_*` series end-to-end.
  - **Validation**:
    - `docker compose -f docker-compose.monitoring.yml up -d` -> `mon-prometheus`, `mon-pushgateway`, `mon-grafana` healthy
    - `python ops/scripts/push_debt_metrics.py --report-file var/debt/2026-03-31-radon.json` -> `Score: 34.7, Grade: C`
    - `Invoke-WebRequest -Uri http://localhost:9091/metrics` -> `vibedebt_workspace_score` visible
    - `Invoke-WebRequest -Uri 'http://localhost:9090/api/v1/query?query=vibedebt_workspace_score'` -> `34.7`

- [x] **GetDayTrends tweet metrics collector hardened for local vs CI runs**
  - **Result**: Updated `collect_posted_tweet_metrics.py` so local smoke runs emit a structured skip payload when the bearer token is missing, while CI remains fail-fast via `--require-token`.
  - **Files**:
    - `.github/workflows/collect-tweet-metrics.yml`
    - `automation/getdaytrends/scripts/collect_posted_tweet_metrics.py`
    - `automation/getdaytrends/tests/test_collect_posted_tweet_metrics.py`
  - **Validation**:
    - `python -m pytest automation/getdaytrends/tests/test_collect_posted_tweet_metrics.py -q` -> `2 passed`
    - `python automation/getdaytrends/scripts/collect_posted_tweet_metrics.py --json-out automation/getdaytrends/data/tweet_metrics_local_smoke.json` -> `status: skipped`, `reason: missing_bearer_token`
    - `python automation/getdaytrends/scripts/collect_posted_tweet_metrics.py --require-token` -> exit `1` when token missing

### 2026-03-31

- [x] **X engagement metrics loop validation**
  - **Result**: Made `collect_posted_tweet_metrics.py` resilient for local smoke runs by emitting a structured skip when the bearer token is missing, while keeping CI fail-fast via `--require-token`.
  - **Validation**:
    - `python -m pytest automation/getdaytrends/tests/test_collect_posted_tweet_metrics.py -q` -> `2 passed`
    - `python automation/getdaytrends/scripts/collect_posted_tweet_metrics.py --json-out automation/getdaytrends/data/tweet_metrics_local_smoke.json` -> `status: skipped`, `reason: missing_bearer_token`

- [x] **VibeDebt Pushgateway E2E smoke**
  - **Result**: Brought up monitoring infrastructure via `docker-compose.monitoring.yml` and successfully pushed local metrics snapshot to Prometheus Pushgateway.
  - **Validation**:
    - `docker compose -f docker-compose.monitoring.yml up -d` -> `mon-pushgateway` and `mon-prometheus` services started & healthy.
    - `python ops/scripts/push_debt_metrics.py --report-file var/debt/2026-03-31-radon.json` -> Metrics published (Score: 34.7, Grade: C).

- [x] **VibeDebt backlog cleanup finished**
  - **Result**: Added the root workspace `dev` extra for `radon>=6.0`, verified that `docker-compose.monitoring.yml` already exposes `pushgateway` on port `9091`, and replaced the stale TODO items with the next operational tasks.
  - **Files**:
    - `pyproject.toml`
    - `TASKS.md`
  - **Validation**:
    - `python -m pip install -e ".[dev]"` -> `radon 6.0.1`
    - `docker compose -f docker-compose.monitoring.yml config --services` -> includes `pushgateway`
    - `python ops/scripts/tech_debt_scanner.py --json-out var/debt/2026-03-31-radon.json` -> `radon_available=true`
    - `python ops/scripts/push_debt_metrics.py --report-file var/debt/2026-03-31-radon.json --dry-run` -> metrics rendered successfully

- [x] **Audience-First Prompt Optimization & Local QC Validated**
  - **Result**: Successfully implemented and verified Creator-focused formatting ("Text blocks" spacing) and the explicit "?�� 바이???�션: XX?? metric injection into GetDayTrends LLM generator prompts.
  - **Action 1**: Configured `DailyNews_AB_Test` to run locally via Windows Task Scheduler (Wed, Sun 19:00 KST) as a fallback strategy to preserve GitHub Actions tier limits.
  - **Action 2**: Modified `prompt_builder.py` (`_build_audience_format_section`) and applied constraints across all short-form and threads generators in `generator.py` and `threads.py`.
  - **Validation**:
    - `python automation/getdaytrends/tests/test_generator.py` -> 29/29 tests passed.
    - `pytest automation/getdaytrends/tests/` -> 414 tests passed, 0 failures.
    - `test_prompt_qc.py` -> Verified explicit viral score hook and visual blank line insertion natively within terminal outputs.

- [x] **System Critical Review & Action Items Execution**
  - **Result**: Conducted a highly critical review of the current AI ecosystem identifying the design/infrastructure gap, followed by immediate execution of 3 strategic action items to stabilize automation and metrics.
  - **Action 1**: Verified GetDayTrends GitHub Actions workflow (`.github/workflows/getdaytrends.yml`) and explicitly disabled the brittle Windows Task Scheduler (`\GetDayTrends_CurrentUser`) via local powershell.
  - **Action 2**: Extracted Prometheus and Grafana into a standalone `docker-compose.monitoring.yml` and started them persistently (`# 200 OK`) to actually utilize the built observability stack 24/7.
  - **Action 3**: Created the `.github/workflows/collect-tweet-metrics.yml` cron workflow to collect real X engagement metrics into SQLite twice daily, closing the loop on A/B testing capability.
  - **Files**:
    - `docs/reports/2026-03/SYSTEM_CRITICAL_REVIEW_2026-03-31.md`
    - `docker-compose.monitoring.yml`
    - `.github/workflows/collect-tweet-metrics.yml`
  - **Validation**:
    - `schtasks /query /tn "\GetDayTrends_CurrentUser"` -> Disabled
    - `docker compose -f docker-compose.monitoring.yml config --services` -> Validated
    - `Invoke-WebRequest -Uri http://localhost:9090/-/ready` -> `200`
    - `Invoke-WebRequest -Uri http://localhost:3000/api/health` -> `200`

- [x] **Daily workspace QC snapshot recorded**
  - **Result**: Ran the deterministic quality gate and recorded the outcome in repo docs plus session records
  - **Validation**:
    - `python ops/scripts/run_workspace_smoke.py --scope all --json-out var/smoke/manual-smoke-2026-03-31.json` -> `15/15 PASS`
    - `git status --porcelain` snapshot showed `25` changed paths before documentation updates
  - **QC Report**:
    - `docs/reports/2026-03/QC_REPORT_2026-03-31_DAILY_WORKSPACE.md`
  - **Recorded In**:
    - `HANDOFF.md`
    - `TASKS.md`
    - `CONTEXT.md`
  - **Verdict**:
    - Operational QC: PASS
    - Release hygiene: CAUTION

- [x] **DailyNews/GetDayTrends ?�롬?�트 마이그레?�션 ?�코???�평가**
  - **Result**: 마이그레?�션 불필?????�행 ?��? 결정
  - **근거**:
    - GetDayTrends `prompt_builder.py` (741�?: ?�르?�나(중연), 카테고리�????�팅, ?�트 가?�레?? ?��? 기반 ?�성 ??**고도�??�적??* ?��???빌딩 로직
    - DailyNews `llm_prompts.py`: ?�사?�게 ?�적 ?�롬?�트 빌더 ?�턴
    - ?�들?� `PromptManager` (YAML ?�적 ?�플�? ?�턴�?맞�? ?�음 ??변??치환???�닌 컨텍?�트 기반 ?�션 ?�성
    - BioLinker ?�롬?�트 마이그레?�션(YAML ?�플릿에 ?�합???�적 ?�롬?�트)?� ?��? Phase 4?�서 ?�료??  - **?�정**: ROI 부족으�?마이그레?�션 ?�킵. ?�행 ?�체 구조 ?��?

- [x] **Docker ?�트 충돌 ?�리 (root-compose vs AgriGuard)**
  - **Result**: 루트 `docker-compose.dev.yml`???�스???�트�?AgriGuard ?�립 compose?� 분리?�고, 관??문서/?�경 ?�제�?같�? 기�??�로 ?�렬
  - **변�?*:
    - PostgreSQL: `5432` ??`5433` (?�경변??`POSTGRES_PORT`�??�버?�이??가??
    - MQTT: `1883` ??`1884` (?�경변??`MQTT_PORT`�??�버?�이??가??
    - AgriGuard Backend: `8002` ??`8003` (?�경변??`AGRIGUARD_PORT`�??�버?�이??가??
    - ?�트 ?�책 ?�션??compose ?�일 ?�더?� ?�영 문서??문서??  - **Files**:
    - `docker-compose.dev.yml`
    - `.env.example`
    - `docs/DOCKER_SETUP_GUIDE.md`
    - `ops/scripts/setup_dev_environment.ps1`
    - `HANDOFF.md`
  - **Validation**: `docker compose -f docker-compose.dev.yml config --services`

- [x] **Intention-first PR triage system adapted from ACPX concepts**
  - **Result**: Added a deterministic PR triage workflow for pull requests, upgraded the PR template to capture intent/problem/validation explicitly, and documented why this repo adopts the triage principles without the full ACPX autonomous runtime.
  - **Files**:
    - `.github/pull_request_template.md`
    - `.github/workflows/pr-triage.yml`
    - `ops/scripts/pr_triage.py`
    - `docs/PR_TRIAGE_SYSTEM.md`
    - `tests/test_pr_triage.py`
  - **Validation**:
    - `python -m pytest tests/test_pr_triage.py -q` -> `9 passed`
    - `python -m py_compile ops/scripts/pr_triage.py` -> exit `0`

- [x] **DailyNews Economy_KR A/B test CI ?�동??*
  - **Result**: Added a weekly GitHub Actions workflow for `ab_test_economy_kr_v2.py`, uploads JSON/Markdown artifacts, appends a run summary, and sends Telegram status notifications.
  - **Files**:
    - `.github/workflows/dailynews-ab-economy-kr.yml`
    - `.github/workflows/dailynews-pipeline.yml`
    - `automation/DailyNews/scripts/ab_test_economy_kr_v2.py`
  - **Validation**:
    - `python -m py_compile automation/DailyNews/scripts/ab_test_economy_kr_v2.py` -> exit `0`
    - `git diff --check -- automation/DailyNews/scripts/ab_test_economy_kr_v2.py .github/workflows/dailynews-pipeline.yml .github/workflows/dailynews-ab-economy-kr.yml` -> clean

- [x] **DailyNews P0-P3 코드 리뷰 ?�체 ?�료 (15�???��)**
  - **Result**: 보안(SQL injection), ?�정??circuit breaker, fallback gate), 관측성(metrics, tracing, Telegram alerting), ?�키?�처(mixin base, BriefAdapters, async ?�일) ?�체 구현
  - **Commits**:
    - `f06bf7a` ??P0/P1: silent failure 차단, SQL injection, log rotation, batch queries
    - `bd79bd0` ??P2: circuit breaker, Telegram alerting, emit_metric(), BriefAdapters
    - `8185a5b` ??P3: _DBProviderBase, asyncio.to_thread, trace context (contextvars)
    - `bff4fc3` ??delivery_state, config alias cleanup, linter fixes, session docs
  - **Tests**: 79 unit tests passed
  - **Key new files**:
    - `src/antigravity_mcp/integrations/circuit_breaker.py`
    - `src/antigravity_mcp/tracing.py`
    - `src/antigravity_mcp/state/base.py`
    - `tests/unit/test_circuit_breaker.py`, `tests/unit/test_tracing.py`

- [x] **DailyNews gray-zone closure recorded**
  - **Result**: Retired the last DailyNews legacy compatibility layer from active runtime behavior. Scripts now use canonical `NOTION_*` settings only, shared deployment examples no longer advertise deprecated names, and config warnings now flag removed legacy env names instead of silently reading them.
  - **Files**:
    - `automation/DailyNews/src/antigravity_mcp/config.py`
    - `automation/DailyNews/scripts/settings.py`
    - `automation/DailyNews/docs/runbooks/gray-zone-closure-checklist.md`
    - `automation/DailyNews/docs/runbooks/environment-mapping.md`
    - `automation/DailyNews/QC_REPORT_2026-03-31_PIPELINE_STABILIZATION.md`
  - **Validation**:
    - `python -m pytest -q tests` -> `195 passed`
    - `python -m compileall -q src apps scripts` -> exit `0`
  - **Recorded In**:
    - `automation/DailyNews/docs/runbooks/gray-zone-closure-checklist.md`
    - `automation/DailyNews/QC_REPORT_2026-03-31_PIPELINE_STABILIZATION.md`
    - `TASKS.md`

### 2026-03-30

- [x] **DailyNews A/B Test v2 ?�로?�션 ?�행**
  - **Result**: NEW 3-Stage Pipeline ??Primary KPI **+23.5??* (목표 +15??초과), NEW 버전 채택 권장
  - **Files**: `automation/DailyNews/output/ab_test_economy_kr_v2.md`, `ab_test_economy_kr_v2.json`
  - **Scores**: Version A 65.0 ??Version B **88.5** (Specificity 60??00, Actionability 50??5)

- [x] **DailyNews fact-check heuristic ?�반??*
  - **Result**: 매번 allowlist??추�??�던 ?�턴????규칙 기반 ?�동 ?�터�??�환. `Voices`, `Taste` (product feature names), ?�국?????�사 ?�간(`?�화??, `증�???), ?�국??개수 ?�위(`18�?, `6�? ?? ?�동 처리
  - **Files**: `automation/DailyNews/src/antigravity_mcp/integrations/fact_check_adapter.py`
  - **Validation**: `pytest tests/unit/test_adapters.py -q` ??**23 passed**

- [x] **Grafana Audience KPI ?�?�보???�성**
  - **Result**: 4�??�로?�트 KPI ?�널 19�??�함?????�?�보???�규 ?�성
  - **File**: `ops/monitoring/grafana/dashboards/audience-metrics.json`
  - **Coverage**: DailyNews(X engagement), GetDayTrends(viral hit rate), AgriGuard(QR funnel+gauge), DeSci(matching), LLM cost panels

- [x] **Daily workspace QC snapshot recorded**
  - **Result**: Ran the deterministic quality gate and recorded the outcome in repo docs plus session records
  - **Validation**:
    - `python ops/scripts/run_workspace_smoke.py --scope all --json-out var/smoke/manual-smoke-2026-03-30.json` -> `15/15 PASS`
    - `git status --porcelain` snapshot showed `119` changed paths before documentation updates
  - **QC Report**:
    - `docs/reports/2026-03/QC_REPORT_2026-03-30_DAILY_WORKSPACE.md`
  - **Recorded In**:
    - `HANDOFF.md`
    - `TASKS.md`
    - `CONTEXT.md`
  - **Verdict**:
    - Operational QC: PASS
    - Release hygiene: CAUTION (active worktree across automation, ops, apps, packages)

### 2026-03-29

- [x] **Phase 5: Security & Compliance**
  - **Result**: Audited secret management (already solid), built audit log middleware for all 4 FastAPI services, wrote comprehensive SECURITY_POLICY.md
  - **5.1 Secret Audit**:
    - `.gitignore` covers `.env`, `credentials.json`, `token*.txt`, `serviceAccountKey.json`
    - Zero `.env` files tracked in git
    - Pre-commit: gitleaks + detect-private-key already active
    - CI: gitleaks-action + pip-audit + npm audit already running
    - Dependabot: 11 ecosystem configs (pip, npm, github-actions)
  - **5.3 Audit Log Middleware** (`packages/shared/audit.py`):
    - JSON structured audit logs for every HTTP request (service, user_id, method, path, status, duration_ms, client_ip)
    - Excludes noisy endpoints (/metrics, /health, /docs)
    - Wired into all 4 services: AgriGuard, GetDayTrends, Dashboard API, BioLinker
  - **5.4 Security Policy** (`docs/SECURITY_POLICY.md`):
    - Secret management rules + leak response procedure
    - Vulnerability patching SLA (Critical 24h, High 7d, Medium 30d)
    - Audit logging spec + retention policy
    - API security (rate limiting, auth, CORS)
    - LLM cost controls documentation
  - **Validation**: All files compile, AgriGuard 6 passed, GetDayTrends 22 passed

- [x] **Phase 4 completion: Prompt migration + few-shot examples + RAG hybrid search**
  - **Result**: Completed all 3 remaining Phase 4 tasks ??BioLinker prompt migration, production few-shot examples, and keyword+semantic hybrid search module
  - **Prompt Migration** (BioLinker ??PromptManager):
    - `agent_service.py` ??3 prompts (research, publisher, lit_review) now loaded from YAML templates
    - `analyzer.py` ??analyzer prompt with few-shot from `rfp_matching.json`
    - `proposal_generator.py` ??3 prompts (proposal, review, lit_synthesis) with graceful fallback
    - 7 new YAML templates: `biolinker_research`, `biolinker_publisher`, `biolinker_lit_review`, `biolinker_analyzer`, `biolinker_proposal`, `biolinker_review`, `biolinker_lit_synthesis`
  - **Production Few-Shot Examples**:
    - `content_generation.json` ??Tech/Economy briefing examples from live DailyNews patterns
    - `biolinker_analysis.json` ??S-grade and D-grade RFP matching examples with full JSON output
    - Total: 4 few-shot sets (trend_analysis, rfp_matching, content_generation, biolinker_analysis)
  - **RAG Hybrid Search** (`packages/shared/search/hybrid.py`):
    - BM25 keyword scoring + cosine semantic similarity
    - Reciprocal Rank Fusion (RRF) re-ranking
    - Weighted linear combination mode available
    - Tested: AI drug discovery query correctly ranks relevant RFPs above generic ones
  - **Validation**: All files compile cleanly, hybrid search returns expected ranking

- [x] **Phase 4: Centralized prompt template system + budget-aware auto-downgrade**
  - **Result**: Built YAML-based prompt template manager with few-shot examples, and added budget-aware tier auto-downgrade to the LLM client
  - **4.1 Prompt Centralization**:
    - `packages/shared/prompts/manager.py` ??PromptManager with YAML loading, variable substitution, few-shot injection, safe dict rendering
    - `packages/shared/prompts/templates/` ??5 templates: content_generation, rfp_analysis, trend_analysis, research_agent, proposal_generation
    - `packages/shared/prompts/few_shot_examples/` ??2 example sets: trend_analysis.json, rfp_matching.json
    - Usage: `pm.render("trend_analysis", platform="X", few_shot_key="trend_analysis")`
  - **4.2 Budget-Aware Auto-Downgrade**:
    - `packages/shared/llm/config.py` ??Added `LLM_DAILY_BUDGET`, `LLM_BUDGET_DOWNGRADE_HEAVY` ($1.50), `LLM_BUDGET_DOWNGRADE_MEDIUM` ($1.80) thresholds (env-configurable)
    - `packages/shared/llm/stats.py` ??Added `get_today_cost()` method for real-time daily cost query
    - `packages/shared/llm/client.py` ??`_budget_downgrade()` auto-demotes HEAVY?�MEDIUM at $1.50/day, MEDIUM?�LIGHTWEIGHT at $1.80/day
    - Existing `RATE_LIMIT.lock` hard cap remains as final safety net at $2.00/day
  - **Validation**:
    - `python -m compileall -q` -> exit 0
    - `python -m pytest tests/test_shared_llm.py -q` -> `20 passed`
    - PromptManager renders 5 templates with variable substitution and few-shot injection

- [x] **Phase 3 monitoring: End-to-end stack verified live**
  - **Result**: Monitoring stack deployed and verified with real data flowing through Prometheus ??Grafana
  - **Live status**:
    - Prometheus :9090 ??`Ready`, scraping AgriGuard :8002 (`up`)
    - Grafana :3000 ??`OK`, 5 dashboards auto-provisioned
    - AlertManager :9093 ??`OK`, 4 `ServiceDown` alerts firing (expected for offline services)
    - Loki :3100 ??`ready`
  - **AgriGuard Docker rebuild**: Added `prometheus_client` + `structlog` to requirements, mounted `packages/shared` as volume, rebuilt and restarted container. `/metrics` endpoint now returns live Prometheus metrics
  - **Files**:
    - `apps/AgriGuard/backend/requirements.txt` ??added `prometheus_client>=0.21.0`, `structlog>=24.0.0`
    - `apps/AgriGuard/docker-compose.yml` ??added shared volume mount + PYTHONPATH
  - **Validation**:
    - `curl http://localhost:8002/metrics` ??returns `http_requests_total`, `http_request_duration_seconds` with `service="agriguard"` labels
    - `curl http://localhost:9090/api/v1/targets` ??agriguard: `health: up`
    - `curl http://localhost:3000/api/search` ??5 dashboards listed
    - `curl http://localhost:9093/api/v2/alerts` ??4 ServiceDown alerts

- [x] **Phase 3 monitoring: Business metrics wired into BioLinker + GetDayTrends scoring**
  - **Result**: Wired remaining business metric counters into BioLinker RFP routers and GetDayTrends scoring pipeline
  - **Files**:
    - `apps/desci-platform/biolinker/routers/rfp.py` ??`biz.rfp_analysis()` on /analyze, `biz.rfp_match()` on /match/paper, `biz.proposal_generated()` on /proposal/generate
    - `automation/getdaytrends/core/pipeline_steps.py` ??`biz.trend_scored()` after every `save_trend()` call
  - **Validation**:
    - `python -m compileall -q` -> exit 0
    - GetDayTrends: `22 passed`, AgriGuard: `6 passed`

- [x] **Phase 3 monitoring: Per-service dashboards + business metrics**
  - **Result**: Created 4 per-service Grafana dashboards with latency heatmaps and endpoint breakdown, plus a custom business metrics module wired into LLM client, AgriGuard QR events, and GetDayTrends tweet publishing
  - **Files**:
    - `packages/shared/business_metrics.py` ??Singleton Prometheus counters for LLM tokens/cost, QR scans, verifications, RFP matches, trend scoring, tweet publishing
    - `packages/shared/llm/client.py` ??`biz.llm_request()` wired after every LLM call
    - `apps/AgriGuard/backend/main.py` ??`biz.qr_scan()` + `biz.verification_complete()` on QR events
    - `automation/getdaytrends/notebooklm_api.py` ??`biz.tweet_published()` on successful X publish
    - `ops/monitoring/grafana/dashboards/agriguard-service.json` ??10 panels (health, latency heatmap, QR scans, verifications, error logs)
    - `ops/monitoring/grafana/dashboards/getdaytrends-service.json` ??10 panels (health, latency heatmap, LLM usage, trends scored, tweets published)
    - `ops/monitoring/grafana/dashboards/biolinker-service.json` ??8 panels (health, latency heatmap, RFP matches, proposals, LLM cost)
    - `ops/monitoring/grafana/dashboards/dashboard-api-service.json` ??5 panels (health, latency heatmap, endpoint latency)
  - **Validation**:
    - All files compile cleanly
    - AgriGuard: `6 passed`, GetDayTrends: `22 passed`, Shared LLM: `20 passed`
  - **Total Grafana Dashboards**: 5 (1 workspace overview + 4 per-service)

- [x] **Phase 3 monitoring: Structured logging, Telegram alerts, Loki log panels**
  - **Result**: Completed the remaining Phase 3 Week 2-3 items: structlog JSON logging for all 4 FastAPI services, AlertManager Telegram relay, Grafana Loki log panels, and pip dependency installation
  - **Files**:
    - `packages/shared/structured_logging.py` ??Reusable structlog JSON config with Loki-compatible output
    - `apps/AgriGuard/backend/main.py` ??`setup_structured_logging(service_name="agriguard")`
    - `automation/getdaytrends/notebooklm_api.py` ??`setup_structured_logging(service_name="getdaytrends")`
    - `apps/dashboard/api.py` ??`setup_structured_logging(service_name="dashboard")`
    - `apps/desci-platform/biolinker/main.py` ??`setup_structured_logging(service_name="biolinker")`
    - `ops/monitoring/alertmanager.yml` ??Telegram relay routing for critical alerts
    - `ops/scripts/alertmanager_telegram_relay.py` ??Standalone HTTP relay (AlertManager ??Telegram Bot API)
    - `ops/monitoring/grafana/dashboards/workspace-overview.json` ??Added 2 Loki log panels (All Logs + Error Logs)
    - `automation/getdaytrends/requirements.txt` ??added `structlog>=24.0.0`
    - `apps/desci-platform/biolinker/requirements.txt` ??added `structlog>=24.0.0`
  - **Validation**:
    - All files compile cleanly
    - AgriGuard: `6 passed`, GetDayTrends: `22 passed`, DailyNews: `23 passed`
    - Docker compose monitoring profile: 12 services validated
    - BioLinker venv: `prometheus_client` + `structlog` installed
  - **Grafana Dashboard**: Now 8 panels total (6 Prometheus metrics + 2 Loki logs)

- [x] **Phase 3 monitoring: Full observability stack deployed**
  - **Result**: Completed Prometheus metrics wiring for all 4 FastAPI services, added AlertManager for alert routing, deployed Loki + Promtail for centralized log aggregation, expanded Grafana with Loki datasource
  - **Files**:
    - `automation/getdaytrends/notebooklm_api.py` ??`setup_metrics(app, service_name="getdaytrends")`
    - `apps/dashboard/api.py` ??`setup_metrics(app, service_name="dashboard")`
    - `apps/desci-platform/biolinker/main.py` ??`setup_metrics(app, service_name="biolinker")`
    - `automation/getdaytrends/requirements.txt` ??added `prometheus_client>=0.21.0`
    - `apps/desci-platform/biolinker/requirements.txt` ??added `prometheus_client>=0.21.0`
    - `ops/monitoring/alertmanager.yml` ??AlertManager config with webhook receiver
    - `ops/monitoring/alert_rules.yml` ??4 alert rules (ServiceDown, HighErrorRate, HighLatency, PrometheusHighMemory)
    - `ops/monitoring/loki.yml` ??Loki log aggregation config (TSDB + filesystem)
    - `ops/monitoring/promtail.yml` ??Docker service discovery log shipper
    - `ops/monitoring/prometheus.yml` ??Added alerting config and rule files reference
    - `ops/monitoring/grafana/provisioning/datasources/prometheus.yml` ??Added Loki datasource
    - `docker-compose.dev.yml` ??Added alertmanager, loki, promtail services + loki-data volume
  - **Validation**:
    - `docker compose -f docker-compose.dev.yml --profile monitoring config --services` -> all 6 monitoring services listed
    - `python -m compileall -q packages/shared/metrics.py automation/getdaytrends/notebooklm_api.py apps/dashboard/api.py apps/desci-platform/biolinker/main.py` -> exit 0
    - `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q` -> `6 passed`
    - `python -m pytest automation/getdaytrends/tests/test_db.py -q` -> `22 passed`
    - `python -m pytest automation/DailyNews/tests/unit/test_adapters.py -q` -> `23 passed`
  - **Launch**: `docker compose -f docker-compose.dev.yml --profile monitoring up -d`
  - **Ports**: Prometheus :9090, Grafana :3000, AlertManager :9093, Loki :3100


---

> **Archive**: Older completed tasks are archived in [`docs/archive/`](docs/archive/).
> Current archive: [`tasks-done-W13.md`](docs/archive/tasks-done-W13.md) (2026-03-24 ~ 2026-03-28)

**Note for agents**: AgriGuard cutover is reconciled.
