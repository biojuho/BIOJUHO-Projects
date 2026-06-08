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

const multimodalSources = [
  "openai_images_vision",
  "openai_file_inputs",
  "openai_speech_to_text",
  "openai_file_search",
  "anthropic_vision",
  "anthropic_pdf_support",
  "anthropic_citations",
  "google_gemini_files",
  "google_gemini_vision",
];

checks.push({
  id: "source_registry",
  status: multimodalSources.every((id) => wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08") ? "pass" : "fail",
  missingTerms: [],
  missingSources: multimodalSources.filter((id) => !(wiki.sources?.[id]?.url?.startsWith("https://") && wiki.sources[id].checked === "2026-06-08")),
});

check("multimodal-file-inputs", [
  "input_image",
  "input_file",
  "file_id",
  "image_url",
  "detail: \"low\"",
  "detail: \"high\"",
  "detail: \"original\"",
  "type: \"image\"",
  "type: \"document\"",
  "citations: {enabled: true}",
  "citations.enabled=true",
  "client.files.upload",
  "createPartFromUri(myfile.uri, myfile.mimeType)",
  "20 MB",
  "OCR",
  "page number",
  "quote snippet",
  "include: [\"file_search_call.results\"]",
  "speech-to-text",
  "gpt-4o-transcribe",
  "gpt-4o-mini-transcribe",
  "gpt-4o-transcribe-diarize",
  "chunking_strategy: \"auto\"",
  "timestamp_granularities",
  "source chips",
  "citation ledger",
  "answer_span",
  "A/B 비교: direct multimodal context vs extracted ingestion pipeline",
  "A/B 비교: provider-native citations vs app-owned citation ledger",
], multimodalSources);

check("source-governance", [
  "Multimodal/File 검증",
  "scripts/check-llm-wiki-multimodal-files.mjs",
  "input_image",
  "input_file",
  "file_id",
  "detail: \"high\"",
  "type: \"image\"",
  "type: \"document\"",
  "citations.enabled=true",
  "gpt-4o-transcribe",
  "gpt-4o-mini-transcribe",
  "source chips",
  "page number",
  "quote snippet",
  "A/B 비교: direct multimodal context vs extracted ingestion pipeline",
  "A/B 비교: provider-native citations vs app-owned citation ledger",
], multimodalSources);

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
