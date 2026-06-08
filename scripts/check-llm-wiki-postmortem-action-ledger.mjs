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

const actionLedgerSources = [
  "openai_evals",
  "openai_eval_best_practices",
  "openai_graders",
  "langfuse_scores_overview",
  "langfuse_annotation_queues",
  "langfuse_experiments_sdk",
  "google_sre_incident_management",
  "google_sre_postmortem_culture",
  "google_sre_workbook_postmortem",
  "nist_incident_handling",
  "nist_sp_800_61r3",
];

const actionLedgerTerms = [
  "postmortem_action_ledger",
  "postmortem_action_contract",
  "action_item_id",
  "postmortem_id",
  "incident_id",
  "failure_cluster_id",
  "eval_run_id",
  "dataset_run_id",
  "trace_id",
  "judge_id",
  "score_config_id",
  "calibration_set_id",
  "action_type",
  "prevent_action",
  "detect_action",
  "mitigate_action",
  "owner_team",
  "action_owner_id",
  "tracking_ticket",
  "priority",
  "due_at",
  "verifiable_end_state",
  "acceptance_eval_id",
  "acceptance_eval_run_id",
  "regression_eval_suite",
  "closure_evidence_uri",
  "closure_reviewer_id",
  "postmortem_reviewed_at",
  "blameless",
  "root_cause",
  "trigger",
  "lessons_learned",
  "recurrence_linked_incident_id",
  "stale_action_escalation",
  "CSF 2.0",
  "Govern",
  "Identify",
  "Protect",
  "Detect",
  "Respond",
  "Recover",
  "lessons learned",
  "continuous improvement",
  "score analytics",
  "Annotation Queues",
  "score config",
  "action_status=closed",
  "risk_acceptance",
  "A/B 비교: free-form postmortem vs action ledger",
  "A/B 비교: manual closure vs eval-gated closure",
  "A/B 비교: prevent vs detect/mitigate action",
];

checks.push({
  id: "source_registry",
  status: actionLedgerSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: actionLedgerSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("postmortem-action-ledger", actionLedgerTerms, actionLedgerSources);

check("source-governance", [
  "Postmortem Action Ledger 검증",
  "scripts/check-llm-wiki-postmortem-action-ledger.mjs",
  "OpenAI Evals",
  "OpenAI evaluation best practices",
  "OpenAI graders",
  "Langfuse scores overview",
  "Langfuse Annotation Queues",
  "Langfuse experiments via SDK",
  "Google SRE incident management",
  "Google SRE postmortem culture",
  "Google SRE Workbook postmortem practices",
  "NIST Computer Security Incident Handling Guide",
  "NIST SP 800-61 Rev. 3",
  ...actionLedgerTerms,
], actionLedgerSources);

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
