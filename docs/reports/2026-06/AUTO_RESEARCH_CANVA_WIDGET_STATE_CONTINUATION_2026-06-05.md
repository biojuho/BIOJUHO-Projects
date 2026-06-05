# AutoResearch Canva Widget State Continuation

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Source signal: `mastra-ai/mastra` commit `b3e9781a93a1`,
  `fix(client-js): keep client tools for signal continuations (#17593)`.
- Source link: https://github.com/mastra-ai/mastra/commit/b3e9781a93a18e8e492849040016ddf239c00d9c

## A/B Contract

- Baseline: `useWidgetState` initialized from a local default when
  `window.openai.widgetState` was absent, but the first effect could replace
  that default with `null`. Future stateful widgets could therefore lose local
  state across continuation-style host global updates.
- Variant: preserve default/local widget state until the host provides a real
  non-null `widgetState`, while retaining `setWidgetState` propagation back to
  `window.openai`.
- Primary KPI: stateful widget hooks no longer wipe fallback state before a
  host-provided `widgetState` exists.
- Guardrails: `useOpenAiGlobal` still only reacts when the relevant global key
  is present in the `openai:set_globals` event, and the pre-push hook now runs
  the hook regression tests.
- Decision rule: adopt only if the hook contract test, pre-push hook self-test,
  Canva MCP typecheck/build, and AutoResearch audits pass.

## Result

- Adopted variant: yes.
- `useWidgetState` now returns early when `widgetStateFromWindow == null`.
- `tests/test_canva_widget_hooks.py` verifies the default-state preservation
  contract and the keyed `openai:set_globals` subscription behavior.
- `ops/hooks/pre-push` now includes `tests/test_canva_widget_hooks.py`.

## Changed Paths

- `mcp/canva-mcp/src/hooks/use-widget-state.ts`
- `tests/test_canva_widget_hooks.py`
- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`
- `ops/references/autoresearch_completion_contract.json`
- `ops/references/autoresearch_objective_requirements.json`

## Verification

- `python -m pytest tests/test_canva_widget_hooks.py tests/test_pre_push_hook.py -q`
  - Passed: `8`.
- `npm.cmd --prefix mcp/canva-mcp run typecheck`
  - Passed.
- `npm.cmd --prefix mcp/canva-mcp run build`
  - Passed.

## Next Cycle

- Continue source-backed adoption from the GitHub digest; runtime or browser
  proof remains required for any user-visible widget behavior change.
