# AutoResearch Credential Env Template Queue - 2026-06-05

## Scope

This env template queue order cycle aligns
`EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example` with the ranked
`unblock_queue` already emitted in JSON and Markdown. The goal is to make the
operator's copy/edit path match the handoff priority order.

## A/B Decision

- Baseline: the env template followed registry order, so OTLP collector
  settings appeared before the GitHub token and Telegram credentials even
  though the unblock queue ranked GitHub and Telegram earlier.
- Variant: `format_env_template()` now iterates `handoff["unblock_queue"]`,
  looks up each boundary by id, and emits `# Queue rank: N` comments before the
  env names for that ranked boundary.
- Decision rule: adopt only if the env template stays redacted, matches the
  deterministic unblock order, and the checked-in handoff drift check still
  passes.
- Result: adopted.

## Queue Order

The env template now follows this order:

1. `# Queue rank: 1` Canva OAuth/OpenAPI env names.
2. `# Queue rank: 2` GitHub token env names: `GITHUB_TOKEN`, `GH_TOKEN`.
3. `# Queue rank: 3` Telegram env names.
4. `# Queue rank: 4` OTLP collector env names, including
   `OTEL_EXPORTER_OTLP_ENDPOINT`.
5. `# Queue rank: 5` hosted runtime/tracing env names.

No secret values are emitted. The template continues to contain only env names
with empty assignments.

## Verification

- Handoff tests:
  `python -m pytest tests\test_external_credential_handoff.py -q --tb=line`
  returned `7 passed` after adding
  `test_env_template_follows_unblock_queue_order`.
- Focused credential/completion suite:
  `python -m pytest tests\test_external_credential_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_live_verify.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  returned `34 passed`.
- Pre-push pytest bundle:
  `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_autoresearch_objective_coverage.py tests\test_autoresearch_completion_audit.py tests\test_mcp_service_runtime_smoke.py tests\test_mcp_otel_collector_handoff.py tests\test_external_credential_boundary_audit.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_agent_workflow_gate_runner.py tests\test_github_modernization_radar.py tests\test_github_source_freshness.py tests\test_dev_server_browser_smoke.py tests\test_dev_server_mcp_contract.py tests\test_dev_server_mcp_runtime.py tests\test_dev_server_mcp_runtime_smoke.py -q --tb=line`
  returned `129 passed` after rebasing over the GitHub modernization radar
  drift guard.
- Handoff regeneration:
  `python ops\scripts\external_credential_handoff.py --json-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --markdown-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md --env-template-out docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example`
  regenerates the redacted JSON, Markdown, and env template from the registry.
- Completion audit:
  after regenerating the checked-in completion audit summary, the audit reports
  `30` criteria with `global_objective_complete=false`.

Completion remains blocked on the same external operator boundaries. This
change improves the handoff path only; `global_objective_complete=false`.
