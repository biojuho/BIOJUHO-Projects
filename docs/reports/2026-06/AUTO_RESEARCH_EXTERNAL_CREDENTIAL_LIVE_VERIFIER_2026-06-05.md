# AutoResearch External Credential Live Verifier

## Scope

Add an executable but safe external credential live verifier for
credential-gated launch boundaries.
This does not provide external credentials and does not claim those boundaries
complete.

## External Sources Checked

- `modelcontextprotocol/python-sdk`: MCP client/server runtime patterns and
  lifecycle checks remain relevant to command-level service verification.
- `open-telemetry/opentelemetry-collector`: live OTLP shipping still needs an
  operator-owned endpoint and credential policy.
- `open-webui/mcpo`: OpenAPI proxy execution remains a guarded boundary until
  OAuth/proxy behavior is approved.
- `humanlayer/humanlayer`: human/operator checkpoints remain a suitable pattern
  for credential and approval gates.

## A/B Decision

- Baseline: `EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.*` lists env names and
  verification commands, but execution readiness is manual.
- Variant: `ops/scripts/external_credential_live_verify.py` reads
  `external_credential_boundaries.json`, plans all boundary verification
  commands, blocks missing required env, and supports `--execute` only for
  ready boundaries.
- Decision: adopted. The variant improves operator readiness without weakening
  credential boundaries or leaking secret values.

## Result

- Default mode: `dry_run`
- Boundaries selected: `5`
- `ready=2`
- `blocked=3`
- Commands executed in dry-run: `0`
- Execute mode redacts env values in captured output.
- Missing required env remains visible and explicit:
  - `CANVA_CLIENT_ID`
  - `CANVA_CLIENT_SECRET`
  - `OTEL_EXPORTER_OTLP_ENDPOINT`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
- `global_objective_complete=false`

## Verification

- `python ops\scripts\external_credential_live_verify.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_LIVE_VERIFY_DRY_RUN_2026-06-05.md`
  - `mode=dry_run`
  - `selected=5`
  - `ready=2`
  - `blocked=3`
  - `executed=0`
- `python -m pytest tests\test_external_credential_live_verify.py tests\test_external_credential_handoff.py tests\test_external_credential_boundary_audit.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  - `26 passed`
- `python -m pytest tests\test_workspace_smoke.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  - `104 passed`
- `python -m py_compile ops\scripts\external_credential_live_verify.py ops\scripts\external_credential_handoff.py ops\scripts\external_credential_boundary_audit.py ops\scripts\autoresearch_completion_audit.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_EXTERNAL_CREDENTIAL_LIVE_VERIFIER_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_EXTERNAL_CREDENTIAL_LIVE_VERIFIER_2026-06-05.md`
  - valid `24` criteria
  - `global_objective_complete=false`

## Remaining Blocker

External credential boundaries remain blocked until the operator supplies the
real credentials or selects the live runtime endpoint/policy. The verifier only
turns those future actions into deterministic plan/execute gates.
