# DeSci Job Stream Partial False Guard

Generated at: `2026-06-05T12:10:30+09:00`

## Source Signal

- Repository: `google/adk-python`
- Source commit: `https://github.com/google/adk-python/commit/cd81f7bde91d`
- Upstream signal: `fix(streaming): Ensure final partial=False frame is always yielded`
- Local mapping: DeSci job progress SSE should expose an explicit terminal
  frame marker, so clients can distinguish partial progress snapshots from the
  final succeeded or failed snapshot without relying only on stream closure.

## A/B Contract

- Baseline: `JobSnapshot` exposed job status and progress, and the stream sent
  terminal snapshots, but the payload did not explicitly mark whether a frame was
  still partial progress or the final terminal frame.
- Variant: add a backward-compatible `partial` boolean to `JobSnapshot`.
  `queued` and `running` snapshots emit `partial=true`; `succeeded` and `failed`
  snapshots emit `partial=false` through both polling and SSE.
- Primary KPI: backend SSE tests prove non-terminal frames are partial and the
  final or late-subscriber terminal frame is `partial=false`.
- Guardrails: frontend `useJobProgress` continues resolving terminal SSE frames
  and remains status-driven; no credentialed runtime is required.
- Decision: adopted.

## Changed Files

- `apps/desci-platform/backend/models.py`
  - Adds the `JobSnapshot.partial` response field.
- `apps/desci-platform/backend/services/job_manager.py`
  - Derives `partial` from terminal job status when snapshots are built.
- `apps/desci-platform/backend/tests/test_jobs.py`
  - Proves polling and SSE terminal snapshots expose `partial=false`.
- `apps/desci-platform/frontend/src/hooks/useJobProgress.test.jsx`
  - Locks frontend handling of `partial=true` progress and `partial=false`
    terminal frames.

## Verification

- `python -m pytest apps\desci-platform\backend\tests\test_jobs.py -q --tb=line`
  - `10 passed`
- `npm.cmd --prefix apps\desci-platform\frontend run test -- src\hooks\useJobProgress.test.jsx`
  - `3 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_jobs.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q --tb=line`
  - `29 passed`
- `python -m py_compile apps\desci-platform\backend\models.py apps\desci-platform\backend\services\job_manager.py ops\scripts\autoresearch_completion_audit.py ops\scripts\autoresearch_objective_coverage.py`
  - passed
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-job-partial-false-2026-06-05.json`
  - `passed=7`, `failed=0`, `total=7`
- `git diff --check`
  - passed

## Remaining Boundary

This cycle hardens the local DeSci job stream contract. It does not add a new
streaming runtime, change job storage, or require live user credentials.

- Product proof baseline for this commit: `39cc4a6`.
- `global_objective_complete=false`
