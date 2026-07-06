# AutoResearch Loop: AgriGuard Status Operator Packet Compose Replacement Guard

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch status and handoff schema packet guard propagation
- Owned code paths:
  - `apps/AgriGuard/scripts/run_guarded_launch.py`
  - `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
  - `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - `apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_STATUS_OPERATOR_PACKET_COMPOSE_REPLACEMENT_GUARD.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_STATUS_OPERATOR_PACKET_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`

## Objective

The operator packet now emits `compose_replacement_guard`, but guarded-launch status views did not mirror the packet-level field. This cycle exposes the packet guard under `status_view.operator_packet` and extends the closed handoff schema accordingly.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: status/handoff views should preserve both producer-level and operator-packet-level safety contracts.

## A/B Hypothesis

- Baseline: packet JSON has `compose_replacement_guard`, but `run_guarded_launch.py --status-only` drops it from `operator_packet`.
- Variant: copy the packet guard into `status_view.operator_packet.compose_replacement_guard` and allow that closed object in the handoff schema.
- Primary KPI: current `agriguard-safe-replace` status view exposes the same packet guard under `operator_packet.compose_replacement_guard`.
- Guardrails: handoff validation stays strict, raw secret values remain redacted, and launch/status/handoff tests plus smoke stay green.

## Variant Evidence

Implemented:

- `run_guarded_launch._build_status_view` now copies `packet.compose_replacement_guard`.
- `guarded_launch_handoff.schema.json` now permits a closed `status_view.operator_packet.compose_replacement_guard` object.
- Status and handoff tests pin JSON propagation and schema validity.

Current status proof:

```powershell
python apps\AgriGuard\scripts\render_launch_operator_packet.py --app-root apps\AgriGuard --preflight-json var\agriguard-safe-replace-preflight.json --env-file var\agriguard-launch-operator.missing-firebase.env --json-out var\agriguard-safe-replace-operator-packet.json --markdown-out var\agriguard-safe-replace-operator-packet.md --env-template-out var\agriguard-safe-replace-operator.env.template --compose-launch-report-json var\agriguard-safe-replace-launch-report.json --exit-zero-on-blocked
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-safe-replace --status-only --status-json-out var\agriguard-status-operator-packet-compose-replacement-guard.json
```

Result:

- top-level `status=blocked`
- `blocker_class=preflight_blocked`
- `operator_packet.status=blocked`
- `operator_packet.blocker_class=operator_values_required`
- `operator_packet.compose_replacement_guard.current_runtime_action_before_preflight=none`
- `operator_packet.compose_replacement_guard.compose_replacement_requires_env_shape_validation=true`
- `operator_packet.compose_replacement_guard.compose_replacement_requires_strict_preflight=true`
- `operator_packet.compose_replacement_guard.compose_runs_only_after_preflight_passes=true`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\run_guarded_launch.py apps\AgriGuard\scripts\guarded_launch_handoff.schema.json apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py -q`
  - Result: 42 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 107 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-operator-packet-compose-replacement-guard.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-status-operator-packet-compose-replacement-guard.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_STATUS_OPERATOR_PACKET_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. Guarded-launch status and handoff schema now preserve the operator packet's compose replacement safety contract.

## Remaining Blockers

- The running default Docker backend on `8002` remains stale.
- Current compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
