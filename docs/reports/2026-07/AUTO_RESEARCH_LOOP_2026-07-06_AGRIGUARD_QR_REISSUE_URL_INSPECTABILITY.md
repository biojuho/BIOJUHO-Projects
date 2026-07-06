# AutoResearch Loop - AgriGuard QR Reissue URL Inspectability - 2026-07-06

## Scope

- Hardened the QR token reissue result URL in `QRTokenManager.jsx`.
- Added `title` inspectability and `select-all` behavior for the one-time public label URL.
- Preserved horizontal scrolling and nowrap layout for safe label production.
- Added regression coverage in the QR token manager reissue flow.

## Verification

- Focused QR token manager test: `npm.cmd test -- --run QRTokenManager.test.jsx`
  - Result: 1 file passed, 7 tests passed.
- Focused QR token manager lint: `npm.cmd run lint -- src/components/QRTokenManager.jsx src/components/QRTokenManager.test.jsx`
  - Result: 0 errors.
  - Existing warning retained: `react-refresh/only-export-components` in `Dashboard.jsx`.
- Full frontend suite: `npm.cmd test -- --run`
  - Result: 18 files passed, 103 tests passed.
- Mobile nav browser smoke: `python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5309 --operator-token browser-smoke-token --json-out var/agriguard-nav-browser-smoke-qr-reissue-url-inspectability.json --screenshot-dir var/agriguard-nav-browser-smoke-qr-reissue-url-inspectability-screens --timeout-ms 30000 --mobile`
  - Result: 65/65 checks passed.
- Aggregate mobile browser suite: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5309 --api-url http://127.0.0.1:8039 --operator-token browser-smoke-token --output-dir var/agriguard-browser-smoke-qr-reissue-url-inspectability --json-out var/agriguard-browser-smoke-qr-reissue-url-inspectability.json --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 191/191 checks passed, 7/7 steps passed, 19/19 screenshot artifacts passed.

## Source Tracking

- Upstream AutoResearch source check:
  - `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
  - Result: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- GitHub modernization radar:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-qr-reissue-url-inspectability-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_QR_REISSUE_URL_INSPECTABILITY_2026-07-06.md`
  - Result: valid, 8 sources, adopted=8, partially_adopted=0, watch=0.

## Guarded Launch Status

- Command: `python apps/AgriGuard/scripts/run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-qr-reissue-url-inspectability-2026-07-06.json`
- Result: still blocked at strict launch preflight by operator-owned Firebase service-account material.
- Blocking action id: `set_firebase_service_account_file`.
- Blocking error: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
