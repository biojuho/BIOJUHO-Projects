# DeSci Platform Stack Alignment

Last updated: 2026-05-11

This file records how the requested stack maps onto the current project without
forcing a risky rewrite.

## Current Runtime

- Frontend: React 19, Vite, JavaScript, Tailwind CSS, Zustand, Firebase client.
- API: Python FastAPI in `biolinker` and the legacy `backend` app.
- Auth/data today: Firebase Auth and some Firestore-backed flows.
- Search/storage: Chroma/Qdrant for vector search, IPFS/Pinata for durable
  research asset storage.
- Contracts: Hardhat/Solidity package under `contracts`.

## Adopted Direction

- Frontend primary: React + Vite.
- Frontend standard going forward: TypeScript for new modules, TanStack Query
  for server state, and the browser Fetch API via `src/services/api.js`.
- Svelte: keep as a future experimental/micro-frontend option only. Do not mix
  Svelte and React in the primary app shell unless there is a specific product
  reason.
- Backend primary today: FastAPI remains the orchestration API while the product
  is still moving quickly.
- Rust: reserve for high-throughput crawlers, PDF/vector indexing, and other
  CPU-sensitive services.
- Go: reserve for queue workers, webhook relays, and lightweight service
  gateways where operational simplicity matters.
- Database target: Supabase/PostgreSQL as the canonical relational store.
  Firestore remains a legacy/current integration until auth and user data are
  migrated.
- Mobile: Flutter first for cross-platform product surfaces. Native Swift/Kotlin
  should be used for platform-specific integrations that Flutter cannot cover
  cleanly.
- Infra: Redis for cache/rate/session-style ephemeral state, RabbitMQ for async
  jobs such as crawl, parse, match, notify, and webhook workflows.

## Research Note

- The product direction also reflects the interaction pattern highlighted by
  MiniCPM-o 4.5 (arXiv:2604.27393): move from purely turn-based/reactive AI
  screens toward streaming, continuously updated, proactive assistance. In this
  codebase that translates first into SSE job progress, operator readiness
  signals, and support diagnostics before adding richer multimodal surfaces.

## What Is Now Reflected

- `frontend` now has `@tanstack/react-query`, a shared QueryClient, and a
  fetch-based API client that preserves the existing `api.get/post` call style.
- `frontend` has a TypeScript baseline (`tsconfig.json` and `npm run typecheck`)
  so new files can move toward TS incrementally.
- `docker-compose.yml` has an optional `infra` profile for Postgres, Redis, and
  RabbitMQ.
- `.env.example` files include `DATABASE_URL`, Supabase, Redis, and RabbitMQ
  variables.
- `supabase/migrations/0001_core_schema.sql` provides a first relational schema
  baseline for profiles, notices, assets, matches, subscriptions, governance,
  and audit events.
- `/health` reports whether Postgres/Supabase, Redis, and RabbitMQ are
  configured, and now also pings RabbitMQ when it is configured.
- `/ready` summarizes launch-readiness checks for required product
  dependencies and optional production services.
- API responses include `X-Request-ID`, response-time, and browser-hardening
  headers so production incidents can be traced from user reports to logs.
- The shared frontend fetch client sends `X-Request-ID` on every request,
  preserves backend request IDs on `ApiError`, and surfaces support IDs in
  important toasts and the copyable error-boundary diagnostics panel.
- Governance proposal list/create/vote endpoints now use Postgres first when
  `DATABASE_URL` is configured, then fall back to the existing Firestore/mock
  path.
- Monthly usage counters now use Redis first when `REDIS_URL` is configured,
  with atomic increments and the existing cache/Firestore path as fallback.
- Long-running work has a first job pipeline:
  - `POST /jobs/notices/collect` creates a notice-collection job.
  - `POST /jobs/papers/index` creates a PDF parsing/vector-index refresh job
    for an uploaded paper.
  - `POST /jobs/match/paper` creates a paper-to-RFP matching job.
  - `POST /jobs/proposal/generate` creates an AI proposal generation job.
  - `GET /jobs/{job_id}` returns progress, result, and event history.
  - `GET /jobs/{job_id}/events` streams progress as server-sent events.
  - User-scoped job endpoints require auth and enforce paper ownership before
    job creation or job reads.
  - Jobs mirror snapshots into Redis when `REDIS_URL` is configured, with an
    in-memory fallback for local execution.
  - The current API runtime executes jobs in-process and exposes the same
    snapshot contract for polling and SSE clients.
- The Funding Radar frontend now starts notice collection through the job API
  and shows live progress before refreshing the notice list.
- Research Submission saves a local paper manifest after upload so the API and
  worker can re-parse and refresh the vector index through the job API.
- Match Studio now runs paper matching and proposal generation through the job
  API, surfacing progress while the AI workflow runs.
- The frontend has a shared `useJobProgress` hook that consumes job SSE streams
  first and falls back to polling if EventSource is unavailable.
- The Dashboard now includes a Product Readiness panel that calls `/ready` and
  turns backend health into an operator-facing launch checklist.
- `scripts/product_smoke.py` checks the live API, `/health`, `/ready`, and
  frontend URL before demos or deployments.

## Rollout Phases

1. Keep shipping on the React/FastAPI path while new frontend data fetching uses
   TanStack Query and the shared fetch API client.
2. Introduce Supabase/Postgres writes behind backend endpoints first; avoid
   direct browser writes until Supabase Auth ownership is decided.
3. Move Firestore-backed usage, governance, and profile data into Postgres using
   the migration baseline.
4. Add Redis caching for hot reads and rate/usage counters where it reduces
   Firestore/Postgres pressure.
5. Add RabbitMQ workers for crawl, parse, vector-index, proposal, and
   notification jobs. Notice collection, paper indexing, paper matching, and
   proposal generation now use the shared worker path.
6. Split Rust/Go services only when a workload has clear throughput,
   concurrency, or deployment reasons.
7. Start Flutter after the API contracts stabilize; keep native modules narrow
   and platform-specific.

## Local Commands

```bash
cd apps/desci-platform
docker compose --profile infra up postgres redis rabbitmq
```

```bash
cd apps/desci-platform
docker compose --profile infra up biolinker-worker
```

```bash
cd apps/desci-platform/backend
python worker.py
```

```bash
cd apps/desci-platform/frontend
npm run typecheck
npm test
```
