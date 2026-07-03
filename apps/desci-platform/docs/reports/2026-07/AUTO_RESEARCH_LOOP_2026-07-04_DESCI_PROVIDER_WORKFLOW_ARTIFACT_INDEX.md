# AutoResearch Loop: DeSci Provider Workflow Artifact Index

Date: 2026-07-04

## Objective

Make the dedicated DeSci provider apply workflow easier to operate after a fail-closed run. The prior workflow uploaded the right JSON, Markdown, provider template, results, and verifier files before failing, but operators still had to infer the review order and artifact completeness from raw paths. This loop adds a machine-readable and Markdown artifact index before upload.

## Scope and Owned Paths

- `.github/workflows/desci-provider-apply-workflow-handoff.yml`
- `ops/scripts/write_desci_provider_workflow_artifact_index.py`
- `tests/test_desci_provider_apply_workflow_handoff.py`
- `tests/test_desci_provider_workflow_artifact_index.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_PROVIDER_WORKFLOW_ARTIFACT_INDEX.md`

Existing unrelated worktree changes were left unstaged, including `.github/workflows/desci-platform-quality.yml` and untracked DeSci backend tests.

## External Sources Checked

- GitHub Actions artifact storage supports uploading workflow data for later inspection.
  - https://docs.github.com/en/actions/tutorials/store-and-share-data
- GitHub Actions workflow commands support `GITHUB_STEP_SUMMARY` for Markdown summaries and `GITHUB_OUTPUT` for step outputs.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: rely on upload artifact paths alone.
  - Rejected because a no-go run still requires manual path-by-path completeness checks before the operator can trust the uploaded bundle.
- Variant B: write a JSON and Markdown artifact index before upload.
  - Adopted because it records required artifact presence, SHA-256 hashes, review order, provider templates, workflow verifier state, and exit codes while preserving the fail-closed final step.

## Implementation

- Added `write_desci_provider_workflow_artifact_index.py`.
- The index writes:
  - `var/desci-provider-workflow-artifact-index-machine.json`
  - `var/desci-provider-workflow-artifact-index-summary.md`
  - optional `GITHUB_STEP_SUMMARY` content.
- The index marks the nine core provider workflow files as required for a complete upload bundle.
- Provider `.env` templates under `var/external-gate-provider-workflow-machine/` are discovered as optional artifacts, so a future go-ready run with zero templates does not false-fail completeness.
- The workflow now writes the index after provider workflow verification and before `actions/upload-artifact`.
- The artifact upload includes the index JSON and Markdown summary.

## Evidence

- Focused tests:
  - `python -m pytest tests/test_desci_provider_workflow_artifact_index.py tests/test_desci_provider_apply_workflow_handoff.py -q`
  - Result: 6 passed.
- Workflow YAML parse:
  - `python -c "import yaml, pathlib; data=yaml.safe_load(pathlib.Path('.github/workflows/desci-provider-apply-workflow-handoff.yml').read_text(encoding='utf-8')); assert data.get('name') == 'DeSci Provider Apply Workflow Handoff'; assert 'provider-apply-workflow-handoff' in data.get('jobs', {}); print('workflow yaml parsed')"`
  - Result: pass.
- Local provider workflow sequence:
  - `external_release_gate.py` exit 1, expected no-go.
  - provider handoff generation exit 1, expected no-go.
  - provider apply results recorder exit 1, expected dry-run blocked.
  - provider workflow verifier exit 1, expected blocked.
  - artifact index writer exit 0.
- Index summary:
  - `complete_bundle=true`
  - `missing_count=0`
  - `first_decision_artifact=var/external-gate-provider-workflow-machine-verify.json`
  - `workflow_ok=false`
  - `phase=provider_apply_workflow_blocked`
  - `failure_count=5`
  - `results_command_failure_count=27`
  - `provider_template_count=4`
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8083 --frontend http://127.0.0.1:5197 --json-out var/desci-product-smoke-provider-workflow-artifact-index-2026-07-04.json`
  - Result: 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5197 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-workflow-artifact-index-2026-07-04.json --trace-on-failure-dir var/traces/provider-workflow-artifact-index-2026-07-04`
  - Result: 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-workflow-artifact-index-2026-07-04.json`
  - Result: 8/8 passed.
- Secret-shape scan over owned files:
  - Result: no exact-value matches.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-provider-workflow-artifact-index.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_PROVIDER_WORKFLOW_ARTIFACT_INDEX.md`
  - Result: valid, 8 sources, adopted=8.

## Current Launch Blocker

The dedicated provider workflow now uploads a self-indexed, hash-backed evidence bundle before fail-closed exit. Public promotion remains no-go until private provider values are applied and the post-apply promotion receipt verifies as go.
