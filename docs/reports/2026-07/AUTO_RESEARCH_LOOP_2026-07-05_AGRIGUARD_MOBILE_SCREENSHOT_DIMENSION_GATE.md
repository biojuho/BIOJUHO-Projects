# AgriGuard Mobile Screenshot Dimension Gate

Date: 2026-07-05

## Loop

- External source refresh: `Veritas-7/autoresearch-skill-system` main/HEAD observed at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Baseline: `run_browser_smoke_suite.py` validated screenshot existence, PNG headers, byte size, and dimensions, but mobile mode did not fail if a child emitted non-viewport screenshots.
- Variant shipped: mobile aggregate browser runs now require every child screenshot artifact to be exactly `390x844`. Desktop behavior remains unchanged.
- Adoption rule: adopt only if the full mobile suite has zero dimension failures and canonical smoke scopes remain green.

## Browser Evidence

Command:

```powershell
python apps\AgriGuard\scripts\run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-mobile-screenshot-dimensions.json --output-dir var\agriguard-browser-smoke-suite-mobile-screenshot-dimensions --timeout-ms 30000
```

Result: 6/6 steps, 150/150 checks, 18/18 screenshots.

Aggregate screenshot gate:

- `screenshot_artifacts_total`: 18
- `screenshot_artifacts_failed`: 0
- `screenshot_artifact_dimension_failures`: `[]`

## Verification

- `python -m py_compile apps\AgriGuard\scripts\run_browser_smoke_suite.py apps\AgriGuard\backend\tests\test_smoke.py`: passed.
- `uv run --isolated --no-project --with pytest>=8.0 --with pytest-asyncio>=0.23.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-suite-screenshot-dimensions"`: 44 passed.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-mobile-screenshot-dimensions.json`: complete, 5/5 passed.
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-mobile-screenshot-dimensions.json`: complete, 9/9 passed.

## Decision

Adopted. The aggregate launch browser suite now fails closed if a future mobile child returns misleading full-page or otherwise non-viewport screenshots.
