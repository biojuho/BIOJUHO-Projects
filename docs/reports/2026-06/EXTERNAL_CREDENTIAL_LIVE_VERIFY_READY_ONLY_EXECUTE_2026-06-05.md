# External Credential Live Verifier

- Status: `pass`
- Mode: `execute`
- Selection: `ready_only`
- Selected boundaries: `1`
- Ready boundaries: `1`
- Blocked boundaries: `0`
- Commands planned: `2`
- Commands executed: `2`

## Boundaries

| Boundary | Live status | Missing required env | Commands |
| --- | --- | ---: | ---: |
| `hosted_agent_runtime_credentials` | `ready_for_execution` | `0` | `2` |

## Commands

### hosted_agent_runtime_credentials

- Status: `pass`
- Command: `python ops/scripts/agent_workflow_gate_runner.py --workflow workspace-quality-dashboard --max-gates 1`
- Return code: `0`

### hosted_agent_runtime_credentials

- Status: `pass`
- Command: `python ops/scripts/autoresearch_completion_audit.py`
- Return code: `0`

## Errors

- none
