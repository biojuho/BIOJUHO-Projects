# AutoResearch Loop - AgriGuard Two-Pass Handoff Status Index

## Objective

Make the guarded-launch handoff and artifact index converge on the same current
status view after artifact-index-backed status was added. The previous compact
status view could read the current artifact index, but a full `--emit-handoff`
wrapper run still needed deterministic ordering so the handoff packet and
artifact index did not preserve stale status evidence.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: run handoff, consumer, and artifact indexing once, then write the
  final status JSON after post-processing.
- Variant: when post-processing succeeds, refresh the status JSON after the
  first artifact index pass and then rerun handoff, consumer, and artifact
  indexing so the final human handoff and artifact index both see
  artifact-index-backed status.
- Primary KPI: live wrapper artifacts report
  `packet_artifact_index_recovery_summary.required=false`,
  `artifact_index.status=pass`, and the artifact index's `status_json` SHA
  matches the final status file SHA.
- Guardrails: focused wrapper/handoff/index tests and canonical AgriGuard smoke
  must pass.

## Change

`run_guarded_launch.py` now writes the refreshed status view before the second
handoff/consumer/artifact-index pass. That gives the second artifact index a
status file that already contains the current artifact-index-backed status view,
while the final deterministic status write preserves the same content and hash.

The regression test simulates both artifact-index invocations and asserts the
first index sees `artifact_index.found=false` while the second sees
`artifact_index.found=true`.

## Verification Commands

```powershell
python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py
```

Result: passed.

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q
```

Result: `39 passed in 2.63s`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.env.template --output-prefix agriguard-guarded-launch-status-index-hash-current-20260704 --emit-handoff --status-json-out var\agriguard-guarded-launch-status-index-hash-current-20260704-status.json
```

Result: expected exit code `1` because launch env-shape validation remains
blocked. The generated handoff and artifact index were internally coherent:

- `packet_artifact_index_recovery_summary.required=false`
- `packet_artifact_index_recovery_command_status=not_required`
- `artifact_index.status=pass`
- `missing_required_roles=[]`
- final status SHA:
  `9452899e58dc073c655c722767deb975300d89b3b630f434cf73132d0d7c2074`
- artifact index `status_json` SHA:
  `9452899e58dc073c655c722767deb975300d89b3b630f434cf73132d0d7c2074`

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-handoff-two-pass-fixed-20260704.json
```

Result: `passed=5`, `failed=0`, `total=5`, elapsed `8m32s`.

## Decision

Adopt the variant. The wrapper now converges the final status, handoff packet,
consumer view, and artifact index on the same artifact-index-backed recovery
state while preserving the real external blocker.

## Remaining Blocker

AgriGuard launch remains externally blocked until the operator supplies the real
Firebase Admin service-account JSON and production secret, pepper, public verify
URL, allowed origins, and database credentials outside the repository.

## Next Cycle

Continue reducing operator ambiguity around the env-shape blocker, or move to
the next product surface with failing live-click evidence.
