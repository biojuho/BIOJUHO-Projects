# External Credential Consent Items Guard

- Date: 2026-06-05
- Source: `microsoft/agent-framework`
- Source commit: `dbc312a78a7579170068910599bfff5ca639c0d6`
- Source link: https://github.com/microsoft/agent-framework/commit/dbc312a78a7579170068910599bfff5ca639c0d6
- Source signal: `Python: Fix toolbox consent flow in hosted agent (#6249)`
- Adopted local guard: per-boundary `operator_consent_items`
- global_objective_complete=false

## A/B Contract

Baseline: the external credential registry and live verifier exposed hosted runtime approval through one boundary-level marker, `HOSTED_AGENT_RUNTIME_APPROVED`. That kept ready-only execution blocked, but it could hide separate hosted toolbox and tracing/runtime consent targets inside the same boundary.

Variant: the hosted-agent boundary now carries explicit redacted consent items:

- `hosted_agent_toolbox_mcp`
- `hosted_agent_tracing_runtime`

The boundary audit validates each consent item, the handoff and operator checklist render them, and the live verifier preserves them in JSON and Markdown. Secret values are still not emitted.

Adoption decision: adopted. The variant makes the operator-facing consent surface more precise without changing the external credential blocker or claiming hosted runtime readiness.

## Evidence

- Registry: `ops/references/external_credential_boundaries.json`
- Boundary audit: `ops/scripts/external_credential_boundary_audit.py`
- Handoff/checklist: `ops/scripts/external_credential_handoff.py`
- Live verifier: `ops/scripts/external_credential_live_verify.py`
- Checked-in artifacts:
  - `docs/reports/2026-06/EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.md`
  - `docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md`
  - `docs/reports/2026-06/EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.md`
  - `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md`

## Verification

- `python -m py_compile ops\scripts\external_credential_boundary_audit.py ops\scripts\external_credential_handoff.py ops\scripts\external_credential_live_verify.py`
- `python -m pytest tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py -q --tb=line` -> `27 passed`

Remaining blocker: the hosted runtime remains operator-owned and blocked until the runtime, tracing backend, toolbox consent policy, and `HOSTED_AGENT_RUNTIME_APPROVED=true` marker are supplied by the operator.
