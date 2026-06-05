# AutoResearch Agent Workflow Timestamp Identity Guard

Date: 2026-06-05

## Source Signal

- Repository: `OpenHands/OpenHands`
- Commit signal: `f2f77a666c92` `PLTF-2899: store GitHub PR timestamps as naive UTC (asyncpg DataError) (#14657)`
- Adjacent signal: `21b3b46ed198` `PLTF-2899: await SaaS get_user_id() in Slack repo-inference log (#14658)`
- Source links:
  - https://github.com/OpenHands/OpenHands/commit/f2f77a666c9286a9df5b5a7d9597eca1e1ddc2c3
  - https://github.com/OpenHands/OpenHands/commit/21b3b46ed1986cff8c87f804148b12053fee5ddc
- Local mapping: the agent workflow gate runner persists launch evidence with `generated_at` fields and reuses duplicate matrix gates across workflows. The launch risk is ambiguous timestamp normalization or a reused gate losing its source workflow identity.

## A/B Contract

- Baseline: the runner already emitted UTC-aware `generated_at` values and `reused_from` metadata, but the tests did not lock those contracts.
- Variant: add regression guards that:
  - parse workflow, matrix, and nested workflow `generated_at` values and require timezone-aware UTC offsets;
  - assert persisted JSON keeps the in-memory `generated_at` value;
  - assert reused matrix gates preserve the source workflow id, gate index, and status.
- Primary KPI: launch evidence remains unambiguous across local timezones and matrix reuse remains attributable to the original gate execution.
- Guardrails: no runner behavior change, no external calls, no credentials, and no side-effect gate execution.
- Decision rule: adopt if focused runner tests pass and a real all-workflows dry-run artifact validates the same UTC timestamp contract.

## Result

- Adopted variant: yes.
- Changed paths:
  - `tests/test_agent_workflow_gate_runner.py`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_TIMESTAMP_IDENTITY_DRY_RUN_2026-06-05.json`
  - `docs/reports/2026-06/AGENT_WORKFLOW_GATE_TIMESTAMP_IDENTITY_DRY_RUN_2026-06-05.md`

## Verification

```text
python -m pytest tests\test_agent_workflow_gate_runner.py -q --tb=line
16 passed in 0.95s
```

```text
python ops\scripts\agent_workflow_gate_runner.py --all-workflows --max-gates 1 --json-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_TIMESTAMP_IDENTITY_DRY_RUN_2026-06-05.json --markdown-out docs\reports\2026-06\AGENT_WORKFLOW_GATE_TIMESTAMP_IDENTITY_DRY_RUN_2026-06-05.md
agent workflow gate matrix valid: workflows=6, mode=dry_run, selected=6, passed=0, failed=0, skipped=0, reused=0
```

```text
artifact timestamp parse check
pass dry_run 6 6
utc_generated_at_ok
```

## Freshness

- Pushed proof commit: `6a60bba`.
- `current_tip_freshness_gate`: `6a60bba` is the active proof baseline for `origin/feat/observability-gateway-2026-05`; this cycle's runner test and report artifacts are evidence-only changes after that proof.
- `protected_path_freshness`: no changed protected paths after proof.
- Audit marker: `global_objective_complete=false`.

## Next Cycle

- Continue the source-backed loop by reviewing the next overflow queue item before adopting another variant.
- If the runner starts storing gate reports in a database, revisit whether the persisted schema wants timezone-aware UTC strings or naive UTC datetimes.
