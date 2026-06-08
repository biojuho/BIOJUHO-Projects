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

const modelOptimizationSources = [
  "openai_model_optimization",
  "openai_supervised_fine_tuning",
  "openai_external_models",
  "openai_evals",
  "openai_eval_best_practices",
  "anthropic_fine_tuning_glossary",
  "google_gemini_model_tuning",
  "vercel_ai_gateway_fallbacks",
  "vercel_ai_gateway_observability",
  "distillation_paper",
];

checks.push({
  id: "source_registry",
  status: modelOptimizationSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: modelOptimizationSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("model-optimization-routing", [
  "eval baseline",
  "fine-tuning platform is winding down",
  "not accessible to new users",
  "Supervised fine-tuning (SFT)",
  "Vision fine-tuning",
  "Direct preference optimization (DPO)",
  "Reinforcement fine-tuning (RFT)",
  "gpt-4.1-mini-2025-04-14",
  "Claude API does not currently offer fine-tuning",
  "Gemini API or AI Studio no longer have a model available which supports fine-tuning",
  "purpose: \"fine-tune\"",
  "fineTuning.jobs.create",
  "POST /v1/fine_tuning/jobs",
  "training_file",
  "validation_file",
  "suffix",
  "JSONL chat-completions",
  "holdout data",
  "full_valid_loss",
  "full_valid_mean_token_accuracy",
  "teacher model",
  "student model",
  "providerOptions.gateway.models",
  "fallback_reason",
  "served_model",
  "served_provider",
  "provider metadata",
  "router_decision",
  "eval_version",
  "policy_version",
  "time_to_first_token",
  "third-party terms",
  "weaker safety guarantees",
  "A/B 비교: fine-tuning vs RAG",
  "A/B 비교: static routing matrix vs gateway fallback",
  "A/B 비교: teacher-student distillation vs runtime routing",
], modelOptimizationSources);

check("source-governance", [
  "Model Optimization/Routing 검증",
  "scripts/check-llm-wiki-model-optimization-routing.mjs",
  "fine-tuning platform is winding down",
  "not accessible to new users",
  "Supervised fine-tuning (SFT)",
  "Direct preference optimization (DPO)",
  "Reinforcement fine-tuning (RFT)",
  "purpose: \"fine-tune\"",
  "training_file",
  "validation_file",
  "fineTuning.jobs.create",
  "full_valid_loss",
  "full_valid_mean_token_accuracy",
  "Claude API does not currently offer fine-tuning",
  "Gemini API or AI Studio no longer have a model available",
  "providerOptions.gateway.models",
  "router_decision",
  "fallback_reason",
  "served_model",
  "served_provider",
  "A/B 비교: fine-tuning vs RAG",
  "A/B 비교: static routing matrix vs gateway fallback",
  "A/B 비교: teacher-student distillation vs runtime routing",
], modelOptimizationSources);

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
