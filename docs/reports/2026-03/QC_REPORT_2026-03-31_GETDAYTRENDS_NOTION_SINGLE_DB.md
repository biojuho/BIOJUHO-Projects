# QC Report: GetDayTrends Notion Single-DB Upload

> **QC Date**: 2026-03-31
> **Scope**: `automation/getdaytrends` Notion upload path revalidation
> **Status**: **PASS**

---

## Executive Summary

The `getdaytrends` Notion upload issue was re-checked and the single-database upload flow is now behaving as intended.

The core outcome is simple:

- main Notion database upload works
- Content Hub secondary database upload stays off by default
- false-return external save cases are now surfaced as real failures instead of being silently ignored

---

## What Changed

The upload path was tightened in four places:

1. `ENABLE_CONTENT_HUB` became the explicit switch for secondary Notion writes.
2. `CONTENT_HUB_DATABASE_ID` alone no longer enables Hub writes.
3. Content Hub writes are skipped unless storage mode, flag, and DB id are all valid.
4. `save_to_notion()` returning `False` is now recorded as an external save failure.

Supporting changes were also made to:

- `.env.example`
- `scripts/setup_content_hub.py`
- regression tests for Content Hub enable/disable behavior

---

## Commands Executed

```bash
python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/getdaytrends --command "python -m pytest tests/test_notion_content_hub.py tests/test_e2e.py tests/test_main.py tests/test_scraper.py -q" --strict
python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/getdaytrends --command "python main.py --one-shot --dry-run --limit 1 --no-alerts" --strict
python .agents/skills/windows-encoding-safe-test/scripts/run_utf8_safe.py --cwd automation/getdaytrends --command "python main.py --one-shot --limit 1 --no-alerts" --strict
```

In addition, a direct live QC was run against the `_step_save` path using the real local Notion configuration so that the actual write target could be verified.

---

## QC Result

### Regression and smoke checks

- `43 passed`
- UTF-8-safe runner reported no encoding warnings
- config validation returned no errors

### Effective runtime configuration

```text
storage_type='notion'
enable_content_hub=False
content_hub_active=False
validation_errors=[]
```

### One-shot execution result

Both entrypoint runs completed successfully.

The live `main.py --one-shot --limit 1 --no-alerts` run ended with `0/0` saved, but this was caused by the collected trend failing the quality threshold, not by a Notion upload failure.

### Direct live upload verification

The real save path was then verified with a controlled QC save.

- `step_save_success_count=1`
- `run_errors=[]`
- main DB matches: `1`
- Content Hub DB matches: `0`

Latest confirmed page created in the main Notion DB:

- `[트렌드 #1] [QC] single-db pipeline 2026-03-31 22:18:16 — 2026-03-31 22:18`

Interpretation:

- upload to the primary `Getdaytrends` database is working
- secondary Hub writes are not occurring in default operation
- the current behavior matches the single-DB requirement

---

## Evidence

- Main database: `Getdaytrends`
- Local env state during QC:
  - `NOTION_DATABASE_ID` set
  - `CONTENT_HUB_DATABASE_ID` set
  - `ENABLE_CONTENT_HUB=false`
- Latest direct QC write:
  - main DB: `1` match
  - hub DB: `0` matches

---

## Final Assessment

**Operational result**: PASS

**Requirement status**: satisfied

`getdaytrends` is currently operating in single-Notion-database mode, with the secondary Content Hub path disabled unless explicitly re-enabled with `ENABLE_CONTENT_HUB=true`.
