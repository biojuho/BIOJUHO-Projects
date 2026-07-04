# AutoResearch Loop: AgriGuard Consumer Command Metadata

Date: 2026-07-05

## Objective

Preserve the guarded-launch `command_text` contract after handoff generation, so consumer and artifact-index outputs do not drop the PowerShell-ready commands needed by operators and downstream tooling.

## Source Evidence

- Veritas AutoResearch source checked with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- Latest observed `main` commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local radar evidence remains `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md` with 8 adopted source-backed patterns.

## A/B Contract

Baseline: the handoff JSON emitted `command_shell` and `command_text`, but `consume_guarded_launch_handoff.py` flattened the handoff without ready-gate, operator-command, or validation command metadata. The artifact index could pass with stale consumer JSON that lacked those fields.

Variant: copy compact command metadata into the consumer view, propagate it into the artifact index and Markdown, and fail the index when command metadata is stale or missing.

Primary KPI: generated artifact index reports `consumer_command_metadata_status: pass` and exposes ready-gate, operator-command, and handoff-validation command text.

Decision rule: adopt only if stale consumer metadata fails closed, generated wrapper artifacts pass the new index gate, and launch/browser/workspace guardrails stay green.

Decision: adopted.

## Owned Paths

- `apps/AgriGuard/scripts/consume_guarded_launch_handoff.py`
- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_CONSUMER_COMMAND_METADATA.md`

## Variant Evidence

- Consumer view now includes `ready_gate_command_shell`, `ready_gate_command_text`, `operator_commands`, `operator_command_count`, `operator_command_text_count`, `handoff_validation_command_shell`, and `handoff_validation_command_text`.
- Artifact index now propagates those fields, renders them in Markdown, and adds `consumer_command_metadata_status`.
- Artifact index pass criteria now require complete consumer command metadata.
- Tests cover positive preservation and stale consumer metadata failure.

Real guarded wrapper:

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-consumer-command-metadata --emit-handoff --status-json-out var\agriguard-consumer-command-metadata-status.json
```

Result: exited `1` as expected because strict launch remains blocked by the missing real Firebase Admin service-account JSON. The generated artifact index passed.

JSON proof:

```json
{"wrapperStatus":"blocked","statusBlockerClass":"preflight_blocked","consumerStatus":"fail","consumerCommandMetadataStatus":"pass","readyGateShell":"powershell","readyGateHasText":true,"operatorCommandCount":2,"operatorCommandTextCount":2,"validationShell":"powershell","validationHasText":true,"indexStatus":"pass","indexRecoveryStatus":"not_required"}
```

Markdown proof from `var\agriguard-consumer-command-metadata-artifact-index.md` includes:

- `Consumer command metadata: pass`
- `Consumer ready gate command shell: powershell`
- `Consumer operator command text count: 2`
- `Consumer handoff validation command shell: powershell`
- `Consumer Operator Commands`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/consume_guarded_launch_handoff.py apps/AgriGuard/scripts/index_guarded_launch_artifacts.py` passed.
- `python -m ruff check apps/AgriGuard/scripts/consume_guarded_launch_handoff.py apps/AgriGuard/scripts/index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py` passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q` passed: 18 tests.
- Expanded launch-readiness suite passed: 85 tests.
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-agriguard-consumer-command-metadata.json` passed: 9/9.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-consumer-command-metadata.json --output-dir var\agriguard-browser-smoke-consumer-command-metadata --timeout-ms 120000` passed: 6/6 steps, 135/135 checks, 18/18 screenshots.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-consumer-command-metadata.json` passed: 5/5, including 616 AgriGuard backend tests and 26 contract tests.

## External Blocker

Local command-metadata preservation, artifact indexing, and app smoke are green. The real strict launch remains blocked until an operator supplies the outside-repo Firebase Admin service-account JSON referenced by the active launch env.

## Next Cycle

Audit whether the launch packet and status-only views should surface the artifact index's new `consumer_command_metadata_status` as a compact operator-facing health field.
