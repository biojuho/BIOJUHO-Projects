# AutoResearch Loop - DeSci Post-Apply Evidence Gate

Date: 2026-07-04 KST

## Objective

Continue the DeSci launch-hardening loop after adding post-apply JSON artifact paths. The next gap was that generated artifacts could exist without a deterministic promotion check. This cycle adds a fail-closed verifier so launch promotion requires a machine-readable gate result, not just the presence of JSON files.

## External Signals

- GitHub Actions artifacts persist build/test/debug outputs after a job completes, which supports storing release evidence as durable artifacts.
  Source: https://docs.github.com/en/actions/tutorials/store-and-share-data
- SLSA artifact guidance emphasizes that provenance/evidence only helps when it is actually inspected and verified.
  Source: https://slsa.dev/spec/v1.0/verifying-artifacts
- Vercel CLI docs describe pulling or refreshing project/environment state from the platform, which reinforces provider-side verification after env changes.
  Source: https://vercel.com/docs/cli/env

## A/B Decision

- Candidate A: Keep post-apply evidence as named JSON output files only.
  - Rejected because release promotion could still depend on humans reading raw external-gate JSON.
- Candidate B: Add a post-apply evidence gate and wire it into the provider apply plan.
  - Selected because promotion now requires `post_apply_evidence_gate.ok=true`, while current no-go evidence is rejected with explicit reasons.

Decision rule: adopt only if the new verifier accepts a fully green external-gate JSON, rejects incomplete/no-go evidence, rejects secret-shaped evidence, generated apply plans include the promotion gate command, browser launch-click evidence stays green, and DeSci workspace smoke remains green.

## Implementation

- Added `apps/desci-platform/scripts/post_apply_evidence_gate.py`.
  - Validates `schema_version=1`.
  - Requires top-level `ok=true`.
  - Requires empty `failed_surfaces`.
  - Requires `deploy_failed=0`, `provider_failed_checks=0`, `failed_surface_count=0`.
  - Requires `provider_ready == provider_count` and `provider_count > 0`.
  - Requires `deploy_readiness.ok=true` and `provider_preflight.ok=true`.
  - Fails if secret-shaped markers appear in the input evidence.
  - Emits a small JSON report without copying raw provider evidence.
- Updated `apps/desci-platform/scripts/external_gate_handoff.py`.
  - `post_apply_completion_evidence.success_condition` is now `post_apply_evidence_gate.ok=true`.
  - Adds `promotion_gate_json_out=var/post-apply-evidence-gate.json`.
  - Adds `promotion_gate_command=python scripts/post_apply_evidence_gate.py --external-gate-json var/external-release-gate-post-apply-all.json --json-out var/post-apply-evidence-gate.json`.
  - Renders the promotion gate in Markdown.
- Added tests in `apps/desci-platform/backend/tests/test_post_apply_evidence_gate.py`.
- Extended `apps/desci-platform/backend/tests/test_external_gate_handoff.py` to assert the promotion gate contract.

## Verification

Commands run from `apps/desci-platform`:

```powershell
python -m py_compile scripts/external_gate_handoff.py scripts/post_apply_evidence_gate.py
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py -q
python scripts/external_gate_handoff.py --external-gate-json var/external-release-gate-provider-2026-07-04.json --json-out var/external-gate-handoff-post-apply-gate-2026-07-04.json --markdown-out var/external-gate-handoff-post-apply-gate-2026-07-04.md --provider-template-dir var/external-gate-provider-post-apply-gate-2026-07-04 --provider-template-index-out var/external-gate-provider-post-apply-gate-index-2026-07-04.json --provider-apply-plan-out var/external-gate-provider-post-apply-gate-2026-07-04.json --provider-apply-plan-markdown-out var/external-gate-provider-post-apply-gate-2026-07-04.md
python scripts/post_apply_evidence_gate.py --external-gate-json var/external-release-gate-provider-2026-07-04.json --json-out var/post-apply-evidence-gate-current-nogo-2026-07-04.json
python -m pytest backend/tests/test_external_gate_handoff.py backend/tests/test_post_apply_evidence_gate.py backend/tests/test_external_release_gate.py backend/tests/test_provider_preflight.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 45 --json-out var/desci-browser-smoke-post-apply-evidence-gate-2026-07-04.json --trace-on-failure-dir var/traces/post-apply-evidence-gate-2026-07-04
```

Command run from workspace root:

```powershell
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-post-apply-evidence-gate-2026-07-04.json
```

Observed results:

- `py_compile`: pass.
- Focused verifier/handoff pytest: `18 passed`.
- Generated apply plan contains `success_condition=post_apply_evidence_gate.ok=true`.
- Generated Markdown contains the promotion gate command and `var/post-apply-evidence-gate.json`.
- Running the new gate on the current no-go external evidence fails closed with 8 failures and `secret_marker_count=0`.
- Secret-pattern scan of generated apply plan/index/gate outputs: no matches.
- Broader release pytest: `88 passed`.
- Browser launch-click suite: `9/9` passed.
- DeSci workspace smoke: `8/8` passed.

## Current Launch State

Adopted. The post-apply release path now has three machine-readable layers:

1. `external_release_gate.py` writes aggregate provider/deploy evidence.
2. `post_apply_evidence_gate.py` validates that aggregate evidence is actually promotable.
3. Launch promotion requires `post_apply_evidence_gate.ok=true`.

External launch remains `no-go` until real provider credentials, deployment values, and provider auth are supplied outside the repo and the promotion gate passes on fresh post-apply evidence.
