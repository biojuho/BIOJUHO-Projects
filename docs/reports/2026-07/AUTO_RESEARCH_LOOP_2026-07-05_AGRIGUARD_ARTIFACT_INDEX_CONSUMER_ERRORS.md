# AutoResearch Loop: AgriGuard Artifact Index Consumer Errors

Date: 2026-07-05

## Objective

Make guarded-launch artifact-index Markdown expose handoff consumer errors. After semantic consistency checks were added to the compact consumer, a failing JSON index carried `consumer_errors`, but the operator-facing Markdown did not show the reason.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUATION_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: machine-readable gates and human-readable operator artifacts must surface the same failure reason.

## A/B Contract

- Baseline: `index_guarded_launch_artifacts.py` failed the JSON index when `consumer_errors` was non-empty, but the Markdown summary omitted those errors.
- Variant: render a `Consumer errors` line in artifact-index Markdown, using `-` for clean blocked/ready evidence.
- Primary KPI: a consumer semantic-drift error appears in the Markdown artifact and still drives index recovery status.
- Guardrails: clean missing-Firebase evidence renders `Consumer errors: -`; workspace smoke and browser suite pass.
- Decision: adopt. Operators can now see the exact compact-consumer error from the Markdown index.

## Changed Paths

- `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
- `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q` - `8 passed`.
- `python apps/AgriGuard/scripts/index_guarded_launch_artifacts.py --app-root apps/AgriGuard --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var\agriguard-handoff-semantic-proof --output-prefix handoff-semantic-proof --status-json var\agriguard-handoff-semantic-proof\handoff-semantic-proof-status.json --json-out var\agriguard-handoff-semantic-proof\handoff-semantic-proof-artifact-index-consumer-errors-line.json --markdown-out var\agriguard-handoff-semantic-proof\handoff-semantic-proof-artifact-index-consumer-errors-line.md --exit-zero-on-fail` - `status=pass`, `consumer_errors=[]`.
- `Select-String -Path var\agriguard-handoff-semantic-proof\handoff-semantic-proof-artifact-index-consumer-errors-line.md -Pattern "Consumer errors"` - line `Consumer errors: -`.
- `python -m pytest apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q` - `29 passed`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-index-consumer-errors.md-line.json` - `passed=5`, `failed=0`.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-artifact-index-consumer-errors-line.json --output-dir var\agriguard-browser-smoke-suite-artifact-index-consumer-errors-line --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. The local operator Markdown now mirrors compact-consumer errors instead of hiding semantic-drift reasons.

## Next Cycle

Continue checking status-only and recovery-copy paths for stale evidence hazards around the missing Firebase blocker.
