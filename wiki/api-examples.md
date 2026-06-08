---
updated: 2026-06-08T16:01:08+09:00
confidence: medium
source_types:
  - web
  - standard
  - paper
  - book
sources:
  - id: anthropic_structured_outputs
    type: web
    title: Anthropic structured outputs
    url: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
    checked: 2026-06-08
  - id: anthropic_tool_use
    type: web
    title: Anthropic tool use with Claude
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
    checked: 2026-06-08
  - id: anthropic_handle_tool_calls
    type: web
    title: Anthropic handle tool calls
    url: https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
    checked: 2026-06-08
  - id: openai_structured_outputs
    type: web
    title: OpenAI structured outputs
    url: https://developers.openai.com/api/docs/guides/structured-outputs
    checked: 2026-06-08
  - id: openai_function_calling
    type: web
    title: OpenAI function calling
    url: https://developers.openai.com/api/docs/guides/function-calling
    checked: 2026-06-08
  - id: openai_tools
    type: web
    title: OpenAI using tools
    url: https://developers.openai.com/api/docs/guides/tools
    checked: 2026-06-08
  - id: mcp_spec
    type: standard
    title: Model Context Protocol specification
    url: https://modelcontextprotocol.io/specification/2025-11-25
    checked: 2026-06-08
  - id: mcp_transports
    type: standard
    title: MCP transports
    url: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
    checked: 2026-06-08
  - id: mcp_tools
    type: standard
    title: MCP server tools
    url: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
    checked: 2026-06-08
  - id: mcp_authorization
    type: standard
    title: MCP authorization
    url: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
    checked: 2026-06-08
  - id: react
    type: paper
    title: "ReAct: Synergizing Reasoning and Acting in Language Models"
    url: https://arxiv.org/abs/2210.03629
    checked: 2026-06-08
  - id: toolformer
    type: paper
    title: "Toolformer: Language Models Can Teach Themselves to Use Tools"
    url: https://arxiv.org/abs/2302.04761
    checked: 2026-06-08
  - id: api_design_patterns
    type: book
    title: "API Design Patterns"
    url: https://openlibrary.org/works/OL25448641W/API_Design_Patterns
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - api
  - structured-outputs
  - tools
  - mcp
  - examples
---

# API Examples

API examples are the smallest stable code and schema patterns that JooPark can reuse across LLM routes. The examples should privilege reproducibility, schema identity, and evalability over demo cleverness.

## Pattern 1: Structured Output

```js
// Claude
output_config: {format: {type: "json_schema", schema: outputSchema}};

// OpenAI Responses API
text: {format: {type: "json_schema", strict: true, schema: outputSchema.schema}};

// OpenAI Chat Completions compatibility
response_format: {type: "json_schema", json_schema: outputSchema, strict: true};

const outputSchema = {
  name: "support_triage_result",
  strict: true,
  schema: {
    type: "object",
    additionalProperties: false,
    properties: {
      category: { type: "string", enum: ["billing", "account", "technical", "policy", "unknown"] },
      severity: { type: "string", enum: ["sev0", "sev1", "sev2", "sev3", "info"] },
      grounded: { type: "boolean" },
      citations: {
        type: "array",
        items: {
          type: "object",
          additionalProperties: false,
          properties: {
            source_id: { type: "string" },
            span_id: { type: "string" },
            claim: { type: "string" }
          },
          required: ["source_id", "span_id", "claim"]
        }
      }
    },
    required: ["category", "severity", "grounded", "citations"]
  }
};
```

Use the same schema id in [[prompt-release-management]], [[eval-result-lineage]], and failure triage so schema drift is visible.

Structured Outputs are appropriate when the final answer itself must be a valid object. Function/tool calling is separate: use it when the model needs to choose an operation, call a backend, and then continue reasoning from the tool result.

## A/B 비교: 최종 JSON vs 함수 호출

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. 최종 JSON | schema validation과 eval fixture가 단순하다. | 외부 데이터 조회나 side effect를 표현하지 못한다. | classification, extraction, scoring. |
| B. Function/tool calling | backend API, MCP server, RAG search를 단계적으로 실행할 수 있다. | loop, permission, error handling이 필요하다. | retrieval/tool/agent workflow. |

## Pattern 2: Tool Definition

```js
// OpenAI Responses API function tool
const workspaceSearchTool = {
  type: "function",
  name: "workspace_search",
  description: "Search authorized workspace documents and return source-backed snippets.",
  parameters: {
    type: "object",
    additionalProperties: false,
    properties: {
      workspace_id: { type: "string" },
      query: { type: "string" },
      top_k: { type: "integer", minimum: 1, maximum: 10 }
    },
    required: ["workspace_id", "query", "top_k"]
  },
  permission_tier: "read_only"
};

const openAiLoop = {
  tool_choice: "auto|required",
  parallel_tool_calls: false,
  output_handoff: { type: "function_call_output", call_id: "call_123", output: "{}" },
  strict: true,
};

const claudeToolLoop = {
  stop_reason: "tool_use",
  allowed_tools: ["workspace_search"],
  result: { type: "tool_result", tool_use_id: "toolu_123", content: "{}", is_error: true },
};
```

The tool definition must map to [[agent-tool-permissions]]: permission tier, max calls, timeout, redaction, and approval state are product behavior, not comments.

