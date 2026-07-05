# AgriGuard AutoResearch Loop: Credential Field Autocomplete Gate

Date: 2026-07-06

## Source Basis

- Veritas source check: `https://github.com/Veritas-7/autoresearch-skill-system.git` `HEAD/main` = `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- MDN autocomplete attribute: `https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/autocomplete`
- MDN form autocompletion security guide: `https://developer.mozilla.org/en-US/docs/Web/Security/Practical_implementation_guides/Turning_off_form_autocompletion`
- MDN spellcheck attribute: `https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/spellcheck`
- HTML standard autocomplete reference: `https://html.spec.whatwg.org/multipage/form-control-infrastructure.html`

## A/B Hypothesis

- Baseline: operator-token and broker-provisioning inputs were labeled, but credential-like fields did not declare autocomplete behavior and sensitive note/path fields did not disable browser spellchecking.
- Variant: add `autoComplete="off"` and `spellCheck={false}` only to operator/security fields, then extend nav smoke so visible credential-like fields fail semantic accessibility if they have no explicit autocomplete value.
- Decision rule: adopt only if focused tests, build, real-browser credential probe, nav smoke, desktop/mobile browser suites, AgriGuard smoke, and workspace smoke pass.

## Adopted Changes

- `Dashboard.jsx`: protected the dashboard operator token recovery field.
- `QRTokenManager.jsx`: protected the QR operator token field.
- `SensorDeviceManager.jsx`: protected the sensor operator token, broker password-file path, and no-secrets evidence note fields.
- `nav_browser_smoke.py`: added `credentialAutocompleteGaps` to route semantic checks.
- Tests now assert `autocomplete="off"` and `spellcheck="false"` for the affected fields, and backend smoke-helper tests assert the new gate fails closed.

## Evidence

- Focused frontend tests:
  - `npm run test -- Dashboard.test.jsx QRTokenManager.test.jsx SensorDeviceManager.test.jsx`
  - Result: 3 files passed, 32 tests passed.
- Focused backend smoke helper tests:
  - `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest tests\test_smoke.py -q -k "nav_browser_smoke"`
  - Result: 4 passed, 44 deselected.
- Frontend production build: `npm run build:lts`
  - Result: pass.
- Browser credential probe on `http://127.0.0.1:5196`:
  - Dashboard: `dashboard-operator-token` reported `autocomplete=off`, `spellcheck=false`.
  - QR Tokens: `operator-token` reported `autocomplete=off`, `spellcheck=false`.
  - Sensors: `sensor-operator-token`, `provisioning-password-file`, and `provisioning-evidence-note` reported `autocomplete=off`, `spellcheck=false`.
- Mobile nav smoke with credential autocomplete gate:
  - `python apps\AgriGuard\scripts\nav_browser_smoke.py --base-url http://127.0.0.1:5196 --operator-token browser-smoke-token --click-nav --json-out var\agriguard-nav-mobile-credential-autocomplete-2026-07-06.json --screenshot-dir var\agriguard-nav-mobile-credential-autocomplete-2026-07-06 --timeout-ms 30000 --mobile`
  - Result: 58/58 PASS.
  - Every route reported `credentialAutocompleteGaps=[]`.
- Full desktop browser smoke:
  - `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5196 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-desktop-credential-autocomplete-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-desktop-credential-autocomplete-2026-07-06 --timeout-ms 30000 --include-unavailable-check`
  - Result: 7/7 steps passed, 166/166 checks passed, 19/19 screenshot artifacts passed.
- Full mobile browser smoke:
  - `python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5196 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-suite-mobile-credential-autocomplete-2026-07-06.json --output-dir var\agriguard-browser-smoke-suite-mobile-credential-autocomplete-2026-07-06 --timeout-ms 30000 --mobile --include-unavailable-check`
  - Result: 7/7 steps passed, 173/173 checks passed, 19/19 screenshot artifacts passed.
- AgriGuard smoke:
  - First run hit the 5-minute tool timeout before returning output.
  - Rerun with a longer timeout: `python ops\scripts\run_workspace_smoke.py --scope agriguard`
  - Result: 5/5 passed.
- Workspace smoke: `python ops\scripts\run_workspace_smoke.py --scope workspace`
  - Result: 9/9 passed.

## Launch Status

- Guarded launch status command:
  - `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --status-json-out var\agriguard-guarded-launch-status-credential-autocomplete-2026-07-06.json`
- Result: `status=blocked`, `blocker_class=preflight_blocked`.
- Remaining blocker is external/operator-owned: `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`
- Operator action ID remains `set_firebase_service_account_file`.
