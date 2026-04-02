# Worktree Triage (2026-04-02)

Checkpoint created after validating the live worktree against the canonical smoke suite.

## Progress Since Triage

- Completed:
  - `1. Infra baseline alignment`
  - commit: `db27e71 chore(infra): align agriguard ports and ci baselines`
- Completed:
  - `2. Ops governance and debt observability`
  - commit: `b6b8cd3 feat(ops): add pr triage and vibedebt audit`
- Completed:
  - `3. Dashboard frontend quality gate and A/B panel`
  - commit: `b06f8f3 feat(dashboard): add ab performance panel and frontend tests`
- Validation completed on the committed infra slice:
  - `docker compose -f docker-compose.dev.yml config --services`
  - `python -m pytest tests -q` in `apps/AgriGuard/backend`
- Validation completed on the committed ops slice:
  - `python -m pytest tests/test_pr_triage.py -q`
  - `python -m py_compile ops/scripts/pr_triage.py`
  - `python ops/scripts/tech_debt_scanner.py --json-out var/debt/triage-check.json`
  - `python ops/scripts/push_debt_metrics.py --report-file var/debt/triage-check.json --dry-run`
- Validation completed on the committed dashboard slice:
  - `npm run lint`
  - `npm run test`
  - `npm run build`
  - `npm run check:bundle`
