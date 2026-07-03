# AutoResearch Loop: DeSci Provider Workflow Bundle Verifier

Date: 2026-07-04

## Objective

Advance the dedicated DeSci provider workflow handoff from "artifact bundle is indexed" to "artifact bundle can be independently verified from that index after upload or download." This keeps the no-go workflow useful for operators: the product may still be blocked by private provider values, but the uploaded evidence bundle can now be checked for required files, size, SHA-256, and secret-shaped markers.

## Scope and Owned Paths

- `.github/workflows/desci-provider-apply-workflow-handoff.yml`
- `ops/scripts/verify_desci_provider_workflow_artifact_bundle.py`
- `tests/test_desci_provider_apply_workflow_handoff.py`
- `tests/test_desci_provider_workflow_artifact_bundle_verifier.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_PROVIDER_WORKFLOW_BUNDLE_VERIFIER.md`

Existing unrelated dirty files were left unstaged.

## External Sources Checked

- GitHub Actions artifact docs support uploading multiple paths, downloading artifacts, and archive-level digest validation during download.
  - https://docs.github.com/en/actions/tutorials/store-and-share-data
- GitHub `actions/upload-artifact` documents `if-no-files-found`, retention controls, artifact IDs, and current artifact action behavior.
  - https://github.com/actions/upload-artifact
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep the provider workflow artifact index as the only bundle integrity surface.
  - Weakness: operators still need a deterministic command to verify a downloaded bundle against the index.
- Variant B: add a verifier that reads the index and recomputes current existence, byte size, SHA-256, and high-confidence secret-shaped markers.
  - Adopted because it is offline, deterministic, works against both workspace-root `var/...` paths and downloaded artifact directories with `var/` stripped, and does not require provider credentials.

## Implementation

- Added `verify_desci_provider_workflow_artifact_bundle.py`.
- The verifier checks:
  - index schema and first decision artifact membership
  - required bundle completeness
  - current file existence
  - byte-size matches
  - SHA-256 matches
  - high-confidence secret-shaped marker patterns
  - optional `--require-workflow-ok` for post-apply promotion use
- The dedicated workflow now runs the verifier after index generation and before artifact upload.
- The upload bundle now includes:
  - `var/desci-provider-workflow-artifact-bundle-verify.json`
  - `var/desci-provider-workflow-artifact-bundle-verify.md`

## Evidence

- Focused tests:
  - `python -m pytest tests/test_desci_provider_workflow_artifact_bundle_verifier.py tests/test_desci_provider_workflow_artifact_index.py tests/test_desci_provider_apply_workflow_handoff.py -q`
  - Result: 11 passed.
- Workflow YAML parse and ordering:
  - `index writer < bundle verifier < artifact upload`
  - Result: pass.
- Local provider workflow sequence:
  - external release gate exit 1, expected no-go.
  - provider handoff generation exit 1, expected no-go.
  - provider apply results recorder exit 1, expected dry-run blocked.
  - provider workflow verifier exit 1, expected blocked.
  - artifact index writer exit 0.
  - bundle verifier exit 0.
- Bundle verifier summary:
  - `ok=true`
  - `index_complete_bundle=true`
  - `workflow_ok=false`
  - `phase=provider_apply_workflow_blocked`
  - `artifact_count=13`
  - `required_artifact_count=9`
  - `artifact_failure_count=0`
  - `missing_required_count=0`
  - `digest_mismatch_count=0`
  - `size_mismatch_count=0`
  - `secret_marker_count=0`
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8084 --frontend http://127.0.0.1:5198 --json-out var/desci-product-smoke-provider-workflow-bundle-2026-07-04.json`
  - Result: 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5198 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-workflow-bundle-2026-07-04.json --trace-on-failure-dir var/traces/provider-workflow-bundle-2026-07-04`
  - Result: 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-workflow-bundle-2026-07-04.json`
  - Result: 8/8 passed.
- Secret-shape scan over owned files:
  - Result: no exact-value matches.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-provider-workflow-bundle.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_PROVIDER_WORKFLOW_BUNDLE.md`
  - Result: valid, 8 sources, adopted=8.

## Current Launch Blocker

The provider workflow evidence bundle is now self-indexed and independently verifiable. Public launch promotion remains no-go until private provider values are applied and the post-apply promotion receipt verifies as go.
