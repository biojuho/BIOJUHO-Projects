# AgriGuard Ready-Gate Live State Status View - 2026-07-05

## Source Check

- AutoResearch upstream checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Change

- `run_guarded_launch.py --status-only` now derives ready-gate `exists` and `sha256` from the live ready-gate file when the path is known.
- This prevents stale artifact-index metadata from reporting `ready_gate.exists=false` after the ready-gate JSON has already been generated.

## Verification

- `python -m pytest apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: `27 passed in 1.46s`
- Default prefix status check:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --status-only --status-json-out var\agriguard-guarded-launch-current-status-ready-gate-live-state.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Ready gate view: `found=true`, `exists=true`, `status=blocked`, `blocker_class=preflight_blocked`, `sha256=def6e54ecb7f0488271931f4bedbad772a28d2792c5c5f96475299304f3ccd06`
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Result: `passed=5, failed=0, total=5`, elapsed `2m59s`
- `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Result: `passed=9, failed=0, total=9`, elapsed `2m52s`

## Remaining Blocker

- Ready-gate status is now accurately reflected from the live file.
- Launch remains blocked only at the expected external preflight blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
