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

const promptReleaseSources = [
  "openai_prompt_engineering",
  "openai_prompt_guidance",
  "openai_eval_best_practices",
  "openai_production_best_practices",
  "openai_prompt_caching",
  "openai_model_snapshots",
  "anthropic_prompt_engineering_overview",
  "anthropic_prompting_tools",
  "anthropic_prompt_caching",
  "langfuse_prompt_management",
  "langfuse_prompt_version_control",
];

checks.push({
  id: "source_registry",
  status: promptReleaseSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: promptReleaseSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("prompt-release-management", [
  "prompt_config_bundle",
  "prompt_id",
  "prompt_version",
  "prompt_hash",
  "registry_label",
  "model_alias",
  "model_snapshot",
  "developer_message_version",
  "schema_version",
  "tool_schema_version",
  "retrieval_version",
  "safety_policy_version",
  "eval_suite_version",
  "rollout_stage",
  "rollback_target",
  "developer and user messages",
  "model-specific prompt tuning",
  "stable prompt prefix",
  "cached_tokens",
  "prompt templates and variables",
  "prompt generator",
  "prompt improver",
  "evaluation tool",
  "storing, versioning, retrieving",
  "version ID",
  "labels",
  "production",
  "staging",
  "prod-a",
  "prod-b",
  "production label",
  "protected prompt labels",
  "eval-driven development",
  "golden dataset",
  "regression set",
  "safety probes",
  "canary-10pct",
  "user_correction_rate",
  "refusal_rate",
  "cost_per_success",
  "rollback runbook",
  "label revert",
  "cache warmup",
  "A/B 비교: hardcoded prompts in code vs prompt registry labels",
  "A/B 비교: model alias vs pinned model snapshot",
  "A/B 비교: big-bang prompt deploy vs staged eval/canary",
], promptReleaseSources);

check("source-governance", [
  "Prompt Release/Version 검증",
  "scripts/check-llm-wiki-prompt-release-management.mjs",
  "OpenAI prompt engineering",
  "OpenAI prompt guidance",
  "OpenAI evaluation best practices",
  "OpenAI production best practices",
  "OpenAI prompt caching",
  "OpenAI model snapshots",
  "Anthropic prompt engineering overview",
  "Anthropic prompting tools",
  "Anthropic prompt caching",
  "Langfuse prompt management",
  "Langfuse prompt version control",
  "prompt_config_bundle",
  "prompt_id",
  "prompt_version",
  "prompt_hash",
  "registry_label",
  "model_alias",
  "model_snapshot",
  "developer_message_version",
  "schema_version",
  "tool_schema_version",
  "retrieval_version",
  "safety_policy_version",
  "eval_suite_version",
  "rollout_stage",
  "rollback_target",
  "developer and user messages",
  "stable prompt prefix",
  "cached_tokens",
  "prompt templates and variables",
  "prompt generator",
  "prompt improver",
  "evaluation tool",
  "storing, versioning, retrieving",
  "version ID",
  "labels",
  "production",
  "staging",
  "prod-a",
  "prod-b",
  "production label",
  "protected prompt labels",
  "eval-driven development",
  "golden dataset",
  "regression set",
  "canary-10pct",
  "rollback runbook",
  "A/B 비교: hardcoded prompts in code vs prompt registry labels",
  "A/B 비교: model alias vs pinned model snapshot",
  "A/B 비교: big-bang prompt deploy vs staged eval/canary",
], promptReleaseSources);

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
