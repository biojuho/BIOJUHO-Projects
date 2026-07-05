# Auto Research Loop - AgriGuard Fresh Aggregate Browser Suite

Date: 2026-07-06

## Source Basis

- The aggregate browser suite is the launch-level browser gate across dashboard auth recovery, navigation, supply chain, QR path, admin routes, product detail, and consumer-unavailable behavior.
- A stale local stack on `5174`/`8002` still returned empty public verify cache headers. A fresh direct-backend stack is required to verify the latest no-store and screenshot-masking changes without disturbing the existing user processes.

## Fresh Stack

- Temporary backend:
  - Port: `8004`
  - Database: throwaway SQLite under `var`
  - Auth: local dev fallback with operator role
  - Public verify base URL: `http://127.0.0.1:5199`
- Temporary frontend:
  - Port: `5199`
  - `VITE_API_URL=http://127.0.0.1:8004`
- Cleanup:
  - Temporary listeners on `8004` and `5199` were stopped after verification.

## Verification

- Existing stale-stack aggregate probe:
  - Command used `http://127.0.0.1:5174` and `http://127.0.0.1:8002`.
  - Result: `failed=1`, failed check `qr_path:public_verify_api_responses_no_store`.
  - Child detail showed public verify responses with empty `cacheControl`, `pragma`, and `expires`, matching stale backend behavior.
- Fresh direct-backend aggregate suite:
  - Command: `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5199 --api-url http://127.0.0.1:8004 --operator-token fresh-suite-secret-token --include-unavailable-check --skip-backend-contract-check --json-out var\agriguard-browser-suite-fresh-2026-07-06.json --output-dir var\agriguard-browser-suite-fresh-2026-07-06 --timeout-ms 30000`
  - Result: `passed=7`, `failed=0`, `checks_passed=166`, `checks_failed=0`, `screenshot_artifacts_passed=19`, `screenshot_artifacts_failed=0`.
  - The proxy precheck was skipped because this isolated frontend intentionally used direct `VITE_API_URL` instead of the `/api` proxy path.
- Aggregate leak probe:
  - Aggregate report and all child JSON files had `OperatorTokenPresent=false`.
  - Raw verify route matches: `0`.
  - Raw `Token...State` table-token hints: `0`.
  - Expected redaction markers appeared in QR-bearing child reports:
    - `admin-routes.json`: `4`
    - `consumer-verify-unavailable.json`: `7`
    - `product-detail.json`: `4`
    - `qr-path.json`: `14`
- Guarded launch status refresh:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-fresh-suite-2026-07-06.json`
  - Result: `status=blocked`, `blocker_class=preflight_blocked`, `operator_action_ids=["set_firebase_service_account_file"]`.

## Current Launch Blocker

The fresh aggregate browser suite passes with the latest local code and redacted QR evidence. Full guarded launch remains externally blocked by the missing operator-provided `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
