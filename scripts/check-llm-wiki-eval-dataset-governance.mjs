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

const evalDatasetSources = [
  "openai_eval_datasets",
  "openai_evals",
  "openai_eval_best_practices",
  "openai_graders",
  "anthropic_eval_tool",
  "huggingface_dataset_cards",
  "datasheets_for_datasets",
  "data_cards_paper",
  "benchmark_data_contamination_survey",
  "openai_data_controls",
  "owasp_llm02_sensitive_information",
];

const evalDatasetTerms = [
  "eval_dataset_governance",
  "eval_dataset_contract",
  "dataset_id",
  "dataset_version",
  "dataset_hash",
  "schema_version",
  "item_schema",
  "data_source_config",
  "testing_criteria",
  "dataset_card",
  "datasheet",
  "data_card",
  "golden_set",
  "regression_set",
  "canary_set",
  "red_team_set",
  "holdout_set",
  "shadow_set",
  "production_sample",
  "consented_sample",
  "synthetic_sample",
  "redacted_fixture",
  "pii_redacted",
  "retention_class",
  "delete_request_id",
  "data_freshness_days",
  "stale_after_days",
  "license",
  "collection_method",
  "intended_use",
  "out_of_scope_use",
  "annotation_guidelines",
  "label_source",
  "subject_matter_expert",
  "inter_annotator_agreement",
  "privacy_review",
  "Evals platform deprecating",
  "read-only",
  "October 31, 2026",
  "shut down",
  "November 30, 2026",
  "generated outputs",
  "expert annotations",
  "string_check",
  "text_similarity",
  "score_model",
  "grader_alignment_set",
  "Claude Console Evaluation tool",
  "Generate Test Case",
  "CSV import",
  "side-by-side comparison",
  "quality grading",
  "prompt versioning",
  "human approval",
  "benchmark data contamination",
  "inflated or unreliable performance",
  "train/test leakage",
  "contamination_check",
  "temporal_holdout",
  "entity_holdout",
  "n-gram overlap",
  "near_duplicate",
  "generator_model",
  "prompt_hash",
  "reviewer_id",
  "task distribution drift",
  "label drift",
  "grader drift",
  "A/B 비교: production sample vs synthetic edge-case set",
  "A/B 비교: static golden set vs dynamic eval flywheel",
  "A/B 비교: public benchmark vs private holdout",
];

checks.push({
  id: "source_registry",
  status: evalDatasetSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: evalDatasetSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("eval-dataset-governance", evalDatasetTerms, evalDatasetSources);

check("source-governance", [
  "Eval Dataset Governance 검증",
  "scripts/check-llm-wiki-eval-dataset-governance.mjs",
  "OpenAI evaluation datasets",
  "OpenAI Evals API",
  "OpenAI evaluation best practices",
  "OpenAI graders",
  "Anthropic Claude Console Evaluation tool",
  "Hugging Face Dataset Cards",
  "Datasheets for Datasets",
  "Data Cards for Responsible AI",
  "Benchmark Data Contamination of LLMs",
  ...evalDatasetTerms,
], evalDatasetSources);

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
