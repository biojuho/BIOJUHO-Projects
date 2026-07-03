# AutoResearch Loop - DeSci Post-Apply Evidence

Date: 2026-07-04 KST

## Objective

Continue the DeSci launch hardening loop after provider operator status by making the post-apply verification step produce durable JSON evidence. The product path is locally green, but the external launch remains blocked until Railway, Vercel, GitHub, and Amoy values/auth are applied outside the repository and verified.

## External Signals

- GitHub Actions workflow artifacts are intended for build/test outputs, logs, screenshots, and other durable debugging/deployment evidence.
  Source: https://docs.github.com/en/actions/tutorials/store-and-share-data
- Railway CLI documents `railway variable set` and stdin-based variable input, which supports applying values without putting secrets into command arguments.
  Source: https://docs.railway.com/cli/variable
- Vercel CLI documents `vercel env pull`, `vercel pull`, and environment command flows for refreshing/checking cloud-side configuration.
  Source: https://vercel.com/docs/cli/env

## A/B Decision

- Candidate A: Keep provider post-apply verification as console-only `external_release_gate.py --target <provider>` commands.
  - Rejected because launch review still depends on ephemeral terminal output.
- Candidate B: Add JSON evidence paths to every provider post-apply command and add an aggregate completion evidence block.
  - Selected because the release reviewer can require `external_release_gate.ok=true` in a named JSON artifact before treating provider application as complete.

Decision rule: adopt only if generated apply plans expose aggregate and provider-specific JSON evidence paths, no secret-like strings are emitted, release tests pass, browser launch-click evidence stays green, and DeSci workspace smoke remains green.

## Implementation

- Updated `apps/desci-platform/scripts/external_gate_handoff.py`:
  - provider `post_apply_verify_commands` now include `--json-out var/external-release-gate-post-apply-<provider>.json`.
  - top-level `post_apply_completion_evidence` now records:
    - `success_condition=external_release_gate.ok=true`
    - `aggregate_json_out=var/external-release-gate-post-apply-all.json`
    - aggregate all-provider command
    - provider-specific JSON output paths
  - Markdown provider apply plans now render a `Post-Apply Evidence` section.
- Updated `apps/desci-platform/backend/tests/test_external_gate_handoff.py` to assert aggregate and provider-specific evidence commands without leaking populated template values.

## Verification

Commands run from `apps/desci-platform`:

```powershell
python -m py_compile scripts/external_gate_handoff.py
python -m pytest backend/tests/test_external_gate_handoff.py -q
python scripts/external_gate_handoff.py --external-gate-json var/external-release-gate-provider-2026-07-04.json --json-out var/external-gate-handoff-post-apply-evidence-2026-07-04.json --markdown-out var/external-gate-handoff-post-apply-evidence-2026-07-04.md --provider-template-dir var/external-gate-provider-post-apply-evidence-2026-07-04 --provider-template-index-out var/external-gate-provider-post-apply-evidence-index-2026-07-04.json --provider-apply-plan-out var/external-gate-provider-post-apply-evidence-2026-07-04.json --provider-apply-plan-markdown-out var/external-gate-provider-post-apply-evidence-2026-07-04.md
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-provider-post-apply-evidence-2026-07-04.json --trace-on-failure-dir var/traces/provider-post-apply-evidence-2026-07-04
```

Command run from workspace root:

```powershell
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-post-apply-evidence-2026-07-04.json
```

Observed results:

- `py_compile`: pass.
- Focused handoff pytest: `13 passed`.
- Generated apply plan includes:
  - aggregate command: `python scripts/external_release_gate.py --provider-template-dir var\external-gate-provider-post-apply-evidence-2026-07-04 --target all --json-out var/external-release-gate-post-apply-all.json`
  - provider JSON outputs for `amoy`, `github`, `railway`, and `vercel`.
- Secret-pattern scan of generated JSON/Markdown/index outputs: no matches.
- Broader release pytest: `83 passed`.
- Browser launch-click suite: `9/9` passed.
- DeSci workspace smoke: first run hit the tool timeout before completion; rerun with a longer timeout passed `8/8`.

## Current Launch State

Adopted. The provider apply plan now has a durable post-apply completion contract:

1. Fill provider templates privately.
2. Apply provider values using the redacted command templates.
3. Run the provider-specific or aggregate post-apply command.
4. Promote launch only when the generated external gate JSON proves `ok=true`.

External launch is still `no-go` until real provider credentials, deployment values, and provider auth are supplied outside the repo.
