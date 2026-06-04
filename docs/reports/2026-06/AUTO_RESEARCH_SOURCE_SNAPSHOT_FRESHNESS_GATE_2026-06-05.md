# AutoResearch Source Snapshot Freshness Gate - 2026-06-05

## Decision

Adopted a JSON timestamp freshness gate for external-source evidence.

- A: Keep GitHub source freshness evidence as file-exists plus term checks only.
  - Rejected: an old `GITHUB_SOURCE_FRESHNESS_2026-06-05.json` file could keep satisfying the completion audit even after the external-source scan is no longer current.
- B: Add a generic `json_freshness` evidence validator to the completion audit.
  - Adopted: the audit now parses configured JSON evidence, requires `status=pass`, validates the `generated_at` timestamp, rejects future timestamps, and fails if the snapshot is older than the configured window.

## Implementation

- `ops/scripts/autoresearch_completion_audit.py`
  - Added optional `json_freshness` evidence validation.
  - Checks `timestamp_field`, `max_age_hours`, `status_field`, and `required_status`.
  - Normalizes evidence summaries with `json_freshness=true` when the gate is configured.
- `ops/references/autoresearch_completion_contract.json`
  - Added required criterion `github_source_snapshot_recency_gate`.
  - Applies `json_freshness` to the expanded `17`-source `docs/reports/2026-06/GITHUB_SOURCE_FRESHNESS_2026-06-05.json`.
  - Requires `status=pass` and `generated_at` no older than `72 hours`.

## Verification

- Focused completion-audit tests:
  - `python -m pytest tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - Result: `11 passed`
- Focused source/radar/audit suite:
  - `python -m pytest tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_autoresearch_completion_audit.py -q -p no:cacheprovider`
  - Result: `19 passed`
- Pre-push-equivalent suite:
  - `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q -p no:cacheprovider`
  - Result: `87 passed`
- Script compile:
  - `python -m py_compile ops\scripts\autoresearch_completion_audit.py`
  - Result: passed
- Runtime probes:
  - `python ops/scripts/dev_server_mcp_runtime_smoke.py`
    - Result: `5` requests, `5` tools, mutation disabled
  - `python ops/scripts/mcp_service_runtime_smoke.py`
    - Result: `3` services checked, `3` passed, `39` tools
  - `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`
    - Result: selected `1` gate
  - `python ops/scripts/agent_workflow_gate_runner.py --workflow desci-launch-readiness --execute --gate-index 2`
    - Result: selected `1`, skipped `1`
  - `python ops/scripts/agent_workflow_gate_runner.py --all-workflows --max-gates 1`
    - Result: `6` workflows, selected `6` gates
- Completion audit:
  - `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SOURCE_SNAPSHOT_FRESHNESS_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SOURCE_SNAPSHOT_FRESHNESS_2026-06-05.md`
  - Result: `19 criteria`, `cycle_evidence_ready=true`, `global_objective_complete=false`

## Evidence Boundary

This gate does not call GitHub during the completion audit. Live source refresh remains owned by `ops/scripts/github_source_freshness.py`; the completion audit now prevents a stale live snapshot artifact from being reused indefinitely.
