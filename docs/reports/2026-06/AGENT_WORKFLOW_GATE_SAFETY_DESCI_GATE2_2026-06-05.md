# Agent Workflow Gate Runner - desci-launch-readiness

- Status: `pass`
- Execution mode: `execute`
- Will execute: `true`
- Allow side-effect gates: `false`
- Project: `apps/desci-platform`
- Smoke scope: `desci`
- Selected gates: `1`
- Passed gates: `0`
- Failed gates: `0`
- Skipped gates: `1`
- Planned gates: `0`
- Approval-required gates: `1`
- Elapsed seconds: `0.0`

## Gates

### Gate 2

- Status: `skipped`
- CWD: `.`
- Command: `"D:\AI project_push_8921d77\.venv\Scripts\python.exe" ops/scripts/dev_server_control.py start --target desci-frontend --wait-ready`
- Safety: `side_effecting`
- Safety reasons: `dev_server_start, wait_ready_process`
- Return code: `None`
- Elapsed seconds: `0.0`
- Skip reason: `side-effecting gate requires --allow-side-effect-gates (dev_server_start, wait_ready_process)`

## Errors

- none
