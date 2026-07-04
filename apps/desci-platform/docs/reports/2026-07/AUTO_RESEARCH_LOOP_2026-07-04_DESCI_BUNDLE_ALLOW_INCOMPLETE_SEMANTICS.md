# AutoResearch Loop - DeSci Bundle Allow-Incomplete Semantics - 2026-07-04

## Objective

Make `--allow-incomplete-bundle` on the DeSci provider workflow artifact bundle verifier match its name: local/custom spot checks should not fail solely because the index already marked required artifacts as absent.

## Scope and Owned Paths

- `ops/scripts/verify_desci_provider_workflow_artifact_bundle.py`
- `tests/test_desci_provider_workflow_artifact_bundle_verifier.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_BUNDLE_ALLOW_INCOMPLETE_SEMANTICS.md`

## Source Evidence

- The custom verify-path spot check now indexes the chosen workflow JSON correctly, but the verifier still returned `ok=false` because eight other default bundle artifacts were intentionally absent.
- The CLI flag is named `--allow-incomplete-bundle`, so a caller using it should still see missing-required counts without those index-reported absences becoming verification failures.

## A/B Hypothesis

- Baseline A: keep `--allow-incomplete-bundle` limited to top-level index completeness checks.
  - Rejected because artifact entries already marked `exists=false` still failed as required missing artifacts, making the flag misleading for local spot checks.
- Variant B: when `require_complete_bundle=False`, do not add artifact-entry failures for required artifacts that the index itself reported as missing.
  - Adopted because changed artifacts, digest mismatches, and artifacts expected to exist still fail, while intentionally incomplete local bundles can verify their present evidence.

## Implementation

- `_verify_artifact_entry()` now accepts `allow_indexed_missing_required`.
- `verify_bundle()` passes that flag when `require_complete_bundle=False`.
- Missing required artifacts still appear in `summary.missing_required_count`.
- Added a regression test proving an incomplete index can verify with `ok=true`, `artifact_failure_count=0`, and a non-zero `missing_required_count`.

## Verification

- `python -m py_compile ops\scripts\verify_desci_provider_workflow_artifact_bundle.py`
  - Result: pass
- `python -m pytest tests\test_desci_provider_workflow_artifact_bundle_verifier.py tests\test_desci_provider_workflow_artifact_index.py tests\test_desci_provider_apply_workflow_handoff.py -q`
  - Result: `14 passed`
- Custom incomplete-bundle verifier:
  - `python ..\..\ops\scripts\verify_desci_provider_workflow_artifact_bundle.py --index var\desci-provider-workflow-artifact-index-custom-verify-path-2026-07-04.json --artifact-root . --allow-incomplete-bundle --json-out var\desci-provider-workflow-artifact-index-custom-verify-path-verify-allow-incomplete-2026-07-04.json --markdown-out var\desci-provider-workflow-artifact-index-custom-verify-path-verify-allow-incomplete-2026-07-04.md`
  - Result: exit `0`, `ok=true`.
  - Summary: `artifact_failure_count=0`, `missing_required_count=8`, `required_artifact_count=9`.
  - Workflow counts preserved: `operator_command_count=8`, `operator_command_failure_count=0`.

## Current Launch Boundary

Public launch remains externally blocked:

- Provider templates still need private values.
- Railway authentication and project-link context remain unresolved.
- Vercel authentication and project-link context remain unresolved.
- Post-apply promotion remains no-go until provider checks pass and promotion evidence is regenerated.

This cycle improves local/custom evidence verification semantics only. Complete upload bundles still require every required artifact unless `--allow-incomplete-bundle` is explicitly supplied.

## Next Cycle

Continue by feeding the verified artifact-index summary fields into the higher-level DeSci operator status refresh, or by generating a full temporary provider workflow bundle for complete local verification.
