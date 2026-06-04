# AutoResearch: GitHub Source Freshness

## Objective

Turn the GitHub modernization radar from a static source map into a live
freshness check for every related project currently tracked by the launch
hardening loop.

## Sources Checked

- GitHub REST repositories API:
  `https://docs.github.com/en/rest/repos`
- Current local radar manifest:
  `ops/references/github_modernization_sources.json`

## A/B Contract

- Baseline: `github_modernization_radar.py` validated static GitHub source
  URLs and local evidence paths, but did not confirm that the repositories
  still resolve or record current upstream metadata.
- Variant: add `ops/scripts/github_source_freshness.py`, a read-only GitHub
  REST snapshot that checks every radar repository and records default branch,
  pushed/updated timestamps, archive/disabled state, visibility, license,
  stars, forks, and open issue count.
- Primary KPI: live source freshness returns `source_count=13`, `passed=13`,
  and `failed=0`.
- Guardrails: no network access is required for unit tests; the script uses
  unauthenticated public API calls by default and supports `GITHUB_TOKEN` only
  for higher rate limits; completion audit still keeps the global objective
  open.
- Decision rule: adopt only if focused tests pass, the live snapshot succeeds
  for all sources, and the completion contract requires the snapshot evidence.

## Adopted Variant

Adopted. The radar now has live freshness evidence for all tracked GitHub
projects without moving that network dependency into the deterministic smoke
runner.

## Runtime Evidence

Command:

```powershell
python ops\scripts\github_source_freshness.py --json-out docs\reports\2026-06\GITHUB_SOURCE_FRESHNESS_2026-06-05.json --markdown-out docs\reports\2026-06\GITHUB_SOURCE_FRESHNESS_2026-06-05.md --timeout 30
```

Result:

- `13` sources
- `13` passed
- `0` failed
- GitHub API version `2022-11-28`
- newest upstream `pushed_at`: `2026-06-04T16:56:53Z`

## Verification

- `python -m pytest tests\test_github_source_freshness.py -q`
  - `4 passed`
- `python -m py_compile ops\scripts\github_source_freshness.py`
  - passed
- `python -m pytest tests/test_workspace_smoke.py tests/test_autoresearch_completion_audit.py tests/test_mcp_service_runtime_smoke.py tests/test_mcp_otel_collector_handoff.py tests/test_agent_workflow_gate_runner.py tests/test_github_source_freshness.py tests/test_dev_server_browser_smoke.py tests/test_dev_server_mcp_contract.py tests/test_dev_server_mcp_runtime.py tests/test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `78 passed`
- `python ops\hooks\install_hooks.py`
  - installed `pre-push` to `D:\AI project\.git\hooks\pre-push`
- `git push --dry-run origin HEAD:feat/observability-gateway-2026-05`
  - installed hook ran `78 passed`
  - runtime probes and completion audit passed
  - remote reported `Everything up-to-date`
- Completion contract now includes required
  `github_source_freshness_snapshot` evidence.
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_GITHUB_SOURCE_FRESHNESS_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_GITHUB_SOURCE_FRESHNESS_2026-06-05.md`
  - `17` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`

## Decision

The variant is adopted as supplemental live research evidence. It improves the
external-source freshness loop while keeping product smoke and pre-push gates
deterministic.
