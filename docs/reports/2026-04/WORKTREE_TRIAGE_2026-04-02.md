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
- Completed:
  - `4. GetDayTrends dashboard monitoring stack`
  - commit: `13e2393 feat(getdaytrends): add dashboard logs and monitoring stack`
- Validation completed on the dashboard/monitoring slice:
  - `python -m pytest automation/getdaytrends/tests/test_dashboard.py -q` -> `13 passed`
  - `python -m py_compile automation/getdaytrends/dashboard.py`
  - `docker compose -f docker-compose.monitoring.yml config`
  - Loki `/ready` -> `ready`
- Completed:
  - `5. Temporary scratch/error output cleanup`
  - commit: `8f4cd3c chore(cleanup): remove temporary error outputs`
- Completed:
  - `6. AgriGuard lint gate closure`
  - commit: `cd7ffb5 fix(agriguard): satisfy vite config lint`
- Validation completed after the lint fix:
  - `npm run lint` in `apps/AgriGuard/frontend`
  - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`
- Completed:
  - `7. Shared cache + GetDayTrends hot-path index hardening`
  - commit: `7ad6552 feat(getdaytrends): add shared cache and hot-path indexes`
- Validation completed on the cache/index slice:
  - `python -m pytest automation/getdaytrends/tests/test_db.py -q` -> `27 passed`
  - `python -m pytest packages/shared/tests/test_cache.py -q` -> `15 passed`
  - `python ops/scripts/run_workspace_smoke.py --scope getdaytrends` -> `2/2 PASS`
  - `docker compose -f docker-compose.dev.yml config --services` -> includes `redis`
- Follow-up architecture hardening was applied after the push-prep checkpoint:
  - added `docs/reports/2026-04/VIBE_CODING_ARCH_REVIEW_2026-04-02.md`
  - hardened AgriGuard cache fallback so the rate limiter remains safe even when shared cache imports fail
  - rewrote `automation/content-intelligence/storage/x_publisher.py` to use async `httpx` with an explicit X user-context token contract
  - updated `automation/content-intelligence/config.py`, `.env.example`, and `tests/test_smoke.py` to lock the contract in place
- Validation completed on the architecture hardening slice:
  - forced cache-fallback regression check with both cache import paths blocked -> `cache.incr(...) == 1`
  - `python -m pytest automation/content-intelligence/tests/test_smoke.py -q` -> `77 passed`
  - `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q -k "not test_qr_ab_script_handles_missing_variant_data"` -> `5 passed, 1 deselected`
  - `python ops/scripts/run_workspace_smoke.py --scope workspace` -> `5/5 PASS`
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard` -> `3/3 PASS`

## Snapshot

- Git state: `main...origin/main [ahead 4]`
- File counts at checkpoint time: `79 modified / 50 untracked / 10 deleted`
- Validation already re-run on the dirty tree:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace` -> `5/5 PASS`
  - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`
  - `python -m pytest automation/content-intelligence/tests/test_smoke.py -q` -> `34 passed`

## Current Push-prep Snapshot

- Git state now: `main...origin/main [ahead 12]`
- The broad multi-area worktree described above has mostly been split into standalone commits.
- Remaining live unsplit worktree now spans AgriGuard plus content-intelligence hardening:
  - `apps/AgriGuard/backend/iot_service.py`
  - `apps/AgriGuard/backend/main.py`
  - `apps/AgriGuard/backend/models.py`
  - `apps/AgriGuard/frontend/src/components/ColdChainMonitor.jsx`
  - `apps/AgriGuard/frontend/vite.config.js`
  - `automation/content-intelligence/.env.example`
  - `automation/content-intelligence/config.py`
  - `automation/content-intelligence/storage/x_publisher.py`
  - `automation/content-intelligence/tests/test_smoke.py`
  - `apps/AgriGuard/frontend/src/hooks/`
  - `docs/reports/2026-04/VIBE_CODING_ARCH_REVIEW_2026-04-02.md`
- Latest full-workspace validation still green:
  - `python ops/scripts/run_workspace_smoke.py --scope all` -> `18/18 PASS`
- Latest targeted follow-up validation:
  - `python -m pytest automation/content-intelligence/tests/test_smoke.py -q` -> `77 passed`
  - `python ops/scripts/run_workspace_smoke.py --scope workspace` -> `5/5 PASS`
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard` -> `3/3 PASS`
- Interpretation:
  - push-readiness is still primarily blocked by review/commit hygiene now, not by known targeted regressions

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
