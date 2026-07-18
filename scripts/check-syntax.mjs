#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const runtimeSyntaxFiles = Object.freeze([
  "search-empty-state.js",
  "calendar-view.js",
  "todo-view.js",
  "notes-view.js",
  "habits-view.js",
  "stats-view.js",
  "llm-wiki-view.js",
  "portfolio-view.js",
  "kanban-view.js",
  "gantt-view.js",
  "team-view.js",
  "pipeline-view.js",
  "workspace-storage.js",
  "dashboard-storage.js",
  "dashboard-prioritization.js",
  "dashboard-evidence-receipts.js",
  "dashboard-insights-engine.js",
  "dashboard-autoresearch-loop.js",
  "dashboard-view.js",
  "storage-status-view.js",
  "settings-view.js",
  "system-status-view.js",
  "backup-import-guards.js",
  "backup-import-ui.js",
  "release-status.js",
  "operations-copy-actions.js",
  "dialog-shell.js",
  "project-picker.js",
  "global-search.js",
  "command-palette.js",
  "db-catalog.js",
  "review-handoff.js",
  "review-result-view.js",
  "review-package-view.js",
  "review-artifact-view.js",
  "review-copy-actions.js",
  "review-submission-copy.js",
  "review-recommendation-export.js",
  "pwa-runtime.js",
  "workspace-seed-data.js",
  "home-view.js",
  "ops-runtime-loader.js",
  "app.js",
]);

const scriptSyntaxFiles = Object.freeze([
  "scripts/audit-raw-xss.mjs",
  "scripts/capture-preview.mjs",
  "scripts/check-app-structure.mjs",
  "scripts/check-doc-architecture.mjs",
  "scripts/check-llm-wiki-docs.mjs",
  "scripts/check-syntax.mjs",
  "scripts/check-vendor-honesty.mjs",
  "scripts/package-release.mjs",
  "scripts/prepare-github-pages-workflow.mjs",
  "scripts/product-smoke-lock.mjs",
  "scripts/run-local-smoke.mjs",
  "scripts/smoke-cockpit.mjs",
  "scripts/measure-large-data-performance.mjs",
  "scripts/verify-dashboard-intelligence.mjs",
  "scripts/smoke-a11y.mjs",
  "scripts/smoke-chrome.mjs",
  "scripts/smoke-delete-undo.mjs",
  "scripts/smoke-interactions.mjs",
  "scripts/smoke-mobile.mjs",
  "scripts/smoke-release.mjs",
  "scripts/test-pure-helpers.mjs",
  "scripts/verify-product-smoke.mjs",
  "scripts/verify-release.mjs",
]);

const syntaxCheckFiles = Object.freeze([
  ...runtimeSyntaxFiles,
  ...scriptSyntaxFiles,
]);

function runSyntaxCheck(file) {
  const result = spawnSync(process.execPath, ["--check", file], {
    cwd: root,
    stdio: "inherit",
  });

  return {
    failed: result.status !== 0 || !!result.error || !!result.signal,
    code: result.status || 1,
    error: result.error,
  };
}

function reportSyntaxFailure(file, result) {
  if (result.error) console.error(`[check-syntax] ${file}: ${result.error.message}`);
  process.exitCode = result.code;
}

for (const file of syntaxCheckFiles) {
  const result = runSyntaxCheck(file);
  if (result.failed) {
    reportSyntaxFailure(file, result);
    break;
  }
}
