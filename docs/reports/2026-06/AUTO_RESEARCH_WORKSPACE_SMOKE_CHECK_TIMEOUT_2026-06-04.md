# AutoResearch Workspace Smoke Check Timeout - 2026-06-04

## Objective

Close the remaining timeout-control gap exposed by the DeSci guardrail run:
when an outer shell or agent timeout kills `run_workspace_smoke.py` before the
runner's own 600-second check timeout, the runner cannot execute its existing
process-tree cleanup.

## A/B Contract

- Baseline: each smoke check used a fixed 600-second internal timeout. Operators
  could not set the runner's timeout below an outer CI/tool timeout.
- Variant: add `--check-timeout <seconds>` and thread it through `run_check()`
  and `run_one()`, preserving the default 600-second behavior.
- Primary KPI: focused tests prove custom timeout values reach
  `run_command_with_timeout()`, and a live smoke scope passes with the option.
- Guardrail: existing partial JSON and process-tree cleanup behavior remains
  unchanged.

## Verification

- `python -m py_compile ops\scripts\run_workspace_smoke.py tests\test_workspace_smoke.py`
  - Result: pass.
- `python -m pytest tests\test_workspace_smoke.py`
  - Result: `28 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope cie --check-timeout 120 --json-out var\workspace-smoke-cie-check-timeout-2026-06-04.json`
  - Result: `2/2` passed; JSON status `complete`.

## Decision

Adopted. Operators can now set the smoke runner's internal per-check timeout
below any outer shell, CI, or agent timeout and let the existing process-tree
terminator own cleanup and partial JSON evidence.
