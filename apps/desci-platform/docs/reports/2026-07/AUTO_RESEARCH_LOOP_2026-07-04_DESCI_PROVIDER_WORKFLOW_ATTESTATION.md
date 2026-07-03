# AutoResearch Loop: DeSci Provider Workflow Attestation

Date: 2026-07-04

## Objective

Advance the DeSci provider apply workflow handoff from downloadable, hash-verified evidence to provenance-backed evidence. The product remains gated by private provider values and a promotion receipt, but the CI handoff bundle now has a cryptographic attestation step before upload.

## Scope and Owned Paths

- `.github/workflows/desci-provider-apply-workflow-handoff.yml`
- `tests/test_desci_provider_apply_workflow_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_PROVIDER_WORKFLOW_ATTESTATION.md`

## External Sources Checked

- GitHub artifact attestations docs:
  - https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- GitHub artifact attestations concept docs:
  - https://docs.github.com/en/actions/concepts/security/artifact-attestations
- `actions/attest` README and action metadata:
  - https://github.com/actions/attest
  - https://raw.githubusercontent.com/actions/attest/v4/action.yml
- Current repository visibility:
  - `gh repo view biojuho/BIOJUHO-Projects --json visibility,nameWithOwner,url` -> `PUBLIC`
- `actions/attest@v4` observed tag:
  - `f6bf1532d7d6793fce74eac584813a8eee607999`
- Veritas AutoResearch source commit:
  - `Veritas-7/autoresearch-skill-system` `main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep provider workflow evidence as an uploaded artifact bundle with local and post-download SHA/size verification.
- Variant B: add a pinned `actions/attest@v4` provenance step for the verified provider workflow evidence files before upload.
- Primary KPI: supply-chain evidence coverage for launch handoff artifacts.
- Guardrails: no regression in workflow structure, artifact upload-before-fail-closed order, product smoke, browser click smoke, or DeSci workspace smoke.
- Decision rule: adopt Variant B only if the attestation permissions and step order are test-covered, the repo meets GitHub's public repository availability condition, and all local guardrails pass.

## Implementation

- Added job-scoped permissions to `provider-apply-workflow-handoff`:
  - `contents: read`
  - `id-token: write`
  - `attestations: write`
- Added `Attest provider apply workflow evidence` after bundle verification and before artifact upload.
- Pinned the action to `actions/attest@f6bf1532d7d6793fce74eac584813a8eee607999 # v4`.
- Attested the generated provider workflow JSON/Markdown, artifact index, bundle verification, apply results, and workflow verification files.
- Extended the workflow structure test to assert permissions, pinned action use, step ordering, and representative attested subjects.

## Verification

- `python -m pytest tests/test_desci_provider_apply_workflow_handoff.py tests/test_desci_provider_workflow_artifact_bundle_verifier.py tests/test_desci_provider_workflow_artifact_index.py -q`
  - `12 passed in 2.14s`
- Workflow YAML parse:
  - `workflow yaml parsed with attestations permission`
- Product smoke:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8090 --frontend http://127.0.0.1:5204 --json-out var/desci-product-smoke-provider-attestation-2026-07-04.json`
  - Result: OK, launch decision still `no-go` because external providers are not applied.
- Browser launch-click smoke:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5204 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-attestation-2026-07-04.json --trace-on-failure-dir var/traces/provider-attestation-2026-07-04`
  - Result: 9/9 launch-critical checks OK.
- DeSci workspace smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-attestation-2026-07-04.json`
  - Result: passed=8, failed=0, total=8.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-next.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_NEXT.md`
  - Result: valid, 8 sources, adopted=8.

## Decision

Adopt Variant B. It improves provider handoff supply-chain evidence without changing the product runtime path. The workflow still fails closed when provider values or the promotion receipt are missing.

## Remaining Blocker

Public launch remains blocked until private provider values are populated outside git and the post-apply promotion receipt verifies as go.

## Next Cycle

Use the attested provider workflow bundle as the operator handoff artifact, then continue hardening the release-approval handoff path without staging unrelated dirty workflow changes unless they become the owned scope of the next loop.
