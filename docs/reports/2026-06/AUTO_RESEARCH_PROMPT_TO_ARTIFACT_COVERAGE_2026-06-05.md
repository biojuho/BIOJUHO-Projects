# AutoResearch Prompt-to-Artifact Coverage

## Decision

Adopted an explicit prompt-to-artifact coverage audit for the original Korean
launch objective. The existing completion audit proves many gates, but this
slice makes the user prompt itself auditable as requirements, mapped completion
criteria, evidence paths, continuous work, and external blockers.

## A/B Result

- Baseline: completion criteria existed, but the prompt-level requirements were
  only implicit in `autoresearch_completion_contract.json`.
- Variant: `ops/references/autoresearch_objective_requirements.json` records the
  original prompt and maps each explicit requirement to completion criteria and
  evidence. `ops/scripts/autoresearch_objective_coverage.py` validates the
  manifest, evidence terms, unknown criterion IDs, and blocked external
  requirements.
- Decision: adopted. The variant improves completion rigor and reduces the risk
  of claiming launch completion from proxy green gates.

## Current Coverage

- `7 requirements`
- `cycle_prompt_covered=true`
- `global_objective_complete=false`
- Korean prompt text and `prompt_terms` are preserved as readable UTF-8 in
  `ops/references/autoresearch_objective_requirements.json`.
- `ops/scripts/autoresearch_objective_coverage.py` rejects known mojibake
  markers so prompt-to-artifact evidence cannot silently degrade into
  unreadable text.
- Continuous requirements remain explicit:
  - GitHub-related project research
  - A/B adoption/commit/push loop until explicit stop
- Blocked external requirement remains explicit:
  - external credential and runtime boundaries

## Generated Evidence

- `ops/references/autoresearch_objective_requirements.json`
- `ops/scripts/autoresearch_objective_coverage.py`
- `tests/test_autoresearch_objective_coverage.py`
- `docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json`
- `docs/reports/2026-06/AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`

## Verification

- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - valid `7` requirements
  - `cycle_prompt_covered=true`
  - `global_objective_complete=false`
- `python -m pytest tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  - `16 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `109 passed`
- `git -c core.hooksPath=ops/hooks push --dry-run origin HEAD:feat/observability-gateway-2026-05`
  - `116 passed` plus runtime probes
- `python -m py_compile ops\scripts\autoresearch_objective_coverage.py ops\scripts\autoresearch_completion_audit.py`
  - passed
- `python -m pytest tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `17 passed`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_OBJECTIVE_COVERAGE_2026-06-05.md`
  - valid `25` criteria
  - `global_objective_complete=false`

## Remaining Blocker

The objective is intentionally not globally complete. The user requested
continuous improvement until explicit stop, and real external credentials or
runtime decisions remain outside local control.
