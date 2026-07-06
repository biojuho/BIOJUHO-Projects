# AutoResearch Loop: AgriGuard Public Verify Cache Precheck

- Date: 2026-07-07 KST
- Scope: AgriGuard aggregate browser smoke runtime-drift diagnostics
- Owned code paths:
  - `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_PUBLIC_VERIFY_CACHE_PRECHECK.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_PUBLIC_VERIFY_CACHE_PRECHECK_2026-07-07.md`

## Objective

Turn a late QR-path browser-smoke failure into an explicit runtime precheck. The current default live target on `http://127.0.0.1:5174` / `http://127.0.0.1:8002` served public QR verification responses without `Cache-Control: no-store`, even though the checked-in backend source already applies those launch-safe headers.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: dev-server/browser automation should fail early on route-level runtime drift and preserve a machine-readable diagnostic before expensive user-path clicks.

## A/B Hypothesis

- Baseline: run the full aggregate browser suite and let `qr_path` discover missing public verify cache headers after several browser steps.
- Variant: add a `public_verify_cache_headers` precheck that probes both `--api-url` and frontend `/api` proxy before child browser steps.
- Primary KPI: stale public verify cache headers are classified as a precheck failure with no child browser ambiguity.
- Guardrails: a fresh current-code backend/frontend pair must pass the same aggregate app-click suite, existing browser-smoke tests must pass, and canonical AgriGuard smoke must remain green.
- Decision rule: adopt only if the stale target fails earlier with clearer diagnostics and the fresh current-code target passes all app-click checks.

## Baseline Evidence

Command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --include-unavailable-check --json-out var\agriguard-browser-smoke-suite-current-desktop-2026-07-07.json --output-dir var\agriguard-browser-smoke-suite-current-desktop-2026-07-07 --timeout-ms 30000
```

Result:

- `status=fail`
- `passed=6`, `failed=1`, `total=7`
- failed step: `qr_path`
- failed check: `qr_path:public_verify_api_responses_no_store`
- direct probe evidence:
  - `http://127.0.0.1:8002/api/qr/not-a-real-token/verify` returned status `200` with no `Cache-Control`, `Pragma`, or `Expires`
  - `http://127.0.0.1:5174/api/api/qr/not-a-real-token/verify` returned status `200` with no `Cache-Control`, `Pragma`, or `Expires`

## Variant Evidence

Implemented:

- Added a `public_verify_cache_headers` aggregate precheck.
- The precheck probes:
  - backend: `{api_url}/api/qr/browser-smoke-cache-precheck-token/verify?...`
  - frontend proxy: `{base_url}/api/api/qr/browser-smoke-cache-precheck-token/verify?...`
- Required headers:
  - `Cache-Control` contains `no-store`
  - `Pragma` contains `no-cache`
  - `Expires` equals `0`
- The suite fails before child browser steps when either target is stale.

Stale default target after patch:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --include-unavailable-check --json-out var\agriguard-browser-smoke-suite-public-cache-precheck-current-2026-07-07.json --output-dir var\agriguard-browser-smoke-suite-public-cache-precheck-current-2026-07-07 --timeout-ms 30000
```

Result:

- `status=fail`
- `prechecks_total=3`, `prechecks_passed=2`, `prechecks_failed=1`
- `failed_precheck_names=["public_verify_cache_headers"]`
- `total=0`, `results=[]`
- failed targets: `backend`, `frontend_proxy`
- detail: restart/rebuild the backend or proxy before running launch browser smoke

Fresh current-code target after patch:

- Started a temporary backend on `http://127.0.0.1:8072` with local SQLite, schema creation, dev-auth fallback, MQTT disabled, and public verify base URL set to the temporary frontend.
- Started a temporary Vite frontend on `http://127.0.0.1:5342` with `VITE_PROXY_API_TARGET=http://127.0.0.1:8072`.
- Stopped the temporary backend and frontend after the run.

Command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5342 --api-url http://127.0.0.1:8072 --include-unavailable-check --json-out var\agriguard-browser-smoke-suite-public-cache-precheck-fresh-2026-07-07.json --output-dir var\agriguard-browser-smoke-suite-public-cache-precheck-fresh-2026-07-07 --timeout-ms 30000
```

Result:

- `status=pass`
- `prechecks_total=4`, `prechecks_passed=4`, `prechecks_failed=0`
- `public_verify_cache_headers` passed through backend and frontend proxy
- `passed=7`, `failed=0`, `total=7`
- `checks_passed=186`, `checks_failed=0`
- `screenshot_artifacts_passed=19`, `screenshot_artifacts_failed=0`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\run_browser_smoke_suite.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 65 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py apps\AgriGuard\backend\tests\test_cors_origins.py -q`
  - Result: 100 passed, 1 warning
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-public-verify-cache-precheck.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-public-verify-cache-precheck-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_PUBLIC_VERIFY_CACHE_PRECHECK_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The aggregate browser suite now catches public verify cache-header runtime drift before app-click execution, while a fresh current-code runtime still passes the full app-click suite.

## Remaining Blockers

- The default live target on `5174/8002` is still stale for public verify cache headers until the backend/proxy is restarted or rebuilt.
- Launch remains externally blocked by the missing real Firebase Admin service-account file at `C:\secure\missing-firebase-service-account.json` for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue by checking whether guarded-launch handoff and operator packet evidence should surface this new browser-smoke precheck failure class when a stale runtime is detected.
