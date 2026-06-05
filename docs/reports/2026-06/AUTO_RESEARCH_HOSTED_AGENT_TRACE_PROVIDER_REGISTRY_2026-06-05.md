# AutoResearch Hosted Agent Trace Provider Registry - 2026-06-05

## Source Signal

- Source: `openai/openai-agents-python`
- Commit: `f4e5d96f9fda158f9541b575d2aa5232107cb939`
- Subject: `docs: add Latitude to external tracing processors list (#3577)`
- Documentation: OpenAI Agents SDK tracing lists ecosystem integrations under the external tracing processors list and includes Latitude.

## A/B Contract

- Baseline: `hosted_agent_runtime_credentials` had a single tracing consent item and three optional env names, but no explicit operator-facing trace processor provider registry.
- Variant: add `trace_processor_providers` to the hosted-agent boundary, include `Latitude` with `LATITUDE_API_KEY`, validate provider metadata, and render provider choices in the boundary audit, handoff, operator checklist, and live verifier.
- Primary KPI: external tracing backend choice is explicit in redacted operator artifacts before any hosted runtime can be claimed complete.
- Guardrails: do not execute provider calls, do not emit secret values, keep the hosted runtime blocked behind `HOSTED_AGENT_RUNTIME_APPROVED`, and preserve the `ready=0 / blocked=5` live-verifier posture without operator credentials.
- Decision rule: adopt only if the credential tooling validates provider metadata, regenerated artifacts show `Latitude` and `LATITUDE_API_KEY`, and existing external credential drift checks pass.

## Changed Paths

- `ops/references/external_credential_boundaries.json`
- `ops/scripts/external_credential_boundary_audit.py`
- `ops/scripts/external_credential_handoff.py`
- `ops/scripts/external_credential_live_verify.py`
- `tests/test_external_credential_boundary_audit.py`
- `tests/test_external_credential_handoff.py`
- `tests/test_external_credential_live_verify.py`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.*`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.*`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.*`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.*`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.*`

## Verification

- `python -m py_compile ops\scripts\external_credential_boundary_audit.py ops\scripts\external_credential_handoff.py ops\scripts\external_credential_live_verify.py` -> passed
- `python -m pytest tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py -q -p no:cacheprovider` -> `28 passed`
- `python ops\scripts\external_credential_boundary_audit.py --registry ops\references\external_credential_boundaries.json --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.md` -> `5 boundaries`, `missing_required_env=5`
- `python ops\scripts\external_credential_handoff.py --registry ops\references\external_credential_boundaries.json --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md --env-template-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example --operator-checklist-json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.json --operator-checklist-markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.md` -> generated `5` redacted boundaries
- `python ops\scripts\external_credential_live_verify.py --registry ops\references\external_credential_boundaries.json --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md` -> `ready=0`, `blocked=5`
- `python ops\scripts\external_credential_live_verify.py --registry ops\references\external_credential_boundaries.json --ready-only --execute --timeout-seconds 180 --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.md` -> `selected=0`, `executed=0`
- `python ops\scripts\autoresearch_completion_audit.py --contract ops\references\autoresearch_completion_contract.json --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md` -> `78` criteria, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --requirements ops\references\autoresearch_objective_requirements.json --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md` -> `7` requirements, `global_objective_complete=false`
- `python -m pytest tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q -p no:cacheprovider` -> `47 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-trace-provider-registry-2026-06-05.json` -> `6/6 passed`

## Decision

Adopted. This improves the operator boundary by making trace backend selection inspectable and source-backed while preserving the blocked external-runtime status. No hosted tracing provider is claimed live without `HOSTED_AGENT_RUNTIME_APPROVED=true` and a real operator-owned provider credential.

`global_objective_complete=false`
