# AutoResearch Loop: Release Gate Provider Blocker Index

Date: 2026-07-04

## Objective

Make release-gate JSON reports index provider blocker and promotion blocking
reason context when post-apply or workflow artifacts are attached.

## Scope

Owned paths changed in this cycle:

- `scripts/release_gate.py`
- `backend/tests/test_release_gate.py`

This is report-only extraction. It does not change release gate pass/fail
decisions and does not broaden product-smoke launch handoff validation.

## External Source Check

- `Veritas-7/autoresearch-skill-system` observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern is durable artifact indexing: when a no-go artifact already
contains provider recovery context, the higher-level release report should make
that context searchable and reviewable.

## A/B Decision

Baseline:

- Generic artifact reports exposed JSON validity, `ok`, schema, checks,
  screenshots, traces, and launch handoff fields.
- Provider-specific no-go context added in recent cycles was present only inside
  the child artifact body.

Variant:

- Extract `provider_blockers` into report fields:
  blocker count, providers, commands, failure reasons, and safe remediations.
- Extract `promotion_blocking_reasons` or receipt `blocking_reasons` into report
  fields with unsafe secret-shaped reason counts.
- Roll those fields into `artifact_summary` across attached artifacts.

Decision rule:

- Adopt if release-gate report tests stay green and the provider/post-apply
  gate tests still pass unchanged.

Result: adopted.

## Verification

- `python -m py_compile scripts\release_gate.py`
  - Exit code `0`.
- `python -m pytest backend\tests\test_release_gate.py::test_release_gate_json_report_exposes_provider_blocker_artifact_context -q`
  - `1 passed`.
- `python -m pytest backend\tests\test_release_gate.py -q`
  - `116 passed`.
- `python -m pytest backend\tests\test_provider_preflight.py backend\tests\test_deploy_readiness.py backend\tests\test_external_release_gate.py backend\tests\test_external_gate_handoff.py backend\tests\test_post_apply_evidence_gate.py -q`
  - `133 passed`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-release-gate-provider-blocker-index-2026-07-04.json`
  - `8 passed, 0 failed`.

## Current Boundary

Launch remains no-go for external reasons. The release-gate report can now index
provider blocker evidence when such artifacts are attached, but Railway/Vercel
auth and real provider secrets still require external operator action.

## Next Cycle

The next local cycle should look for remaining high-value launch readiness gaps
outside the provider-remediation chain.
