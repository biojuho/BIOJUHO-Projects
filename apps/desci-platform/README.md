# DSCI-DecentBio

DSCI-DecentBio is a DeSci operating system for research teams, funders, and
operators. It connects paper intake, funding discovery, AI-assisted matching,
proposal drafting, IPFS/Web3 asset workflows, governance, and launch readiness
into one product surface.

## What Is Built

- Research submission: upload PDFs, capture metadata, index papers, and prepare IP-NFT minting.
- Funding radar: collect KDDF/NTIS style notices and normalize them for search.
- Match studio: match papers and researcher profiles against funding calls.
- Proposal generation: draft grant/proposal material from the matched context.
- Investor and asset views: expose research assets, readiness signals, and Web3 status.
- Governance hub: create proposals, track voting, and inspect execution state.
- Launch control: `/ready` exposes subsystem checks and `/launch` returns an operator go/no-go decision.

## System Shape

- Frontend: React, Vite, TanStack Query, Vitest, Playwright smoke coverage.
- Backend: FastAPI, async job API, SSE job progress, Redis-backed fallback state, RabbitMQ worker option.
- Data: PostgreSQL/Supabase migration path, local vector store, Qdrant-compatible boundary.
- Web3/storage: Hardhat 3 contracts, local deploy smoke scripts, IPFS/Pinata integration.
- Operations: env doctor, product smoke, browser smoke, one-command release gate.

See [STACK_ALIGNMENT.md](./STACK_ALIGNMENT.md) for the architecture alignment notes.

## Quick Start

Start infrastructure plus the worker when you want the full local system:

```bash
cd apps/desci-platform
docker compose --profile infra up postgres redis rabbitmq backend-worker
```

Run the backend:

```bash
cd apps/desci-platform/backend
uv sync --extra dev
uv run uvicorn main:app --reload
```

Run the frontend:

```bash
cd apps/desci-platform/frontend
npm install
npm run dev
```

Run contract checks:

```bash
cd apps/desci-platform/contracts
npm install
npm run test
```

## Launch Control

The product has two operator-facing readiness endpoints:

- `GET /ready`: raw subsystem readiness checks with pass/warn/fail status.
- `GET /launch`: final operator decision with `go`, `go-with-watch`, or `no-go`.

Use strict smoke checks before a public demo or production handoff:

```bash
cd apps/desci-platform
python scripts/product_smoke.py --strict-ready --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173
```

## Release Gate

Run the full local release gate:

```bash
cd apps/desci-platform
python scripts/release_gate.py --json-out ../../var/desci-release-gate.json
```

For a full diagnostic report even after a failure:

```bash
python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate.json
```

The gate validates environment readiness, Docker Compose config, backend tests,
frontend lint/typecheck/tests/build/bundle budget, contract build/tests, and
local contract deployment smoke scripts.

## Production Environment Checklist

Required before public launch:

- `ENV=production`
- At least one LLM key: `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, or `ANTHROPIC_API_KEY`
- Auth credentials: `GOOGLE_APPLICATION_CREDENTIALS`, `FIREBASE_PROJECT_ID`, or `FIREBASE_SERVICE_ACCOUNT_JSON`
- Frontend Firebase keys: all `VITE_FIREBASE_*` values
- `VITE_API_BASE_URL` and `ALLOWED_ORIGINS`
- `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_URL` and `RABBITMQ_URL`

Recommended before public minting or paid checkout:

- `PINATA_JWT` or Pinata API key/secret pair
- `WEB3_RPC_URL` plus deployed DSCI/NFT/DAO contract addresses
- Stripe secret key, webhook secret, and price IDs

Run the preflight directly:

```bash
cd apps/desci-platform
python scripts/env_doctor.py --profile production --env-file .env.production --ignore-process-env
```

## Key API Surface

- `GET /health`: subsystem health and integration availability.
- `GET /ready`: launch-readiness checks.
- `GET /launch`: operator go/no-go decision.
- `GET /jobs/{job_id}`: background job state.
- `GET /jobs/{job_id}/events`: SSE progress stream.
- `POST /jobs/notices/collect`: collect funding notices.
- `POST /jobs/papers/index`: index papers.
- `POST /jobs/match/paper`: match papers to notices.
- `POST /jobs/proposal/generate`: generate proposal drafts.

## More Operations Docs

- [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md)
- [API_SPEC.md](./API_SPEC.md)
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- [QC_LOG.md](./QC_LOG.md)
