# Auto Research Loop - AgriGuard Env Template Checked Path - 2026-07-06

## Objective

Make the operator env template show the Firebase service-account path currently checked by preflight, while keeping the editable env assignment as an explicit placeholder that operators must replace deliberately.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ENV_TEMPLATE_CHECKED_PATH_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Changes

- `apps/AgriGuard/scripts/render_launch_operator_packet.py`
  - Reads `preflight_checks.firebase_credentials_resolved_path` when rendering the operator env template.
  - Adds `# Current preflight checked path: ...` above `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` when the packet has that value.
  - Leaves `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=<absolute-path-outside-repo-to-firebase-service-account.json>` unchanged.
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - Verifies the current checked Firebase path comment appears in the template.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
  - Result: `17 passed in 1.32s`
- `python apps/AgriGuard/scripts/render_launch_operator_packet.py --app-root apps\AgriGuard --preflight-json var\agriguard-guarded-launch-preflight.json --json-out var\agriguard-env-template-checked-path-operator-packet.json --markdown-out var\agriguard-env-template-checked-path-operator-packet.md --env-template-out var\agriguard-env-template-checked-path.env.template`
  - Result: exit `1` as expected because the packet remains blocked.
  - Template includes `# Current preflight checked path: C:\secure\missing-firebase-service-account.json`.
  - Template keeps `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE=<absolute-path-outside-repo-to-firebase-service-account.json>`.
- `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-env-template-checked-path-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`
  - Local artifact index remains `pass` and `ready`.

## Current Blocker

Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
