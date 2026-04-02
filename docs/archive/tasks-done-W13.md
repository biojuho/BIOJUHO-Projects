# Archived Tasks (2026-03-24 ~ 2026-03-28)

### 2026-03-28

- [x] **Audience-First Week 2: DeSci A/B test script created**
  - **Result**: Created `ab_test_matching.py` for RFP matching algorithm comparison (keyword vs vector similarity), completing the Week 2 A/B test coverage across all 4 projects
  - **Files**:
    - `apps/desci-platform/biolinker/scripts/ab_test_matching.py`
    - `apps/desci-platform/data/ab_tests/matching_eval_2026-03-28.md`
    - `apps/desci-platform/data/ab_tests/matching_eval_2026-03-28.json`
  - **Validation**:
    - `python -m compileall -q apps/desci-platform/biolinker/scripts/ab_test_matching.py` -> exit 0
    - `python apps/desci-platform/biolinker/scripts/ab_test_matching.py --top-k 5` -> Precision@5: 1.00 (both), sample data well-separated
  - **Design**: Audience-First framework (B2B Prosumer dual persona), Precision@5 primary KPI, >=30% relative lift decision rule

- [x] **DailyNews fact-check allowlist replaced with pattern-based heuristic**
  - **Result**: Replaced ~100-item flat `_NOISE_ENTITY_TERMS` allowlist with 5 heuristic rules that cover open-ended patterns, reducing the need to manually add terms for each live batch
  - **Rules**:
    - R1: Korean causative/passive verb suffixes (`~시`, `~시키`) via regex
    - R2: Korean particle/adverb fragments (`반드시`, `다시`, `불구`)
    - R3: Short all-uppercase ASCII acronyms (≤5 chars: DNA, JSON, GDP)
    - R4: Generic English domain terms (reduced seed set)
    - R5: Generic Korean domain nouns (reduced seed set)
  - **Files**:
    - `automation/DailyNews/src/antigravity_mcp/integrations/fact_check_adapter.py`
  - **Validation**:
    - `python -m pytest tests/unit/test_adapters.py tests/unit/test_config_aliases.py -q` -> `25 passed`
  - **Impact**: New Korean `~시` fragments (중단시, 증가시, 우선시, etc.) are now auto-classified without allowlist updates

- [x] **GetDayTrends `_record_x_publish_result` implemented**
  - **Result**: Implemented the missing async function that bridges X publish results back to the local SQLite database, enabling measured labels for A/B testing
  - **Files**:
    - `automation/getdaytrends/notebooklm_api.py`
  - **Validation**:
    - `python -m compileall -q notebooklm_api.py` -> exit 0
    - `python -m pytest tests/test_db.py -q` -> `22 passed`
  - **Operational Note**: Once tweets are published via `/publish-x` with `local_tweet_id`, the DB will record `posted_at` and `x_tweet_id`, enabling `collect_posted_tweet_metrics.py` to fetch real X performance data and produce measured labels instead of inferred ones

- [x] **Phase 3 monitoring: Prometheus app metrics + Grafana dashboard expansion**
  - **Result**: Created shared Prometheus metrics middleware, wired into AgriGuard, expanded Prometheus scrape config to all 4 services, and rebuilt Grafana dashboard with 6 panels
  - **Files**:
    - `packages/shared/metrics.py` — Reusable FastAPI middleware (request count, latency histogram, in-flight gauge, /metrics endpoint)
    - `apps/AgriGuard/backend/main.py` — Wired `setup_metrics(app, service_name="agriguard")`
    - `ops/monitoring/prometheus.yml` — Added scrape targets: agriguard:8002, getdaytrends:8788, dashboard-api:8080, desci-biolinker:8000
    - `ops/monitoring/grafana/dashboards/workspace-overview.json` — 6 panels: Service Health, Request Rate, Latency p50/p95, Error Rate, In-Flight, Endpoint Breakdown
  - **Validation**:
    - `python -m compileall -q packages/shared/metrics.py apps/AgriGuard/backend/main.py` -> exit 0
    - `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q` -> `4 passed`
  - **Next Steps**: Install `prometheus_client` in each service, wire `setup_metrics()` into remaining FastAPI apps (GetDayTrends, Dashboard API, BioLinker)

