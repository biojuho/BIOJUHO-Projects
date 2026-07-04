# AutoResearch Loop - DeSci GitHub Output Verifier - 2026-07-04

## Objective

Validate generated provider apply workflow GitHub-output files against the workflow JSON before downstream CI consumers rely on those values.

## Scope and Owned Paths

- `apps/desci-platform/scripts/external_gate_handoff.py`
- `apps/desci-platform/backend/tests/test_external_gate_handoff.py`
- `apps/desci-platform/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_DESCI_GITHUB_OUTPUT_VERIFIER.md`

## Source Evidence

- Railway and Vercel provider operations remain blocked by authenticated project context, so the CI-facing no-go outputs must stay exact and machine-checkable.
  - https://docs.railway.com/cli
  - https://docs.railway.com/cli/link
  - https://vercel.com/docs/cli
  - https://vercel.com/docs/cli/project-linking
- Local workflow evidence now emits both full next-action JSON and primary-blocker GitHub outputs.

## Baseline

- `append_github_output()` wrote scalar and multiline output values.
- Tests covered writing multiline output.
- No parser or verifier existed to compare a generated GitHub-output file back to the workflow payload.

## A/B Decision

- Baseline A: trust that `append_github_output()` and `provider_apply_workflow_github_outputs()` remain aligned.
  - Rejected because downstream CI consumers need a direct way to prove the output file matches the source workflow JSON.
- Variant B: add a GitHub-output parser plus a verifier that compares every expected workflow output and scans for secret-shaped markers.
  - Adopted because it gives CI and tests a closed-loop validation surface.

## Implementation

- Added `parse_github_output()` for GitHub `name=value` and `name<<delimiter` multiline syntax.
- Added `verify_provider_apply_workflow_github_output()` to compare parsed output values to `provider_apply_workflow_github_outputs(payload)`.
- The verifier reports expected, parsed, checked, mismatched, failure, and secret-marker counts.
- Added tests for multiline parsing, successful output verification, and mismatch detection.

## Verification

- `python -m py_compile apps\desci-platform\scripts\external_gate_handoff.py`
  - Result: pass
- `python -m pytest apps\desci-platform\backend\tests\test_external_gate_handoff.py -q`
  - Result: `57 passed`
- `python -m pytest apps\desci-platform\backend\tests\test_provider_preflight.py apps\desci-platform\backend\tests\test_external_release_gate.py apps\desci-platform\backend\tests\test_external_gate_handoff.py apps\desci-platform\backend\tests\test_post_apply_evidence_gate.py -q`
  - Result: `112 passed`
- `python -c "import json, sys; sys.path.insert(0, 'scripts'); import external_gate_handoff as h; payload=json.load(open(r'var\provider-apply-workflow-primary-blocker-2026-07-04.json', encoding='utf-8')); result=h.verify_provider_apply_workflow_github_output(r'var\provider-apply-workflow-primary-blocker-github-output-2026-07-04.txt', payload); print(json.dumps(result['summary'], indent=2)); sys.exit(0 if result['ok'] else 1)"`
  - Result: `failure_count=0`, expected outputs `22`, parsed outputs `22`, checked outputs `22`, mismatched outputs `0`, secret markers `0`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-github-output-verifier-2026-07-04.json`
  - Result: `passed=8`, `failed=0`, `total=8`, no expected or unexpected external failures.

## Current Launch Boundary

Public launch remains externally blocked:

- Deploy readiness still has unresolved production secrets/configuration.
- Railway auth context is missing.
- Railway project context is missing for `railway status`.
- Vercel auth context is missing.
- Vercel project context is missing.
- GitHub provider CLI preflight is OK, but deploy readiness still requires repository secret configuration.

The CI output file can now be parsed and verified against the workflow JSON without trusting Markdown or manual inspection.

## Next Cycle

Continue hardening release automation by deciding whether this GitHub-output verifier should become a CLI mode or remain a library-level check used by tests and scripts.
