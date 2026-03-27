# AI Projects Workspace Quick Start

This workspace is organized around canonical top-level folders:

- `apps/` for product apps
- `automation/` for scheduled pipelines
- `mcp/` for MCP servers
- `packages/` for shared libraries
- `ops/` for scripts, monitoring, and infra helpers
- `docs/` for living docs and reports
- `archive/` for inactive projects
- `var/` for runtime data, logs, snapshots, and smoke output

## First-time setup

```bash
git clone <repo-url>
cd "AI 프로젝트"

cp .env.example .env
python bootstrap_legacy_paths.py
```

The bootstrap step creates local compatibility aliases such as `scripts/`, `getdaytrends/`, and `DailyNews/` so older commands still work.

## Prerequisites

- Python 3.13+
- Node.js 22+
- Docker
- Git

## Common root commands

```bash
python bootstrap_legacy_paths.py
python ops/scripts/run_workspace_smoke.py --scope all
npm run build:all
npm run test:all
npm run lint:all
npm run typecheck:all
docker compose config
docker compose -f docker-compose.dev.yml config
```

If you specifically need a legacy command, run bootstrap first and then use it:

```bash
python scripts/run_workspace_smoke.py --scope all
```

## Local development

### DeSci Platform

```bash
cd apps/desci-platform/biolinker
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd apps/desci-platform/frontend
npm install
npm run dev
```

### AgriGuard

```bash
cd apps/AgriGuard/backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

```bash
cd apps/AgriGuard/frontend
npm install
npm run dev
```

### Automation pipelines

```bash
cd automation/getdaytrends
pip install -r requirements.txt
python main.py --one-shot --dry-run --verbose
```

```bash
cd automation/DailyNews
pip install -r requirements.txt
python scripts/run_daily_news.py --mode full
```

## Docker

```bash
docker compose up -d
docker compose ps
docker compose logs -f
```

## Layout snapshot

```text
.
|-- apps/
|-- automation/
|-- mcp/
|-- packages/
|-- ops/
|-- docs/
|-- archive/
|-- var/
|-- bootstrap_legacy_paths.py
|-- docker-compose.yml
`-- package.json
```

## Where to look next

- `CLAUDE.md` for the workspace overview
- `ONBOARDING.md` for a guided setup path
- `CONTRIBUTING.md` for contribution conventions
- `docs/QUALITY_GATE.md` for the deterministic validation contract
