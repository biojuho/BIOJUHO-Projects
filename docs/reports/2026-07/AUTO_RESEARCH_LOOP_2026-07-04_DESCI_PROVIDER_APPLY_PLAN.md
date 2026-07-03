# AutoResearch Loop - DeSci Provider Apply Plan

Date: 2026-07-04 KST

## Objective

Continue the DeSci launch hardening loop by turning provider templates into a redacted apply plan. The previous loops generated blank templates, a no-secret index, and external-gate input wiring. This loop adds the operator-facing step between "templates are filled" and "external gate is rerun" without exposing secret values.

## External Signals

- GitHub CLI supports `gh secret set --env-file <file>`, which fits a GitHub-specific template apply command.
  Source: https://cli.github.com/manual/gh_secret_set
- Vercel CLI supports `vercel env add <name> <environment> < <file>`, and production/preview values are treated as sensitive by default.
  Source: https://vercel.com/docs/cli/env
- Railway CLI supports `railway variable set KEY --stdin`, which lets values be piped without placing them in command arguments.
  Source: https://docs.railway.com/cli/variable

## A/B Decision

- Candidate A: Keep only provider `.env` templates and tell operators to apply them manually.
  - Rejected because it leaves too much room for copying the wrong provider values or running the gate before every key is populated.
- Candidate B: Add a redacted provider apply plan plus a template-preservation option.
  - Selected because it keeps generated values out of the repo, avoids overwriting filled templates, and records command templates and post-apply verification commands.

## Implementation

- Extended `apps/desci-platform/scripts/external_gate_handoff.py` with:
  - `--preserve-provider-templates`
  - `--provider-apply-plan-out`
  - `--provider-apply-plan-markdown-out`
  - redacted apply command templates for GitHub, Railway, and Vercel
  - `ready_to_apply` / `blank_key_count` provider status
  - post-apply `external_release_gate.py --provider-template-dir ... --target ...` verify commands
- Extended `apps/desci-platform/backend/tests/test_external_gate_handoff.py` to verify:
  - existing filled templates can be preserved,
  - apply plans do not leak populated values,
  - blank templates are not marked ready,
  - fully populated templates are marked ready without exposing values.

## Verification

Commands run from `apps/desci-platform`:

```powershell
python -m py_compile scripts/external_gate_handoff.py
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py -q
python scripts/external_gate_handoff.py --external-gate-json var/external-release-gate-provider-2026-07-04.json --json-out var/external-gate-handoff-apply-plan-2026-07-04.json --markdown-out var/external-gate-handoff-apply-plan-2026-07-04.md --provider-template-dir var/external-gate-provider-apply-plan-2026-07-04 --provider-template-index-out var/external-gate-provider-apply-plan-index-2026-07-04.json --provider-apply-plan-out var/external-gate-provider-apply-plan-2026-07-04.json --provider-apply-plan-markdown-out var/external-gate-provider-apply-plan-2026-07-04.md
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-provider-apply-plan-2026-07-04.json --trace-on-failure-dir var/traces/provider-apply-plan-2026-07-04
```

Command run from workspace root:

```powershell
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-apply-plan-2026-07-04.json
```

Observed results:

- `py_compile`: pass.
- Focused pytest: `20 passed`.
- Apply plan generation: `ready_provider_count=0`, `provider_count=4`, expected because generated templates are still blank.
- Secret-pattern scan of apply plan/index outputs: no matches.
- Broader release pytest: `82 passed`.
- Browser launch-click suite: `9/9` passed.
- DeSci workspace smoke: `8/8` passed.

## Current Launch State

The product remains locally green and the external launch path is now more deterministic:

1. Generate provider templates, index, and apply plan.
2. Fill provider templates locally.
3. Regenerate apply plan with `--preserve-provider-templates`.
4. Apply provider commands from the redacted plan.
5. Rerun `external_release_gate.py --provider-template-dir <filled-template-dir>`.

External launch is still no-go until real provider credentials and deployment values are supplied.
