# Dashboard Operator Checklist

## Decision

- Variant A: keep the external credential operator checklist in generated docs and API artifacts only.
- Variant B: surface the same redacted checklist directly in the dashboard Quality panel.
- Adopted: Variant B, because the operator can now see readiness and the next blocked action in the product surface instead of hunting through reports.

## Result

- `/api/quality_overview` now exposes `credential_boundaries.operator_checklist` from the latest `EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_*.json` artifact.
- The dashboard Quality panel renders `Credential Operator Checklist`, `Checklist progress`, `Checklist next`, and a compact per-boundary checklist table.
- The current checked-in artifact renders `1 ready / 4 blocked` and points next at `canva_oauth_and_openapi_tool_execution`.
- The first visible blocker remains `Canva OAuth and OpenAPI tool execution` with `Required env: missing`.
- The ready item remains `Hosted agent runtime and tracing credentials`.

## Credential Boundary

- operator clarity: the dashboard shows readiness, blocker state, and the next checklist boundary without showing secret values.
- no credential values are emitted by the dashboard API or UI; only env names and redacted action labels appear.
- This does not claim credential-gated commands complete. Canva OAuth/OpenAPI execution, GitHub high-volume live refresh, Telegram delivery, OTLP collector shipping, and hosted runtime decisions still require operator credentials or runtime approval.
- `global_objective_complete=false`

## Browser Proof

- Manifest expected text now includes `CREDENTIAL OPERATOR CHECKLIST`, `1 ready / 4 blocked`, `Checklist next`, and `Required env: missing`.
- Dashboard dev-server browser smoke pass: `1/1` routes, `0` failures, `expected=15/15`.
- Browser proof: `docs/reports/2026-06/DEV_SERVER_BROWSER_SMOKE_DASHBOARD_OPERATOR_CHECKLIST_2026-06-05.md`.

## Verification

- `python -m pytest tests\test_dashboard_api.py -q --tb=line` -> `51 passed`
- `python -m pytest tests\test_dashboard_api.py tests\test_dev_server_browser_smoke.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q --tb=line` -> `77 passed`
- `npm test -- --run` in `apps/dashboard` -> `9 passed`
- `npm run build` in `apps/dashboard` -> passed with the existing Lightning CSS `@extend` warning
- `python ops\scripts\dev_server_browser_smoke.py --target dashboard-frontend --timeout 45 --json-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_OPERATOR_CHECKLIST_2026-06-05.json --markdown-out docs\reports\2026-06\DEV_SERVER_BROWSER_SMOKE_DASHBOARD_OPERATOR_CHECKLIST_2026-06-05.md` -> browser smoke pass, `1/1` routes, `failed=0`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md` -> `7` requirements, `cycle_prompt_covered=true`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md` -> `38` criteria, `cycle_evidence_ready=true`, `global_objective_complete=false`
- Managed dashboard dev server was stopped after the browser proof.
