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

const runtimeSources = [
  "openai_rate_limits",
  "openai_error_codes",
  "openai_api_request_debugging",
  "anthropic_rate_limits",
  "anthropic_errors",
  "anthropic_rate_limits_api",
  "google_gemini_rate_limits",
  "google_gemini_troubleshooting",
  "vercel_ai_gateway_provider_options",
  "vercel_ai_gateway_provider_timeouts",
  "vercel_ai_gateway_fallbacks",
];

checks.push({
  id: "source_registry",
  status: runtimeSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: runtimeSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("runtime-reliability", [
  "success_rate",
  "p95_latency_ms",
  "retry_count",
  "fallback_rate",
  "rate_limit_headroom",
  "error_budget_burn",
  "RPM",
  "RPD",
  "TPM",
  "TPD",
  "IPM",
  "x-ratelimit-limit-requests",
  "x-ratelimit-remaining-tokens",
  "x-ratelimit-reset-requests",
  "random exponential backoff",
  "unsuccessful requests contribute to your per-minute limit",
  "503 - Slow Down",
  "x-request-id",
  "X-Client-Request-Id",
  "token bucket algorithm",
  "retry-after",
  "anthropic-ratelimit-requests-remaining",
  "anthropic-ratelimit-requests-reset",
  "anthropic-ratelimit-input-tokens-reset",
  "429 rate_limit_error",
  "504 timeout_error",
  "529 overloaded_error",
  "request-id",
  "SSE after 200",
  "Rate Limits API",
  "group_type",
  "requests_per_minute",
  "input_tokens_per_minute",
  "output_tokens_per_minute",
  "per project, not per API key",
  "RPD quotas reset at midnight Pacific time",
  "experimental and preview models",
  "429 RESOURCE_EXHAUSTED",
  "500 INTERNAL",
  "503 UNAVAILABLE",
  "504 DEADLINE_EXCEEDED",
  "providerOptions.gateway",
  "providerTimeouts",
  "order",
  "only",
  "models",
  "BYOK",
  "first token arrives",
  "retryable_status",
  "non_retryable_status",
  "max_attempts",
  "honor_retry_after",
  "client_timeout_ms",
  "fallback_models",
  "idempotency_key",
  "x_client_request_id",
  "fallback_reason",
  "served_model",
  "served_provider",
  "timeout_phase",
  "A/B 비교: blind exponential retry vs header-aware client throttling",
  "A/B 비교: single-provider retry vs cross-provider failover",
  "A/B 비교: long timeout vs fast failover timeout",
], runtimeSources);

check("source-governance", [
  "Runtime Reliability 검증",
  "scripts/check-llm-wiki-runtime-reliability.mjs",
  "OpenAI rate limits",
  "OpenAI error codes",
  "OpenAI API request debugging",
  "Anthropic rate limits",
  "Anthropic API errors",
  "Anthropic Rate Limits API",
  "Google Gemini API rate limits",
  "Google Gemini API troubleshooting",
  "Vercel AI Gateway provider options",
  "Vercel AI Gateway provider timeouts",
  "Vercel AI Gateway model fallbacks",
  "RPM",
  "RPD",
  "TPM",
  "TPD",
  "IPM",
  "x-ratelimit-limit-requests",
  "random exponential backoff",
  "unsuccessful requests contribute to your per-minute limit",
  "503 - Slow Down",
  "x-request-id",
  "X-Client-Request-Id",
  "token bucket algorithm",
  "retry-after",
  "anthropic-ratelimit-requests-remaining",
  "429 rate_limit_error",
  "504 timeout_error",
  "529 overloaded_error",
  "request-id",
  "SSE after 200",
  "Rate Limits API",
  "group_type",
  "per project, not per API key",
  "RESOURCE_EXHAUSTED",
  "DEADLINE_EXCEEDED",
  "providerOptions.gateway",
  "providerTimeouts",
  "order",
  "only",
  "models",
  "BYOK",
  "first token arrives",
  "A/B 비교: blind exponential retry vs header-aware client throttling",
  "A/B 비교: single-provider retry vs cross-provider failover",
  "A/B 비교: long timeout vs fast failover timeout",
], runtimeSources);

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
