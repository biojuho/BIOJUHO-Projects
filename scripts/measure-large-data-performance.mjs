#!/usr/bin/env node

import { performance } from "node:perf_hooks";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function finiteNumberOption(value, fallback) {
  if (value === undefined || value === null || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function boundedIntegerOption(value, fallback, minimum = 0) {
  return Math.max(minimum, Math.trunc(finiteNumberOption(value, fallback)));
}

const issueCount = boundedIntegerOption(process.env.JOOPARK_PERF_ISSUES, 5000, 1);
const storageItems = boundedIntegerOption(process.env.JOOPARK_PERF_STORAGE_ITEMS, 2500, 1);
const maxKanbanModelMs = finiteNumberOption(process.env.JOOPARK_PERF_MAX_KANBAN_MODEL_MS, 150);
const maxKanbanRenderMs = finiteNumberOption(process.env.JOOPARK_PERF_MAX_KANBAN_RENDER_MS, 900);
const maxKanbanRenderedCards = finiteNumberOption(process.env.JOOPARK_PERF_MAX_KANBAN_RENDERED_CARDS, 360);
const maxStorageSerializeMs = finiteNumberOption(process.env.JOOPARK_PERF_MAX_STORAGE_SERIALIZE_MS, 250);
// Wall-clock timing on shared CI runners is noisy, and noise is one-sided: it only
// ever *adds* time to a sample, never removes it. A single sample therefore flakes
// (observed kanban render 334ms–906ms run-to-run). Taking the minimum of N warmed-up
// samples converges on the true compute cost — the cleanest sample is the least
// contended one — so thresholds stay tight (regression-sensitive) without flaking.
const perfSamples = boundedIntegerOption(process.env.JOOPARK_PERF_SAMPLES, 5, 1);
const perfWarmups = boundedIntegerOption(process.env.JOOPARK_PERF_WARMUPS, 2, 0);

function loadRuntime(relPath) {
  const sandbox = { console };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(readFileSync(join(root, relPath), "utf8"), sandbox, { filename: relPath });
  return sandbox;
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function raw(value) {
  return { __raw: true, value: value == null ? "" : String(value) };
}

function html(strings, ...values) {
  let out = "";
  for (let index = 0; index < strings.length; index += 1) {
    out += strings[index];
    if (index >= values.length) continue;
    const value = values[index];
    if (value === null || value === undefined || value === false) continue;
    if (value && value.__raw) out += value.value;
    else if (Array.isArray(value)) out += value.map((item) => item && item.__raw ? item.value : escapeHtml(item)).join("");
    else out += escapeHtml(value);
  }
  return out;
}

function measure(label, fn) {
  let value;
  // Warmups prime the JIT and caches; their timings are discarded.
  for (let i = 0; i < perfWarmups; i += 1) value = fn();
  let best = Infinity;
  const samples = [];
  for (let i = 0; i < perfSamples; i += 1) {
    const started = performance.now();
    value = fn();
    const ms = performance.now() - started;
    samples.push(Number(ms.toFixed(2)));
    if (ms < best) best = ms;
  }
  const sorted = [...samples].sort((a, b) => a - b);
  const median = sorted[Math.floor((sorted.length - 1) / 2)];
  return {
    label,
    // `ms` is the best-of-N (minimum) — the stable estimator the thresholds gate on.
    ms: Number(best.toFixed(2)),
    medianMs: Number(median.toFixed(2)),
    samples,
    value,
  };
}

function createIssues(count) {
  const statuses = ["todo", "in-progress", "review", "done"];
  const priorities = ["crit", "high", "med", "low"];
  return Array.from({ length: count }, (_, index) => ({
    id: `ISS-${String(index + 1).padStart(5, "0")}`,
    project: "perf-project",
    title: `Synthetic issue ${index + 1}`,
    status: statuses[index % statuses.length],
    priority: priorities[index % priorities.length],
    assignee: `m${index % 12}`,
    labels: [`batch-${index % 20}`, { name: `lane-${index % 4}` }],
    due: "2026-06-30",
    order: (Math.floor(index / statuses.length) + 1) * 1000,
  }));
}

function createStoragePayload(count) {
  const rows = Array.from({ length: count }, (_, index) => ({
    id: `row-${index}`,
    title: `Large payload item ${index}`,
    memo: "x".repeat(80),
    createdAt: "2026-06-09T00:00:00.000Z",
  }));
  return {
    v: 3,
    events: rows.slice(0, count / 5),
    todos: rows.slice(0, count / 5),
    notes: rows.slice(0, count / 5),
    projects: rows.slice(0, count / 10),
    issues: createIssues(count),
    savedAt: "2026-06-09T00:00:00.000Z",
  };
}

const kanbanRuntime = loadRuntime("kanban-view.js");
const kanban = kanbanRuntime.JooParkKanbanView.create({
  html,
  raw,
  matches: (value, query) => String(value).toLowerCase().includes(String(query).toLowerCase()),
  kpiCard: (item) => html`<article>${item.title}:${item.value}</article>`,
  panelHead: (title, _link, controls) => html`<header><h2>${title}</h2>${raw(controls || "")}</header>`,
  searchEmptyState: (kind, title) => html`<p data-empty="${kind}">${title}</p>`,
  memberName: (id) => id || "미지정",
  projectName: (id) => id || "프로젝트",
  formatMonthDay: (value) => value || "",
  issueExecutionChecklistItems: () => [],
  issueExecutionChecklistProgress: () => ({ done: 0, total: 0, percent: 0 }),
});

const issues = createIssues(issueCount);
const modelMeasure = measure("kanbanViewModel", () => kanban.kanbanViewModel({ issues, currentProjectId: "perf-project", sourceFilter: "all", density: "compact" }));
const renderMeasure = measure("renderKanbanHTML", () => kanban.renderKanbanHTML({ issues, currentProjectId: "perf-project", sourceFilter: "all", density: "compact" }));
const storageMeasure = measure("storage JSON stringify", () => JSON.stringify(createStoragePayload(storageItems)));
const kanbanRenderedCards = (renderMeasure.value.match(/class="kanban-card-wrap"/g) || []).length;
const kanbanVirtualNotes = (renderMeasure.value.match(/data-kanban-virtualized="true"/g) || []).length;

const summary = {
  status: "pass",
  issueCount,
  storageItems,
  thresholds: {
    maxKanbanModelMs,
    maxKanbanRenderMs,
    maxKanbanRenderedCards,
    maxStorageSerializeMs,
  },
  sampling: {
    samples: perfSamples,
    warmups: perfWarmups,
    estimator: "best-of-N (min)",
  },
  measurements: {
    kanbanModelMs: modelMeasure.ms,
    kanbanModelMedianMs: modelMeasure.medianMs,
    kanbanRenderMs: renderMeasure.ms,
    kanbanRenderMedianMs: renderMeasure.medianMs,
    kanbanRenderSamplesMs: renderMeasure.samples,
    kanbanRenderedBytes: renderMeasure.value.length,
    kanbanRenderedCards,
    kanbanVirtualNotes,
    storageSerializeMs: storageMeasure.ms,
    storageBytes: storageMeasure.value.length,
  },
};

const failures = [];
if (modelMeasure.ms > maxKanbanModelMs) failures.push(`kanban model ${modelMeasure.ms}ms > ${maxKanbanModelMs}ms`);
if (renderMeasure.ms > maxKanbanRenderMs) failures.push(`kanban render ${renderMeasure.ms}ms > ${maxKanbanRenderMs}ms`);
if (kanbanRenderedCards > maxKanbanRenderedCards) failures.push(`kanban rendered cards ${kanbanRenderedCards} > ${maxKanbanRenderedCards}`);
if (issueCount > maxKanbanRenderedCards && kanbanVirtualNotes === 0) failures.push("kanban virtualization note missing for large issue count");
if (storageMeasure.ms > maxStorageSerializeMs) failures.push(`storage serialize ${storageMeasure.ms}ms > ${maxStorageSerializeMs}ms`);

if (failures.length) {
  summary.status = "fail";
  summary.failures = failures;
  console.error(JSON.stringify(summary, null, 2));
  process.exit(1);
}

console.log(JSON.stringify(summary, null, 2));
