# Context Guide

Lightweight navigation file for agents and contributors.

## Read order

1. `HANDOFF.md`
2. `TASKS.md`
3. `CLAUDE.md`
4. `CONTEXT.md`

## Workspace shape

- Active apps live under `apps/`
- Automation pipelines live under `automation/`
- MCP servers live under `mcp/`
- Shared code lives under `packages/shared`
- Operational scripts live under `ops/scripts`
- Dated reports live under `docs/reports/`
- Inactive or frozen material lives under `archive/`
- Runtime data and logs live under `var/`

## Quick commands

```bash
python bootstrap_legacy_paths.py
python ops/scripts/run_workspace_smoke.py --scope workspace
python ops/scripts/healthcheck.py
npm run build:all
```

## Notes for agents

- Prefer canonical paths in code and docs
- Use `workspace-map.json` as the workspace source of truth
- Only rely on legacy root paths after running bootstrap
- Treat `archive/` and `var/` as excluded from normal discovery unless the task is explicitly about them
- Pull requests now use an intention-first template and a deterministic triage workflow (`.github/workflows/pr-triage.yml`)

## Helpful docs

- `QUICK_START.md`
- `ONBOARDING.md`
- `CONTRIBUTING.md`
- `docs/QUALITY_GATE.md`
- `docs/reports/2026-03/COMPREHENSIVE_PROJECT_HEALTH_REPORT.md`

## Daily Snapshot (2026-04-02)

### Workspace QC Restored

**Status**: Complete (`18/18 PASS` after targeted repair)

**Evidence**:
- `python -m pytest tests -q` in `automation/getdaytrends` -> `453 passed, 6 skipped, 1 deselected`
- `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`
- `TASKS.md`

**TASKS.md**: The save-path schema drift in GetDayTrends was repaired and the workspace is green again, but the worktree is still not release-clean.

## Recent Sessions (2026-04-02)

### GetDayTrends QC Recovery

**Status**: Complete

**What**:
- Repaired `init_db()` / migration drift so fresh or drifted DBs regain `tweets.variant_id` and `tweets.language`.
- Re-ran the focused storage/save-path regressions, the full `automation/getdaytrends` suite, and the workspace smoke matrix.

**Entry points**:
- `automation/getdaytrends/db_schema.py`
- `automation/getdaytrends/tests/test_db.py`
- `docs/reports/2026-04/WORKTREE_TRIAGE_2026-04-02.md`

### Ops Governance Commit

**Status**: Complete

**What**:
- Isolated PR triage, VibeDebt audit, and heartbeat-monitor improvements into their own standalone commit

**Entry points**:
- `.github/workflows/pr-triage.yml`
- `.github/workflows/tech-debt-audit.yml`
- `ops/scripts/pr_triage.py`
- `ops/scripts/tech_debt_scanner.py`

### Infra Baseline Commit

**Status**: Complete

**What**:
- Isolated AgriGuard port policy, backend dependency cleanup, and CI Python baseline alignment into their own standalone commit

**Entry points**:
- `docker-compose.dev.yml`
- `apps/AgriGuard/backend/main.py`
- `.github/workflows/agriguard-ci.yml`

### Dashboard Slice Commit

**Status**: Complete

**What**:
- Isolated the dashboard app change set into its own standalone commit
- Left the broader infra, automation, and shared-runtime worktree untouched for later split

**Entry points**:
- `apps/dashboard/`
- `docs/reports/2026-04/WORKTREE_TRIAGE_2026-04-02.md`

### Docs Sync + Worktree Revalidation

**Status**: Complete

**What**:
- Revalidated the current live worktree rather than relying only on the 2026-04-01 notes
- Confirmed canonical smoke still passes with the current uncommitted diff
- Recorded the active change clusters so the next session can resume without re-triaging the entire repo

**Entry points**:
- `HANDOFF.md`
- `TASKS.md`
- `docs/reports/2026-04/WORKTREE_TRIAGE_2026-04-02.md`
- `var/reports/workspace-smoke-latest.txt`
- `var/reports/workspace-smoke-all-latest.txt`

