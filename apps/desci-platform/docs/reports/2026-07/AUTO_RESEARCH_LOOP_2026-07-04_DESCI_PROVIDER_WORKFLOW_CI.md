# AutoResearch Loop: DeSci Provider Workflow CI Handoff

Date: 2026-07-04

## Objective

Move the DeSci provider apply workflow from local-only CLI usage into an operator-runnable GitHub Actions handoff path. The previous loop added JSON, Markdown, step-summary, annotation, and output support to the verifier; this loop adds a dedicated manual workflow that generates the same provider workflow evidence bundle and fails closed after artifact upload.

## Scope and Owned Paths

- `.github/workflows/desci-provider-apply-workflow-handoff.yml`
- `tests/test_desci_provider_apply_workflow_handoff.py`

Existing `.github/workflows/desci-platform-quality.yml` and several product docs were already dirty in the worktree, so this loop uses a new dedicated workflow file and does not stage those unrelated changes.

## External Sources Checked

- GitHub Actions workflow syntax stores workflow files in `.github/workflows`, supports manual `workflow_dispatch`, and supports top-level `permissions`.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Actions workflow commands set step outputs through `GITHUB_OUTPUT` and append Markdown summaries through `GITHUB_STEP_SUMMARY`.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep provider workflow verification as local CLI commands documented in the reports.
  - Rejected because launch operators still have to reconstruct the command sequence and manually preserve artifacts before failure.
- Variant B: add a dedicated manual GitHub Actions workflow.
  - Adopted because it preserves the existing fail-closed verifier, emits GitHub summary/annotation/output surfaces, uploads the provider handoff bundle before the final failing step, and avoids mixing with pre-existing dirty changes in `desci-platform-quality.yml`.

## Implementation

- Added a manual workflow `DeSci Provider Apply Workflow Handoff`.
- The workflow uses `permissions: contents: read` and `persist-credentials: false`.
- It runs:
  - `external_release_gate.py` to produce external launch gate evidence.
  - `external_gate_handoff.py` to generate the provider handoff packet, provider templates, template index, and redacted apply plan.
  - `external_gate_handoff.py --record-provider-apply-results-from-plan` to write dry-run apply results.
  - `external_gate_handoff.py --verify-provider-apply-workflow` with `--github-step-summary`, `--github-annotations`, and `--github-output`.
- It uploads the provider workflow artifacts with `if-no-files-found: error` and `retention-days: 30`.
- It exits fail-closed after upload if any provider workflow gate is still blocked.
- Added a root contract test for the workflow file.

## Evidence

- Workflow YAML parse:
  - `python -c "import yaml, pathlib; data=yaml.safe_load(pathlib.Path('.github/workflows/desci-provider-apply-workflow-handoff.yml').read_text(encoding='utf-8')); assert data.get('name') == 'DeSci Provider Apply Workflow Handoff'; assert 'provider-apply-workflow-handoff' in data.get('jobs', {}); print('workflow yaml parsed')"` -> pass.
- Focused contract test:
  - `python -m pytest tests/test_desci_provider_apply_workflow_handoff.py -q` -> 1 passed.
- Related provider tests:
  - `python -m pytest tests/test_desci_provider_apply_workflow_handoff.py apps/desci-platform/backend/tests/test_external_release_gate.py apps/desci-platform/backend/tests/test_external_gate_handoff.py -q` -> 59 passed.
- Local workflow command sequence:
  - `external_release_gate.py` -> exit 1, expected no-go, wrote `var/external-release-gate-provider-workflow-machine.json`.
  - provider handoff generation -> exit 1, expected no-go, wrote handoff JSON/Markdown, provider templates, template index, and apply plan.
  - dry-run apply results recorder -> exit 1, expected dry-run blocked, `command_count=27`.
  - workflow verifier -> exit 1, expected blocked, wrote JSON/Markdown/step summary/annotation log/GitHub output.
  - Verifier output: `ok=false`, `operator_phase=provider_apply_workflow_blocked`, `failure_count=5`, `results_command_failure_count=27`.
  - `var/external-gate-provider-workflow-machine-github-output.txt` includes `provider_apply_workflow_ok=false`, `provider_apply_workflow_failure_count=5`, and `provider_apply_workflow_results_command_failure_count=27`.
- Secret-shape scan over generated provider workflow handoff artifacts:
  - Result: no secret-shaped values found across 16 generated files. Environment key names such as `private_key` were treated as field names, not leaked values.
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8082 --frontend http://127.0.0.1:5196 --json-out var/desci-product-smoke-provider-workflow-ci-2026-07-04.json`
  - 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5196 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-workflow-ci-2026-07-04.json --trace-on-failure-dir var/traces/provider-workflow-ci-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-workflow-ci-2026-07-04.json`
  - 8/8 passed.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-provider-workflow-ci.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_PROVIDER_WORKFLOW_CI.md`
  - Result: valid, 8 sources, adopted=8.

## Current Launch Blocker

The provider workflow can now be generated locally or through a dedicated manual GitHub Actions handoff path, and the CI path preserves artifacts before failing closed. Public promotion still remains no-go until private provider values are applied and the post-apply promotion receipt verifies as go.