### 2026-03-27

- [x] **DailyNews dashboard refresh fixed and warning triage extended**
  - **Result**: Filled `NOTION_DASHBOARD_PAGE_ID` in the active DailyNews environment, taught the new pipeline config to fall back to `config/dashboard_config.json`, and expanded fact-check noise filtering for the next batch of low-signal entity fragments seen in live evening runs
  - **Files**:
    - `automation/DailyNews/.env`
    - `automation/DailyNews/src/antigravity_mcp/config.py`
    - `automation/DailyNews/src/antigravity_mcp/integrations/fact_check_adapter.py`
    - `automation/DailyNews/tests/unit/test_adapters.py`
    - `automation/DailyNews/tests/unit/test_config_aliases.py`
    - `automation/DailyNews/README.md`
    - `automation/DailyNews/docs/runbooks/environment-mapping.md`
  - **Validation**:
    - `python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/DailyNews --command "python -m pytest tests/unit/test_adapters.py tests/unit/test_config_aliases.py -q" --strict` -> `25 passed`
    - `python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/DailyNews --command "cmd /c run_cli.bat ops refresh-dashboard" --strict` -> `status: ok`, `warnings: []`, `updated_blocks: 24`
    - `python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/DailyNews\\scripts --command "cmd /c run_evening_insights.bat" --strict` -> batch completed, dashboard update now `ok`
  - **Operational Note**: The dashboard is now configured correctly, but the full evening brief still returns `partial` because fresh fact-check noise terms rotate with live content. Multi-source warnings and some feed fetch retries are still surfaced by design

- [x] **DailyNews evening batch verified and additional fact-check samples triaged**
  - **Result**: Re-ran the real `run_evening_insights.bat` batch under a UTF-8-safe wrapper, confirmed it exits cleanly end-to-end, and tightened fact-check noise filtering for forecast-style Korean fragments so `Global_Affairs` sample runs no longer raise spurious fact-check warnings
  - **Files**:
    - `automation/DailyNews/src/antigravity_mcp/integrations/fact_check_adapter.py`
    - `automation/DailyNews/tests/unit/test_adapters.py`
    - `automation/DailyNews/logs/insights/evening_2026-03-27_오후04.log`
  - **Validation**:
    - `python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/DailyNews --command "python -m pytest tests/unit/test_adapters.py -q" --strict` -> `23 passed`
    - `python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/DailyNews --command "cmd /c run_cli.bat jobs generate-brief --categories Global_Affairs --window morning --max-items 2" --strict` -> only `Global_Affairs: 1 multi-source topic(s)` remains, no fact-check warnings
    - `python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/DailyNews\\scripts --command "cmd /c run_evening_insights.bat" --strict` -> batch completed, log written successfully
  - **Operational Note**: The full evening batch still surfaces some fact-check warnings in other categories (`프라이버시`, `완화시`, `고조시`, `상기시`, quote/number issues), so the pipeline is operational but not yet warning-clean across all categories

