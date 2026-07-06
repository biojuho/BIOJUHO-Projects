# AutoResearch Loop: AgriGuard Docker Runtime Diagnostic

- Date: 2026-07-07 KST
- Scope: AgriGuard aggregate browser-smoke runtime diagnostics
- Owned code paths:
  - `apps/AgriGuard/scripts/run_browser_smoke_suite.py`
  - `apps/AgriGuard/backend/tests/test_smoke.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_DOCKER_RUNTIME_DIAGNOSTIC.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_DOCKER_RUNTIME_DIAGNOSTIC_2026-07-07.md`

## Objective

Make the default `5174/8002` browser-smoke failure actionable. The public verify cache-header precheck already failed before browser clicks, but it did not explain that `8002` was served by an old Docker-backed AgriGuard runtime with launch-unsafe env and a repo-local Firebase secret mount.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: browser automation should combine route-level checks with runtime/process diagnostics so failures point to the stale service, not only the failing UI path.

## A/B Hypothesis

- Baseline: cache-header precheck failure says to restart/rebuild the backend or proxy, but does not identify the runtime drift source.
- Variant: when the cache-header precheck is already failing and `--api-url` is localhost, best-effort inspect the Docker container publishing that port and attach launch-unsafe drift signals.
- Primary KPI: failing default browser-smoke JSON identifies the Docker container and launch-unsafe signals.
- Guardrails: fresh non-Docker local runs do not depend on Docker, diagnostic output does not leak raw env secret values, and canonical AgriGuard smoke remains green.

## Baseline Evidence

Earlier default-target run:

- `status=fail`
- failed precheck: `public_verify_cache_headers`
- failed targets: `backend`, `frontend_proxy`
- detail only said to restart/rebuild the backend or proxy.

Manual runtime inspection then showed:

- `8002` was owned by Docker and mapped to container `agriguard-backend`.
- The container had dev fallback enabled, empty QR/public verify launch env, and a repo-local Firebase secret bind.

## Variant Evidence

Implemented:

- Added best-effort Docker runtime diagnostics in `run_browser_smoke_suite.py`.
- The diagnostic only runs after public verify cache headers fail.
- It reports signal names such as `ALLOW_DEV_AUTH_FALLBACK=true`, `SECRET_KEY=dev-default`, `QR_TOKEN_PEPPER_EMPTY`, `PUBLIC_VERIFY_BASE_URL_EMPTY`, and `FIREBASE_SECRET_REPO_LOCAL`.
- It redacts raw env values and emits only a repo-relative mount hint for repo-local Firebase secret mounts.
- Docker subprocess decoding now uses UTF-8 with replacement to avoid Windows CP949 reader-thread noise.

Default-target proof:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --include-unavailable-check --json-out var\agriguard-browser-smoke-suite-docker-runtime-diagnostic-2026-07-07.json --output-dir var\agriguard-browser-smoke-suite-docker-runtime-diagnostic-2026-07-07 --timeout-ms 30000
```

Result:

- `status=fail`
- `failed_precheck_names=["public_verify_cache_headers"]`
- `prechecks_total=3`, `prechecks_passed=2`, `prechecks_failed=1`
- `runtime_diagnostics.backend_docker_runtime.name=agriguard-backend`
- `runtime_diagnostics.backend_docker_runtime.launch_unsafe_signals`:
  - `ALLOW_DEV_AUTH_FALLBACK=true`
  - `SECRET_KEY=dev-default`
  - `QR_TOKEN_PEPPER_EMPTY`
  - `PUBLIC_VERIFY_BASE_URL_EMPTY`
  - `FIREBASE_SECRET_REPO_LOCAL`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\run_browser_smoke_suite.py apps\AgriGuard\backend\tests\test_smoke.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q`
  - Result: 67 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-docker-runtime-diagnostic.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-docker-runtime-diagnostic-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_DOCKER_RUNTIME_DIAGNOSTIC_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The failing default browser-smoke precheck now explains the stale Docker runtime and launch-unsafe signals instead of stopping at a generic cache-header error.

## Remaining Blockers

- The running default Docker backend on `8002` is still stale. Current compose cannot safely restore it without the real outside-repo Firebase Admin service-account file.
- Launch remains externally blocked by the missing real Firebase Admin service-account file at `C:\secure\missing-firebase-service-account.json` for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue by adding an operator-safe restart/rebuild helper that refuses to stop the current Docker runtime unless the replacement launch env can mount a real Firebase service-account JSON and pass strict preflight.
