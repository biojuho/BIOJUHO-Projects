# AutoResearch Loop: AgriGuard Operator Packet Compose Replacement Guard

- Date: 2026-07-07 KST
- Scope: AgriGuard launch operator packet guard visibility
- Owned code paths:
  - `apps/AgriGuard/scripts/render_launch_operator_packet.py`
  - `apps/AgriGuard/scripts/launch_compose.py`
  - `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_OPERATOR_PACKET_COMPOSE_REPLACEMENT_GUARD.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_OPERATOR_PACKET_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`

## Objective

The guarded-launch status and handoff now expose `compose_replacement_guard`, but the operator packet still required reading a separate launch report to understand the safe replacement policy. This cycle puts the same policy directly into the packet the operator uses to unblock launch.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: operator-facing recovery artifacts should include the fail-closed runtime policy alongside the commands they ask operators to run.

## A/B Hypothesis

- Baseline: the operator packet lists actions and rerun commands, but it does not explicitly say that the current runtime will not be replaced before env-shape and strict preflight gates.
- Variant: add top-level `compose_replacement_guard` to the operator packet, render the key fields in packet markdown, and summarize the field in launch reports when packet JSON includes it.
- Primary KPI: current operator packet JSON exposes `compose_replacement_requires_env_shape_validation=true`, `compose_replacement_requires_strict_preflight=true`, and `compose_runs_only_after_preflight_passes=true`.
- Guardrails: no command-order change, no raw secret exposure, and launch-compose plus packet tests remain green.

## Variant Evidence

Implemented:

- `render_launch_operator_packet.py` emits top-level `compose_replacement_guard`.
- The packet computes env-shape guard from its own safe rerun contract:
  - one env file: `compose_replacement_requires_env_shape_validation=true`
  - no or multiple env files: `compose_replacement_requires_env_shape_validation=false`
- Packet markdown renders:
  - `Compose replacement action before preflight`
  - `Compose replacement requires env-shape validation`
  - `Compose replacement requires strict preflight`
  - `Compose runs only after preflight passes`
- `launch_compose.py` includes the packet guard in `child_reports.operator_packet` when present.

Current operator-packet proof from the existing failed safe-replace preflight:

```powershell
python apps\AgriGuard\scripts\render_launch_operator_packet.py --app-root apps\AgriGuard --preflight-json var\agriguard-safe-replace-preflight.json --env-file var\agriguard-launch-operator.missing-firebase.env --json-out var\agriguard-compose-replacement-operator-packet.json --markdown-out var\agriguard-compose-replacement-operator-packet.md --env-template-out var\agriguard-compose-replacement-operator.env.template --compose-launch-report-json var\agriguard-safe-replace-launch-report.json --exit-zero-on-blocked
```

Result:

- `status=blocked`
- `blocker_class=operator_values_required`
- `compose_replacement_guard.current_runtime_action_before_preflight=none`
- `compose_replacement_guard.compose_replacement_requires_env_shape_validation=true`
- `compose_replacement_guard.compose_replacement_requires_strict_preflight=true`
- `compose_replacement_guard.compose_runs_only_after_preflight_passes=true`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\render_launch_operator_packet.py apps\AgriGuard\scripts\launch_compose.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_launch_compose_script.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_launch_compose_script.py -q`
  - Result: 35 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 107 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-operator-packet-compose-replacement-guard.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-operator-packet-compose-replacement-guard.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_OPERATOR_PACKET_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The operator packet now carries the same fail-closed compose replacement policy as the launch report and guarded-launch status surfaces.

## Remaining Blockers

- The running default Docker backend on `8002` remains stale.
- Current compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
