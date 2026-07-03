# AutoResearch Loop - DeSci External Gate Provider Templates

Date: 2026-07-04 KST

## Objective

Continue the DeSci launch loop after adding the external gate handoff. The next operator gap was converting the no-go handoff into provider-specific, no-secret env templates that can be applied in Railway, Vercel, GitHub, and Amoy workflows.

## External Signals

- GitHub CLI `gh secret set` supports repository, environment, organization, and user secrets, so GitHub blockers should be isolated into a GitHub-specific template/action group.
  Source: https://cli.github.com/manual/gh_secret_set
- Vercel documents environment variables as environment-scoped deployment configuration, and the CLI supports env operations across environments.
  Source: https://vercel.com/docs/environment-variables
- Railway service variables can be pasted through the service Variables tab RAW Editor, so Railway launch blockers should be emitted as a single Railway `.env` template.
  Source: https://docs.railway.com/variables

## A/B Decision

- Candidate A: Add more prose to the Markdown handoff.
  - Rejected because prose still leaves the operator to manually copy scattered keys.
- Candidate B: Add `--provider-template-dir` to `external_gate_handoff.py`.
  - Selected because it produces directly usable, provider-scoped `.env` files while keeping all values blank.

## Implementation

- Extended `apps/desci-platform/scripts/external_gate_handoff.py` with:
  - `render_provider_env_template`
  - `write_provider_templates`
  - `--provider-template-dir`
- Extended `apps/desci-platform/backend/tests/test_external_gate_handoff.py` to verify:
  - provider templates are written atomically,
  - duplicated keys are emitted once,
  - provider-preflight-only failures do not create value templates,
  - secret-like values are not emitted.

## Verification

Commands run from `apps/desci-platform`:

```powershell
python -m py_compile scripts/external_gate_handoff.py
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py -q
python scripts/external_gate_handoff.py --external-gate-json var/external-release-gate-provider-2026-07-04.json --json-out var/external-gate-handoff-templates-2026-07-04.json --markdown-out var/external-gate-handoff-templates-2026-07-04.md --provider-template-dir var/external-gate-provider-templates-2026-07-04
$matches = Get-ChildItem -Path 'var/external-gate-provider-templates-2026-07-04' -Filter '*.env' | Select-String -Pattern '^[A-Z0-9_]+=.+'
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q
```

Command run from workspace root:

```powershell
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-external-gate-templates-2026-07-04.json
```

Observed results:

- `py_compile`: pass.
- Focused pytest: `12 passed`.
- Provider templates generated:
  - `amoy.env`
  - `github.env`
  - `railway.env`
  - `vercel.env`
- Non-comment `KEY=` value check: `provider_templates_have_no_values`.
- Broader release pytest: `74 passed`.
- DeSci workspace smoke: `8/8` passed.

## Current Launch State

The platform still fails closed for live external launch, but the external blockers are now converted into provider-specific no-secret templates. Remaining work is external/operator configuration: fill/apply provider secrets, authenticate Railway and Vercel CLIs, deploy Amoy contracts, then rerun `external_release_gate.py` and `external_gate_handoff.py`.
