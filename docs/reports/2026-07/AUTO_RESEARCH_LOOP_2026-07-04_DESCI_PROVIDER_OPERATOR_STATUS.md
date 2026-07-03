# AutoResearch Loop - DeSci Provider Operator Status

Date: 2026-07-04 KST

## Objective

Continue DeSci launch hardening after the provider apply-plan loop by making the operator's next state machine-readable. The product still cannot be externally launched without provider secrets and auth, so this cycle improves the no-secret handoff between generated provider templates, private value filling, provider application, and the final external gate rerun.

## External Signals

- Veritas AutoResearch source observed on `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`. Local adoption: bounded A/B loop, durable evidence, fail-closed completion marker.
- GitHub Actions environments require protection rules before jobs can proceed or access environment secrets.
  Source: https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment
- Vercel CLI documents `vercel env pull` for refreshing local env/project settings after provider-side changes.
  Source: https://vercel.com/docs/cli/env
- OpenSSF Scorecard remains a relevant launch-security comparator for CI/repository security posture.
  Source: https://github.com/ossf/scorecard-action

## A/B Decision

- Candidate A: Keep provider apply plans as provider counts plus per-provider commands.
  - Rejected because operators still need to infer whether the current artifact means "fill templates", "apply values", or "rerun the external gate".
- Candidate B: Add a top-level `operator_status` object and Markdown section.
  - Selected because it turns the handoff into an explicit fail-closed state machine without storing any provider secret values.

Decision rule: adopt only if redacted generated artifacts include a deterministic operator stage and completion marker, no secret-like strings are emitted, focused release tests pass, browser click evidence stays green, and DeSci workspace smoke remains green.

## Implementation

- Added `operator_status` to `apps/desci-platform/scripts/external_gate_handoff.py` provider apply plans:
  - `stage`
  - `ready_to_apply`
  - `ready_provider_count`
  - `blocked_provider_count`
  - `provider_templates_safe_to_commit`
  - `apply_plan_safe_to_commit`
  - `private_template_values_present`
  - `completion_marker`
  - `next_required_action`
- Added an `Operator Status` section to the provider apply-plan Markdown.
- Extended `apps/desci-platform/backend/tests/test_external_gate_handoff.py` so blank templates assert `stage=fill_provider_templates`, and privately populated templates assert `stage=apply_provider_values`.

## Verification

Commands run from `apps/desci-platform`:

```powershell
python -m py_compile scripts/external_gate_handoff.py
python -m pytest backend/tests/test_external_gate_handoff.py -q
python scripts/external_gate_handoff.py --external-gate-json var/external-release-gate-provider-2026-07-04.json --json-out var/external-gate-handoff-operator-status-2026-07-04.json --markdown-out var/external-gate-handoff-operator-status-2026-07-04.md --provider-template-dir var/external-gate-provider-operator-status-2026-07-04 --provider-template-index-out var/external-gate-provider-operator-status-index-2026-07-04.json --provider-apply-plan-out var/external-gate-provider-operator-status-2026-07-04.json --provider-apply-plan-markdown-out var/external-gate-provider-operator-status-2026-07-04.md
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-provider-operator-status-2026-07-04.json --trace-on-failure-dir var/traces/provider-operator-status-2026-07-04
```

Command run from workspace root:

```powershell
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-provider-operator-status-2026-07-04.json
```

Observed results:

- `py_compile`: pass.
- Focused handoff pytest: `13 passed`.
- Generated apply plan operator status: `stage=fill_provider_templates`, `ready_to_apply=false`, `ready_provider_count=0`, `blocked_provider_count=4`, `completion_marker=external_release_gate.ok=true`.
- Secret-pattern scan of generated JSON/Markdown/index outputs: no matches.
- Broader release pytest: `83 passed`.
- Browser launch-click suite: `9/9` passed.
- DeSci workspace smoke: `8/8` passed.

## Current Launch State

Adopted. The provider apply plan is now a redacted state machine:

1. `fill_provider_templates`: blank provider templates are safe to commit but not ready to apply.
2. `apply_provider_values`: private filled templates are not safe to commit, but the redacted apply plan stays safe and can guide provider writes.
3. `external_release_gate.ok=true`: completion marker after real provider values/auth are applied and the external gate is rerun.

External launch remains no-go until Railway, Vercel, GitHub, and Amoy values/auth are supplied outside the repo and the external gate passes against those real provider states.