Claude Messages API client tool result handling has an ordering rule: `tool_result` 앞에 텍스트가 오면 the follow-up message can fail. OpenAI Responses API function tool loops hand execution results back with `function_call_output`. Keep `tool_choice`, required tool mode, `allowed_tools`, `parallel_tool_calls: false`, and `is_error: true` behavior in examples so tests cover the protocol edge cases.

## A/B 비교: 수동 루프 vs SDK/서버 툴

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. 수동 tool loop | 권한 승인, 로깅, 재시도, rollback을 세밀하게 통제한다. | 메시지 순서와 `tool_result` 매칭 오류가 잦다. | side effect가 크거나 감사가 필요한 업무. |
| B. SDK/서버 툴 | boilerplate를 줄이고 provider-native validation을 활용한다. | 내부 approval/audit 정책을 놓치기 쉽다. | read-only, low-risk tool path. |

## Pattern 3: MCP Server Shape

```js
const mcpServerChecklist = {
  protocol: "JSON-RPC 2.0",
  transports: ["stdio", "Streamable HTTP", "HTTP+SSE"],
  transport_guards: ["Origin", "localhost binding"],
  tools: ["workspace_search", "ticket_draft"],
  discovery: ["tools/list", "tools/call"],
  schemas: ["inputSchema", "outputSchema"],
  error_result: { isError: true },
  resources: ["workspace://{workspace_id}/documents/{document_id}"],
  prompts: ["support_triage_prompt"],
  auth: "OAuth 2.1 + Protected Resource Metadata",
  openai_remote_mcp: { type: "mcp", server_label: "workspace-docs", require_approval: "always" },
  audit: ["tool_call_id", "subject", "resource", "normalized_args", "result_summary"],
  safety: ["untrusted_tool_output", "prompt_injection_eval", "acl_boundary_eval"]
};
```

MCP server concepts separate tools, resources, and prompts. JooPark should keep that separation in docs and tests instead of treating every integration as a generic function call. The MCP contract should show JSON-RPC 2.0, stdio and Streamable HTTP transports, the legacy HTTP+SSE migration marker, Origin checks, localhost binding, `tools/list`, `tools/call`, `inputSchema`, `outputSchema`, `isError: true`, OAuth 2.1, Protected Resource Metadata, OpenAI remote MCP `type: "mcp"`, `server_label`, and `require_approval`.

## A/B 비교: 직접 tool API vs MCP

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. 직접 tool API | 코드가 작고 기존 backend endpoint를 바로 쓴다. | host/model 간 재사용, discovery, schema identity가 약하다. | single-app internal tool. |
| B. MCP 서버 | 여러 host/model에서 재사용하고 `tools/list` discovery와 resources/prompts를 확장할 수 있다. | server 운영, OAuth/Origin/approval UX, schema version 관리가 필요하다. | 조직 도구·다중 host 재사용. |

## Pattern 4: Eval Fixture

```js
const apiExampleEvalRow = {
  row_id: "support-triage-structured-001",
  prompt_release_id: "support_triage_system@17",
  tool_schema_versions: ["workspace_search@3"],
  input: "Can I get a refund for plan X after 31 days?",
  expected: {
    category: "policy",
    grounded: true,
    required_source_ids: ["refund_policy_20260601"]
  },
  graders: ["json_schema_valid", "groundedness", "citation_support"]
};
```

Examples without eval rows are tutorials. Production API examples should be executable fixtures.

## Example Governance

- Keep every example tied to a route, schema id, prompt version, and eval row.
- Avoid provider-specific code where a schema pattern is the real lesson.
- Show invalid examples in tests, not in the main product docs.
- Keep secrets and real user data out of examples.
- Add `checked_at` to examples that depend on API syntax likely to change.
- Link examples to [[source-governance]] so stale docs can be refreshed.

ReAct and Toolformer justify tool-use patterns as a first-class agent design surface, while API Design Patterns provides stable API-design vocabulary for schemas, resources, and evolution.

## Product Hook

JooPark should maintain an API examples gallery with:

- schema examples;
- tool examples;
- MCP server examples;
- eval fixtures;
- copy/run status;
- last verified date;
- linked release and route.

## Open Questions

- Should examples be generated from source code or curated as docs?
- Which SDK/language should JooPark use as the canonical example surface?
- Should MCP examples live in app docs or in a separate developer workspace?

## Backlinks

- [[index]]
- [[prompt-release-management]]
- [[eval-result-lineage]]
- [[agent-tool-permissions]]
- [[safety]]
- [[rag-evals]]
- [[source-governance]]

## References

### Web

- Anthropic. "Structured outputs." https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Anthropic. "Tool use." https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- Anthropic. "Handle tool calls." https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
- OpenAI. "Structured outputs." https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI. "Function calling." https://developers.openai.com/api/docs/guides/function-calling
- OpenAI. "Using tools." https://developers.openai.com/api/docs/guides/tools

### Standard

- Model Context Protocol. "Specification." https://modelcontextprotocol.io/specification/2025-11-25
- Model Context Protocol. "Transports." https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- Model Context Protocol. "Tools." https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- Model Context Protocol. "Authorization." https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization

### Paper

- Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models." arXiv:2210.03629. https://arxiv.org/abs/2210.03629
- Schick et al. "Toolformer: Language Models Can Teach Themselves to Use Tools." arXiv:2302.04761. https://arxiv.org/abs/2302.04761

### Book

- Geewax. "API Design Patterns." Manning, 2021. ISBN 9781617295850. https://openlibrary.org/works/OL25448641W/API_Design_Patterns
