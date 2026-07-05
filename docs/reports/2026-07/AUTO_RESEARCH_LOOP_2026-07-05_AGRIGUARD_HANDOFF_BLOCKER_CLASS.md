# Auto Research Loop - AgriGuard Handoff Blocker Class

Date: 2026-07-05

## Objective

Close the next launch-readiness contract gap found after the ready-gate status
metadata pass: the guarded-launch handoff JSON exposed `status: blocked` but
did not expose a top-level `blocker_class`, forcing simple consumers to inspect
nested status details to classify the external launch blocker.

## Source Baseline

- Veritas autoresearch source refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- HEAD/main resolved to `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Change

- Added `blocker_class` to the guarded-launch handoff JSON root.
- Derived the handoff root class from the compact status view, using `ready`
  only when the ready gate passes.
- Added schema coverage so handoffs missing root `blocker_class` fail validation.
- Added consumer semantic drift detection for root `blocker_class` versus
  `status_view.blocker_class`.
- Updated handoff markdown to print the handoff root blocker class.

## Evidence

Static and focused checks:

```powershell
python -m py_compile apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/scripts/consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py
python -m json.tool apps/AgriGuard/scripts/guarded_launch_handoff.schema.json > $null
python -m ruff check apps/AgriGuard/scripts/render_guarded_launch_handoff.py apps/AgriGuard/scripts/consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py
python -m pytest apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py -q
```

Results:

- Ruff passed.
- Handoff focused suite passed: `17 passed`.

Launch contract suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `164 passed`.

Real guarded wrapper evidence:

```powershell
$prefix='agriguard-handoff-blocker-class'
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix $prefix --emit-handoff --status-json-out "var\$prefix-status.json" *> "var\$prefix-wrapper.log"
```

Result: exit code `1`, expected fail-closed state due to the missing Firebase
Admin service-account file.

Regenerated artifact proof:

```json
{
  "handoffStatus": "blocked",
  "handoffBlockerClass": "preflight_blocked",
  "statusBlockerClass": "preflight_blocked",
  "externalBlockerClass": "preflight_blocked",
  "consumerBlockerClass": "preflight_blocked",
  "consumerHandoffBlockerClass": "preflight_blocked",
  "consumerErrors": [],
  "statusJsonBlockerClass": "preflight_blocked",
  "readyGateFound": false,
  "readyGateCommandShell": "powershell",
  "artifactIndexStatus": "pass"
}
```

Handoff validation:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-handoff-blocker-class-handoff.json --json-out var\agriguard-handoff-blocker-class-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

Workspace gates:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-handoff-blocker-class.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-handoff-blocker-class.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-handoff-blocker-class.json --output-dir var\agriguard-browser-smoke-suite-handoff-blocker-class --timeout-ms 30000
```

Results:

- Workspace smoke: `9/9` passed.
- AgriGuard smoke: `5/5` passed.
- Browser smoke: `6/6` flows, `135/135` checks, `18/18` screenshot artifacts passed.

Note: workspace and AgriGuard smoke were first attempted in parallel with a
3-minute timeout and both timed out at the harness level. They passed when
rerun separately with a longer timeout.

## Remaining External Blocker

Strict launch remains externally blocked until the operator supplies a real
outside-repo Firebase Admin service-account JSON for
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and the remaining production operator
values.
