# AutoResearch Loop - AgriGuard Admin Fail-Closed Browser Smoke

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: protected admin browser fail-closed coverage
- External context: `Veritas-7/autoresearch-skill-system` main was refreshed at `b8bbf393759d6e67e780f03c572ec626fab6593b`; the workspace modernization radar recorded 8 source-backed patterns as already adopted.

## Source-Backed Rationale

The AutoResearch loop prioritizes real app smokes for launch risks that are visible only after browser state, local storage, routing, and API calls interact. The existing admin browser smoke proved QR-token and sensor-device happy paths with an operator token, but it did not prove the same UI failed closed when that token was missing.

## A/B Hypothesis

Baseline: `admin_routes_browser_smoke.py` seeded a product and exercised the operator-authenticated QR-token and sensor-device routes. It recorded 8 passing checks, but none covered anonymous admin behavior.

Variant: run an anonymous browser context first, with `agriguard-operator-token` removed from local storage, and assert protected actions return visible 401 authorization failures. Then run the existing operator-authenticated happy path in a separate page.

Adopt rule: adopt only if the expanded smoke records the expected fail-closed checks and still passes the operator happy path, focused compile, and full AgriGuard smoke scope.

## Adopted Change

- Added `MISSING_AUTH_DETAIL = "Authorization header missing"` to `scripts/admin_routes_browser_smoke.py`.
- Added anonymous QR-token checks:
  - no-token notice is visible
  - `Load tokens` triggers a 401 response for `/qr-tokens/products/...`
  - the missing authorization message is visible
- Added anonymous sensor-device checks:
  - no-token notice is visible
  - `Register sensor` triggers a 401 response for `PUT /sensor-devices/...`
  - the missing authorization message is visible
- Kept the existing operator-token context and happy-path checks after the anonymous checks.

## Browser Evidence

Baseline happy-path artifact:

`D:\AI project\var\agriguard-browser-click-2026-07-04\admin-routes-rerun.json`

Result: `status=pass`, 8 checks, 0 failed checks.

Variant artifact:

`D:\AI project\var\agriguard-admin-failclosed-browser-2026-07-04\admin-failclosed-variant-fixed.json`

Result: `status=pass`, 12 checks, 0 failed checks.

Variant check names:

- `seed_product`
- `qr_tokens_missing_token_notice_visible`
- `qr_tokens_missing_token_blocked`
- `sensor_devices_missing_token_notice_visible`
- `sensor_devices_missing_token_blocked`
- `qr_tokens_loaded`
- `qr_token_reissued`
- `sensor_registered`
- `mqtt_broker_provisioning_rendered`
- `no_page_errors`
- `no_request_failures`
- `no_console_errors`

Screenshots were written under:

`D:\AI project\var\agriguard-admin-failclosed-browser-2026-07-04\admin-failclosed-variant-fixed-screens`

## Verification

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/scripts/admin_routes_browser_smoke.py'
```

Result: pass.

```powershell
python apps/AgriGuard/scripts/admin_routes_browser_smoke.py --base-url http://127.0.0.1:5192 --api-url http://127.0.0.1:8006 --operator-token browser-smoke-token --json-out var/agriguard-admin-failclosed-browser-2026-07-04/admin-failclosed-variant-fixed.json --screenshot-dir var/agriguard-admin-failclosed-browser-2026-07-04/admin-failclosed-variant-fixed-screens --timeout-ms 30000
```

Result: `admin routes browser smoke pass`.

An intermediate variant failed because `get_by_text("Authorization header missing")` matched multiple expected sensor-page errors in Playwright strict mode. The final variant uses `.first` for that expected repeated auth message.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-admin-failclosed-browser-smoke.json
```

Result: `passed=5, failed=0, total=5` in `4m26s`.

Slowest checks:

- `agriguard backend tests`: pass in `3m50s`
- `agriguard frontend lint`: pass in `11.9s`
- `agriguard frontend build`: pass in `11.7s`
- `agriguard contracts tests`: pass in `8.9s`
- `agriguard contracts compile`: pass in `3.3s`

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-admin-failclosed-browser-smoke.json`

## Current Launch State

AgriGuard admin browser evidence now covers both sides of the protected route contract: anonymous users see blocked protected actions, while operator-authenticated users can still manage QR tokens and sensor devices through the browser workflow.