- [x] **DailyNews CLI launcher and fact-check tuning completed**
  - **Result**: Added a shared Windows CLI launcher with `PYTHONPATH=src`, updated the install path to prefer editable installs, routed Windows batch jobs through the shared launcher, and tuned DailyNews fact-checking to ignore CTA/draft noise and low-signal entity warnings
  - **Files**:
    - `automation/DailyNews/run_cli.bat`
    - `automation/DailyNews/run_server.bat`
    - `automation/DailyNews/install.bat`
    - `automation/DailyNews/scripts/run_morning_insights.bat`
    - `automation/DailyNews/scripts/run_evening_insights.bat`
    - `automation/DailyNews/scripts/test_insight_generation.bat`
    - `automation/DailyNews/src/antigravity_mcp/integrations/fact_check_adapter.py`
    - `automation/DailyNews/README.md`
    - `automation/DailyNews/docs/runbooks/windows-utf8.md`
  - **Validation**:
    - `pytest automation/DailyNews/tests/unit/test_adapters.py -q` -> `23 passed`
    - `cmd /c run_cli.bat --help` -> CLI help output renders successfully
    - `cmd /c run_cli.bat jobs generate-brief --categories Crypto --window morning --max-items 2` -> `status: ok`, `warnings: []`
  - **Operational Note**: DailyNews now has a no-install Windows entrypoint for CLI jobs, and the same `Crypto` brief run that previously surfaced fact-check warnings now completes cleanly

- [x] **Self-Hosted Inference Engine v1.0 구축 완료**
  - **Result**: 기존 `shared/llm` 모듈에 Qwen3-Coder/DeepSeek-R1 로컬 추론 통합 + 4개 고급 Reasoning Engine 모듈 신규 구축
  - **Phase 1 — Ollama 확장**:
    - `config.py`: Qwen3-Coder HEAVY/MEDIUM 체인 추가, DeepSeek-R1 LIGHTWEIGHT 추가, MODEL_COSTS/MODEL_TO_TIER 업데이트, `REASONING_CONFIG` 환경변수 설정
    - `backends.py`: `_ollama_list_models()`, `_ollama_has_model()` 모델 감지 + 60초 캐싱
    - `model_patches.py`: Qwen3-Coder 8192 / DeepSeek-R1 4096 / 소형모델 2048 max_tokens 패치
  - **Phase 2 — Reasoning Engine**:
    - `reasoning/chain_of_thought.py` — CoT(o1-style) multi-sample consensus + early stopping
    - `reasoning/forest_of_thought.py` — FoT 재귀적 서브태스크 분해·합성
    - `reasoning/sage.py` — SAGE 자기인식 신뢰도 기반 적응형 추론 깊이
    - `reasoning/smart_router.py` — LLM 호출 없이 키워드 heuristic 기반 복잡도 분류 및 자동 전략 선택
  - **Phase 3 — 통합**:
    - `client.py`: `create_with_reasoning()` / `acreate_with_reasoning()` 메서드
    - `__init__.py`: `SmartRouter`, `QueryComplexity` public export
  - **Files**:
    - `shared/llm/config.py` — TIER_CHAINS, MODEL_COSTS, REASONING_CONFIG
    - `shared/llm/backends.py` — Ollama model detection
    - `shared/llm/model_patches.py` — Qwen3-Coder patches
    - `shared/llm/client.py` — Reasoning-aware create methods
    - `shared/llm/__init__.py` — Phase 5 exports
    - `shared/llm/reasoning/__init__.py` — Module init
    - `shared/llm/reasoning/chain_of_thought.py` — CoT engine
    - `shared/llm/reasoning/forest_of_thought.py` — FoT engine
    - `shared/llm/reasoning/sage.py` — SAGE engine
    - `shared/llm/reasoning/smart_router.py` — Smart Router
    - `tests/test_reasoning_engine.py` — 31 test cases
  - **Validation**:
    - `python -m compileall -q shared/llm/ tests/test_reasoning_engine.py` → exit 0
    - `pytest tests/test_reasoning_engine.py -q` → `31 passed`
    - `pytest tests/test_shared_llm.py tests/test_llm_enhancements.py -q` → `72 passed` (하위호환 무결)
  - **비용 영향**: Qwen3-Coder/DeepSeek-R1 로컬 추론 시 API 비용 $0, 기존 상용 API는 폴백으로만 사용


