# Auto Research Loop - AgriGuard QR A/B UTC Timestamp - 2026-07-06

## Objective

Make QR page A/B Markdown evidence portable across Windows terminals by replacing localized timezone text with an ASCII UTC timestamp.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_AB_UTC_TIMESTAMP_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Gap Found

- The QR A/B report generated timestamps with `datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")`.
- On this Windows/Korea locale, the report contained localized timezone text that rendered as mojibake in PowerShell reads, weakening evidence portability.

## Fix

- `apps/AgriGuard/scripts/ab_test_qr_page.py`
  - Added `generated_timestamp_utc()` and changed Markdown rendering to use an ASCII UTC value like `2026-07-06T11:51:47Z`.
- `apps/AgriGuard/backend/tests/test_smoke.py`
  - Fixed the dynamic script import helper to register modules in `sys.modules` while executing them, which is required for dataclass type resolution.
  - Added a regression test that renders QR A/B Markdown and asserts the generated timestamp line is ASCII and UTC-suffixed.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -k "qr_ab"`
  - First run exposed the dynamic import helper issue.
  - Final result: `3 passed, 57 deselected`
- `python apps\AgriGuard\scripts\ab_test_qr_page.py --dataset var\agriguard-qr-page-ab-auto-research-2026-07-06.json --json-out var\agriguard-qr-page-ab-auto-research-self-dataset-fixed-utc-2026-07-06.json --output docs\reports\2026-07\AGRIGUARD_QR_PAGE_AB_SELF_DATASET_UTC_2026-07-06.md`
  - Result: exit `0`
  - Generated line: `- Generated: 2026-07-06T11:51:47Z`
  - Sessions: `20`
  - Decision: `adopt_b`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: `60 passed in 47.88s`
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate-qr-ab-utc-timestamp-2026-07-06.json`
  - Result: exit `1` as expected.
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Checked Firebase credential path: `C:\secure\missing-firebase-service-account.json`

## Current Blocker

Local QR A/B report portability and smoke evidence are green. Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`: `C:\secure\missing-firebase-service-account.json`.
