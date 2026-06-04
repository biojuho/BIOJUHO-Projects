# AutoResearch Var Artifact Gitignore Hygiene - 2026-06-05

## Decision

Adopted local-only ignore patterns for transient AutoResearch and browser-smoke
artifacts under `var/`.

- A: Keep the existing ignore rules, which only ignored root-level
  `var/*.json`, `var/*.sarif`, and `var/*.txt` diagnostics.
  - Rejected: repeated product-click and runtime-smoke cycles left `33`
    untracked `var/` artifacts in the worktree, including screenshots,
    markdown probe notes, PID files, and `var/dev-servers/*.json`.
- B: Extend `.gitignore` for local AutoResearch/browser evidence types while
  keeping durable proof in `docs/reports/2026-06/`.
  - Adopted: `var/**/*.json`, `var/**/*.md`, `var/**/*.png`,
    `var/**/*.pid`, `var/*.out`, `var/*.err`, `var/**/*.out`,
    `var/**/*.err`, and `var/dev-servers/` are ignored.

## Verification

- Baseline untracked local `var/` artifacts:
  - `git ls-files --others --exclude-standard var`
  - Result: `33`
- Variant untracked local `var/` artifacts:
  - `git ls-files --others --exclude-standard var`
  - Result: `0`
- Ignore behavior:
  - `git check-ignore -v var\dashboard-click-refresh-2026-06-04.png var\dev-server-mcp-runtime-smoke-policy-tool-2026-06-05.md var\canva-mcp-openapi-server-2026-06-04.pid var\dev-servers\dashboard-api.json`
  - Result: all four paths matched the new `.gitignore` rules.
- Background smoke stdout/stderr behavior:
  - `git check-ignore -v var\workspace-smoke-all-current-tip-2026-06-05.out var\workspace-smoke-all-current-tip-2026-06-05.err`
  - Result: both paths matched the new `.gitignore` rules.
- Regression test:
  - `python -m pytest tests\test_workspace_smoke.py -q -p no:cacheprovider`
  - Result: `29 passed`
- Pre-push-equivalent pytest suite:
  - `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_external_credential_boundary_audit.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - Result: `93 passed`
- Hook-equivalent runtime probes:
  - dev-server MCP runtime smoke: `5` requests, `5` tools, mutation disabled
  - MCP service runtime smoke: `3` services checked, `3` passed, `39` tools
  - single workflow dry-run: selected `1`
  - side-effect safety execute: selected `1`, skipped `1`
  - all-workflow matrix dry-run: `6` workflows, selected `6`
- Completion audit:
  - Result: `22` criteria, `cycle_evidence_ready=true`, `global_objective_complete=false`

## Boundary

This does not hide repo-owned evidence. Reports, JSON summaries, and completion
audit artifacts that matter for launch readiness remain versioned under
`docs/reports/2026-06/`; `var/` remains the local scratch area for screenshots,
runtime probes, PID files, and transient dev-server state.
