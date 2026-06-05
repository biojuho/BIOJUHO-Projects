# AutoResearch DeSci Job Stream Fallback Guard

Date: 2026-06-05

## Source Signal

- Repository: `pydantic/pydantic-ai`
- Commit signal: `49f62a386041` `Fix incomplete streamed response when event_stream_handler doesn't consume the stream (#5771)`
- Adjacent signal: `ed31bdd64e11` `Handle UploadedFile consistently with FileUrl in UI adapters (#5772)`
- Local mapping: DeSci job workflows expose long-running paper/RFP work through `/jobs/{job_id}/events` and the frontend `useJobProgress` hook. The launch risk is an incomplete or interrupted SSE stream that never delivers the terminal snapshot to the operator UI.

## A/B Contract

- Baseline: job SSE and polling fallback existed, but the tests only covered a fully consumed EventSource success stream and an EventSource-unavailable polling path.
- Variant: add regression guards for two product-critical stream edges:
  - backend: a late subscriber to an already terminal job receives exactly one terminal SSE snapshot;
  - frontend: if EventSource emits a running snapshot and ends before the terminal snapshot, polling fetches the latest job and resolves the user-facing promise.
- Primary KPI: the job UI can still converge to a completed result after an incomplete streamed response.
- Guardrails: no API behavior change, no auth policy change, no new dependencies, and no credentialed external calls.
- Decision rule: adopt if focused backend and frontend tests pass and no formatting/audit guard regresses.

## Result

- Adopted variant: yes.
- Added backend guard: `test_terminal_job_streams_snapshot_for_late_subscriber`.
- Added frontend guard: `falls back to polling when EventSource ends before the terminal snapshot`.
- Changed paths:
  - `apps/desci-platform/backend/tests/test_jobs.py`
  - `apps/desci-platform/frontend/src/hooks/useJobProgress.test.jsx`

## Verification

```text
python -m pytest apps/desci-platform/backend/tests/test_jobs.py -q --tb=line
10 passed in 0.78s
```

```text
npm.cmd --prefix apps/desci-platform/frontend run test -- src/hooks/useJobProgress.test.jsx
Test Files 1 passed
Tests 3 passed
```

```text
python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-job-stream-fallback-2026-06-05.json
passed=7, failed=0, total=7
```

## Next Cycle

- Continue the source-backed loop by either hardening DeSci uploaded-file adapter parity or reviewing OpenHands timestamp/async identity signals against local agent workflow evidence.
- If DeSci job-stream behavior changes again, rerun the DeSci scope smoke before adoption.
