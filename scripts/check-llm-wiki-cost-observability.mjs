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

const costSources = [
  "openai_cost_optimization",
  "openai_latency_optimization",
  "openai_batch_api",
  "openai_flex_processing",
  "openai_priority_processing",
  "openai_prompt_caching",
  "anthropic_prompt_caching",
  "anthropic_batch_processing",
  "anthropic_token_counting",
];

const observabilitySources = [
  "openai_production_best_practices",
  "openai_agents_tracing",
  "openai_cost_optimization",
  "openai_latency_optimization",
  "openai_safety_checks",
];

const registryRequired = [...new Set([...costSources, ...observabilitySources])];

checks.push({
  id: "source_registry",
  status: registryRequired.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: registryRequired.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("cost", [
  "fewer requests",
  "minimize tokens",
  "smaller model",
  "cached_tokens",
  "usage.cache_read_input_tokens",
  "Batch API / Message Batches API",
  "50% cost discount",
  "24-hour turnaround",
  "Zero Data Retention (ZDR)",
  "service_tier: \"flex\"",
  "service_tier: \"priority\"",
  "premium token cost",
  "process tokens faster",
  "time_to_first_token",
  "messages.count_tokens",
  "A/B 비교: async low-cost vs priority low-latency",
], costSources);

check("observability", [
  "trace_id",
  "span_id",
  "parent_id",
  "workflow_name",
  "group_id",
  "time_to_first_token_ms",
  "service_tier",
  "cached_tokens",
  "safety_identifier",
  "LLM generations",
  "function tool calls",
  "guardrails",
  "handoffs",
  "ZDR",
  "cost_per_success",
  "p50/p95/p99",
  "A/B 비교: provider tracing vs self-managed OpenTelemetry",
], observabilitySources);

check("source-governance", [
  "Cost/Observability 검증",
  "scripts/check-llm-wiki-cost-observability.mjs",
  "service_tier: \"flex\"",
  "service_tier: \"priority\"",
  "cached_tokens",
  "messages.count_tokens",
  "50% cost discount",
  "24-hour turnaround",
  "time_to_first_token_ms",
  "trace_id",
  "span_id",
  "workflow_name",
  "guardrails",
  "ZDR",
  "A/B 비교: async low-cost vs priority low-latency",
  "A/B 비교: provider tracing vs self-managed OpenTelemetry",
], registryRequired);

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