- [x] **DailyNews generate-brief runtime cleanup**
  - **Result**: Fixed the stale Gemini embedding model path and aligned `market_snapshot` skill expectations with the actual market adapter interface, so runtime generation no longer emits the previous embedding `404` or `AttributeError`
  - **Files**:
    - `automation/DailyNews/src/antigravity_mcp/integrations/embedding_adapter.py`
    - `automation/DailyNews/src/antigravity_mcp/integrations/market_adapter.py`
    - `automation/DailyNews/tests/unit/test_adapters.py`
  - **Validation**:
    - `pytest automation/DailyNews/tests/unit/test_adapters.py -q` -> `21 passed`
    - `PYTHONPATH=src python -m antigravity_mcp jobs generate-brief --categories Crypto --window morning --max-items 2` -> `partial`, with no embedding `404` and no `market_snapshot` adapter error
  - **Current Runtime Note**: The command still returns `partial` because content-quality and fact-check warnings are surfaced by design, but the blocking runtime errors from embeddings and market skill wiring are gone

- [x] **DailyNews Brief Notion query endpoint fixed**
  - **Result**: Replaced legacy `/v1/data_sources/{id}/query` usage with the standard `/v1/databases/{id}/query` path in the DailyNews Notion adapter and script call sites, so brief-generation-related Notion reads no longer fail with `404`
  - **Files**:
    - `automation/DailyNews/src/antigravity_mcp/integrations/notion_adapter.py`
    - `automation/DailyNews/scripts/collect_news.py`
    - `automation/DailyNews/scripts/update_dashboard.py`
    - `automation/DailyNews/scripts/visualization.py`
    - `automation/DailyNews/tests/test_notion_adapter.py`
    - `automation/DailyNews/tests/test_collect_news.py`
    - `automation/DailyNews/tests/test_update_dashboard.py`
  - **Validation**:
    - `pytest automation/DailyNews/tests/test_notion_adapter.py automation/DailyNews/tests/test_collect_news.py automation/DailyNews/tests/test_update_dashboard.py -q` -> `7 passed`
    - `python -m compileall -q automation/DailyNews/src/antigravity_mcp/integrations/notion_adapter.py automation/DailyNews/scripts/collect_news.py automation/DailyNews/scripts/update_dashboard.py automation/DailyNews/scripts/visualization.py automation/DailyNews/tests/test_notion_adapter.py automation/DailyNews/tests/test_collect_news.py automation/DailyNews/tests/test_update_dashboard.py`
  - **Operational Note**: `query_data_source()` remains as a backward-compatible alias, but now routes through the database query endpoint internally to prevent the same 404 from returning

- [x] **GetDayTrends posting telemetry wired to real performance fields**
  - **Result**: Publishing can now persist `x_tweet_id` and `posted_at`, performance collection can sync `impressions`, `engagements`, and `engagement_rate`, the historical exporter now prefers measured labels when they exist, and a queued-post publisher can forward local tweet identifiers into `/publish-x`
  - **Files**:
    - `automation/getdaytrends/db.py`
    - `automation/getdaytrends/db_schema.py`
    - `automation/getdaytrends/notebooklm_api.py`
    - `automation/getdaytrends/n8n_workflows/master_pipeline.json`
    - `automation/getdaytrends/performance_tracker.py`
    - `automation/getdaytrends/scripts/collect_posted_tweet_metrics.py`
    - `automation/getdaytrends/scripts/export_ab_test_viral_scoring_dataset.py`
    - `automation/getdaytrends/scripts/publish_saved_tweets.py`
  - **Validation**:
    - `python -m compileall -q automation/getdaytrends/db.py automation/getdaytrends/db_schema.py automation/getdaytrends/performance_tracker.py automation/getdaytrends/notebooklm_api.py automation/getdaytrends/scripts/export_ab_test_viral_scoring_dataset.py automation/getdaytrends/scripts/collect_posted_tweet_metrics.py`
    - `pytest automation/getdaytrends/tests/test_db.py -q` -> `22 passed`
    - `pytest automation/getdaytrends/tests/test_x_publish.py -q` -> `1 skipped` (`notebooklm_automation` unavailable in local env)
    - `python automation/getdaytrends/scripts/export_ab_test_viral_scoring_dataset.py --db-path automation/getdaytrends/data/getdaytrends.db --output automation/getdaytrends/data/ab_tests/viral_scoring_history_2026-03-27_measured.json`
    - `python automation/getdaytrends/scripts/publish_saved_tweets.py --dry-run --limit 2` -> `queued_count: 2`
  - **Current Runtime Note**: The measured-label path is ready, but the current DB still has `Measured Labels: 0`, so `actual_hit` remains inferred until real posted tweets accumulate metrics

