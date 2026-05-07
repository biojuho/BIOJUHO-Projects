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
- `docs/reports/2026-04/GETDAYTRENDS_V2_PRD_2026-04-02.md`
- `docs/reports/2026-04/CONTENT_AUTOMATION_V2_PRD_2026-04-02.md`

## Daily Snapshot

> Auto-generated on **2026-05-07 09:38 KST**

| Item | Status |
|:-----|:-------|
| Branch | `main` @ `8cd3ed8` |
| Last Smoke | 21/21 PASS (2026-05-06) |
| getdaytrends | ✅ |
| DailyNews | ✅ |
| CIE | ✅ (인코딩 복원 완료) |
| AgriGuard | ✅ |
| DeSci | ✅ |
| Dashboard | ✅ |
| shared | ✅ |

### Recent Session (2026-05-07)

**System Modernization** — 전체 시스템 고도화

- Phase 1: CIE main.py mojibake 복원 + 레거시 파일 13개 삭제
- Phase 2: HANDOFF/CONTEXT/next-actions 문서 현대화
- Phase 3: CI/CD 강화 (PR 코멘트 자동 리포팅)
- Phase 4: Observability 점검

**Entry points**: `HANDOFF.md`, `next-actions.md`
