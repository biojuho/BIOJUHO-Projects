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
  "openai_safety_best_practices",
  "openai_safety_checks",
  "anthropic_mitigate_jailbreaks",
  "anthropic_reduce_prompt_leak",
  "owasp_llm01_prompt_injection",
  "mcp_security_best_practices",
];

checks.push({
  id: "source_registry",
  status: registryRequired.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: registryRequired.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("safety", [
  "LLM01:2025",
  "direct prompt injection",
  "indirect prompt injection",
  "tool_result blocks",
  "JSON-encode untrusted content",
  "Moderation API",
  "safety_identifier",
  "Human in the loop (HITL)",
  "red-teaming",
  "per-client consent",
  "redirect_uri",
  "OAuth state",
  "token passthrough",
  "Prompt leak",
  "foolproof",
  "A/B 비교: prompt-only guardrails vs layered enforcement",
  "fail closed",
], registryRequired);

check("source-governance", [
  "Safety/Guardrail 검증",
  "scripts/check-llm-wiki-safety-ops.mjs",
  "LLM01:2025",
  "direct prompt injection",
  "indirect prompt injection",
  "tool_result blocks",
  "JSON-encode untrusted content",
  "Moderation API",
  "safety_identifier",
  "Human in the loop (HITL)",
  "per-client consent",
  "redirect_uri",
  "OAuth state",
  "token passthrough",
  "A/B 비교: prompt-only guardrails vs layered enforcement",
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
