# AutoResearch Loop: DeSci Provider Workflow Attestation Verify

Date: 2026-07-04

## Objective

Close the DeSci provider workflow evidence loop by verifying the generated GitHub artifact attestations after the handoff bundle is downloaded. The previous loop created provenance attestations; this loop adds the consumer-side verification step.

## Scope and Owned Paths

- `.github/workflows/desci-provider-apply-workflow-handoff.yml`
- `tests/test_desci_provider_apply_workflow_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_PROVIDER_WORKFLOW_ATTESTATION_VERIFY.md`

Existing release-approval handoff worktree changes were inspected as a candidate but not adopted in this loop because they pre-existed this cycle and have a larger ownership surface.

## External Sources Checked

- GitHub CLI `gh attestation verify` manual:
  - https://cli.github.com/manual/gh_attestation_verify
- GitHub Actions `GITHUB_TOKEN` authentication guidance:
  - https://docs.github.com/actions/reference/authentication-in-a-workflow
- GitHub artifact attestations docs:
  - https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- `actions/attest` repository:
  - https://github.com/actions/attest
- Veritas AutoResearch source commit:
  - `Veritas-7/autoresearch-skill-system` `main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: generate and upload provider workflow attestations, but leave attestation verification to a manual reviewer.
- Variant B: after downloading the provider workflow artifact, verify representative attested evidence files with `gh attestation verify --repo "${GITHUB_REPOSITORY}" --format json`, write per-subject JSON or stderr evidence, append a Markdown summary, and upload that verification evidence.
- Primary KPI: consumer-side provenance verification coverage for launch handoff evidence.
- Guardrails: keep fail-closed workflow behavior, preserve upload-before-fail-closed evidence, keep product and browser smoke green, and keep DeSci workspace smoke green.
- Decision rule: adopt Variant B only if workflow structure is test-covered, GitHub CLI support is present, and all local guardrails pass.

## Implementation

- Added `Verify downloaded provider apply workflow attestations` to the post-download job.
- Uses `GH_TOKEN: ${{ github.token }}` and `gh attestation verify`.
- Verifies four representative downloaded files:
  - artifact index JSON
  - bundle verification JSON
  - provider apply results receipt
  - provider workflow verification Markdown
- Writes verification evidence under `var/provider-workflow-attestation-verify`.
- Uploads `var/provider-workflow-attestation-verify/**` with the post-download verification artifact.
- Extended the workflow contract test to assert the step, `GH_TOKEN`, `--repo`, `--format json`, evidence directory, and upload inclusion.

## Verification

- Focused tests:
  - `python -m pytest tests/test_desci_provider_apply_workflow_handoff.py tests/test_desci_provider_workflow_artifact_bundle_verifier.py -q`
  - Result: `7 passed in 1.53s`
- Workflow YAML parse:
  - Result: `workflow yaml parsed with post-download attestation verify`
- GitHub CLI local capability check:
  - `gh attestation verify --help`
  - Result: command supports `--repo` and `--format json`.
- Bash syntax check:
  - Attempted to run `bash -n` against the extracted CI shell block.
  - Local Windows environment lacks `/bin/bash`; CI target is `ubuntu-latest`, so this remains covered by YAML parsing and contract tests locally.
- Product smoke:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8091 --frontend http://127.0.0.1:5205 --json-out var/desci-product-smoke-provider-attestation-verify-2026-07-04.json`
  - Result: OK, launch decision still `no-go` due external provider blockers.
- Browser launch-click smoke:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5205 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-attestation-verify-2026-07-04.json --trace-on-failure-dir var/traces/provider-attestation-verify-2026-07-04`
  - Result: 9/9 launch-critical checks OK.
- DeSci workspace smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-attestation-verify-2026-07-04.json`
  - Result: passed=8, failed=0, total=8.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-release-approval-next.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_RELEASE_APPROVAL_NEXT.md`
  - Result: valid, 8 sources, adopted=8.

## Decision

Adopt Variant B. It turns provider workflow provenance from producer-only metadata into an operator-verifiable post-download check while keeping existing artifact verification and fail-closed semantics.

## Remaining Blocker

Public launch remains no-go until private provider values are applied outside git and the promotion receipt verifies as go.

## Next Cycle

Re-evaluate the existing release-approval handoff dirty changes as their own owned cycle, with targeted tests and a separate commit, or continue hardening provider workflow verification around stricter signer identity once the live GitHub workflow run evidence is available.
