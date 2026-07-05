# Auto Research Loop - AgriGuard Launch Report Blocker Class

Date: 2026-07-05

## Objective

Close the next launch-readiness metadata gap in the aggregate launch report:
the report stopped at `preflight_failed` but did not expose a top-level
`blocker_class`, even though nested readiness artifacts already classified the
run as `preflight_blocked`.

## Source Baseline

- Veritas autoresearch source refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- HEAD/main resolved to `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Change

- Added launch-report `blocker_class` classification for pass, env-shape,
  preflight, compose, and browser-smoke terminal states.
- Preserved launch-report `blocker_class` in readiness summaries.
- Exposed launch-report `blocker_class` in the compact guarded-launch status
  view and embedded handoff status view.
- Updated the guarded-launch handoff schema to require the embedded
  `launch.blocker_class` field.
- Added exact launch-compose branch tests for ready and blocked terminal states.

## Evidence

Static and focused checks:

```powershell
python -m py_compile apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/summarize_launch_readiness.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py
python -m json.tool apps/AgriGuard/scripts/guarded_launch_handoff.schema.json > $null
python -m ruff check apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/summarize_launch_readiness.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py -q
```

Results:

- Ruff passed.
- Focused suite passed: `54 passed`.

Launch contract suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `165 passed`.

Real guarded wrapper evidence:

```powershell
$prefix='agriguard-launch-report-blocker-class'
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix $prefix --emit-handoff --status-json-out "var\$prefix-status.json" *> "var\$prefix-wrapper.log"
```

Result: exit code `1`, expected fail-closed state due to the missing Firebase
Admin service-account file.

Regenerated artifact proof:

```json
{
  "launchStatus": "fail",
  "launchStage": "preflight",
  "launchStopReason": "preflight_failed",
  "launchBlockerClass": "preflight_blocked",
  "summaryStatus": "blocked",
  "summaryBlockerClass": "preflight_blocked",
  "summaryLaunchBlockerClass": "preflight_blocked",
  "statusBlockerClass": "preflight_blocked",
  "statusLaunchBlockerClass": "preflight_blocked",
  "handoffBlockerClass": "preflight_blocked",
  "handoffLaunchBlockerClass": "preflight_blocked",
  "packetBlockerClass": "operator_values_required"
}
```

Handoff validation:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-launch-report-blocker-class-handoff.json --json-out var\agriguard-launch-report-blocker-class-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

Workspace gates:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-launch-report-blocker-class.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-report-blocker-class.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-launch-report-blocker-class.json --output-dir var\agriguard-browser-smoke-suite-launch-report-blocker-class --timeout-ms 30000
```

Results:

- Workspace smoke: `9/9` passed.
- AgriGuard smoke: `5/5` passed after rerun with a longer timeout; backend tests took `5m17s`.
- Browser smoke: `6/6` flows, `135/135` checks, `18/18` screenshot artifacts passed.

## Remaining External Blocker

Strict launch remains externally blocked until the operator supplies a real
outside-repo Firebase Admin service-account JSON for
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and the remaining production operator
values.
