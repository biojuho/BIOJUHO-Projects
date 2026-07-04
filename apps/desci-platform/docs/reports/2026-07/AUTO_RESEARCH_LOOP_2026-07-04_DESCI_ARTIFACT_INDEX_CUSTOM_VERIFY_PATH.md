# AutoResearch Loop - DeSci Artifact Index Custom Verify Path - 2026-07-04

## Objective

Fix the provider workflow artifact index so a caller-supplied `--verify-json` path is included in the review order and artifact list. This keeps `first_decision_artifact` valid for custom/local provider workflow evidence bundles.

## Scope and Owned Paths

- `ops/scripts/write_desci_provider_workflow_artifact_index.py`
- `tests/test_desci_provider_workflow_artifact_index.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_ARTIFACT_INDEX_CUSTOM_VERIFY_PATH.md`

## Source Evidence

- Upstream comparison reference: `https://github.com/Veritas-7/autoresearch-skill-system.git` main/HEAD at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- The previous local spot check showed a custom workflow verify JSON path could become `first_decision_artifact` without appearing in the artifact review order.
- The bundle verifier requires `first_decision_artifact` to be present in indexed artifacts before a bundle can be trusted.

## A/B Hypothesis

- Baseline A: keep `REVIEW_ORDER` static and only change `first_decision_artifact`.
  - Rejected because custom-path index users get a first-decision artifact that downstream verification cannot locate in the bundle.
- Variant B: derive the review order from the chosen `verify_json`, replacing the provider workflow verification JSON path when it differs from the default.
  - Adopted because the indexed artifact list now matches the selected first-decision artifact while preserving the default upload contract.

## Implementation

- Added `review_order_for_verify_json()`.
- Added path-key normalization so forward-slash and backslash variants compare consistently.
- `build_payload()` now uses the derived review order for:
  - required artifact metadata
  - the serialized `review_order`
  - the `artifacts` list
- Added a focused regression test that verifies a custom workflow JSON replaces the default review-order path and is indexed as `provider_workflow_verification_json`.

## Verification

- `python -m py_compile ops\scripts\write_desci_provider_workflow_artifact_index.py`
  - Result: pass
- `python -m pytest tests\test_desci_provider_workflow_artifact_index.py tests\test_desci_provider_workflow_artifact_bundle_verifier.py tests\test_desci_provider_apply_workflow_handoff.py -q`
  - Result: `13 passed`
- Custom-path index spot check:
  - `python ..\..\ops\scripts\write_desci_provider_workflow_artifact_index.py --workspace-root . --json-out var\desci-provider-workflow-artifact-index-custom-verify-path-2026-07-04.json --markdown-summary-out var\desci-provider-workflow-artifact-index-custom-verify-path-2026-07-04.md --verify-json var\provider-apply-plan-operator-command-summary-workflow-output-2026-07-04.json --provider-template-dir var\provider-templates-operator-command-counts-2026-07-04 --external-exit-code 1 --handoff-exit-code 1 --results-exit-code 1 --verify-exit-code 0`
  - Result: custom verify JSON appears in `review_order`, `first_decision_artifact`, and `artifacts`.
  - Indexed `provider_workflow_verification_json` exists, has a SHA-256 digest, and carries `operator_command_count=8`, `operator_command_failure_count=0`.
- Bundle verifier spot check:
  - `python ..\..\ops\scripts\verify_desci_provider_workflow_artifact_bundle.py --index var\desci-provider-workflow-artifact-index-custom-verify-path-2026-07-04.json --artifact-root . --allow-incomplete-bundle --json-out var\desci-provider-workflow-artifact-index-custom-verify-path-verify-2026-07-04.json --markdown-out var\desci-provider-workflow-artifact-index-custom-verify-path-verify-2026-07-04.md`
  - Result: `first_decision_artifact` is included in artifacts and no longer fails that top-level verifier check.
  - Expected local caveat: verifier `ok=false` because the other eight default bundle artifacts were not generated for this custom spot check.

## Current Launch Boundary

Public launch remains externally blocked:

- Provider templates still need private values.
- Railway authentication and project-link context remain unresolved.
- Vercel authentication and project-link context remain unresolved.
- Post-apply promotion remains no-go until provider checks pass and promotion evidence is regenerated.

This cycle fixes artifact-index correctness for custom workflow evidence paths only.

## Next Cycle

Continue by deciding whether `--allow-incomplete-bundle` should ignore missing required artifact entries during local spot checks, or leave it strict and generate a full temporary bundle for local verification.
