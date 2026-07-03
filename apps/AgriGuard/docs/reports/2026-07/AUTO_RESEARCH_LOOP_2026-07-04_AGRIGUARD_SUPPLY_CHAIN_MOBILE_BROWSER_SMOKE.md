# AutoResearch Loop - AgriGuard Supply Chain Mobile Browser Smoke

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: mobile supply-chain browser workflow coverage
- External context: `Veritas-7/autoresearch-skill-system` main was refreshed at `b8bbf393759d6e67e780f03c572ec626fab6593b`; the workspace modernization radar recorded 8 source-backed patterns as already adopted.

## Source-Backed Rationale

The AutoResearch loop treats real browser checks as the deciding evidence for responsive workflow risk. The supply-chain smoke already checked pagination, search reset, bounded page payloads, and overflow, but only at the desktop viewport. The mobile surface is launch-relevant because supply-chain browsing is likely to happen from field and packhouse devices.

## A/B Hypothesis

Baseline: `supply_chain_browser_smoke.py` hard-coded a `1440x960` desktop viewport, so the smoke could not prove mobile pagination, search, or horizontal overflow behavior.

Variant: add explicit viewport resolution, keep the desktop default, and let `--mobile` run the same workflow at a phone-sized `390x844` viewport with mobile/touch emulation.

Adopt rule: adopt only if desktop stays green, mobile passes the same workflow checks, focused unit coverage passes, and the full AgriGuard smoke scope remains green.

## Adopted Change

- Added `DEFAULT_DESKTOP_VIEWPORT`, `DEFAULT_MOBILE_VIEWPORT`, `parse_viewport()`, and `resolve_viewport()` to `scripts/supply_chain_browser_smoke.py`.
- Added `--viewport` and `--mobile` CLI options.
- Recorded `viewport` and `mobile` in the JSON smoke output.
- Updated the shared script import test helper to stub Playwright `Response`.
- Added `backend/tests/test_smoke.py::test_supply_chain_browser_smoke_uses_phone_viewport_for_mobile_default`.

## Browser Evidence

All browser evidence was recorded under:

`D:\AI project\var\agriguard-supply-chain-mobile-browser-2026-07-04`

### Desktop Regression

```powershell
python apps/AgriGuard/scripts/supply_chain_browser_smoke.py --url http://127.0.0.1:5193/supply-chain --operator-token browser-smoke-token --json-out var/agriguard-supply-chain-mobile-browser-2026-07-04/supply-chain-desktop-after-viewport.json --screenshot var/agriguard-supply-chain-mobile-browser-2026-07-04/supply-chain-desktop-after-viewport.png --timeout-ms 30000
```

Result: `21/21 PASS`, `ok=true`, viewport `1440x960`, `mobile=false`, 0 failed checks, no horizontal overflow.

### Mobile Variant

```powershell
python apps/AgriGuard/scripts/supply_chain_browser_smoke.py --url http://127.0.0.1:5193/supply-chain --operator-token browser-smoke-token --mobile --json-out var/agriguard-supply-chain-mobile-browser-2026-07-04/supply-chain-mobile-variant.json --screenshot var/agriguard-supply-chain-mobile-browser-2026-07-04/supply-chain-mobile-variant.png --timeout-ms 30000
```

Result: `21/21 PASS`, `ok=true`, viewport `390x844`, `mobile=true`, 0 failed checks, no horizontal overflow.

## Verification

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/scripts/supply_chain_browser_smoke.py' 'apps/AgriGuard/backend/tests/test_smoke.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_smoke.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-supply-chain-mobile-full'
```

Result: `9 passed in 44.57s`.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-supply-chain-mobile-browser-smoke.json
```

Result: `passed=5, failed=0, total=5` in `4m15s`.

Slowest checks:

- `agriguard backend tests`: pass in `3m38s`
- `agriguard frontend lint`: pass in `16.1s`
- `agriguard frontend build`: pass in `8.9s`
- `agriguard contracts tests`: pass in `8.7s`
- `agriguard contracts compile`: pass in `3.0s`

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-supply-chain-mobile-browser-smoke.json`

## Current Launch State

The supply-chain browser smoke now proves the same paged product workflow on desktop and mobile. Mobile evidence covers page load, bounded product cards, pagination, search reset, normalized statuses, paginated API usage, bounded payloads, screenshot capture, and no horizontal overflow.