- Validation completed after the later GetDayTrends QC recovery:
  - root cause repaired: `tweets.variant_id` / `tweets.language` schema drift in fresh or marker-drifted DBs
  - `python -m pytest tests/test_storage.py tests/test_e2e.py tests/test_notion_content_hub.py tests/test_db.py -q` -> `41 passed`
  - `python -m pytest tests -q` in `automation/getdaytrends` -> `453 passed, 6 skipped, 1 deselected`
  - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`

## Snapshot

- Git state: `main...origin/main [ahead 4]`
- File counts at checkpoint time: `79 modified / 50 untracked / 10 deleted`
- Validation already re-run on the dirty tree:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace` -> `5/5 PASS`
  - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`
  - `python -m pytest automation/content-intelligence/tests/test_smoke.py -q` -> `34 passed`

## Suggested Commit Order

### 1. Infra baseline alignment

Status: committed in `db27e71`

**Why this can stand alone**

- Aligns local compose ports, AgriGuard backend defaults, and Python CI versions.
- Low coupling to the feature work in `automation/`.

**Include**

- `.env.example`
- `docker-compose.dev.yml`
- `docs/DOCKER_SETUP_GUIDE.md`
- `ops/scripts/setup_dev_environment.ps1`
- `apps/AgriGuard/backend/main.py`
- `apps/AgriGuard/backend/requirements.txt`
- `.github/workflows/agriguard-ci.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/desci-platform-quality.yml`
- `.github/workflows/github-mcp-ci.yml`
- cleanup of `apps/AgriGuard/backend/=0.23.0` and `apps/AgriGuard/backend/=2.1.0`

**Validation**

- `docker compose -f docker-compose.dev.yml config --services`
- `python ops/scripts/run_workspace_smoke.py --scope all`

### 2. Ops governance and debt observability

Status: committed in `b6b8cd3`

**Why this can stand alone**

- Adds repo governance and tech-debt reporting without changing product logic.
- Naturally grouped around `.github`, `ops`, and repo docs.

**Include**

- `.github/pull_request_template.md`
- `.github/workflows/pr-triage.yml`
- `.github/workflows/tech-debt-audit.yml`
- `.github/workflows/heartbeat-monitor.yml`
- `ops/scripts/pr_triage.py`
- `ops/scripts/tech_debt_scanner.py`
- `ops/scripts/push_debt_metrics.py`
- `ops/monitoring/prometheus.yml`
- `ops/monitoring/grafana/dashboards/tech-debt.json`
- `docs/PR_TRIAGE_SYSTEM.md`
- `docs/reports/2026-03/VIBEDEBT_PROPOSAL.md`
- `docs/reports/2026-03/QC_REPORT_2026-03-31_DAILY_WORKSPACE.md`
- `docs/reports/2026-03/QC_REPORT_2026-03-31_GETDAYTRENDS_NOTION_SINGLE_DB.md`
- `tests/test_pr_triage.py`

**Validation**

- `python -m pytest tests/test_pr_triage.py -q`
- `python -m py_compile ops/scripts/pr_triage.py`
- `python ops/scripts/tech_debt_scanner.py --json-out var/debt/triage-check.json`
- `python ops/scripts/push_debt_metrics.py --report-file var/debt/triage-check.json --dry-run`

### 3. Dashboard frontend quality gate and A/B panel

Status: committed in `b06f8f3`

**Why this can stand alone**

- Frontend-only product improvement with matching test/lint/bundle-budget support.
- Smoke runner changes are directly in support of this area.

**Include**

- `apps/dashboard/api.py`
- `apps/dashboard/package.json`
- `apps/dashboard/package-lock.json`
- `apps/dashboard/src/App.jsx`
- `apps/dashboard/src/App.test.jsx`
- `apps/dashboard/src/components/charts.jsx`
- `apps/dashboard/src/test/setup.js`
- `apps/dashboard/vitest.config.js`
- `apps/dashboard/eslint.config.js`
- `apps/dashboard/scripts/check-bundle-size.mjs`
- `ops/scripts/run_workspace_smoke.py`
- `tests/test_workspace_regressions.py`
- `tests/test_workspace_smoke.py`

**Validation**

- `npm run lint` in `apps/dashboard`
- `npm run test` in `apps/dashboard`
- `npm run build` in `apps/dashboard`
- `npm run check:bundle` in `apps/dashboard`

### 4. Content Intelligence audience and QA upgrade

**Why this can stand alone**

- Clear functional theme: personas, stronger QA, duplicate prevention, ROI and feedback loop.
- Already has focused smoke coverage.

**Include**

- `automation/content-intelligence/config.py`
- `automation/content-intelligence/main.py`
- `automation/content-intelligence/generators/content_engine.py`
- `automation/content-intelligence/prompts/content_generation.py`
- `automation/content-intelligence/storage/local_db.py`
- `automation/content-intelligence/storage/models.py`
- `automation/content-intelligence/collectors/base.py`
- `automation/content-intelligence/collectors/gdt_bridge.py`
- `automation/content-intelligence/regulators/checklist.py`
- `automation/content-intelligence/tests/test_smoke.py`
- `automation/content-intelligence/personas.json`
- `.github/workflows/content-intelligence.yml`
- `ops/scripts/roi_report.py`
- `docs/content-quality-improvement-proposal.md`

**Validation**

- `python -m pytest automation/content-intelligence/tests/test_smoke.py -q`

### 5. GetDayTrends runtime hardening

**Why this can stand alone**

- Focused on operational robustness: duplicate-run prevention, cookie security, budget safety, CI cleanup.

**Include**

- `automation/getdaytrends/main.py`
- `automation/getdaytrends/core/pipeline.py`
- `automation/getdaytrends/x_client.py`
- `automation/getdaytrends/requirements.txt`
- `automation/getdaytrends/db.py`
- `.github/workflows/getdaytrends.yml`
- `.github/workflows/collect-tweet-metrics.yml`

**Validation**

- `python ops/scripts/run_workspace_smoke.py --scope all`
- `python -m pytest automation/getdaytrends/tests -q`

### 6. Shared runtime foundation

**Why this should precede DailyNews if split**

- `automation/DailyNews` now imports pieces extracted into `packages/shared`.
- Keeping the shared layer in its own commit makes downstream DailyNews diff easier to review.

**Include**

- `packages/shared/circuit_breaker.py`
- `packages/shared/env_loader.py`
- `packages/shared/paths.py`
- `packages/shared/py.typed`
- `packages/shared/intelligence/__init__.py`
- `packages/shared/intelligence/topic_bridge.py`
- `packages/shared/llm/__init__.py`
- `packages/shared/llm/client.py`
- `tests/shared/llm/test_qa_regressions.py`
- `tests/conftest.py`
- `tests/test_live_reasoning.py`

**Validation**

- `python -m pytest tests/shared/llm/test_qa_regressions.py tests/test_live_reasoning.py -q`

### 7. DailyNews pipeline adoption and test reorganization

**Why this should follow the shared runtime commit**

- Depends on the shared circuit breaker and path/env helpers.
- Large enough to deserve its own review lane.

**Include**

- `automation/DailyNews/pyproject.toml`
- `automation/DailyNews/init_mock_db.py`
- `automation/DailyNews/scripts/ab_test_economy_kr_v2.py`
- `automation/DailyNews/scripts/news_bot.py`
- `automation/DailyNews/scripts/runtime.py`
- `automation/DailyNews/src/antigravity_mcp/**`
- `automation/DailyNews/tests/**`
- `.github/workflows/dailynews-pipeline.yml`
- `.github/workflows/dailynews-ab-economy-kr.yml`

**Specific note**

- The deleted flat manual files appear to be replaced by `automation/DailyNews/tests/manual/`.
- Keep that move in the same commit as the test reorganization so Git can track it as a rename/move more cleanly.

**Validation**

- `python -m pytest automation/DailyNews/tests/unit -q`
- `python ops/scripts/run_workspace_smoke.py --scope all`

## Likely Do-Not-Stage Artifacts

These look like generated outputs or local scratch files unless you intentionally want them versioned:

- `automation/DailyNews/coverage.json`
- `ops/scripts/_env_check.txt`
- `ops/scripts/_out2.txt`
- `out.txt`
- `temp.txt`
- `var/debt/*.json`
- `var/reports/*.json`
- `var/reports/*.txt`
- `packages/shared/intelligence/__pycache__/`

## Notes And Risks

- The current tree is development-safe but not release-clean. The broadest risk is reviewability, not immediate breakage.
- Workflow changes are spread across CI, scheduler heartbeat, DailyNews, GetDayTrends, and new content-intelligence automation. Keep CI-facing changes grouped so failures are easier to attribute.
- `packages/shared` and `automation/DailyNews` are coupled now. If you split them, commit the shared layer first.
- Console previews in this environment show mojibake for some Korean text, but UTF-8 byte checks for `automation/content-intelligence/personas.json` and `packages/shared/intelligence/topic_bridge.py` were clean. Treat the preview issue as terminal encoding noise unless a runtime bug proves otherwise.
- If you want the smallest next review slice, the safest first branchable chunk is `apps/dashboard` plus the smoke-runner support.
