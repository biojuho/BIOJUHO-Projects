# DSCI-DecentBio Operations Runbook

This runbook is the release gate for a production-like launch.

## 1. One-Command Release Gate

Run the local release gate before handing the build to deployment:

```bash
cd apps/desci-platform
python scripts/release_gate.py --json-out ../../var/desci-release-gate.json
```

In CI environments that use uv-managed Python dependencies, run:

```bash
uv run python apps/desci-platform/scripts/release_gate.py --python-command "uv run python"
```

The gate runs environment preflight, Docker Compose validation, backend tests,
frontend lint/typecheck/tests, production build, bundle budget checks, contract
build/tests, and local contract deployment smoke checks.

When you need a complete failure inventory instead of fail-fast behavior, run:

```bash
python scripts/release_gate.py --continue-on-failure --json-out ../../var/desci-release-gate.json
```

## 2. Environment Preflight

Create a real environment file from `.env.production.example`, then run:

```bash
cd apps/desci-platform
python scripts/env_doctor.py --profile production --env-file .env.production --ignore-process-env
```

The command fails on missing required services and prints remediation for every
failed or recommended check.

For local smoke runs, use:

```bash
python scripts/env_doctor.py --profile local
```

## 3. Service Config Check

```bash
docker compose config --quiet
```

This should complete without unset-variable warnings.

## 4. Backend Tests

```bash
cd apps/desci-platform/backend
python -m pytest tests -q
```

This backend suite now covers the job API contract, including creation,
validation failures, auth failures, polling, SSE progress snapshots, readiness
signals, env doctor wiring, and worker dispatch behavior.

## 5. Frontend Tests

```bash
cd apps/desci-platform/frontend
npm run lint
npm run typecheck
npm run test
npm run build:lts
npm run check:bundle
```

## 6. Contract Checks

```bash
cd apps/desci-platform/contracts
npm run build
npm run test
npm run deploy:smoke:core
npm run deploy:smoke:nft
```

## 7. Runtime Smoke

With backend and frontend running:

```bash
cd apps/desci-platform
python scripts/product_smoke.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:5173
python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --json-out ../../var/desci-browser-smoke.json
```

`product_smoke.py` validates `/health`, `/ready`, and `/launch`. The `/launch`
endpoint is the operator-facing decision: `go`, `go-with-watch`, or `no-go`.

Before public rollout, make readiness strict:

```bash
python scripts/product_smoke.py --strict-ready --api https://api.example.com --frontend https://app.example.com
```

## Required Production Services

- LLM provider: one of Gemini, Google, OpenAI, DeepSeek, or Anthropic.
- Auth: Firebase service account or equivalent backend credentials.
- Frontend Firebase: all `VITE_FIREBASE_*` values.
- Frontend/API routing: `VITE_API_BASE_URL` and `ALLOWED_ORIGINS`.
- Data plane: `DATABASE_URL`, Supabase service credentials, Redis, RabbitMQ.

## Recommended Before Public Minting or Paid Checkout

- Pinata/IPFS credentials.
- Web3 RPC plus at least one deployed contract address, or `MOCK_MODE=true` for local demos.
- Stripe secret key, webhook secret, and price IDs.
