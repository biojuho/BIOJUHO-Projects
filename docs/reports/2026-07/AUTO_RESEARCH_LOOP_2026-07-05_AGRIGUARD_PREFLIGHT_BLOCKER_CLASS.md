# Auto Research Loop - AgriGuard Preflight Blocker Class

Date: 2026-07-05

## Objective

Close the next launch-readiness metadata gap in the strict preflight report:
the preflight JSON was `status: fail` with concrete errors but had no
first-class `blocker_class` for consumers that read the preflight artifact
directly.

## Source Baseline

- Veritas autoresearch source refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- HEAD/main resolved to `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Change

- Added `blocker_class` to strict preflight JSON reports.
- Classified passing preflight reports as `ready` and failing reports as
  `preflight_blocked`.
- Refreshed `blocker_class` after Firebase service-account file checks and
  Docker readiness checks mutate preflight status.
- Propagated preflight `blocker_class` into launch-compose child preflight
  summaries.

## Evidence

Static and focused checks:

```powershell
python -m py_compile apps/AgriGuard/scripts/launch_env_preflight.py apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_launch_compose_script.py
python -m ruff check apps/AgriGuard/scripts/launch_env_preflight.py apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_launch_compose_script.py
python -m pytest apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_launch_compose_script.py -q
```

Results:

- Ruff passed.
- Focused suite passed: `84 passed`.

Launch contract suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `165 passed`.

Real guarded wrapper evidence:

```powershell
$prefix='agriguard-preflight-blocker-class'
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix $prefix --emit-handoff --status-json-out "var\$prefix-status.json" *> "var\$prefix-wrapper.log"
```

Result: exit code `1`, expected fail-closed state due to the missing Firebase
Admin service-account file.

Regenerated artifact proof:

```json
{
  "preflightStatus": "fail",
  "preflightBlockerClass": "preflight_blocked",
  "preflightErrorCount": 1,
  "launchBlockerClass": "preflight_blocked",
  "launchPreflightChildBlockerClass": "preflight_blocked",
  "packetBlockerClass": "operator_values_required",
  "statusBlockerClass": "preflight_blocked"
}
```

Handoff validation:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-preflight-blocker-class-handoff.json --json-out var\agriguard-preflight-blocker-class-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

Workspace gates:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-preflight-blocker-class.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-preflight-blocker-class.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-preflight-blocker-class.json --output-dir var\agriguard-browser-smoke-suite-preflight-blocker-class --timeout-ms 30000
```

Results:

- Workspace smoke: `9/9` passed.
- AgriGuard smoke: `5/5` passed; backend tests took `5m29s`.
- Browser smoke: `6/6` flows, `135/135` checks, `18/18` screenshot artifacts passed.

## Remaining External Blocker

Strict launch remains externally blocked until the operator supplies a real
outside-repo Firebase Admin service-account JSON for
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and the remaining production operator
values.
