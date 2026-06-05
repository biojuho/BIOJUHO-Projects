# AutoResearch Canva MCP OpenAI Namespace Metadata

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Source signal: `vercel/ai` commit `94eba1b0594e`,
  `fix(openai): round-trip namespace on function_call input items (#15193)`.
- Source link: https://github.com/vercel/ai/commit/94eba1b0594ec6e34726cf3436bb953e46000106

## A/B Contract

- Baseline: Canva MCP widget tools had OpenAI/ChatGPT Apps namespaced metadata
  in MCP descriptors, but the OpenAPI interop summary and `/tools` metadata
  endpoint exposed only name, description, read-only/destructive flags, and
  schema references.
- Variant: preserve OpenAI namespaced metadata in the interop summaries via
  `openAiMeta` and `openAiMetaKeys`, and make the offline OpenAPI contract fail
  when `x-mcp-tools` drops `openai/...` keys.
- Primary KPI: generated contract evidence reports all widget-capable tools
  with OpenAI namespaced metadata and includes `openAiMetaKeys` in the schema
  and summary.
- Guardrails: no live OpenAPI tool execution is enabled; the existing
  `openapi_tool_execution_disabled` boundary stays in place until Canva OAuth
  and proxy authentication are verified.
- Decision rule: adopt only if the contract generator, server metadata schema,
  and focused tests prove namespace preservation without changing tool
  execution behavior.

## Result

- Adopted variant: yes.
- OpenAI namespaced metadata fields: `openAiMeta`, `openAiMetaKeys`.
- Contract summary: `4` tools with OpenAI namespaced metadata.
- Preserved keys: `openai/outputTemplate`,
  `openai/resultCanProduceWidget`, `openai/toolInvocation/invoked`,
  `openai/toolInvocation/invoking`, and `openai/widgetAccessible`.
- OpenAPI execution remains disabled with the existing 501 response until
  operator-owned OAuth/proxy authorization is verified.

## Changed Paths

- `mcp/canva-mcp/src/server/server.ts`
- `ops/scripts/canva_mcp_openapi_contract.py`
- `tests/test_canva_mcp_openapi_contract.py`
- `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.json`
- `docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.md`
- `ops/references/autoresearch_completion_contract.json`
- `ops/references/autoresearch_objective_requirements.json`

## Verification

- `python -m py_compile ops/scripts/canva_mcp_openapi_contract.py`
  - Passed.
- `python -m pytest tests/test_canva_mcp_openapi_contract.py -q`
  - Passed: `7 passed`.
- `python ops/scripts/canva_mcp_openapi_contract.py --openapi-out docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.json --summary-out var/canva-mcp-openapi-contract-2026-06-04.json --markdown-out docs/reports/2026-06/CANVA_MCP_OPENAPI_CONTRACT_2026-06-04.md`
  - Passed: `20` tools, `read_only=9`, `destructive=1`.
- `npm.cmd --prefix mcp/canva-mcp run typecheck`
  - Passed.
- `npm.cmd --prefix mcp/canva-mcp run build`
  - Passed.
- Built-server `/tools` runtime probe
  - Passed: `tools=20`, `search_meta=5`, `upload_meta=3`.

## Next Cycle

- Continue source-backed adoption from the GitHub digest, with browser/runtime
  proof required for any change that affects a user-visible or executable tool
  path.
