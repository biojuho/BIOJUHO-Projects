# AutoResearch: Workspace Smoke Timeout Tree Cleanup

Date: 2026-06-04

## Source-backed prompt

The split completion audit recorded that a monolithic all-scope smoke run timed
out and left a getdaytrends pytest child process running. The runner already
returned timeout evidence, but it did not explicitly own and terminate the full
process tree.

## A/B contract

- Baseline: `run_workspace_smoke.py` delegated timeout behavior to
  `subprocess.run(..., timeout=600)`, which can terminate the direct process
  while child processes survive on Windows.
- Variant: run checks through an owned `Popen` process, create a killable process
  group, terminate the whole process tree on timeout, and preserve stdout/stderr
  in the existing timeout result.
- KPI: focused tests prove the tree terminator runs on timeout, and a live smoke
  scope still passes through the new process runner.

## Adopted variant

The process-tree timeout runner was adopted.

Implementation:

- `ops/scripts/run_workspace_smoke.py` now uses `run_command_with_timeout()` for
  smoke checks.
- Windows timeouts call `taskkill /PID <pid> /T /F`; POSIX timeouts kill the
  spawned process group.
- The existing timeout result contract is preserved: return code `124`,
  captured stdout/stderr tails, and elapsed seconds.
- `tests/test_workspace_smoke.py` now verifies that timeout cleanup calls the
  process-tree terminator and preserves post-kill output.

## Verification

- `python -m py_compile ops\scripts\run_workspace_smoke.py` -> PASS
- `python -m pytest tests\test_workspace_smoke.py tests\test_smoke_report_readers.py -q -p no:cacheprovider`
  -> `20 passed`
- `python ops\scripts\run_workspace_smoke.py --scope cie --json-out var\workspace-smoke-cie-timeout-hardening-2026-06-04.json`
  -> `2/2 PASS`

Live artifact summary:

- `schema_version`: `1`
- `status`: `complete`
- `summary`: `total=2`, `completed=2`, `passed=2`, `failed=0`, `remaining=0`
- `duration_seconds`: `27.422`
- Per-check timings: `cie compile=0.766s`, `cie tests=26.634s`

## Follow-up

This closes the orphan-child-process risk noted in the completion audit. A later
all-scope run can now timeout with stronger cleanup guarantees and still leave
partial schema-v1 evidence behind.
