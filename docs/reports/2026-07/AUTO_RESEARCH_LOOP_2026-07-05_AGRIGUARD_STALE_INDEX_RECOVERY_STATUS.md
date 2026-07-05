# AgriGuard Stale Artifact Index Recovery Status - 2026-07-05

## Source Check

- AutoResearch upstream checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Change

- Status-only guarded launch output now treats stale `status: pass` artifact indexes with missing consumer command metadata as requiring recovery.
- Added a stale-metadata recovery action and note.
- Reused the operator packet's guarded wrapper command as the recovery command when available.
- Preserved existing behavior for legitimate failing artifact indexes that already expose their own recovery command.

## Verification

- `python -m pytest apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: `26 passed in 1.38s`
- Default prefix status check:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --status-only --status-json-out var\agriguard-guarded-launch-current-status-stale-index-recovery.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Artifact index view: `status=pass`, `consumer_metadata_status=fail`, `blocker_class=artifact_index_blocked`
  - Recovery summary: `required=true`, `status=fail`, `blocker_class=artifact_index_recovery_blocked`
  - Recovery command shell: `powershell`
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Result: `passed=5, failed=0, total=5`, elapsed `5m56s`
- `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Result: `passed=9, failed=0, total=9`, elapsed `2m52s`

## Post-Recovery Operational Check

- Ran the emitted recovery path:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --emit-handoff --status-json-out var\agriguard-guarded-launch-status.json`
  - Result: exit `1`, expected fail-closed preflight stop at missing Firebase service-account file.
- Rechecked default status:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --status-only --status-json-out var\agriguard-guarded-launch-current-status-post-recovery.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Artifact index view after recovery: `status=pass`, `blocker_class=ready`, `consumer_metadata_status=pass`, `consumer_command_metadata_status=pass`
  - Recovery summary after recovery: `required=false`, `status=not_required`, `blocker_class=ready`

## Remaining Blocker

- The status artifact recovery contract is fixed locally, and the default prefix has been refreshed out of stale-index state.
- The default launch prefix still stops at the expected external preflight blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
