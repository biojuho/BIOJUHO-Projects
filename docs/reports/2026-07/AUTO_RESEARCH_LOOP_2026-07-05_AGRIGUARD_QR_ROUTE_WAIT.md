# AutoResearch Loop: AgriGuard QR Route Wait

Date: 2026-07-05

## Objective

Remove a flaky QR-path browser-smoke wait around manual verification navigation without weakening the launch gate. The real product proof should remain the rendered `/verify/:token` public page, not a Playwright same-document navigation load event.

## Source Evidence

- Veritas source check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main` observed `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUATION_2026-07-05.md`, `8` sources valid, `8` adopted, `0` partial, `0` watch.
- Applied pattern: browser automation should assert the real app state and keep diagnostics for route failures instead of treating framework-internal SPA navigation timing as the product contract.

## A/B Contract

- Baseline: `qr_path_browser_smoke.py` clicked the manual verification button, then used `page.wait_for_url(..., wait_until="load")`. A transient full-suite run timed out even though the app later passed on retry.
- Variant: replace the URL load wait with a Python-side poll of `page.url` against the expected `/verify/:token` route, preserving the downstream `Public view` and product evidence assertions.
- Primary KPI: focused QR-path smoke passes against the live app while retaining `manual_verify_url_opened`, public-view, trust-copy, batch-evidence, unavailable-state, console, request-failure, and screenshot checks.
- Guardrails: canonical AgriGuard workspace smoke and full browser suite must pass; timeout diagnostics must include expected route, current URL, and body sample.
- Decision: adopt. The QR route gate now matches SPA behavior and remains product-state based.

## Changed Paths

- `apps/AgriGuard/scripts/qr_path_browser_smoke.py`
- `apps/AgriGuard/backend/tests/test_smoke.py`

## Verification

- `python -m ruff check apps/AgriGuard/scripts/qr_path_browser_smoke.py apps/AgriGuard/backend/tests/test_smoke.py` - pass.
- `python -m py_compile apps/AgriGuard/scripts/qr_path_browser_smoke.py apps/AgriGuard/backend/tests/test_smoke.py` - pass.
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q` - `38 passed`.
- First live variant run wrote `var/agriguard-qr-path-spa-route-wait.json` with the improved diagnostic: the browser was already at the expected `/verify/:token` URL while the page-function wait timed out. This proved the remaining issue was the helper implementation, not product navigation.
- Final focused live run: `python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --operator-token dev-operator-token --json-out var\agriguard-qr-path-spa-route-wait.json --screenshot-dir var\agriguard-qr-path-spa-route-wait-screens --timeout-ms 120000` - `22/22 PASS`.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-qr-route-wait.json` - final report status `complete`, `passed=5`, `failed=0`; backend tests `608 passed`. The shell tool timed out first, but the smoke process completed naturally and wrote a passing report.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-qr-route-wait.json --output-dir var\agriguard-browser-smoke-suite-qr-route-wait --timeout-ms 120000` - `passed=6`, `failed=0`, `checks_passed=135/135`, `screenshots_passed=18/18`.

## Remaining Blocker

The real launch remains externally blocked on the missing Firebase Admin service-account JSON. Local QR-path browser evidence is now less flaky and more diagnostic.

## Next Cycle

Continue tightening AgriGuard launch handoff around the missing Firebase blocker, with preference for evidence consumers that prevent stale or mismatched operator artifacts.
