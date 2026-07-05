# Auto Research Loop - AgriGuard Artifact Index Blocker Class

Date: 2026-07-05

## Objective

Close the next launch-readiness metadata gap in the guarded-launch artifact
index: the index JSON had a top-level `status` but no first-class
`blocker_class`, even though downstream status and handoff views depend on it
to classify evidence completeness.

## Source Baseline

- Veritas autoresearch source refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- HEAD/main resolved to `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Change

- Added `blocker_class` to guarded-launch artifact-index reports.
- Classified passing artifact indexes as `ready` and failing indexes as
  `artifact_index_blocked`.
- Propagated the artifact-index blocker class through guarded status JSON,
  operator-packet guarded evidence, launch-report operator-packet summaries,
  readiness summaries, handoff consumers, and guarded Markdown views.
- Kept artifact-index readiness separate from launch readiness: a complete
  artifact index can be `ready` while the launch remains `preflight_blocked`.

## Evidence

Focused artifact-index, packet, handoff, and wrapper suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py -q
```

Result: `87 passed`.

Launch contract suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `165 passed`.

Real guarded wrapper evidence:

```powershell
$prefix = 'agriguard-artifact-index-blocker-class'
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix $prefix --emit-handoff --status-json-out "var\$prefix-status.json" *> "var\$prefix-wrapper.log"
```

Result: exit code `1`, expected fail-closed state due to the missing Firebase
Admin service-account file.

Regenerated artifact proof:

```json
{
  "artifactIndexStatus": "pass",
  "artifactIndexBlockerClass": "ready",
  "statusArtifactIndexBlockerClass": "ready",
  "packetArtifactIndexBlockerClass": "ready",
  "launchOperatorPacketArtifactIndexBlockerClass": "ready",
  "readinessOperatorPacketArtifactIndexBlockerClass": "ready",
  "statusReadinessOperatorPacketArtifactIndexBlockerClass": "ready",
  "launchBlockerClass": "preflight_blocked",
  "statusBlockerClass": "preflight_blocked"
}
```

Handoff validation:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-artifact-index-blocker-class-handoff.json --json-out var\agriguard-artifact-index-blocker-class-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

Workspace gates:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-artifact-index-blocker-class.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-index-blocker-class.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-artifact-index-blocker-class.json --output-dir var\agriguard-browser-smoke-suite-artifact-index-blocker-class --timeout-ms 30000
```

Results:

- Workspace smoke: command exited `0`; `9/9` passed; elapsed `3m54s`.
- AgriGuard smoke: outer shell timed out after writing
  `var\workspace-smoke-agriguard-artifact-index-blocker-class.json`; that JSON
  is complete with `5/5` passed and `0` failed, elapsed `9m52s`.
- Browser smoke: command exited `0`; `6/6` flows, `135/135` checks, `18/18`
  screenshot artifacts passed.

## Remaining External Blocker

Strict launch remains externally blocked until the operator supplies a real
outside-repo Firebase Admin service-account JSON for
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and the remaining production operator
values.
