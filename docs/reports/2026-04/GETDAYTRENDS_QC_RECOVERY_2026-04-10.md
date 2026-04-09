# GetDayTrends QC Recovery (2026-04-10)

Checkpoint recorded after restoring the GetDayTrends Notion upload path, scheduled execution path, and local cache health.

## Status

- Overall status: PASS
- Scope: `automation/getdaytrends`, shared cache, Windows scheduled runner
- Date verified: 2026-04-10
- Notion sync for this write-up: blocked in current Codex session because the Notion connector returned `Auth required`

## Root Causes Repaired

### 1. Scheduled task drift

- Windows Task Scheduler task `GetDayTrends_CurrentUser` was disabled.
- The task action still pointed to the stale legacy path:
  - `D:\AI 프로젝트\getdaytrends\run_scheduled_getdaytrends.ps1`
- This prevented automatic runs even when manual runs succeeded.

### 2. Missing local runner files

- The current workspace expected:
  - `automation/getdaytrends/run_scheduled_getdaytrends.ps1`
  - `automation/getdaytrends/run_getdaytrends.bat`
- Those runner files were not present in the active workspace, so the scheduled entrypoint could not be executed reliably.

### 3. Notion schema mismatch

- The active Notion database uses Korean property names such as:
  - `제목`, `주제`, `순위`, `생성시각`, `상태`, `바이럴점수`, `공감유도형`, `꿀팁형`, `찬반질문형`, `명언형`, `유머밈형`, `쓰레드`
- The legacy save path in code was still attempting English property names such as:
  - `Name`, `Topic`, `Rank`, `Created At`, `Status`, `Viral Score`
- Result: Notion page creation failed even when generation completed successfully.

### 4. Instructor backend API drift

- The installed Instructor/Gemini path exposes `chat.completions.create(...)`.
- The code was attempting `create_async(...)` for Gemini.
- This caused structured extraction fallback noise during runtime.

### 5. Missing runtime dependency

- `jsonref` was not installed in the active `.venv`.
- Instructor fallback logs exposed the missing dependency during structured extraction attempts.

### 6. Redis cache instability and noisy fallback

- Redis was unavailable initially, so the pipeline fell back correctly but logged repeated timeout noise.
- After Redis was brought online, a stale connection path could still emit:
  - `Event loop is closed`
- This was treated as a cache-path issue, not a pipeline-blocking issue.

## Changes Applied

### Scheduled runner and task recovery

- Added:
  - `automation/getdaytrends/run_scheduled_getdaytrends.ps1`
  - `automation/getdaytrends/run_getdaytrends.bat`
- Updated the Windows scheduled task action to the live workspace path:
  - `D:\AI project\automation\getdaytrends\run_scheduled_getdaytrends.ps1`
- Re-enabled `GetDayTrends_CurrentUser`

### Notion save-path repair

- Added a Korean-schema property builder in:
  - `automation/getdaytrends/storage.py`
- Ensured the active `save_to_notion(...)` path saves against the legacy Korean Notion database schema.

### Instructor compatibility repair

- Replaced backend-specific async assumptions with a backend-agnostic helper in:
  - `automation/getdaytrends/structured_output.py`
- The helper now supports both:
  - sync `create()`
  - async `create()`
- Expected Instructor retry/validation fallback noise was downgraded away from warning-level spam.

### Shared cache hardening

- Hardened:
  - `packages/shared/cache.py`
- Added short-term suspension after connection failures so Redis timeouts do not spam logs repeatedly.
- Reduced Redis connect/socket timeout to 1 second for faster fallback.
- Treated `RuntimeError: Event loop is closed` as a reconnectable cache-path error.

### Dependency and test updates

- Added dependency:
  - `jsonref>=1.1.0,<2.0`
  - file: `automation/getdaytrends/pyproject.toml`
- Added/updated tests in:
  - `automation/getdaytrends/tests/test_storage_edge_cases.py`
  - `automation/getdaytrends/tests/test_structured_output.py`
  - `packages/shared/tests/test_cache.py`

## Validation Performed

### Targeted tests

- `python -m pytest automation/getdaytrends/tests/test_storage.py automation/getdaytrends/tests/test_storage_edge_cases.py automation/getdaytrends/tests/test_notion_content_hub.py automation/getdaytrends/tests/test_structured_output.py automation/getdaytrends/tests/test_db_layer_resilience.py packages/shared/tests/test_cache.py -q`
  - result: `82 passed`

### Additional cache validation

- `python -m pytest packages/shared/tests/test_cache.py -q`
  - result: `17 passed`

### Syntax validation

- `python -m py_compile automation/getdaytrends/storage.py automation/getdaytrends/structured_output.py packages/shared/cache.py`
  - result: pass

### Real scheduled-run validations

- 2026-04-09 19:29 KST
  - confirmed `Notion save complete` in:
    - `automation/getdaytrends/logs/scheduler/run_2026-04-09_192747.log`
- 2026-04-09 19:35 KST
  - confirmed scheduled task path repair and successful run in:
    - `automation/getdaytrends/logs/scheduler/run_2026-04-09_193143.log`
- 2026-04-10 05:25 KST
  - confirmed successful run without Redis timeout spam in:
    - `automation/getdaytrends/logs/scheduler/run_2026-04-10_052351.log`
- 2026-04-10 07:17 KST
  - confirmed Notion save success in:
    - `automation/getdaytrends/logs/scheduler/run_2026-04-10_071336.log`
- 2026-04-10 07:20 KST
  - confirmed clean follow-up run with `errors=0` in:
    - `automation/getdaytrends/logs/scheduler/run_2026-04-10_071920.log`

## Redis Recovery Notes

- `docker compose -f docker-compose.dev.yml up -d redis` was not reliable on this machine because the command path hit a Windows paging-file related PowerShell failure.
- Redis was recovered via direct container run instead:
  - image: `redis:7-alpine`
  - container: `dev-redis`
  - port: `6379`
  - restart policy: `unless-stopped`
- Verified with:
  - `docker exec dev-redis redis-cli ping` -> `PONG`
  - shared cache round-trip -> `{'status': 'ok'}`

## Operational State At Record Time

- Scheduled task: enabled
- Scheduled task name: `GetDayTrends_CurrentUser`
- Last successful result observed: `LastTaskResult = 0`
- Next scheduled run observed during QC: `2026-04-10 09:00:00` KST
- Redis: healthy via local container
- Notion upload: healthy

## Remaining Notes

- Runtime QA and fact-check warnings may still appear for low-confidence or weak-context trends. Those are content-quality signals, not infrastructure failures.
- This report was not pushed to Notion because the current Notion connector session required re-authentication.

## Files Touched In This Recovery

- `automation/getdaytrends/storage.py`
- `automation/getdaytrends/structured_output.py`
- `automation/getdaytrends/run_scheduled_getdaytrends.ps1`
- `automation/getdaytrends/run_getdaytrends.bat`
- `automation/getdaytrends/pyproject.toml`
- `automation/getdaytrends/tests/test_storage_edge_cases.py`
- `automation/getdaytrends/tests/test_structured_output.py`
- `packages/shared/cache.py`
- `packages/shared/tests/test_cache.py`