## Daily Snapshot (2026-04-01)

### Monitoring And Metrics Loop

**Status**: Recorded

**Evidence**:
- `var/debt/2026-03-31-radon.json`
- `automation/getdaytrends/data/tweet_metrics_local_smoke.json`
- `TASKS.md`

**TASKS.md**: TODO 0건 — Pushgateway E2E and tweet-metrics loop hardening recorded

## Recent Sessions (2026-04-01)

### Pushgateway E2E + Metrics Collector Hardening

**Status**: Complete

**What**:
- Revalidated Pushgateway -> Prometheus ingestion using live `vibedebt_*` metrics
- Hardened `collect_posted_tweet_metrics.py` for local no-token runs while preserving CI fail-fast semantics
- Added regression tests for both local skip and CI error modes

**Entry points**:
- `ops/scripts/push_debt_metrics.py`
- `.github/workflows/collect-tweet-metrics.yml`
- `automation/getdaytrends/scripts/collect_posted_tweet_metrics.py`
- `automation/getdaytrends/tests/test_collect_posted_tweet_metrics.py`

## Daily Snapshot (2026-03-31)

### Workspace QC

**Status**: Complete (`15/15 PASS`)

**Evidence**:
- `var/smoke/manual-smoke-2026-03-31.json`
- `docs/reports/2026-03/QC_REPORT_2026-03-31_DAILY_WORKSPACE.md`

**TASKS.md**: TODO 0건 — 모든 계류 작업 완료

## Recent Sessions (2026-03-31)

### Docker Port Conflict Resolution + Task Closure

**Status**: ✅ Complete (QC PASS)

**What**:
- Root compose 포트를 AgriGuard 독립 compose와 분리 (5433/1884/8003)
- DailyNews/GetDayTrends 프롬프트 마이그레이션 → 불필요 결정 (동적 빌더 유지)
- Notion 속성 v13 표준 스키마 통합 (20+개 → 8개)

**Entry points**:
- `docker-compose.dev.yml` (포트 정책 헤더 19~26행)
- `.env.example` (포트 기본값 11~14행)
- `docs/DOCKER_SETUP_GUIDE.md` (서비스 포트 목록)

### PR Triage Adaptation

**Status**: Enabled (repo-native adaptation, not full ACPX runtime)

**What**:
- Added intention-first PR template
- Added deterministic PR triage workflow and script
- Added documentation explaining why the repo adopts the principle without autonomous PR close/land behavior

**Entry points**:
- `.github/pull_request_template.md`
- `.github/workflows/pr-triage.yml`
- `ops/scripts/pr_triage.py`
- `docs/PR_TRIAGE_SYSTEM.md`

## Recent Sessions (2026-03-26)

### Audience-First Framework v2.0

**Status**: ✅ Complete (QC passed 10/10)

**What**: Full framework for audience-centric product/content development with A/B testing

**Deliverables**: 7 files (83.7 KB)
- `.claude/skills/audience-first/SKILL.md` — Core framework with Phase 4 (KPIs), B2B/B2C distinction
- `.claude/skills/audience-first/references/workspace-audience-profiles.md` — 4 project personas
- `.claude/skills/audience-first/references/ab-testing-guide.md` — 5-step A/B testing framework
- `automation/DailyNews/scripts/ab_test_economy_kr_v2.py` — Enhanced A/B test script
- `docs/reports/2026-03/AUDIENCE_FIRST_IMPLEMENTATION_GUIDE.md` — 4-week roadmap
- `AUDIENCE_FIRST_SUMMARY.md` — Quick start guide
- `docs/reports/2026-03/QC_AUDIENCE_FIRST_FRAMEWORK.md` — QC report

**Entry Point**: [AUDIENCE_FIRST_SUMMARY.md](AUDIENCE_FIRST_SUMMARY.md)

**Next Steps**: Week 1 — Add "Target Audience" sections to all project READMEs
