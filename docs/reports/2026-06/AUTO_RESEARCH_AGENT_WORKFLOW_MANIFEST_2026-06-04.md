# AutoResearch Agent Workflow Manifest - 2026-06-04

## Source-Backed Candidate

- Source: `evalstate/fast-agent` (`https://github.com/evalstate/fast-agent`)
- Radar gap: shared harness runtime pieces existed, but there was no single manifest declaring launch-critical agent workflows across apps.
- Local constraint: keep the first adoption declarative and validator-backed before promoting anything to runtime orchestration.

## Adopted Variant

- Added `ops/references/agent_workflows.json` with six launch-critical workflow declarations:
  - `dailynews-x-ops`
  - `getdaytrends-operator-run`
  - `desci-launch-readiness`
  - `agriguard-qr-product-verification`
  - `canva-widget-oauth-preview`
  - `workspace-quality-dashboard`
- Added `ops/scripts/agent_workflow_manifest.py` to validate:
  - schema version and timestamp,
  - GitHub source context,
  - unique workflow ids,
  - allowed smoke scopes and launch statuses,
  - repo-relative entrypoint and evidence paths.
- Added dry-run workflow plan rendering for one workflow id:
  - `--workflow-plan`
  - `--plan-json-out`
  - `--plan-markdown-out`
- Added `tests/test_agent_workflow_manifest.py`.
- Generated `docs/reports/2026-06/AGENT_WORKFLOW_MANIFEST_2026-06-04.md`.
- Generated:
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.md`

## Verification

- `python ops\scripts\agent_workflow_manifest.py --json-out var\agent-workflow-manifest-2026-06-04.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_MANIFEST_2026-06-04.md`
  - `6` workflows valid
  - launch statuses: `active=6`
- `python -m pytest tests\test_agent_workflow_manifest.py -q -p no:cacheprovider`
  - `7 passed`
- `python -m compileall -q ops\scripts\agent_workflow_manifest.py`
  - passed
- `python ops\scripts\agent_workflow_manifest.py --workflow-plan workspace-quality-dashboard --plan-json-out docs\reports\2026-06\AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.json --plan-markdown-out docs\reports\2026-06\AGENT_WORKFLOW_PLAN_WORKSPACE_QUALITY_DASHBOARD_2026-06-04.md`
  - generated a dry-run plan
  - `will_execute=false`
  - `7` steps: `3` entrypoints, `2` quality gates, `2` evidence reviews
  - parsed dashboard test gate cwd as `apps/dashboard`

## Remaining Gap

The manifest now supports dry-run command planning. Runtime workflow execution should remain in the existing project CLIs and smoke/dev-server gates until there is a strong need for a central orchestrator.
