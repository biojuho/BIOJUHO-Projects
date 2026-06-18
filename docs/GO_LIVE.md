# Go-Live Checklist

Single source of truth for taking the workspace's deployable services live.
The **code is launch-ready and verified-running** (see per-service notes);
what remains is supplying credentials. Run the env preflight first:

```bash
python apps/desci-platform/scripts/env_doctor.py   # target: 0 warnings
```

---

## 1. DeSci backend (BioLinker) → Railway

- **Config**: `apps/desci-platform/railway.json` (Dockerfile `backend/Dockerfile`, healthcheck `/health`). Verified valid.
- **Runtime status**: starts healthy; `GET /health` → `{"status":"healthy",...}`, 54 API routes.
- **Required env** (set in the Railway service, see `env_doctor` for the full list):
  - `DATABASE_URL` (production PostgreSQL)
  - `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`
  - `GOOGLE_APPLICATION_CREDENTIALS` or `FIREBASE_SERVICE_ACCOUNT_JSON`
  - At least one LLM key (`GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / …)
  - `ALLOWED_ORIGINS` (deployed frontend origin), `DESCI_FRONTEND_URL`
  - `REDIS_URL`, `RABBITMQ_URL`, `PINATA_JWT` (optional features)
  - Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_YEARLY`
  - Web3 (optional): `WEB3_RPC_URL` + contract addresses; keep `DISTRIBUTOR_PRIVATE_KEY` in a secret manager
- **Deploy**: `cd apps/desci-platform/backend && railway up` (or `scripts/deploy.sh backend`).

## 2. DeSci frontend → Vercel

- **Config**: `apps/desci-platform/frontend/vercel.json` (`build:lts`, node 24.15, SPA + `/api` proxy). Security headers set. Verified building.
- **Required env**:
  - `VITE_API_BASE_URL` → the deployed Railway backend HTTPS URL
  - `VITE_FIREBASE_*` (project config)
  - Wallet (optional): `VITE_WALLET_CHAIN_ID=80002`, `VITE_DSCI_TOKEN_ADDRESS`, `VITE_RESEARCH_PAPER_NFT_ADDRESS`
- **Also update** `vercel.json` `rewrites[].destination` from the `your-biolinker-api.railway.app` placeholder to the real backend URL.
- **Deploy**: `cd apps/desci-platform/frontend && vercel deploy --prod` (or `scripts/deploy.sh frontend`).

> One-command path for both: `apps/desci-platform/scripts/deploy.sh` (supports `--dry-run`).

## 3. Dashboard → Google Cloud Run

- **Workflow**: `.github/workflows/deploy-dashboard.yml` (auto on `apps/dashboard/**` push, or `workflow_dispatch`).
- **Blocked since 2026-04**: the GCP auth step fails because these repo secrets are **not set** (only `GOOGLE_API_KEY` exists):
  - `GCP_CREDENTIALS` (service-account JSON)
  - `GCP_PROJECT_ID`
  - `SUPABASE_DATABASE_URL`
- **Deploy**: add the three secrets, then the next `apps/dashboard/**` push (or a manual `workflow_dispatch` run) deploys to Cloud Run.

## 4. AgriGuard → Docker

- **Backend**: `apps/AgriGuard/backend/Dockerfile`; `GET /health` now returns `{"status":"healthy","database":...}`. Runs with `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_ORIGINS`.
- **Frontend**: `apps/AgriGuard/frontend/Dockerfile` (Vite build).
- Compose: root `docker-compose.yml` build contexts verified (`docker compose config` valid).

---

## Known follow-ups
- `.github/workflows/ci.yml` `desci-backend` job still has `working-directory: apps/desci-platform/biolinker` (moved to `backend/`) — repoint it so the backend CI job runs.
