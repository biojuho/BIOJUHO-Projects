# AutoResearch: GitHub Radar Pre-Push Gate

## Objective

Bind the expanded GitHub modernization radar to the local pre-push gate so
future source-map edits cannot bypass the manifest validator while only source
freshness tests run.

## A/B Contract

- Baseline: pre-push runs `tests/test_github_source_freshness.py` but not
  `tests/test_github_modernization_radar.py`.
- Variant: add `tests/test_github_modernization_radar.py` to
  `ops\hooks\pre-push` and to the completion contract's
  `pre_push_regression_gate` evidence.
- Primary KPI: hook-equivalent pytest coverage increases from `80` to `84`
  tests with no runtime probe regression.
- Guardrails: keep the hook deterministic and offline; source freshness unit
  tests use fake GitHub collectors, and live GitHub API checks remain explicit
  report-generation commands.
- Decision rule: adopt only if focused tests, pre-push-equivalent tests,
  runtime probes, and completion audit pass.

## Changed Paths

- `ops\hooks\pre-push`
- `ops\references\autoresearch_completion_contract.json`

## Verification

- Completion audit regenerated successfully with `18` criteria,
  `cycle_evidence_ready=true`, and `global_objective_complete=false`.
- Focused source/radar/audit tests:
  - `python -m pytest tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - `16 passed`
- Expanded pre-push-equivalent pytest suite:
  - `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - `84 passed`
- Hook installation:
  - `python ops\hooks\install_hooks.py`
  - installed `pre-push` to `D:\AI project\.git\hooks\pre-push`
- Hook-equivalent runtime probes passed:
  - dev-server MCP runtime smoke: `5` requests, `5` tools,
    `process_mutation_disabled`
  - MCP service runtime smoke: `3` checked, `3` passed, `39` tools
  - single workflow dry-run: selected `1`
  - side-effect safety execute: selected `1`, skipped `1`
  - all-workflow matrix dry-run: `6` workflows, selected `6`
  - completion audit: `18` criteria,
    `cycle_evidence_ready=true`, `global_objective_complete=false`
