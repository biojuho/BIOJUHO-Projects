# AutoResearch Loop: AgriGuard Launch Report App-Root Commands

Date: 2026-07-05

## Objective

Make launch-report replay command surfaces carry explicit app-root context and keep browser launch evidence green. The audit followed the operator-packet command hardening and checked readiness-summary and launch-report command arrays.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: launch reports should preserve replayable command arrays with explicit workspace/app context and browser evidence must catch real user-path regressions.

## A/B Contract

- Baseline: launch-compose child commands used absolute script paths but did not pass explicit `--app-root`; guarded-launch dry-run delegated to `launch_compose.py` without app-root context.
- Variant: add `--app-root` to launch-compose child commands that support it and to the guarded-launch delegated launch command.
- Guardrail discovery: the full browser suite found a reproducible QR manual-entry failure when a generated URL-safe token started with `-`.
- QR variant: allow URL-safe bare manual tokens that start with `-` or `_`, matching generated public verification tokens.
- Decision: adopt both. Command arrays now carry explicit app-root context, and the QR manual fallback accepts generated URL-safe tokens.

## Changed Paths

- `apps/AgriGuard/scripts/launch_compose.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/backend/tests/test_launch_compose_script.py`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `apps/AgriGuard/frontend/src/components/QRReader.jsx`
- `apps/AgriGuard/frontend/src/components/QRReader.test.jsx`

## Verification

- `python -m py_compile apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m ruff check apps/AgriGuard/scripts/launch_compose.py apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q` - `38 passed`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var\agriguard-launch-report-app-root-command-proof --output-prefix launch-report-app-root-command-proof --emit-handoff` - expected exit `1`; handoff consumer `errors=[]`, artifact index `status=pass`.
- Launch report command audit: `env_validation`, `operator_packet`, and `readiness_summary` command arrays all include `--app-root D:\AI project\apps\AgriGuard`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var/agriguard-launch-operator.missing-firebase.env --output-dir var\agriguard-launch-report-app-root-command-proof --output-prefix launch-report-app-root-command-proof --dry-run` - delegated `launch_compose.py` command includes `--app-root`.
- `npm run test -- src/components/QRReader.test.jsx` - `11 passed`.
- `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-qr-path-browser-smoke-leading-dash-token.json --screenshot-dir var\agriguard-qr-path-browser-smoke-leading-dash-token-screens --timeout-ms 120000` - `22/22 PASS`.
- First full browser suite exposed `qr_path:unhandled_exception` for a leading-dash token; after the QR fix, `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-launch-report-app-root-commands-retry.json --output-dir var\agriguard-browser-smoke-suite-launch-report-app-root-commands-retry --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-report-app-root-commands-final.json` - `passed=5`, `failed=0`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. Local command replay, readiness artifacts, QR manual fallback, workspace smoke, and browser smoke are green.

## Next Cycle

Audit generated readiness summary next-action text for command snippets that should be upgraded from prose-only guidance into copyable commands.
