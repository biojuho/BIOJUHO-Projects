# DeSci Platform Frontend

React 19 + Vite frontend for DSCI-DecentBio. The app is an operator-style product surface for research submission, funding discovery, paper-to-RFP matching, investor views, rewards, and governance.

## Stack

- React 19 and Vite
- Tailwind CSS design tokens
- TanStack Query for server state
- Shared Fetch API client in `src/services/api.js`
- Incremental TypeScript baseline via `tsconfig.json`
- EventSource/SSE job progress with polling fallback

## Product Surfaces

- Dashboard: KPI overview, quick actions, product readiness, investor/recommendation summaries
- Funding Radar: notices, filters, and async collection jobs
- Research Submission: PDF upload, IPFS registration, and async vector indexing
- Match Studio: RFP analysis, paper matching, proposal generation, literature review
- Investor View: explainable VC fit and deal flow
- Research Vault / Wallet / Governance: trust and reward operations

## Job Progress

Long-running workflows use backend jobs and stream progress through:

```text
GET /jobs/{job_id}/events
```

When `EventSource` is unavailable, `useJobProgress` falls back to `GET /jobs/{job_id}` polling.

## Product Readiness

The dashboard calls:

```text
GET /ready
```

and renders required vs optional launch checks for API, auth, vector search, LLM, PostgreSQL/Supabase, Redis, RabbitMQ, IPFS, Web3, and GROBID.

## Support Diagnostics

- The shared Fetch API client attaches `X-Request-ID` to every request.
- `ApiError` exposes `requestId` and `responseTimeMs` from backend responses.
- Key API failure toasts include the support ID, and the app error boundary shows a copyable diagnostics payload for support handoff.

## Local Development

```bash
npm install
npm run dev
```

Set `VITE_API_BASE_URL` when the backend is not running on `http://127.0.0.1:8000`.

## Quality Gate

```bash
npm run lint
npm run typecheck
npm run test
npm run build:lts
npm run check:bundle
```

With the API and frontend running, add a browser-level smoke check:

```bash
python ../scripts/browser_smoke.py --frontend http://127.0.0.1:5173
```
