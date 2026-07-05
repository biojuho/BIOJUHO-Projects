# AgriGuard No-Browser Smoke Command Preservation - 2026-07-05

## Source Check

- AutoResearch upstream checked: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Change

- Added an explicit `--no-browser-smoke` contract to `render_launch_operator_packet.py`.
- Threaded the browser-smoke intent from `launch_compose.py` into the operator packet renderer command.
- Threaded the same intent from `run_guarded_launch.py` into the packet refresh command.
- Updated generated safe rerun commands so:
  - guarded-wrapper reruns include `--no-browser-smoke` when the wrapper was launched with that mode;
  - compose reruns omit `--run-browser-smoke` when browser smoke was disabled.

## Verification

- `python -m pytest apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: `59 passed in 2.46s`
- Real guarded wrapper evidence command:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.env.template --output-dir var --output-prefix agriguard-guarded-launch-no-browser-refresh --emit-handoff --no-browser-smoke --status-json-out var\agriguard-guarded-launch-no-browser-refresh-status.json`
  - Result: exit `1`, expected fail-closed env-shape block from template placeholders before strict preflight.
- Structured artifact check across:
  - `var\agriguard-guarded-launch-no-browser-refresh-operator-packet.json`
  - `var\agriguard-guarded-launch-no-browser-refresh-readiness-summary.json`
  - `var\agriguard-guarded-launch-no-browser-refresh-artifact-index.json`
  - `var\agriguard-guarded-launch-no-browser-refresh-launch-report.json`
  - Result:
    - `global_run_browser_occurrences`: `0`
    - `global_no_browser_occurrences`: `9`
    - `packet_guarded_has_no_browser`: `true`
    - `packet_compose_has_run_browser`: `false`
    - `readiness_guarded_has_no_browser`: `true`
    - `readiness_compose_has_run_browser`: `false`
    - `artifact_index_guarded_has_no_browser`: `true`
    - `artifact_index_compose_has_run_browser`: `false`
    - `launch_report_run_browser_smoke`: `false`
    - `launch_report_operator_packet_has_no_browser`: `true`
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Result: `passed=5, failed=0, total=5`, elapsed `3m24s`
- `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Result: `passed=9, failed=0, total=9`, elapsed `2m47s`

## Remaining Blocker

- The no-browser command contract is fixed locally.
- The guarded launch remains blocked by operator-owned launch env values: the checked run used `var\agriguard-launch-operator.env.template`, so env validation correctly stopped at `env_shape_blocked` / `fix_env_shape_validation`.