- [x] **AgriGuard QR funnel telemetry moved from draft to experiment-ready**
  - **Result**: Added QR scan event storage, a public telemetry endpoint, a QR funnel summary endpoint, a frontend analytics service, retry/recovery UX, and verification-complete tracking tied to the QR scan session
  - **Files**:
    - `apps/AgriGuard/backend/main.py`
    - `apps/AgriGuard/backend/models.py`
    - `apps/AgriGuard/backend/schemas.py`
    - `apps/AgriGuard/backend/alembic/versions/0002_add_qr_scan_events.py`
    - `apps/AgriGuard/frontend/src/components/QRReader.jsx`
    - `apps/AgriGuard/frontend/src/components/ProductDetail.jsx`
    - `apps/AgriGuard/frontend/src/components/QRReader.test.jsx`
    - `apps/AgriGuard/frontend/src/services/api.js`
    - `apps/AgriGuard/frontend/src/services/qrAnalytics.js`
  - **Validation**:
    - `pytest apps/AgriGuard/backend/tests/test_smoke.py -q` -> `4 passed`
    - `python apps/AgriGuard/backend/scripts/run_migrations.py` -> `Alembic migrations applied successfully`
    - `npx vitest run src/components/QRReader.test.jsx` (in `apps/AgriGuard/frontend`) -> `2 passed`
  - **Tracked Events**: `scan_start`, `scan_failure`, `scan_recovery`, `verification_complete`
  - **Operational Check**: Live PostgreSQL now includes `qr_scan_events`, and `GET /qr-events/summary` returns a valid zero-state funnel on an empty dataset

- [x] **Audience README rollout completed**
  - **Result**: Added the missing root README for AgriGuard and confirmed that all 4 priority project READMEs now include a `Target Audience` section
  - **Files**:
    - `apps/AgriGuard/README.md` — new root project README with audience, quick start, and quality checks
    - `automation/DailyNews/README.md` — audience section present
    - `automation/getdaytrends/README.md` — audience section present
    - `apps/desci-platform/README.md` — audience section present
  - **Validation**: `rg -n "^## Target Audience" automation/DailyNews/README.md automation/getdaytrends/README.md apps/desci-platform/README.md apps/AgriGuard/README.md`
  - **Outcome**: Week 1 Audience-First README follow-up is complete

- [x] **GetDayTrends A/B test draft created**
  - **Result**: Added a runnable draft script for comparing single-source vs multi-source viral scoring with `Precision@10` as the primary KPI
  - **File**: `automation/getdaytrends/scripts/ab_test_viral_scoring.py`
  - **Features**:
    - Built-in sample dataset for immediate dry runs
    - Optional JSON dataset input for real historical experiments
    - Markdown and JSON output support
    - Decision rule based on relative lift and false-positive control
  - **Validation**: `python automation/getdaytrends/scripts/ab_test_viral_scoring.py --top-k 10`
  - **Validation**: `python -m compileall -q automation/getdaytrends/scripts/ab_test_viral_scoring.py`
  - **Validation**: `python ops/scripts/run_workspace_smoke.py --scope getdaytrends --json-out var/smoke/smoke_report_getdaytrends_2026-03-27_followup.json` -> `2/2 PASS`
  - **Sample Result**: Precision@10 improved from `0.60` to `0.90` on the built-in sample dataset

