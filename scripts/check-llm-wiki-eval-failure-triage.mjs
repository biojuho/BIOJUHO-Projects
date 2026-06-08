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

const triageSources = [
  "openai_evals",
  "openai_eval_best_practices",
  "openai_graders",
  "openai_agents_tracing",
  "langfuse_scores_overview",
  "langfuse_experiments_sdk",
  "langfuse_experiment_data_model",
  "google_sre_incident_management",
  "nist_incident_handling",
  "tool_augmented_llm_failure_taxonomy",
  "owasp_llm01_prompt_injection",
  "owasp_llm02_sensitive_information",
  "owasp_llm06_excessive_agency",
];

const triageTerms = [
  "eval_failure_triage",
  "failure_triage_taxonomy",
  "failure_cluster_id",
  "incident_id",
  "severity",
  "user_impact",
  "blast_radius",
  "detection_source",
  "score_name",
  "score_value",
  "score_comment",
  "NUMERIC",
  "CATEGORICAL",
  "BOOLEAN",
  "TEXT",
  "Open coding",
  "axial coding",
  "failure_mode",
  "root_cause_layer",
  "symptom",
  "attribution_confidence",
  "owner_team",
  "time_to_detect_ms",
  "time_to_triage_ms",
  "time_to_mitigate_ms",
  "regression_bug",
  "retrieval_miss",
  "retrieval_irrelevant",
  "generator_ignored_top_doc",
  "citation_mismatch",
  "stale_context",
  "prompt_regression",
  "schema_violation",
  "tool_selection_error",
  "tool_parameter_error",
  "tool_execution_error",
  "tool_result_interpretation_error",
  "policy_violation",
  "pii_leak",
  "excessive_agency",
  "latency_regression",
  "cost_regression",
  "rate_limit_regression",
  "guardrail_false_positive",
  "guardrail_false_negative",
  "judge_drift",
  "data_drift",
  "label_drift",
  "cluster_signature_hash",
  "representative_trace_id",
  "runbook_id",
  "mitigation_status",
  "postmortem_required",
  "blameless postmortem",
  "Incident Commander",
  "Communications Lead",
  "Operations Lead",
  "Preparation",
  "Detection and Analysis",
  "Containment, Eradication, and Recovery",
  "Post-Incident Activity",
  "NIST SP 800-61",
  "score analytics",
  "annotation queue",
  "full execution traces",
  "A/B 비교: manual taxonomy vs embedding clustering",
  "A/B 비교: symptom cluster vs root-cause cluster",
  "A/B 비교: eval-only triage vs incident workflow",
];

checks.push({
  id: "source_registry",
  status: triageSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: triageSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("eval-failure-triage", triageTerms, triageSources);

check("source-governance", [
  "Eval Failure Triage 검증",
  "scripts/check-llm-wiki-eval-failure-triage.mjs",
  "OpenAI Evals API",
  "OpenAI evaluation best practices",
  "OpenAI graders",
  "OpenAI Agents SDK tracing",
  "Langfuse scores overview",
  "Langfuse experiments via SDK",
  "Langfuse experiment data model",
  "Google SRE incident management",
  "NIST SP 800-61",
  "A Taxonomy of Failures in Tool-Augmented LLMs",
  ...triageTerms,
], triageSources);

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
