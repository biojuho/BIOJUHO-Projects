# AI Projects Workspace

Multi-project workspace for product apps, automation pipelines, MCP servers, and shared tooling.

## Canonical layout

- `apps/desci-platform`
- `apps/AgriGuard`
- `apps/dashboard`
- `automation/DailyNews`
- `automation/getdaytrends`
- `automation/content-intelligence`
- `mcp/*`
- `packages/shared`
- `ops/scripts`
- `ops/monitoring`
- `docs`
- `archive`
- `var`

## Bootstrap contract

Run this after clone and before using legacy paths:

```bash
python bootstrap_legacy_paths.py
```

This generates local compatibility aliases such as:

- `scripts/` -> `ops/scripts/`
- `DailyNews/` -> `automation/DailyNews/`
- `getdaytrends/` -> `automation/getdaytrends/`
- `shared/` -> `packages/shared/`

## Main projects

| Unit | Path | Purpose |
| --- | --- | --- |
| BioLinker API | `apps/desci-platform/biolinker` | RFP matching and research backend |
| DeSci frontend | `apps/desci-platform/frontend` | Web UI for the DeSci platform |
| DeSci contracts | `apps/desci-platform/contracts` | Smart contracts |
| AgriGuard backend | `apps/AgriGuard/backend` | Supply chain tracking API |
| AgriGuard frontend | `apps/AgriGuard/frontend` | Supply chain web UI |
| Dashboard | `apps/dashboard` | Workspace dashboard app |
| DailyNews | `automation/DailyNews` | News and publishing automation |
| GetDayTrends | `automation/getdaytrends` | Trend analysis and content generation |

## Root commands

```bash
python ops/scripts/run_workspace_smoke.py --scope all
python ops/scripts/healthcheck.py
npm run build:all
npm run test:all
npm run lint:all
npm run typecheck:all
docker compose config
```

## Local development

### BioLinker

```bash
cd apps/desci-platform/biolinker
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### DeSci frontend

```bash
cd apps/desci-platform/frontend
npm install
npm run dev
```

### AgriGuard backend

```bash
cd apps/AgriGuard/backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### GetDayTrends

```bash
cd automation/getdaytrends
pip install -r requirements.txt
python main.py --one-shot --dry-run --verbose
```

### DailyNews

```bash
cd automation/DailyNews
pip install -r requirements.txt
python scripts/run_daily_news.py --mode full
```

## Shared and ops paths

- `packages/shared` for common LLM, telemetry, and utility modules
- `ops/scripts` for orchestration, smoke, healthcheck, and reporting utilities
- `ops/monitoring` for Grafana and Prometheus config
- `ops/nginx` for shared nginx assets

## Notes

- `workspace-map.json` is the source of truth for active units and legacy aliases
- `archive/` is excluded from normal smoke and package discovery
- `var/` holds runtime data, logs, snapshots, and generated smoke output
