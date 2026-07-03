# AutoResearch Loop: AgriGuard Quality Workflow BOM

Date: 2026-07-04

## Objective

Restore the AgriGuard Quality Gate GitHub Actions run after the latest pushed
branch produced a failed run with no jobs and no logs.

## Remote finding

- Branch: `feat/shared-llm-modernization-2026-06-19`
- Commit under inspection: `dfe121656ad3cbd544be6a014bbac169650b670e`
- Failing run: `28686629910`
- Run URL: `https://github.com/biojuho/BIOJUHO-Projects/actions/runs/28686629910`
- `gh run view 28686629910 --json jobs` returned `jobs: []`.
- `gh run view 28686629910 --log-failed` returned `failed to get run log: log not found`.
- The API run name was `.github/workflows/agriguard-quality.yml` instead of
  `AgriGuard Quality Gate`.

Local YAML parsing showed the top-level key was `\ufeffname` because the file
contained an embedded UTF-8 BOM immediately before `name:`. GitHub therefore did
not see a valid workflow name and created an unusable zero-job run.

## Source checks

- GitHub workflow syntax docs:
  `https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions`
- GitHub manual workflow docs:
  `https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow`
- GitHub events docs:
  `https://docs.github.com/actions/using-workflows/events-that-trigger-workflows`

The fix follows the documented `workflow_dispatch` trigger shape and includes
the workflow file itself in `push` and `pull_request` path filters so future
workflow-only fixes can trigger the gate.

## Implementation

- Removed the embedded BOM before `name: AgriGuard Quality Gate` in
  `.github/workflows/agriguard-quality.yml`.
- Added `workflow_dispatch: {}` to the workflow triggers.
- Added `.github/workflows/agriguard-quality.yml` to both `push.paths` and
  `pull_request.paths`.
- Hardened `tests/test_security_gate_contracts.py` so all tracked GitHub
  workflows must parse as YAML mappings with `name`, `on`, and `jobs`.
- Added a specific AgriGuard workflow contract test covering the workflow name,
  self-triggering path filters, and pinned checkout/setup-node actions.

## Verification

- `python -m pytest tests/test_security_gate_contracts.py::test_github_workflows_are_valid_yaml tests/test_security_gate_contracts.py::test_agriguard_quality_workflow_is_named_and_self_triggering -q`
  - Result: `2 passed in 1.77s`
- `python -m pytest tests/test_security_gate_contracts.py -q`
  - Result: `15 passed in 3.73s`
- Local YAML diagnostic:
  - `embedded_bom= False`
  - `name= AgriGuard Quality Gate`
  - `trigger_keys= ['pull_request', 'push', 'workflow_dispatch']`
  - `jobs= ['quality']`
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out apps/AgriGuard/var/workspace-smoke-agriguard-quality-workflow-bom-2026-07-04.json`
  - Result: `complete`, `5/5 passed`
  - Backend tests: `477 passed, 2 warnings in 318.41s`
  - Contracts tests: `26 passing`
- Browser A/B:
  - Existing Docker-backed preview on `5174/8002` produced `46/47 PASS` because
    the Docker API on `8002` was stale and returned 404 for current QR KPI and
    sensor admin endpoints.
  - Current checkout backend/frontend on temporary ports `8008/5183` produced
    `47/47 PASS` with
    `apps/AgriGuard/var/agriguard-nav-browser-smoke-quality-workflow-current-backend-2026-07-04.json`.
- Post-push remote Actions:
  - Commit: `071775aff13fd03d9903082570c185ec414984a5`
  - Run: `28687348976`
  - URL: `https://github.com/biojuho/BIOJUHO-Projects/actions/runs/28687348976`
  - Workflow: `AgriGuard Quality Gate`
  - Job: `quality (24.15.0)`
  - Result: success in 53s
  - Steps completed successfully: checkout, bootstrap legacy paths, setup-node,
    install dependencies, lint, unit tests, build, and bundle budget check.

## Remaining risk

The prior zero-job remote failure is fixed. Remaining launch risk is outside
this workflow repair: production launch still needs current provider/runtime
values and operator promotion approval before it should be treated as fully
released.
