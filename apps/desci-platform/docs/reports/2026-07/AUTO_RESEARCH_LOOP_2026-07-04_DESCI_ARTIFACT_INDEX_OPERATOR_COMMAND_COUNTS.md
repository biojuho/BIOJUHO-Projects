# AutoResearch Loop - DeSci Artifact Index Operator Command Counts - 2026-07-04

## Objective

Carry provider apply workflow operator command-summary counts into the downstream artifact index and bundle verifier so uploaded no-go evidence bundles preserve command-chain drift status after artifact download and verification.

## Scope and Owned Paths

- `ops/scripts/write_desci_provider_workflow_artifact_index.py`
- `ops/scripts/verify_desci_provider_workflow_artifact_bundle.py`
- `tests/test_desci_provider_workflow_artifact_index.py`
- `tests/test_desci_provider_workflow_artifact_bundle_verifier.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_ARTIFACT_INDEX_OPERATOR_COMMAND_COUNTS.md`

## Source Evidence

- Upstream comparison reference: `https://github.com/Veritas-7/autoresearch-skill-system.git` main/HEAD at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Prior local cycle added workflow JSON, Markdown, GitHub output, and console fields for:
  - `operator_command_count`
  - `operator_command_failure_count`
- Existing DeSci provider workflow artifact index is the downstream review and upload surface for fail-closed provider apply evidence.

## A/B Hypothesis

- Baseline A: keep operator command counts only in the workflow verifier artifact.
  - Rejected because post-download bundle verification and artifact index consumers would still lose the command-chain drift signal.
- Variant B: copy the workflow summary counts into the artifact index and preserve them through bundle verification Markdown/JSON.
  - Adopted because the no-go evidence bundle now keeps the same workflow command status across all review layers.

## Implementation

- `provider_apply_workflow_summary()` now emits:
  - `operator_command_count`
  - `operator_command_failure_count`
- Artifact-index Markdown now prints both counts.
- Bundle verification JSON now carries both counts under `provider_apply_workflow`.
- Bundle verification Markdown now prints both counts.
- Tests cover present workflow JSON, missing workflow JSON, index Markdown, complete bundle verification, and CLI-generated verifier Markdown.

## Verification

- `python -m py_compile ops\scripts\write_desci_provider_workflow_artifact_index.py ops\scripts\verify_desci_provider_workflow_artifact_bundle.py`
  - Result: pass
- `python -m pytest tests\test_desci_provider_workflow_artifact_index.py tests\test_desci_provider_workflow_artifact_bundle_verifier.py tests\test_desci_provider_apply_workflow_handoff.py -q`
  - Result: `12 passed`
- Real workflow index spot-check:
  - `python ..\..\ops\scripts\write_desci_provider_workflow_artifact_index.py --workspace-root . --json-out var\desci-provider-workflow-artifact-index-operator-command-counts-2026-07-04.json --markdown-summary-out var\desci-provider-workflow-artifact-index-operator-command-counts-2026-07-04.md --verify-json var\provider-apply-plan-operator-command-summary-workflow-output-2026-07-04.json --provider-template-dir var\provider-templates-operator-command-counts-2026-07-04 --external-exit-code 1 --handoff-exit-code 1 --results-exit-code 1 --verify-exit-code 0`
  - Result: index JSON and Markdown include `operator_command_count=8` and `operator_command_failure_count=0`.
- Real bundle verifier spot-check:
  - `python ..\..\ops\scripts\verify_desci_provider_workflow_artifact_bundle.py --index var\desci-provider-workflow-artifact-index-operator-command-counts-2026-07-04.json --artifact-root . --allow-incomplete-bundle --json-out var\desci-provider-workflow-artifact-index-operator-command-counts-verify-2026-07-04.json --markdown-out var\desci-provider-workflow-artifact-index-operator-command-counts-verify-2026-07-04.md`
  - Result: verifier JSON and Markdown carry `operator_command_count=8` and `operator_command_failure_count=0`.
  - Expected local caveat: verifier `ok=false` because the custom spot-check verify JSON path is not part of the default upload review order. The focused tests cover the complete-bundle path.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-artifact-index-operator-command-counts-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`.

## Current Launch Boundary

Public launch remains externally blocked:

- Provider templates still need private values.
- Railway authentication and project-link context remain unresolved.
- Vercel authentication and project-link context remain unresolved.
- Post-apply promotion remains no-go until provider checks pass and promotion evidence is regenerated.

This cycle only preserves operator command-status evidence across bundle/index layers. It does not bypass the fail-closed provider workflow.

## Next Cycle

Continue by tightening the custom verify-json artifact-index path behavior, or by feeding bundle verifier command counts into the higher-level operator status refresh.
