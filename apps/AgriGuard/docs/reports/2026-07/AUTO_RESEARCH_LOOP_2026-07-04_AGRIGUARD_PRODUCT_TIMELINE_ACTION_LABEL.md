# AutoResearch Loop - AgriGuard Product Timeline Action Label

- Date: 2026-07-04
- Scope: `apps/AgriGuard`
- Slice: product-detail timeline event contract
- External context: `Veritas-7/autoresearch-skill-system` main was refreshed at `b8bbf393759d6e67e780f03c572ec626fab6593b`; the workspace modernization radar recorded 8 source-backed patterns as already adopted.

## Source-Backed Rationale

The product-detail browser smoke exposed a launch-visible defect: tracking updates were saved and shown in the blockchain timeline, but the timeline card title rendered `UNKNOWN EVENT`. The frontend timeline component keys its title and icon off `data.action`, while the tracking route only logged `status`.

## A/B Hypothesis

Baseline: tracking chain events contained `status=IN_TRANSIT` but no `action`, so product detail timelines rendered tracking rows as `UNKNOWN EVENT`.

Variant: keep the existing `status` field and add normalized `action=status.upper()` to the chain event payload emitted by `POST /products/{product_id}/track`.

Adopt rule: adopt only if the backend contract test passes, the product-detail browser smoke confirms no `UNKNOWN EVENT`, and the full AgriGuard smoke scope stays green.

## Adopted Change

- Updated `backend/routers/products.py` so tracking chain events include `action`.
- Added `backend/tests/test_product_timeline_action_contract.py`, an isolated contract test for the tracking chain payload.
- Tightened `scripts/product_detail_browser_smoke.py` with `tracking_event_action_label_visible`, which fails if the final timeline contains `UNKNOWN EVENT`.

## Browser Evidence

Artifact:

`D:\AI project\var\agriguard-product-timeline-action-browser-2026-07-04\product-detail-timeline-action-mobile.json`

Result: `status=pass`, 18 checks, 0 failed checks, viewport `390x844`.

Evidence summary:

- `tracking_event_action_label_visible=true`
- final body sample contains `IN_TRANSIT`
- final body sample does not contain `UNKNOWN EVENT`

## Verification

### Focused Checks

```powershell
python -m py_compile 'apps/AgriGuard/backend/routers/products.py' 'apps/AgriGuard/backend/tests/test_product_timeline_action_contract.py' 'apps/AgriGuard/scripts/product_detail_browser_smoke.py'
```

Result: pass.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_product_timeline_action_contract.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-product-timeline-action-contract'
```

Result: `1 passed, 1 warning in 3.56s`.

```powershell
uv run --isolated --no-project --with 'pytest>=8.0' --with 'pytest-asyncio>=0.23.0' --with-editable 'D:\AI project' --with-editable 'D:\AI project\apps\AgriGuard\backend' python -m pytest tests/test_product_and_qr_routes.py -q --basetemp 'D:\AI project\var\tmp\pytest-agriguard-product-timeline-action-full'
```

Result: `41 passed, 1 warning in 6.61s`.

### Workspace Smoke

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-product-timeline-action.json
```

Result: `passed=5, failed=0, total=5` in `5m24s`.

Slowest checks:

- `agriguard backend tests`: pass in `4m51s`
- `agriguard frontend lint`: pass in `11.3s`
- `agriguard contracts tests`: pass in `9.1s`
- `agriguard frontend build`: pass in `8.6s`
- `agriguard contracts compile`: pass in `3.4s`

Smoke artifact: `D:\AI project\var\workspace-smoke-agriguard-product-timeline-action.json`

## Current Launch State

Product-detail tracking events now render as concrete timeline actions instead of `UNKNOWN EVENT`, while preserving the existing `status`, location, handler, and timestamp payload fields.
