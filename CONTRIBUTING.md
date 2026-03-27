# Contributing

This repository is a multi-project workspace. The canonical layout is:

- `apps/AgriGuard`
- `apps/desci-platform`
- `apps/dashboard`
- `automation/DailyNews`
- `automation/getdaytrends`
- `automation/content-intelligence`
- `mcp/*`
- `packages/shared`
- `ops/*`

## Before you start

```bash
cp .env.example .env
python bootstrap_legacy_paths.py
python -m venv .venv
.venv\\Scripts\\activate
```

Install the dependencies you need in the project you are changing. Examples:

```bash
npm install --prefix apps/AgriGuard/frontend
npm install --prefix apps/desci-platform/frontend
pip install -r apps/desci-platform/biolinker/requirements.txt
pip install -r automation/getdaytrends/requirements.txt
```

## Validation

Use the workspace runners from the repo root whenever possible:

```bash
python ops/scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json
npm run build:all
npm run test:all
npm run lint:all
npm run typecheck:all
```

Legacy commands are still supported after running bootstrap:

```bash
python scripts/run_workspace_smoke.py --scope all
```

## Commit hygiene

- Do not commit `.env` files or generated runtime data from `var/`
- Keep archive content under `archive/`; do not mix it back into active roots
- Prefer canonical paths in code, docs, and CI
- Treat `workspace-map.json` as the source of truth for active units and legacy aliases

## Project notes

- `packages/shared` contains shared LLM, telemetry, and utility code
- `ops/scripts` contains workspace automation and smoke orchestration
- `docs/reports/` is for dated reports; keep root docs focused on living guidance
