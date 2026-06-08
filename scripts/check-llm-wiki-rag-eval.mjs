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
  "openai_embeddings",
  "openai_file_search",
  "openai_retrieval",
  "openai_evals",
  "openai_eval_best_practices",
  "anthropic_search_results",
  "rag_paper",
  "beir_paper",
  "mteb_paper",
];

checks.push({
  id: "source_registry",
  status: registryRequired.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: registryRequired.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("embeddings", [
  "text-embedding-3-small",
  "text-embedding-3-large",
  "dimensions",
  "cosine similarity",
  "A/B 비교: embedding 차원",
  "recall@k",
  "nDCG@10",
], ["openai_embeddings", "mteb_paper"]);

check("rag", [
  "vector_store_ids",
  "max_num_results",
  "include: [\"file_search_call.results\"]",
  "ranking_options",
  "score_threshold",
  "hybrid_search",
  "search_result",
  "citations.enabled",
  "citation coverage",
  "A/B 비교: hosted File Search vs self-managed RAG",
], ["rag_paper", "openai_file_search", "openai_retrieval", "anthropic_search_results", "beir_paper"]);

check("evaluation", [
  "data_source_config",
  "item_schema",
  "testing_criteria",
  "string_check",
  "recall@k",
  "precision@k",
  "nDCG@10",
  "MRR",
  "LLM-as-judge",
  "human labels",
  "A/B 비교: offline golden-set eval vs online shadow eval",
], ["openai_evals", "openai_eval_best_practices", "beir_paper", "mteb_paper"]);

check("source-governance", [
  "RAG/Evals 검증",
  "scripts/check-llm-wiki-rag-eval.mjs",
  "text-embedding-3-large",
  "vector_store_ids",
  "include: [\"file_search_call.results\"]",
  "citations.enabled",
  "recall@k",
  "nDCG@10",
  "testing_criteria",
], ["openai_embeddings", "openai_file_search", "openai_retrieval", "openai_evals", "openai_eval_best_practices", "anthropic_search_results", "rag_paper", "beir_paper", "mteb_paper"]);

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
