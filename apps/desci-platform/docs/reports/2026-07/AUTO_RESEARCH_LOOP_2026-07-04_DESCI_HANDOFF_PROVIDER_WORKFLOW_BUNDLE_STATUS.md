# AutoResearch Loop - DeSci Handoff Provider Workflow Bundle Status - 2026-07-04

## Objective

Feed provider workflow artifact-bundle verification results into the higher-level DeSci launch handoff refresh so operators can see bundle integrity and operator command counts in the refreshed status JSON/Markdown.

## Scope and Owned Paths

- `ops/scripts/desci_launch_handoff_refresh.py`
- `tests/test_desci_launch_handoff_refresh.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_HANDOFF_PROVIDER_WORKFLOW_BUNDLE_STATUS.md`

## Source Evidence

- The provider workflow bundle verifier now emits:
  - `summary.missing_required_count`
  - `summary.artifact_failure_count`
  - `provider_apply_workflow.operator_command_count`
  - `provider_apply_workflow.operator_command_failure_count`
- The DeSci handoff refresh already injects active bundle fields into `status.desci.handoff_refresh`, making it the right operator-facing surface.

## A/B Hypothesis

- Baseline A: leave provider workflow bundle verification as a separate JSON/Markdown artifact.
  - Rejected because operators reading the active DeSci status still have to know which bundle verifier artifact to open.
- Variant B: accept an explicit `--provider-workflow-bundle-json` and summarize safe verifier fields into the handoff refresh bundle, status JSON, and status Markdown.
  - Adopted because it keeps the source artifact separate while surfacing the actionable counts in the active handoff.

## Implementation

- Added `provider_workflow_bundle_json` to `refresh_desci_launch_handoff()` and the CLI as `--provider-workflow-bundle-json`.
- The path is included in secret-scan extra paths.
- `_build_bundle()` now includes `provider_workflow_bundle`.
- Active status now receives provider workflow bundle fields under `desci.handoff_refresh`.
- Status Markdown now appends a `DeSci Provider Workflow Bundle` section when the bundle input is provided.
- Markdown scalar rendering now handles non-string booleans and counts instead of blanking them.

## Verification

- `python -m py_compile ops\scripts\desci_launch_handoff_refresh.py`
  - Result: pass
- `python -m pytest tests\test_desci_launch_handoff_refresh.py -q`
  - Result: `14 passed`
- Regression coverage verifies:
  - provider workflow bundle JSON is scanned in each secret-scan pass,
  - bundle summary is present in the handoff refresh bundle,
  - active status JSON includes workflow bundle status, missing artifact count, artifact failure count, and operator command count,
  - status Markdown includes `DeSci Provider Workflow Bundle`, `Operator commands: 8`, and `Missing required artifacts: 8`.

## Current Launch Boundary

Public launch remains externally blocked:

- Provider templates still need private values.
- Railway authentication and project-link context remain unresolved.
- Vercel authentication and project-link context remain unresolved.
- Post-apply promotion remains no-go until provider checks pass and promotion evidence is regenerated.

This cycle improves operator visibility; it does not make provider workflow no-go evidence launch-ready.

## Next Cycle

Continue by running a real handoff refresh with the latest provider workflow bundle verifier artifact, or by generating a complete local provider workflow bundle so the status can report `index_complete_bundle=true`.
