#!/usr/bin/env node

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dashboardFiles = [
  "dashboard-storage.js",
  "dashboard-prioritization.js",
  "dashboard-evidence-receipts.js",
  "dashboard-insights-engine.js",
  "dashboard-autoresearch-loop.js",
  "dashboard-view.js",
];
const storageKeys = [
  "dashboardInsights",
  "dashboardResearchLoops",
  "dashboardImprovementCandidates",
  "dashboardDecisionReceipts",
  "dashboardEvidenceSnapshots",
  "dashboardHealthChecks",
];
const scoreKeys = [
  "userValue",
  "urgency",
  "difficulty",
  "regressionRisk",
  "performance",
  "accessibility",
  "security",
  "maintainability",
  "releaseReadiness",
  "localStorageStability",
  "mobileUX",
  "evidenceTraceability",
];

function read(path) {
  return readFileSync(join(root, path), "utf-8");
}

function loadRuntime(files) {
  const sandbox = { console };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const file of files) {
    vm.runInContext(read(file), sandbox, { filename: file });
  }
  return sandbox;
}

function assertIncludes(path, term) {
  assert.ok(read(path).includes(term), `${path} missing ${term}`);
}

for (const file of dashboardFiles) {
  assert.ok(read(file).includes("JooPark"), `${file} should expose a JooPark global`);
  assertIncludes("index.html", `./${file}`);
  assertIncludes("package.json", `"${file}"`);
  assertIncludes("scripts/package-release.mjs", `"${file}"`);
  assertIncludes("sw.js", `./${file}`);
  assertIncludes("docs/app-architecture.md", file);
}

for (const key of storageKeys) {
  assertIncludes("workspace-storage.js", key);
  assertIncludes("backup-import-guards.js", key);
  assertIncludes("backup-import-ui.js", key);
  assertIncludes("app.js", key);
}

assertIncludes("dashboard-view.js", "data-dashboard-intelligence");
assertIncludes("home-view.js", "dashboardIntelligenceHTML");
assertIncludes("app.js", "dashboardIntelligenceHTML");
assertIncludes("dashboard-view.js", "data-system-dashboard-receipts");
assertIncludes("system-status-view.js", "systemDashboardReceiptHTML");
assertIncludes("scripts/audit-raw-xss.mjs", "dashboard-view.js");

const sandbox = loadRuntime([
  "dashboard-storage.js",
  "dashboard-prioritization.js",
  "dashboard-evidence-receipts.js",
  "dashboard-insights-engine.js",
  "dashboard-autoresearch-loop.js",
]);
const storage = sandbox.JooParkDashboardStorage.create();
const prioritization = sandbox.JooParkDashboardPrioritization.create();
const receipts = sandbox.JooParkDashboardEvidenceReceipts.create({ storage });
const insightsEngine = sandbox.JooParkDashboardInsightsEngine.create();
const loop = sandbox.JooParkDashboardAutoresearchLoop.create();
const dashboard = {
  events: [{ id: "ev1", title: "Today", date: "2026-06-09" }],
  todos: [{ id: "td1", title: "Late", due: "2026-06-08", done: false }],
  notes: [{ id: "n1", title: "Note" }],
  habits: [{ id: "h1", name: "Run", log: { "2026-06-09": true } }],
  projects: [{ id: "p1", name: "Project", progress: 40, status: "delayed", health: "red" }],
  issues: [{ id: "I1", title: "Blocker", project: "p1", status: "todo", priority: "crit", due: "2026-06-08" }],
  gantt: { tasks: [{ id: "t1", name: "Task", end: "2026-06-08", milestone: false }] },
};
const model = insightsEngine.dashboardInsightsModel({
  dashboard,
  state: { storageHealth: { localBytes: 1000, checkedAt: "2026-06-09T00:00:00.000Z" } },
  today: "2026-06-09",
  publishItems: [{ key: "release-gates", state: "blocked" }],
  productLoop: { status: "ready-for-external-claim", latestExperiment: "demo", generatedAt: "2026-06-09T00:00:00.000Z" },
  createdAt: "2026-06-09T00:00:00.000Z",
});
assert.equal(model.cards.length, 9);
assert.ok(model.cards.every((card) => card.status && card.evidence && card.lastUpdated && card.riskLabel && card.nextAction));
assert.equal(model.sourceSummary.needs_external_validation, false);
assert.ok(model.externalResearchSources.length >= 4);

const result = loop.runLoop({
  dashboard,
  state: { storageHealth: { localBytes: 1000 } },
  today: "2026-06-09",
  createdAt: "2026-06-09T00:00:00.000Z",
  publishItems: [{ key: "release-gates", state: "blocked" }],
  productLoop: { status: "ready-for-external-claim", latestExperiment: "demo" },
  storage,
  prioritization,
  receipts,
  insightsEngine,
  active: true,
});
assert.equal(result.loopRecord.loopSteps.length, 12);
for (const key of storageKeys) {
  assert.ok(Array.isArray(dashboard[key]), `${key} should be an array`);
  assert.ok(dashboard[key].length >= 1, `${key} should receive loop data`);
  const record = dashboard[key][0];
  for (const field of ["id", "createdAt", "sourceRefs", "summary", "scoreBreakdown", "confidence", "verificationStatus", "riskFlags", "nextAction", "receiptHash"]) {
    assert.ok(record[field] !== undefined, `${key}[0] missing ${field}`);
  }
}
for (const key of scoreKeys) {
  assert.ok(result.decisionReceipt.scoreBreakdown[key] >= 1 && result.decisionReceipt.scoreBreakdown[key] <= 5, `score ${key} out of range`);
}

console.log("[verify-dashboard-intelligence] PASS", {
  files: dashboardFiles.length,
  cards: model.cards.length,
  sources: model.externalResearchSources.length,
  loopSteps: result.loopRecord.loopSteps.length,
});
