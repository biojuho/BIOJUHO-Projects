# AutoResearch Loop: DeSci Provider Apply Recorder

Date: 2026-07-04

## Objective

Close the launch gap between a verified provider apply plan and a verified provider apply-results receipt. The prior verifier could prove a receipt after it existed, but the operator still had to manually create that receipt after running provider commands.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- Python `subprocess.run` supports captured stdout/stderr and command timeouts.
  - https://docs.python.org/3/library/subprocess.html
- GitHub Actions status can be controlled by process exit codes.
  - https://docs.github.com/actions/creating-actions/setting-exit-codes-for-actions
- GitHub CLI supports `gh secret set --env-file` and encrypts secret values before sending them.
  - https://cli.github.com/manual/gh_secret_set
- Vercel CLI documents `vercel env add` and stdin/file-based env value input.
  - https://vercel.com/docs/cli/env
- Railway CLI documents `railway variable` with `--stdin`.
  - https://docs.railway.com/cli/variable
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep a manual apply-results template plus verifier.
  - Rejected because it still leaves the launch operator manually translating command execution into JSON.
- Variant B: add a dry-run-by-default provider apply recorder with an explicit execution switch.
  - Adopted because it provides a safe receipt generator, records exit codes directly, captures redacted stdout/stderr, and fails closed until actual provider commands succeed.

## Implementation

- Added `--record-provider-apply-results-from-plan`.
- Added explicit `--execute-provider-apply-commands`; without it, recorder writes a dry-run receipt and exits non-zero.
- Added per-command timeout via `--provider-apply-command-timeout`.
- Added provider-specific safe invocations:
  - GitHub: `gh secret set --env-file <template>`.
  - Railway: `railway variable set KEY --stdin`, with values read from the private provider template and piped only through stdin.
  - Vercel: `vercel env add KEY production`, with values read from the private provider template and piped only through stdin.
- Added fail-closed behavior when the apply plan is not `ready_to_apply`.
- Added secret-shaped stdout/stderr redaction; any command output that looks like a secret makes the command result fail.
- Added recorder commands to generated provider apply plan JSON and Markdown.

## Evidence

- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --latest-observed-commit Veritas-7/autoresearch-skill-system=b8bbf393759d6e67e780f03c572ec626fab6593b --json-out var/github-modernization-radar-auto-research-2026-07-04-provider-apply-recorder.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_PROVIDER_APPLY_RECORDER.md`
  - Result: valid, 8 sources, adopted=8.
- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py -q` -> 32 passed.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 128 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 171 passed.
- Current handoff/apply plan regeneration:
  - `release_decision=no-go`, `ok=false`, `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`, `next_actions=12`.
- Recorder dry-run receipt:
  - `execution_mode=dry_run`, `command_count=22`, statuses `dry_run=22`, `ok=false`.
- Dry-run verifier:
  - `ok=false`, `all_commands_succeeded=false`, `expected=22`, `reported=22`, `command_failures=22`, `secret_marker_count=0`.
- Execute mode against current blank plan:
  - `execution_mode=execute`, `command_count=22`, statuses `blocked=22`, `ok=false`.
  - No provider CLI commands were run because the plan is not `ready_to_apply`.
- Secret-shape scan over 12 generated provider apply-recorder JSON/Markdown/env artifacts -> `findings=0`.
- Product smoke:
  - `python scripts/product_smoke.py --api http://127.0.0.1:8077 --frontend http://127.0.0.1:5191 --json-out var/desci-product-smoke-provider-apply-recorder-2026-07-04.json`
  - 5/5 passed; fixture remains `/ready status=blocked` and `/launch decision=no-go`.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5191 --expect-dev-auth --launch-click-suite --json-out var/desci-browser-smoke-provider-apply-recorder-2026-07-04.json --trace-on-failure-dir var/traces/provider-apply-recorder-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out apps/desci-platform/var/workspace-smoke-desci-provider-apply-recorder-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

The local launch automation now has a complete safe path from provider apply plan to redacted execution receipt:

- verify provider apply plan
- record provider apply results
- verify provider apply results
- run post-apply external gate and promotion receipt checks

Public launch is still no-go because the private provider templates remain blank and the current external gate still reports provider/deploy blockers. The next real-world step is to populate private templates outside git, regenerate the apply plan with `--preserve-provider-templates`, run the recorder with `--execute-provider-apply-commands`, and then verify the resulting receipt.