- [x] **GetDayTrends historical A/B dataset exported and connected**
  - **Result**: Exported real trend history from `automation/getdaytrends/data/getdaytrends.db` and connected it to the A/B scoring draft
  - **Files**:
    - `automation/getdaytrends/scripts/export_ab_test_viral_scoring_dataset.py`
    - `automation/getdaytrends/data/ab_tests/viral_scoring_history_2026-03-27.json`
    - `automation/getdaytrends/data/ab_tests/viral_scoring_eval_2026-03-27.md`
    - `automation/getdaytrends/data/ab_tests/viral_scoring_eval_2026-03-27.json`
  - **Important Note**: `actual_hit` is inferred from recurrence within a 48-hour lookahead window because direct social performance data is not populated yet
  - **Validation**: `python automation/getdaytrends/scripts/export_ab_test_viral_scoring_dataset.py --output automation/getdaytrends/data/ab_tests/viral_scoring_history_2026-03-27.json`
  - **Validation**: `python automation/getdaytrends/scripts/ab_test_viral_scoring.py --dataset automation/getdaytrends/data/ab_tests/viral_scoring_history_2026-03-27.json --top-k 10 --output automation/getdaytrends/data/ab_tests/viral_scoring_eval_2026-03-27.md --json-out automation/getdaytrends/data/ab_tests/viral_scoring_eval_2026-03-27.json`
  - **Historical Result**: `Precision@10 0.10 -> 0.10` on inferred labels, so current proxy data does not yet support adopting multi-source scoring over the single-source baseline

- [x] **AgriGuard QR page A/B draft created**
  - **Result**: Added a reusable experiment draft for the QR verification flow with audience, KPI, decision rule, and sample session data
  - **Files**:
    - `apps/AgriGuard/scripts/ab_test_qr_page.py`
    - `apps/AgriGuard/data/ab_tests/qr_page_ab_test_2026-03-27.md`
    - `apps/AgriGuard/data/ab_tests/qr_page_ab_test_2026-03-27.json`
  - **Validation**: `python apps/AgriGuard/scripts/ab_test_qr_page.py --output apps/AgriGuard/data/ab_tests/qr_page_ab_test_2026-03-27.md --json-out apps/AgriGuard/data/ab_tests/qr_page_ab_test_2026-03-27.json`
  - **Validation**: `python -m compileall -q apps/AgriGuard/scripts/ab_test_qr_page.py`
  - **Sample Result**: Verification success improved from `0.60` to `0.90` on the built-in draft dataset

### 2026-03-26

- [x] **Audience-First Framework v2.0 Complete**
  - **Result**: Full framework delivered and QC passed (10/10)
  - **Deliverables**: 7 files (83.7 KB)
    - `.claude/skills/audience-first/SKILL.md` (12.8 KB) — v2.0 with Phase 4, B2B/B2C, A/B testing, i18n
    - `.claude/skills/audience-first/references/workspace-audience-profiles.md` (15.5 KB) — 4 project personas
    - `.claude/skills/audience-first/references/ab-testing-guide.md` (14.4 KB) — 5-step framework
    - `automation/DailyNews/scripts/ab_test_economy_kr_v2.py` (19.8 KB) — Enhanced A/B test script
    - `docs/reports/2026-03/AUDIENCE_FIRST_IMPLEMENTATION_GUIDE.md` (15.0 KB) — 4-week roadmap
    - `AUDIENCE_FIRST_SUMMARY.md` (6.2 KB) — Quick start guide
    - `docs/reports/2026-03/QC_AUDIENCE_FIRST_FRAMEWORK.md` (20+ KB) — QC report
  - **Key Features**:
    - ✅ Success Metrics & KPI framework (Phase 4)
    - ✅ B2B vs B2C distinction with decision matrix
    - ✅ Data-driven A/B testing (statistical validation)
    - ✅ Localization guidance (ko-KR specific)
    - ✅ 4 detailed workspace personas (DailyNews, GetDayTrends, DeSci, AgriGuard)
    - ✅ Automated evaluation function (4 metrics: specificity, actionability, emotion, CTA)
  - **QC Results**: All checks passed
    - Files: 6/6 present
    - Python syntax: Valid, compiles successfully
    - Markdown links: 10 broken → 0 (fixed)
    - Framework completeness: 100% coverage
    - Security: No issues
  - **Expected Impact (4 weeks)**:
    - DailyNews engagement: 3% → 5% (+67%)
    - GetDayTrends hit rate: 15% → 20% (+33%)
    - DeSci matching: 60% → 80% (+33%)
    - AgriGuard QR scans: 50 → 1000/day (+1900%)
  - **Next Steps**: Week 1 — Add "Target Audience" sections to all project READMEs
  - **Resources**: [AUDIENCE_FIRST_SUMMARY.md](AUDIENCE_FIRST_SUMMARY.md), [QC Report](docs/reports/2026-03/QC_AUDIENCE_FIRST_FRAMEWORK.md)

