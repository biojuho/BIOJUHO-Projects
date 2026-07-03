# AutoResearch Loop: DeSci Provider Workflow Annotations

Date: 2026-07-04

## Objective

Make the DeSci provider apply workflow verifier more visible in GitHub Actions. The previous loop added JSON, Markdown, and job-summary evidence; this loop adds CI annotations so blocked release conditions appear directly in the workflow UI.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub Actions workflow commands support `notice`, `warning`, and `error` annotations via stdout.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Actions job summaries support Markdown via `GITHUB_STEP_SUMMARY`.
  - https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
- GitHub Actions artifacts are the supported way to store and share workflow evidence after a run.
  - https://docs.github.com/en/actions/tutorials/store-and-share-data
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: rely on JSON, Markdown, and step summary output.
  - Rejected as incomplete for CI review because release blockers are still one click away from the Checks annotation list.
- Variant B: add opt-in GitHub Actions annotations to the provider workflow verifier.
  - Adopted because the workflow still fails closed through exit code and JSON, while each blocking reason can also appear as an Actions error annotation.

## Implementation

- Added GitHub workflow-command escaping for annotation data and properties.
- Added `provider_apply_workflow_github_annotations()`.
- Added `print_provider_apply_workflow_github_annotations()`.
- Added `--github-annotations` to `--verify-provider-apply-workflow`.
- Added CLI validation so `--github-annotations` is only accepted in workflow verification mode.
- Added tests for escaping, blocked workflow annotation output, and invalid flag usage.

## Evidence

- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --refresh-latest-commits --json-out var/github-modernization-radar-auto-research-2026-07-04-workflow-annotations.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_WORKFLOW_ANNOTATIONS.md`
  - Result: valid, 8 sources, adopted=8.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py -q` -> 45 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 184 passed.
- Current handoff/apply plan regeneration:
  - `release_decision=no-go`, `ok=false`, `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`, `next_actions=12`.
  - Failed surfaces: `deploy_readiness`, `provider_preflight`.
- Workflow verifier with GitHub annotations:
  - `ok=false`, `operator_phase=provider_apply_workflow_blocked`.
  - `ready_to_apply=false`, `all_commands_succeeded=false`, `promotion_receipt_ok=false`.
  - `failure_count=5`, `results_command_failure_count=22`.
  - Annotation log contained 5 `::error title=DeSci provider apply workflow::...` lines.
- Secret-shape scan over generated workflow-annotation artifacts:
  - scanned=14, findings=0.
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8080 --frontend http://127.0.0.1:5194 --json-out var/desci-product-smoke-workflow-annotations-2026-07-04.json`
  - 5/5 passed.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5194 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-workflow-annotations-2026-07-04.json --trace-on-failure-dir var/traces/workflow-annotations-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-workflow-annotations-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The provider workflow gate is now machine-readable, human-readable, job-summary ready, and annotation-ready. Public promotion remains no-go until private provider values are applied and the post-apply promotion receipt verifies as go.
