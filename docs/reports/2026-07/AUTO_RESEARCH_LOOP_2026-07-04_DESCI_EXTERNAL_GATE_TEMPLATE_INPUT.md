# AutoResearch Loop - DeSci External Gate Template Input

Date: 2026-07-04 KST

## Objective

Continue reducing the remaining DeSci launch operator gap. The previous loops generated provider-specific blank `.env` templates and a safe template index; this loop makes those templates directly usable as input to the external release gate after an operator fills them locally.

## External Signals

- Railway variables can be pasted through the service RAW Editor, which fits a provider-specific `.env` template workflow.
  Source: https://docs.railway.com/variables
- Vercel environment variables are environment-scoped and managed through the CLI/dashboard, so filled Vercel template values need to be reflected in a rerun before launch.
  Source: https://vercel.com/docs/cli/env
- GitHub CLI supports setting secrets at repository/environment scopes, so a filled GitHub template should be verified by the same external gate that checks `GITLEAKS_LICENSE`.
  Source: https://cli.github.com/manual/gh_secret_set

## A/B Decision

- Candidate A: Keep provider templates as standalone operator artifacts.
  - Rejected because the operator would still need to manually list each filled template when rerunning the gate.
- Candidate B: Add `--provider-template-dir` to `external_release_gate.py`.
  - Selected because the operator can fill the generated ignored templates and rerun one command that appends all provider `.env` files after the default env inputs.

## Implementation

- Added `DEFAULT_ENV_FILES`, `provider_template_env_files`, and `resolve_env_files` to `apps/desci-platform/scripts/external_release_gate.py`.
- Added `--provider-template-dir` to `external_release_gate.py`.
- Added tests proving:
  - provider template env files are appended after explicit/default env inputs,
  - filled `github.env` can satisfy the GitHub deploy readiness check,
  - a missing provider template directory fails with exit code `2`.

## Verification

Commands run from `apps/desci-platform`:

```powershell
python -m py_compile scripts/external_release_gate.py scripts/external_gate_handoff.py
python -m pytest backend/tests/test_external_release_gate.py backend/tests/test_external_gate_handoff.py -q
python scripts/external_release_gate.py --provider-timeout 12 --provider-template-dir var/external-gate-provider-templates-indexed-2026-07-04 --json-out var/external-release-gate-with-provider-template-dir-2026-07-04.json
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-provider-template-dir-2026-07-04.json --trace-on-failure-dir var/traces/provider-template-dir-2026-07-04
```

Command run from workspace root:

```powershell
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-template-dir-2026-07-04.json
```

Observed results:

- `py_compile`: pass.
- Focused pytest: `17 passed`.
- Real external gate with `--provider-template-dir`: expected no-go, with `deploy_failed=14`, `deploy_warnings=3`, `provider_ready=1/3`, `provider_failed_checks=4`.
- External gate evidence included all four provider template env files as sources: `amoy.env`, `github.env`, `railway.env`, `vercel.env`.
- Broader release pytest: `79 passed`.
- Browser launch-click suite: `9/9` passed.
- DeSci workspace smoke: `8/8` passed.

## Current Launch State

The product remains locally green but externally no-go because provider values are still blank or unauthenticated. The operator path is now shorter:

1. Generate provider templates and index from `external_gate_handoff.py`.
2. Fill the ignored provider templates locally or apply them in each provider.
3. Rerun `external_release_gate.py --provider-template-dir <filled-template-dir>`.
4. Regenerate the handoff and proceed only if the external gate flips to `ok=true`.
