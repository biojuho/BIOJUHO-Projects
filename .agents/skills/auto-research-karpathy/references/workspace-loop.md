# Workspace AutoResearch Loop

Use this reference for `D:\AI project` cycles.

## First Commands

Run these before editing:

```powershell
git status --short --branch
git ls-files -u
python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research.json --markdown-out docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md
```

If the worktree is dirty, identify owned paths for the current cycle and avoid
staging unrelated files.

## Project Surfaces

Use these scopes when choosing app-by-app validation:

- `workspace`: root contracts, security checks, shared package, dashboard.
- `desci`: `apps/desci-platform`, including product smoke, browser smoke,
  frontend, backend, contracts, release readiness.
- `agriguard`: `apps/AgriGuard`, including QR/product routes, frontend,
  backend, contracts.
- `mcp`: NotebookLM MCP, GitHub MCP, Canva MCP, DeSci research MCP, Telegram
  MCP, plus DailyNews unit paths.
- `getdaytrends`: `automation/getdaytrends`, including CLI, scheduler,
  content generation, and A/B scripts.
- `cie`: `automation/content-intelligence`.

## Existing A/B Entry Points

Prefer existing experiment scripts before adding new ones:

```powershell
python automation/getdaytrends/scripts/ab_test_viral_scoring.py --help
python apps/desci-platform/backend/scripts/ab_test_matching.py --help
python apps/AgriGuard/scripts/ab_test_qr_page.py --help
```

Use these as draft evaluators unless the cycle requires real traffic, external
publishing, or live user analytics.

## Browser and Product Smoke

For user-facing DeSci work:

```powershell
python apps/desci-platform/scripts/product_smoke.py --help
python apps/desci-platform/scripts/browser_smoke.py --help
```

Start local servers only when the smoke path requires them. Capture screenshots
or JSON evidence when UI changes are part of the objective. Treat missing
Playwright, unavailable browsers, or blocked ports as environment blockers only
after confirming the script help path works.

## Canonical Smoke Matrix

Run the smallest affected scope first:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope mcp --json-out var/workspace-smoke-mcp-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope getdaytrends --json-out var/workspace-smoke-getdaytrends-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope cie --json-out var/workspace-smoke-cie-auto-research.json
```

Use split scopes for interactive completion. The monolithic `--scope all` run
is useful for final evidence when time allows, but split schema v1 reports are
acceptable when they cover all required scopes.

## Cycle Report Template

Create `docs/reports/<year-month>/AUTO_RESEARCH_LOOP_<date>_<slug>.md` with:

- Objective
- Scope and owned paths
- External sources checked
- A/B hypothesis and decision rule
- Baseline evidence
- Variant evidence
- Adopt/reject decision
- Verification commands
- Completion audit: success criteria, prompt-to-artifact evidence, uncovered
  requirements, and whether the loop must continue
- Commit and push status
- Next cycle

## Commit and Push Procedure

Use explicit staging only:

```powershell
git add -- <owned-path-1> <owned-path-2>
git diff --cached --stat
git diff --cached --check
git commit -m "<type>(<scope>): <summary>"
git push origin HEAD
```

Do not stage broad globs in a dirty worktree. Do not push when targeted
verification fails, secrets are present, or the branch is not the intended
remote branch.
