# AutoResearch: Workspace Smoke npm Preflight

Date: 2026-06-04

## Source-backed prompt

After process-tree timeout hardening, a clean-worktree monolithic
`run_workspace_smoke.py --scope all` completed instead of hanging, but failed
14 Node checks because all clean worktree `node_modules` directories were
missing. The split completion audit had already needed manual `npm ci` prep for
frontend/contract workspaces, so this was an automation gap in the quality gate.

## A/B contract

- Baseline: clean-worktree `--scope all` relied on manually prepared
  `node_modules`. Result: `11/25 PASS`, with every failure caused by missing
  local npm binaries or build outputs.
- Variant: before npm-based checks, identify unique lockfile-backed package
  directories and run `npm ci --no-audit` once when `node_modules` is absent.
  Continue the smoke run even if installation fails so JSON evidence is still
  produced.
- KPI: a clean-worktree monolithic all-scope run can bootstrap Node
  dependencies and produce a complete `25/25 PASS` schema-v1 artifact.

## Adopted variant

The npm preflight was adopted.

Implementation:

- `ops/scripts/run_workspace_smoke.py` now discovers npm check workspaces,
  dedupes package directories, uses the existing process-tree timeout runner for
  `npm ci --no-audit`, and keeps npm cache under
  `var/tmp/workspace-smoke/.tool-cache/npm`.
- `tests/test_workspace_smoke.py` now covers npm workspace discovery, install
  invocation, and skipping workspaces where `node_modules` already exists.
- `docs/QUALITY_GATE.md` documents the clean-worktree npm preflight and notes
  that dependency artifacts remain local runtime state.

## Verification

- `python -m py_compile ops\scripts\run_workspace_smoke.py` -> PASS
- `python -m pytest tests\test_workspace_smoke.py tests\test_smoke_report_readers.py -q -p no:cacheprovider`
  -> `24 passed` after rebasing on remote tip `aa8733e`
- `python -m pytest tests\test_workspace_smoke.py tests\test_smoke_report_readers.py tests\test_agent_workflow_manifest.py tests\test_canva_mcp_openapi_contract.py tests\test_github_modernization_radar.py -q -p no:cacheprovider`
  -> `36 passed` after rebasing on remote tip `a7816b6`
- Baseline:
  `python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-launch-audit-2026-06-04.json`
  -> `11/25 PASS`; failed Node checks all reported missing `eslint`, `vitest`,
  `vite`, `hardhat`, or missing build artifacts.
- Final:
  `python ops\scripts\run_workspace_smoke.py --scope all --json-out var\workspace-smoke-all-launch-audit-npm-preflight-post-rebase-2026-06-04.json`
  -> `25/25 PASS`

Final artifact summary:

- `schema_version`: `1`
- `status`: `complete`
- `summary`: `total=25`, `completed=25`, `passed=25`, `failed=0`,
  `remaining=0`
- `duration_seconds`: `797.526`
- Slowest checks:
  `desci frontend unit tests=154.475s`, `getdaytrends tests=84.744s`,
  `DailyNews unit tests=73.313s`, `desci frontend lint=60.58s`,
  `dashboard frontend tests=59.268s`

## Follow-up

The launch gate now has a clean-worktree monolithic proof path. Future all-scope
runs should not require manual npm dependency preparation.
