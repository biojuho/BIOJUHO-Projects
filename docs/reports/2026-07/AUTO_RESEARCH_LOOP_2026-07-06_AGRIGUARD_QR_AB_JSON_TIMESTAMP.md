# Auto Research Loop - AgriGuard QR A/B JSON Timestamp - 2026-07-06

## Objective

Make paired QR page A/B Markdown and JSON evidence easier to correlate by sharing one ASCII UTC generation timestamp across both outputs.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_AB_JSON_TIMESTAMP_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Gap Found

- The QR A/B Markdown report had a portable UTC `Generated` line, but the JSON summary did not expose a `generated_at` value.
- This made paired Markdown/JSON evidence harder to correlate after repeated AutoResearch runs.

## Fix

- `apps/AgriGuard/scripts/ab_test_qr_page.py`
  - Computes `generated_at` once in `main()`.
  - Passes the same value into Markdown rendering.
  - Adds the same value to JSON output under `generated_at`.
- `apps/AgriGuard/backend/tests/test_smoke.py`
  - Extends the QR A/B JSON-output regression to assert `generated_at` is ASCII and UTC-suffixed.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -k "qr_ab"`
  - Result: `3 passed, 57 deselected`
- `python apps\AgriGuard\scripts\ab_test_qr_page.py --dataset var\agriguard-qr-page-ab-auto-research-2026-07-06.json --json-out var\agriguard-qr-page-ab-auto-research-json-timestamp-2026-07-06.json --output docs\reports\2026-07\AGRIGUARD_QR_PAGE_AB_JSON_TIMESTAMP_2026-07-06.md`
  - Result: exit `0`
  - Markdown generated timestamp: `2026-07-06T11:55:49Z`
  - JSON generated timestamp: `2026-07-06T11:55:49Z`
  - Timestamp match: `true`
  - Sessions: `20`
  - Decision: `adopt_b`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: `60 passed in 37.41s`
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate-qr-ab-json-timestamp-2026-07-06.json`
  - Result: exit `1` as expected.
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Checked Firebase credential path: `C:\secure\missing-firebase-service-account.json`

## Current Blocker

Local QR A/B evidence correlation and smoke coverage are green. Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`: `C:\secure\missing-firebase-service-account.json`.
