# AutoResearch Loop - DeSci External Gate Handoff

Date: 2026-07-04 KST

## Objective

Continue the DeSci launch loop by making the external release gate output directly usable as an operator handoff. The prior loop produced `external_release_gate.py` and real provider/deploy evidence; this loop turns that evidence into a no-secret JSON/Markdown launch packet without modifying unrelated dirty files.

## External Signals

- GitHub Actions environments support deployment protection rules and custom protection rules, so a machine-readable gate result is an appropriate control point before production deployment.
  Source: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- Vercel environment variable changes only apply to new deployments, so the handoff must keep Vercel env actions tied to redeploy guidance.
  Source: https://vercel.com/docs/environment-variables/managing-environment-variables
- Railway service variables can be entered through the Variables tab or RAW Editor, so Railway env blockers should remain grouped by provider and env key.
  Source: https://docs.railway.com/variables

## A/B Decision

- Candidate A: Patch the workspace-level `ops/scripts/desci_launch_handoff_refresh.py` flow.
  - Rejected for this loop because that file and its test are existing untracked workspace files. Touching them would risk mixing this loop with unrelated local work.
- Candidate B: Add a DeSci-local `scripts/external_gate_handoff.py` that consumes `external_release_gate.py` JSON evidence.
  - Selected because it preserves the app boundary, stages only new owned files, and creates a reusable handoff artifact from the already verified external gate contract.

## Implementation

- Added `apps/desci-platform/scripts/external_gate_handoff.py`.
- Added `apps/desci-platform/backend/tests/test_external_gate_handoff.py`.
- The handoff builder:
  - validates external gate JSON schema and child evidence,
  - derives `go` / `no-go` and `external_launch_ready` / `external_launch_blocked`,
  - groups deploy readiness failures by owner/surface,
  - groups provider CLI/auth failures by provider,
  - emits provider rollups with existing Railway, Vercel, GitHub, and Amoy apply guidance,
  - writes JSON and Markdown evidence atomically.

## Verification

Commands run from `apps/desci-platform`:

```powershell
python -m py_compile scripts/external_gate_handoff.py scripts/external_release_gate.py
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py -q
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q
python scripts/external_gate_handoff.py --external-gate-json var/external-release-gate-provider-2026-07-04.json --json-out var/external-gate-handoff-2026-07-04.json --markdown-out var/external-gate-handoff-2026-07-04.md
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-external-gate-handoff-2026-07-04.json --trace-on-failure-dir var/traces/external-gate-handoff-2026-07-04
```

Expected gate-blocked CLI result was normalized for the shell because the current real external gate is still no-go.

Command run from workspace root:

```powershell
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-external-gate-handoff-rerun-2026-07-04.json
```

Observed results:

- `py_compile`: pass.
- Focused pytest: `11 passed`.
- Broader release pytest: `73 passed`.
- Browser launch-click suite: `9/9` passed.
- DeSci workspace smoke rerun: `8/8` passed.
- Real handoff generation:
  - `decision=no-go`
  - `ok=False`
  - `deploy_failed=14`
  - `deploy_warnings=3`
  - `provider_ready=1/3`
  - `provider_failed_checks=4`
  - `next_actions=12`
  - `failed_surfaces=deploy_readiness, provider_preflight`

Generated local evidence:

- `apps/desci-platform/var/external-gate-handoff-2026-07-04.json`
- `apps/desci-platform/var/external-gate-handoff-2026-07-04.md`
- `apps/desci-platform/var/desci-browser-smoke-external-gate-handoff-2026-07-04.json`
- `var/workspace-smoke-desci-external-gate-handoff-rerun-2026-07-04.json`

Note: the first workspace smoke attempt had one transient frontend unit-test failure in `DashboardLists.test.jsx`; the identical standalone frontend test command then passed (`201 passed`), and the full DeSci workspace smoke rerun passed `8/8`.

## Current Launch State

The local product/browser path remains ready from the previous loop, but external launch remains fail-closed. The next live blocker is operator/provider configuration: Railway runtime variables and auth, Vercel auth/environment variables, Amoy deployment inputs, and the GitHub Gitleaks license secret.
