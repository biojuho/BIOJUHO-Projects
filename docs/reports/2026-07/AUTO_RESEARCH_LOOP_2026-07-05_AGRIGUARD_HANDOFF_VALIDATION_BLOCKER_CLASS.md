# Auto Research Loop - AgriGuard Handoff Validation Blocker Class

Date: 2026-07-05

## Objective

Close the final generated guarded-launch metadata gap found by the artifact
scanner: the handoff validation report root had `status` but no
`blocker_class`.

## Source Baseline

- Veritas autoresearch source refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- HEAD/main resolved to `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Change

- Added `blocker_class` to handoff validation reports.
- Classified passing handoff validation as `ready`.
- Classified failing handoff validation as
  `guarded_launch_handoff_validation_blocked`.
- Mirrored the validation blocker class through the handoff consumer view and
  artifact index report.

## Evidence

Focused validation, consumer, and artifact-index suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q
```

Result: `23 passed`.

Launch contract suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `165 passed`.

Real guarded wrapper evidence:

```powershell
$prefix = 'agriguard-handoff-validation-blocker-class'
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix $prefix --emit-handoff --status-json-out "var\$prefix-status.json" *> "var\$prefix-wrapper.log"
```

Result: exit code `1`, expected fail-closed state due to the missing Firebase
Admin service-account file.

Regenerated artifact proof:

```json
{
  "consumerValidationBlockerClass": "ready",
  "indexBlockerClass": "ready",
  "indexStatus": "pass",
  "indexValidationBlockerClass": "ready",
  "validationBlockerClass": "ready",
  "validationStatus": "pass"
}
```

Final status-object scan:

```text
no missing blocker_class fields for status-bearing objects
```

Handoff validation:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-handoff-validation-blocker-class-handoff.json --json-out var\agriguard-handoff-validation-blocker-class-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

Workspace gates:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-handoff-validation-blocker-class.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-handoff-validation-blocker-class.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-handoff-validation-blocker-class.json --output-dir var\agriguard-browser-smoke-suite-handoff-validation-blocker-class --timeout-ms 30000
```

Results:

- Workspace smoke: `9/9` passed; elapsed `3m47s`.
- AgriGuard smoke: `5/5` passed; elapsed `5m59s`.
- Browser smoke: `6/6` flows, `135/135` checks, `18/18` screenshot artifacts passed.

## Remaining External Blocker

Strict launch remains externally blocked until the operator supplies a real
outside-repo Firebase Admin service-account JSON for
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and the remaining production operator
values.
