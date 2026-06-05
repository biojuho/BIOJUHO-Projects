# AutoResearch: Agent Workflow JSON-Safe Model Serialization

## Objective

Keep agent workflow gate reports JSON-safe when model-like runtime objects
reach report metadata, workflow metadata, or gate metadata.

## Source Signal

- Source: `google/adk-python`
- Commit: `c1e852fd2df3b476d298193a489da27e9271f6ec`
- URL: `https://github.com/google/adk-python/commit/c1e852fd2df3b476d298193a489da27e9271f6ec`
- Relevant signal: `fix(cli): Serialize LiteLlm graph models safely`.

## A/B Contract

- Baseline: `agent_workflow_gate_runner.py` deep-copied report fragments and
  wrote them with `json.dumps()`. Existing manifest-loaded values are
  JSON-native, but a future runtime workflow graph could pass a model/client
  object with a `.model` name through report metadata and fail at JSON export.
- Variant: add `to_json_safe()` for report payloads. Model-like objects with a
  string `.model` become that model string, paths become strings, dataclasses and
  collections are recursively normalized, and final JSON writing runs through
  the same serializer.
- Primary KPI: workflow reports remain JSON-encodable when model-like runtime
  objects appear in report inputs.
- Guardrails: do not change workflow selection, command execution, side-effect
  gating, or normal JSON-native report output.
- Decision: adopted.

## Implementation

- `ops/scripts/agent_workflow_gate_runner.py`
  - Adds `to_json_safe()` and applies it to source context, workflow metadata,
    gate results, matrix workflow reports, and JSON file output.
- `tests/test_agent_workflow_gate_runner.py`
  - Adds a regression test that injects a model-like object into report inputs,
    expects `ollama_chat/llama3` in the report, and proves `json.dumps(report)`
    succeeds.

## Verification

- `python -m pytest tests\test_agent_workflow_gate_runner.py -q`
  - `21 passed`
- `python -m py_compile ops\scripts\agent_workflow_gate_runner.py`
  - passed
- `python ops\scripts\agent_workflow_gate_runner.py --all-workflows --max-gates 1 --json-out var\agent-workflow-json-safe-models.json --markdown-out var\agent-workflow-json-safe-models.md`
  - workflows: `6`
  - selected gates: `6`
  - mode: `dry_run`

## Remaining Boundary

This cycle hardens agent workflow report serialization. It does not complete the
open-ended AutoResearch objective or remove operator-owned credential/runtime
boundaries.

global_objective_complete=false
