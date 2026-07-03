# AutoResearch Loop - AgriGuard Frontend Docker Node 24

Date: 2026-07-04
App: AgriGuard
Cycle: Frontend Docker build runtime alignment

## Baseline

The frontend package declares `engines.node` as `>=24.0.0`, and the verified production build path uses `node@24.15.0`. The frontend Dockerfile still used `node:22-alpine` for the build stage.

Risk:

- Docker builds could run under a Node version below the app's declared runtime floor.
- Vite 8 / plugin runtime assumptions could diverge between local verification and container builds.

## Variant

Updated the frontend Docker build stage to `node:24-alpine` and added a config test that checks:

- `apps/AgriGuard/frontend/package.json` requires Node 24+
- `apps/AgriGuard/frontend/Dockerfile` uses `FROM node:24-alpine AS build`
- The old `FROM node:22` base is absent

## Evidence

- `uv run --isolated --no-project --with pytest>=8.0 --with-editable "D:\AI project" --with-editable "D:\AI project\apps\AgriGuard\backend" python -m pytest apps/AgriGuard/backend/tests/test_cors_origins.py -q --basetemp "D:\AI project\var\tmp\pytest-agriguard-frontend-docker-node"`
  - Result: 8 passed
- `npm run build:lts`
  - Status: pass
  - Node path: `node@24.15.0`
- Docker image build was not run because Docker Desktop's Linux engine is not running on this machine.

## Decision

Adopt the Node 24 frontend Docker build stage. It aligns container builds with the app's declared engine and the verified production build command.
