# AutoResearch AgriGuard Browser Pass - 2026-06-04

## Scope

- App: `apps/AgriGuard`
- Frontend: Vite on `http://localhost:5173`
- Backend: `python -m uvicorn main:app --host 127.0.0.1 --port 8002` from `apps/AgriGuard/backend`
- Method: Playwright browser navigation/click pass plus direct API probes.
- Intent: product-readiness evidence for the AutoResearch/Karpathy loop without staging unrelated dirty AgriGuard source changes.

## Evidence

- Backend direct probes:
  - `GET http://127.0.0.1:8002/dashboard/summary` returned `200`.
  - `GET http://127.0.0.1:8002/products/` returned `502` products.
- Browser routes checked:
  - `http://localhost:5173/`
  - `http://localhost:5173/registry`
  - `http://localhost:5173/scan`
  - `http://localhost:5173/supply-chain`
  - `http://localhost:5173/cold-chain`
  - `http://localhost:5173/product/dbb58381-d19a-49dd-8b9f-c4ae47107c2a`
- Local snapshots captured:
  - `agriguard-dashboard-localhost-loaded.md`
  - `agriguard-registry-localhost-loaded.md`
  - `agriguard-scan-localhost-loaded.md`
  - `agriguard-supply-chain-localhost-loaded.md`
  - `agriguard-cold-chain-localhost-loaded.md`
  - `agriguard-product-detail-localhost-loaded.md`
  - `agriguard-console-warnings-localhost.md`

## Result

Core routes render when the browser uses `http://localhost:5173`. Dashboard, registry, scanner, cold-chain monitor, and product detail load without Playwright-reported page errors. Product detail exposes the expected back navigation, QR/product content, and action buttons for tracking/certification.

`http://127.0.0.1:5173` is not currently an equivalent local entrypoint. The frontend default API origin is `http://localhost:8002`, while backend `ALLOWED_ORIGINS` defaults include `http://localhost:5173` but not `http://127.0.0.1:5173`. Opening the app at `127.0.0.1` therefore produces a CORS failure and the dashboard fallback message even though the backend is healthy.

## Findings

1. Supply-chain route renders all products at once.
   - `GET /products/` returned `502` rows.
   - `/supply-chain` rendered a document around `123,955px` tall in the accessibility snapshot.
   - Launch fix: paginate, virtualize, or cap the default query and provide explicit filtering.

2. Localhost/127.0.0.1 origin mismatch can look like backend downtime.
   - `http://localhost:5173` works with the default backend CORS config.
   - `http://127.0.0.1:5173` fails against the default `http://localhost:8002` API origin.
   - Launch fix: document the canonical local URL, include `127.0.0.1` in dev `ALLOWED_ORIGINS`, or set `VITE_API_URL` consistently in the dev runner.

3. Manifest icon is missing or invalid.
   - Browser warning: `Error while trying to use the following icon from the Manifest: http://localhost:5173/icons/icon-192.png`.
   - Launch fix: add a valid `public/icons/icon-192.png` asset or remove the manifest reference.

4. Dashboard chart containers emit Recharts sizing warnings.
   - Warning: `The width(-1) and height(-1) of chart should be greater than 0`.
   - Launch fix: give chart containers stable dimensions/min sizes and defer chart rendering until parent layout is measurable.

5. Cold-chain IoT WebSocket does not complete in the current dev route.
   - Warning: `WebSocket connection to 'ws://localhost:5173/api/ws/iot' failed: WebSocket is closed before the connection is established`.
   - Launch fix: verify Vite proxy websocket forwarding and backend websocket readiness for `/api/ws/iot`.

## Next Action

Treat item 1 as the highest product-readiness blocker. A supply-chain page that renders 500+ full cards by default will be slow, hard to scan, and likely brittle under larger datasets even when the API is healthy.
