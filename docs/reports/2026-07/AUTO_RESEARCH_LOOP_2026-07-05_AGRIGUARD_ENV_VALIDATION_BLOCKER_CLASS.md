# Auto Research Loop - AgriGuard Env Validation Blocker Class

Date: 2026-07-05

## Objective

Close the next launch-readiness metadata gap in the env-template validation
artifact: the env validation JSON had `status` and `ready_for_preflight`, but
no first-class `blocker_class` for consumers that read the shape-validation
artifact directly.

## Source Baseline

- Veritas autoresearch source refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- HEAD/main resolved to `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Change

- Added `blocker_class` to env-template validation reports.
- Classified passing env-shape reports as `ready` and failing env-shape reports
  as `env_shape_blocked`.
- Propagated the env-validation blocker class through launch-compose child
  reports, readiness summaries, operator packets, guarded status JSON,
  handoff consumers, artifact indexes, and guarded Markdown summaries.
- Kept the existing fail-closed launch behavior unchanged: the sample operator
  env still passes shape validation but blocks at strict preflight without a
  real outside-repo Firebase Admin service-account JSON.

## Evidence

Focused metadata and handoff suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `92 passed`.

Launch contract suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `165 passed`.

Real guarded wrapper evidence:

```powershell
$prefix = 'agriguard-env-validation-blocker-class'
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix $prefix --emit-handoff --status-json-out "var\$prefix-status.json" *> "var\$prefix-wrapper.log"
```

Result: exit code `1`, expected fail-closed state due to the missing Firebase
Admin service-account file.

Regenerated artifact proof:

```json
{
  "envValidationStatus": "pass",
  "envValidationBlockerClass": "ready",
  "launchEnvValidationBlockerClass": "ready",
  "readinessEnvValidationBlockerClass": "ready",
  "statusReadinessEnvValidationBlockerClass": "ready",
  "packetEnvValidationBlockerClass": "ready",
  "statusOperatorPacketEnvValidationBlockerClass": "ready",
  "launchBlockerClass": "preflight_blocked",
  "statusBlockerClass": "preflight_blocked"
}
```

Handoff validation:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-env-validation-blocker-class-handoff.json --json-out var\agriguard-env-validation-blocker-class-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

Workspace gates:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-env-validation-blocker-class.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-env-validation-blocker-class.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-env-validation-blocker-class.json --output-dir var\agriguard-browser-smoke-suite-env-validation-blocker-class --timeout-ms 30000
```

Results:

- Workspace smoke: `9/9` passed; elapsed `2m54s`.
- AgriGuard smoke: `5/5` passed; backend tests took `5m20s`.
- Browser smoke: `6/6` flows, `135/135` checks, `18/18` screenshot artifacts passed.

## Remaining External Blocker

Strict launch remains externally blocked until the operator supplies a real
outside-repo Firebase Admin service-account JSON for
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and the remaining production operator
values.
