# AutoResearch Loop: DeSci Provider Apply-Ready Verifier

Date: 2026-07-04

## Objective

Make the DeSci external-provider handoff closer to launch execution by adding a deterministic verifier for the redacted provider apply plan. The verifier must confirm that blank private templates are still safe but not ready, while filled private templates can be checked without leaking values.

## Scope and Owned Paths

- `scripts/external_gate_handoff.py`
- `backend/tests/test_external_gate_handoff.py`

## External Sources Checked

- GitHub CLI supports setting secrets from an env file and locally encrypts values before sending them.
  - https://cli.github.com/manual/gh_secret_set
- Vercel documents `vercel env` for managing project environment variables and stdin-based updates.
  - https://vercel.com/docs/cli/env
- Railway documents CLI token-based operation for CI and provider automation.
  - https://docs.railway.com/cli
- Railway documents variables as the deployment/runtime configuration surface.
  - https://docs.railway.com/variables
- Veritas-7 AutoResearch source observed this cycle:
  - `b8bbf393759d6e67e780f03c572ec626fab6593b`

## A/B Hypothesis

- Baseline A: keep the provider apply plan as a redacted JSON/Markdown document that humans inspect.
  - Rejected because the external launch path still needs an exit-code signal for "templates are filled and safe to apply".
- Variant B: add `--verify-provider-apply-plan` and `--require-ready-to-apply`.
  - Adopted because it separates plan integrity from readiness. Blank templates verify as a consistent handoff, while release automation can fail until every provider template is populated.

## Implementation

- `external_gate_handoff.py`
  - Added `verify_provider_apply_plan`.
  - Added CLI mode `--verify-provider-apply-plan`.
  - Added `--require-ready-to-apply` for CI/operator gating.
  - Added provider apply plan verification commands into the generated apply plan and Markdown.
  - Added `env_keys` to provider entries so verification can detect template key drift without exposing values.
  - Verifier checks schema, counts, operator status, safe-to-commit metadata, template file existence, template key/count drift, redacted command placeholders, and secret-shaped markers in the redacted plan JSON.

## Evidence

- Source/radar refresh:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-04-provider-apply.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_PROVIDER_APPLY.md` -> valid, 8 sources adopted.
  - `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` -> `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- `python -m py_compile scripts/external_gate_handoff.py` -> pass.
- `python -m pytest backend/tests/test_external_gate_handoff.py -q` -> 19 passed.
- `python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 113 passed.
- Generated current provider apply-ready evidence:
  - `var/external-gate-handoff-provider-apply-ready-2026-07-04.json`
  - `var/external-gate-handoff-provider-apply-ready-2026-07-04.md`
  - `var/external-gate-provider-apply-ready-index-2026-07-04.json`
  - `var/external-gate-provider-apply-ready-2026-07-04.json`
  - `var/external-gate-provider-apply-ready-2026-07-04.md`
- Current blank-template verifier:
  - `python scripts/external_gate_handoff.py --verify-provider-apply-plan var/external-gate-provider-apply-ready-2026-07-04.json --json-out var/external-gate-provider-apply-ready-2026-07-04-verify.json`
  - result: `ok=true`, `ready_to_apply=false`, `failure_count=0`, `provider_failure_count=0`.
- Current require-ready verifier:
  - `python scripts/external_gate_handoff.py --verify-provider-apply-plan var/external-gate-provider-apply-ready-2026-07-04.json --require-ready-to-apply --json-out var/external-gate-provider-apply-ready-2026-07-04-require-ready.json`
  - expected result: `ok=false`, `failure_count=1`, `provider_failure_count=4`, first failure `provider apply plan must be ready_to_apply`.
- Secret-shape scan over generated provider apply-ready artifacts returned no matches.
- Browser launch-click suite:
  - `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-provider-apply-ready-2026-07-04.json --trace-on-failure-dir var/traces/provider-apply-ready-2026-07-04`
  - 9/9 passed.
- Workspace DeSci smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-apply-ready-2026-07-04.json`
  - 8/8 passed.

## Current Launch Blocker

Local launch gates remain green, and the provider apply plan is internally consistent. Public promotion is still no-go because the private provider templates are intentionally blank and provider authentication has not been applied. The new machine-readable next gate is:

- `provider_apply_plan_verification.ok=true`
- `provider_apply_plan.ready_to_apply=true`

Only after that should the provider apply commands run, followed by the post-apply external gate, manifest verification, promotion receipt, and require-go receipt checks.
