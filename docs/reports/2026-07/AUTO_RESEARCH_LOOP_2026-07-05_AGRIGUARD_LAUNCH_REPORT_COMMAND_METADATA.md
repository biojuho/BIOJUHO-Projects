# AutoResearch Loop: AgriGuard Launch Report Command Metadata

Date: 2026-07-05

## Objective

Expose guarded-launch consumer command-metadata health in the top-level launch report, so an operator can inspect `*-launch-report.json` first without losing the refreshed artifact-index status.

## Source Evidence

- Veritas AutoResearch source checked with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- Latest observed `main` commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local radar evidence remains `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md` with 8 adopted source-backed patterns.

## A/B Contract

Baseline: `launch_compose.py` summarized the operator packet before the artifact index existed. The guarded wrapper later refreshed the operator packet with `consumer_command_metadata_status: pass`, but `*-launch-report.json` remained stale with null command-metadata fields.

Variant: summarize guarded artifact-index health into `child_reports.operator_packet`, and have `run_guarded_launch.py` refresh those launch-report fields immediately after the post-index operator-packet refresh.

Primary KPI: the final launch report, refreshed operator packet, status view, and artifact index all agree on `consumer_command_metadata_status: pass` while the strict launch remains fail-closed on the real external Firebase credential blocker.

Decision rule: adopt only if focused contracts, expanded launch-readiness tests, the real guarded wrapper, browser smoke, workspace smoke, and AgriGuard smoke remain green.

Decision: adopted.

## Owned Paths

- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_LAUNCH_REPORT_COMMAND_METADATA.md`

## Variant Evidence

- `launch_compose.py` now mirrors compact artifact-index fields into `child_reports.operator_packet` when the operator packet already contains guarded-launch evidence.
- `run_guarded_launch.py` now refreshes the launch-report operator-packet fields after the post-index operator-packet refresh.
- Regression coverage reproduces the stale launch-report state and asserts the final launch report carries:
  - `artifact_index_status: pass`
  - `consumer_packet_validation_status: pass`
  - `consumer_command_metadata_status: pass`
  - `artifact_index_recovery_command_status: not_required`

Real guarded wrapper:

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-launch-report-command-metadata --emit-handoff --status-json-out var\agriguard-launch-report-command-metadata-status.json
```

Result: exited `1` as expected because strict launch remains blocked by the missing real Firebase Admin service-account JSON. The final launch report was refreshed after artifact indexing.

JSON proof:

```json
{"indexConsumerCommandMetadata":"pass","launchReportArtifactIndexStatus":"pass","launchReportConsumerCommandMetadata":"pass","launchReportConsumerPacketValidation":"pass","launchReportRecoveryCommand":"not_required","launchStage":"preflight","launchStatus":"fail","operatorPacketFound":true,"packetConsumerCommandMetadata":"pass","statusArtifactIndexCommandMetadata":"pass"}
```

The launch report still records the expected external blocker:

```json
{"errors":["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."]}
```

## Verification

- `python -m py_compile apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` passed.
- `python -m ruff check apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q` passed: 40 tests.
- Expanded launch-readiness suite passed: 163 tests.
- `python ops/scripts/run_workspace_smoke.py --scope workspace` passed on rerun with longer timeout: 9/9.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-launch-report-command-metadata-browser-smoke.json --output-dir var\agriguard-launch-report-command-metadata-browser-smoke --timeout-ms 120000` passed: 6/6 steps, 135/135 checks, 18/18 screenshots.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard` passed: 5/5.

## External Blocker

Local launch-report metadata propagation and all guardrails are green. Full strict launch remains blocked until an operator supplies a real outside-repo Firebase Admin service-account JSON for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue auditing downstream operator views for any remaining stale compact fields after post-index artifact refresh.
