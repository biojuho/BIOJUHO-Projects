# External Credential Live Verifier

- Status: `fail`
- Mode: `execute`
- Selected boundaries: `2`
- Ready boundaries: `2`
- Blocked boundaries: `0`
- Commands planned: `3`
- Commands executed: `3`

## Boundaries

| Boundary | Live status | Missing required env | Commands |
| --- | --- | ---: | ---: |
| `hosted_agent_runtime_credentials` | `ready_for_execution` | `0` | `2` |
| `github_source_refresh_rate_limit_token` | `ready_for_execution` | `0` | `1` |

## Commands

### hosted_agent_runtime_credentials

- Status: `pass`
- Command: `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`
- Return code: `0`

### hosted_agent_runtime_credentials

- Status: `pass`
- Command: `python ops/scripts/autoresearch_completion_audit.py`
- Return code: `0`

### github_source_refresh_rate_limit_token

- Status: `fail`
- Command: `python ops/scripts/github_source_freshness.py --json-out var/github-source-freshness-live.json --markdown-out var/github-source-freshness-live.md`
- Return code: `1`

## Errors

- github_source_refresh_rate_limit_token: python ops/scripts/github_source_freshness.py --json-out var/github-source-freshness-live.json --markdown-out var/github-source-freshness-live.md failed with 1
