# Auto Research Loop - AgriGuard Operator Markdown Preflight Checks - 2026-07-06

## Objective

Expose key launch preflight checks in the human-facing operator packet markdown, including the resolved Firebase service-account path added to the packet JSON in the previous loop.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_OPERATOR_MARKDOWN_PREFLIGHT_CHECKS_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
  - Adds a `Preflight Checks` markdown section between operator actions and preflight errors.
  - Renders non-empty launch check values such as runtime, Docker check status, Firebase credential source, resolved Firebase credential path, origin/public URL sources, and database password source.
  - Normalizes booleans and lists for compact markdown table output.
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - Verifies `firebase_credentials_resolved_path` appears in rendered markdown.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - Result: `17 passed in 1.15s`
- `python apps/AgriGuard/scripts/render_launch_operator_packet.py --app-root apps\AgriGuard --preflight-json var\agriguard-firebase-path-evidence-preflight.json --json-out var\agriguard-markdown-preflight-checks-operator-packet.json --markdown-out var\agriguard-markdown-preflight-checks-operator-packet.md --env-template-out var\agriguard-markdown-preflight-checks.env.template`
  - Result: exit `1` as expected because the packet remains blocked on operator values.
  - Markdown now contains `## Preflight Checks`.
  - Markdown includes `firebase_credentials_resolved_path=C:\secure\missing-firebase-service-account.json`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-operator-markdown-preflight-checks-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Local artifact index and consumer metadata remain `pass`.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
