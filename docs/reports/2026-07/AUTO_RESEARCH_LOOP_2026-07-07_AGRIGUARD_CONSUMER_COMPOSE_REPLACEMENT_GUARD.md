# AutoResearch Loop: AgriGuard Consumer Compose Replacement Guard

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch handoff consumer view
- Owned code paths:
  - `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
  - `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_CONSUMER_COMPOSE_REPLACEMENT_GUARD.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONSUMER_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`

## Objective

The launch report, operator packet, guarded status view, and handoff schema now carry `compose_replacement_guard`. The final compact handoff consumer view still dropped that safety contract, so downstream automation had to inspect nested handoff JSON to confirm that compose replacement remains fail-closed.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: final consumer views should preserve the safety-critical status fields that automation needs for fail-closed launch decisions.

## A/B Hypothesis

- Baseline: `consume_guarded_launch_handoff.py` reports blocker state, validation state, action IDs, and packet validation, but not the compose replacement guard.
- Variant: add `launch_compose_replacement_guard` and `operator_packet_compose_replacement_guard` to the compact consumer view.
- Primary KPI: current consumer JSON exposes both guard dictionaries while still reporting `handoff_status=blocked` and `blocker_class=preflight_blocked`.
- Guardrails: schema validation still passes, consumer errors stay empty for the current blocked handoff, and launch/smoke gates stay green.

## Variant Evidence

Implemented:

- Added a safe dictionary copier in `consume_guarded_launch_handoff.py`.
- Exposed:
  - `launch_compose_replacement_guard`
  - `operator_packet_compose_replacement_guard`
- Updated consumer tests for ready and blocked handoff paths.

Current consumer proof:

```powershell
python apps\AgriGuard\scripts\render_guarded_launch_handoff.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-safe-replace --ready-gate-json var\agriguard-safe-replace-ready-gate.json --json-out var\agriguard-consumer-compose-replacement-guard-handoff.json --markdown-out var\agriguard-consumer-compose-replacement-guard-handoff.md --validation-json-out var\agriguard-consumer-compose-replacement-guard-handoff.validation.json --exit-zero-on-blocked
python apps\AgriGuard\scripts\consume_guarded_launch_handoff.py var\agriguard-consumer-compose-replacement-guard-handoff.json --validation-json var\agriguard-consumer-compose-replacement-guard-handoff.validation.json --json-out var\agriguard-consumer-compose-replacement-guard-consumer.json --exit-zero-on-blocked
```

Result:

- `status=fail`
- `handoff_status=blocked`
- `blocker_class=preflight_blocked`
- `errors=[]`
- `launch_compose_replacement_guard.current_runtime_action_before_preflight=none`
- `launch_compose_replacement_guard.compose_replacement_requires_strict_preflight=true`
- `launch_compose_replacement_guard.compose_runs_only_after_preflight_passes=true`
- `operator_packet_compose_replacement_guard.current_runtime_action_before_preflight=none`
- `operator_packet_compose_replacement_guard.compose_replacement_requires_env_shape_validation=true`
- `operator_packet_compose_replacement_guard.compose_replacement_requires_strict_preflight=true`
- `operator_packet_compose_replacement_guard.compose_runs_only_after_preflight_passes=true`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py -q`
  - Result: 9 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_validate_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 107 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-consumer-compose-replacement-guard.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-consumer-compose-replacement-guard.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONSUMER_COMPOSE_REPLACEMENT_GUARD_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The compact consumer view now preserves the fail-closed compose replacement policy needed by downstream launch automation.

## Remaining Blockers

- The running default Docker backend on `8002` remains stale.
- Current compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
