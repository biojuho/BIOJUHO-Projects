# Schema Transactional Index Guard

- Date: 2026-06-05
- Source repo: `OpenHands/OpenHands`
- Source commit: `57b0da3df60794ea05e25258ad81a661034293d5`
- Source signal: `PLTF-2895: event_callback index - use plain CREATE INDEX (#14651)`
- Source URL: https://github.com/OpenHands/OpenHands/commit/57b0da3df60794ea05e25258ad81a661034293d5
- Local status: adopted
- Global objective complete: `false`

## Source Signal

OpenHands changed an Alembic event-callback index migration away from an autocommit/concurrent index path and documented that the migration harness requires a plain CREATE INDEX inside the normal transaction.

## A/B Contract

- A: Allow schema and migration files to introduce `CREATE INDEX CONCURRENTLY`, `DROP INDEX CONCURRENTLY`, `postgresql_concurrently=True`, or `autocommit_block()` without a repo-level regression check.
- B: Add a focused schema snapshot regression guard that scans the repo's active schema and migration files and fails with exact path/line evidence if those concurrent/autocommit patterns appear.

Adopted B. This keeps current local migrations on plain transactional index creation while making future deviations visible in the existing schema drift test suite.

## Local Changes

- `tests/test_schema_snapshot.py`
  - Added `SCHEMA_INDEX_GUARD_FILES` for getdaytrends, DailyNews, DeSci, AgriGuard, and shared local schema/index files.
  - Added `CONCURRENT_INDEX_PATTERNS` for concurrent CREATE/DROP index SQL, Alembic `postgresql_concurrently`, and Alembic `autocommit_block`.
  - Added `test_schema_migrations_use_transactional_index_creation` with exact path/line offender output.

## Verification

- `python -m pytest tests\test_schema_snapshot.py -q` -> `8 passed, 1 skipped`
- `python -m pytest tests\test_schema_snapshot.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q` -> `27 passed, 1 skipped`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-schema-transactional-index-guard-2026-06-05.json` -> `6/6 passed`

## Completion State

- `global_objective_complete=false`