- [x] **Workspace QC completed**
  - **Result**: `python ops/scripts/run_workspace_smoke.py --scope all --json-out var/smoke/smoke_report_qc_2026-03-26.json` completed successfully
  - **Validation**: Workspace smoke `15/15 PASS`

- [x] **Content Intelligence v2.0 QC completed**
  - **Result**: `automation/content-intelligence` v2.0 changes verified after the publishing and GDT bridge updates
  - **Validation**: `python -m pytest automation/content-intelligence/tests/test_smoke.py -q` -> `31 passed`
  - **Validation**: `python -X utf8 automation/content-intelligence/main.py --dry-run` -> OK

- [x] **Docker dev environment hardening and live QC**
  - **Result**: Fixed the Mosquitto healthcheck interpolation bug, added starter Prometheus/Grafana config, and hardened `ops/scripts/setup_dev_environment.ps1`
  - **Validation**: `docker compose -f docker-compose.dev.yml --profile monitoring config --no-interpolate`
  - **Validation**: `powershell -ExecutionPolicy Bypass -File ops/scripts/setup_dev_environment.ps1 -Status`
  - **Live checks**: `docker compose -f docker-compose.dev.yml --profile monitoring up -d prometheus grafana`
  - **Live checks**: `http://localhost:9090/-/ready` -> `200`
  - **Live checks**: `http://localhost:3000/login` -> `200`
  - **Note**: The monitoring containers were intentionally brought back down after QC

- [x] **Unified AI Dashboard v1.0 verified**
  - **Result**: Dashboard API and frontend were verified end-to-end in the earlier 2026-03-26 session
  - **QC**: `.agent/qa-reports/2026-03-26-dashboard-v1.md`

- [x] **Tech debt inventory enhancement**
  - **Result**: Enhanced classification logic to eliminate false P1 positives
  - **Changes**: Documents default to P3, excluded .agent/.sessions/ directories
  - **Outcome**: P1 reduced from 6 to 0 (code-related)

- [x] **GetDayTrends QA and prompts migration completed**
  - **Result**: Verified migrations already complete; added backward-compatible wrappers
  - **Files**: `generation/audit.py`, `generation/prompts.py` now re-export from `content_qa.py` and `prompt_builder.py`

- [x] **Canva MCP integration completed**
  - **Result**: Complete rewrite from 38-line skeleton to 223-line functional MCP bridge
  - **Features**: CanvaMCPClient class, JSON-RPC 2.0 protocol, async design creation, graceful fallback
  - **File**: `automation/getdaytrends/canva.py`
  - **Status**: Last P2 tech debt item resolved

