# AutoResearch Loop - AgriGuard Two-Pass Handoff Index

## Objective

Fix the remaining circular evidence drift between guarded-launch handoff
artifacts and the artifact index. After compact status learned to read the
current artifact-index JSON, a default `--emit-handoff` run could still leave
the handoff consumer JSON with a stale packet artifact-index recovery summary
because the handoff was rendered before the artifact index was regenerated.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: run handoff rendering, handoff consumption, and artifact indexing
  once after launch.
- Variant: when all post-processing commands succeed, run a second
  handoff-consumer-index pass so the final handoff and consumer artifacts read
  the freshly generated artifact index before the final index is written.
- Primary KPI: final status, handoff consumer, and artifact index all agree
  that artifact-index recovery is `not_required`.
- Guardrails: failed post-processing still returns the first post failure,
  blocked launch exit codes are preserved, wrapper tests pass, and canonical
  AgriGuard smoke passes.

## Baseline Evidence

After default artifact-index regeneration, compact status and the index file
were correct:

- `status.artifact_index_recovery_summary.required=false`
- `artifact_index.recovery_summary.required=false`
- `artifact_index.status=pass`

But `var\agriguard-guarded-launch-handoff.consumer.json` still reported the
old packet recovery summary:

- `packet_artifact_index_recovery_summary.required=true`
- recovery note: `Recovery command is present because this artifact index did
  not meet pass criteria.`

## Variant Evidence

- `run_guarded_launch.py` now runs post-launch handoff rendering, handoff
  consumption, and artifact indexing a second time only when the first
  post-processing pass succeeded.
- The first pass creates the artifact index needed by status/handoff views.
- The second pass re-renders handoff and consumer artifacts against that current
  index, then rewrites the final artifact index over the final handoff and
  consumer hashes.
- Existing failure branches remain single-pass because `post_launch_returncode`
  prevents the second pass after a failed handoff, consumer, or index command.
- The wrapper still returns the original launch failure when launch is blocked
  but all post-processing evidence is generated successfully.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `17 passed in 0.78s`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --emit-handoff --status-json-out var\agriguard-guarded-launch-status-after-two-pass-index-refresh.json
```

Result: process exited `1` because launch remains `env_shape_blocked`, which is
expected without production env values. Post-processing evidence was aligned:

- `var\agriguard-guarded-launch-status-after-two-pass-index-refresh.json`:
  `artifact_index.status=pass`,
  `artifact_index_recovery_summary.required=false`, and
  `artifact_index_recovery_summary.status=not_required`.
- `var\agriguard-guarded-launch-handoff.consumer.json`:
  `packet_validation_status=pass` and
  `packet_artifact_index_recovery_summary.required=false`.
- `var\agriguard-guarded-launch-artifact-index.json`:
  `status=pass`, `missing_required_roles=[]`, and
  `recovery_summary.status=not_required`.

## Decision

Adopt the two-pass handoff/index post-processing. It removes stale recovery
instructions from the operator handoff packet while keeping the real launch
blocker explicit and fail-closed.

## Next Cycle

Run canonical smoke, commit and push this scoped patch, then continue with the
next launch-readiness gap.
