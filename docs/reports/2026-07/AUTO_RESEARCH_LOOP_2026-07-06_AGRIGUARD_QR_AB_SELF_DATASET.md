# Auto Research Loop - AgriGuard QR A/B Self-Dataset Reuse - 2026-07-06

## Objective

Make the QR page A/B helper reproducible by allowing the JSON summary it emits to be reused as a later `--dataset` input.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_AB_SELF_DATASET_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Gap Found

- `python apps\AgriGuard\scripts\ab_test_qr_page.py --dataset var\agriguard-qr-page-ab-auto-research-2026-07-06.json --json-out var\agriguard-qr-page-ab-auto-research-self-dataset-2026-07-06.json`
- Before the fix, the helper accepted the prior JSON summary but found `0` sessions because it only read `sessions`, `observations`, or `items`; its own output stores rows under `control.session_rows` and `variant.session_rows`.

## Fix

- `apps/AgriGuard/scripts/ab_test_qr_page.py`
  - Added summary-output dataset loading from `control.session_rows` and `variant.session_rows`.
  - Kept the existing summary helper refactor intact.
- `apps/AgriGuard/backend/tests/test_smoke.py`
  - Added a regression test that feeds a prior-style summary JSON back into the script and asserts the output contains both variants.

## Verification

- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -k "qr_ab"`
  - Result: `2 passed, 57 deselected`
- `python apps\AgriGuard\scripts\ab_test_qr_page.py --dataset var\agriguard-qr-page-ab-auto-research-2026-07-06.json --json-out var\agriguard-qr-page-ab-auto-research-self-dataset-fixed-2026-07-06.json --output docs\reports\2026-07\AGRIGUARD_QR_PAGE_AB_SELF_DATASET_2026-07-06.md`
  - Result: exit `0`
  - Dataset: `built-in sample`
  - Sessions: `20`
  - Control verification success: `0.60`
  - Guided variant verification success: `0.90`
  - Verification relative lift: `50.00%`
  - Decision: `adopt_b`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py`
  - Result: `59 passed in 38.68s`
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate-qr-ab-self-dataset-2026-07-06.json`
  - Result: exit `1` as expected.
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Checked Firebase credential path: `C:\secure\missing-firebase-service-account.json`

## Current Blocker

Local A/B reproducibility and smoke evidence are green. Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`: `C:\secure\missing-firebase-service-account.json`.
