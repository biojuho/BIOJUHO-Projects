# AutoResearch Loop: AgriGuard Source vs Runtime Cache Header Divergence

- Date: 2026-07-07 KST
- Scope: AgriGuard public verify cache-header launch blocker
- Owned artifact paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_SOURCE_RUNTIME_CACHE_DIVERGENCE.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_SOURCE_RUNTIME_CACHE_DIVERGENCE_2026-07-07.md`

## Objective

The strict browser launch suite remains blocked by `public_verify_cache_headers`. Before changing source code, this pass separated source correctness from the current live runtime state. The result is clear: source-level router and full-app middleware tests pass, while the running Docker backend/proxy still returns public verify responses without no-store headers.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: distinguish source regression from stale runtime/operator blocker before applying code changes.

## Source Evidence

Source locations already define and apply no-store public verify headers:

- `apps/AgriGuard/backend/main.py`
  - `PUBLIC_VERIFY_CACHE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache", "Expires": "0"}`
  - middleware applies those headers when the path starts with `/api/qr/` and ends with `/verify`.
- `apps/AgriGuard/backend/routers/qr_verify.py`
  - router-local `PUBLIC_VERIFY_CACHE_HEADERS` matches the same contract.
  - `verify_qr_token()` calls `set_public_verify_cache_headers(response)` before returning.

Source verification:

```powershell
python -m pytest apps\AgriGuard\backend\tests\test_public_qr_verify_cache_headers.py apps\AgriGuard\backend\tests\test_cors_origins.py -q
```

Result:

- `37 passed`
- one expected local warning: `SECRET_KEY is not set! Using an insecure default.`

## Runtime Evidence

Strict live browser precheck:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-suite-source-runtime-cache-divergence-strict-2026-07-07.json --output-dir var\agriguard-browser-suite-source-runtime-cache-divergence-strict-2026-07-07 --timeout-ms 30000
```

Result:

- `status=fail`
- `evidence_class=launch_precheck_blocked`
- `launch_gate_enforced=true`
- `failed_precheck_names=[public_verify_cache_headers]`
- failed targets: `backend`, `frontend_proxy`
- backend probe headers:
  - `Cache-Control=""`
  - `Pragma=""`
  - `Expires=""`
- frontend proxy probe headers:
  - `Cache-Control=""`
  - `Pragma=""`
  - `Expires=""`

Runtime diagnostics:

- container: `agriguard-backend`
- stale/unsafe drift signals:
  - `ALLOW_DEV_AUTH_FALLBACK=true`
  - `SECRET_KEY=dev-default`
  - `QR_TOKEN_PEPPER_EMPTY`
  - `PUBLIC_VERIFY_BASE_URL_EMPTY`
  - `FIREBASE_SECRET_REPO_LOCAL`

## Decision

No source patch was applied for cache headers in this pass. The repository source and tests already enforce the no-store public verify contract. The current blocker is the running backend/proxy runtime, which must be safely replaced only after strict launch preflight can use a real outside-repo Firebase Admin service-account file.

## Remaining Blockers

- Strict launch remains blocked by stale backend/proxy runtime cache headers.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
