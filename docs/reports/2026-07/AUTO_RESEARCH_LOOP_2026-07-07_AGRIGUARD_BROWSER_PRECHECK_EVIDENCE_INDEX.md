# AutoResearch Loop: AgriGuard Browser Precheck Evidence Index

- Date: 2026-07-07 KST
- Scope: AgriGuard guarded-launch evidence handoff
- Owned code paths:
  - `apps/AgriGuard/scripts/index_guarded_launch_artifacts.py`
  - `apps/AgriGuard/scripts/render_launch_operator_packet.py`
  - `apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py`
  - `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_AGRIGUARD_BROWSER_PRECHECK_EVIDENCE_INDEX.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_PRECHECK_EVIDENCE_INDEX_2026-07-07.md`

## Objective

Carry browser-smoke precheck failures from the launch report into the guarded artifact index and operator packet. The previous cache-header precheck correctly produced `failed_precheck_names=["public_verify_cache_headers"]`, but the artifact index only exposed launch status and stage, so operator-facing index evidence could lose the actionable precheck name.

## External Sources Checked

- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Relevant adopted pattern: automation handoffs should preserve machine-readable failure names at each summarization boundary, not only in the lowest-level browser artifact.

## A/B Hypothesis

- Baseline: the launch report/readiness summary can carry browser-smoke precheck names, but the artifact index and operator packet only mirror generic launch status/stage.
- Variant: add a compact `launch_browser_smoke` object to the artifact index and mirror it into the guarded-launch readiness section of the operator packet markdown.
- Primary KPI: a launch-stage browser precheck failure remains visible as `public_verify_cache_headers` in index JSON and packet markdown.
- Guardrails: the artifact index pass/fail gate must not change, missing browser-smoke evidence must remain non-blocking when launch stops at preflight, and the guarded-launch test suite plus workspace smoke must stay green.

## Variant Evidence

Implemented:

- `index_guarded_launch_artifacts.py` now extracts compact browser-smoke evidence from `launch_report_json.child_reports.browser_smoke`.
- Preserved fields include status, path, base/API URL, step/check/precheck/screenshot counts, and failed step/check/precheck names.
- `render_launch_operator_packet.py` now mirrors `launch_browser_smoke` from the artifact index readiness summary and renders browser-smoke status, path, precheck ratio, and failed precheck names.

Focused fixture:

- `test_index_guarded_launch_artifacts_mirrors_browser_smoke_precheck_failure` creates a launch report with `stage=browser_smoke`, `prechecks_passed=2`, `prechecks_total=3`, and `failed_precheck_names=["public_verify_cache_headers"]`.
- Result: index JSON contains the same precheck failure and markdown renders `Launch browser smoke failed prechecks: public_verify_cache_headers`.
- `test_operator_packet_mirrors_artifact_index_readiness_summary` now verifies the operator packet markdown renders `Browser smoke failed prechecks: public_verify_cache_headers`.

## Verification Commands

- `python -m py_compile apps\AgriGuard\scripts\index_guarded_launch_artifacts.py apps\AgriGuard\scripts\render_launch_operator_packet.py`
  - Result: pass
- `python -m pytest apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py -q`
  - Result: 31 passed
- `python -m pytest apps\AgriGuard\backend\tests\test_launch_compose_script.py apps\AgriGuard\backend\tests\test_render_launch_operator_packet.py apps\AgriGuard\backend\tests\test_summarize_launch_readiness.py apps\AgriGuard\backend\tests\test_render_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_consume_guarded_launch_handoff.py apps\AgriGuard\backend\tests\test_index_guarded_launch_artifacts.py apps\AgriGuard\backend\tests\test_run_guarded_launch_script.py -q`
  - Result: 102 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-browser-precheck-evidence-index.json`
  - Result: `status=complete`, passed=5, failed=0, total=5
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-agriguard-browser-precheck-evidence-index-2026-07-07.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_BROWSER_PRECHECK_EVIDENCE_INDEX_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. Browser-smoke precheck failures now survive the launch report to artifact index to operator packet evidence chain, without changing the existing guarded-launch readiness gate.

## Remaining Blockers

- The default live target on `5174/8002` is still stale for public verify cache headers until the backend/proxy is restarted or rebuilt.
- Launch remains externally blocked by the missing real Firebase Admin service-account file at `C:\secure\missing-firebase-service-account.json` for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue by refreshing the guarded-launch artifacts after the runtime is restarted or by adding a ready-gate check that detects stale public verify cache headers before browser launch in the full guarded wrapper.
