# AutoResearch: External Credential Boundary Registry

## Objective

Make the remaining credential-gated launch boundaries executable and
machine-readable without weakening the rule that real external credentials and
operator-owned runtime decisions are required before claiming completion.

## A/B Contract

- Baseline: external-auth and future-scoped boundaries were recorded across
  reports, but there was no single executable registry proving that those
  boundaries stayed visible.
- Variant: add `ops/references/external_credential_boundaries.json` plus
  `ops/scripts/external_credential_boundary_audit.py` to validate boundary
  IDs, claim policies, evidence paths, required env names, optional env choices,
  and secret-value redaction behavior.
- Primary KPI: the registry audit passes with `5 boundaries` and keeps
  `missing_required_env` explicit by env name only.
- Guardrail: keep `external_credential_boundaries` blocked and keep
  `global_objective_complete=false`; this slice is visibility and policy
  hardening, not credential fulfillment.

## Adopted Variant

Adopted.

- Registry: `ops/references/external_credential_boundaries.json`
- Validator: `ops/scripts/external_credential_boundary_audit.py`
- Tests: `tests/test_external_credential_boundary_audit.py`
- Generated JSON:
  `docs/reports/2026-06/EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.json`
- Generated Markdown:
  `docs/reports/2026-06/EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.md`

The registry currently tracks:

- Canva OAuth and OpenAPI tool execution
- OTLP collector endpoint and credentials
- Hosted agent runtime and tracing credentials
- GitHub source-refresh rate-limit token boundary
- Telegram notification MCP credentials

## Verification

- `python -m pytest tests\test_external_credential_boundary_audit.py -q`
  - `4 passed`
- `python ops\scripts\external_credential_boundary_audit.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_BOUNDARY_AUDIT_2026-06-05.md`
  - `5 boundaries`
  - `missing_required_env=5`
  - missing required env names include `CANVA_CLIENT_SECRET`
- Focused credential/completion audit tests:
  - `15 passed`
- Pre-push-equivalent pytest suite:
  - `93 passed`
- Runtime probes:
  - dev-server MCP runtime smoke passed
  - MCP service runtime smoke passed
  - single workflow dry-run passed
  - side-effect safety skip passed
  - all-workflow matrix dry-run passed
- Completion audit:
  - `22` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`

## Remaining Boundary

This does not satisfy external credentials. Canva login/consent, live OpenAPI
tool execution, OTLP endpoint credentials, hosted agent runtime credentials,
GitHub token-backed high-volume refreshes, and Telegram delivery checks remain
operator-owned until real credentials and approval policies are supplied.
