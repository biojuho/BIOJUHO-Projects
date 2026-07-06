# Auto Research Loop - AgriGuard Readiness Preflight Checks - 2026-07-06

## Objective

Expose safe operator-packet preflight checks in the launch readiness summary JSON and markdown so the resolved Firebase service-account path is available in the readiness artifact as well as the operator packet, status view, handoff, and env template.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_READINESS_PREFLIGHT_CHECKS_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/summarize_launch_readiness.py`
  - Adds a safe `reports.operator_packet.preflight_checks` subset to the readiness summary JSON.
  - Renders an `Operator Packet Preflight Checks` markdown table when those values are present.
- `apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
  - Verifies the resolved Firebase credential path appears in both readiness summary JSON and markdown.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py`
  - Result: `7 passed in 0.44s`
- `python apps/AgriGuard/scripts/summarize_launch_readiness.py --app-root apps\AgriGuard --launch-report-json var\agriguard-guarded-launch-launch-report.json --env-validation-json var\agriguard-guarded-launch-env-validation.json --operator-packet-json var\agriguard-guarded-launch-operator-packet.json --json-out var\agriguard-readiness-preflight-checks-summary.json --markdown-out var\agriguard-readiness-preflight-checks-summary.md`
  - Result: exit `1` as expected because readiness remains blocked.
  - JSON includes `reports.operator_packet.preflight_checks.firebase_credentials_resolved_path=C:\secure\missing-firebase-service-account.json`.
  - Markdown includes `## Operator Packet Preflight Checks`.
  - Markdown includes `firebase_credentials_resolved_path=C:\secure\missing-firebase-service-account.json`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-readiness-preflight-checks-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Local artifact index remains `pass` and `ready`.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
