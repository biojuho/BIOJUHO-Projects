# AutoResearch External Credential Handoff

## Decision

Adopted a redacted credential handoff package generated from the external
credential boundary registry. This keeps operator-owned secrets outside the
repository while making the remaining launch actions executable and auditable.

## Adopted Variant

- Added `ops/scripts/external_credential_handoff.py` to emit JSON, Markdown, and
  env-template handoff artifacts from
  `ops/references/external_credential_boundaries.json`.
- Added `verification_commands` to every credential boundary so the handoff
  lists the exact smoke or doctor command to run after credentials are supplied.
- Generated:
  - `docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json`
  - `docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md`
  - `docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example`

## Current Result

- Handoff status: `operator_action_required`
- Boundary count: `5`
- `missing_required_env=5`
- Secret values are not emitted; outputs contain env names, present/missing
  booleans, claim policies, blocked-until text, and verification commands only.
- The global launch objective remains credential-blocked:
  `global_objective_complete=false`.

## Verification

- `python ops\scripts\external_credential_handoff.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md --env-template-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example`
  - generated `5` boundaries with `status=operator_action_required`
  - reported `missing_required_env=5`
- `python ops\scripts\external_credential_boundary_audit.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.md`
  - valid `5` boundaries
  - reported `missing_required_env=5`
- `python -m pytest tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  - `19 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `97 passed`
- `python -m py_compile ops\scripts\external_credential_boundary_audit.py ops\scripts\external_credential_handoff.py ops\scripts\autoresearch_completion_audit.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md`
  - valid `23` criteria
  - `global_objective_complete=false`

## Remaining Blocker

This slice does not resolve the external credential boundaries. Canva OAuth,
Telegram delivery, live OTLP collector shipping, optional GitHub token capacity,
and hosted runtime credentials still require operator-owned credentials or
runtime choices before they can be claimed complete.
