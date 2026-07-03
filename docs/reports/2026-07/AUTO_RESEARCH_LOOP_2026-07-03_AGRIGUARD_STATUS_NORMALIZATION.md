# AutoResearch Loop - AgriGuard Supply Chain Status Normalization

Date: 2026-07-03

## Objective

Remove the user-visible `Unknown Status` label from supply-chain cards when backend tracking history contains valid seed/runtime labels such as `Quality Check Passed` or `Delivered to Warehouse`.

## Observation

The supply-chain browser smoke screenshot showed a searched product with real tracking history, but the card rendered:

- `Current Status: Unknown Status`

The backend seed/runtime statuses include human-readable labels:

- `Planted`
- `Harvested`
- `In Transit`
- `Delivered to Warehouse`
- `Quality Check Passed`

The UI status flow expects canonical status keys:

- `REGISTERED`
- `IN_TRANSIT`
- `DELIVERED`
- `VERIFIED`

## Adopted Change

- Normalize backend tracking labels before status rendering.
- Select the latest tracking event by timestamp, with array order as the fallback tie breaker.
- Map `Quality Check Passed` to `VERIFIED`.
- Map `Delivered to Warehouse` to `DELIVERED`.
- Map `Planted` and `Harvested` to `REGISTERED`.
- Keep truly unknown statuses visible as `Unknown Status`.

## Verification

```powershell
npm run test -- SupplyChain.test.jsx
npm run lint
npm run build:lts
python apps\AgriGuard\scripts\supply_chain_browser_smoke.py --url http://127.0.0.1:5174/supply-chain?smoke=status-normalization --json-out var\agriguard-supply-chain-browser-smoke-status-normalization.json --screenshot var\agriguard-supply-chain-browser-smoke-status-normalization.png --operator-token browser-smoke-token --timeout-ms 30000
```

Results:

- SupplyChain targeted test: 1 file passed, 3 tests passed
- Frontend lint: passed
- Frontend build: passed
- Browser smoke: `19/19 PASS`
- Browser JSON text sample includes `Current Status: Delivered & Available`
- Browser JSON text sample has no `Unknown Status` for the searched product
- Screenshot: `var/agriguard-supply-chain-browser-smoke-status-normalization.png`
- JSON: `var/agriguard-supply-chain-browser-smoke-status-normalization.json`
