# AutoResearch Dashboard Release Refresh Workflow

- Date: 2026-06-05
- Source reviewed: `google/adk-python` commit `928017d3919401a6225a9a51b3f762a6ceb7836c`
- Source signal: `chore: add automatic adk web updates in release process`
- Source URL: https://github.com/google/adk-python/commit/928017d3919401a6225a9a51b3f762a6ceb7836c
- Local guard: `dashboard_release_refresh_workflow_guard`
- Decision: adopted
- Global objective complete: `false`
- Marker: `global_objective_complete=false`

## A/B Contract

- A, control: rely on the deployment workflow build step and the local pre-push hook for dashboard bundle freshness.
- B, adopted: add a manual, read-only dashboard release refresh workflow that rebuilds the dashboard from source, runs dashboard tests, checks the bundle budget, and uploads `apps/dashboard/dist` as a reviewable release artifact before production credentials are involved.

## Adopted Changes

- Added `.github/workflows/dashboard-release-refresh.yml` with `workflow_dispatch`, `contents: read`, pinned checkout/setup-node/upload-artifact actions, `npm ci`, `npm test -- --run`, `npm run build`, `npm run check:bundle`, and `if-no-files-found: error` for `apps/dashboard/dist`.
- Hardened `.github/workflows/deploy-dashboard.yml` so the deployment path also runs `npm run check:bundle` after `npm run build` and before `gcloud builds submit`.
- Added regression coverage in `tests/test_github_workflows.py` so the release refresh workflow remains read-only, builds the dashboard, uploads the dist artifact, and the deploy workflow keeps the bundle check before Cloud Build.

## Verification

- Workflow and audit regression suite: `25 passed`.
- Dashboard UI tests: `9 passed`.
- Dashboard production build: passed.
- Dashboard bundle budget: passed; max chunk `223.07KB`, entry limit `400KB`.
- Workspace smoke: `6/6 passed` via `var/workspace-smoke-dashboard-release-refresh-2026-06-05.json`.
- Completion audit: `79 criteria`, `cycle_evidence_ready=true`, `global_objective_complete=false`.
- Objective coverage audit: `7 requirements`, `cycle_prompt_covered=true`, `global_objective_complete=false`.

## Remaining Boundary

- The refresh workflow intentionally does not deploy and does not need GCP credentials. The production deploy remains credential-gated by the existing Cloud Run workflow secrets.
