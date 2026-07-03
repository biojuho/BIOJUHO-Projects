# AutoResearch Loop: DeSci Provider Apply Results Verifier

Date: 2026-07-04

## Objective

Close the next DeSci launch gap after the provider apply-ready verifier: once private provider values are applied, operators and CI need a machine-readable, redacted proof that every provider apply command actually succeeded.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `scripts/post_apply_evidence_gate.py`
- `scripts/browser_smoke.py`
- `backend/tests/test_external_gate_handoff.py`
- `backend/tests/test_post_apply_evidence_gate.py`
- `backend/tests/test_browser_smoke.py`

## External Sources Checked

- GitHub Actions fail when an action exits with a non-zero code.
  - https://docs.github.com/actions/creating-actions/setting-exit-codes-for-actions
- GitHub CLI supports `gh secret set` and env-file input for repository secrets.
  - https://cli.github.com/manual/gh_secret_set
- Vercel documents environment variables and the `vercel env` CLI surface.
  - https://vercel.com/docs/environment-variables
  - https://vercel.com/docs/cli/env
- Railway documents CLI operation and runtime variables.
  - https://docs.railway.com/cli
  - https://docs.railway.com/variables
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: stop at the provider apply plan and apply-ready verifier.
  - Rejected because it proves the operator has the right commands, but not that those commands ran and exited successfully.
- Variant B: add a redacted provider apply-results template and verifier.
  - Adopted because it lets private apply execution remain outside git while producing a safe JSON receipt that CI can fail on until all command results are `status=success` and `exit_code=0`.

## Implementation

- `external_gate_handoff.py`
  - Added `provider_apply_results_verification` metadata to generated provider apply plans and Markdown.
  - Added `--provider-apply-results-template-from-plan`.
  - Added `--verify-provider-apply-results --provider-apply-plan`.
  - Added verifier checks for schema, plan path, expected command coverage, duplicate/unknown commands, non-success status, non-zero exit code, missing commands, and secret-shaped stdout/stderr excerpts.
  - Accepted PowerShell UTF-8 BOM result files and Windows/path-separator drift between generated templates and CLI arguments.
- `post_apply_evidence_gate.py`
  - Tightened generic private assignment detection so empty env templates and comment labels do not produce false secret findings, while populated same-line assignments still fail closed.
- `browser_smoke.py`
  - Made `dashboard-quick-upload-click` install the same dashboard shell, `/ready`, and `/launch` mocks used by readiness checks so the launch click suite can run against the fixture API without CORS noise.

## Evidence

- `python -m py_compile scripts/external_gate_handoff.py scripts/post_apply_evidence_gate.py scripts/browser_smoke.py` -> pass.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py -q` -> 95 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 165 passed.
- Current handoff/apply plan regeneration:
  - `decision=no-go`, `ok=false`, `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`, `next_actions=12`.
  - Wrote `var/external-gate-handoff-provider-apply-results-2026-07-04.json`.
  - Wrote `var/external-gate-provider-apply-results-2026-07-04.json`.
- Pending template verification:
  - `provider_apply_results_ok=False`
  - `all_commands_succeeded=False`
  - `expected=22`, `reported=22`, `command_failures=22`, `failures=0`, `secret_markers=0`.
- Redacted success fixture verification:
  - `provider_apply_results_ok=True`
  - `all_commands_succeeded=True`
  - `expected=22`, `reported=22`, `command_failures=0`, `failures=0`, `secret_markers=0`.
- Secret-shape scan over 13 generated provider apply-results JSON/Markdown/env artifacts -> `findings=0`.
- Product smoke against local launch fixture:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8077 --frontend http://127.0.0.1:5191 --json-out var/desci-product-smoke-provider-apply-results-2026-07-04.json`
  - 5/5 passed; fixture still reports `/ready status=blocked` and `/launch decision=no-go`.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5191 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-apply-results-2026-07-04.json --trace-on-failure-dir var/traces/provider-apply-results-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-apply-results-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

Local product, browser, workspace, and verifier gates are green. Public promotion remains no-go because private provider values have not been applied to GitHub, Railway, Vercel, and Amoy, and the current external gate still reports provider/deploy blockers.

The new machine-readable next gate is:

- `provider_apply_results_verification.ok=true`
- `provider_apply_results.all_commands_succeeded=true`

After that passes on real provider execution receipts, run the post-apply external gate, evidence manifest verification, promotion receipt verification, and require-go receipt check.
