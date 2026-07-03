# AutoResearch Loop: Release Approval Handoff Gate

Date: 2026-07-04

## Objective

Adopt the pending release-approval handoff hardening as a verified launch gate. The goal is to make the manual release approval workflow produce reviewable artifacts, upload them before fail-closed termination, and document the evidence contract for operators.

## Scope and Owned Paths

- `.github/workflows/desci-platform-quality.yml`
- `docs/QUALITY_GATE.md`
- `ops/scripts/write_release_approval_handoff_artifact_index.py`
- `tests/test_release_approval_handoff_artifact_index.py`
- `tests/test_security_gate_contracts.py`
- `tests/test_workspace_smoke.py`
- `apps/desci-platform/backend/tests/test_deployment_docs.py`
- `packages/shared/tests/test_llm_provider_order.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_RELEASE_APPROVAL_HANDOFF_GATE.md`

## External Sources Checked

- GitHub `workflow_dispatch` and manual workflow docs:
  - https://docs.github.com/enterprise-cloud@latest/actions/using-workflows/workflow-syntax-for-github-actions
  - https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow
- GitHub workflow command docs for `GITHUB_STEP_SUMMARY`:
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- `actions/upload-artifact` repository and artifact retention behavior:
  - https://github.com/actions/upload-artifact
- Xiaomi MiMo current model docs:
  - https://mimo.mi.com/docs/en-US/updates/model
  - https://mimo.xiaomi.com/mimo-v2-5-pro/
- Veritas AutoResearch source commit:
  - `Veritas-7/autoresearch-skill-system` `main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: release approval remains a local/operator script path, with evidence mostly in local files or chat summaries.
- Variant B: expose release approval as a manual GitHub Actions handoff with a boolean `workflow_dispatch` input, machine-readable artifact index, Markdown summary, uploaded evidence bundle, and fail-closed exit-code handling after artifact upload.
- Primary KPI: release-approval evidence completeness and CI operator reproducibility.
- Guardrails: focused contract tests, workspace smoke, DeSci smoke, product smoke, browser click smoke, secret-shape scan, and push smoke must pass.
- Decision rule: adopt Variant B only if the handoff artifact index and workflow contract are test-covered and the current product path stays green.

## Implementation

- Added `release_approval_handoff` as a manual workflow input in `desci-platform-quality.yml`.
- Added a dedicated `Release Approval Handoff` job that:
  - runs the release approval machine wrapper,
  - validates the Markdown handoff through DeSci `release_gate.py`,
  - writes a machine-readable artifact index and Markdown summary,
  - uploads the evidence bundle with `if-no-files-found: error`,
  - fails closed only after artifacts are uploaded.
- Added `write_release_approval_handoff_artifact_index.py` for SHA-256, size, missing-artifact, exit-code, and review-order metadata.
- Expanded quality gate and workflow contract tests for the release approval artifact contract.
- Added DeSci deployment docs contract coverage.
- Fixed the shared LLM provider-order test to expect current Xiaomi MiMo `mimo-v2.5-pro`, matching local routing config and Xiaomi's current model docs.

## Verification

- Focused release/quality tests:
  - `python -m pytest tests/test_release_approval_handoff_artifact_index.py tests/test_security_gate_contracts.py tests/test_workspace_smoke.py apps/desci-platform/backend/tests/test_deployment_docs.py -q`
  - Result: `79 passed in 77.30s`
- Script compile:
  - `python -m py_compile ops/scripts/write_release_approval_handoff_artifact_index.py`
  - Result: pass.
- Workflow YAML parse:
  - Result: `desci-platform-quality workflow yaml parsed`
- Shared package regression:
  - `python -m pytest packages/shared/tests/ -q --tb=short`
  - First run found stale `mimo-v2-pro` expectation.
  - After test fix: `353 passed in 33.97s`
- Workspace smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-release-approval-handoff-2026-07-04.json`
  - Result: passed=9, failed=0, total=9.
- Product smoke:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8092 --frontend http://127.0.0.1:5206 --json-out var/desci-product-smoke-release-approval-handoff-2026-07-04.json`
  - Result: OK; launch decision remains `no-go` because external provider values are still missing.
- Browser launch-click smoke:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5206 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-release-approval-handoff-2026-07-04.json --trace-on-failure-dir var/traces/release-approval-handoff-2026-07-04`
  - Result: 9/9 launch-critical checks OK.
- DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-release-approval-handoff-2026-07-04.json`
  - Result: passed=8, failed=0, total=8.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-release-approval-handoff.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_RELEASE_APPROVAL_HANDOFF.md`
  - Result: valid, 8 sources, adopted=8.

## Decision

Adopt Variant B. The release approval handoff is now a CI-visible, artifact-backed, fail-closed operator path rather than only a local script path.

## Remaining Blocker

Public product launch remains no-go until private provider values are applied outside git and the promotion receipt verifies as go.

## Next Cycle

Run the manual GitHub workflow once the branch is on the default branch or otherwise available for manual dispatch, then inspect the uploaded release-approval handoff artifact index and summary from the live workflow run.
