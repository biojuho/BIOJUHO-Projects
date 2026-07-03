# AutoResearch Loop: DeSci Provider Workflow Post-Download Verification

Date: 2026-07-04

## Objective

Advance the DeSci provider workflow handoff from "the artifact bundle is verified before upload" to "the uploaded artifact can be downloaded and verified again." This improves launch operations because a failed provider workflow still leaves a reviewer with a checked, downloadable evidence bundle rather than only runner-local files.

## Scope and Owned Paths

- `.github/workflows/desci-provider-apply-workflow-handoff.yml`
- `tests/test_desci_provider_apply_workflow_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_PROVIDER_WORKFLOW_POST_DOWNLOAD.md`

Existing unrelated dirty files were left unstaged.

## External Sources Checked

- GitHub Actions artifacts docs document current-run `download-artifact`, artifact sharing across jobs, and digest validation when downloading artifacts.
  - https://docs.github.com/en/actions/tutorials/store-and-share-data
- GitHub workflow artifact download docs document repository read access, the artifact list UI, and GitHub CLI download behavior.
  - https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts
- `actions/download-artifact` v5 tag observed:
  - `634f93cb2916e3fdff6788551b99b062d0335ce0`
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: verify the provider workflow bundle before upload only.
  - Weakness: it proves the runner-local files, but not the actual downloaded artifact shape operators will inspect.
- Variant B: add a second workflow job that downloads the uploaded provider workflow artifact and reruns the bundle verifier against the downloaded directory.
  - Adopted because GitHub performs artifact digest validation during download, while the repo verifier checks the bundle's internal file-level SHA-256/size/index contract.

## Implementation

- Added `provider-apply-workflow-artifact-post-download` job.
- The job:
  - uses `needs: provider-apply-workflow-handoff`
  - runs with `if: always()` so it still runs after the provider handoff job fails closed
  - downloads `provider-apply-workflow-handoff-${{ github.run_id }}-${{ github.run_attempt }}`
  - verifies `var/provider-workflow-downloaded-artifact/desci-provider-workflow-artifact-index-machine.json`
  - uploads `provider-apply-workflow-post-download-verification-${{ github.run_id }}-${{ github.run_attempt }}`
- Added YAML structure assertions for job order and pinned `actions/download-artifact` usage.

## Evidence

- Focused tests:
  - `python -m pytest tests/test_desci_provider_apply_workflow_handoff.py tests/test_desci_provider_workflow_artifact_bundle_verifier.py -q`
  - Result: 7 passed.
- Workflow YAML parse:
  - provider handoff job exists
  - post-download verification job exists
  - Result: pass.
- Local provider workflow sequence with simulated downloaded artifact layout:
  - external release gate exit 1, expected no-go
  - provider handoff generation exit 1, expected no-go
  - provider apply results recorder exit 1, expected dry-run blocked
  - provider workflow verifier exit 1, expected blocked
  - artifact index writer exit 0
  - pre-upload bundle verifier exit 0
  - simulated post-download bundle verifier exit 0
- Post-download verifier summary:
  - `ok=true`
  - `workflow_ok=false`
  - `artifact_count=13`
  - `required_artifact_count=9`
  - `artifact_failure_count=0`
  - `missing_required_count=0`
  - `digest_mismatch_count=0`
  - `size_mismatch_count=0`
  - `secret_marker_count=0`
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8085 --frontend http://127.0.0.1:5199 --json-out var/desci-product-smoke-provider-workflow-post-download-2026-07-04.json`
  - Result: 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5199 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-workflow-post-download-2026-07-04.json --trace-on-failure-dir var/traces/provider-workflow-post-download-2026-07-04`
  - Result: 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-workflow-post-download-2026-07-04.json`
  - Result: 8/8 passed.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-provider-workflow-post-download.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_PROVIDER_WORKFLOW_POST_DOWNLOAD.md`
  - Result: valid, 8 sources, adopted=8.

## Current Launch Blocker

The provider workflow artifact is now verified before upload and again after download. Public launch promotion remains no-go until private provider values are applied and the post-apply promotion receipt verifies as go.
