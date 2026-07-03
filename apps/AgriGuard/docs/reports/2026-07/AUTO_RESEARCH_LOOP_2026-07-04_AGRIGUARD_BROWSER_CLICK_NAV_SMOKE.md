# AutoResearch Loop - AgriGuard Browser Click Nav Smoke

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: mobile browser-click launch validation for the authenticated navigation surface
- External context: `Veritas-7/autoresearch-skill-system` main was refreshed at `b8bbf393759d6e67e780f03c572ec626fab6593b`; the workspace modernization radar recorded 8 source-backed patterns as already adopted.

## Source-Backed Rationale

The AutoResearch skill loop favors a real browser/app smoke over static inspection when the risk is route reachability, responsive navigation, or user-visible errors. This slice applied that rule to AgriGuard's authenticated mobile navigation: click through the app with Playwright, record the baseline, change only the local verifier when the app is not the failing component, and keep the desktop and workflow browser smokes green.

## A/B Hypothesis

Baseline issue: `scripts/nav_browser_smoke.py --mobile --click-nav` enabled mobile browser options but kept the default desktop viewport. The test expected a mobile menu button, while the page was rendered at `1440x960`, so the mobile click path failed waiting for `Open menu`.

Variant: make the smoke harness resolve a phone-sized default viewport when `--mobile` is used, while preserving the `1440x960` desktop default and allowing explicit `--viewport` overrides.

Adopt rule: adopt only if the variant passes the mobile click navigation smoke and does not regress desktop navigation, supply-chain browser workflow, admin route browser workflow, focused unit coverage, or the full AgriGuard smoke scope.

## Adopted Change

- Added `DEFAULT_DESKTOP_VIEWPORT`, `DEFAULT_MOBILE_VIEWPORT`, and `resolve_viewport()` to `scripts/nav_browser_smoke.py`.
- Changed `--viewport` from an unconditional `1440x960` default to an optional override.
- Made `--mobile` default to `390x844`, matching a phone-sized viewport where the mobile menu is present.
- Added `backend/tests/test_smoke.py::test_nav_browser_smoke_uses_phone_viewport_for_mobile_default` to lock desktop default, mobile default, and explicit mobile override behavior.

## Browser Evidence

All browser evidence was recorded under:

`D:\AI project\var\agriguard-browser-click-2026-07-04`

### Baseline

```powershell
$env:AGRIGUARD_BROWSER_OPERATOR_TOKEN='browser-smoke-token'
python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5188 --operator-token browser-smoke-token --mobile --click-nav --json-out var/agriguard-browser-click-2026-07-04/nav-click-mobile-rerun.json --screenshot-dir var/agriguard-browser-click-2026-07-04/nav-click-mobile-rerun-screens --timeout-ms 30000
```

Result: `4/12 PASS`, `ok=false`, viewport `1440x960`, 8 failed checks. The failures were harness-induced: the desktop viewport meant the page had no mobile `Open menu` button for the mobile click path.

### Variant

```powershell
$env:AGRIGUARD_BROWSER_OPERATOR_TOKEN='browser-smoke-token'
python apps/AgriGuard/scripts/nav_browser_smoke.py --base-url http://127.0.0.1:5188 --operator-token browser-smoke-token --mobile --click-nav --json-out var/agriguard-browser-click-2026-07-04/nav-click-mobile-fixed.json --screenshot-dir var/agriguard-browser-click-2026-07-04/nav-click-mobile-fixed-screens --timeout-ms 30000
```

Result: `47/47 PASS`, `ok=true`, viewport `390x844`, 0 failed checks.

### Regression Browser Checks

- Desktop nav click smoke: `47/47 PASS`, viewport `1440x960`.
- Supply-chain browser smoke: `20/20 PASS`.
- Admin routes browser smoke: `status=pass`, 8 checks, 0 failed checks.

The first local server attempt allowed Vite to choose port `5176`, which was outside the backend CORS allow-list and produced setup-induced browser request failures. The accepted evidence was rerun with deterministic strict port `5188` and matching backend CORS config.

## Verification

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/scripts/nav_browser_smoke.py' 'apps/AgriGuard/backend/tests/test_smoke.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_smoke.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-nav-browser-smoke-full'
```

Result: `7 passed in 22.79s`.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-browser-click-nav-smoke.json
```

Result: `passed=5, failed=0, total=5` in `5m6s`.

Slowest checks:

- `agriguard backend tests`: pass in `4m29s`
- `agriguard frontend lint`: pass in `14.0s`
- `agriguard frontend build`: pass in `10.3s`
- `agriguard contracts tests`: pass in `8.8s`
- `agriguard contracts compile`: pass in `3.1s`

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-browser-click-nav-smoke.json`

## Current Launch State

AgriGuard now has a real mobile click-through navigation smoke that exercises the responsive menu at a phone viewport. The app passed mobile nav, desktop nav, admin routes, supply-chain browser workflow, focused unit coverage, and the full AgriGuard smoke scope for this slice.
