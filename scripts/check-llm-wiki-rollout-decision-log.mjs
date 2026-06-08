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

const rolloutSources = [
  "openai_evals",
  "openai_eval_best_practices",
  "langfuse_experiments_sdk",
  "langfuse_scores_overview",
  "langfuse_experiments_ci_cd",
  "openfeature_evaluation_context",
  "opentelemetry_feature_flag_semconv",
  "argo_rollouts_canary",
  "github_actions_environments",
  "kubernetes_deployment_rollback",
];

const rolloutTerms = [
  "rollout_decision_log",
  "rollout_decision_contract",
  "decision_id",
  "action_item_id",
  "postmortem_id",
  "release_candidate_id",
  "eval_run_id",
  "dataset_run_id",
  "acceptance_eval_run_id",
  "regression_eval_suite",
  "rollout_stage",
  "rollout_strategy",
  "feature_flag_key",
  "feature_flag_context",
  "targeting_key",
  "flag_variant",
  "feature_flag.result.variant",
  "feature_flag.result.reason",
  "feature_flag.version",
  "feature_flag.provider.name",
  "canary_weight",
  "canary_step_index",
  "canary_analysis_run_id",
  "analysis_status",
  "abort_on_failed_analysis",
  "guarded_promote",
  "promote_criteria",
  "rollback_target",
  "rollback_trigger",
  "rollback_runbook_id",
  "rollback_window",
  "stable_replica_set",
  "deployment_environment",
  "environment_protection_rule",
  "required_reviewers",
  "wait_timer",
  "deployment_status_id",
  "decision_owner_id",
  "approver_id",
  "blast_radius",
  "observability_window",
  "decision_status",
  "go_decision",
  "no_go_decision",
  "risk_acceptance",
  "RegressionError",
  "targeting key",
  "setWeight",
  "pause",
  "stable/canary ReplicaSet",
  "required reviewers",
  "Deployment rollback",
  "A/B 비교: feature flag rollout vs deployment canary",
  "A/B 비교: automatic abort vs human approval",
  "A/B 비교: dashboard decision vs app-owned decision log",
];

checks.push({
  id: "source_registry",
  status: rolloutSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: rolloutSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("rollout-decision-log", rolloutTerms, rolloutSources);

check("source-governance", [
  "Rollout Decision Log 검증",
  "scripts/check-llm-wiki-rollout-decision-log.mjs",
  "OpenAI Evals",
  "OpenAI evaluation best practices",
  "Langfuse experiments via SDK",
  "Langfuse scores overview",
  "Langfuse experiments in CI/CD",
  "OpenFeature Evaluation Context",
  "OpenTelemetry feature flag semantic conventions",
  "Argo Rollouts canary strategy",
  "GitHub Actions deployment environments",
  "Kubernetes deployment rollbacks",
  ...rolloutTerms,
], rolloutSources);

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
