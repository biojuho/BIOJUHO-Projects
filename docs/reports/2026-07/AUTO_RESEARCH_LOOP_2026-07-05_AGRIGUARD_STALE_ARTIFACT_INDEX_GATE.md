# AgriGuard Stale Artifact Index Gate

Date: 2026-07-05

## Loop

- External source refresh: `Veritas-7/autoresearch-skill-system` main/HEAD observed at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Baseline: a previously generated artifact index could still say `status: pass` while omitting newer consumer command metadata fields.
- Variant shipped: `run_guarded_launch.py --status-only` now derives `artifact_index.consumer_metadata_status` and classifies stale pass indexes as `artifact_index_blocked`.
- Adoption rule: adopt only if stale pass metadata is blocked, complete metadata remains ready, and AgriGuard/workspace gates remain green.

## Status Evidence

Current status-only capture:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --status-only
```

Captured at:

- `var\agriguard-guarded-launch-status-stale-index-gate.json`

Result:

- Top-level: `blocked`, `preflight_blocked`
- Artifact index status: `pass`
- Artifact index blocker class: `artifact_index_blocked`
- Artifact index consumer metadata status: `fail`

Fresh artifact-index regeneration:

```powershell
python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-artifact-index-current-regenerated.json --markdown-out var\agriguard-guarded-launch-artifact-index-current-regenerated.md
```

Expected fail-closed result:

- Exit code: 1
- Status: `fail`
- Blocker class: `artifact_index_blocked`
- Consumer command metadata status: `fail`

## Verification

- `python -m py_compile apps\AgriGuard\scripts\run_guarded_launch.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py`: passed.
- `python -m pytest apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`: 25 passed.
- `python -m pytest apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py -q`: 42 passed.
- `python scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-stale-artifact-index-gate.json`: complete, 5/5 passed.
- `python scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-stale-artifact-index-gate.json`: complete, 9/9 passed.

## Decision

Adopted. Status-only launch evidence now fails closed when an old artifact index omits the command metadata required by the current handoff consumer contract.

Remaining launch blocker: production launch still requires operator-provided Firebase Admin/service-account configuration outside this local repo change.