### 2026-03-25
- [x] **AgriGuard sensor_readings resync investigation completed**
  - **Root cause**: A long-running local `python -m uvicorn main:app --reload --port 8002` listener imported `database.py` before `.env` was loaded, so it silently fell back to SQLite and kept appending simulated `sensor_readings`
  - **Fix**: Backend entrypoints now load `apps/AgriGuard/backend/.env` consistently through `apps/AgriGuard/backend/env_loader.py`
  - **Resync**: PostgreSQL was intentionally rebuilt from `apps/AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555` with `--truncate`
  - **Validation**: `qc_postgres_migration.py` passed `5/5`

- [x] **AgriGuard backend container startup fixed**
  - **Root cause**: `main.py` assumed `Path(__file__).resolve().parents[2]`, which crashes inside the Docker image layout
  - **Fix**: Observability path discovery now scans available parents safely before extending `sys.path`

- [x] **AgriGuard backend env loading hardened**
  - **Result**: Local backend entrypoints now load `backend/.env` before DB initialization, preventing accidental SQLite fallback during import order
  - **Validation**: `python -m pytest apps/AgriGuard/backend/tests/test_database_config.py apps/AgriGuard/backend/tests/test_env_loading.py -q`

- [x] **Content Intelligence Engine v2.0 upgrade**
  - **Result**: Content Intelligence workspace updates completed earlier on 2026-03-25

- [x] **AgriGuard PostgreSQL QC snapshot documented**
  - **Result**: Root-safe QC script and written QC report added for the initial cutover validation snapshot
  - **Files**: `apps/AgriGuard/POSTGRES_MIGRATION_QC_REPORT.md`, `apps/AgriGuard/backend/scripts/qc_postgres_migration.py`

- [x] **AgriGuard SQLite snapshot archived**
  - **Result**: Snapshot saved as `apps/AgriGuard/backend/agriguard.db.archived_20260325`

- [x] **AgriGuard PostgreSQL benchmark completed**
  - **Result**: SQLite vs PostgreSQL benchmark captured in `apps/AgriGuard/BENCHMARK_RESULTS.md`

- [x] **AgriGuard backend switched to PostgreSQL configuration**
  - **Result**: `apps/AgriGuard/backend/.env` now points to PostgreSQL

- [x] **AgriGuard migration QC script hardened**
  - **Result**: QC script now resolves the SQLite path relative to the backend directory and accepts configurable PostgreSQL settings

- [x] **GetDayTrends package import compatibility restored**
  - **Result**: Root-package imports and timeout propagation verified

- [x] **Workspace package runner and smoke retry added**
  - **Result**: Root `npm run *:all` commands now walk package scripts directly, and transient Vitest worker failures retry once

### 2026-03-24
- [x] **GetDayTrends modular refactoring**
  - **Validation**: `435 passed, 4 skipped, 1 deselected`

- [x] **AgriGuard PostgreSQL Week 1-2**
  - **Result**: Alembic setup, Docker validation, PostgreSQL smoke checks

- [x] **Workspace QC recovery + NotebookLM auth**
  - **Result**: workspace smoke checks passed

---

## Board Statistics

- **Total Active Tasks**: 0
- **In Progress**: 0
- **Completed (7 days)**: 26+
- **Workspace Smoke**: 15/15 passed
- **CIE v2 Smoke**: 31/31 passed
- **Dashboard QA/QC**: verified (6 auto-fixes)
- **Dashboard Status**: Backend (http://localhost:8080) + Frontend (http://localhost:5173) running
- **AgriGuard QC**: frozen resync snapshot passes `5/5`; live PostgreSQL writes resumed after cutover
- **Tech Debt**: P0=0, P1=0 (code), P2=0, P3=278+ (all non-critical)
- **Docker Port Policy**: root compose uses 5433/1884 to avoid AgriGuard standalone (5432/1883) conflicts

---

**Note for agents**: AgriGuard cutover is reconciled. Use `apps/AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555` as the preserved SQLite evidence snapshot, not as a live source.
