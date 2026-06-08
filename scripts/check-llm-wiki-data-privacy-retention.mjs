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

const privacySources = [
  "openai_data_controls",
  "anthropic_api_data_retention",
  "anthropic_training_privacy",
  "anthropic_standard_retention",
  "google_gemini_api_terms",
  "vercel_ai_gateway_zdr",
  "owasp_llm02_sensitive_information",
];

checks.push({
  id: "source_registry",
  status: privacySources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: privacySources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("data-privacy-retention", [
  "LLM02:2025 Sensitive Information Disclosure",
  "data_inventory",
  "data_classification",
  "PII",
  "PHI",
  "secrets",
  "source retention class",
  "not used to train",
  "abuse monitoring logs",
  "retained for up to 30 days",
  "store: false",
  "Application State",
  "MCP servers are third-party services",
  "automatically delete inputs and outputs on our backend within 30 days",
  "Files API",
  "explicitly deleted",
  "ZDR applies to Messages and Token Counting APIs",
  "2 years",
  "7 years",
  "Unpaid Services",
  "Paid Services",
  "human reviewers may read",
  "Do not submit sensitive, confidential, or personal information to the Unpaid Services",
  "zeroDataRetention: true",
  "BYOK",
  "prompts, outputs, or sensitive data",
  "By default, AI Gateway does not route based on the data retention policy",
  "provider_route",
  "redaction_policy",
  "deletion_sla_days",
  "prompt_hash",
  "delete_request_id",
  "A/B 비교: default API retention vs zero data retention",
  "A/B 비교: unpaid/free developer tier vs paid/commercial API",
  "A/B 비교: raw observability logs vs redacted audit ledger",
], privacySources);

check("source-governance", [
  "Data Privacy/Retention 검증",
  "scripts/check-llm-wiki-data-privacy-retention.mjs",
  "OpenAI data controls",
  "Anthropic API data handling",
  "Anthropic commercial data use and training",
  "Anthropic standard data retention",
  "Google Gemini API terms",
  "Vercel AI Gateway ZDR",
  "OWASP LLM02:2025",
  "LLM02:2025 Sensitive Information Disclosure",
  "data_inventory",
  "data_classification",
  "PII",
  "PHI",
  "secrets",
  "source retention class",
  "not used to train",
  "abuse monitoring logs",
  "retained for up to 30 days",
  "store: false",
  "Application State",
  "MCP servers are third-party services",
  "automatically delete inputs and outputs on our backend within 30 days",
  "Files API",
  "explicitly deleted",
  "ZDR applies to Messages and Token Counting APIs",
  "Unpaid Services",
  "Paid Services",
  "human reviewers may read",
  "Do not submit sensitive, confidential, or personal information to the Unpaid Services",
  "zeroDataRetention: true",
  "BYOK",
  "A/B 비교: default API retention vs zero data retention",
  "A/B 비교: unpaid/free developer tier vs paid/commercial API",
  "A/B 비교: raw observability logs vs redacted audit ledger",
], privacySources);

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
