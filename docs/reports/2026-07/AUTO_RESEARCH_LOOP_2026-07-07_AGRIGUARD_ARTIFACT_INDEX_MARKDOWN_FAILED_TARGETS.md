# AutoResearch Loop: AgriGuard Artifact Index Markdown Failed Targets

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded launch artifact index Markdown handoff
- Owned code paths:
  - `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
  - `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_ARTIFACT_INDEX_MARKDOWN_FAILED_TARGETS.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ARTIFACT_INDEX_MARKDOWN_FAILED_TARGETS_2026-07-07.md`

## Objective

The guarded launch artifact index already preserved browser-smoke `failed_targets` in JSON. The Markdown index still omitted them, so an operator reading the handoff could see the failed precheck name without seeing which live surfaces failed that precheck.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: handoff artifacts should keep failure classification and failing target surfaces together.

## A/B Hypothesis

- Baseline: Markdown rendered launch browser failed prechecks but not failed targets.
- Variant: render `Launch browser smoke failed targets` from the indexed `failed_targets` list.
- Primary KPI: the browser-smoke-stage fixture Markdown includes `backend, frontend_proxy`.
- Guardrails: JSON index shape remains unchanged and existing launch preflight behavior is unchanged.

## Variant Evidence

Implemented:

- Added a Markdown line for launch browser smoke failed targets.
- Added a focused assertion that failed targets render as `backend, frontend_proxy`.

Focused verification:

```powershell
python -m pytest apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py -q
```

Result:

- `14 passed`

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py -q`
  - Result: 14 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-index-markdown-failed-targets.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-artifact-index-markdown-failed-targets.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ARTIFACT_INDEX_MARKDOWN_FAILED_TARGETS_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. Markdown handoffs now show the failed live targets alongside the failed browser precheck.

## Remaining Blockers

- Strict launch remains blocked by stale backend/proxy public verify cache-header runtime.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
