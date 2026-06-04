# AutoResearch Loop - AgriGuard CORS and Docker Browser QA - 2026-06-04

## Objective

Use the AutoResearch product loop on a live app surface: open AgriGuard in a browser, click real UI paths, adopt the variant only if it fixes the observed runtime defect, and preserve deterministic evidence.

## Scope and Owned Paths

- `apps/AgriGuard/backend/main.py`
- `apps/AgriGuard/backend/tests/test_cors_origins.py`
- `apps/AgriGuard/backend/.dockerignore`
- `apps/AgriGuard/backend/Dockerfile`
- `apps/AgriGuard/.env.example`
- `apps/AgriGuard/backend/.env.example`
- `apps/AgriGuard/docker-compose.yml`
- `apps/AgriGuard/README.md`
- `docker-compose.yml`
- `docker-compose.dev.yml`

## A/B Hypothesis

- Baseline: local AgriGuard frontend at `http://127.0.0.1:5174/` loads the dashboard but the browser blocks `http://127.0.0.1:8002/dashboard/summary` because the running Docker backend does not return `access-control-allow-origin`.
- Variant: make the allowed-origin contract explicit across backend defaults, env examples, and Docker compose; isolate Docker-only DB/CORS overrides behind `AGRIGUARD_DATABASE_URL` and `AGRIGUARD_ALLOWED_ORIGINS`; repair backend Docker rebuild blockers so the running container can be regenerated from current code.
- Primary KPI: dashboard API request succeeds from the live `5174` frontend without browser CORS errors.
- Guardrails: Docker rebuild succeeds, API readiness passes, browser navigation has no console warnings/errors, targeted backend tests pass, and canonical AgriGuard smoke remains green.

## Baseline Evidence

- Browser console before fix: `agriguard-auto-research-console-home.md`
  - `Access to XMLHttpRequest at 'http://127.0.0.1:8002/dashboard/summary' from origin 'http://127.0.0.1:5174' has been blocked by CORS policy`
  - `Failed to load resource: net::ERR_FAILED`
- Direct CORS probe before fix:
  - GET returned `200` but no `access-control-allow-origin`.
  - OPTIONS returned `Disallowed CORS origin`.
- Docker rebuild blockers found on the live path:
  - build context failed on `apps/AgriGuard/backend/.pytest-tmp`.
  - Dockerfile copied missing `requirements.txt`.
  - app compose inherited host `.env` `DATABASE_URL=sqlite:///./backend/agriguard.db`.
  - container layout `/app/main.py` failed `Path(__file__).resolve().parents[2]`.

## Variant Adopted

- Added `http://localhost:5174` and `http://127.0.0.1:5174` to the durable AgriGuard CORS contract.
- Added compose-level `ALLOWED_ORIGINS` defaults for root, dev, and AgriGuard app compose.
- Changed AgriGuard app compose to use `AGRIGUARD_DATABASE_URL` and `AGRIGUARD_ALLOWED_ORIGINS` so local `.env` defaults cannot silently break Docker runtime.
- Updated backend Dockerfile to install from `pyproject.toml`.
- Ignored pytest/cache/coverage artifacts from the backend Docker build context.
- Made workspace-root resolution work for both monorepo and `/app` container copy layouts.
- Updated README backend install command to `pip install -e .`.

## Verification

- `python -m pytest apps\AgriGuard\backend\tests\test_cors_origins.py -q -p no:cacheprovider` -> `6 passed`.
- `python -m pytest apps\AgriGuard\backend\tests\test_cors_origins.py apps\AgriGuard\backend\tests\test_product_and_qr_routes.py apps\AgriGuard\backend\tests\test_dashboard_routes.py -q -p no:cacheprovider` -> `31 passed`.
- `docker compose -f apps\AgriGuard\docker-compose.yml config --quiet` -> passed.
- `docker compose -f docker-compose.yml config --quiet` -> passed with missing optional secret warnings.
- `docker compose -f apps\AgriGuard\docker-compose.yml up -d --build backend` -> image rebuilt and backend recreated.
- `python ops\scripts\dev_server_status.py --target agriguard-api --wait-ready --wait-timeout 60 --poll-interval 2 --timeout 3 --json-out var\dev-server-status-agriguard-api-cors-fix-2026-06-04-env-final.json` -> `1/1 ready`.
- Direct CORS GET from `Origin: http://127.0.0.1:5174` -> `200`, `access-control-allow-origin: http://127.0.0.1:5174`.
- Direct CORS OPTIONS preflight -> `200`, `access-control-allow-origin: http://127.0.0.1:5174`.
- Browser evidence:
  - `agriguard-auto-research-console-after-cors-fix-home.md` -> `0` errors, `0` warnings.
  - `agriguard-auto-research-console-registry-after-cors-fix.md` -> `0` errors, `0` warnings.
  - `agriguard-auto-research-console-supply-chain-after-cors-fix.md` -> `0` errors, `0` warnings.
  - `agriguard-auto-research-console-scanner-after-cors-fix.md` -> `0` errors, `0` warnings.
  - `agriguard-auto-research-console-scanner-camera-click-after-cors-fix.md` -> `0` errors, `0` warnings.
  - `agriguard-auto-research-dashboard-after-cors-fix.png`
  - `agriguard-auto-research-scanner-camera-click-after-cors-fix-viewport.png`
- `python ops\scripts\dev_server_status.py --target agriguard-api --target agriguard-frontend --json-out var\dev-server-status-agriguard-ui-cors-fix-2026-06-04.json` -> `2/2 ready`.
- `python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-auto-research-cors-fix-2026-06-04.json` -> `5/5 PASS`.

## Decision

Adopted. The variant fixed the real browser CORS defect, restored Docker backend rebuild/recreate, and passed the affected product smoke scope.

## Remaining Notes

- `docker-compose.dev.yml config --quiet` is still blocked by the pre-existing missing `apps/desci-platform/biolinker/.env`; this was not introduced by this cycle.
- Full-page screenshot on the scanner camera-click state hit the Playwright 5s screenshot timeout, so viewport screenshot evidence was retained instead.
