# AutoResearch Loop: AgriGuard Artifact Index Browser Evidence Class

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded launch artifact index
- Owned code paths:
  - `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
  - `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_ARTIFACT_INDEX_BROWSER_EVIDENCE_CLASS.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ARTIFACT_INDEX_BROWSER_EVIDENCE_CLASS_2026-07-07.md`

## Objective

The browser launch suite now distinguishes strict launch-blocked evidence from skipped-precheck UI coverage with `evidence_class`, `launch_gate_enforced`, and `operator_action`. The guarded launch artifact index still only mirrored status/path/precheck counts, so the operator-facing index could lose the launch-gate explanation after evidence collection.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: operator-facing launch evidence should preserve machine-readable guardrail classification and next action, not only child artifact paths.

## A/B Hypothesis

- Baseline: `index_guarded_launch_artifacts.py` reported launch browser status, precheck counts, failed prechecks, and artifact path.
- Variant: mirror browser-suite `evidence_class`, `launch_gate_enforced`, `operator_action`, and `failed_targets` into the JSON index and render evidence class/gate/action in Markdown.
- Primary KPI: a browser-smoke-stage artifact index preserves the suite's launch classification and operator action.
- Guardrails: preflight-stage artifact sets still report browser fields as null/empty when no browser smoke artifact exists.

## Variant Evidence

Implemented:

- `launch_browser_smoke` JSON now includes `evidence_class`.
- `launch_browser_smoke` JSON now resolves `launch_gate_enforced` from top-level, summary, or nested `launch_gate` data.
- `launch_browser_smoke` JSON now includes `operator_action` and `failed_targets`.
- Markdown now renders launch browser smoke evidence class, launch-gate enforcement, and operator action when a browser artifact is present.

Focused fixture proof:

```powershell
python -m pytest apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py -q
```

Result:

- `14 passed`
- The new fixture covers a launch browser smoke artifact with:
  - `evidence_class=launch_precheck_blocked`
  - `launch_gate_enforced=true`
  - `operator_action=resolve failed prechecks before running launch browser smoke`
  - failed targets: `backend`, `frontend_proxy`

Live preflight artifact-index proof:

```powershell
python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-evidence-class-artifact-index.json --markdown-out var\agriguard-guarded-launch-evidence-class-artifact-index.md --exit-zero-on-fail
```

Result:

- exited `0`
- current live guarded launch artifact set is still `stage=preflight`
- launch browser smoke fields remain null/empty by design because the strict launch flow is stopped before browser smoke execution

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py -q`
  - Result: 14 passed
- `python apps\AgriGuard\scripts\index_guarded_launch_artifacts.py --app-root apps\AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-guarded-launch --json-out var\agriguard-guarded-launch-evidence-class-artifact-index.json --markdown-out var\agriguard-guarded-launch-evidence-class-artifact-index.md --exit-zero-on-fail`
  - Result: exited 0, current stage preflight
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-artifact-index-browser-evidence-class.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-artifact-index-browser-evidence-class.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_ARTIFACT_INDEX_BROWSER_EVIDENCE_CLASS_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. Guarded launch artifact indexes now preserve browser-suite launch classification and operator action when a browser smoke artifact is present.

## Remaining Blockers

- Strict launch remains blocked by stale backend/proxy public verify cache-header runtime.
- Compose replacement remains externally blocked until a real outside-repo Firebase Admin service-account file exists at the configured path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
