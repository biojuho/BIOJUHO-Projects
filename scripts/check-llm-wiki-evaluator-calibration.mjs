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

const calibrationSources = [
  "openai_evals",
  "openai_eval_best_practices",
  "openai_graders",
  "langfuse_scores_overview",
  "langfuse_llm_as_judge",
  "langfuse_annotation_queues",
  "langfuse_experiments_sdk",
  "llm_judge_mt_bench",
  "ge_eval_paper",
];

const calibrationTerms = [
  "evaluator_calibration",
  "judge_calibration_contract",
  "judge_id",
  "judge_model",
  "judge_prompt_hash",
  "rubric_version",
  "score_config_id",
  "score_type",
  "numeric_scale",
  "categorical_labels",
  "boolean_threshold",
  "human_alignment_set",
  "human_label_batch_id",
  "annotator_id",
  "annotator_role",
  "blinded_review",
  "randomized_order",
  "inter_annotator_agreement",
  "golden_label",
  "adjudicated_label",
  "disagreement_reason",
  "label_confidence",
  "calibration_set_id",
  "calibration_split",
  "judge_human_agreement",
  "pairwise_agreement",
  "kappa",
  "spearman_correlation",
  "kendall_tau",
  "mean_absolute_error",
  "calibration_curve",
  "drift_window",
  "judge_drift",
  "label_drift",
  "threshold_drift",
  "position_bias",
  "verbosity_bias",
  "self_preference_bias",
  "reference_leakage",
  "rubric_ambiguity",
  "grader_hacking",
  "pass_threshold",
  "sampling_params",
  "seed",
  "temperature",
  "reasoning_effort",
  "score_model",
  "LLM-as-a-Judge",
  "Annotation Queues",
  "score config",
  "corrected outputs",
  "score reasoning",
  "human reviewers",
  "Human evals",
  "MT-Bench",
  "Chatbot Arena",
  "over 80% agreement",
  "G-Eval",
  "form-filling paradigm",
  "A/B 비교: LLM-as-a-Judge vs human review",
  "A/B 비교: single judge vs judge panel",
  "A/B 비교: fixed rubric vs evolving rubric",
];

checks.push({
  id: "source_registry",
  status: calibrationSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: calibrationSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("evaluator-calibration", calibrationTerms, calibrationSources);

check("source-governance", [
  "Evaluator Calibration 검증",
  "scripts/check-llm-wiki-evaluator-calibration.mjs",
  "OpenAI Evals",
  "OpenAI evaluation best practices",
  "OpenAI graders",
  "Langfuse scores overview",
  "Langfuse LLM-as-a-Judge",
  "Langfuse Annotation Queues",
  "Langfuse experiments via SDK",
  "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena",
  "G-Eval",
  ...calibrationTerms,
], calibrationSources);

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
