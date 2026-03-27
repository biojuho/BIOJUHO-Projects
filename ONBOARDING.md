# Onboarding

This workspace now uses a canonical top-level layout and a generated legacy-path layer.

## Step 1: Prepare your machine

- Install Python 3.13+
- Install Node.js 22+
- Install Docker
- Install Git

## Step 2: Clone and bootstrap

```bash
git clone <repo-url>
cd "AI 프로젝트"
cp .env.example .env
python bootstrap_legacy_paths.py
```

`bootstrap_legacy_paths.py` creates local aliases for older paths like `scripts/`, `getdaytrends/`, and `DailyNews/`.

## Step 3: Learn the layout

```text
apps/
  AgriGuard/
  desci-platform/
  dashboard/
automation/
  DailyNews/
  getdaytrends/
  content-intelligence/
mcp/
packages/
  shared/
ops/
  scripts/
  monitoring/
  nginx/
  agents/
  directives/
docs/
archive/
var/
```

## Step 4: Verify the workspace

```bash
python ops/scripts/healthcheck.py
python ops/scripts/run_workspace_smoke.py --scope workspace
docker compose config
```

## Step 5: Run one project locally

### DeSci backend

```bash
cd apps/desci-platform/biolinker
pip install -r requirements.txt
python -m uvicorn main:app --port 8000 --reload
```

### DeSci frontend

```bash
cd apps/desci-platform/frontend
npm install
npm run dev
```

### GetDayTrends

```bash
cd automation/getdaytrends
pip install -r requirements.txt
python main.py --one-shot --dry-run --verbose
```

## Step 6: Use the root runners

```bash
npm run build:all
npm run test:all
npm run lint:all
npm run typecheck:all
```

If an older guide uses `scripts/...` or root project folders, run bootstrap first and the aliases will resolve locally.
