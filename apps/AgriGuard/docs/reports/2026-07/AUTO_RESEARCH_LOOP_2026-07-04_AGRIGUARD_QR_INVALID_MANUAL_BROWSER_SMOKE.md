# AutoResearch Loop - AgriGuard QR Invalid Manual Browser Smoke

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: QR scanner manual-entry recovery coverage
- External context: `Veritas-7/autoresearch-skill-system` main was refreshed at `b8bbf393759d6e67e780f03c572ec626fab6593b`; the workspace modernization radar recorded 8 source-backed patterns as already adopted.

## Source-Backed Rationale

The AutoResearch loop calls for browser/app smokes when the risk is an end-user workflow rather than a pure function. AgriGuard already had a QR scanner smoke that covered the normal manual token path and the invalid public verification page. It did not click the invalid manual-entry branch on `/scan`, which is the path a consumer uses when the camera is unavailable or a pasted value is malformed.

## A/B Hypothesis

Baseline: the QR path browser smoke proved the happy manual token path and invalid `/verify/:token` rendering, but it did not assert that a malformed manual value stays on `/scan`, shows a useful error, exposes retry, and keeps recovery possible.

Variant: add an invalid manual-entry click before the valid token click, then continue through the existing valid and invalid verification checks.

Adopt rule: adopt only if the variant passes the expanded QR browser smoke, focused unit coverage, and the full AgriGuard smoke scope.

## Adopted Change

- Added `--invalid-manual-value` to `scripts/qr_path_browser_smoke.py`.
- Added a browser assertion block that fills a malformed manual value, clicks `Verify code`, and checks:
  - invalid manual error copy is visible
  - retry control is visible
  - scanner paused state is visible
  - the browser remains on `/scan`
- Kept the existing valid manual token and invalid public verification checks after the new recovery probe.
- Added `backend/tests/test_smoke.py::test_qr_path_browser_smoke_keeps_invalid_manual_probe_distinct` so the invalid probe cannot silently duplicate the valid token or invalid public token defaults.

## Browser Evidence

All browser evidence was recorded under:

`D:\AI project\var\agriguard-qr-path-browser-2026-07-04`

### Baseline

```powershell
python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5190 --manual-token mock-0 --invalid-token not-a-real-token --json-out var/agriguard-qr-path-browser-2026-07-04/qr-path-baseline.json --screenshot-dir var/agriguard-qr-path-browser-2026-07-04/qr-path-baseline-screens --timeout-ms 30000
```

Result: `17/17 PASS`, `ok=true`, viewport `390x844`. No invalid-manual-entry observation was recorded.

### Variant

```powershell
python apps/AgriGuard/scripts/qr_path_browser_smoke.py --base-url http://127.0.0.1:5190 --manual-token mock-0 --invalid-token not-a-real-token --json-out var/agriguard-qr-path-browser-2026-07-04/qr-path-invalid-manual-variant.json --screenshot-dir var/agriguard-qr-path-browser-2026-07-04/qr-path-invalid-manual-variant-screens --timeout-ms 30000
```

Result: `21/21 PASS`, `ok=true`, viewport `390x844`, 0 failed checks.

Recorded invalid-manual observation:

- `invalid_manual_present=true`
- `invalid_manual_error_visible=true`
- `invalid_manual_still_on_scan=true`

## Verification

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/scripts/qr_path_browser_smoke.py' 'apps/AgriGuard/backend/tests/test_smoke.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_smoke.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-qr-path-smoke-full'
```

Result: `8 passed in 36.94s`.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-qr-invalid-manual-browser-smoke.json
```

Result: `passed=5, failed=0, total=5` in `5m45s`.

Slowest checks:

- `agriguard backend tests`: pass in `5m6s`
- `agriguard frontend lint`: pass in `15.3s`
- `agriguard frontend build`: pass in `11.4s`
- `agriguard contracts tests`: pass in `9.4s`
- `agriguard contracts compile`: pass in `3.3s`

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-qr-invalid-manual-browser-smoke.json`

## Current Launch State

The QR scanner smoke now covers the consumer's malformed manual-entry recovery path before proving the successful manual verification path and invalid public verification page. This gives AgriGuard stronger browser-level launch evidence for the QR flow without changing runtime product behavior.
