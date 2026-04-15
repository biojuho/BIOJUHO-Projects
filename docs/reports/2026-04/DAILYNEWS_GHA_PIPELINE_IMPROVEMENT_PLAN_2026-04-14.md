# DailyNews GitHub Actions Improvement Plan

Date: 2026-04-14
Scope: [dailynews-pipeline.yml](</d:/AI project/.github/workflows/dailynews-pipeline.yml>)

## Why this pass

The current workflow already runs the DailyNews job on schedule and on demand, but it still has a few operational gaps:

- overlapping scheduled and manual runs can waste runner time and compete for the same downstream resources,
- required runtime configuration is only discovered after dependency install and partial startup,
- manual inputs are loosely typed and not normalized before execution,
- success notifications do not describe the actual execution context,
- artifact upload does not make missing logs explicit.

## Improvements to apply now

1. Add workflow-level concurrency.
   This prevents duplicate runs from stacking when a scheduled run is delayed and a manual retry starts at the same time.

2. Normalize `workflow_dispatch` inputs before execution.
   Validate `max_items`, clamp the allowed range, and convert `force` into explicit run outputs that later steps can reuse consistently.

3. Add a preflight runtime configuration check.
   Fail fast when `NOTION_API_KEY`, `NOTION_REPORTS_DATABASE_ID`, or all LLM keys are missing.

4. Make notifications actionable.
   Include the run window label, `max_items`, and run URL so failures and successful heartbeats are easier to interpret from Telegram or Discord alone.

5. Make artifact behavior explicit.
   Upload logs on every run and warn rather than silently skipping when no files are found.

## Changes implemented in this pass

- `permissions: contents: read`
- `concurrency` guard for the workflow
- `Normalize run inputs` step with validated outputs
- `Verify required runtime configuration` step
- updated run command to consume normalized outputs
- step summary with execution context
- clearer Discord and Telegram messages
- `if-no-files-found: warn` for log artifacts
- `SUPABASE_DATABASE_URL` mirrored from `DATABASE_URL` for runtimes that prefer the canonical name
- canonical Notion secret fallback chain for `NOTION_API_KEY`, task DB, and reports DB
- pre-run smoke gate for `test_run_daily_news.py` and `test_config_aliases.py`

## Deferred follow-ups

- Switch `uv sync` to a lock-enforcing mode once the workspace lockfile policy is finalized.
- Add a lightweight workflow smoke test job for `automation/DailyNews/tests/test_run_daily_news.py`.
- Split morning and evening window handling into separate reusable workflow inputs if operators need more manual control.

## Session record

2026-04-15 update:

- Applied the workflow hardening directly in `.github/workflows/dailynews-pipeline.yml`.
- Added workflow-level `concurrency`, normalized `workflow_dispatch` inputs, and inserted a preflight runtime configuration check.
- Added a pre-run smoke gate for `automation/DailyNews/tests/test_run_daily_news.py` and `automation/DailyNews/tests/unit/test_config_aliases.py`.
- Reworked Notion secret mapping to prefer DailyNews-specific secrets first and then fall back to canonical workspace secrets.
- Updated success and failure notifications so they include the run window label, `max_items`, and the run URL.

Verification recorded in this session:

- YAML parse check passed for `.github/workflows/dailynews-pipeline.yml`.
- `pytest automation/DailyNews/tests/test_run_daily_news.py -q` passed.
- `pytest automation/DailyNews/tests/test_run_daily_news.py automation/DailyNews/tests/unit/test_config_aliases.py -q` passed with `11 passed`.

Outstanding operator follow-up:

- If DailyNews has a dedicated Notion tasks database, set `DAILYNEWS_NOTION_TASKS_DB_ID` in repository secrets so task writes no longer fall back to the reports database ID.
