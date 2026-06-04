# AutoResearch Hosted Agent Approval Boundary

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Source signal: `microsoft/agent-framework` commit digest surfaced
  `Python: Fix toolbox consent flow in hosted agent (#6249)`.

## A/B Contract

- Baseline: `hosted_agent_runtime_credentials` had no missing required env by
  default, so the redacted checklist and live verifier could classify it as
  executable without a concrete hosted runtime consent decision.
- Variant: require a non-secret operator approval marker,
  `HOSTED_AGENT_RUNTIME_APPROVED`, before hosted-agent runtime checks become
  ready for execution.
- Primary KPI: default credential planning must show no executable hosted-agent
  runtime boundary until the operator confirms hosted runtime consent and
  approval policy.
- Guardrails: no secret values emitted, existing credential blockers stay
  redacted, and ready-only execution must not run hosted-agent commands by
  default.
- Decision rule: adopt the variant only if dry-run planning reports `ready=0`
  and `blocked=5`, ready-only execution selects `0` boundaries, dashboard text
  renders `0 ready / 5 blocked`, and the contract audit remains open with
  `global_objective_complete=false`.

## Result

- Adopted variant: yes.
- Operator approval marker: `HOSTED_AGENT_RUNTIME_APPROVED`.
- Hosted runtime status: `blocked_operator_approval`.
- Operator checklist summary: `ready_to_execute=0`, `blocked=5`.
- Live verifier dry-run: `selected=5`, `ready=0`, `blocked=5`,
  `executed=0`.
- Ready-only execute: `selected=0`, `ready=0`, `blocked=0`, `executed=0`.
- Dashboard browser smoke pass: `1/1` route with `15/15` expected text checks,
  including `0 ready / 5 blocked`.

## Post-Push Freshness

- Pushed proof commit: `8d5e263`.
- `current_tip_freshness_gate`: `origin/feat/observability-gateway-2026-05`
  now uses proof commit `8d5e263`.
- `protected_path_freshness`: dashboard protected-path changes are covered by
  the hosted approval browser smoke proof at `8d5e263`.
- Freshness result after this evidence-only follow-up: no changed protected paths after proof.

## Changed Paths

- `ops/references/external_credential_boundaries.json`
- `ops/scripts/external_credential_boundary_audit.py`
- `ops/scripts/external_credential_handoff.py`
- `ops/scripts/external_credential_live_verify.py`
- `tests/test_external_credential_boundary_audit.py`
- `tests/test_external_credential_handoff.py`
- `tests/test_external_credential_live_verify.py`
- `tests/test_dashboard_api.py`
- `tests/test_dev_server_browser_smoke.py`
- `apps/dashboard/src/App.test.jsx`
- `ops/references/dev_server_browser_checks.json`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.*`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.*`
- `docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.*`
- `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_HOSTED_AGENT_APPROVAL_2026-06-05.*`

## Verification

- `python -m py_compile ops/scripts/external_credential_boundary_audit.py ops/scripts/external_credential_handoff.py ops/scripts/external_credential_live_verify.py`
  - Passed.
- `python ops/scripts/external_credential_boundary_audit.py --json-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.json --markdown-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.md`
  - Passed: `5` boundaries, `missing_required_env=5`.
- `python ops/scripts/external_credential_handoff.py --json-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --markdown-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md --env-template-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example --operator-checklist-json-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.json --operator-checklist-markdown-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.md`
  - Passed: `5` boundaries, `status=operator_action_required`,
    `missing_required_env=5`.
- `python ops/scripts/external_credential_live_verify.py --json-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json --markdown-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md`
  - Passed: `mode=dry_run`, `selected=5`, `ready=0`, `blocked=5`,
    `next=canva_oauth_and_openapi_tool_execution`, `executed=0`.
- `python ops/scripts/external_credential_live_verify.py --ready-only --execute --timeout-seconds 180 --json-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.json --markdown-out docs/reports/2026-06/EXTERNAL_CREDENTIAL_LIVE_VERIFY_READY_ONLY_EXECUTE_2026-06-05.md`
  - Passed: `mode=execute`, `selected=0`, `ready=0`, `blocked=0`,
    `executed=0`.
- `npm.cmd --prefix apps/dashboard test -- --run`
  - Passed: `9`.
- `python ops/scripts/dev_server_browser_smoke.py --target dashboard-frontend --json-out docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_HOSTED_AGENT_APPROVAL_2026-06-05.json --markdown-out docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_HOSTED_AGENT_APPROVAL_2026-06-05.md`
  - Passed: `1/1` routes, `0` failed.

## Next Cycle

- Continue using source commit digests as adoption inputs, but keep hosted-agent
  runtime execution blocked until the operator selects a concrete hosted
  runtime, tracing backend, approval UI, credential owner, and explicitly sets
  `HOSTED_AGENT_RUNTIME_APPROVED=true`.
