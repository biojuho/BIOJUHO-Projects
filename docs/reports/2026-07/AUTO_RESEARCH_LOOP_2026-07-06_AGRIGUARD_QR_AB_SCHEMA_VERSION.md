# AutoResearch Loop - AgriGuard QR A/B Schema Version - 2026-07-06

## Objective

Add an explicit `schema_version=1` contract to the AgriGuard QR page A/B JSON summary so experiment evidence carries both schema and freshness metadata.

## Source-Backed Check

- AutoResearch reference repository checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- GitHub modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_AB_SCHEMA_VERSION_2026-07-06.md`
- Radar result: `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`

## Changes

- `apps/AgriGuard/scripts/ab_test_qr_page.py`
  - Adds top-level `schema_version=1` to `--json-out` payloads.
- `apps/AgriGuard/backend/tests/test_smoke.py`
  - Extends the QR A/B self-output reuse regression to assert the JSON summary schema version.

## Verification

- Focused QR A/B tests:
  - Result: `3 passed`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: `63 passed`
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-qr-ab-schema-version.json`
  - Result: `status=complete`, `passed=5`, `failed=0`, `total=5`

## Live Evidence

QR A/B sample run:

```powershell
python apps\AgriGuard\scripts\ab_test_qr_page.py --json-out var\agriguard-qr-page-ab-schema-version-2026-07-06.json --output var\agriguard-qr-page-ab-schema-version-2026-07-06.md
```

- Result: exit `0`
- JSON: `schema_version=1`, `generated_at=2026-07-06T14:31:41Z`, `dataset_size=20`, `decision.outcome=adopt_b`
- Markdown: generated with the same timestamp and the built-in sample decision summary.

## Current Launch State

QR A/B JSON evidence now has a stable schema marker and generation timestamp. Real compose/browser launch remains externally blocked until the operator provides a real Firebase Admin service-account `.json` at `C:\secure\missing-firebase-service-account.json`.
