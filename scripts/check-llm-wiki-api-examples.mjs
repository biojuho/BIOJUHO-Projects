#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(join(root, "llm-wiki-view.js"), "utf8");
const context = { window: {} };
vm.runInNewContext(source, context, { filename: "llm-wiki-view.js" });

const wiki = context.window.JooParkLlmWikiView?.data;
if (!wiki) {
  console.error(JSON.stringify({ status: "fail", error: "missing JooParkLlmWikiView data" }, null, 2));
  process.exit(1);
}

const articles = wiki.categories.flatMap((cat) => (cat.articles || []).map((article) => ({ cat, article })));
const byId = new Map(articles.map((entry) => [entry.article.id, entry]));
const checks = [];

function body(id) {
  const entry = byId.get(id);
  return entry ? entry.article.body || "" : "";
}

function articleSources(id) {
  const entry = byId.get(id);
  return entry ? entry.article.sources || [] : [];
}

function check(id, terms, sources = []) {
  const text = body(id);
  const actualSources = articleSources(id);
  const missingTerms = terms.filter((term) => !text.includes(term));
  const missingSources = sources.filter((sourceId) => !actualSources.includes(sourceId));
  checks.push({
    id,
    status: missingTerms.length || missingSources.length ? "fail" : "pass",
    missingTerms,
    missingSources,
  });
}

const registryRequired = [
  "anthropic_structured_outputs",
  "anthropic_tool_use",
  "anthropic_handle_tool_calls",
  "openai_structured_outputs",
  "openai_function_calling",
  "openai_tools",
  "mcp_spec",
  "mcp_transports",
  "mcp_tools",
  "mcp_authorization",
];

checks.push({
  id: "source_registry",
  status: registryRequired.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: registryRequired.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("structured-output", [
  "output_config: {format: {type: \"json_schema\"",
  "OpenAI Responses API",
  "text: {",
  "response_format: {type: \"json_schema\"",
  "strict: true",
  "additionalProperties: false",
  "A/B 비교: 최종 JSON vs 함수 호출",
  "Function/tool calling",
], ["anthropic_structured_outputs", "openai_structured_outputs", "openai_function_calling"]);

check("tool-use", [
  "OpenAI Responses API function tool",
  "Claude Messages API client tool result",
  "tool_choice",
  "required",
  "allowed_tools",
  "parallel_tool_calls: false",
  "stop_reason: \"tool_use\"",
  "`tool_result` 앞에 텍스트",
  "is_error: true",
  "function_call_output",
  "strict: true",
  "A/B 비교: 수동 루프 vs SDK/서버 툴",
], ["anthropic_tool_use", "anthropic_handle_tool_calls", "openai_function_calling", "openai_tools"]);

check("mcp", [
  "JSON-RPC 2.0",
  "stdio",
  "Streamable HTTP",
  "HTTP+SSE",
  "Origin",
  "localhost binding",
  "tools/list",
  "tools/call",
  "inputSchema",
  "outputSchema",
  "isError: true",
  "OAuth 2.1",
  "Protected Resource Metadata",
  "type: \"mcp\"",
  "server_label",
  "require_approval",
  "A/B 비교: 직접 tool API vs MCP",
], ["mcp_spec", "mcp_transports", "mcp_tools", "mcp_authorization", "openai_tools"]);

check("source-governance", [
  "API 예시 검증",
  "scripts/check-llm-wiki-api-examples.mjs",
  "Claude `tool_result` ordering",
  "MCP `tools/list`, `tools/call`, `Streamable HTTP`, `OAuth 2.1` marker",
], ["anthropic_structured_outputs", "openai_structured_outputs", "mcp_tools"]);

const failed = checks.filter((item) => item.status !== "pass");
const payload = {
  status: failed.length ? "fail" : "pass",
  checkedAt: new Date().toISOString(),
  articleCount: articles.length,
  sourceCount: Object.keys(wiki.sources || {}).length,
  checks,
};

console.log(JSON.stringify(payload, null, 2));
if (failed.length) process.exit(1);
