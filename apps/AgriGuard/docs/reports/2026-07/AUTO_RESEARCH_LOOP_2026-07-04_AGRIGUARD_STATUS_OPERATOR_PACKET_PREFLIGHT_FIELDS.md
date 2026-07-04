# AutoResearch Loop - AgriGuard Status Operator Packet Preflight Fields

## Objective

Reduce operator ambiguity in the compact guarded-launch status view. The
redacted operator packet already contained the blocking action count, preflight
status, and safe preflight errors, but `run_guarded_launch.py --status-only`
only showed the action ID.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: compact status requires opening the operator packet to see the
  concrete Firebase preflight error.
- Variant: copy safe packet fields into `status_view.operator_packet`:
  `blocking_action_count`, `preflight_status`, and `preflight_errors`.
- Primary KPI: live `--status-only` output shows the exact remaining blocker
  `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.` while keeping
  `secrets_redacted=true`.
- Guardrails: handoff schema validation, focused wrapper/handoff/index tests,
  and canonical AgriGuard smoke must pass.

## Change

`_build_status_view()` now emits the redacted packet's blocking action count,
preflight status, and preflight errors. The guarded-launch handoff schema was
extended so embedded status views validate with those fields.

## Verification Commands

```powershell
python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py
```

Result: passed.

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q
```

Result: `39 passed in 2.23s`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-status-operator-packet-preflight-fields-20260704.json
```

Result: compact status stayed `blocked` with `blocker_class=preflight_blocked`
and now includes:

- `operator_packet.blocking_action_count=1`
- `operator_packet.preflight_status=fail`
- `operator_packet.preflight_errors=["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."]`
- `operator_packet.secrets_redacted=true`

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --output-prefix agriguard-guarded-launch-operator-packet-preflight-fields-20260704 --emit-handoff --status-json-out var\agriguard-guarded-launch-operator-packet-preflight-fields-20260704-status.json
```

Result: expected exit code `1` with the template env file still
`env_shape_blocked`; handoff validation passed with the expanded
`status_view.operator_packet` schema and `packet_validation_status=pass`.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-operator-packet-preflight-fields-20260704.json
```

Result: `passed=5`, `failed=0`, `total=5`, elapsed `5m41s`.

## Decision

Adopt the variant. Compact status now shows the safe operator-packet preflight
reason directly, without weakening redaction or changing the launch gate.

## Remaining Blocker

The current default guarded-launch prefix remains `preflight_blocked` because
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` points to a file that does not exist.
The next real launch step requires a host-local Firebase Admin service-account
JSON path outside the repository.

## Next Cycle

Continue improving operator recovery around the Firebase service-account path,
or switch to another product surface with live-click failure evidence.
