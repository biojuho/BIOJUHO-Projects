# AutoResearch Loop - AgriGuard Public QR Analytics Input Allowlist

Date: 2026-07-06

## Source basis

- AutoResearch/Karpathy source guard refreshed against `https://github.com/Veritas-7/autoresearch-skill-system.git` at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- OWASP Input Validation Cheat Sheet on GitHub recommends allowlist validation for user-provided input fields: https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/Input_Validation_Cheat_Sheet.md

## Baseline finding

The public QR verification route accepted `session_id`, `variant_id`, and `source` query parameters with length limits, but those analytics labels were still stored directly in `qr_scan_events`. That allowed malformed labels with whitespace, newlines, or markup-like characters to pollute launch evidence and downstream analytics, even though the public verification result stayed safe.

## Adopted changes

- Added an allowlist for public QR analytics labels: letters, digits, `.`, `_`, `:`, and `-`.
- Invalid or blank `session_id` now falls back to the existing generated `public-<uuid>` session ID path.
- Invalid `variant_id` falls back to `qr_consumer_v1`.
- Invalid `source` falls back to `consumer_verify_page`.
- Extended `test_public_qr_verify_cache_headers.py` with a regression case proving malformed analytics inputs are normalized before persistence.

## Evidence

- `python -m pytest apps\AgriGuard\backend\tests\test_public_qr_verify_cache_headers.py -q`: 2 passed.
- `python -m pytest apps\AgriGuard\backend\tests\test_product_and_qr_routes.py -q`: 41 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard`: passed=5, failed=0, total=5.
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-public-qr-analytics-inputs-2026-07-06.json`: status `blocked`, blocker_class `preflight_blocked`.

## Remaining blocker

Launch remains externally blocked on operator-provided Firebase Admin credentials:

`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

Public QR analytics input hygiene is local and green. Guarded launch should still fail closed until the operator supplies the real service-account file outside the repository and reruns strict preflight.
