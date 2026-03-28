# AgriGuard

AgriGuard is a cold-chain traceability platform for agricultural products. It combines QR-based product history, IoT temperature monitoring, and blockchain-backed records so logistics teams can react faster and consumers can trust what they buy.

## Target Audience

**Type**: B2B enterprise platform with a consumer-facing verification layer

**Persona A: Supply Chain Manager**
- Works in logistics, distribution, or retail operations for agricultural products
- Needs fast cold-chain incident detection, reliable claim evidence, and fewer manual tracking errors
- Values easy rollout, measurable ROI, and low training overhead

**Persona B: Safety-Conscious Consumer**
- Scans QR codes to verify origin, storage history, and product trustworthiness
- Needs a simple mobile experience and clear answers without technical jargon
- Values confidence, safety, and proof that a product is authentic

**What They Need**
- Instant QR-based traceability for full product history
- Real-time temperature monitoring for cold-chain failures
- Tamper-resistant records for audits and claims
- Clear dashboards for logistics teams and low-friction verification for consumers

**Success Metrics**
- QR scan success rate `>99%`
- Temperature collection interval `<= 5 minutes`
- Blockchain record latency `<30 seconds`
- Claim reduction rate `-90%`
- Consumer QR scans `>1,000/day`

This README captures the audience assumptions currently used for AgriGuard product, QR, and cold-chain workflows.

## Project Layout

- [`backend`](./backend): FastAPI API, database access, MQTT integration, and migration scripts
- [`frontend`](./frontend): React/Vite user interface for traceability and monitoring
- [`contracts`](./contracts): Hardhat smart contracts for blockchain-backed records
- [`docker-compose.yml`](./docker-compose.yml): Local stack for PostgreSQL, MQTT, backend, frontend, and nginx
- [`nginx`](./nginx): Reverse proxy configuration

## Quick Start

### Docker stack

```bash
cd apps/AgriGuard
docker compose up -d postgres mosquitto backend frontend
```

### Frontend

```bash
cd apps/AgriGuard/frontend
npm install
npm run dev
```

### Backend

```bash
cd apps/AgriGuard/backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8002
```

## Quality Checks

From the workspace root:

```bash
python ops/scripts/run_workspace_smoke.py --scope agriguard
```

Project-level checks:

```bash
cd apps/AgriGuard/frontend
npm run lint
npm run build:lts
```

```bash
python -m compileall -q apps/AgriGuard/backend
```

## Related Docs

- [`frontend/README.md`](./frontend/README.md)
- [`POSTGRES_MIGRATION_PLAN.md`](./POSTGRES_MIGRATION_PLAN.md)
- [`POSTGRES_MIGRATION_QC_REPORT.md`](./POSTGRES_MIGRATION_QC_REPORT.md)
- [`BENCHMARK_RESULTS.md`](./BENCHMARK_RESULTS.md)
