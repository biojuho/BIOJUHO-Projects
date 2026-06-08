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

const lineageSources = [
  "openai_evals",
  "openai_graders",
  "openai_agents_tracing",
  "langfuse_experiments_sdk",
  "langfuse_experiment_data_model",
  "mlflow_tracking",
  "opentelemetry_genai_semconv",
  "w3c_prov_dm",
  "openai_data_controls",
];

const lineageTerms = [
  "eval_result_lineage",
  "eval_result_lineage_contract",
  "experiment_id",
  "experiment_run_id",
  "eval_id",
  "eval_run_id",
  "result_id",
  "report_url",
  "result_counts",
  "dataset_id",
  "dataset_version",
  "dataset_hash",
  "dataset_run_id",
  "source_trace_id",
  "source_observation_id",
  "trace_id",
  "span_id",
  "parent_id",
  "workflow_name",
  "group_id",
  "prompt_id",
  "prompt_version",
  "prompt_hash",
  "model_alias",
  "model_snapshot",
  "provider_name",
  "grader_id",
  "grader_version",
  "grader_type",
  "score_model",
  "pass_threshold",
  "metric_name",
  "metric_value",
  "artifact_uri",
  "raw_results_jsonl",
  "confusion_matrix_uri",
  "code_version",
  "config_hash",
  "lineage_schema_version",
  "decision_id",
  "rollback_target",
  "retention_class",
  "redaction_status",
  "failure_cluster_id",
  "lineage_complete=false",
  "sourceTraceId",
  "sourceObservationId",
  "DatasetRun",
  "grader hacking",
  "flush_traces()",
  "gen_ai.operation.name",
  "gen_ai.provider.name",
  "gen_ai.request.model",
  "gen_ai.response.model",
  "W3C PROV-DM",
  "Entity",
  "Activity",
  "Agent",
  "wasGeneratedBy",
  "used",
  "wasDerivedFrom",
  "wasAssociatedWith",
  "A/B 비교: vendor dashboard result vs app-owned experiment ledger",
  "A/B 비교: trace-first debugging vs eval-first release gate",
  "A/B 비교: OpenTelemetry attributes vs W3C PROV graph",
];

checks.push({
  id: "source_registry",
  status: lineageSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: lineageSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("eval-result-lineage", lineageTerms, lineageSources);

check("source-governance", [
  "Eval Result Lineage 검증",
  "scripts/check-llm-wiki-eval-result-lineage.mjs",
  "OpenAI Evals API",
  "OpenAI graders",
  "OpenAI Agents SDK tracing",
  "Langfuse experiments via SDK",
  "Langfuse experiment data model",
  "MLflow Tracking",
  "OpenTelemetry GenAI semantic conventions",
  "W3C PROV-DM",
  ...lineageTerms,
], lineageSources);

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
