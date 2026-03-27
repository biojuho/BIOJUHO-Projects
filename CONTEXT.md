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

## Helpful docs

- `QUICK_START.md`
- `ONBOARDING.md`
- `CONTRIBUTING.md`
- `docs/QUALITY_GATE.md`
- `docs/reports/2026-03/COMPREHENSIVE_PROJECT_HEALTH_REPORT.md`

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
