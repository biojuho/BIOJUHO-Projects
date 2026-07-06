# AutoResearch Loop - AgriGuard Self Ready Gate - 2026-07-06

## Objective

Make a copied AgriGuard `require_ready` command produce a truthful ready-gate JSON artifact on the first run when `--status-json-out` points to the same path as `artifacts.ready_gate_json`.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-06_AGRIGUARD_SELF_READY_GATE.md`
- `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_SELF_READY_GATE_2026-07-06.md`

## External Sources Checked

- AutoResearch reference repository: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- `git ls-remote` observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_SELF_READY_GATE_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## A/B Hypothesis and Decision Rule

- Baseline: status-only ready-gate output reads `ready_gate_json` before writing `--status-json-out`; a first run can describe its own output file as missing.
- Variant: before writing status JSON, detect when `--status-json-out` equals `artifacts.ready_gate_json` and mark the ready-gate artifact as the current status output.
- Primary KPI: first-run persisted ready-gate JSON reports `ready_gate.found=true`, `ready_gate.exists=true`, and current `status` / `blocker_class`.
- Guardrail: do not publish a misleading self-hash; `ready_gate.sha256` stays `null` with `sha256_status=self_referential_unavailable`.
- Decision: adopt. The variant fixes the first-run artifact truthfulness and all targeted/canonical checks passed.

## Changes

- Adds a status-output finalizer in `run_guarded_launch.py`.
- Applies that finalizer to all guarded-launch status JSON write points.
- Adds a regression for the first-run self-ready-gate case where the ready-gate file does not exist before the command runs.

## Verification

- Focused tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py::test_guarded_launch_status_only_self_ready_gate_output_is_current apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py::test_guarded_launch_status_only_prefers_live_ready_gate_file_state apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py::test_guarded_launch_status_only_ready_gate_arg_overrides_index_path`
  - Result: `3 passed`
- Full guarded-launch script tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Result: `31 passed`
- Canonical AgriGuard smoke:
  - `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-self-ready-gate.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

Generated a fresh guarded-launch handoff prefix:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --env-file var\agriguard-launch-operator.missing-firebase.env --output-prefix agriguard-guarded-launch-self-ready-gate --emit-handoff --status-json-out var\agriguard-guarded-launch-self-ready-gate-status-2026-07-06.json --handoff-json-out var\agriguard-guarded-launch-self-ready-gate-handoff-2026-07-06.json --handoff-markdown-out var\agriguard-guarded-launch-self-ready-gate-handoff-2026-07-06.md --handoff-validation-json-out var\agriguard-guarded-launch-self-ready-gate-handoff-validation-2026-07-06.json --handoff-consumer-json-out var\agriguard-guarded-launch-self-ready-gate-handoff-consumer-2026-07-06.json --handoff-ready-gate-json-out var\agriguard-guarded-launch-self-ready-gate-ready-gate-2026-07-06.json
```

- Result: exit `1`, expected because strict preflight still fails closed.
- Fresh artifact index before ready gate: `ready_gate_exists=false`, `consumer_command_metadata_status=pass`.
- Preflight blocker: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Ran the ready-gate command once:

```powershell
python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --output-dir var --output-prefix agriguard-guarded-launch-self-ready-gate --status-only --env-file var\agriguard-launch-operator.missing-firebase.env --require-ready --status-json-out var\agriguard-guarded-launch-self-ready-gate-ready-gate-2026-07-06.json
```

- Result: exit `1`, expected because `--require-ready` fails closed.
- Persisted ready-gate JSON: `status=blocked`, `blocker_class=preflight_blocked`.
- `ready_gate.found=true`, `ready_gate.exists=true`, `ready_gate.status=blocked`, `ready_gate.blocker_class=preflight_blocked`.
- `ready_gate.sha256=null`, `ready_gate.sha256_status=self_referential_unavailable`.
- `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch State

The copied ready-gate command is now first-run truthful for its own output artifact. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.

## Next Cycle

Continue launch hardening around operator handoff freshness and browser evidence once the Firebase credential is available, or keep improving fail-closed diagnostics that can be verified without external credentials.
