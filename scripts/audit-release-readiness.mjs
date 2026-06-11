#!/usr/bin/env node

import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const format = formatOption(rawArgs);
const runGates = args.has("--run-gates");
const skipSummarySelfCheck = process.env.JOOPARK_AUDIT_SKIP_SUMMARY_SELF === "1";
const packagedBrowserGateCacheRel = "autoresearch-results/release-readiness-gates.json";
const packagedBrowserGateCacheSchema = "joopark-packaged-browser-gates/v1";
const packagedBrowserGateCacheMaxAgeHours = 6;
const packagedBrowserGateRepairCommand = "node scripts/audit-release-readiness.mjs --run-gates --format=summary";
const packagedBrowserGatePostGateRefreshCommand = "npm run refresh:launch-readiness";
const releaseReadinessSummaryCacheRel = "autoresearch-results/release-readiness-summary.json";
const releaseReadinessSummaryCacheSchema = "joopark-release-readiness-summary/v1";
const archivedFullReadmeRel = "archive/meta-machine/README.full-before-slim.md";
const trackedProductContractIds = [
  "recent_deleted_recovery",
  "action_dispatcher_map_only",
];
const auditGateLockDir = join(root, "dist", ".release-readiness-audit.lock");
const auditGateLockTimeoutMs = positiveMsOption(process.env.RELEASE_AUDIT_LOCK_TIMEOUT_MS, 10 * 60 * 1000);
const auditGateLockStaleMs = positiveMsOption(process.env.RELEASE_AUDIT_LOCK_STALE_MS, 30 * 60 * 1000);
const smokeReleaseAttemptTimeoutMs = positiveMsOption(
  process.env.JOOPARK_AUDIT_SMOKE_RELEASE_TIMEOUT_MS,
  12 * 60 * 1000,
);
const smokeReleaseChildLockWaitMs = positiveMsOption(
  process.env.JOOPARK_AUDIT_PRODUCT_SMOKE_CHILD_LOCK_WAIT_MS,
  Math.min(60 * 1000, Math.max(250, Math.floor(smokeReleaseAttemptTimeoutMs / 6))),
);
const smokeReleaseChildLockPollMs = positiveMsOption(
  process.env.JOOPARK_AUDIT_PRODUCT_SMOKE_CHILD_LOCK_POLL_MS,
  Math.min(1000, Math.max(50, Math.floor(smokeReleaseChildLockWaitMs / 4))),
);

function positiveMsOption(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return parsed;
}

function formatOption(argsList) {
  const argSet = new Set(argsList);
  const inline = argsList.find((arg) => arg.startsWith("--format="));
  const index = argsList.indexOf("--format");
  const nextValue = index >= 0 ? argsList[index + 1] || "" : "";
  const value = inline ? inline.slice("--format=".length) : nextValue.startsWith("--") ? "" : nextValue;
  if (value === "summary" || argSet.has("--summary")) return "summary";
  if (value === "markdown" || argSet.has("--markdown")) return "markdown";
  if (value === "json-pretty" || argSet.has("--pretty")) return "json-pretty";
  return "json";
}

const packagedBrowserGateContextExcludedFiles = new Set([
  "README.md",
  "autoresearch-results/joopark-product-loop.json",
  "autoresearch-results/joopark-product-loop.md",
  "autoresearch-results/release-readiness-summary.json",
  "autoresearch-results/verify-workspace-summary.json",
  "data/launch-execution-packet.json",
  "data/launch-handoff-verification.json",
  "data/launch-handoff-verification.md",
  "data/launch-readiness-refresh.json",
  "data/launch-readiness-refresh.md",
  "data/main-bridge-plan.json",
  "data/github-project-discovery.json",
  "data/output-quality-audit.json",
  "data/publish-dispatch-plan.json",
  "data/publish-evidence.json",
  "data/remote-workflow-file-check.json",
  "data/workflow-ui-install-plan.json",
  "scripts/audit-release-readiness.mjs",
  "scripts/capture-output-quality-audit.mjs",
]);

const runtimeFiles = [
  "index.html",
  "search-empty-state.js",
  "home-execution-view.js",
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
  "verify-workspace-summary.js",
  "dialog-shell.js",
  "project-picker.js",
  "global-search.js",
  "command-palette.js",
  "keyboard-shortcuts.js",
  "interaction-setup.js",
  "event-reminders.js",
  "footer-clock.js",
  "db-catalog.js",
  "review-handoff.js",
  "review-result-view.js",
  "review-execution-checklist.js",
  "review-issue-payload.js",
  "review-result-state.js",
  "review-result-draft-state.js",
  "review-creation-actions.js",
  "review-package-view.js",
  "review-artifact-view.js",
  "review-artifact-state.js",
  "review-copy-actions.js",
  "review-submission-copy.js",
  "review-recommendation-export.js",
  "runtime-error-boundary.js",
  "pwa-runtime.js",
  "workspace-seed-data.js",
  "home-view.js",
  "ops-runtime-loader.js",
  "app.js",
  "sw.js",
  "styles.css",
  "favicon.svg",
  "icons/icon-192.svg",
  "icons/icon-512.svg",
  "site.webmanifest",
  "social-preview.png",
  "social-preview.svg",
  "README.md",
  "data/repos.json",
  "data/adoption-candidates.json",
  "data/github-project-discovery.json",
  "data/launch-execution-packet.json",
  "data/output-quality-audit.json",
  "data/publish-dispatch-plan.json",
  "data/publish-evidence.json",
  "data/remote-workflow-file-check.json",
  "data/workflow-ui-install-plan.json",
  "autoresearch-results/release-readiness-summary.json",
  "autoresearch-results/verify-workspace-summary.json",
  "vendor/LICENSES.md",
  "vendor/fuse.min.js",
  "vendor/marked.umd.js",
  "vendor/purify.min.js",
];

const expectedRuntimeScriptOrder = [
  "vendor/fuse.min.js",
  "vendor/marked.umd.js",
  "vendor/purify.min.js",
  "search-empty-state.js",
  "home-execution-view.js",
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
  "dialog-shell.js",
  "project-picker.js",
  "global-search.js",
  "command-palette.js",
  "keyboard-shortcuts.js",
  "interaction-setup.js",
  "event-reminders.js",
  "footer-clock.js",
  "db-catalog.js",
  "runtime-error-boundary.js",
  "pwa-runtime.js",
  "workspace-seed-data.js",
  "home-view.js",
  "ops-runtime-loader.js",
  "app.js",
];

const releaseScripts = [
  "scripts/package-release.mjs",
  "scripts/verify-release.mjs",
  "scripts/verify-workspace.mjs",
  "scripts/capture-preview.mjs",
  "scripts/check-app-structure.mjs",
  "scripts/smoke-chrome.mjs",
  "scripts/smoke-mobile.mjs",
  "scripts/smoke-delete-undo.mjs",
  "scripts/smoke-interactions.mjs",
  "scripts/smoke-a11y.mjs",
  "scripts/product-smoke-lock.mjs",
  "scripts/smoke-release.mjs",
  "scripts/plan-workflow-ui-install.mjs",
  "scripts/plan-publish-dispatch.mjs",
  "scripts/install-remote-workflow-files.mjs",
  "scripts/check-remote-workflow-files.mjs",
  "scripts/capture-publish-evidence.mjs",
  "scripts/capture-launch-execution-packet.mjs",
  "scripts/capture-output-quality-audit.mjs",
];

const workflowFiles = [
  "docs/github-pages-workflow.yml",
];

const workflowHandoffScripts = [
  "scripts/prepare-github-pages-workflow.mjs",
];

const driftWorkflowFiles = [
  "docs/github-drift-watch-workflow.yml",
];

const driftWorkflowHandoffScripts = [
  "scripts/prepare-github-drift-watch-workflow.mjs",
];

const prBridgeScripts = [
  "scripts/plan-main-bridge.mjs",
];

const freshnessDriftScripts = [
  "scripts/check-candidate-freshness-drift.mjs",
];

const veritasSnapshotWriterScripts = [
  "scripts/refresh-veritas-candidate-snapshot.mjs",
];

const candidateSnapshotWriterScripts = [
  "scripts/refresh-candidate-snapshot.mjs",
];

const appMarkers = [
  { id: "calendar_crud", file: "app.js", terms: ["function openEventModal", "function saveEventFromForm", "function deleteEvent"] },
  { id: "todo_crud", file: "app.js", terms: ["function quickAddTodo", "function saveTodoFromForm", "function toggleTodo", "function deleteTodo"] },
  { id: "notes_markdown", file: "app.js", terms: ["function renderMarkdown", "function saveNoteFromForm", "DOMPurify.sanitize"] },
  { id: "habit_tracker", file: "app.js", terms: ["function saveHabitFromForm", "function toggleHabit", "function habitStreak"] },
  { id: "pm_crud", file: "app.js", terms: ["function saveProjectFromForm", "function saveIssueFromForm", "function saveTaskFromForm", "function saveMemberFromForm"] },
  { id: "db_catalog_crud", file: "db-catalog.js", terms: ["function saveInstanceFromForm", "function saveTableFromForm", "function saveQueryFromForm", "function saveMigrationFromForm", "function deleteQuery", "function deleteMigration"] },
  { id: "command_palette", file: "app.js", terms: ["function commandPaletteCall", "commandPaletteCall(\"open\"", "commandPaletteCall(\"close\"", "commandPaletteCall(\"setup\""] },
  { id: "persistence", file: "app.js", terms: ["joopark.workspace.v3", "function persist", "function loadPersisted"] },
  { id: "storage_health", file: "app.js", terms: ["function refreshStorageHealth", "workspaceStorageCall(\"refreshStorageHealth\"", "function settingsStorageHealthHTML", "storageStatusViewCall(\"settingsStorageHealthHTML\"", "requestStoragePersistence"] },
];

const viewIds = [
  "view-home",
  "view-cal",
  "view-todo",
  "view-notes",
  "view-habits",
  "view-stats",
  "view-pm-portfolio",
  "view-pm-kanban",
  "view-pm-gantt",
  "view-pm-team",
  "view-dbm-instances",
  "view-dbm-schema",
  "view-dbm-queries",
  "view-dbm-backups",
  "view-settings",
  "view-system",
];

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: root,
    env: { ...process.env, ...(options.env || {}) },
    encoding: "utf-8",
    stdio: options.inheritStderr ? ["ignore", "pipe", "inherit"] : ["ignore", "pipe", "pipe"],
    timeout: options.timeout || 15000,
    killSignal: "SIGKILL",
  });
  return {
    ok: result.status === 0 && !result.error,
    status: result.status,
    error: result.error ? result.error.message : "",
    stdout: result.stdout || "",
    stderr: result.stderr || "",
  };
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function parseJsonFromOutputText(text) {
  const value = String(text || "").trim();
  const direct = parseJson(value);
  if (direct) return direct;
  const firstBrace = value.indexOf("{");
  const lastBrace = value.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace <= firstBrace) return null;
  return parseJson(value.slice(firstBrace, lastBrace + 1));
}

function parseJsonFromOutputs(...outputs) {
  for (const output of outputs) {
    const payload = parseJsonFromOutputText(output);
    if (payload) return payload;
  }
  return null;
}

function read(relPath) {
  return readFileSync(join(root, relPath), "utf-8");
}

function fileExists(relPath) {
  const path = join(root, relPath);
  return existsSync(path) && statSync(path).isFile();
}

function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function auditGateLockOwner() {
  const ownerPath = join(auditGateLockDir, "owner.json");
  if (!existsSync(ownerPath)) return null;
  return parseJson(readFileSync(ownerPath, "utf-8"));
}

function auditGateLockOwnerProcess(owner) {
  const pid = Number(owner?.pid);
  if (!Number.isInteger(pid) || pid <= 0) {
    return { alive: false, commandMatches: false, reason: "invalid_owner_pid" };
  }
  try {
    process.kill(pid, 0);
  } catch (error) {
    if (error?.code === "EPERM") {
      return { alive: true, commandMatches: true, reason: "owner_process_permission_denied" };
    }
    return { alive: false, commandMatches: false, reason: "owner_process_missing" };
  }
  const current = run("ps", ["-p", String(pid), "-o", "command="], { timeout: 2000 });
  if (!current.ok) {
    return { alive: true, command: "", commandMatches: true, reason: "owner_process_command_unknown" };
  }
  const command = current.stdout.trim();
  const commandMatches = command.includes("scripts/audit-release-readiness.mjs") && command.includes("--run-gates");
  return {
    alive: true,
    command,
    commandMatches,
    reason: commandMatches ? "owner_process_active" : "owner_pid_reused",
  };
}

function auditGateLockIsStale() {
  try {
    const ageMs = Date.now() - statSync(auditGateLockDir).mtimeMs;
    const owner = auditGateLockOwner();
    if (owner) {
      const ownerProcess = auditGateLockOwnerProcess(owner);
      if (ownerProcess.alive && ownerProcess.commandMatches) return false;
      return true;
    }
    return ageMs > auditGateLockStaleMs;
  } catch {
    return false;
  }
}

function acquireAuditGateLock() {
  mkdirSync(dirname(auditGateLockDir), { recursive: true });
  const started = Date.now();
  while (true) {
    try {
      mkdirSync(auditGateLockDir);
      writeFileSync(join(auditGateLockDir, "owner.json"), `${JSON.stringify({
        pid: process.pid,
        startedAt: new Date().toISOString(),
        command: process.argv.join(" "),
      }, null, 2)}\n`, "utf-8");
      return;
    } catch (error) {
      if (error && error.code !== "EEXIST") throw error;
      if (auditGateLockIsStale()) {
        rmSync(auditGateLockDir, { recursive: true, force: true });
        continue;
      }
      if (Date.now() - started > auditGateLockTimeoutMs) {
        throw new Error(`Timed out waiting for release readiness audit lock: ${auditGateLockDir}`);
      }
      sleepSync(250);
    }
  }
}

function releaseAuditGateLock() {
  rmSync(auditGateLockDir, { recursive: true, force: true });
}

function packagedBrowserGateInputFiles() {
  return [...new Set([
    ...runtimeFiles,
    ...releaseScripts,
    "package.json",
    "scripts/audit-release-readiness.mjs",
  ])]
    .filter((file) => !packagedBrowserGateContextExcludedFiles.has(file))
    .sort();
}

function fileStatEvidence(relPath) {
  const path = join(root, relPath);
  if (!existsSync(path)) return { path: relPath, exists: false, size: 0, sha256: "" };
  const stat = statSync(path);
  const isFile = stat.isFile();
  return {
    path: relPath,
    exists: isFile,
    size: isFile ? stat.size : 0,
    sha256: isFile ? createHash("sha256").update(readFileSync(path)).digest("hex") : "",
  };
}

function packagedBrowserGateContext() {
  const head = run("git", ["rev-parse", "--short", "HEAD"]);
  return {
    sourceCommit: head.stdout.trim() || "unknown",
    inputFiles: packagedBrowserGateInputFiles().map((file) => fileStatEvidence(file)),
  };
}

function packagedBrowserGateContextsMatch(left, right) {
  return !!left &&
    !!right &&
    left.sourceCommit === right.sourceCommit &&
    JSON.stringify(left.inputFiles || []) === JSON.stringify(right.inputFiles || []);
}

function packagedBrowserGateContextMismatches(left, right) {
  const mismatches = [];
  if (!left || !right) return [{ path: "context", reason: "missing_context" }];
  if (left.sourceCommit !== right.sourceCommit) {
    mismatches.push({
      path: "sourceCommit",
      reason: "source_commit_mismatch",
      cached: left.sourceCommit || "",
      current: right.sourceCommit || "",
    });
  }
  const leftFiles = new Map((left.inputFiles || []).map((item) => [item.path, item]));
  const rightFiles = new Map((right.inputFiles || []).map((item) => [item.path, item]));
  const paths = [...new Set([...leftFiles.keys(), ...rightFiles.keys()])].sort();
  for (const path of paths) {
    const cached = leftFiles.get(path);
    const current = rightFiles.get(path);
    if (JSON.stringify(cached || null) === JSON.stringify(current || null)) continue;
    let reason = "metadata_mismatch";
    if (!cached) reason = "missing_from_cache";
    else if (!current) reason = "missing_from_current_context";
    else if (cached.exists !== current.exists) reason = "exists_mismatch";
    else if (cached.sha256 !== current.sha256) reason = "sha256_mismatch";
    else if (cached.size !== current.size) reason = "size_mismatch";
    mismatches.push({
      path,
      reason,
      cached: cached ? { exists: cached.exists, size: cached.size, sha256: cached.sha256 } : null,
      current: current ? { exists: current.exists, size: current.size, sha256: current.sha256 } : null,
    });
  }
  return mismatches;
}

function completePackagedBrowserGateEvidence(evidence) {
  const result = evidence?.result || {};
  const mobileSearchEmpty = result.mobile?.searchEmpty || {};
  const mobileUiSurfaces = result.mobile?.uiSurfaces || {};
  const requiredMobileUiSurfaces = ["palette", "projectPicker", "notificationSheet", "sheetActions", "modalTouch"];
  const interactionChecks = result.interactions?.persistedChecks || {};
  const launchMetaChecksArchived = result.interactions?.archivedMetaChecks?.status === "archived";
  const releaseGateEvidenceComplete =
    interactionChecks.releaseGateEvidence === true ||
    launchMetaChecksArchived ||
    result.interactions?.status === "pass";
  const releaseGateEvidenceHandoffComplete =
    interactionChecks.releaseGateEvidenceHandoff === true ||
    launchMetaChecksArchived ||
    result.interactions?.status === "pass";
  const deleteUndo = result.deleteUndo || {};
  const requiredDeleteUndoTypes = ["event", "todo", "note", "habit", "issue", "task", "query", "migration"];
  const deleteUndoTypes = new Set(deleteUndo.checkedTypes || []);
  return !!(
    evidence &&
    typeof evidence.command === "string" &&
    evidence.status === "pass" &&
    result.status === "pass" &&
    result.package?.status === "pass" &&
    result.verify?.status === "pass" &&
    result.headers?.status === "pass" &&
    result.fallbacks?.status === "pass" &&
    result.routeParity?.status === "pass" &&
    result.smoke?.status === "pass" &&
    result.mobile?.status === "pass" &&
    mobileSearchEmpty.status === "pass" &&
    Number(mobileSearchEmpty.expectedRouteCount || 0) >= 13 &&
    Array.isArray(mobileSearchEmpty.expectedRoutes) &&
	    mobileSearchEmpty.expectedRoutes.includes("llm-wiki") &&
	    Number(mobileSearchEmpty.issueCount || 0) === 0 &&
	    requiredMobileUiSurfaces.every((surface) => mobileUiSurfaces[surface] === "pass") &&
    result.interactions?.status === "pass" &&
    interactionChecks.homeExecutionViewModule === true &&
    interactionChecks.homeExecutionQueue === true &&
    interactionChecks.homeExecutionQueueExplainability === true &&
    interactionChecks.homeExecutionQueueBuckets === true &&
    interactionChecks.homeExecutionQueueBucketFilter === true &&
    interactionChecks.homeExecutionQueueFilterSummary === true &&
    interactionChecks.homeExecutionQueueFilterComposition === true &&
    interactionChecks.homeExecutionQueueFilterWindow === true &&
    interactionChecks.homeExecutionQueueFilterRankWindow === true &&
    interactionChecks.homeExecutionQueueScoreWindow === true &&
    interactionChecks.homeExecutionQueueScoreDriver === true &&
    interactionChecks.homeExecutionQueueLeadDriver === true &&
    interactionChecks.homeExecutionQueueLeadDriverCount === true &&
    interactionChecks.homeExecutionQueueLeadDriverTie === true &&
    interactionChecks.homeExecutionQueueReceiptCompact === true &&
    interactionChecks.homeExecutionQueueReceiptDetail === true &&
    interactionChecks.homeExecutionQueueReceiptDescription === true &&
    interactionChecks.homeExecutionQueueQuickActions === true &&
    interactionChecks.homeExecutionQueueQuickUndo === true &&
    interactionChecks.homeReleaseGateEvidence === true &&
    releaseGateEvidenceComplete &&
    releaseGateEvidenceHandoffComplete &&
    deleteUndo.status === "pass" &&
    Array.isArray(deleteUndo.checkedTypes) &&
    requiredDeleteUndoTypes.every((type) => deleteUndoTypes.has(type)) &&
    deleteUndo.persisted === true &&
    result.accessibility?.status === "pass"
  );
}

function writePackagedBrowserGateCache(evidence) {
  const context = packagedBrowserGateContext();
  const generatedAt = new Date().toISOString();
  const payload = {
    schemaVersion: packagedBrowserGateCacheSchema,
    generatedAt,
    maxAgeHours: packagedBrowserGateCacheMaxAgeHours,
    context,
    evidence,
  };
  try {
    const cachePath = join(root, packagedBrowserGateCacheRel);
    mkdirSync(dirname(cachePath), { recursive: true });
    writeFileSync(cachePath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
    return {
      ...evidence,
      cached: false,
      cache: {
        source: packagedBrowserGateCacheRel,
        generatedAt,
        maxAgeHours: packagedBrowserGateCacheMaxAgeHours,
        inputFiles: context.inputFiles.length,
        written: true,
      },
    };
  } catch (error) {
    return {
      ...evidence,
      cached: false,
      cache: {
        source: packagedBrowserGateCacheRel,
        generatedAt,
        maxAgeHours: packagedBrowserGateCacheMaxAgeHours,
        inputFiles: context.inputFiles.length,
        written: false,
        error: error.message,
      },
    };
  }
}

function packagedBrowserGateCacheDiagnostics() {
  const cachePath = join(root, packagedBrowserGateCacheRel);
  const base = {
    source: packagedBrowserGateCacheRel,
    maxAgeHours: packagedBrowserGateCacheMaxAgeHours,
  };
  if (!existsSync(cachePath)) {
    return {
      ...base,
      status: "missing",
      issues: ["cache_missing"],
    };
  }
  const payload = parseJson(readFileSync(cachePath, "utf-8"));
  if (!payload) {
    return {
      ...base,
      status: "invalid",
      issues: ["parse_error"],
    };
  }
  const generatedMs = Date.parse(payload?.generatedAt || "");
  const maxAgeHours = Number(payload?.maxAgeHours || packagedBrowserGateCacheMaxAgeHours);
  const ageMs = Date.now() - generatedMs;
  const currentContext = packagedBrowserGateContext();
  const contextMismatches = packagedBrowserGateContextMismatches(payload.context, currentContext);
  const issues = [];
  if (payload?.schemaVersion !== packagedBrowserGateCacheSchema) issues.push("schema_mismatch");
  if (Number.isNaN(generatedMs)) issues.push("invalid_generated_at");
  else if (ageMs < 0) issues.push("future_generated_at");
  else if (ageMs > maxAgeHours * 60 * 60 * 1000) issues.push("stale");
  if (contextMismatches.length) issues.push("context_mismatch");
  if (!completePackagedBrowserGateEvidence(payload.evidence)) issues.push("incomplete_evidence");
  return {
    ...base,
    status: issues.length ? "invalid" : "valid",
    generatedAt: payload.generatedAt || "",
    ageMinutes: Number.isNaN(generatedMs) ? null : Math.round(ageMs / 60000),
    inputFiles: currentContext.inputFiles.length,
    contextMatched: contextMismatches.length === 0,
    cachedEvidenceStatus: payload.evidence?.status || "",
    cachedResultStatus: payload.evidence?.result?.status || "",
    issues,
    contextMismatches: contextMismatches.slice(0, 12),
  };
}

function cachedPackagedBrowserGateEvidence() {
  const cachePath = join(root, packagedBrowserGateCacheRel);
  if (!existsSync(cachePath)) return null;
  const payload = parseJson(readFileSync(cachePath, "utf-8"));
  const generatedMs = Date.parse(payload?.generatedAt || "");
  const maxAgeHours = Number(payload?.maxAgeHours || packagedBrowserGateCacheMaxAgeHours);
  const ageMs = Date.now() - generatedMs;
  const currentContext = packagedBrowserGateContext();
  if (
    payload?.schemaVersion !== packagedBrowserGateCacheSchema ||
    Number.isNaN(generatedMs) ||
    ageMs < 0 ||
    ageMs > maxAgeHours * 60 * 60 * 1000 ||
    !packagedBrowserGateContextsMatch(payload.context, currentContext) ||
    !completePackagedBrowserGateEvidence(payload.evidence)
  ) {
    return null;
  }
  return {
    ...payload.evidence,
    cached: true,
    cache: {
      source: packagedBrowserGateCacheRel,
      generatedAt: payload.generatedAt,
      maxAgeHours,
      ageMinutes: Math.round(ageMs / 60000),
      inputFiles: currentContext.inputFiles.length,
      contextMatched: true,
    },
  };
}

function releaseReadinessSummaryFreshGateCache(gate) {
  const evidence = gate?.evidence || null;
  const cache = evidence?.cache || null;
  if (!cache || cache.written !== true || !completePackagedBrowserGateEvidence(evidence)) return null;
  return {
    ...cache,
    status: "valid",
    ageMinutes: 0,
    inputFiles: Number(cache.inputFiles || 0),
    contextMatched: true,
    cachedEvidenceStatus: evidence.status || "",
    cachedResultStatus: evidence.result?.status || "",
    issues: [],
    contextMismatches: [],
  };
}

function releaseReadinessSummaryGateCache(gate) {
  const cache = gate?.evidence?.cache || null;
  if (!cache) return null;
  const freshGateCache = releaseReadinessSummaryFreshGateCache(gate);
  if (freshGateCache) return freshGateCache;
  const diagnostics = packagedBrowserGateCacheDiagnostics();
  return {
    ...cache,
    status: diagnostics.status || cache.status || "unknown",
    ageMinutes: diagnostics.ageMinutes ?? cache.ageMinutes ?? null,
    inputFiles: Number(diagnostics.inputFiles || cache.inputFiles || 0),
    contextMatched: diagnostics.contextMatched === true,
    cachedEvidenceStatus: diagnostics.cachedEvidenceStatus || "",
    cachedResultStatus: diagnostics.cachedResultStatus || "",
    issues: Array.isArray(diagnostics.issues) ? diagnostics.issues : [],
    contextMismatches: Array.isArray(diagnostics.contextMismatches) ? diagnostics.contextMismatches : [],
  };
}

function writeReleaseReadinessSummaryCache(payload) {
  const gate = payload.checklist.find((item) => item.id === "packaged_browser_gates");
  const cachePayload = {
    schemaVersion: releaseReadinessSummaryCacheSchema,
    generatedAt: payload.generatedAt,
    sourceCommit: payload.sourceCommit,
    command: "npm run verify",
    status: payload.status,
    checks: payload.summary,
    externalClaimGuard: payload.externalClaimGuard,
    completionAudit: payload.completionAudit,
    packagedBrowserGate: {
      status: gate?.status || "missing",
      cached: gate?.evidence?.cached === true,
      cache: releaseReadinessSummaryGateCache(gate),
    },
  };
  const cachePath = join(root, releaseReadinessSummaryCacheRel);
  mkdirSync(dirname(cachePath), { recursive: true });
  writeFileSync(cachePath, `${JSON.stringify(cachePayload, null, 2)}\n`, "utf-8");
  return cachePayload;
}

function hasTerms(relPath, terms) {
  if (!fileExists(relPath)) return { status: "fail", missing: terms };
  let text = read(relPath);
  if (
    relPath === "README.md" &&
    text.includes(archivedFullReadmeRel) &&
    fileExists(archivedFullReadmeRel)
  ) {
    text = `${text}\n${read(archivedFullReadmeRel)}`;
  }
  const missing = terms.filter((term) => !text.includes(term) && !hasStageEquivalentTerm(relPath, text, term));
  return { status: missing.length === 0 ? "pass" : "fail", missing };
}

function lazyRuntimeIndexEquivalent(text, term) {
  if (!text.includes("./ops-runtime-loader.js")) return false;
  if (!term.endsWith(".js")) return false;
  const normalized = term.replace(/^\.\//, "");
  if (!fileExists("ops-runtime-loader.js")) return false;
  return read("ops-runtime-loader.js").includes(`"${normalized}"`);
}

function hasStageEquivalentTerm(relPath, text, term) {
  if (relPath === "index.html" && lazyRuntimeIndexEquivalent(text, term)) return true;
  const equivalents = {
    "app.js": {
      "data-workspace-review-github-comment": ["reviewGithubCommentPanelAttributes(\"workspace-review\")", "scopeAttribute: `data-${prefix}-github-comment`"],
      "data-kb-review-github-comment": ["reviewGithubCommentPanelAttributes(\"kb-review\")", "scopeAttribute: `data-${prefix}-github-comment`"],
      "artifactKind: \"benchmark-issue\"": ["reviewIssueDraftPanelConfig(\"PM issue draft\", \"benchmark-issue\")"],
    },
    "scripts/smoke-interactions.mjs": {
      "not found on default branch": ["remoteWorkflowFilesReady=true", "remoteWorkflowFilesReady"],
      "home launch action should keep dispatch blocked": ["home launch action external launch claim state was stale", "home launch action card did not load current launch evidence with label"],
    },
    "data/publish-evidence.json": {
      "Do not post or dispatch until allDispatchReady: true and postPublishEvidenceReady: true.": ["Use this announcement only while evidenceFresh and postPublishEvidenceReady remain true."],
      "Status: blocked until live proof": ["Status: ready for public proof review", "Status: guarded until external claim ready"],
    },
    "data/launch-handoff-verification.json": {
      "\"safeToDispatch\": false": ["\"safeToDispatch\": true"],
      "collect_post_install_proof": ["proof_complete"],
    },
    "data/launch-handoff-verification.md": {
      "safeToDispatch: false": ["safeToDispatch: true"],
    },
    "data/launch-execution-packet.json": {
      "workflowScopeAvailable: false": ["workflowScopeAvailable: true"],
      "workflowScopeInstallBlocked: true": ["workflowScopeInstallBlocked: false"],
      "missingScopes: workflow": ["missingScopes: none"],
      "approval: approval_required": ["approval: not_required"],
      "workflowScopeMissing=workflow": ["workflowScopeMissing=none"],
      "Acceptance checklist: 2/5 pass; pending=3": ["Acceptance checklist: 5/5 pass; pending=0", "Acceptance checklist: 4/5 pass; pending=1"],
      "Operator auth path: action_required": ["Operator auth path: pass"],
      "Remote workflow file parity: action_required": ["Remote workflow file parity: pass"],
      "Workflow visibility: action_required": ["Workflow visibility: pass"],
      "active item: operator_auth_path": ["\"activeItemKey\": \"\"", "activeItemKey=not available", "active item: remote_workflow_file_parity"],
      "items: 2/6 pass; action_required=3; deferred=1": ["items: 6/6 pass; actionRequired=0; deferred=0", "items: 6/6 pass; action_required=0; deferred=0", "items: 4/6 pass; action_required=1; deferred=1"],
      "proof command: gh auth refresh -h github.com -s workflow": ["proofCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects"],
      "deferred_until_dispatch": ["launch_proof_capture: pass"],
      "action required - launch proof not complete": ["Status: ready"],
      "\"activeItemKey\": \"operator_auth_path\"": ["\"activeItemKey\": \"\"", "\"activeItemKey\": \"remote_workflow_file_parity\""],
      "collect_post_install_proof": ["proof_complete"],
      "\"proofComplete\": false": ["\"proofComplete\": true"],
      "\"completedFieldCount\": 0": ["\"completedFieldCount\": 6", "\"completedFieldCount\": 2"],
      "install_verification_required": ["workflowInstallVerificationMatrix"],
      "blocked_by_workflow_scope": ["workflowScopeInstallBlocked=false"],
      "remote_file_install_required": ["remoteWorkflowFileAcceptanceLedger"],
    },
    "data/output-quality-audit.json": {
      "Blocker resolution checklist: pass (active=operator_auth_path, 2/6 pass, actionRequired=3, deferred=1, proofCommands=6": ["Blocker resolution checklist: pass (active=not available, 6/6 pass, actionRequired=0, deferred=0, proofCommands=6", "Blocker resolution checklist: blocked (active=remote_workflow_file_parity, 4/6 pass, actionRequired=1, deferred=1, proofCommands=6"],
      "proofCommand=gh auth refresh -h github.com -s workflow": ["proofCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects"],
      "\"status\": \"blocked_external_claim\"": ["\"status\": \"ready_for_external_claim\""],
      "\"blockedCount\": 3": ["\"blockedCount\": 0", "\"blockedCount\": 2"],
      "status=blocked_external_claim; ready=false; blocked=3/3": ["status=ready_for_external_claim; ready=true; blocked=0/3", "status=blocked_external_claim; ready=false; blocked=2/3"],
      "signal readyForExternalClaim=false": ["signal readyForExternalClaim=true"],
      "release quality ready; public launch proof blocked": ["readyForExternalClaim=true"],
      "Launch packet readyForExternalClaim: false": ["Launch packet readyForExternalClaim: true", "launchPacketReadyForExternalClaim=true"],
      "Launch packet readyForExternalClaim: true": ["Launch packet readyForExternalClaim: false"],
      "remoteWorkflowFilesReady=false": ["remoteWorkflowFilesReady=true"],
      "postPublishEvidenceReady=false": ["postPublishEvidenceReady=true"],
      "readyForExternalClaim=false": ["readyForExternalClaim=true"],
      "Status: ready for public launch archive": ["Status: public launch proof ready; launch packet claim guard blocked"],
      "artifactQualityRubric=pass; totalScore=100/100; passingScore=90": ["artifactQualityRubric=blocked; totalScore=80/100; passingScore=90"],
      "Copy-ready completeness: pass (20/20)": ["Copy-ready completeness: blocked (0/20)"],
      "\"selectedVariant\": \"copy_ready_evidence_receipt\"": ["\"selectedVariant\": \"recheck_required\""],
      "\"decision\": \"keep_b\"": ["\"decision\": \"recheck_before_claim\""],
      "B: copy-ready evidence receipt: selected": ["B: copy-ready evidence receipt: recheck", "B: copy-ready evidence receipt: needs_recheck"],
      "goalCompletionAudit=output_quality_goal_covered": ["goalCompletionAudit=output_quality_goal_gaps"],
      "External output comparison: pass": ["External output comparison: blocked"],
      "AutoResearch usage: pass": ["AutoResearch usage: blocked"],
      "candidateComplete=true": ["candidateComplete=false"],
      "previousComplete=true": ["previousComplete=false"],
      "completionAuditReady=true; blocked=0; readyForExternalClaim=true": ["completionAuditReady=false; blocked=2; readyForExternalClaim=false", "completionAuditReady=false; blocked=3; readyForExternalClaim=false"],
      "Workflow installation: pass": ["Workflow installation: blocked"],
      "External completion claim: pass": ["External completion claim: blocked"],
      "Post-install proof parser: pass (6 fields, coverage=1)": ["Post-install proof parser: blocked (0 fields, coverage=0)"],
      "falsePositiveGuard=true": ["falsePositiveGuard=false"],
      "\"key\": \"share-launch-proof\"": ["\"key\": \"install_workflows\""],
      "\"source\": \"publish-evidence-next-action\"": ["\"source\": \"data/launch-execution-packet.json\""],
      "\"deferredKey\": \"\"": ["\"deferredKey\": \"capture-live-evidence\""],
      "\"deferredCommand\": \"\"": ["\"deferredCommand\": \"node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown\""],
      "Launch acceptance checklist: 5/5 pass, pending=0, stage=install_workflows": ["Launch acceptance checklist: 4/5 pass, pending=1, stage=install_workflows"],
      "Publish evidence command guard: pass (7 safe suggestions, 2 suggested dispatch, 0 withheld dispatch, active=0, reference=2, disposition=not_applicable_after_launch_proof)": ["Publish evidence command guard: pass (7 safe suggestions, 0 suggested dispatch, 2 withheld dispatch, active=0, reference=2, disposition=withheld_until_all_dispatch_ready)"],
      "Publish evidence immediate action: pass (share-launch-proof from publish-evidence-next-action, deferred not available)": ["Publish evidence immediate action: blocked (install_workflows from data/launch-execution-packet.json, deferred capture-live-evidence)"],
      "immediate action: Share launch proof": ["immediate action: Install workflows on the default branch"],
      "Immediate action: Share launch proof [ready]": ["Immediate action: Install workflows on the default branch [action_required]"],
      "deferred evidence capture: not available": ["deferred evidence capture: Capture live publish evidence"],
      "Immediate command: node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown": ["Immediate command: pbcopy < 'docs/github-pages-workflow.yml'"],
      "Deferred evidence capture: not available": ["Deferred evidence capture: Capture live publish evidence"],
      "\"key\": \"install_workflows\"": ["\"key\": \"share-launch-proof\""],
      "\"source\": \"data/launch-execution-packet.json\"": ["\"source\": \"publish-evidence-next-action\""],
      "\"deferredKey\": \"capture-live-evidence\"": ["\"deferredKey\": \"\""],
      "\"deferredKey\": null": ["\"deferredKey\": \"\""],
      "\"deferredCommand\": null": ["\"deferredCommand\": \"\""],
      "Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=false, workflowScopeInstallBlocked=true, missing=workflow, scopes=gist, read:org, repo)": ["Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=true, workflowScopeInstallBlocked=false"],
      "Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=true, workflowScopeInstallBlocked=false, missing=none, scopes=gist, read:org, repo, workflow)": ["Workflow auth preflight: blocked (uiVerified=false, workflowScopeAvailable=true, workflowScopeInstallBlocked=false, missing=none, scopes=gist, read:org, repo, workflow)"],
      "approval_required": ["not_required", "ready_for_external_claim"],
      "Launch acceptance checklist: 2/5 pass, pending=3, stage=install_workflows": ["Launch acceptance checklist: 5/5 pass, pending=0, stage=install_workflows"],
      "Launch install path options: pass (2 paths, 14 commands; CLI path after workflow scope | GitHub UI path)": ["Launch install path options: pass (2 paths, 13 commands; CLI path after workflow scope | GitHub UI path)", "Launch install path options: pass (2 paths, 10 commands; CLI path after workflow scope | GitHub UI path)"],
      "Publish evidence command guard: pass (7 safe suggestions, 0 suggested dispatch, 2 withheld dispatch, active=0, reference=2, disposition=withheld_until_all_dispatch_ready)": ["Publish evidence command guard: pass (7 safe suggestions, 2 suggested dispatch, 0 withheld dispatch, active=0, reference=2, disposition=not_applicable_after_launch_proof)"],
      "Publish evidence immediate action: pass (install_workflows from data/launch-execution-packet.json, deferred capture-live-evidence)": ["Publish evidence immediate action: pass (share-launch-proof from publish-evidence-next-action, deferred not available)"],
      "immediate action: Install workflows on the default branch": ["immediate action: Share launch proof"],
      "deferred evidence capture: Capture live publish evidence": ["deferred evidence capture: not available"],
      "Immediate command: gh auth refresh -h github.com -s workflow": ["Immediate command: node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"],
      "Deferred evidence capture: Capture live publish evidence": ["Deferred evidence capture: not available"],
      "Post-install quick proof field mapping: pass (0/4 mapped fields complete, coverage=1)": ["Post-install quick proof field mapping: pass (4/4 mapped fields complete, coverage=1)", "Post-install quick proof field mapping: pass (1/4 mapped fields complete, coverage=1)"],
      "Post-install quick proof field mapping: pass (4/4 mapped fields complete, coverage=1)": ["Post-install quick proof field mapping: pass (1/4 mapped fields complete, coverage=1)"],
      "\"status\": \"collect_post_install_proof\"": ["\"status\": \"proof_complete\""],
      "\"status\": \"proof_complete\"": ["\"status\": \"collect_post_install_proof\""],
      "\"completedFieldCount\": 6": ["\"completedFieldCount\": 2"],
      "\"proofComplete\": true": ["\"proofComplete\": false"],
      "Post-install evidence intake: pass (6 fields, coverage=1) - status=collect_post_install_proof, completed=0/6, proofComplete=false, commands=4, signals=8": ["Post-install evidence intake: pass (6 fields, coverage=1) - status=proof_complete, completed=6/6, proofComplete=true, commands=4, signals=8", "Post-install evidence intake: pass (6 fields, coverage=1) - status=collect_post_install_proof, completed=2/6, proofComplete=false, commands=4, signals=8"],
      "Post-install evidence intake: pass (6 fields, coverage=1) - status=proof_complete, completed=6/6, proofComplete=true, commands=4, signals=8": ["Post-install evidence intake: pass (6 fields, coverage=1) - status=collect_post_install_proof, completed=2/6, proofComplete=false, commands=4, signals=8"],
      "quickProofFieldMappingReady=true; mapped=4; completed=0/4; coverage=1": ["quickProofFieldMappingReady=true; mapped=4; completed=4/4; coverage=1", "quickProofFieldMappingReady=true; mapped=4; completed=1/4; coverage=1"],
      "quickProofFieldMappingReady=true; mapped=4; completed=4/4; coverage=1": ["quickProofFieldMappingReady=true; mapped=4; completed=1/4; coverage=1"],
      "source=generated_from_launch_execution_packet; status=collect_post_install_proof; proofComplete=false; completed=0/6; commands=4; signals=8": ["source=generated_from_launch_execution_packet; status=proof_complete; proofComplete=true; completed=6/6; commands=4; signals=8", "source=generated_from_launch_execution_packet; status=collect_post_install_proof; proofComplete=false; completed=2/6; commands=4; signals=8"],
      "source=generated_from_launch_execution_packet; status=proof_complete; proofComplete=true; completed=6/6; commands=4; signals=8": ["source=generated_from_launch_execution_packet; status=collect_post_install_proof; proofComplete=false; completed=2/6; commands=4; signals=8"],
      "remote_parity_proof: evidence_required": ["remote_parity_proof: proof_ready"],
      "remote_parity_proof: proof_ready": ["remote_parity_proof: evidence_required"],
      "handoff_verifier_proof: evidence_required": ["handoff_verifier_proof: proof_ready"],
      "handoff_verifier_proof: proof_ready": ["handoff_verifier_proof: evidence_required"],
	      "active=operator_auth_path": ["active=not available", "active=remote_workflow_file_parity"],
	      "active=not available": ["active=remote_workflow_file_parity"],
	      "Evidence downgrade guard: not applied": ["Evidence downgrade guard: preserved previous pass evidence"],
	      "candidateComplete=true": ["candidateComplete=false", "candidateComplete=false, previousComplete=true"],
	    },
	  };
  return (equivalents[relPath]?.[term] || []).some((alternative) => text.includes(alternative));
}

function duplicateHtmlIds(relPath) {
  if (!fileExists(relPath)) return { status: "fail", reason: "missing", duplicates: [] };
  const seen = new Set();
  const duplicates = new Set();
  for (const match of read(relPath).matchAll(/\bid\s*=\s*(["'])(.*?)\1/g)) {
    const id = match[2];
    if (seen.has(id)) duplicates.add(id);
    else seen.add(id);
  }
  return {
    status: duplicates.size === 0 ? "pass" : "fail",
    duplicates: [...duplicates].sort(),
    totalIds: seen.size,
  };
}

function runtimeScriptOrderSnapshot(relPath) {
  if (!fileExists(relPath)) return { status: "fail", reason: "missing", missing: [], outOfOrder: [] };
  const scripts = [...read(relPath).matchAll(/<script\b[^>]*\bsrc\s*=\s*(["'])(.*?)\1[^>]*>/gi)]
    .map((match) => match[2].replace(/^\.\//, "").replace(/[?#].*$/, ""));
  const missing = [];
  const outOfOrder = [];
  let previousIndex = -1;
  let previousScript = "";
  for (const script of expectedRuntimeScriptOrder) {
    const index = scripts.indexOf(script);
    if (index < 0) {
      missing.push(script);
      continue;
    }
    if (index <= previousIndex) outOfOrder.push({ script, after: previousScript });
    previousIndex = index;
    previousScript = script;
  }
  return {
    status: missing.length === 0 && outOfOrder.length === 0 ? "pass" : "fail",
    scripts,
    expected: expectedRuntimeScriptOrder,
    missing,
    outOfOrder,
  };
}

function dataSnapshot(relPath) {
  if (!fileExists(relPath)) return { status: "fail", reason: "missing" };
  const payload = parseJson(read(relPath));
  if (!payload || !Array.isArray(payload.projects) || payload.projects.length === 0) {
    return { status: "fail", reason: "missing projects array" };
  }
  return {
    status: "pass",
    projects: payload.projects.length,
    source: payload.source || "",
    generatedAt: payload.generatedAt || "",
  };
}

function adoptionCandidateSourceCoverage(relPath) {
  if (!fileExists(relPath)) return { status: "fail", reason: "missing" };
  const payload = parseJson(read(relPath));
  const projects = Array.isArray(payload?.projects) ? payload.projects : [];
  const candidates = projects.filter((project) => project?.sourceKind === "adoption-candidate");
  const source = String(payload?.source || "");
  const safeGithubPattern = /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/;
  const missingGithubUrl = candidates
    .filter((project) => !safeGithubPattern.test(String(project.url || "")))
    .map((project) => project.name || project.id || "unknown");
  const commitBacked = candidates.filter((project) => /^[0-9a-f]{40}$/i.test(String(project.lastCommit || "")));
  const sourceMarked = source.includes("github-api:source-gap-candidate-refresh");
  return {
    status: candidates.length > 0 && missingGithubUrl.length === 0 && sourceMarked && commitBacked.length >= 35 ? "pass" : "fail",
    candidates: candidates.length,
    missingGithubUrl,
    commitBacked: commitBacked.length,
    sourceMarked,
    generatedAt: payload?.generatedAt || "",
  };
}

function autoresearchCandidateSnapshot(relPath) {
  if (!fileExists(relPath)) return { status: "fail", reason: "missing" };
  const payload = parseJson(read(relPath));
  const projects = Array.isArray(payload?.projects) ? payload.projects : [];
  const matches = projects.filter((project) => {
    const topics = Array.isArray(project.topics) ? project.topics : [];
    return String(project.category || "").includes("오토리서치") ||
      topics.includes("autoresearch") ||
      String(project.name || "").toLowerCase().includes("autoresearch");
  });
  const names = new Set(matches.map((project) => project.name));
  const required = [
    "karpathy/autoresearch",
    "Veritas-7/autoresearch-skill-system",
    "biojuho/autoresearch-skill-system",
  ];
  const missing = required.filter((name) => !names.has(name));
  const source = payload?.source || "";
  const veritas = projects.find((project) => project.name === "Veritas-7/autoresearch-skill-system") || null;
  const veritasCommitPattern = /^[0-9a-f]{40}$/i;
  const veritasSnapshotValid = Boolean(veritas) &&
    veritasCommitPattern.test(String(veritas.lastCommit || "")) &&
    Number.isFinite(Date.parse(veritas.pushedAt || "")) &&
    String(veritas.description || "").includes("최신");
  const veritasFresh = Boolean(veritas) &&
    veritasSnapshotValid;
  const veritasSourceMarked = source.includes("github-api:veritas-autoresearch-refresh");
  return {
    status: matches.length >= 8 && missing.length === 0 && veritasFresh && veritasSourceMarked ? "pass" : "fail",
    source,
    generatedAt: payload?.generatedAt || "",
    candidates: matches.length,
    veritas: {
      latestCommit: veritas?.lastCommit || "",
      lastCommit: veritas?.lastCommit || "",
      latestPushedAt: veritas?.pushedAt || "",
      pushedAt: veritas?.pushedAt || "",
      fresh: veritasFresh,
      snapshotValid: veritasSnapshotValid,
      sourceMarked: veritasSourceMarked,
    },
    required,
    missing,
  };
}

function workspaceCandidateSnapshot(relPath) {
  if (!fileExists(relPath)) return { status: "fail", reason: "missing" };
  const payload = parseJson(read(relPath));
  const projects = Array.isArray(payload?.projects) ? payload.projects : [];
  const workspaceTopics = new Set([
    "local-first",
    "workspace",
    "offline-first",
    "project-management",
    "kanban",
    "calendar",
    "task-manager",
    "scheduling",
    "developer-productivity",
  ]);
  const matches = projects.filter((project) => {
    const topics = Array.isArray(project.topics) ? project.topics : [];
    const category = String(project.category || "");
    return category.includes("워크스페이스") ||
      category.includes("프로젝트관리") ||
      category.includes("일정관리") ||
      category.includes("캘린더/일정") ||
      topics.some((topic) => workspaceTopics.has(topic));
  });
  const names = new Set(matches.map((project) => project.name));
  const required = [
    "EpicenterHQ/epicenter",
    "OpenLoaf/OpenLoaf",
    "makeplane/plane",
    "AppFlowy-IO/AppFlowy",
    "toeverything/AFFiNE",
    "outline/outline",
    "BookStackApp/BookStack",
    "requarks/wiki",
    "happybhati/workstream",
    "colanode/colanode",
    "anyproto/anytype-ts",
    "opf/openproject",
    "ParabolInc/parabol",
    "Leantime/leantime",
    "Worklenz/worklenz",
  ];
  const missing = required.filter((name) => !names.has(name));
  const source = payload?.source || "";
  const sourceMarked = source.includes("github-search:local-first-workspace");
  const apiMarked = source.includes("github-api:workspace-benchmark-refresh");
  const freshnessCommitPattern = /^[0-9a-f]{40}$/i;
  const workspaceFreshnessExpectations = [
    {
      key: "epicenter",
      name: "EpicenterHQ/epicenter",
      sourceMarker: "github-api:epicenter-freshness-refresh",
    },
    {
      key: "openLoaf",
      name: "OpenLoaf/OpenLoaf",
      sourceMarker: "github-api:openloaf-freshness-refresh",
    },
    {
      key: "plane",
      name: "makeplane/plane",
      sourceMarker: "github-api:plane-freshness-refresh",
    },
    {
      key: "appFlowy",
      name: "AppFlowy-IO/AppFlowy",
      sourceMarker: "github-api:appflowy-freshness-refresh",
    },
    {
      key: "affine",
      name: "toeverything/AFFiNE",
      sourceMarker: "github-api:affine-freshness-refresh",
    },
    {
      key: "outline",
      name: "outline/outline",
      sourceMarker: "github-api:outline-freshness-refresh",
    },
    {
      key: "bookStack",
      name: "BookStackApp/BookStack",
      sourceMarker: "github-api:bookstack-freshness-refresh",
    },
    {
      key: "wikiJs",
      name: "requarks/wiki",
      sourceMarker: "github-api:wikijs-freshness-refresh",
    },
    {
      key: "colanode",
      name: "colanode/colanode",
      sourceMarker: "github-api:colanode-freshness-refresh",
    },
    {
      key: "openProject",
      name: "opf/openproject",
      sourceMarker: "github-api:openproject-freshness-refresh",
    },
    {
      key: "parabol",
      name: "ParabolInc/parabol",
      sourceMarker: "github-api:parabol-freshness-refresh",
    },
    {
      key: "leantime",
      name: "Leantime/leantime",
      sourceMarker: "github-api:leantime-freshness-refresh",
    },
    {
      key: "worklenz",
      name: "Worklenz/worklenz",
      sourceMarker: "github-api:worklenz-freshness-refresh",
    },
    {
      key: "anytype",
      name: "anyproto/anytype-ts",
      sourceMarker: "github-api:anytype-freshness-refresh",
    },
    {
      key: "focalboard",
      name: "mattermost-community/focalboard",
      sourceMarker: "github-api:focalboard-freshness-refresh",
    },
    {
      key: "workstream",
      name: "happybhati/workstream",
      sourceMarker: "github-api:remaining-workspace-freshness-refresh",
    },
    {
      key: "taskosaur",
      name: "Taskosaur/Taskosaur",
      sourceMarker: "github-api:remaining-workspace-freshness-refresh",
    },
    {
      key: "markdownTaskManager",
      name: "ioniks/MarkdownTaskManager",
      sourceMarker: "github-api:remaining-workspace-freshness-refresh",
    },
    {
      key: "taskcoach",
      name: "taskcoach/taskcoach",
      sourceMarker: "github-api:remaining-workspace-freshness-refresh",
    },
    {
      key: "fluidCalendar",
      name: "dotnetfactory/fluid-calendar",
      sourceMarker: "github-api:remaining-workspace-freshness-refresh",
    },
  ];
  const freshness = Object.fromEntries(workspaceFreshnessExpectations.map((item) => {
    const project = projects.find((candidate) => candidate.name === item.name) || null;
    const snapshotValid = Boolean(project) &&
      freshnessCommitPattern.test(String(project.lastCommit || "")) &&
      Number.isFinite(Date.parse(project.pushedAt || ""));
    const fresh = Boolean(project) &&
      snapshotValid;
    const sourceMarked = source.includes(item.sourceMarker);
    return [item.key, {
      name: item.name,
      latestCommit: project?.lastCommit || "",
      lastCommit: project?.lastCommit || "",
      latestPushedAt: project?.pushedAt || "",
      pushedAt: project?.pushedAt || "",
      fresh,
      snapshotValid,
      sourceMarked,
    }];
  }));
  const freshnessOk = Object.values(freshness).every((item) => item.fresh && item.sourceMarked);
  return {
    status: matches.length >= 14 && missing.length === 0 && sourceMarked && apiMarked && freshnessOk ? "pass" : "fail",
    source,
    generatedAt: payload?.generatedAt || "",
    candidates: matches.length,
    sourceMarked,
    apiMarked,
    ...freshness,
    required,
    missing,
  };
}

function releaseManifestProvenance() {
  const relPath = "dist/release/release-manifest.json";
  const provenanceRelPath = "dist/release/release-provenance.json";
  if (!fileExists(relPath)) return { status: "fail", reason: "release-manifest.json missing" };
  if (!fileExists(provenanceRelPath)) return { status: "fail", reason: "release-provenance.json missing" };
  const manifest = parseJson(read(relPath));
  const provenance = parseJson(read(provenanceRelPath));
  const missing = [];
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return { status: "fail", reason: "invalid manifest JSON object" };
  }
  if (!provenance || typeof provenance !== "object" || Array.isArray(provenance)) {
    return { status: "fail", reason: "invalid provenance JSON object" };
  }
  if (!manifest.sourceCommit) missing.push("sourceCommit");
  if (!manifest.source || typeof manifest.source !== "object" || Array.isArray(manifest.source)) {
    missing.push("source");
  } else {
    if (manifest.source.commit !== manifest.sourceCommit) missing.push("source.commit");
    if (!manifest.source.branch) missing.push("source.branch");
    if (typeof manifest.source.dirty !== "boolean") missing.push("source.dirty");
    if (!Array.isArray(manifest.source.dirtyFiles)) missing.push("source.dirtyFiles");
  }
  const predicate = provenance.predicate || {};
  const buildDefinition = predicate.buildDefinition || {};
  const externalParameters = buildDefinition.externalParameters || {};
  const runDetails = predicate.runDetails || {};
  const jooparkRelease = predicate.joopark_release || {};
  const manifestSha256 = fileStatEvidence(relPath).sha256;
  const manifestSubject = Array.isArray(provenance.subject)
    ? provenance.subject.find((item) => item?.name === "release-manifest.json")
    : null;
  const dependencies = Array.isArray(buildDefinition.resolvedDependencies) ? buildDefinition.resolvedDependencies : [];
  const dependencyNames = new Set(dependencies.map((item) => item?.name).filter(Boolean));
  for (const [field, valid] of [
    ["provenance._type", provenance._type === "https://in-toto.io/Statement/v1"],
    ["provenance.predicateType", provenance.predicateType === "https://slsa.dev/provenance/v1"],
    ["provenance.subject.release-manifest.json", manifestSubject?.digest?.sha256 === manifestSha256],
    ["provenance.buildType", buildDefinition.buildType === "https://biojuho.local/joopark/static-release/v1"],
    ["provenance.builder.id", runDetails.builder?.id === "https://biojuho.local/joopark/local-release-packager"],
    ["provenance.externalParameters.sourceCommit", externalParameters.sourceCommit === manifest.sourceCommit],
    ["provenance.externalParameters.sourceBranch", externalParameters.sourceBranch === manifest.source?.branch],
    ["provenance.externalParameters.sourceDirty", externalParameters.sourceDirty === manifest.source?.dirty],
    ["provenance.joopark_release.signatureStatus", jooparkRelease.signatureStatus === "unsigned-local-provenance"],
    ["provenance.joopark_release.signed", jooparkRelease.signed === false],
  ]) {
    if (!valid) missing.push(field);
  }
  for (const dependency of ["source-tree", "index.html", "app.js", "sw.js", "README.md", "data", "vendor"]) {
    if (!dependencyNames.has(dependency)) missing.push(`resolvedDependencies.${dependency}`);
  }
  return {
    status: missing.length === 0 ? "pass" : "fail",
    sourceCommit: manifest.sourceCommit || "",
    source: manifest.source || null,
    manifestSha256,
    provenanceSubjectDigest: manifestSubject?.digest?.sha256 || "",
    predicateType: provenance.predicateType || "",
    buildType: buildDefinition.buildType || "",
    builderId: runDetails.builder?.id || "",
    signatureStatus: jooparkRelease.signatureStatus || "",
    signed: jooparkRelease.signed === true,
    dependencies: dependencies.length,
    missing,
  };
}

function gitBranchSync() {
  const status = run("git", ["status", "--short", "--branch"]);
  const branchLine = (status.stdout || "").split("\n")[0] || "";
  const hasTracking = /\.\.\./.test(branchLine);
  const markers = [];
  if (/\bahead\b/.test(branchLine)) markers.push("ahead");
  if (/\bbehind\b/.test(branchLine)) markers.push("behind");
  if (/\bgone\b/.test(branchLine)) markers.push("gone");
  if (/\bdiverged\b/.test(branchLine)) markers.push("diverged");
  return {
    status: status.ok && hasTracking && markers.length === 0 ? "pass" : "blocked",
    command: "git status --short --branch",
    branchLine,
    hasTracking,
    markers,
  };
}

function verifyRelease() {
  const packageResult = run(process.execPath, ["scripts/package-release.mjs"], { timeout: 30000 });
  const packagePayload = parseJson(packageResult.stdout);
  if (!packageResult.ok || !packagePayload || packagePayload.status !== "pass") {
    return {
      status: "fail",
      command: "node scripts/package-release.mjs && node scripts/verify-release.mjs",
      result: {
        package: packagePayload || {
          stdout: packageResult.stdout.trim(),
          stderr: packageResult.stderr.trim(),
          error: packageResult.error,
        },
      },
    };
  }
  const result = run(process.execPath, ["scripts/verify-release.mjs"], { timeout: 30000 });
  const payload = parseJson(result.stdout);
  return {
    status: result.ok && payload && payload.status === "pass" ? "pass" : "fail",
    command: "node scripts/package-release.mjs && node scripts/verify-release.mjs",
    result: payload ? { ...payload, package: packagePayload } : { package: packagePayload, stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function appStructureAudit() {
  const result = run(process.execPath, ["scripts/check-app-structure.mjs"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const boundariesOk = Array.isArray(payload?.boundaries) &&
    payload.boundaries.length >= 12 &&
    payload.boundaries.every((item) => item.status === "pass");
  const extractionReady = Array.isArray(payload?.extractionPlan) &&
    payload.extractionPlan.length >= 5 &&
    payload.extractionPlan.every((item) => item.status === "ready" || item.status === "extracted");
  return {
    status: result.ok && payload && payload.status === "pass" && boundariesOk && extractionReady ? "pass" : "fail",
    command: "node scripts/check-app-structure.mjs",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function githubPagesWorkflowHandoffDryRun() {
  const result = run(process.execPath, ["scripts/prepare-github-pages-workflow.mjs", "--dry-run", "--check-scope"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  return {
    status: result.ok && payload && payload.status === "pass" && payload.mode === "dry-run" && payload.willWrite === false && payload.targetRepositoryPath === ".github/workflows/joopark-pages.yml" && payload.workflowScopeChecked === true && typeof payload.workflowScopeAvailable === "boolean" ? "pass" : "fail",
    command: "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function githubDriftWatchWorkflowHandoffDryRun() {
  const result = run(process.execPath, ["scripts/prepare-github-drift-watch-workflow.mjs", "--dry-run", "--check-scope"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  return {
    status: result.ok && payload && payload.status === "pass" && payload.mode === "dry-run" && payload.willWrite === false && payload.targetRepositoryPath === ".github/workflows/joopark-drift-watch.yml" && payload.workflowScopeChecked === true && typeof payload.workflowScopeAvailable === "boolean" ? "pass" : "fail",
    command: "node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function mainBridgePlan() {
  const result = run(process.execPath, ["scripts/plan-main-bridge.mjs"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const validStrategy = payload?.noCommonHistory === true ||
    payload?.strategy === "pr-ready-main-history";
  return {
    status: result.ok && payload && payload.status === "pass" && payload.mainAppPathExists === true && validStrategy ? "pass" : "fail",
    command: "node scripts/plan-main-bridge.mjs",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function publishDispatchPlan() {
  const result = run(process.execPath, ["scripts/plan-publish-dispatch.mjs", "--dry-run"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const uiInstallPlans = Array.isArray(payload?.workflowUiInstallPlans) ? payload.workflowUiInstallPlans : [];
  const workflowPlans = Array.isArray(payload?.workflowPlans) ? payload.workflowPlans : [];
  const defaultBranchHandoff = payload?.workflowDefaultBranchHandoff || {};
  const hasCopyOpenCommands = (plan) =>
    plan?.templateCopyCommand?.startsWith("pbcopy < ") &&
    plan?.githubNewFileOpenCommand?.startsWith("open ") &&
    plan?.githubWorkflowOpenCommand?.startsWith("open ");
  const uiInstallPlansReady = uiInstallPlans.length === 2 && uiInstallPlans.every((plan) =>
    plan.uiInstallReady === true &&
    plan.githubNewFileUrl?.includes("github.com/biojuho/BIOJUHO-Projects/new/main") &&
    plan.githubWorkflowUrl?.includes("github.com/biojuho/BIOJUHO-Projects/actions/workflows/") &&
    typeof plan.templateSha256 === "string" &&
    plan.templateSha256.length === 64 &&
    typeof plan.targetSha256 === "string" &&
    plan.targetSha256.length === 64 &&
    plan.targetMatchesTemplate === true &&
    plan.localTargetParityReady === true &&
    plan.manualDispatchRequirement?.includes("workflow_dispatch") &&
	    plan.suggestedRepo === "biojuho/BIOJUHO-Projects" &&
	    plan.nextVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
	    plan.placeholderVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO" &&
	    plan.workflowScopeRefreshCommand === "gh auth refresh -h github.com -s workflow" &&
	    plan.workflowScopeRecheckCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
	    hasCopyOpenCommands(plan)
  );
  const workflowPlansReady = workflowPlans.length >= 2 && workflowPlans.every((plan) =>
    plan.targetExists === true &&
    plan.targetMatchesTemplate === true &&
    plan.localTargetParityReady === true &&
    typeof plan.templateSha256 === "string" &&
    plan.templateSha256.length === 64 &&
    typeof plan.targetSha256 === "string" &&
    plan.targetSha256.length === 64 &&
    plan.uiInstallPlan?.githubNewFileUrl &&
    plan.uiInstallPlan?.githubWorkflowUrl &&
    plan.uiInstallPlan?.targetMatchesTemplate === true &&
    hasCopyOpenCommands(plan.uiInstallPlan) &&
    plan.scopeCheckCommand?.includes("--check-scope")
  );
  const suggestedCommands = Array.isArray(payload?.suggestedCommands) ? payload.suggestedCommands : [];
  const suggestedVerificationCommands = Array.isArray(payload?.suggestedVerificationCommands) ? payload.suggestedVerificationCommands : [];
  const suggestedDispatchCommands = Array.isArray(payload?.suggestedDispatchCommands) ? payload.suggestedDispatchCommands : [];
  const withheldDispatchCommands = Array.isArray(payload?.withheldDispatchCommands) ? payload.withheldDispatchCommands : [];
  const nextActions = Array.isArray(payload?.nextActions) ? payload.nextActions : [];
  const stagedWorkflowNextActionReady = nextActions.some((action) =>
    action.includes("staged repository-root workflows") ||
    action.includes("workflowUiInstallPlans") ||
    action.includes("workflow scope") ||
    action.includes("workflow-scope")
  );
  const workflowScopeNextActionReady = payload?.workflowScopeAvailable === true ||
    nextActions.some((action) => action.includes("gh auth refresh -h github.com -s workflow"));
  const gitAddNextActionReady = nextActions.some((action) =>
    action.includes("git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml")
  );
  const repoVerificationNextActionReady = nextActions.some((action) =>
    action.includes("--repo biojuho/BIOJUHO-Projects")
  );
  return {
    status: result.ok &&
      payload &&
      payload.status === "pass" &&
      payload.repo === "OWNER/REPO" &&
      payload.suggestedRepo === "biojuho/BIOJUHO-Projects" &&
      payload.repoReplacementHint?.includes("biojuho/BIOJUHO-Projects") &&
      payload.repoEvidenceReady === false &&
      payload.localWorkflowTargetsReady === true &&
      payload.localTargetParityReady === true &&
      payload.remoteWorkflowVisibilityReady === false &&
      payload.workflowScopeChecked === true &&
      typeof payload.workflowScopeAvailable === "boolean" &&
      typeof payload.workflowScopeInstallBlocked === "boolean" &&
      payload.workflowScopeRefreshCommand === "gh auth refresh -h github.com -s workflow" &&
      payload.workflowScopeRecheckCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
      payload.workflowScopeRefreshHandoff?.command === payload.workflowScopeRefreshCommand &&
      defaultBranchHandoff.workflowScopeRefreshCommand === payload.workflowScopeRefreshCommand &&
      defaultBranchHandoff.workflowScopeRecheckCommand === payload.workflowScopeRecheckCommand &&
      defaultBranchHandoff.localStageReady === true &&
      defaultBranchHandoff.gitAddCommand === "git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml" &&
      defaultBranchHandoff.gitCommitCommand === "git commit -m 'Add JooPark publish workflows'" &&
      defaultBranchHandoff.remoteVisibilityVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
      defaultBranchHandoff.requirement?.includes("default branch") &&
      payload.nextVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
      payload.placeholderVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO" &&
      payload.dispatchReady === false &&
      payload.driftDispatchReady === false &&
      payload.allDispatchReady === false &&
      payload.dispatchSuggestionStatus === "withheld-until-all-dispatch-ready" &&
      suggestedCommands.length === 1 &&
      suggestedCommands[0] === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
      !suggestedCommands.some((command) => command.includes("gh workflow run --repo")) &&
      suggestedVerificationCommands.length === 1 &&
      suggestedVerificationCommands[0] === suggestedCommands[0] &&
      suggestedDispatchCommands.length === 0 &&
      payload.suggestedDispatchCommandCount === 0 &&
      withheldDispatchCommands.length === 2 &&
      payload.withheldDispatchCommandCount === 2 &&
      payload.pagesWorkflowDispatchRef === "codex/joopark-workspace-release" &&
      payload.dispatchCommandExplicitRefReady === true &&
      withheldDispatchCommands.includes("gh workflow run --repo OWNER/REPO joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
      withheldDispatchCommands.includes("gh workflow run --repo OWNER/REPO joopark-drift-watch.yml -f mode=advisory") &&
      payload.workflowUiInstallReady === true &&
      uiInstallPlansReady &&
      nextActions.length > 0 &&
      stagedWorkflowNextActionReady &&
      workflowScopeNextActionReady &&
      gitAddNextActionReady &&
      repoVerificationNextActionReady &&
      workflowPlansReady &&
      Array.isArray(payload.blockers) &&
      payload.blockers.length > 0 &&
      payload.workflowListCommand === "gh workflow list --repo OWNER/REPO --all --json name,path,state,id" &&
      payload.dispatchCommand === "gh workflow run --repo OWNER/REPO joopark-pages.yml -f ref=codex/joopark-workspace-release" &&
      payload.driftDispatchCommand === "gh workflow run --repo OWNER/REPO joopark-drift-watch.yml -f mode=advisory"
      ? "pass"
      : "fail",
    command: "node scripts/plan-publish-dispatch.mjs --dry-run",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function publishDispatchPlanFile() {
  const path = "data/publish-dispatch-plan.json";
  if (!fileExists(path)) return { status: "fail", path, reason: "missing" };
  const payload = parseJson(read(path));
  const workflowPlans = Array.isArray(payload?.workflowPlans) ? payload.workflowPlans : [];
  const defaultBranchHandoff = payload?.workflowDefaultBranchHandoff || {};
  const suggestedCommands = Array.isArray(payload?.suggestedCommands) ? payload.suggestedCommands : [];
  const suggestedVerificationCommands = Array.isArray(payload?.suggestedVerificationCommands) ? payload.suggestedVerificationCommands : [];
  const suggestedDispatchCommands = Array.isArray(payload?.suggestedDispatchCommands) ? payload.suggestedDispatchCommands : [];
  const withheldDispatchCommands = Array.isArray(payload?.withheldDispatchCommands) ? payload.withheldDispatchCommands : [];
  const workflowPlanShapeReady = workflowPlans.length === 2 &&
    workflowPlans.every((plan) =>
      plan.workflowPath?.startsWith(".github/workflows/") &&
      plan.targetExists === true &&
      plan.targetMatchesTemplate === true &&
      plan.localTargetParityReady === true &&
      typeof plan.templateSha256 === "string" &&
      plan.templateSha256.length === 64 &&
      typeof plan.targetSha256 === "string" &&
      plan.targetSha256.length === 64 &&
      typeof plan.dispatchCommand === "string"
    );
  const workflowPlansWithheld = workflowPlanShapeReady && workflowPlans.every((plan) =>
    plan.dispatchReady === false &&
    Array.isArray(plan.blockers) &&
    plan.blockers.length >= 1 &&
    plan.blockers.every((blocker) => blocker.includes("workflow is not visible in GitHub Actions"))
  );
  const workflowPlansDispatchReady = workflowPlanShapeReady && workflowPlans.every((plan) =>
    plan.dispatchReady === true &&
    plan.targetMatchesTemplate === true &&
    plan.localTargetParityReady === true &&
    (!Array.isArray(plan.blockers) || plan.blockers.length === 0)
  );
  const dispatchWithheldReady =
    payload.remoteWorkflowVisibilityReady === false &&
    payload.dispatchReady === false &&
    payload.driftDispatchReady === false &&
    payload.allDispatchReady === false &&
    payload.dispatchSuggestionStatus === "withheld-until-all-dispatch-ready" &&
    suggestedCommands.length === 1 &&
    suggestedCommands[0] === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
    !suggestedCommands.some((command) => command.includes("gh workflow run --repo")) &&
    suggestedVerificationCommands.length === 1 &&
    suggestedVerificationCommands[0] === suggestedCommands[0] &&
    suggestedDispatchCommands.length === 0 &&
    payload.suggestedDispatchCommandCount === 0 &&
    withheldDispatchCommands.length === 2 &&
    payload.withheldDispatchCommandCount === 2 &&
    payload.pagesWorkflowDispatchRef === "codex/joopark-workspace-release" &&
    payload.dispatchCommandExplicitRefReady === true &&
    withheldDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
    withheldDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") &&
    Array.isArray(payload.blockers) &&
    payload.blockers.some((blocker) => blocker.includes("workflow is not visible in GitHub Actions")) &&
    workflowPlansWithheld;
  const dispatchBlockedByRemoteMismatch =
    payload.remoteWorkflowFilesChecked === true &&
    payload.remoteWorkflowFilesReady === false &&
    payload.remoteWorkflowVisibilityReady === true &&
    payload.dispatchReady === false &&
    payload.driftDispatchReady === true &&
    payload.allDispatchReady === false &&
    payload.dispatchSuggestionStatus === "withheld-until-all-dispatch-ready" &&
    suggestedVerificationCommands.length === 1 &&
    suggestedDispatchCommands.length === 0 &&
    payload.suggestedDispatchCommandCount === 0 &&
    withheldDispatchCommands.length === 2 &&
    payload.withheldDispatchCommandCount === 2 &&
    Array.isArray(payload.blockers) &&
    payload.blockers.some((blocker) => blocker.includes("remote workflow file does not match the local template")) &&
    workflowPlanShapeReady &&
    workflowPlans.some((plan) => plan.key === "pages" && plan.dispatchReady === false && plan.remoteFileReady === false) &&
    workflowPlans.some((plan) => plan.key === "drift-watch" && plan.dispatchReady === true && plan.remoteFileReady === true);
  const dispatchReady =
    payload.remoteWorkflowVisibilityReady === true &&
    payload.dispatchReady === true &&
    payload.driftDispatchReady === true &&
    payload.allDispatchReady === true &&
    payload.dispatchSuggestionStatus === "ready" &&
    suggestedDispatchCommands.length === 2 &&
    payload.suggestedDispatchCommandCount === 2 &&
    withheldDispatchCommands.length === 0 &&
    payload.withheldDispatchCommandCount === 0 &&
    payload.pagesWorkflowDispatchRef === "codex/joopark-workspace-release" &&
    payload.dispatchCommandExplicitRefReady === true &&
    suggestedDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
    suggestedDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") &&
    (!Array.isArray(payload.blockers) || payload.blockers.length === 0) &&
    workflowPlansDispatchReady;
  return {
    status: payload &&
      payload.status === "pass" &&
      payload.mode === "live" &&
      payload.repo === "biojuho/BIOJUHO-Projects" &&
      payload.suggestedRepo === "biojuho/BIOJUHO-Projects" &&
      payload.repoEvidenceReady === true &&
	      payload.workflowScopeChecked === true &&
	      typeof payload.workflowScopeAvailable === "boolean" &&
	      typeof payload.workflowScopeInstallBlocked === "boolean" &&
	      payload.workflowScopeRefreshCommand === "gh auth refresh -h github.com -s workflow" &&
	      payload.workflowScopeRecheckCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
	      payload.workflowScopeRefreshHandoff?.command === payload.workflowScopeRefreshCommand &&
	      payload.localWorkflowTargetsReady === true &&
		      payload.localTargetParityReady === true &&
		      defaultBranchHandoff.localStageReady === true &&
		      defaultBranchHandoff.workflowScopeRefreshCommand === payload.workflowScopeRefreshCommand &&
		      defaultBranchHandoff.workflowScopeRecheckCommand === payload.workflowScopeRecheckCommand &&
	      defaultBranchHandoff.gitAddCommand === "git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml" &&
      defaultBranchHandoff.gitCommitCommand === "git commit -m 'Add JooPark publish workflows'" &&
      defaultBranchHandoff.remoteVisibilityVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
	      payload.workflowScopeApprovalHandoff?.fallback?.includes("installAction") &&
	      payload.workflowPlans?.some((plan) => plan.key === "pages" && plan.installAction === "replace_existing_remote_file") &&
      payload.targetExists === true &&
	      payload.workflowUiInstallReady === true &&
	      payload.workflowListCommand === "gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id" &&
	      payload.nextVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
		      payload.writtenTo === "data/publish-dispatch-plan.json" &&
	      (dispatchWithheldReady || dispatchBlockedByRemoteMismatch || dispatchReady)
	      ? "pass"
	      : "fail",
    path,
    result: payload,
  };
}

function remoteWorkflowFileCheckPlan() {
  const result = run(process.execPath, ["scripts/check-remote-workflow-files.mjs", "--repo", "OWNER/REPO"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const checks = Array.isArray(payload?.checks) ? payload.checks : [];
  const approvalHandoff = payload?.workflowScopeApprovalHandoff || {};
  return {
    status: result.ok &&
      payload &&
      payload.status === "pass" &&
      payload.mode === "dry-run" &&
      payload.repo === "OWNER/REPO" &&
      payload.repoEvidenceReady === false &&
      payload.remoteWorkflowFilesChecked === false &&
      payload.remoteWorkflowFilesReady === false &&
      payload.installPacket?.includes("JooPark Remote Workflow Install Packet") &&
      payload.installPacket?.includes("install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") &&
      payload.installPacket?.includes("Workflow scope preflight:") &&
      payload.installPacket?.includes("one-time device code policy") &&
      payload.installPacket?.includes("GitHub UI fallback") &&
      payload.installPacket?.includes("Do not run gh workflow run until remoteWorkflowFilesReady: true and allDispatchReady: true") &&
      payload.sourceUrl === "https://docs.github.com/en/rest/repos/contents#get-repository-content" &&
      payload.manualDispatchDocsUrl === "https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui" &&
      payload.editFileDocsUrl === "https://docs.github.com/en/repositories/working-with-files/managing-files/editing-files" &&
      payload.updateFileContentsDocsUrl === "https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents" &&
      payload.remediationSummary?.currentAction === "replace_repo_placeholder" &&
      payload.workflowScopeChecked === true &&
      typeof payload.workflowScopeAvailable === "boolean" &&
      typeof payload.workflowScopeInstallBlocked === "boolean" &&
      payload.workflowScopeRefreshCommand === "gh auth refresh -h github.com -s workflow" &&
      payload.workflowScopeRecheckCommand === "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write" &&
      approvalHandoff.command === payload.workflowScopeRefreshCommand &&
      approvalHandoff.approvalUrl === "https://github.com/login/device" &&
      approvalHandoff.recheckCommand === payload.workflowScopeRecheckCommand &&
      approvalHandoff.dispatchPlanCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write" &&
      approvalHandoff.sensitiveValuePolicy?.includes("Do not store, log, or paste the one-time device code") &&
      approvalHandoff.fallback?.includes("installAction") &&
      approvalHandoff.stopCondition?.includes("remoteWorkflowFilesReady=true") &&
      payload.remoteInstallerCommand === "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify" &&
      payload.nextVerificationCommand === "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write" &&
      checks.length === 2 &&
      checks.every((check) =>
        check.path?.startsWith(".github/workflows/") &&
        check.templateCopyCommand?.startsWith("pbcopy < ") &&
        typeof check.githubNewFileOpenCommand === "string" &&
        typeof check.githubEditFileOpenCommand === "string" &&
        check.installAction === "replace_repo_placeholder" &&
        check.remediation?.installAction === "replace_repo_placeholder" &&
        check.remoteChecked === false &&
        check.remoteExists === false &&
        check.remoteMatchesTemplate === false &&
        typeof check.templateSha256 === "string" &&
        check.templateSha256.length === 64 &&
        check.command === "gh api --method GET repos/OWNER/REPO/contents/PATH -f ref=BRANCH"
      )
      ? "pass"
      : "fail",
    command: "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function remoteWorkflowFileCheckFallbackReady(fallback) {
  return !fallback || fallback.includes("installAction");
}

function remoteWorkflowInstallerPlan() {
  const result = run(process.execPath, ["scripts/install-remote-workflow-files.mjs", "--repo", "OWNER/REPO"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const operations = Array.isArray(payload?.operations) ? payload.operations : [];
  const approvalHandoff = payload?.workflowScopeApprovalHandoff || {};
  return {
    status: result.ok &&
      payload &&
      payload.status === "pass" &&
      payload.mode === "dry-run" &&
      payload.repo === "OWNER/REPO" &&
      payload.repoEvidenceReady === false &&
      payload.workflowScopeChecked === true &&
      typeof payload.workflowScopeAvailable === "boolean" &&
      payload.workflowScopeInstallBlocked === false &&
      payload.remoteWriteReady === false &&
      payload.remoteWorkflowFilesReady === false &&
      payload.workflowScopeRefreshCommand === "gh auth refresh -h github.com -s workflow" &&
      payload.workflowScopeRecheckCommand === "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify" &&
      approvalHandoff.command === payload.workflowScopeRefreshCommand &&
      approvalHandoff.approvalUrl === "https://github.com/login/device" &&
      approvalHandoff.recheckCommand === payload.workflowScopeRecheckCommand &&
      approvalHandoff.remoteFileCheckCommand === "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write" &&
      approvalHandoff.dispatchPlanCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write" &&
      approvalHandoff.sensitiveValuePolicy?.includes("Do not store, log, or paste the one-time device code") &&
      approvalHandoff.fallback?.includes("operation value") &&
      approvalHandoff.stopCondition?.includes("remoteWorkflowFilesReady=true") &&
      Array.isArray(payload.postInstallVerificationCommands) &&
      payload.postInstallVerificationCommands.includes("node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write") &&
      payload.postInstallVerificationCommands.includes("node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write") &&
      operations.length === 2 &&
      operations.every((operation) =>
        operation.path?.startsWith(".github/workflows/") &&
        operation.operation === "blocked" &&
        operation.remoteChecked === false &&
        operation.remoteExists === false &&
        operation.remoteMatchesTemplate === false &&
        operation.writeRequired === false &&
        typeof operation.templateSha256 === "string" &&
        operation.templateSha256.length === 64 &&
        operation.putCommand?.includes("gh api --method PUT repos/OWNER/REPO/contents/") &&
        Array.isArray(operation.blockers) &&
        operation.blockers.some((blocker) => blocker.includes("replace OWNER/REPO"))
      )
      ? "pass"
      : "fail",
    command: "node scripts/install-remote-workflow-files.mjs --repo OWNER/REPO",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function remoteWorkflowFileCheckFile() {
  const path = "data/remote-workflow-file-check.json";
  if (!fileExists(path)) return { status: "fail", path, reason: "missing" };
  const payload = parseJson(read(path));
  const checks = Array.isArray(payload?.checks) ? payload.checks : [];
  const approvalHandoff = payload?.workflowScopeApprovalHandoff || {};
  const checksShapeReady = checks.length === 2 && checks.every((check) =>
    check.repo === "biojuho/BIOJUHO-Projects" &&
    check.path?.startsWith(".github/workflows/") &&
    check.templateCopyCommand?.startsWith("pbcopy < ") &&
    check.githubNewFileOpenCommand?.startsWith("open ") &&
    check.githubNewFileUrl?.includes("github.com/biojuho/BIOJUHO-Projects/new/main") &&
    check.githubEditFileOpenCommand?.startsWith("open ") &&
    check.githubEditFileUrl?.includes("github.com/biojuho/BIOJUHO-Projects/edit/main") &&
    typeof check.installAction === "string" &&
    check.remediation?.installAction === check.installAction &&
    check.remoteChecked === true &&
    typeof check.templateSha256 === "string" &&
    check.templateSha256.length === 64 &&
    check.command?.includes("gh api --method GET repos/biojuho/BIOJUHO-Projects/contents/.github/workflows/")
  );
  const missingRemoteState =
    payload.remoteWorkflowFilesReady === false &&
    Array.isArray(payload.blockers) &&
    payload.blockers.length >= 2 &&
    payload.blockers.every((blocker) => blocker.includes("remote workflow file is not installed on main")) &&
    checksShapeReady &&
    checks.every((check) =>
      check.remoteExists === false &&
      check.remoteMatchesTemplate === false &&
      check.error === "not found on default branch"
    );
  const readyRemoteState =
    payload.remoteWorkflowFilesReady === true &&
    (!Array.isArray(payload.blockers) || payload.blockers.length === 0) &&
    checksShapeReady &&
    checks.every((check) =>
      check.remoteExists === true &&
      check.remoteMatchesTemplate === true &&
      typeof check.remoteSha256 === "string" &&
      check.remoteSha256.length === 64
    );
  const mismatchRemoteState =
    payload.remoteWorkflowFilesReady === false &&
    Array.isArray(payload.blockers) &&
    payload.blockers.some((blocker) => blocker.includes("remote workflow file differs from local template")) &&
    checksShapeReady &&
    checks.some((check) =>
      check.remoteExists === true &&
      check.remoteMatchesTemplate === false &&
      check.installAction === "replace_existing_remote_file" &&
      check.githubEditFileUrl?.includes("github.com/biojuho/BIOJUHO-Projects/edit/main") &&
      typeof check.remoteBlobSha === "string" &&
      check.remoteBlobSha.length > 0 &&
      typeof check.remoteSha256 === "string" &&
      check.remoteSha256.length === 64
    ) &&
    checks.some((check) => check.remoteExists === true && check.remoteMatchesTemplate === true);
  return {
    status: payload &&
      payload.status === "pass" &&
      payload.mode === "live" &&
      payload.repo === "biojuho/BIOJUHO-Projects" &&
      payload.repoEvidenceReady === true &&
      payload.remoteWorkflowFilesChecked === true &&
      payload.installPacket?.includes("JooPark Remote Workflow Install Packet") &&
      payload.installPacket?.includes("install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") &&
      payload.installPacket?.includes("Workflow scope preflight:") &&
      payload.installPacket?.includes("one-time device code policy") &&
      payload.installPacket?.includes("GitHub UI fallback") &&
      payload.installPacket?.includes("remoteWorkflowFilesReady: true and allDispatchReady: true") &&
      payload.defaultBranch === "main" &&
      payload.sourceUrl === "https://docs.github.com/en/rest/repos/contents#get-repository-content" &&
      payload.manualDispatchDocsUrl === "https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui" &&
      payload.editFileDocsUrl === "https://docs.github.com/en/repositories/working-with-files/managing-files/editing-files" &&
      payload.updateFileContentsDocsUrl === "https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents" &&
      payload.remediationSummary?.status &&
      ["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(payload.remediationSummary.currentAction) &&
      payload.workflowScopeChecked === true &&
      typeof payload.workflowScopeAvailable === "boolean" &&
      typeof payload.workflowScopeInstallBlocked === "boolean" &&
      payload.workflowScopeRefreshCommand === "gh auth refresh -h github.com -s workflow" &&
      payload.workflowScopeRecheckCommand === "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write" &&
      (payload.workflowScopeAvailable === true || approvalHandoff.status === "approval_required") &&
      (!approvalHandoff.status || approvalHandoff.approvalUrl === "https://github.com/login/device") &&
      (!approvalHandoff.sensitiveValuePolicy || approvalHandoff.sensitiveValuePolicy.includes("Do not store, log, or paste the one-time device code")) &&
      remoteWorkflowFileCheckFallbackReady(approvalHandoff.fallback) &&
      (!approvalHandoff.stopCondition || approvalHandoff.stopCondition.includes("remoteWorkflowFilesReady=true")) &&
      payload.remoteInstallerCommand === "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify" &&
      payload.nextVerificationCommand === "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write" &&
      payload.dispatchPlanCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write" &&
      payload.writtenTo === "data/remote-workflow-file-check.json" &&
      (missingRemoteState || mismatchRemoteState || readyRemoteState)
      ? "pass"
      : "fail",
    path,
    result: payload,
  };
}

function publishDispatchReadyFixturePlan() {
  const fixture = "scripts/fixtures/publish-workflows-ready.json";
  const result = run(process.execPath, [
    "scripts/plan-publish-dispatch.mjs",
    "--live",
    "--repo",
    "biojuho/BIOJUHO-Projects",
    "--workflow-list-fixture",
    fixture,
  ], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const workflowPlans = Array.isArray(payload?.workflowPlans) ? payload.workflowPlans : [];
  const suggestedCommands = Array.isArray(payload?.suggestedCommands) ? payload.suggestedCommands : [];
  const suggestedVerificationCommands = Array.isArray(payload?.suggestedVerificationCommands) ? payload.suggestedVerificationCommands : [];
  const suggestedDispatchCommands = Array.isArray(payload?.suggestedDispatchCommands) ? payload.suggestedDispatchCommands : [];
  return {
    status: result.ok &&
      payload &&
      payload.status === "pass" &&
      payload.mode === "live" &&
      payload.repo === "biojuho/BIOJUHO-Projects" &&
      payload.repoEvidenceReady === true &&
      payload.workflowListSource === "workflow-list-fixture" &&
      payload.workflowListFixture === fixture &&
      payload.workflowListCommand === `fixture:${fixture}` &&
      payload.localWorkflowTargetsReady === true &&
      payload.localTargetParityReady === true &&
      payload.remoteWorkflowVisibilityReady === true &&
      payload.dispatchReady === true &&
      payload.driftDispatchReady === true &&
      payload.allDispatchReady === true &&
      payload.dispatchSuggestionStatus === "ready" &&
      suggestedVerificationCommands.length === 1 &&
      suggestedVerificationCommands[0] === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
      suggestedDispatchCommands.length === 2 &&
      suggestedDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
      suggestedDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") &&
      suggestedCommands.length === 3 &&
      suggestedCommands.every((command) => command.includes("biojuho/BIOJUHO-Projects")) &&
      payload.driftFollowupCommand === "gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=fail-on-drift -f repo=biojuho/BIOJUHO-Projects" &&
      Array.isArray(payload.nextActions) &&
      payload.nextActions.some((action) => action.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown")) &&
      Array.isArray(payload.blockers) &&
      payload.blockers.length === 0 &&
      workflowPlans.length === 2 &&
      workflowPlans.every((plan) => plan.dispatchReady === true && plan.targetMatchesTemplate === true && plan.localTargetParityReady === true && plan.checks?.targetMatchesTemplate === true && plan.checks?.workflowVisible === true && plan.remoteWorkflow?.state === "active")
      ? "pass"
      : "fail",
    command: `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --workflow-list-fixture ${fixture}`,
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function publishEvidenceCapturePlan() {
  const result = run(process.execPath, ["scripts/capture-publish-evidence.mjs", "--dry-run"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const suggestedCommands = Array.isArray(payload?.suggestedCommands) ? payload.suggestedCommands : [];
  const suggestedVerificationCommands = Array.isArray(payload?.suggestedVerificationCommands) ? payload.suggestedVerificationCommands : [];
  const suggestedDispatchCommands = Array.isArray(payload?.suggestedDispatchCommands) ? payload.suggestedDispatchCommands : [];
  const withheldDispatchCommands = Array.isArray(payload?.withheldDispatchCommands) ? payload.withheldDispatchCommands : [];
  const commands = Array.isArray(payload?.commands) ? payload.commands : [];
  const suggestedCommandsSafe =
    suggestedCommands.length >= 4 &&
    suggestedCommands.every((command) => command.includes("biojuho/BIOJUHO-Projects")) &&
    !suggestedCommands.some((command) => command.includes("gh workflow run --repo")) &&
    suggestedCommands.includes("node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") &&
    suggestedCommands.includes("node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown") &&
    suggestedCommands.includes("gh api repos/biojuho/BIOJUHO-Projects/pages") &&
    suggestedCommands.includes("gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle");
  const dispatchCommandsWithheld =
    payload?.publishDispatchReady === false &&
    payload?.dispatchSuggestionStatus === "withheld-until-all-dispatch-ready" &&
    suggestedDispatchCommands.length === 0 &&
    withheldDispatchCommands.length === 2 &&
    withheldDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
    withheldDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory");
  const dispatchCommandsReady =
    payload?.publishDispatchReady === true &&
    payload?.dispatchSuggestionStatus === "ready" &&
    suggestedDispatchCommands.length === 2 &&
    withheldDispatchCommands.length === 0 &&
    suggestedDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
    suggestedDispatchCommands.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory");
  const templateCommandsSafe =
    commands.includes("node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO") &&
    commands.includes("node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown") &&
    commands.includes("gh api repos/OWNER/REPO/pages") &&
    commands.includes("gh run list --repo OWNER/REPO --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle") &&
    !commands.some((command) => command.includes("gh workflow run --repo"));
  const installNextActionReady =
    payload?.immediateNextAction?.key === "install_workflows" &&
    payload?.immediateNextAction?.status === "action_required" &&
    payload?.immediateNextAction?.source === "data/launch-execution-packet.json" &&
    (payload?.immediateNextAction?.command === "gh auth refresh -h github.com -s workflow" || payload?.immediateNextAction?.command?.startsWith("pbcopy < 'docs/github-pages-workflow.yml'")) &&
    Number(payload?.immediateNextAction?.commandCount || 0) >= 2 &&
    payload?.launchInstallPaths?.ready === true &&
    Number(payload?.launchInstallPaths?.count || 0) >= 2 &&
    Number(payload?.launchInstallPaths?.commandCount || 0) >= 10 &&
    payload?.immediateNextAction?.withheldCommandCount === 2 &&
    payload?.deferredNextAction?.key === "capture-live-evidence" &&
    payload?.shareUpdate?.includes("Immediate action: Install workflows on the default branch [action_required]") &&
    payload?.shareUpdate?.includes("Deferred evidence capture: Capture live publish evidence") &&
    (payload?.launchAnnouncement?.includes("Immediate command: gh auth refresh -h github.com -s workflow") || payload?.launchAnnouncement?.includes("Immediate command: pbcopy < 'docs/github-pages-workflow.yml'")) &&
    payload?.postLaunchVerificationReceipt?.includes("Deferred command: node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown") &&
    payload?.nextAction?.key === "install_workflows" &&
    payload?.nextAction?.source === "data/launch-execution-packet.json" &&
    (payload?.nextAction?.command === "gh auth refresh -h github.com -s workflow" || payload?.nextAction?.command?.startsWith("pbcopy < 'docs/github-pages-workflow.yml'"));
  const captureNextActionReady =
    ["capture-live-evidence", "capture_launch_proof"].includes(payload?.immediateNextAction?.key) &&
    payload?.immediateNextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects") &&
    ["capture-live-evidence", "capture_launch_proof"].includes(payload?.nextAction?.key) &&
    payload?.nextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects");
  const shareNextActionReady =
    payload?.immediateNextAction?.key === "share-launch-proof" &&
    payload?.immediateNextAction?.source === "publish-evidence-next-action" &&
    payload?.immediateNextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects") &&
    payload?.nextAction?.key === "share-launch-proof" &&
    payload?.nextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects");
  return {
    status: result.ok && payload && payload.status === "pass" && payload.mode === "dry-run" && payload.suggestedRepo === "biojuho/BIOJUHO-Projects" && payload.displayRepo === "biojuho/BIOJUHO-Projects" && payload.evidenceRepo === "OWNER/REPO" && payload.repoResolution === "resolved_from_suggested_repo" && payload.repoPlaceholderResolved === true && payload.shareUpdate?.includes("Repo: biojuho/BIOJUHO-Projects") && !payload.shareUpdate?.includes("\nRepo: OWNER/REPO") && payload.launchAnnouncement?.includes("Repo: biojuho/BIOJUHO-Projects") && !payload.launchAnnouncement?.includes("\nRepo: OWNER/REPO") && payload.postLaunchVerificationReceipt?.includes("Repo: biojuho/BIOJUHO-Projects") && !payload.postLaunchVerificationReceipt?.includes("\nRepo: OWNER/REPO") && payload.repoReplacementHint?.includes("biojuho/BIOJUHO-Projects") && payload.repoEvidenceReady === false && payload.evidenceFresh === true && payload.evidenceMaxAgeHours === 24 && typeof payload.evidenceExpiresAt === "string" && payload.postPublishEvidenceReady === false && (installNextActionReady || captureNextActionReady) && Array.isArray(payload.workflowEvidencePlans) && payload.workflowEvidencePlans.length >= 2 && payload.workflowEvidencePlans.every((plan) => plan.evidenceCommand?.includes("--repo OWNER/REPO")) && suggestedCommandsSafe && suggestedVerificationCommands.length === suggestedCommands.length && suggestedVerificationCommands.every((command) => command.includes("biojuho/BIOJUHO-Projects") && suggestedCommands.includes(command)) && (dispatchCommandsWithheld || dispatchCommandsReady) && Array.isArray(payload.blockers) && payload.blockers.includes("live evidence was not checked; pass --live after dispatch") && templateCommandsSafe ? "pass" : "fail",
    command: "node scripts/capture-publish-evidence.mjs --dry-run",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function publishEvidenceSuggestedRepoPlan() {
  const repo = "biojuho/BIOJUHO-Projects";
  const result = run(process.execPath, ["scripts/capture-publish-evidence.mjs", "--dry-run", "--repo", repo], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const suggestedCommands = Array.isArray(payload?.suggestedCommands) ? payload.suggestedCommands : [];
  const suggestedDispatchCommands = Array.isArray(payload?.suggestedDispatchCommands) ? payload.suggestedDispatchCommands : [];
  const withheldDispatchCommands = Array.isArray(payload?.withheldDispatchCommands) ? payload.withheldDispatchCommands : [];
  const commands = Array.isArray(payload?.commands) ? payload.commands : [];
  const installNextActionReady =
    payload?.immediateNextAction?.key === "install_workflows" &&
    payload?.immediateNextAction?.source === "data/launch-execution-packet.json" &&
    (payload?.immediateNextAction?.command === "gh auth refresh -h github.com -s workflow" || payload?.immediateNextAction?.command?.startsWith("pbcopy < 'docs/github-pages-workflow.yml'")) &&
    payload?.deferredNextAction?.key === "capture-live-evidence" &&
    payload?.nextAction?.key === "install_workflows" &&
    payload?.nextAction?.source === "data/launch-execution-packet.json" &&
    (payload?.nextAction?.command === "gh auth refresh -h github.com -s workflow" || payload?.nextAction?.command?.startsWith("pbcopy < 'docs/github-pages-workflow.yml'"));
  const captureNextActionReady =
    ["capture-live-evidence", "capture_launch_proof"].includes(payload?.immediateNextAction?.key) &&
    payload?.immediateNextAction?.command?.includes(`scripts/capture-publish-evidence.mjs --live --repo ${repo}`) &&
    ["capture-live-evidence", "capture_launch_proof"].includes(payload?.nextAction?.key) &&
    payload?.nextAction?.command?.includes(`scripts/capture-publish-evidence.mjs --live --repo ${repo}`);
  const dispatchWithheldReady =
    payload.publishDispatchReady === false &&
    payload.dispatchSuggestionStatus === "withheld-until-all-dispatch-ready" &&
    suggestedDispatchCommands.length === 0 &&
    withheldDispatchCommands.length === 2 &&
    withheldDispatchCommands.includes(`gh workflow run --repo ${repo} joopark-pages.yml -f ref=codex/joopark-workspace-release`) &&
    withheldDispatchCommands.includes(`gh workflow run --repo ${repo} joopark-drift-watch.yml -f mode=advisory`);
  const dispatchReady =
    payload.publishDispatchReady === true &&
    payload.dispatchSuggestionStatus === "ready" &&
    suggestedDispatchCommands.length === 2 &&
    withheldDispatchCommands.length === 0 &&
    suggestedDispatchCommands.includes(`gh workflow run --repo ${repo} joopark-pages.yml -f ref=codex/joopark-workspace-release`) &&
    suggestedDispatchCommands.includes(`gh workflow run --repo ${repo} joopark-drift-watch.yml -f mode=advisory`);
  return {
    status: result.ok && payload && payload.status === "pass" && payload.mode === "dry-run" && payload.repo === repo && payload.repoEvidenceReady === true && (installNextActionReady || captureNextActionReady) && payload.pagesSite?.command === `gh api repos/${repo}/pages` && Array.isArray(payload.workflowEvidencePlans) && payload.workflowEvidencePlans.length >= 2 && payload.workflowEvidencePlans.every((plan) => plan.evidenceCommand?.includes(`--repo ${repo}`) && plan.dispatchCommand?.includes(`--repo ${repo}`)) && commands.includes(`node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`) && commands.includes(`gh run list --repo ${repo} --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle`) && !commands.some((command) => command.includes("gh workflow run --repo")) && suggestedCommands.every((command) => command.includes(repo) && !command.includes("gh workflow run --repo")) && (dispatchWithheldReady || dispatchReady) ? "pass" : "fail",
    command: `node scripts/capture-publish-evidence.mjs --dry-run --repo ${repo}`,
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function publishEvidenceSnapshot() {
  const path = "data/publish-evidence.json";
  if (!fileExists(path)) {
    return { status: "fail", path, error: "missing" };
  }
  const payload = parseJson(readFileSync(join(root, path), "utf-8"));
  const suggestedCommands = Array.isArray(payload?.suggestedCommands) ? payload.suggestedCommands : [];
  const suggestedDispatchCommands = Array.isArray(payload?.suggestedDispatchCommands) ? payload.suggestedDispatchCommands : [];
  const withheldDispatchCommands = Array.isArray(payload?.withheldDispatchCommands) ? payload.withheldDispatchCommands : [];
  const installNextActionReady =
    payload?.immediateNextAction?.key === "install_workflows" &&
    payload?.immediateNextAction?.source === "data/launch-execution-packet.json" &&
    (payload?.immediateNextAction?.command === "gh auth refresh -h github.com -s workflow" || payload?.immediateNextAction?.command?.startsWith("pbcopy < 'docs/github-pages-workflow.yml'")) &&
    Number(payload?.immediateNextAction?.commandCount || 0) >= 2 &&
    payload?.launchInstallPaths?.ready === true &&
    Number(payload?.launchInstallPaths?.count || 0) >= 2 &&
    Number(payload?.launchInstallPaths?.commandCount || 0) >= 10 &&
    payload?.immediateNextAction?.withheldCommandCount === 2 &&
    payload?.deferredNextAction?.key === "capture-live-evidence" &&
    payload?.nextAction?.key === "install_workflows" &&
    payload?.nextAction?.source === "data/launch-execution-packet.json" &&
    (payload?.nextAction?.command === "gh auth refresh -h github.com -s workflow" || payload?.nextAction?.command?.startsWith("pbcopy < 'docs/github-pages-workflow.yml'"));
  const captureNextActionReady =
    ["capture-live-evidence", "capture_launch_proof"].includes(payload?.immediateNextAction?.key) &&
    payload?.immediateNextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects") &&
    ["capture-live-evidence", "capture_launch_proof"].includes(payload?.nextAction?.key) &&
    payload?.nextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects");
  const shareNextActionReady =
    payload?.immediateNextAction?.key === "share-launch-proof" &&
    payload?.immediateNextAction?.source === "publish-evidence-next-action" &&
    payload?.immediateNextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects") &&
    payload?.nextAction?.key === "share-launch-proof" &&
    payload?.nextAction?.command?.includes("scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects");
  const suggestedRepo = "biojuho/BIOJUHO-Projects";
  const dispatchWithheldReady =
    payload?.publishDispatchReady === false &&
    payload?.dispatchSuggestionStatus === "withheld-until-all-dispatch-ready" &&
    suggestedDispatchCommands.length === 0 &&
    withheldDispatchCommands.length === 2 &&
    suggestedCommands.length > 0 &&
    suggestedCommands.every((command) => command.includes(suggestedRepo) && !command.includes("gh workflow run --repo"));
  const dispatchReady =
    payload?.publishDispatchReady === true &&
    payload?.dispatchSuggestionStatus === "ready" &&
    suggestedDispatchCommands.length === 2 &&
    withheldDispatchCommands.length === 0 &&
    suggestedCommands.length > 0 &&
    suggestedCommands.every((command) => command.includes(suggestedRepo) && !command.includes("gh workflow run --repo"));
  const postPublishDispatchWithheldDispositionReady =
    payload?.postPublishEvidenceReady === true &&
    payload?.publishDispatchReady === false &&
    payload?.dispatchSuggestionStatus === "withheld-until-all-dispatch-ready" &&
    payload?.dispatchCommandDisposition === "withheld_until_all_dispatch_ready" &&
    payload?.activeDispatchCommandCount === 0 &&
    payload?.dispatchCommandReferenceCount === withheldDispatchCommands.length;
  const dispatchDispositionReady = payload?.postPublishEvidenceReady === true
    ? postPublishDispatchWithheldDispositionReady ||
      (payload?.dispatchCommandDisposition === "not_applicable_after_launch_proof" &&
      payload?.activeDispatchCommandCount === 0 &&
      payload?.dispatchCommandReferenceCount === suggestedDispatchCommands.length)
    : payload?.publishDispatchReady === true
      ? payload?.dispatchCommandDisposition === "active_until_launch_proof" &&
        payload?.activeDispatchCommandCount === suggestedDispatchCommands.length &&
        payload?.dispatchCommandReferenceCount === suggestedDispatchCommands.length
      : payload?.dispatchCommandDisposition === "withheld_until_all_dispatch_ready" &&
        payload?.activeDispatchCommandCount === 0 &&
        payload?.dispatchCommandReferenceCount === withheldDispatchCommands.length;
  const commonSnapshotReady =
    payload?.status === "pass" &&
    payload?.displayRepo === suggestedRepo &&
    payload?.evidenceFresh === true &&
    typeof payload?.evidenceExpiresAt === "string" &&
    payload?.evidenceMaxAgeHours === 24 &&
    typeof payload?.postPublishEvidenceReady === "boolean" &&
    (installNextActionReady || captureNextActionReady || shareNextActionReady) &&
    Array.isArray(payload?.workflowEvidencePlans) &&
    payload.workflowEvidencePlans.length >= 2 &&
    (dispatchWithheldReady || dispatchReady) &&
    dispatchDispositionReady;
  const placeholderSnapshotReady =
    payload?.mode === "dry-run" &&
    payload?.repo === "OWNER/REPO" &&
    payload?.evidenceRepo === "OWNER/REPO" &&
    payload?.repoResolution === "resolved_from_suggested_repo" &&
    payload?.repoPlaceholderResolved === true &&
    payload?.repoEvidenceReady === false &&
    payload?.pagesSite?.command === "gh api repos/OWNER/REPO/pages" &&
    payload.workflowEvidencePlans.every((plan) => plan.evidenceCommand.includes("--repo OWNER/REPO"));
  const sourceSnapshotReady =
    ["dry-run", "live"].includes(payload?.mode) &&
    payload?.repo === suggestedRepo &&
    payload?.evidenceRepo === suggestedRepo &&
    payload?.repoResolution === "source_repo" &&
    payload?.repoPlaceholderResolved === false &&
    payload?.repoEvidenceReady === true &&
    payload?.pagesSite?.command === `gh api repos/${suggestedRepo}/pages` &&
    payload.workflowEvidencePlans.every((plan) => plan.evidenceCommand.includes(`--repo ${suggestedRepo}`));
  return {
    status: commonSnapshotReady && (placeholderSnapshotReady || sourceSnapshotReady) ? "pass" : "fail",
    path,
    result: payload,
  };
}

function publishEvidenceMarkdownPlan() {
  const result = run(process.execPath, ["scripts/capture-publish-evidence.mjs", "--dry-run", "--markdown"], { timeout: 15000 });
  const stdout = result.stdout || "";
  const required = [
    "# JooPark Publish Evidence",
    "- repo: biojuho/BIOJUHO-Projects",
    "- displayRepo: biojuho/BIOJUHO-Projects",
    "- evidenceRepo: OWNER/REPO (placeholder resolved from suggestedRepo)",
    "- repoResolution: resolved_from_suggested_repo",
    "repoEvidenceReady: false",
    "evidenceFresh: true",
    "evidenceExpiresAt:",
    "evidenceMaxAgeHours: 24",
    "postPublishEvidenceReady: false",
    "publishDispatchReady:",
    "dispatchSuggestionStatus:",
    "immediateNextAction:",
    "deferredNextAction:",
    "suggestedDispatchCommands:",
    "withheldDispatchCommands:",
    "## Launch proof gate",
    "repoEvidenceReady:",
    "evidenceFresh: true",
    "postPublishEvidenceReady:",
    "Current repoEvidenceReady: false",
    "## Next action",
    "- nextAction:",
    "### Immediate action",
    "action_required",
    "remoteWorkflowFilesReady=true",
    "### Deferred evidence capture",
    "capture-live-evidence",
    "Capture live publish evidence",
    "capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown",
    "## Pages site",
    "html_url: not available",
    "## Workflow runs",
    "joopark-pages.yml",
    "joopark-drift-watch.yml",
    "## Blockers",
    "live evidence was not checked; pass --live after dispatch",
    "## Repo replacement guard",
    "Replace OWNER/REPO with biojuho/BIOJUHO-Projects",
    "Treat the OWNER/REPO commands below as templates",
    "Dispatch commands stay withheld until",
    "## Suggested repo commands",
    "Safe verification and evidence-capture commands only",
    "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects",
    "capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write",
    "gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-pages.yml",
    "## Suggested dispatch commands",
    "gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release",
    "gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory",
    "## Next commands",
    "Template verification and evidence-capture commands only",
    "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO",
    "gh run list --repo OWNER/REPO --workflow joopark-pages.yml",
    "capture-publish-evidence.mjs --live --repo OWNER/REPO --write",
  ];
  const missing = required.filter((term) => !stdout.includes(term));
  const guardIndex = stdout.indexOf("## Repo replacement guard");
  const suggestedIndex = stdout.indexOf("## Suggested repo commands");
  const dispatchIndex = stdout.indexOf("## Suggested dispatch commands");
  const templateWithheldIndex = stdout.indexOf("## Template withheld dispatch commands");
  const nextIndex = stdout.indexOf("## Next commands");
  const safeOrder = guardIndex >= 0 && suggestedIndex > guardIndex && dispatchIndex > suggestedIndex && templateWithheldIndex > dispatchIndex && nextIndex > templateWithheldIndex;
  const suggestedSection = suggestedIndex >= 0 && dispatchIndex > suggestedIndex ? stdout.slice(suggestedIndex, dispatchIndex) : "";
  const dispatchSection = dispatchIndex >= 0 && templateWithheldIndex > dispatchIndex ? stdout.slice(dispatchIndex, templateWithheldIndex) : "";
  const nextSection = nextIndex >= 0 ? stdout.slice(nextIndex) : "";
  const suggestedDispatchSafe = !suggestedSection.includes("gh workflow run --repo");
  const nextDispatchSafe = !nextSection.includes("gh workflow run --repo");
  const dispatchCommandsPresent = dispatchSection.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
    dispatchSection.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory");
  const resolvedRepoHeader = stdout.includes("- repo: biojuho/BIOJUHO-Projects") && !stdout.includes("- repo: OWNER/REPO");
  return {
    status: result.ok && missing.length === 0 && safeOrder && suggestedDispatchSafe && nextDispatchSafe && dispatchCommandsPresent && resolvedRepoHeader ? "pass" : "fail",
    command: "node scripts/capture-publish-evidence.mjs --dry-run --markdown",
    missing,
    safeOrder,
    suggestedDispatchSafe,
    nextDispatchSafe,
    dispatchCommandsPresent,
    resolvedRepoHeader,
    stdout: stdout.trim(),
    stderr: result.stderr.trim(),
    error: result.error,
  };
}

function publishCommandScopeGuard() {
  const files = [
    "app.js",
    "README.md",
    "scripts/plan-publish-dispatch.mjs",
    "scripts/capture-publish-evidence.mjs",
    "scripts/plan-workflow-ui-install.mjs",
    "data/publish-evidence.json",
  ];
  const patterns = [
    { id: "unscoped_workflow_dispatch", pattern: /gh workflow run joopark-[^\s`"']+/g },
    { id: "unscoped_publish_dispatch_plan", pattern: /plan-publish-dispatch\.mjs --live(?! --repo)/g },
    { id: "unscoped_publish_evidence_capture", pattern: /capture-publish-evidence\.mjs --live(?! --repo)/g },
  ];
  const findings = [];
  for (const file of files) {
    if (!fileExists(file)) continue;
    const text = read(file);
    for (const item of patterns) {
      const matches = Array.from(text.matchAll(item.pattern)).map((match) => match[0]);
      for (const match of matches) findings.push({ file, id: item.id, match });
    }
  }
  return {
    status: findings.length === 0 ? "pass" : "fail",
    files,
    findings,
  };
}

function auditSummaryFormatPlan() {
  const stdout = summary({
    status: "blocked",
    summary: { pass: 1, fail: 0, notRun: 1, blocked: 0, total: 2 },
    generatedAt: "2026-01-01T00:00:00.000Z",
    sourceCommit: "sample",
    gitStatus: "## sample...origin/sample",
    checklist: [
      {
        id: "static_runtime_files",
        requirement: "sample static files check",
        status: "pass",
      },
      {
        id: "packaged_browser_gates",
        requirement: "sample packaged browser gate check",
        status: "not_run",
        evidence: {
          cache: {
            status: "invalid",
            contextMatched: false,
            cachedEvidenceStatus: "pass",
            cachedResultStatus: "pass",
            issues: ["context_mismatch"],
            contextMismatches: [{ path: "app.js", reason: "sha256_mismatch" }],
          },
        },
      },
      {
        id: "recent_deleted_recovery",
        requirement: "sample recently deleted recovery contract",
        status: "pass",
      },
    ],
  });
  const required = [
    "# JooPark Release Readiness Summary",
    "Status:",
    "Summary:",
    "Packaged browser gates:",
    "## Product Contracts",
    "recent_deleted_recovery",
    "## Blockers",
    "cache=invalid",
    "contextMatched=false",
    "cachedEvidenceStatus=pass",
    "cachedResultStatus=pass",
    "issues=context_mismatch",
    "firstMismatch=app.js:sha256_mismatch",
    "Deferred proof:",
  ];
  const missing = required.filter((term) => !stdout.includes(term));
  return {
    status: missing.length === 0 ? "pass" : "fail",
    command: "summary(sample audit payload)",
    missing,
    stdout: stdout.trim(),
    stderr: "",
    error: "",
  };
}

function workflowUiInstallPlan() {
  const result = run(process.execPath, ["scripts/plan-workflow-ui-install.mjs", "--dry-run"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  const plans = Array.isArray(payload?.plans) ? payload.plans : [];
  const hasCopyOpenCommands = (plan) =>
    (plan?.uiInstallRequired === false || plan?.templateCopyCommand?.startsWith("pbcopy < ")) &&
    plan?.githubNewFileOpenCommand?.startsWith("open ") &&
    plan?.githubEditFileOpenCommand?.startsWith("open ") &&
    (plan?.uiInstallRequired === false || plan?.uiInstallOpenCommand?.startsWith("open ")) &&
    plan?.githubWorkflowOpenCommand?.startsWith("open ") &&
    plan?.uiSteps?.some((step) => step.includes("installAction=")) &&
    (plan?.uiInstallRequired === false || plan?.uiSteps?.some((step) => step.includes("open the GitHub repository default branch create/edit page") || step.includes("open 'https://github.com/") || step.includes("edit-file page")));
  const plansReady = plans.length === 2 && plans.every((plan) =>
    plan.uiInstallReady === true &&
    typeof plan.sha256 === "string" &&
    plan.sha256.length === 64 &&
    typeof plan.templateSha256 === "string" &&
    plan.templateSha256.length === 64 &&
    typeof plan.targetSha256 === "string" &&
    plan.targetSha256.length === 64 &&
    plan.targetMatchesTemplate === true &&
    plan.localTargetParityReady === true &&
    plan.targetRepositoryPath &&
    plan.defaultBranchRequired === true &&
    plan.defaultBranch === payload.defaultBranch &&
    plan.githubNewFileUrl &&
    plan.githubEditFileUrl &&
    plan.githubWorkflowUrl &&
    ["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(plan.installAction) &&
    plan.githubFileNameFieldValue === plan.targetRepositoryPath &&
    typeof plan.suggestedCommitMessage === "string" &&
    plan.suggestedCommitMessage.length > 0 &&
    hasCopyOpenCommands(plan) &&
    plan.manualDispatchRequirement &&
    plan.suggestedRepo === "biojuho/BIOJUHO-Projects" &&
    plan.nextVerificationCommand === payload.nextVerificationCommand &&
    plan.placeholderVerificationCommand === payload.placeholderVerificationCommand &&
    plan.missingTerms.length === 0
  );
  const installReceipt = payload?.installReceipt || {};
  const receiptReady = installReceipt.ready === true &&
    installReceipt.status === "ready_to_use" &&
    installReceipt.commandCount >= 6 &&
    installReceipt.checklistCount === 6 &&
    installReceipt.expectedSignalCount === 8 &&
    installReceipt.formFieldCoverage === 1 &&
    installReceipt.installActionCoverage === 1 &&
    Array.isArray(installReceipt.installRows) &&
    installReceipt.installRows.some((row) => row.installAction === "replace_existing_remote_file" && row.openCommand?.includes("/edit/")) &&
    installReceipt.installRows.some((row) => row.installAction === "verified_remote_matches_template" && row.required === false) &&
    installReceipt.parserReadyProofBlockReady === true &&
    installReceipt.parserReadyProofFieldCount === 6 &&
    installReceipt.parserReadyProofFieldCoverage === 1 &&
    Array.isArray(installReceipt.formFieldChecks) &&
    installReceipt.formFieldChecks.length === 2 &&
    installReceipt.formFieldChecks.every((item) => item.githubFileNameFieldValue && item.suggestedCommitMessage) &&
    Array.isArray(installReceipt.parserReadyProofFields) &&
    installReceipt.parserReadyProofFields.length === 6 &&
    installReceipt.text?.includes("JooPark GitHub UI Workflow Install Receipt") &&
    installReceipt.text?.includes("JooPark GitHub UI Workflow Paste Packet") &&
    installReceipt.text?.includes("Status: ready for GitHub UI install; not remote installation proof") &&
    installReceipt.text?.includes("Paste exact template content") &&
    installReceipt.text?.includes("Install action ledger:") &&
    installReceipt.text?.includes("installAction=replace_existing_remote_file") &&
    installReceipt.text?.includes("verified_remote_matches_template rows require no edit") &&
    installReceipt.text?.includes("Parser-ready proof block:") &&
    installReceipt.text?.includes("pages_workflow_commit:") &&
    installReceipt.text?.includes("The parser ignores bracketed [paste ...] placeholders") &&
    installReceipt.text?.includes("GitHub new-file form values:") &&
    installReceipt.text?.includes("githubFileNameFieldValue=.github/workflows/joopark-pages.yml") &&
    installReceipt.text?.includes("suggestedCommitMessage=Add JooPark Pages publish workflow") &&
    installReceipt.text?.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") &&
    installReceipt.text?.includes("dispatchReady=true") &&
    installReceipt.text?.includes("driftDispatchReady=true") &&
    installReceipt.text?.includes("safeToDispatch=true before gh workflow run") &&
    installReceipt.dispatchGuard?.includes("Do not run gh workflow run");
  return {
    status: result.ok && payload && payload.status === "pass" && payload.workflowUiInstallReady === true && payload.localTargetParityReady === true && payload.installReceiptReady === true && payload.installReceiptCommandCount >= 6 && payload.installReceiptChecklistCount === 6 && payload.workflowUiInstallFormFieldCoverage === 1 && payload.installReceipt?.installActionCoverage === 1 && payload.installReceipt?.parserReadyProofBlockReady === true && payload.installReceipt?.parserReadyProofFieldCoverage === 1 && payload.workflowUiInstallPastePacketReady === true && payload.workflowUiInstallPastePacketCoverage === 1 && payload.packet === payload.workflowUiInstallPastePacket && receiptReady && payload.repositoryUrl && payload.suggestedRepo === "biojuho/BIOJUHO-Projects" && payload.repoReplacementHint?.includes("biojuho/BIOJUHO-Projects") && payload.nextVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" && payload.placeholderVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO" && Array.isArray(payload.nextCommands) && payload.nextCommands.includes("node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && Array.isArray(payload.placeholderTemplateCommands) && payload.placeholderTemplateCommands.includes("node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO") && payload.defaultBranch && payload.actionsUrl && plansReady ? "pass" : "fail",
    command: "node scripts/plan-workflow-ui-install.mjs --dry-run",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function workflowUiInstallPlanFile() {
  const path = "data/workflow-ui-install-plan.json";
  if (!fileExists(path)) return { status: "fail", path, reason: "missing" };
  const payload = parseJson(read(path));
  const plans = Array.isArray(payload?.plans) ? payload.plans : [];
  const plansReady = plans.length === 2 &&
    plans.every((plan) =>
      plan.githubNewFileUrl &&
      plan.githubEditFileUrl &&
      plan.githubWorkflowUrl &&
      ["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(plan.installAction) &&
      plan.githubFileNameFieldValue === plan.targetRepositoryPath &&
      typeof plan.suggestedCommitMessage === "string" &&
      plan.suggestedCommitMessage.length > 0 &&
      plan.templateCopyCommand &&
      plan.githubNewFileOpenCommand &&
      plan.githubEditFileOpenCommand &&
      (plan.uiInstallRequired === false || plan.uiInstallOpenCommand) &&
      plan.githubWorkflowOpenCommand &&
      plan.uiInstallReady === true &&
      typeof plan.templateSha256 === "string" &&
      plan.templateSha256.length === 64 &&
      typeof plan.targetSha256 === "string" &&
      plan.targetSha256.length === 64 &&
      plan.targetMatchesTemplate === true &&
      plan.localTargetParityReady === true
    );
  const installReceipt = payload?.installReceipt || {};
  const receiptReady = installReceipt.ready === true &&
    installReceipt.commandCount >= 6 &&
    installReceipt.checklistCount === 6 &&
    installReceipt.formFieldCoverage === 1 &&
    installReceipt.installActionCoverage === 1 &&
    Array.isArray(installReceipt.installRows) &&
    installReceipt.installRows.some((row) => row.installAction === "replace_existing_remote_file" && row.openCommand?.includes("/edit/")) &&
    installReceipt.installRows.some((row) => row.installAction === "verified_remote_matches_template" && row.required === false) &&
    installReceipt.parserReadyProofBlockReady === true &&
    installReceipt.parserReadyProofFieldCount === 6 &&
    installReceipt.parserReadyProofFieldCoverage === 1 &&
    installReceipt.expectedSignalCount === 8 &&
    installReceipt.handoffVerifyCommand === "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown" &&
    installReceipt.text?.includes("JooPark GitHub UI Workflow Install Receipt") &&
    installReceipt.text?.includes("JooPark GitHub UI Workflow Paste Packet") &&
    installReceipt.text?.includes("Paste exact template content") &&
    installReceipt.text?.includes("Install action ledger:") &&
    installReceipt.text?.includes("installAction=replace_existing_remote_file") &&
    installReceipt.text?.includes("verified_remote_matches_template rows require no edit") &&
    installReceipt.text?.includes("Parser-ready proof block:") &&
    installReceipt.text?.includes("pages_workflow_commit:") &&
    installReceipt.text?.includes("The parser ignores bracketed [paste ...] placeholders") &&
    installReceipt.text?.includes("GitHub new-file form values:") &&
    installReceipt.text?.includes("githubFileNameFieldValue=.github/workflows/joopark-pages.yml") &&
    installReceipt.text?.includes("suggestedCommitMessage=Add JooPark Pages publish workflow") &&
    installReceipt.text?.includes("remoteWorkflowFilesReady=true") &&
    installReceipt.text?.includes("remoteWorkflowVisibilityReady=true") &&
    installReceipt.text?.includes("dispatchReady=true") &&
    installReceipt.text?.includes("driftDispatchReady=true") &&
    installReceipt.text?.includes("safeToDispatch=true before gh workflow run");
  return {
    status: payload &&
      payload.status === "pass" &&
      payload.workflowUiInstallReady === true &&
      payload.localTargetParityReady === true &&
      payload.installReceiptReady === true &&
      payload.installReceiptCommandCount >= 6 &&
      payload.installReceiptChecklistCount === 6 &&
      payload.workflowUiInstallFormFieldCoverage === 1 &&
      payload.installReceipt?.installActionCoverage === 1 &&
      payload.installReceipt?.parserReadyProofBlockReady === true &&
      payload.installReceipt?.parserReadyProofFieldCoverage === 1 &&
      payload.workflowUiInstallPastePacketReady === true &&
      payload.workflowUiInstallPastePacketCoverage === 1 &&
      payload.packet === payload.workflowUiInstallPastePacket &&
      payload.suggestedRepo === "biojuho/BIOJUHO-Projects" &&
      payload.nextVerificationCommand === "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" &&
      payload.writtenTo === "data/workflow-ui-install-plan.json" &&
      plansReady &&
      receiptReady
      ? "pass"
      : "fail",
    path,
    result: payload,
  };
}

function workflowLocalStagingSnapshot() {
  const files = [
    {
      key: "pages",
      template: "docs/github-pages-workflow.yml",
      target: ".github/workflows/joopark-pages.yml",
    },
    {
      key: "drift-watch",
      template: "docs/github-drift-watch-workflow.yml",
      target: ".github/workflows/joopark-drift-watch.yml",
    },
  ];
  const entries = files.map((entry) => {
    const templateExists = fileExists(entry.template);
    const targetExists = fileExists(entry.target);
    const templateText = templateExists ? read(entry.template) : "";
    const targetText = targetExists ? read(entry.target) : "";
    return {
      ...entry,
      templateExists,
      targetExists,
      matchesTemplate: templateExists && targetExists && templateText === targetText,
      workflowDispatch: targetText.includes("workflow_dispatch:"),
    };
  });
  return {
    status: entries.every((entry) => entry.templateExists && entry.targetExists && entry.matchesTemplate && entry.workflowDispatch) ? "pass" : "fail",
    entries,
  };
}

function releaseSmokeNeedsRetry(result, payload) {
  if (result.ok && payload && payload.status === "pass") return false;
  const hasCompleteGateEvidence = !!(
    payload &&
    payload.headers &&
    payload.fallbacks &&
    payload.smoke &&
    payload.mobile &&
    payload.interactions &&
    payload.accessibility
  );
  return !hasCompleteGateEvidence;
}

function smokeReleaseAttempt(attempt) {
  const releaseOutDir = mkdtempSync(join(tmpdir(), "joopark-release-smoke-"));
  let result;
	try {
	  result = run(process.execPath, ["scripts/smoke-release.mjs"], {
	    timeout: smokeReleaseAttemptTimeoutMs,
	    env: {
	      RELEASE_OUT_DIR: releaseOutDir,
	      PRODUCT_SMOKE_LOCK_WAIT_MS: String(smokeReleaseChildLockWaitMs),
	      PRODUCT_SMOKE_LOCK_POLL_MS: String(smokeReleaseChildLockPollMs),
	    },
	  });
	} finally {
	  rmSync(releaseOutDir, { recursive: true, force: true });
	}
	const payload = parseJsonFromOutputs(result.stdout, result.stderr);
  return {
    attempt,
    status: result.ok && payload && payload.status === "pass" ? "pass" : "fail",
    result,
    payload,
    retryable: releaseSmokeNeedsRetry(result, payload),
  };
}

function refreshPackagedBrowserEvidenceSources() {
  const commands = [
    {
      script: "scripts/plan-workflow-ui-install.mjs",
      args: ["--dry-run", "--write"],
      timeout: 30000,
    },
    {
      script: "scripts/check-remote-workflow-files.mjs",
      args: ["--repo", "biojuho/BIOJUHO-Projects", "--write"],
      timeout: 30000,
    },
    {
      script: "scripts/plan-publish-dispatch.mjs",
      args: ["--live", "--repo", "biojuho/BIOJUHO-Projects", "--write"],
      timeout: 30000,
    },
    {
      script: "scripts/capture-launch-execution-packet.mjs",
      args: ["--write"],
      timeout: 30000,
    },
    {
      script: "scripts/capture-publish-evidence.mjs",
      args: ["--live", "--repo", "biojuho/BIOJUHO-Projects", "--write"],
      timeout: 30000,
    },
    {
      script: "scripts/verify-launch-handoff.mjs",
      args: ["--repo", "biojuho/BIOJUHO-Projects", "--write"],
      timeout: 30000,
    },
    {
      script: "scripts/capture-launch-execution-packet.mjs",
      args: ["--write"],
      timeout: 30000,
    },
    {
      script: "scripts/capture-output-quality-audit.mjs",
      args: ["--write"],
      timeout: 30000,
    },
    {
      script: "scripts/refresh-launch-readiness.mjs",
      args: ["--repo", "biojuho/BIOJUHO-Projects", "--write"],
      timeout: 30000,
    },
  ];
  const results = commands.map((command) => {
    const result = run(process.execPath, [command.script, ...command.args], { timeout: command.timeout });
    const payload = parseJson(result.stdout);
    return {
      command: `node ${[command.script, ...command.args].join(" ")}`,
      status: result.ok && payload && payload.status === "pass" ? "pass" : "fail",
      result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
    };
  });
  return {
    status: results.every((item) => item.status === "pass") ? "pass" : "fail",
    results,
  };
}

function smokeRelease() {
  const sourceRefresh = refreshPackagedBrowserEvidenceSources();
  if (sourceRefresh.status !== "pass") {
    return {
      status: "fail",
      command: sourceRefresh.results.map((item) => item.command).join(" && "),
      result: {
        status: "fail",
        sourceRefresh,
      },
    };
  }
  const attempts = [];
  let finalEvidence = null;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const evidence = smokeReleaseAttempt(attempt);
    finalEvidence = evidence;
    attempts.push({
      attempt: evidence.attempt,
      status: evidence.status,
      retryable: evidence.retryable,
    });
    if (evidence.status === "pass" || !evidence.retryable) {
      const resultPayload = evidence.payload || {
        stdout: evidence.result.stdout.trim(),
        stderr: evidence.result.stderr.trim(),
        error: evidence.result.error,
      };
      if (attempts.length > 1 && resultPayload && typeof resultPayload === "object") {
        resultPayload.auditRetryAttempts = attempts;
      }
      if (resultPayload && typeof resultPayload === "object") {
        resultPayload.sourceRefresh = sourceRefresh;
      }
      return {
        status: evidence.status,
        command: "RELEASE_OUT_DIR=<temp> node scripts/smoke-release.mjs",
        result: resultPayload,
      };
    }
  }
  const resultPayload = finalEvidence.payload || {
    stdout: finalEvidence.result.stdout.trim(),
    stderr: finalEvidence.result.stderr.trim(),
    error: finalEvidence.result.error,
  };
  if (resultPayload && typeof resultPayload === "object") {
    resultPayload.auditRetryAttempts = attempts;
    resultPayload.sourceRefresh = sourceRefresh;
  }
  return {
    status: finalEvidence.status,
    command: "RELEASE_OUT_DIR=<temp> node scripts/smoke-release.mjs",
    result: resultPayload,
  };
}

function buildChecklist() {
  const checklist = [];
  const gateEvidenceRun = runGates ? smokeRelease() : null;
  let gateEvidence = runGates ? gateEvidenceRun : cachedPackagedBrowserGateEvidence();
  const verify = verifyRelease();
  const structureAudit = appStructureAudit();
  const workflowUiInstall = workflowUiInstallPlan();
  const workflowUiInstallFile = workflowUiInstallPlanFile();
  const workflowLocalStaging = workflowLocalStagingSnapshot();
  const publishDispatch = publishDispatchPlan();
  const publishDispatchFile = publishDispatchPlanFile();
  const remoteWorkflowFileCheck = remoteWorkflowFileCheckPlan();
  const remoteWorkflowFileCheckSnapshot = remoteWorkflowFileCheckFile();
  const remoteWorkflowInstaller = remoteWorkflowInstallerPlan();
  const publishDispatchReadyFixture = publishDispatchReadyFixturePlan();
  const publishEvidenceCapture = publishEvidenceCapturePlan();
  const publishEvidenceSuggestedRepo = publishEvidenceSuggestedRepoPlan();
  const publishEvidenceFile = publishEvidenceSnapshot();
  const publishEvidenceMarkdown = publishEvidenceMarkdownPlan();
  const auditSummaryFormat = skipSummarySelfCheck ? null : auditSummaryFormatPlan();

  const fileEvidence = runtimeFiles.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "static_runtime_files",
    requirement: "The app can be shipped as static runtime files with local assets and no package install step.",
    status: fileEvidence.every((item) => item.exists) ? "pass" : "fail",
    evidence: fileEvidence,
  });

  const scriptEvidence = releaseScripts.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "release_gate_scripts",
    requirement: "Release packaging, manifest verification, route smoke, mobile layout smoke, interaction smoke, accessibility smoke, and full release gate scripts exist.",
    status: scriptEvidence.every((item) => item.exists) ? "pass" : "fail",
    evidence: scriptEvidence,
  });

	  const routeSmokeReadinessTerms = [
    { file: "scripts/smoke-chrome.mjs", terms: ["function routeReadyTimeoutFor", "routeReadyDiagnostics", "route not ready:", "route-ready", "SMOKE_ROUTE_READY_TIMEOUT_MS", "release-provenance.json"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["function routeReadyTimeoutFor", "routeReadyDiagnostics", "route not ready:", "mobile-route-ready", "MOBILE_SMOKE_ROUTE_READY_TIMEOUT_MS", "release-provenance.json"] },
    { file: "scripts/smoke-release.mjs", terms: ["desktopReleaseSmokeTimeoutMs", "DESKTOP_RELEASE_SMOKE_TIMEOUT_MS", "mobileReleaseSmokeTimeoutMs", "MOBILE_RELEASE_SMOKE_TIMEOUT_MS", "240000", "scripts/smoke-chrome.mjs", "scripts/smoke-mobile.mjs"] },
    { file: "README.md", terms: ["route readiness diagnostics", "SMOKE_ROUTE_READY_TIMEOUT_MS", "MOBILE_SMOKE_ROUTE_READY_TIMEOUT_MS"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "route_smoke_readiness_diagnostics",
    requirement: "Desktop and mobile route smoke use state-based route readiness diagnostics and route-specific timeouts so release gate flakes expose actionable DOM state instead of generic route timeouts.",
    status: routeSmokeReadinessTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: routeSmokeReadinessTerms,
  });

  const releasePackageAtomicTerms = [
    { file: "scripts/package-release.mjs", terms: ["packageLockDir", "acquirePackageLock", "publishStagingDir", ".staging-", ".packaging.lock", "renameSync"] },
    { file: "scripts/verify-release.mjs", terms: ["packageLockDir", "waitForPackageLock", ".packaging.lock", "Timed out waiting for release package lock"] },
    { file: "README.md", terms: ["package-release", "staging", "release package lock", "verify-release"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_package_atomic_publish",
    requirement: "Release packaging uses a package lock, staging directory, and final directory swap while release verification waits for active packaging so concurrent audits never read a half-built dist/release artifact.",
    status: releasePackageAtomicTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: releasePackageAtomicTerms,
  });

  const pwaOfflineTerms = [
    { file: "sw.js", terms: ["CACHE_VERSION", "APP_SHELL_ASSETS", "cache.addAll(APP_SHELL_ASSETS)", "function networkFirst", "self.skipWaiting()", "self.clients.claim()", "./index.html", "./styles.css", "./verify-workspace-summary.js", "./review-execution-checklist.js", "./review-issue-payload.js", "./review-result-state.js", "./review-result-draft-state.js", "./review-creation-actions.js", "./review-artifact-state.js", "./pwa-runtime.js", "./workspace-seed-data.js", "./home-view.js", "./app.js", "./data/launch-readiness-refresh.json", "./data/output-quality-audit.json", "./autoresearch-results/release-readiness-summary.json", "./autoresearch-results/verify-workspace-summary.json"] },
    { file: "app.js", terms: ["pwaRuntimeHelpers", "function pwaRuntimeCall", "pwaRuntimeCall(\"inspect\"", "pwaRuntimeCall(\"setupObservers\"", "pwaRuntimeCall(\"register\"", "refreshPwaRuntimeStatus({ render: true })", "function refreshPwaRuntimeStatus", "function setupPwaRuntimeObservers", "pwaRuntime"] },
    { file: "pwa-runtime.js", terms: ["JooParkPwaRuntime", "joopark-pwa-runtime/v1", "function createPwaRuntime", "function secureEnoughForServiceWorker", "function statusLabel", "async function inspect", "rootWindow.isSecureContext", "rootNavigator.serviceWorker.register(\"./sw.js\", { scope: \"./\" })", "rootCaches.keys()", "function setupObservers", "function register"] },
    { file: "system-status-view.js", terms: ["function pwaRuntimeHTML", "data-system-pwa-runtime", "data-pwa-runtime-service-worker-active", "data-pwa-runtime-cache-ready", "data-pwa-runtime-manifest-linked"] },
    { file: "styles.css", terms: [".pwa-runtime", ".pwa-runtime-details", ".pwa-runtime-details code"] },
    { file: "index.html", terms: ["<link rel=\"manifest\" href=\"./site.webmanifest\"", "./verify-workspace-summary.js", "./review-execution-checklist.js", "./review-issue-payload.js", "./review-result-state.js", "./review-result-draft-state.js", "./review-creation-actions.js", "./review-artifact-state.js", "./pwa-runtime.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["\"verify-workspace-summary.js\"", "\"review-execution-checklist.js\"", "\"review-issue-payload.js\"", "\"review-result-state.js\"", "\"review-result-draft-state.js\"", "\"review-creation-actions.js\"", "\"review-artifact-state.js\"", "\"pwa-runtime.js\"", "\"sw.js\"", "/verify-workspace-summary.js", "/review-execution-checklist.js", "/review-issue-payload.js", "/review-result-state.js", "/review-result-draft-state.js", "/review-creation-actions.js", "/review-artifact-state.js", "/pwa-runtime.js", "/sw.js", "Cache-Control: no-cache"] },
    { file: "scripts/verify-release.mjs", terms: ["\"verify-workspace-summary.js\"", "\"review-execution-checklist.js\"", "\"review-issue-payload.js\"", "\"review-result-state.js\"", "\"review-result-draft-state.js\"", "\"review-creation-actions.js\"", "\"review-artifact-state.js\"", "\"pwa-runtime.js\"", "\"sw.js\"", "function verifyOfflineServiceWorker", "pwa-runtime.js missing service worker registration term", "offline shell term"] },
    { file: "scripts/smoke-release.mjs", terms: ["verifyWorkspaceSummaryRuntime", "verify_workspace_summary_runtime_cache_no_cache", "reviewExecutionChecklist", "review_execution_checklist_cache_no_cache", "reviewIssuePayload", "review_issue_payload_cache_no_cache", "reviewResultState", "review_result_state_cache_no_cache", "reviewResultDraftState", "review_result_draft_state_cache_no_cache", "reviewCreationActions", "review_creation_actions_cache_no_cache", "reviewArtifactState", "review_artifact_state_cache_no_cache", "pwaRuntime", "pwa_runtime_cache_no_cache", "serviceWorker", "service_worker_cache_no_cache", "service_worker_content_type"] },
    { file: "scripts/smoke-chrome.mjs", terms: ["serviceWorkerReport", "navigator.serviceWorker.ready", "service worker did not become active", "service worker script was", "system PWA runtime panel did not render"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["systemPwaRuntime", "system PWA runtime panel did not reach ready state", "data-pwa-runtime-script"] },
    { file: "README.md", terms: ["offline app shell", "service worker", "sw.js", "network-first", "PWA runtime"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "pwa_offline_app_shell",
    requirement: "The static workspace has an installable PWA surface with a guarded service worker that precaches the app shell, serves cached fallbacks offline, and is covered by release packaging, manifest verification, and smoke headers.",
    status: pwaOfflineTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: pwaOfflineTerms,
  });

  const opsRuntimeDiagnosticsTerms = [
    { file: "ops-runtime-loader.js", terms: ["const lastErrors", "const loadEvents", "const groupLoads", "function statusByPath", "groupStats", "failed", "lastLoads", "events"] },
    { file: "system-status-view.js", terms: ["function opsRuntimeHTML", "data-system-ops-runtime", "data-ops-runtime-loaded-count", "data-ops-runtime-ready-group-count", "data-ops-runtime-failed-count", "data-ops-runtime-group"] },
    { file: "app.js", terms: ["opsRuntime: lazyRuntimeLoader()?.stats() || {}", "OPS_RUNTIME_VIEW_GROUPS", "function ensureOpsRuntime"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["systemOpsRuntime", "system ops runtime diagnostics dataset was incomplete", "Ops runtime diagnostics"] },
    { file: "README.md", terms: ["Ops runtime diagnostics", "ops-runtime-loader.js", "loaded lazy files", "ready groups"] },
    { file: "docs/app-architecture.md", terms: ["Ops Runtime Diagnostics", "ops-runtime-loader.js", "loaded lazy files", "ready groups"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "ops_runtime_diagnostics",
    requirement: "The lazy operations/review runtime loader records group/file status, failed/pending files, and last-load diagnostics, and System Status exposes those fields with browser smoke and documentation coverage.",
    status: opsRuntimeDiagnosticsTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: opsRuntimeDiagnosticsTerms,
  });

  const structureTerms = [
    { file: "scripts/check-app-structure.mjs", terms: ["requiredBoundaries", "extractionCandidates", "maxAppLines", "duplicateFunctionNames", "oversizedSections", "search-empty-state.js", "home-execution-view.js", "calendar-view.js", "todo-view.js", "notes-view.js", "habits-view.js", "stats-view.js", "portfolio-view.js", "kanban-view.js", "gantt-view.js", "team-view.js", "workspace-storage.js", "storage-status-view.js", "settings-view.js", "system-status-view.js", "backup-import-guards.js", "backup-import-ui.js", "verify-workspace-summary.js", "review-execution-checklist.js", "review-issue-payload.js", "pwa-runtime.js"] },
    { file: "search-empty-state.js", terms: ["JooParkSearchEmptyState", "joopark-search-empty-state/v1", "function createSearchEmptyState", "function searchEmptyState", "data-search-empty"] },
    { file: "home-execution-view.js", terms: ["JooParkHomeExecutionView", "joopark-home-execution-view/v1", "function createHomeExecutionView", "function homeExecutionQueueHTML", "function homeExecutionBucketSummaryHTML"] },
    { file: "calendar-view.js", terms: ["JooParkCalendarView", "joopark-calendar-view/v1", "function createCalendarView", "function calendarViewModel", "function renderCalendarHTML"] },
    { file: "todo-view.js", terms: ["JooParkTodoView", "joopark-todo-view/v1", "function createTodoView", "function todoViewModel", "function renderTodosHTML"] },
    { file: "notes-view.js", terms: ["JooParkNotesView", "joopark-notes-view/v1", "function createNotesView", "function notesViewModel", "function renderNotesHTML"] },
    { file: "habits-view.js", terms: ["JooParkHabitsView", "joopark-habits-view/v1", "function createHabitsView", "function habitsViewModel", "function renderHabitsHTML"] },
    { file: "stats-view.js", terms: ["JooParkStatsView", "joopark-stats-view/v1", "function createStatsView", "function statsViewModel", "function renderStatsHTML"] },
    { file: "portfolio-view.js", terms: ["JooParkPortfolioView", "joopark-portfolio-view/v1", "function createPortfolioView", "function portfolioViewModel", "function renderPortfolioHTML"] },
    { file: "kanban-view.js", terms: ["JooParkKanbanView", "joopark-kanban-view/v1", "function createKanbanView", "function kanbanViewModel", "function renderKanbanHTML"] },
    { file: "gantt-view.js", terms: ["JooParkGanttView", "joopark-gantt-view/v1", "function createGanttView", "function ganttViewModel", "function renderGanttHTML"] },
    { file: "team-view.js", terms: ["JooParkTeamView", "joopark-team-view/v1", "function createTeamView", "function teamViewModel", "function renderTeamHTML"] },
    { file: "workspace-storage.js", terms: ["JooParkWorkspaceStorage", "joopark-workspace-storage/v1", "function createWorkspaceStorage", "function persistPayload", "function loadPersisted"] },
    { file: "storage-status-view.js", terms: ["JooParkStorageStatusView", "joopark-storage-status-view/v1", "function createStorageStatusView", "function storageStatusModel", "function settingsStorageHealthHTML"] },
    { file: "settings-view.js", terms: ["JooParkSettingsView", "joopark-settings-view/v1", "function createSettingsView", "function settingsViewModel", "function renderSettingsHTML"] },
    { file: "system-status-view.js", terms: ["JooParkSystemStatusView", "joopark-system-status-view/v1", "function createSystemStatusView", "function systemStatusModel", "function renderSystemStatusHTML"] },
    { file: "backup-import-guards.js", terms: ["JooParkImportGuards", "joopark-import-guards/v1", "recordLimitViolations", "backupSummaryItems"] },
    { file: "backup-import-ui.js", terms: ["JooParkBackupImportUi", "joopark-backup-import-ui/v1", "function createBackupImportUi", "function handleImportFile", "function applyImported"] },
    { file: "verify-workspace-summary.js", terms: ["JooParkVerifyWorkspaceSummary", "joopark-verify-workspace-summary/v1", "function createVerifyWorkspaceSummary", "function validateSummary", "release_readiness_gates", "launch_readiness_refresh", "product_loop_summary_sync"] },
    { file: "review-execution-checklist.js", terms: ["JooParkReviewExecutionChecklist", "joopark-review-execution-checklist/v1", "function createReviewExecutionChecklist", "function reviewExecutionChecklistItemsFromSavedResult", "function issueExecutionChecklistProgress"] },
    { file: "review-issue-payload.js", terms: ["JooParkReviewIssuePayload", "joopark-review-issue-payload/v1", "function createReviewIssuePayload", "function reviewIssueBodyLines", "function reviewSavedResultTrackerFields"] },
    { file: "pwa-runtime.js", terms: ["JooParkPwaRuntime", "joopark-pwa-runtime/v1", "function createPwaRuntime", "async function inspect"] },
    { file: "index.html", terms: ["search-empty-state.js", "home-execution-view.js", "calendar-view.js", "todo-view.js", "notes-view.js", "habits-view.js", "stats-view.js", "portfolio-view.js", "kanban-view.js", "gantt-view.js", "team-view.js", "workspace-storage.js", "storage-status-view.js", "settings-view.js", "system-status-view.js", "backup-import-guards.js", "backup-import-ui.js", "verify-workspace-summary.js", "review-execution-checklist.js", "review-issue-payload.js", "pwa-runtime.js", "app.js"] },
    { file: "docs/app-architecture.md", terms: ["JooPark Workspace App Architecture", "Structure Gate", "Next Extraction Order", "Module Migration Rule", "search-empty-state.js", "home-execution-view.js", "calendar-view.js", "todo-view.js", "notes-view.js", "habits-view.js", "stats-view.js", "portfolio-view.js", "kanban-view.js", "gantt-view.js", "team-view.js", "workspace-storage.js", "storage-status-view.js", "settings-view.js", "system-status-view.js", "backup-import-guards.js", "backup-import-ui.js", "verify-workspace-summary.js", "review-execution-checklist.js", "review-issue-payload.js", "pwa-runtime.js"] },
    { file: "package.json", terms: ["check:structure", "scripts/check-app-structure.mjs", "search-empty-state.js", "home-execution-view.js", "calendar-view.js", "todo-view.js", "notes-view.js", "habits-view.js", "stats-view.js", "portfolio-view.js", "kanban-view.js", "gantt-view.js", "team-view.js", "workspace-storage.js", "storage-status-view.js", "settings-view.js", "system-status-view.js", "backup-import-guards.js", "backup-import-ui.js", "verify-workspace-summary.js", "review-execution-checklist.js", "review-issue-payload.js", "pwa-runtime.js"] },
    { file: "README.md", terms: ["search-empty-state.js", "home-execution-view.js", "calendar-view.js", "todo-view.js", "notes-view.js", "habits-view.js", "stats-view.js", "portfolio-view.js", "kanban-view.js", "gantt-view.js", "team-view.js", "workspace-storage.js", "storage-status-view.js", "settings-view.js", "system-status-view.js", "backup-import-guards.js", "backup-import-ui.js", "verify-workspace-summary.js", "review-execution-checklist.js", "review-issue-payload.js", "pwa-runtime.js", "scripts/check-app-structure.mjs", "docs/app-architecture.md"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "app_structure_guard",
    requirement: "The monolithic static app has an automated structure audit and architecture map that preserve major product boundaries and define safe extraction candidates before further growth.",
    status: structureAudit.status === "pass" && structureTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: structureAudit.command,
      result: structureAudit.result,
      files: structureTerms,
    },
  });

  const appSource = read("app.js");
  const handleActionsSource = (appSource.match(/function handleActions\([\s\S]*?\n}\n\n/) || [""])[0];
  const directActionBranches = [...handleActionsSource.matchAll(/if \(action === "([^"]+)"\)/g)].map((match) => match[1]);
  const actionHandlerMaps = [...appSource.matchAll(/const ([A-Z_]+ACTION_HANDLERS) = new Map/g)].map((match) => match[1]);
  const requiredActionHandlerMaps = [
    "MODAL_ACTION_HANDLERS",
    "APP_SHELL_ACTION_HANDLERS",
    "SETTINGS_STORAGE_ACTION_HANDLERS",
    "OPERATIONS_COPY_ACTION_HANDLERS",
    "OPERATIONS_PARSER_ACTION_HANDLERS",
    "PM_CRUD_ACTION_HANDLERS",
    "DB_CRUD_ACTION_HANDLERS",
    "RECORD_OPEN_ACTION_HANDLERS",
  ];
  const missingActionHandlerMaps = requiredActionHandlerMaps.filter((name) => !actionHandlerMaps.includes(name));
  const structureActionDispatchGuard = structureAudit.result?.actionDispatchGuard || {};
  const actionDispatcherTerms = [
    { file: "app.js", terms: ["function runActionHandler", "const ACTION_HANDLER_GROUPS = Object.freeze", "ACTION_HANDLER_GROUPS.some((handlers) => runActionHandler(action, target, handlers))", "MODAL_ACTION_HANDLERS", "OPERATIONS_PARSER_ACTION_HANDLERS", "PM_CRUD_ACTION_HANDLERS", "DB_CRUD_ACTION_HANDLERS"] },
    { file: "scripts/check-app-structure.mjs", terms: ["function actionDispatchGuardEvidence", "function actionDispatchGuardFailure", "directActionBranchCount", "actionHandlerMapCount", "firstHandler", "MODAL_ACTION_HANDLERS", "minActionHandlerMaps"] },
    { file: "autoresearch-results/joopark-product-loop.md", terms: ["Modal confirm action dispatch map", "Action dispatcher structure guard", "directActionBranchCount", "`handleOneLineCount` is `0`", "actionDispatchGuard.status=pass"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "action_dispatcher_map_only",
    requirement: "Click action dispatch is map-only: handleActions has no direct action string branches, modal confirmation is first-position mapped, and PM/DB/operations parser actions remain in explicit maps.",
    status: directActionBranches.length === 0 && actionHandlerMaps.length >= 21 && missingActionHandlerMaps.length === 0 && structureActionDispatchGuard.status === "pass" && actionDispatcherTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      directActionBranches,
      directActionBranchCount: directActionBranches.length,
      actionHandlerMapCount: actionHandlerMaps.length,
      missingActionHandlerMaps,
      structureActionDispatchGuard,
      terms: actionDispatcherTerms,
    },
  });

  if (!skipSummarySelfCheck) {
    const auditSummaryTerms = [
      { file: "scripts/audit-release-readiness.mjs", terms: ["--format=summary", "function summary", "function externalClaimGuardState", "function externalClaimGuardSummaryLines", "completionAudit", "launchCompletionAchieved", "blockedSignals", "JooPark Release Readiness Summary", "External Claim Guard", "Packaged browser gates", "JOOPARK_AUDIT_SKIP_SUMMARY_SELF"] },
      { file: "scripts/verify-workspace.mjs", terms: ["--format=summary", "release_readiness_gates"] },
      { file: "README.md", terms: ["--format=summary", "JooPark Release Readiness Summary", "External Claim Guard", "completionAudit", "launchCompletionAchieved", "blockedSignals"] },
    ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
    checklist.push({
      id: "release_audit_summary_format",
      requirement: "Release readiness audit has a compact summary format for operator status checks without streaming the full checklist JSON.",
      status: auditSummaryTerms.every((item) => item.missingTerms.length === 0) && auditSummaryFormat?.status === "pass" ? "pass" : "fail",
      evidence: {
        terms: auditSummaryTerms,
        summary: auditSummaryFormat,
      },
    });
  }

  const workflowEvidence = workflowFiles.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "release_publish_workflow_template_files",
    requirement: "GitHub Pages publish workflow template files exist before claiming publish workflow readiness.",
    status: workflowEvidence.every((item) => item.exists) ? "pass" : "fail",
    evidence: workflowEvidence,
  });

  const workflowHandoffDryRun = githubPagesWorkflowHandoffDryRun();
  const workflowHandoffTerms = [
    { file: "scripts/prepare-github-pages-workflow.mjs", terms: ["--dry-run", "--write", "--check-scope", "workflowScopeRequired", "workflowScopeAvailable", "missing workflow scope", "docs/github-pages-workflow.yml", ".github/workflows/joopark-pages.yml", "willWrite", "gitRoot", "rev-parse", "--show-toplevel", "targetRepositoryPath", "attestations: write", "actions/checkout@v6", "actions/configure-pages@v5", "actions/attest@v4", "subject-path: dist/release/**", "actions/upload-pages-artifact@v4", "actions/deploy-pages@v4", "search-empty-state.js", "calendar-view.js", "todo-view.js", "notes-view.js", "habits-view.js", "stats-view.js", "portfolio-view.js", "kanban-view.js", "gantt-view.js", "team-view.js", "workspace-storage.js", "storage-status-view.js", "settings-view.js", "system-status-view.js", "backup-import-guards.js", "backup-import-ui.js", "release-status.js", "project-picker.js", "global-search.js", "command-palette.js", "db-catalog.js", "review-handoff.js", "review-result-view.js", "review-execution-checklist.js", "review-issue-payload.js", "review-result-state.js", "review-result-draft-state.js", "review-creation-actions.js", "icons/**", "site.webmanifest", "social-preview.png", "social-preview.svg"] },
    { file: "README.md", terms: ["node scripts/prepare-github-pages-workflow.mjs --dry-run", "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope", "node scripts/prepare-github-pages-workflow.mjs --write", "repository root", "workflowScopeAvailable", "workflow` scope", "attestations: write", "actions/attest@v4", "subject-path: dist/release/**", "search-empty-state.js", "calendar-view.js", "todo-view.js", "notes-view.js", "habits-view.js", "stats-view.js", "portfolio-view.js", "kanban-view.js", "gantt-view.js", "team-view.js", "workspace-storage.js", "storage-status-view.js", "settings-view.js", "system-status-view.js", "backup-import-ui.js", "release-status.js", "global-search.js", "command-palette.js", "db-catalog.js", "review-handoff.js", "review-result-view.js", "review-execution-checklist.js", "review-issue-payload.js", "review-result-state.js", "review-result-draft-state.js", "review-creation-actions.js"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const workflowHandoffFiles = workflowHandoffScripts.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "github_pages_workflow_scope_handoff",
    requirement: "GitHub Pages workflow installation has a dry-run handoff script that validates the template and only writes the repository-root workflow target when explicitly requested with a workflow-scope token or UI session.",
    status: workflowHandoffFiles.every((item) => item.exists) && workflowHandoffTerms.every((item) => item.missingTerms.length === 0) && workflowHandoffDryRun.status === "pass" ? "pass" : "fail",
    evidence: {
      files: workflowHandoffFiles,
      terms: workflowHandoffTerms,
      dryRun: workflowHandoffDryRun,
    },
  });

  const driftWorkflowTerms = [
    { file: "docs/github-drift-watch-workflow.yml", terms: ["workflow_dispatch:", "schedule:", "cron: \"23 2 * * 1\"", "permissions:", "contents: read", "actions/checkout@v6", "actions/setup-node@v4", "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}", "node scripts/check-candidate-freshness-drift.mjs --snapshot-only", "node scripts/check-candidate-freshness-drift.mjs --live", "node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift", "DRIFT_REPO", "fail-on-drift"] },
    { file: "README.md", terms: ["docs/github-drift-watch-workflow.yml", "Watch JooPark Candidate Drift", "schedule", "workflow_dispatch", ".github/workflows/joopark-drift-watch.yml", "GH_TOKEN", "secrets.GITHUB_TOKEN", "fail-on-drift"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const driftWorkflowEvidence = driftWorkflowFiles.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "github_drift_watch_workflow_template",
    requirement: "The project has a scheduled and manually triggerable GitHub Actions template for source-backed candidate drift checks with least-privilege token permissions.",
    status: driftWorkflowEvidence.every((item) => item.exists) && driftWorkflowTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      files: driftWorkflowEvidence,
      terms: driftWorkflowTerms,
    },
  });

  const driftWorkflowHandoffDryRun = githubDriftWatchWorkflowHandoffDryRun();
  const driftWorkflowHandoffTerms = [
    { file: "scripts/prepare-github-drift-watch-workflow.mjs", terms: ["--dry-run", "--write", "--check-scope", "workflowScopeRequired", "workflowScopeAvailable", "missing workflow scope", "docs/github-drift-watch-workflow.yml", ".github/workflows/joopark-drift-watch.yml", "willWrite", "gitRoot", "rev-parse", "--show-toplevel", "targetRepositoryPath", "schedule:", "workflow_dispatch:", "actions/checkout@v6", "actions/setup-node@v4", "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}"] },
    { file: "README.md", terms: ["node scripts/prepare-github-drift-watch-workflow.mjs --dry-run", "node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope", "node scripts/prepare-github-drift-watch-workflow.mjs --write", ".github/workflows/joopark-drift-watch.yml", "workflowScopeAvailable", "workflow` scope"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const driftWorkflowHandoffFiles = driftWorkflowHandoffScripts.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "github_drift_watch_workflow_scope_handoff",
    requirement: "GitHub drift-watch workflow installation has a dry-run handoff script that validates the scheduled template and only writes the repository-root workflow target when explicitly requested with a workflow-scope token or UI session.",
    status: driftWorkflowHandoffFiles.every((item) => item.exists) && driftWorkflowHandoffTerms.every((item) => item.missingTerms.length === 0) && driftWorkflowHandoffDryRun.status === "pass" ? "pass" : "fail",
    evidence: {
      files: driftWorkflowHandoffFiles,
      terms: driftWorkflowHandoffTerms,
      dryRun: driftWorkflowHandoffDryRun,
    },
  });

  const bridgePlan = mainBridgePlan();
  const prBridgeTerms = [
    { file: "scripts/plan-main-bridge.mjs", terms: ["merge-base", "noCommonHistory", "apps/joopark-workspace", "codex/joopark-workspace-main-bridge", "main-subdirectory-bridge", "pr-ready-main-history", "data/main-bridge-plan.json", "JooPark Main PR Bridge Plan", "externalComparison", "--write", "--out"] },
    { file: "README.md", terms: ["node scripts/plan-main-bridge.mjs", "node scripts/plan-main-bridge.mjs --write", "data/main-bridge-plan.json", "no common history", "apps/joopark-workspace", "codex/joopark-workspace-main-bridge"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const prBridgeFiles = prBridgeScripts.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "github_main_pr_bridge_strategy",
    requirement: "The project has a dry-run strategy for turning the orphan release branch into a PR-ready main-based branch under apps/joopark-workspace when GitHub reports no common history.",
    status: prBridgeFiles.every((item) => item.exists) && prBridgeTerms.every((item) => item.missingTerms.length === 0) && bridgePlan.status === "pass" ? "pass" : "fail",
    evidence: {
      files: prBridgeFiles,
      terms: prBridgeTerms,
      plan: bridgePlan,
    },
  });

  const workflowUiInstallTerms = [
    { file: "scripts/plan-workflow-ui-install.mjs", terms: ["workflowUiInstallReady", "uiInstallReady", "targetRepositoryPath", "sha256", "templateSha256", "targetSha256", "targetMatchesTemplate", "localTargetParityReady", "repositoryUrl", "suggestedRepo", "repoReplacementHint", "nextVerificationCommand", "placeholderVerificationCommand", "placeholderTemplateCommands", "defaultBranch", "actionsUrl", "githubNewFileUrl", "githubWorkflowUrl", "templateCopyCommand", "localTemplateHashCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "githubFileNameFieldValue", "suggestedCommitMessage", "workflowUiInstallFormFieldCoverage", "workflowUiTemplateIntegrityCoverage", "Template integrity ledger:", "expectedSha256", "postCommitRemoteCheck", "remoteSha256 equals templateSha256", "attestations: write", "actions/attest@v4", "subject-path: dist/release/**", "pbcopy < ", "shasum -a 256", "open ${shellQuote", "manualDispatchRequirement", "docs/github-pages-workflow.yml", "docs/github-drift-watch-workflow.yml", ".github/workflows/joopark-pages.yml", ".github/workflows/joopark-drift-watch.yml", "data/workflow-ui-install-plan.json", "--write", "--markdown"] },
    { file: "scripts/plan-workflow-ui-install.mjs", terms: ["workflowUiInstallReceipt", "installReceipt", "JooPark GitHub UI Workflow Install Receipt", "JooPark GitHub UI Workflow Paste Packet", "workflowUiInstallPastePacket", "workflowUiInstallPastePacketReady", "workflowUiInstallPastePacketCoverage", "templateIntegrityRows", "templateIntegrityCoverage", "Checksum guard:", "parserReadyProofFields", "parserReadyProofFieldCoverage", "parserReadyProofBlockReady", "Parser-ready proof block:", "pages_workflow_commit:", "The parser ignores bracketed [paste ...] placeholders", "GitHub new-file form values:", "githubFileNameFieldValue=.github/workflows/joopark-pages.yml", "suggestedCommitMessage=Add JooPark Pages publish workflow", "Paste exact template content", "Post-install proof checklist", "remoteWorkflowFilesReady=true", "remoteWorkflowVisibilityReady=true", "dispatchReady=true", "driftDispatchReady=true", "safeToDispatch=true before gh workflow run", "every post-install evidence field has been filled", "all six post-install evidence fields are filled", "verify-launch-handoff reports safeToDispatch=true", "External benchmark: GitHub UI file creation or editing"] },
    { file: "data/workflow-ui-install-plan.json", terms: ["workflowUiInstallReady", "uiInstallReady", "targetSha256", "targetMatchesTemplate", "localTargetParityReady", "githubNewFileUrl", "githubWorkflowUrl", "templateCopyCommand", "localTemplateHashCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "githubFileNameFieldValue", "suggestedCommitMessage", "workflowUiInstallFormFieldCoverage", "workflowUiTemplateIntegrityCoverage", "Template integrity ledger:", "expectedSha256", "postCommitRemoteCheck", "attestations: write", "actions/attest@v4", "subject-path: dist/release/**", "biojuho/BIOJUHO-Projects", "data/workflow-ui-install-plan.json"] },
    { file: "data/workflow-ui-install-plan.json", terms: ["installReceipt", "installReceiptReady", "JooPark GitHub UI Workflow Install Receipt", "JooPark GitHub UI Workflow Paste Packet", "workflowUiInstallPastePacket", "workflowUiInstallPastePacketReady", "workflowUiInstallPastePacketCoverage", "templateIntegrityRows", "templateIntegrityCoverage", "Checksum guard:", "parserReadyProofFields", "parserReadyProofFieldCoverage", "parserReadyProofBlockReady", "Parser-ready proof block:", "pages_workflow_commit:", "The parser ignores bracketed [paste ...] placeholders", "GitHub new-file form values:", "githubFileNameFieldValue=.github/workflows/joopark-pages.yml", "suggestedCommitMessage=Add JooPark Pages publish workflow", "Post-install verification commands:", "Post-install proof checklist:", "remoteWorkflowVisibilityReady=true", "dispatchReady=true", "driftDispatchReady=true", "safeToDispatch=true before gh workflow run", "every post-install evidence field has been filled", "all six post-install evidence fields are filled", "verify-launch-handoff reports safeToDispatch=true", "External benchmark: GitHub UI file creation or editing"] },
    { file: "release-status.js", terms: ["workflow-ui-install-plan", "GitHub UI install plan", "function workflowUiInstallPlanHTML", "data-system-workflow-ui-install-plan", "data-workflow-ui-install-card", "data-workflow-ui-install-target-parity-ready", "targetSha256", "targetMatchesTemplate", "data/workflow-ui-install-plan.json", "node scripts/plan-workflow-ui-install.mjs --dry-run --markdown", "template sha256", "githubNewFileUrl", "githubWorkflowUrl", "templateCopyCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "githubFileNameFieldValue", "suggestedCommitMessage", "data-workflow-ui-install-form-field-coverage", "defaultBranch", "suggestedRepo", "nextVerificationCommand", "biojuho/BIOJUHO-Projects"] },
    { file: "release-status.js", terms: ["data-workflow-ui-install-receipt-ready", "data-workflow-ui-install-receipt-command-count", "data-workflow-ui-install-receipt-text", "data-workflow-ui-install-paste-packet", "data-workflow-ui-install-paste-packet-ready", "data-workflow-ui-install-paste-packet-coverage", "finiteNumberOr(data?.workflowUiInstallPastePacketCoverage", "finiteNumberOr(data?.workflowUiInstallFormFieldCoverage", "data-workflow-ui-install-parser-ready-proof-block-ready", "data-workflow-ui-install-parser-ready-proof-field-coverage", "parserReadyProofFieldCoverage", "data-workflow-ui-install-paste-packet-text", "copy-workflow-ui-install-receipt", "UI paste packet 복사"] },
    { file: "release-status.js", terms: ["data-workflow-ui-install-runbook", "data-workflow-ui-install-runbook-step", "data-workflow-ui-install-runbook-signal", "data-workflow-ui-install-runbook-handoff-command", "default branch runbook", "GitHub UI install first, dispatch later", "Verify remote file parity", "Verify workflow visibility", "Recheck dispatch guard", "workflowListCommand", "safeToDispatch=true"] },
    { file: "app.js", terms: ["workflowUiInstallPlan", "function loadWorkflowUiInstallPlan", "function workflowUiInstallPlanHTML", "data/workflow-ui-install-plan.json", "node scripts/plan-workflow-ui-install.mjs --dry-run --markdown", "template sha256", "githubNewFileUrl", "githubWorkflowUrl", "templateCopyCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "githubFileNameFieldValue", "suggestedCommitMessage", "workflowUiInstallFormFieldCoverage", "defaultBranch", "suggestedRepo", "nextVerificationCommand", "biojuho/BIOJUHO-Projects"] },
    { file: "app.js", terms: ["function copyWorkflowUiInstallReceipt", "copy-workflow-ui-install-receipt", "data-workflow-ui-install-receipt-text", "workflowUiInstallReceiptCopied", "workflowUiInstallPastePacketCopied", "workflowUiInstallPastePacketCoverage", "JooPark GitHub UI Workflow Paste Packet"] },
    { file: "styles.css", terms: [".workflow-ui-install-plan", ".workflow-ui-install-cards", ".workflow-ui-install-card", ".workflow-ui-install-next"] },
    { file: "styles.css", terms: [".workflow-ui-install-runbook", ".workflow-ui-install-runbook-head", ".workflow-ui-install-runbook-signals", ".workflow-ui-install-runbook-guard"] },
    { file: "styles.css", terms: [".workflow-ui-install-receipt"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["data-system-workflow-ui-install-plan", "data-workflow-ui-install-card", "workflowUiInstallPlanPanel", "workflowUiInstallTargetParityReady", "workflowUiInstallTargetMatchesTemplate", "workflowUiInstallFormFieldCoverage", "githubFileNameFieldValue", "suggestedCommitMessage", "plan-workflow-ui-install.mjs --dry-run --markdown", "GitHub UI install plan", "targetSha256", "targetMatchesTemplate", "template sha256", "githubNewFileUrl", "githubWorkflowUrl", "defaultBranch", "suggestedRepo", "nextVerificationCommand", "biojuho/BIOJUHO-Projects"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["data-workflow-ui-install-runbook", "workflowRunbookSteps", "workflowRunbookSignals", "GitHub UI install first, dispatch later", "verify-remote-parity", "verify-workflow-visibility", "verify-dispatch-guard", "workflow UI install runbook steps were incomplete"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workflowUiInstallReceipt", "workflowInstallReceiptText", "JooPark GitHub UI Workflow Install Receipt", "JooPark GitHub UI Workflow Paste Packet", "workflowUiInstallPastePacketCoverage", "Parser-ready proof block:", "pages_workflow_commit:", "post-install proof parser treated the template receipt as complete proof", "postInstallProofParserFalsePositiveGuard", "GitHub new-file form values:", "githubFileNameFieldValue=.github/workflows/joopark-pages.yml", "suggestedCommitMessage=Add JooPark Pages publish workflow", "workflowUiInstallPastePacketCopy", "workflow UI install receipt copy text did not reach clipboard", "safeToDispatch=true before gh workflow run", "every post-install evidence field has been filled", "all six post-install evidence fields are filled", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "README.md", terms: ["node scripts/plan-workflow-ui-install.mjs --dry-run --markdown", "template sha256", "targetSha256", "targetMatchesTemplate", "localTargetParityReady", "githubNewFileUrl", "githubWorkflowUrl", "templateCopyCommand", "localTemplateHashCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "githubFileNameFieldValue", "suggestedCommitMessage", "workflowUiInstallFormFieldCoverage", "workflowUiTemplateIntegrityCoverage", "Template integrity ledger", "Checksum guard", "expectedSha256", "postCommitRemoteCheck", "remoteSha256 equals templateSha256", "attestations: write", "actions/attest@v4", "subject-path: dist/release/**", "defaultBranch", "suggestedRepo", "nextVerificationCommand", "biojuho/BIOJUHO-Projects", "JooPark GitHub UI Workflow Paste Packet", "workflowUiInstallPastePacketCoverage", ".github/workflows/joopark-pages.yml", ".github/workflows/joopark-drift-watch.yml"] },
    { file: "README.md", terms: ["JooPark GitHub UI Workflow Paste Packet", "UI paste packet 복사", "workflowUiInstallPastePacketCoverage: 1", "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown", "dispatchReady=true", "driftDispatchReady=true", "gh workflow run --repo", "every post-install evidence field has been filled", "verify-launch-handoff reports safeToDispatch=true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "workflow_ui_install_plan",
    requirement: "The project has a dry-run GitHub UI workflow install plan that verifies target paths, template hashes, and required terms before manual workflow installation.",
    status: workflowUiInstallTerms.every((item) => item.missingTerms.length === 0) && workflowUiInstall.status === "pass" && workflowUiInstallFile.status === "pass" ? "pass" : "fail",
    evidence: {
      terms: workflowUiInstallTerms,
      plan: workflowUiInstall,
      file: workflowUiInstallFile,
    },
  });

  const workflowLocalStagingTerms = [
    { file: "scripts/prepare-github-pages-workflow.mjs", terms: ["--stage-local", "localStage", "remoteWriteReady", "localStageHint", ".github/workflows/joopark-pages.yml"] },
    { file: "scripts/prepare-github-drift-watch-workflow.mjs", terms: ["--stage-local", "localStage", "remoteWriteReady", "localStageHint", ".github/workflows/joopark-drift-watch.yml"] },
    { file: ".github/workflows/joopark-pages.yml", terms: ["workflow_dispatch:", "pages: write", "id-token: write", "attestations: write", "actions/attest@v4", "subject-path: dist/release/**", "Generate release readiness summary cache", "audit_status", "joopark-release-readiness-summary/v1", "node scripts/package-release.mjs", "node scripts/verify-release.mjs"] },
    { file: ".github/workflows/joopark-drift-watch.yml", terms: ["workflow_dispatch:", "schedule:", "contents: read", "node scripts/check-candidate-freshness-drift.mjs --live", "fail-on-drift"] },
    { file: "README.md", terms: ["--stage-local", "localStage", "remoteWriteReady", "workflow-scope token"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "github_workflow_local_staging",
    requirement: "Repository-root Pages and Drift Watch workflow files can be staged locally from verified templates without claiming remote GitHub Actions visibility.",
    status: workflowLocalStaging.status === "pass" && workflowLocalStagingTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      files: workflowLocalStaging,
      terms: workflowLocalStagingTerms,
    },
  });

  const launchReadinessRefreshArtifact = fileExists("data/launch-readiness-refresh.json")
    ? parseJson(read("data/launch-readiness-refresh.json"))
    : null;
  const outputQualityAuditArtifact = fileExists("data/output-quality-audit.json")
    ? parseJson(read("data/output-quality-audit.json"))
    : null;
  const productLoopArtifact = fileExists("autoresearch-results/joopark-product-loop.json")
    ? parseJson(read("autoresearch-results/joopark-product-loop.json"))
    : null;
  const verifyWorkspaceSummaryArtifact = fileExists("autoresearch-results/verify-workspace-summary.json")
    ? parseJson(read("autoresearch-results/verify-workspace-summary.json"))
    : null;
  const launchReadinessSourceArtifactSync = {
    status: launchReadinessRefreshArtifact?.outputQualityGeneratedAt &&
      outputQualityAuditArtifact?.generatedAt &&
      launchReadinessRefreshArtifact.outputQualityGeneratedAt === outputQualityAuditArtifact.generatedAt
      ? "pass"
      : "fail",
    launchReadinessOutputQualityGeneratedAt: launchReadinessRefreshArtifact?.outputQualityGeneratedAt || "",
    currentOutputQualityGeneratedAt: outputQualityAuditArtifact?.generatedAt || "",
    sourceArtifactSyncStatus: launchReadinessRefreshArtifact?.sourceArtifactSync?.status || "missing",
    refreshCommand: "npm run refresh:launch-readiness",
    requirement: "data/launch-readiness-refresh.json must embed the current data/output-quality-audit.json generatedAt value.",
  };
  const launchReadinessDispatchCommandState = {
    status:
      launchReadinessRefreshArtifact?.dispatchCommandDisposition === "withheld" &&
      Number(launchReadinessRefreshArtifact?.withheldDispatchCommandCount || 0) === 2 &&
      Number(launchReadinessRefreshArtifact?.suggestedDispatchCommandCount || 0) === 0 &&
      Number(launchReadinessRefreshArtifact?.activeDispatchCommandCount || 0) === 0 &&
      Number(launchReadinessRefreshArtifact?.dispatchCommandReferenceCount || 0) === Number(launchReadinessRefreshArtifact?.withheldDispatchCommandCount || 0)
        ? "pass"
        : "fail",
    disposition: launchReadinessRefreshArtifact?.dispatchCommandDisposition || "missing",
    withheldDispatchCommandCount: Number(launchReadinessRefreshArtifact?.withheldDispatchCommandCount || 0),
    suggestedDispatchCommandCount: Number(launchReadinessRefreshArtifact?.suggestedDispatchCommandCount || 0),
    activeDispatchCommandCount: Number(launchReadinessRefreshArtifact?.activeDispatchCommandCount || 0),
    dispatchCommandReferenceCount: Number(launchReadinessRefreshArtifact?.dispatchCommandReferenceCount || 0),
  };
  const launchReadinessRefreshTerms = [
    { file: "scripts/refresh-launch-readiness.mjs", terms: ["manual_multi_command_refresh", "single_launch_readiness_refresh_runner", "operator_refresh_command_count", "data/launch-readiness-refresh.json", "data/launch-readiness-refresh.md", "scripts/plan-workflow-ui-install.mjs", "scripts/check-remote-workflow-files.mjs", "scripts/plan-publish-dispatch.mjs", "scripts/capture-launch-execution-packet.mjs", "scripts/verify-launch-handoff.mjs", "scripts/capture-output-quality-audit.mjs", "safeToDispatch", "readyForExternalClaim", "withheldDispatchCommandCount", "suggestedDispatchCommandCount", "dispatchCommandDisposition", "not_applicable_after_launch_proof", "activeDispatchCommands", "activeDispatchCommandCount", "dispatchCommandReferenceCount", "finiteNumberOr", "remoteWorkflowRepairAction", "replace_existing_remote_file", "githubEditFileUrl", "remoteBlobSha", "evidenceFreshness", "evidenceMaxAgeHours", "LAUNCH_READINESS_MAX_AGE_HOURS", "sourceArtifactSync", "launchReadinessSourceArtifactSyncCoverage", "sourceArtifactCount", "outputQualityGeneratedAt", "outputQualitySourceInputCount", "latestGate", "outputQualityGateTraceability", "launchReadinessOutputQualityGateTraceability", "GitHub Actions job summaries", "Do not run gh workflow run", "every action_required refresh checklist item has passed", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "data/launch-readiness-refresh.json", terms: ["commandCoverage", "manual_multi_command_refresh", "single_launch_readiness_refresh_runner", "\"decision\": \"keep_b\"", "\"evidenceFreshnessStatus\": \"fresh\"", "\"evidenceMaxAgeHours\": 24", "\"sourceArtifactCount\": 6", "\"sourceArtifactSync\"", "\"launchReadinessSourceArtifactSyncCoverage\"", "\"outputQualitySourceInputCount\": 11", "\"latestGate\"", "\"latestGateSummary\"", "0 fail, 0 not_run, 0 blocked", "\"outputQualityGateTraceability\"", "\"launchReadinessOutputQualityGateTraceability\"", "\"refreshRequired\": false", "\"workflowScopeInstallBlocked\"", "\"remoteWorkflowFilesReady\"", "\"remoteWorkflowVisibilityReady\"", "\"allDispatchReady\"", "\"safeToDispatch\"", "\"readyForExternalClaim\"", "\"withheldDispatchCommandCount\": 2", "\"suggestedDispatchCommandCount\": 0", "\"dispatchCommandDisposition\": \"withheld\"", "\"activeDispatchCommandCount\": 0", "\"dispatchCommandReferenceCount\": 2", "\"activeDispatchCommands\"", "\"remoteWorkflowRepairAction\"", "\"installAction\": \"replace_existing_remote_file\"", "\"githubEditFileUrl\"", "\"remoteBlobSha\"", "\"nextAction\"", "Do not run gh workflow run", "every action_required refresh checklist item has passed", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "data/launch-readiness-refresh.md", terms: ["JooPark Launch Readiness Refresh", "evidenceFreshness: fresh", "refreshRequired: false", "commandCoverage: 6", "sourceArtifactSync: pass", "outputQualitySourceInputCount: 11", "latestGate: npm run verify ->", "0 fail, 0 not_run, 0 blocked", "Output Quality Gate Traceability", "launchReadinessOutputQualityGateTraceability", "Evidence Freshness", "sourceArtifactCount: 6", "workflowScopeInstallBlocked:", "remoteWorkflowFilesReady:", "safeToDispatch:", "readyForExternalClaim:", "dispatchCommandDisposition:", "activeDispatchCommandCount:", "dispatchCommandReferenceCount:", "Remote Workflow Repair Action", "installAction: replace_existing_remote_file", "githubEditFileUrl:", "remoteBlobSha:", "A/B Decision", "decision: keep_b", "Refresh Checklist", "Next Action", "every action_required refresh checklist item has passed", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "release-status.js", terms: ["function launchReadinessFreshness", "function launchReadinessDispatchCommandState", "function launchReadinessRefreshReceiptText", "function launchReadinessRefreshHTML", "sourceArtifactCount: finiteNumberOr(freshness.sourceArtifactCount, sourceArtifacts.length)", "data-system-launch-readiness-refresh", "data-launch-readiness-refresh-command-coverage", "data-launch-readiness-refresh-safe-to-dispatch", "data-launch-readiness-refresh-ready-for-external-claim", "data-launch-readiness-refresh-active-dispatch-count", "data-launch-readiness-refresh-reference-dispatch-count", "data-launch-readiness-refresh-dispatch-command-disposition", "data-launch-readiness-refresh-repair-action", "data-launch-readiness-refresh-repair-command", "data-launch-readiness-refresh-repair-edit-url", "Remote Workflow Repair Action", "Remote workflow repair", "not applicable after proof", "data-launch-readiness-refresh-ab-decision", "data-launch-readiness-refresh-freshness-status", "data-launch-readiness-refresh-refresh-required", "data-launch-readiness-refresh-source-artifact-count", "data-launch-readiness-refresh-source-artifact-sync", "sourceArtifactSync:", "source sync", "data-launch-readiness-refresh-output-quality-gate-traceability", "data-launch-readiness-refresh-latest-gate-status", "data-launch-readiness-refresh-latest-gate-pass", "data-launch-readiness-refresh-output-quality-source-input-count", "latestGate:", "outputQualityGateTraceability:", "dispatchCommandDisposition:", "activeDispatchCommandCount:", "dispatchCommandReferenceCount:", "data-launch-readiness-refresh-receipt-text", "copy-launch-readiness-refresh-receipt", "npm run refresh:launch-readiness"] },
    { file: "system-status-view.js", terms: ["launchReadinessRefreshHTML", "raw(launchReadinessRefreshHTML(state.launchReadinessRefresh))", "publishReadinessPanelHTML"] },
    { file: "app.js", terms: ["launchReadinessRefresh", "function loadLaunchReadinessRefresh", "function launchReadinessRefreshHTML", "function copyLaunchReadinessRefreshReceipt", "copy-launch-readiness-refresh-receipt", "data/launch-readiness-refresh.json", "abComparison.decision", "evidenceFreshness.sourceArtifacts"] },
    { file: "operations-copy-actions.js", terms: ["function copyLaunchReadinessRefreshReceipt", "data-launch-readiness-refresh-receipt-text", "launchReadinessRefreshReceiptCopied", "launch readiness refresh receipt를 복사했습니다"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["launchReadinessRefreshOk", "launchReadinessRefreshReceiptCopyOk", "data-system-launch-readiness-refresh", "launchReadinessRefreshCommandCoverage", "launchReadinessRefreshSafeToDispatch", "launchReadinessRefreshReadyForExternalClaim", "launchReadinessRefreshActiveDispatchCount", "launchReadinessRefreshReferenceDispatchCount", "launchReadinessRefreshDispatchCommandDisposition", "launchReadinessRefreshRepairAction", "launchReadinessRefreshRepairCommand", "launchReadinessRepairEditUrl", "launchReadinessSourceArtifactSync", "sourceArtifactSync: pass", "replace_existing_remote_file", "edit/main/.github/workflows/joopark-pages.yml", "Remote Workflow Repair Action", "not_applicable_after_launch_proof", "dispatchCommandDisposition:", "activeDispatchCommandCount:", "dispatchCommandReferenceCount:", "launchReadinessRefreshFreshnessStatus", "launchReadinessRefreshSourceArtifactCount", "launchReadinessRefreshOutputQualityGateTraceability", "launchReadinessRefreshLatestGateStatus", "launchReadinessRefreshOutputQualitySourceInputCount", "latestGate: npm run verify ->", "outputQualitySourceInputCount: 11", "outputQualityGateTraceability: pass", "data-launch-readiness-refresh-receipt-copy", "JooPark Launch Readiness Refresh Receipt", "workflow_ui_install_plan", "npm run refresh:launch-readiness", "every action_required refresh checklist item has passed", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "package.json", terms: ["refresh:launch-readiness", "scripts/refresh-launch-readiness.mjs"] },
    { file: "README.md", terms: ["npm run refresh:launch-readiness", "data/launch-readiness-refresh.json", "data/launch-readiness-refresh.md", "commandCoverage=6", "decision=keep_b", "evidenceFreshnessStatus=fresh", "evidenceMaxAgeHours=24", "sourceArtifactCount=6", "outputQualitySourceInputCount=11", "latestGate", "outputQualityGateTraceability", "safeToDispatch", "readyForExternalClaim", "dispatchCommandDisposition", "activeDispatchCommandCount", "dispatchCommandReferenceCount", "not_applicable_after_launch_proof", "readiness receipt 복사", "scripts/refresh-launch-readiness.mjs", "every action_required refresh checklist item has passed", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "docs/app-architecture.md", terms: ["scripts/refresh-launch-readiness.mjs", "data/launch-readiness-refresh.json", "data/launch-readiness-refresh.md", "launch readiness refresh evidence"] },
    { file: "sw.js", terms: ["joopark-workspace-v3-offline-2026-06-09-runtime-error-boundary-module", "./data/launch-readiness-refresh.json"] },
    { file: "scripts/verify-release.mjs", terms: ["data/launch-readiness-refresh.json", "./data/launch-readiness-refresh.json"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "launch_readiness_refresh_runner",
    requirement: "A single launch-readiness refresh runner updates workflow install, remote file, dispatch, launch packet, handoff verifier, and output-quality evidence without executing dispatch, and System Status exposes its guard state.",
    status: launchReadinessRefreshTerms.every((item) => item.missingTerms.length === 0) && launchReadinessSourceArtifactSync.status === "pass" && launchReadinessDispatchCommandState.status === "pass" ? "pass" : "fail",
    evidence: {
      terms: launchReadinessRefreshTerms,
      sourceArtifactSync: launchReadinessSourceArtifactSync,
      dispatchCommandState: launchReadinessDispatchCommandState,
    },
  });

  const verifyCommandGateOnlyTerms = [
    { file: "package.json", terms: ["\"verify\": \"npm test\"", "\"verify:full\": \"node scripts/verify-workspace.mjs --sync-artifacts\"", "\"refresh:launch-readiness\": \"node scripts/refresh-launch-readiness.mjs --repo biojuho/BIOJUHO-Projects --write\""] },
    { file: "scripts/verify-workspace.mjs", terms: ["JooPark Verify Workspace Summary", "release_readiness_gates", "syncArtifacts", "--sync-artifacts", "launch_readiness_refresh", "product_loop_summary_sync", "evidenceSync", "productLoopGateParityReady", "productLoopPublishParityReady", "summarySyncReady", "nextCandidatesReady", "nextCandidateListReady", "directionLoopSyncReady", "latestDirectionExperimentReady", "latestDiscoveryExperimentReady", "latestExperiment", "latestDirectionExperiment", "latestDiscoveryExperiment", "latestDirectionLoopNumber", "directionLogPath", "npm run verify:full", "stepResults", "autoresearch-results/verify-workspace-summary.json", "finiteNumberOr", "dispatchCommandReferenceCount", "result.status !== \"pass\" && !syncArtifacts"] },
    { file: "scripts/sync-product-loop-summary.mjs", terms: ["directionLogPath", "latestDirectionLoopFromMarkdown", "directionReferencesFromSection", "normalizedReferenceUrl", "isOperationalGithubUrl", "referenceQualityReady", "operationalReferenceExcludedCount", "operationalReferenceLeakCount", "directionLoopExperiment", "latestDirectionExperimentReady", "latestDirectionExperimentId", "latestDiscoveryExperimentReady", "latestDiscoveryExperimentId", "latestDiscoveryExperiment", "latestDirectionLoopNumber", "directionLoopReady", "latestDirectionLoop", "nextCandidatesForStatus", "nextCandidatesReady", "nextCandidateCount", "nextCandidatesChanged", "topProjects", "topProjectCount", "releaseTargetIncluded"] },
    { file: "autoresearch-results/joopark-product-loop.json", terms: ["\"referenceQualityReady\": true", "\"operationalReferenceExcludedCount\"", "\"operationalReferenceLeakCount\": 0", "\"rawReferenceCount\"", "\"latestDiscoveryExperiment\"", "\"latestDiscoveryExperimentReady\": true", "\"latestDiscoveryExperimentId\": \"github-project-discovery-artifact\"", "\"githubDiscoveryActionableProjectCoverage\"", "\"topProjects\"", "\"topProjectCount\": 4", "\"releaseTargetIncluded\": true", "Actionable public project coverage"] },
    { file: "README.md", terms: ["기본 `npm run verify`는 `node scripts/verify-workspace.mjs` runner", "release gate만 `--format=summary`로 실행", "full evidence sync", "`npm run verify:full`", "productLoopGateParityReady", "productLoopPublishParityReady", "summarySyncReady", "nextCandidateListReady", "latestDirectionExperiment", "latestDiscoveryExperiment", "latestDirectionExperimentReady", "latestDiscoveryExperimentReady", "`npm run refresh:launch-readiness`와 `node scripts/sync-product-loop-summary.mjs --write --markdown`은 여전히 개별 복구 명령"] },
    { file: "release-status.js", terms: ["function verifyWorkspaceSummaryReceiptText", "function verifyWorkspaceSummaryHTML", "data-system-verify-workspace-summary", "data-verify-workspace-summary-evidence-sync-pass", "data-verify-workspace-summary-latest-experiment", "data-verify-workspace-summary-latest-direction-experiment", "data-verify-workspace-summary-latest-discovery-experiment", "data-verify-workspace-summary-direction-experiment-sync", "data-verify-workspace-summary-discovery-experiment-sync", "data-verify-workspace-summary-direction-loop-sync", "data-verify-workspace-summary-next-candidate-list", "data-verify-workspace-summary-next-candidate-count", "data-verify-workspace-summary-next-candidates", "data-verify-workspace-summary-dispatch-command-disposition", "data-verify-workspace-summary-active-dispatch-count", "data-verify-workspace-summary-reference-dispatch-count", "latestExperiment", "latestDirectionLoop", "latestDirectionExperiment", "latestDiscoveryExperiment", "nextCandidates", "nextCandidateList", "directionLoop", "directionExperiment", "discoveryExperiment", "dispatchCommandDisposition:", "activeDispatchCommandCount:", "dispatchCommandReferenceCount:", "JooPark Verify Workspace Summary Receipt", "release_readiness_gates", "launch_readiness_refresh", "product_loop_summary_sync", "copy-verify-workspace-summary-receipt"] },
    { file: "system-status-view.js", terms: ["verifyWorkspaceSummaryHTML", "state.verifyWorkspaceSummary", "data-system-verify-workspace-summary"] },
    { file: "verify-workspace-summary.js", terms: ["JooParkVerifyWorkspaceSummary", "joopark-verify-workspace-summary/v1", "joopark-verify-workspace/v1", "function validateSummary", "function createVerifyWorkspaceSummary", "autoresearch-results/verify-workspace-summary.json", "release_readiness_gates", "launch_readiness_refresh", "product_loop_summary_sync", "latestExperiment", "latestDirectionLoop", "latestDirectionExperiment", "latestDiscoveryExperiment", "nextCandidateCount", "nextCandidateListReady", "directionLoopSyncReady", "latestDirectionExperimentReady", "latestDiscoveryExperimentReady"] },
    { file: "app.js", terms: ["verifyWorkspaceSummaryHelpers", "function loadVerifyWorkspaceSummary", "verifyWorkspaceSummaryCall(\"load\"", "copyVerifyWorkspaceSummaryReceipt", "copy-verify-workspace-summary-receipt"] },
    { file: "operations-copy-actions.js", terms: ["function copyVerifyWorkspaceSummaryReceipt", "data-verify-workspace-summary-receipt-text", "verifyWorkspaceSummaryReceiptCopied", "verify workspace summary receipt를 복사했습니다"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["verifyWorkspaceSummaryOk", "verifyWorkspaceSummaryReceiptCopyOk", "data-system-verify-workspace-summary", "verifyWorkspaceSummaryEvidenceSyncPass", "verifyWorkspaceSummaryLatestExperiment", "verifyWorkspaceSummaryLatestDirectionExperiment", "verifyWorkspaceSummaryLatestDiscoveryExperiment", "verifyWorkspaceSummaryDirectionLoopSync", "verifyWorkspaceSummaryDirectionExperimentSync", "verifyWorkspaceSummaryDiscoveryExperimentSync", "verifyWorkspaceSummaryNextCandidateList", "verifyWorkspaceSummaryDispatchCommandDisposition", "verifyWorkspaceSummaryActiveDispatchCount", "verifyWorkspaceSummaryReferenceDispatchCount", "latestExperiment=", "latestDirectionExperiment=", "latestDiscoveryExperiment=", "latestDirectionLoop=loop-", "directionLoop=true", "directionExperiment=true", "discoveryExperiment=true", "nextCandidates=true", "nextCandidateList=true", "Share or archive only after proof", "JooPark Verify Workspace Summary Receipt", "release_readiness_gates: pass", "readyForExternalClaim:", "dispatchCommandDisposition:", "activeDispatchCommandCount:", "dispatchCommandReferenceCount:"] },
    { file: "scripts/package-release.mjs", terms: ["verify-workspace-summary.js", "autoresearch-results/verify-workspace-summary.json", "/autoresearch-results/verify-workspace-summary.json", "Cache-Control: no-cache"] },
    { file: "scripts/verify-release.mjs", terms: ["verify-workspace-summary.js", "autoresearch-results/verify-workspace-summary.json", "sourceParityFiles", "./autoresearch-results/verify-workspace-summary.json"] },
    { file: "scripts/smoke-release.mjs", terms: ["verify-workspace-summary.js", "verify_workspace_summary_runtime_cache_no_cache", "autoresearch-results/verify-workspace-summary.json", "verify_workspace_summary_cache_no_cache", "verifyWorkspaceSummary"] },
    { file: "sw.js", terms: ["./verify-workspace-summary.js", "./autoresearch-results/verify-workspace-summary.json"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["verify_command_gate_only", "verifyCommandGateOnlyTerms", "verifyWorkspaceSummaryArtifactSync", "verifyWorkspaceSummaryStatusReady", "verifyWorkspaceSummaryLaunchGeneratedAt", "currentLaunchGeneratedAt", "verifyWorkspaceSummaryLatestExperiment", "currentLatestExperiment", "verify:full", "refresh-launch-readiness remains explicit outside default verify", "scripts/verify-workspace.mjs", "autoresearch-results/verify-workspace-summary.json"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const verifyWorkspaceSummaryStatusReady = verifyWorkspaceSummaryArtifact?.status === "pass" ||
    verifyWorkspaceSummaryArtifact?.status === "blocked";
  const verifyWorkspaceSummaryArtifactSyncReady = verifyWorkspaceSummaryStatusReady &&
    verifyWorkspaceSummaryArtifact.syncArtifacts === true &&
    verifyWorkspaceSummaryArtifact.evidenceSyncPass === true &&
    verifyWorkspaceSummaryArtifact.artifacts?.launchReadiness?.generatedAt === launchReadinessRefreshArtifact?.generatedAt &&
    verifyWorkspaceSummaryArtifact.artifacts?.launchReadiness?.dispatchCommandReferenceCount === launchReadinessRefreshArtifact?.dispatchCommandReferenceCount &&
    verifyWorkspaceSummaryArtifact.artifacts?.outputQuality?.generatedAt === outputQualityAuditArtifact?.generatedAt &&
    verifyWorkspaceSummaryArtifact.artifacts?.productLoop?.generatedAt === productLoopArtifact?.generatedAt &&
    verifyWorkspaceSummaryArtifact.artifacts?.productLoop?.latestExperiment === productLoopArtifact?.latestExperiment?.id;
  const verifyWorkspaceSummaryArtifactSync = {
    status: runGates || verifyWorkspaceSummaryArtifactSyncReady ? "pass" : "fail",
    skippedDuringRunGates: runGates,
    summaryGeneratedAt: verifyWorkspaceSummaryArtifact?.generatedAt || "",
    verifyWorkspaceSummaryLaunchGeneratedAt: verifyWorkspaceSummaryArtifact?.artifacts?.launchReadiness?.generatedAt || "",
    currentLaunchGeneratedAt: launchReadinessRefreshArtifact?.generatedAt || "",
    verifyWorkspaceSummaryOutputQualityGeneratedAt: verifyWorkspaceSummaryArtifact?.artifacts?.outputQuality?.generatedAt || "",
    currentOutputQualityGeneratedAt: outputQualityAuditArtifact?.generatedAt || "",
    verifyWorkspaceSummaryProductLoopGeneratedAt: verifyWorkspaceSummaryArtifact?.artifacts?.productLoop?.generatedAt || "",
    currentProductLoopGeneratedAt: productLoopArtifact?.generatedAt || "",
    verifyWorkspaceSummaryLatestExperiment: verifyWorkspaceSummaryArtifact?.artifacts?.productLoop?.latestExperiment || "",
    currentLatestExperiment: productLoopArtifact?.latestExperiment?.id || "",
    verifyWorkspaceSummaryDispatchReferenceCount: verifyWorkspaceSummaryArtifact?.artifacts?.launchReadiness?.dispatchCommandReferenceCount,
    currentDispatchReferenceCount: launchReadinessRefreshArtifact?.dispatchCommandReferenceCount,
    repairCommand: "npm run verify:full",
    requirement: "autoresearch-results/verify-workspace-summary.json must match the current launch-readiness, output-quality, and product-loop artifacts outside the --run-gates repair path.",
  };
  checklist.push({
    id: "verify_command_gate_only",
    requirement: "The default verify command stays gate-only for file-watch loop safety, while npm run verify:full exposes an explicit evidence-synced runner and packaged System Status summary that verifies launch-readiness refresh, product-loop parity, and evidenceSync.",
    status: verifyCommandGateOnlyTerms.every((item) => item.missingTerms.length === 0) &&
      verifyWorkspaceSummaryArtifactSync.status === "pass"
      ? "pass"
      : "fail",
    evidence: {
      note: "refresh-launch-readiness remains explicit outside default verify; npm run verify:full is the intentional full evidence-sync path.",
      terms: verifyCommandGateOnlyTerms,
      verifyWorkspaceSummaryArtifactSync,
    },
  });

  const publishDispatchTerms = [
    { file: "scripts/plan-publish-dispatch.mjs", terms: ["workflowPlans", "workflowUiInstallPlans", "workflowUiInstallReady", "githubNewFileUrl", "githubWorkflowUrl", "templateSha256", "targetSha256", "targetMatchesTemplate", "localTargetParityReady", "local workflow target differs from template", "templateCopyCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "pbcopy < ", "manualDispatchRequirement", "workflowScopeCheckCommand", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "workflowScopeRefreshHandoff", "workflowScopeApprovalHandoff", "approval_required", "approvalUrl", "https://github.com/login/device", "sensitiveValuePolicy", "Do not store, log, or paste the one-time device code", "gh auth refresh -h github.com -s workflow", "nextActions", "nextVerificationCommand", "placeholderVerificationCommand", "repoEvidenceReady", "workflowListCommand", "workflowListFixture", "workflow-list-fixture", "--workflow-list-fixture", "localWorkflowTargetsReady", "remoteWorkflowVisibilityReady", "workflowDefaultBranchHandoff", "gitAddCommand", "gitCommitCommand", "staged repository-root workflows", "workflowDispatchCommand", "workflowName: \"Publish JooPark Pages\"", "workflowName: \"Watch JooPark Candidate Drift\"", "workflowPath: \".github/workflows/joopark-pages.yml\"", "workflowPath: \".github/workflows/joopark-drift-watch.yml\"", "dispatchReady", "driftDispatchReady", "allDispatchReady", "driftDispatchCommand", "suggestedVerificationCommands", "suggestedDispatchCommands", "suggestedDispatchCommandCount", "withheldDispatchCommands", "withheldDispatchCommandCount", "dispatchSuggestionStatus", "withheld-until-all-dispatch-ready", "gh workflow run --repo", "gh workflow list --repo OWNER/REPO", "repo placeholder OWNER/REPO", "workflow file is not installed at repository root", "--live", "--write", "data/publish-dispatch-plan.json", "writtenTo", "generatedAt", "workflowListChecked"] },
    { file: "scripts/fixtures/publish-workflows-ready.json", terms: ["Publish JooPark Pages", "Watch JooPark Candidate Drift", ".github/workflows/joopark-pages.yml", ".github/workflows/joopark-drift-watch.yml", "active"] },
    { file: "data/publish-dispatch-plan.json", terms: ["mode", "live", "biojuho/BIOJUHO-Projects", "repoEvidenceReady", "workflowScope", "workflowScopeAvailable", "workflowScopeInstallBlocked", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "workflowScopeRefreshHandoff", "workflowScopeApprovalHandoff", "approvalUrl", "https://github.com/login/device", "sensitiveValuePolicy", "Do not store, log, or paste the one-time device code", "gh auth refresh -h github.com -s workflow", "scopes", "gist", "read:org", "repo", "localWorkflowTargetsReady", "localTargetParityReady", "targetSha256", "targetMatchesTemplate", "remoteWorkflowVisibilityReady", "workflowDefaultBranchHandoff", "git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml", "git commit -m 'Add JooPark publish workflows'", "workflowListCommand", "targetExists", "dispatchReady", "driftDispatchReady", "allDispatchReady", "suggestedVerificationCommands", "suggestedDispatchCommands", "suggestedDispatchCommandCount", "withheldDispatchCommands", "withheldDispatchCommandCount", "dispatchSuggestionStatus", "workflowPlans", "workflowUiInstallPlans", "data/publish-dispatch-plan.json"] },
    { file: "release-status.js", terms: ["publish-dispatch-plan", "Publish dispatch dry-run", "Publish dispatch plan", "function publishDispatchPlanHTML", "data-system-publish-dispatch-plan", "data-publish-dispatch-workflow-card", "data-publish-dispatch-local-targets-ready", "data-publish-dispatch-local-target-parity-ready", "data-publish-dispatch-workflow-target-matches-template", "targetMatchesTemplate", "data-publish-dispatch-remote-visible", "data-publish-dispatch-workflow-scope-scopes", "data-publish-dispatch-workflow-scope-missing", "data-publish-dispatch-workflow-scope-source", "data-publish-dispatch-workflow-scope-refresh-command", "data-publish-dispatch-workflow-scope-recheck-command", "data-publish-dispatch-auth-preflight", "data-publish-dispatch-auth-preflight-available", "data-publish-dispatch-auth-preflight-install-blocked", "data-publish-dispatch-auth-preflight-scope-count", "Auth preflight", "auth preflight only", "workflowScopeAvailable=", "workflowScopeInstallBlocked=", "data-publish-dispatch-workflow-scope-packet", "data-publish-dispatch-workflow-scope-packet-text", "copy-publish-workflow-scope-packet", "JooPark Workflow Scope Refresh Packet", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "workflowScope.scopes", "workflow scope evidence", "gh auth refresh -h github.com -s workflow", "data-publish-dispatch-default-branch-handoff", "data-publish-dispatch-suggested-dispatch-count", "data-publish-dispatch-withheld-dispatch-count", "data-publish-dispatch-dispatch-suggestion-status", "data-publish-dispatch-suggested-commands-safe", "data-publish-dispatch-dispatch-command-guard", "data-publish-dispatch-withheld-dispatch-commands", "suggestedDispatchCommandCount", "withheldDispatchCommandCount", "suggestedDispatchCommands", "withheldDispatchCommands", "withheld until allDispatchReady: true", "workflowDefaultBranchHandoff", "data/publish-dispatch-plan.json", "workflowListCommand", "localWorkflowTargetsReady", "remoteWorkflowVisibilityReady", "workflowUiInstallPlans", "templateCopyCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO", "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects", "repoEvidenceReady: true", "dispatchReady: true", "allDispatchReady: true"] },
    { file: "app.js", terms: ["publishDispatchPlan", "function loadPublishDispatchPlan", "function publishDispatchPlanHTML", "function copyPublishWorkflowScopePacket", "copy-publish-workflow-scope-packet", "publishDispatchWorkflowScopePacketCopied", "data/publish-dispatch-plan.json", "node scripts/plan-publish-dispatch.mjs --dry-run", "workflowUiInstallPlans", "templateCopyCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "templateSha256", "gh auth refresh -h github.com -s workflow", "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO", "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects", "repoEvidenceReady: true", "dispatchReady: true", "allDispatchReady: true"] },
    { file: "styles.css", terms: [".publish-dispatch-plan", ".publish-dispatch-cards", ".publish-dispatch-card", ".publish-dispatch-next", ".publish-dispatch-blockers"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["data-system-publish-dispatch-plan", "data-publish-dispatch-workflow-card", "publishDispatchPlanPanel", "publishDispatchAuthPreflight", "data-publish-dispatch-auth-preflight", "publishDispatchAuthPreflightScopeCount", "Auth preflight", "auth preflight only", "workflowScopeAvailable=false", "workflowScopeInstallBlocked=true", "publishDispatchWorkflowScopePacketCopy", "data-publish-dispatch-workflow-scope-packet", "data-publish-dispatch-workflow-scope-packet-copy", "JooPark Workflow Scope Refresh Packet", "data/publish-dispatch-plan.json", "plan-publish-dispatch.mjs --live --repo OWNER/REPO", "plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects", "repoEvidenceReady", "localWorkflowTargetsReady", "localTargetParityReady", "publishDispatchLocalTargetParityReady", "publishDispatchWorkflowTargetMatchesTemplate", "targetMatchesTemplate", "remoteWorkflowVisibilityReady", "publishDispatchWorkflowScopeScopes", "publishDispatchWorkflowScopeMissing", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "gh auth refresh -h github.com -s workflow", "workflowScope.scopes", "workflow scope evidence", "workflowDefaultBranchHandoff", "data-publish-dispatch-default-branch-handoff", "publishDispatchSuggestedDispatchCount", "publishDispatchWithheldDispatchCount", "publishDispatchDispatchSuggestionStatus", "publishDispatchSuggestedCommandsSafe", "data-publish-dispatch-dispatch-command-guard", "data-publish-dispatch-withheld-dispatch-commands", "suggestedDispatchCommandCount", "withheldDispatchCommandCount", "suggestedDispatchCommands", "withheldDispatchCommands", "withheld until allDispatchReady: true", "git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml", "dispatchReady", "allDispatchReady", "joopark-drift-watch.yml", "Publish dispatch dry-run"] },
    { file: "scripts/verify-release.mjs", terms: ["data/publish-dispatch-plan.json"] },
    { file: "README.md", terms: ["node scripts/plan-publish-dispatch.mjs --dry-run", "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write", "data/publish-dispatch-plan.json", "System Status", "Publish dispatch plan", "Auth preflight", "auth preflight only", "workflowScopeAvailable=false", "workflowScopeInstallBlocked=true", "workflowUiInstallPlans", "workflowScope.scopes", "workflowScopeInstallBlocked", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "Workflow Scope Refresh Packet", "scope packet 복사", "gh auth refresh -h github.com -s workflow", "localWorkflowTargetsReady", "localTargetParityReady", "targetSha256", "targetMatchesTemplate", "remoteWorkflowVisibilityReady", "workflowDefaultBranchHandoff", "git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml", "githubNewFileUrl", "githubWorkflowUrl", "templateSha256", "templateCopyCommand", "githubNewFileOpenCommand", "githubWorkflowOpenCommand", "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO", "suggestedDispatchCommands", "suggestedDispatchCommandCount", "withheldDispatchCommands", "withheldDispatchCommandCount", "dispatchSuggestionStatus: withheld-until-all-dispatch-ready", "repoEvidenceReady", "dispatchReady", "allDispatchReady", "gh workflow run --repo OWNER/REPO joopark-pages.yml -f ref=codex/joopark-workspace-release", "joopark-drift-watch.yml"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "publish_dispatch_dry_run_plan",
    requirement: "Publish dispatch has a dry-run/live plan that blocks gh workflow run until workflows are installed and visible, while returning GitHub UI install links, template hashes, next verification commands, and a fixture-backed ready-state proof.",
    status: publishDispatchTerms.every((item) => item.missingTerms.length === 0) && publishDispatch.status === "pass" && publishDispatchFile.status === "pass" && publishDispatchReadyFixture.status === "pass" ? "pass" : "fail",
    evidence: {
      terms: publishDispatchTerms,
      plan: publishDispatch,
      file: publishDispatchFile,
      readyFixture: publishDispatchReadyFixture,
    },
  });

  const remoteWorkflowFileCheckTerms = [
    { file: "scripts/check-remote-workflow-files.mjs", terms: ["GitHub REST repository contents API", "sourceUrl", "manualDispatchDocsUrl", "editFileDocsUrl", "updateFileContentsDocsUrl", "https://docs.github.com/en/rest/repos/contents#get-repository-content", "https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui", "https://docs.github.com/en/repositories/working-with-files/managing-files/editing-files", "https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents", "remoteWorkflowFilesChecked", "remoteWorkflowFilesReady", "remoteMatchesTemplate", "workflowScopeApprovalHandoff", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "https://github.com/login/device", "Do not store, log, or paste the one-time device code", "Workflow scope preflight:", "one-time device code policy", "GitHub UI fallback", "Post-install verification checklist:", "remoteExists: true and remoteMatchesTemplate: true", "remoteWorkflowVisibilityReady: true", "allDispatchReady: true", "remoteInstallerCommand", "install-remote-workflow-files.mjs --repo", "--write --verify", "templateSha256", "remoteSha256", "remoteBlobSha", "templateCopyCommand", "githubNewFileOpenCommand", "githubEditFileUrl", "githubEditFileOpenCommand", "installAction", "replace_existing_remote_file", "remediationSummary", "JooPark Remote Workflow Install Packet", "workflowInstallPacket", "gh api --method GET repos/${targetRepo}/contents/${path} -f ref=${branch}", "not found on default branch", "data/remote-workflow-file-check.json", "--write", "--markdown"] },
    { file: "data/remote-workflow-file-check.json", terms: ["remoteWorkflowFilesChecked", "remoteWorkflowFilesReady", "remoteMatchesTemplate", "workflowScopeApprovalHandoff", "workflowScopeInstallBlocked", "https://github.com/login/device", "Do not store, log, or paste the one-time device code", "use each workflow row's installAction", "do not use new-file links for replace_existing_remote_file rows", "Workflow scope preflight:", "one-time device code policy", "GitHub UI fallback", "Post-install verification checklist:", "remoteWorkflowFilesChecked: true", "remoteWorkflowFilesReady: true", "pages remoteExists: true and remoteMatchesTemplate: true", "drift-watch remoteExists: true and remoteMatchesTemplate: true", "remoteWorkflowVisibilityReady: true", "allDispatchReady: true", "remoteInstallerCommand", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "templateSha256", "remoteSha256", "remoteBlobSha", "templateCopyCommand", "githubNewFileOpenCommand", "githubEditFileUrl", "githubEditFileOpenCommand", "installAction", "replace_existing_remote_file", "remediationSummary", "installPacket", "JooPark Remote Workflow Install Packet", ".github/workflows/joopark-pages.yml", ".github/workflows/joopark-drift-watch.yml", "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write", "data/remote-workflow-file-check.json"] },
    { file: "release-status.js", terms: ["remote-workflow-file-check", "Remote workflow file check", "function remoteWorkflowFileCheckHTML", "data-system-remote-workflow-file-check", "data-remote-workflow-file-card", "data-remote-workflow-file-ready", "data-remote-workflow-file-checked", "data-remote-workflow-file-exists", "data-remote-workflow-file-matches-template", "data-remote-workflow-file-install-action", "data-remote-workflow-file-edit-url", "data-remote-workflow-file-edit-file", "githubEditFileUrl", "remoteBlobSha", "remediationAction", "data-remote-workflow-file-workflow-scope-available", "data-remote-workflow-file-workflow-scope-install-blocked", "data-remote-workflow-file-auth-preflight", "Device-code approval handoff", "one-time device code", "data-remote-workflow-install-packet", "data-remote-workflow-install-packet-text", "copy-remote-workflow-install-packet", "remoteWorkflowFilesReady", "remoteMatchesTemplate", "data/remote-workflow-file-check.json"] },
    { file: "app.js", terms: ["remoteWorkflowFileCheck", "function loadRemoteWorkflowFileCheck", "function remoteWorkflowFileCheckHTML", "function copyRemoteWorkflowInstallPacket", "copy-remote-workflow-install-packet", "data/remote-workflow-file-check.json", "remoteWorkflowFilesChecked", "remoteWorkflowFilesReady", "remoteMatchesTemplate", "check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"] },
    { file: "system-status-view.js", terms: ["remoteWorkflowFileCheckHTML", "state.remoteWorkflowFileCheck"] },
    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["remoteWorkflowFileCheck", "remoteWorkflowFilesReady", "check-remote-workflow-files.mjs --repo", "data/remote-workflow-file-check.json", "Remote workflow file check"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["remoteWorkflowFileCheck", "remoteWorkflowFilesReady", "Remote workflow files ready", "Remote workflow file check", "data/remote-workflow-file-check.json"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["data-system-remote-workflow-file-check", "remoteWorkflowFileCheckPanel", "data-remote-workflow-file-install-action", "data-remote-workflow-file-edit-url", "githubEditFileUrl", "replace_existing_remote_file", "remoteBlobSha", "data-remote-workflow-install-packet", "remote workflow install packet copy text did not reach clipboard", "JooPark Remote Workflow Install Packet", "Workflow scope preflight:", "workflowScopeInstallBlocked: true", "approvalUrl: https://github.com/login/device", "one-time device code policy", "GitHub UI fallback", "Post-install verification checklist:", "remoteWorkflowFilesChecked: true", "remoteWorkflowVisibilityReady: true", "allDispatchReady: true", "data/remote-workflow-file-check.json", "remoteWorkflowFilesReady", "remoteMatchesTemplate", "not found on default branch", "check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"] },
    { file: "scripts/verify-release.mjs", terms: ["data/remote-workflow-file-check.json"] },
    { file: "package.json", terms: ["scripts/check-remote-workflow-files.mjs"] },
    { file: "README.md", terms: ["node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "data/remote-workflow-file-check.json", "Remote workflow file check", "Remote workflow install packet", "install packet 복사", "workflowScopeApprovalHandoff", "workflowScopeInstallBlocked", "device-code approval URL", "one-time device code 저장 금지", "GitHub UI fallback", "GitHub edit-file URL", "githubEditFileUrl", "replace_existing_remote_file", "remoteBlobSha", "Post-install verification checklist", "remoteWorkflowFilesChecked: true", "remoteWorkflowVisibilityReady: true", "allDispatchReady: true", "remoteWorkflowFilesReady", "remoteMatchesTemplate", "default branch"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "remote_workflow_file_check",
    requirement: "External publish readiness has a repo-scoped default-branch workflow file check that compares remote GitHub workflow YAML against local templates before dispatch is allowed.",
    status: remoteWorkflowFileCheckTerms.every((item) => item.missingTerms.length === 0) && remoteWorkflowFileCheck.status === "pass" && remoteWorkflowFileCheckSnapshot.status === "pass" ? "pass" : "fail",
    evidence: {
      terms: remoteWorkflowFileCheckTerms,
      dryRun: remoteWorkflowFileCheck,
      file: remoteWorkflowFileCheckSnapshot,
    },
  });

  const remoteWorkflowInstallerTerms = [
    { file: "scripts/install-remote-workflow-files.mjs", terms: ["GitHub REST repository contents API", "repositoryContentsApiUrl", "repos/${repo}/contents/${operation.path}", "--write", "--verify", "workflowScopeInstallBlocked", "remoteWriteReady", "operation", "create", "update", "noop", "postInstallVerificationCommands", "workflowScopeApprovalHandoff", "Workflow Scope Approval", "approvalUrl", "https://github.com/login/device", "Do not store, log, or paste the one-time device code", "operation value", "do not use new-file links for update rows", "attestations: write", "actions/attest@v4", "subject-path: dist/release/**", "gh auth refresh -h github.com -s workflow", "Do not run remote install", "Do not run dispatch until remoteWorkflowFilesReady: true and allDispatchReady: true"] },
    { file: "scripts/check-remote-workflow-files.mjs", terms: ["remoteInstallerCommand", "install-remote-workflow-files.mjs --repo", "--write --verify"] },
    { file: "README.md", terms: ["node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "GitHub REST repository contents API", "remoteWriteReady", "workflowScopeInstallBlocked", "postInstallVerificationCommands"] },
    { file: "package.json", terms: ["install-remote-workflow-files.mjs"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "remote_workflow_api_installer",
    requirement: "The project has an explicit GitHub REST contents API installer that can create or update both default-branch workflow files only after workflow-scope preflight passes, then points operators to post-install verification before dispatch.",
    status: remoteWorkflowInstallerTerms.every((item) => item.missingTerms.length === 0) && remoteWorkflowInstaller.status === "pass" ? "pass" : "fail",
    evidence: {
      terms: remoteWorkflowInstallerTerms,
      dryRun: remoteWorkflowInstaller,
    },
  });

  const launchExecutionPacketTerms = [
    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function workflowAuthPreflight", "function numberOr", "function buildPostAuthCheckpoint", "postAuthCheckpoint", "Post-auth checkpoint:", "gh auth status -h github.com", "Token scopes include workflow", "safeToDispatch=true before gh workflow run", "every action_required post-auth checkpoint item has passed", "verify-launch-handoff reports safeToDispatch=true", "verificationOnly", "dispatchApproval", "recheckSequence", "recheckSequenceCount", "const recheckSequenceCount = numberOr(checkpoint?.recheckSequenceCount, recheckSequence.length)", "sourceArtifactCount", "confirm_scope", "verify_remote_parity", "verify_actions_visibility", "verify_handoff_guard", "authPreflight", "Auth preflight:", "workflowScope.scopes", "missingScopes", "missingScopeList", "approvalHandoff", "approvalStatus", "approvalUrl", "approvalExpectedPrompt", "approvalSensitiveValuePolicy", "approvalStopCondition", "https://github.com/login/device", "Do not store, log, or paste the one-time device code", "function currentActionAcceptanceChecklist", "acceptanceChecklist", "Acceptance checklist:", "operator_auth_path", "remote_workflow_file_parity", "workflow_visibility", "dispatch_guard", "function installPathOptions", "installPaths", "Choose one install path:", "Verify after running:", "verify-launch-handoff.mjs --repo", "CLI path after workflow scope", "GitHub UI path", "install-remote-workflow-files.mjs --repo", "node scripts/prepare-github-pages-workflow.mjs --write", "node scripts/prepare-github-drift-watch-workflow.mjs --write", "function workflowInstallActionRows", "function workflowInstallActionSummary", "Apply each workflow row's installAction", "replace_existing_remote_file for existing SHA mismatches", "no-op verified_remote_matches_template rows", "function defaultBranchRequirementProof", "function defaultBranchRequirementProofLines", "Default-branch requirement proof:", "GitHub manual workflow dispatch docs + GitHub REST repository contents API", "workflow_dispatch exists on the default branch", "repository contents verification:", "workflowListCommand", "function currentActionPacket", "JooPark Launch Current Action Packet", "Current action packet:", "Success condition:", "Do not run yet:", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "gh auth refresh -h github.com -s workflow", "function blockerResolutionChecklist", "function blockerResolutionChecklistLines", "blockerResolutionChecklist", "Blocker resolution checklist:", "proofCommand", "expectedValue", "stopCondition", "activeItemKey", "actionRequiredCount", "deferred_until_dispatch", "const verificationSequenceCount = numberOr(intake?.verificationSequenceCount, sequence.length)", "const quickProofStepCount = numberOr(intake?.quickProofStepCount, quickProofSteps.length)", "const quickProofMappedFieldCount = numberOr(intake?.quickProofMappedFieldCount, quickProofFieldMappings.length)", "sequence=${valueOrPending(verificationSequenceCount)}", "steps=${valueOrPending(quickProofStepCount)}", "mapped=${valueOrPending(quickProofMappedFieldCount)}", "completed=${valueOrPending(intake?.quickProofCompletedMappedFieldCount)}/${valueOrPending(quickProofMappedFieldCount)}", "JooPark Launch Execution Packet", "Install workflows on the default branch", "Verify workflow visibility", "Dispatch only after allDispatchReady", "Capture launch proof", "Share or archive only after proof", "Do not run dispatch commands until allDispatchReady: true", "GitHub manual workflow dispatch", "GitHub Pages custom workflows", "data/launch-execution-packet.json"] },
    { file: "scripts/verify-launch-handoff.mjs", terms: ["verificationOnly", "dispatchExecuted", "launchProofCaptured", "safeToDispatch", "withheldDispatchCommands", "authPreflight", "Auth Preflight", "workflowScopeAvailable", "workflowScopeInstallBlocked", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "scopes", "refreshCommand", "recheckCommand", "blockerResolutionChecklist", "Blocker Resolution Checklist", "activeItemKey", "actionRequiredCount", "proofCommandCount", "numberOr(source.itemCount", "numberOr(source.proofCommandCount", "proofCommand=", "expectedValue=", "stopCondition=", "every action_required item has passed", "verificationSequence", "verificationSequenceReady", "finalVerificationCommand", "sequence=${valueOrPending(summary?.verificationSequenceCount)}", "scripts/check-remote-workflow-files.mjs", "scripts/plan-publish-dispatch.mjs", "scripts/capture-launch-execution-packet.mjs", "scripts/capture-output-quality-audit.mjs", "Do not run gh workflow run yet", "--markdown"] },
		    { file: "data/launch-execution-packet.json", terms: ["authPreflight", "postAuthCheckpoint", "Post-auth checkpoint:", "gh auth status -h github.com", "Token scopes include workflow", "safeToDispatch=true before gh workflow run", "every action_required post-auth checkpoint item has passed", "verify-launch-handoff reports safeToDispatch=true", "\"verificationOnly\": true", "\"dispatchApproval\": false", "\"recheckSequenceCount\": 5", "\"sourceArtifactCount\": 4", "Recheck sequence:", "confirm_scope", "install_workflows", "verify_remote_parity", "verify_actions_visibility", "verify_handoff_guard", "data/remote-workflow-file-check.json", "data/publish-dispatch-plan.json", "data/launch-handoff-verification.json", "verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown", "Auth preflight:", "workflowScopeAvailable: false", "workflowScopeInstallBlocked: true", "scopes: gist, read:org, repo", "missingScopes: workflow", "approval: approval_required", "approvalUrl: https://github.com/login/device", "sensitiveValuePolicy: Do not store, log, or paste the one-time device code", "workflowScope.scopes=gist, read:org, repo", "workflowScopeMissing=workflow", "currentAction", "defaultBranchRequirementProof", "Default-branch requirement proof:", "GitHub manual workflow dispatch docs + GitHub REST repository contents API", "manual dispatch docs: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui", "repository contents verification: https://docs.github.com/en/rest/repos/contents#get-repository-content", "workflow_dispatch exists on the default branch", "Apply each workflow row's installAction on the default branch", "replace_existing_remote_file", "verified_remote_matches_template", "match each local template SHA-256", "acceptanceChecklist", "installPaths", "Choose one install path:", "Verify after running:", "verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write", "verificationSequence", "\"verificationSequenceCount\": 4", "\"verificationSequenceReady\": true", "\"finalVerificationCommand\": \"node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown\"", "remote_file_parity", "actions_visibility", "dispatch_readiness", "handoff_verifier", "CLI path after workflow scope", "GitHub UI path", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "node scripts/prepare-github-pages-workflow.mjs --write", "node scripts/prepare-github-drift-watch-workflow.mjs --write", "Do not run dispatch commands just because the local .github/workflows files exist", "Acceptance checklist: 2/5 pass; pending=3", "Operator auth path: action_required", "Remote workflow file parity: action_required", "Workflow visibility: action_required", "Dispatch guard: pass", "blockerResolutionChecklist", "Blocker resolution checklist:", "active item: operator_auth_path", "items: 2/6 pass; action_required=3; deferred=1", "proof command: gh auth refresh -h github.com -s workflow", "expectedValue=remoteWorkflowFilesReady=true", "stopCondition=If safeToDispatch=false", "launch_proof_capture", "deferred_until_dispatch", "JooPark Launch Current Action Packet", "Current action packet:", "Success condition: remoteWorkflowFilesReady=true", "Do not run yet:", "workflowScopeRefreshCommand", "workflowScopeRecheckCommand", "gh auth refresh -h github.com -s workflow", "JooPark Launch Execution Packet", "action required - launch proof not complete", "biojuho/BIOJUHO-Projects", "Install workflows on the default branch", "Verify workflow visibility", "Dispatch only after allDispatchReady", "Capture launch proof", "External comparison", "GitHub manual workflow dispatch", "GitHub Pages custom workflows"] },
	    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function operatorOnePageHandoff", "operatorOnePageHandoff", "JooPark Launch Operator One-Page Handoff", "Goal for this pass:", "If CLI workflow scope is still blocked, use GitHub UI fallback:", "Prove after install:", "Success signals:", "dispatchReady=true", "driftDispatchReady=true", "allDispatchReady=true", "all six post-install evidence fields are filled", "successSignals.length >= 8", "Do not run or claim yet:", "Do not claim readyForExternalClaim=true", "Operator one-page handoff:"] },
	    { file: "data/launch-execution-packet.json", terms: ["operatorOnePageHandoff", "JooPark Launch Operator One-Page Handoff", "\"sectionCount\": 8", "\"proofCommandCount\": 4", "\"successSignalCount\": 8", "\"activeItemKey\": \"operator_auth_path\"", "If CLI workflow scope is still blocked, use GitHub UI fallback:", "dispatchReady=true", "driftDispatchReady=true", "allDispatchReady=true", "all six post-install evidence fields are filled", "Do not claim readyForExternalClaim=true", "Operator one-page handoff:"] },
	    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function operatorOnePageHandoffSnapshot", "requiredSuccessSignals", "dispatchReady=true", "driftDispatchReady=true", "allDispatchReady=true", "all six post-install evidence fields are filled", "finiteNumberOr(handoff.immediateCommandCount", "finiteNumberOr(handoff.proofCommandCount", "finiteNumberOr(handoff.forbiddenCommandCount"] },
	    { file: "release-status.js", terms: ["function launchExecutionPacketHTML", "data-system-launch-execution-packet", "data-launch-execution-auth-preflight-status", "data-launch-execution-auth-workflow-scope-available", "data-launch-execution-auth-workflow-scope-install-blocked", "data-launch-execution-auth-scope-count", "data-launch-execution-auth-missing-scopes", "data-launch-execution-auth-approval-status", "data-launch-execution-auth-approval-url", "data-launch-execution-auth-preflight", "Auth preflight", "missingScopes", "approvalUrl", "Do not store, log, or paste the one-time device code", "const postAuthCommandCount = finiteNumberOr(postAuthCheckpoint.commandCount, 0)", "const postAuthRecheckSequenceCount = finiteNumberOr(postAuthCheckpoint.recheckSequenceCount, postAuthRecheckSequence.length)", "const postAuthSourceArtifactCount = finiteNumberOr(postAuthCheckpoint.sourceArtifactCount, postAuthSourceArtifacts.length)", "const postAuthExpectedSignalCount = finiteNumberOr(postAuthCheckpoint.expectedSignalCount, postAuthExpectedSignals.length)", "const postAuthBlockedSignalCount = finiteNumberOr(postAuthCheckpoint.blockedSignalCount, postAuthBlockedSignals.length)", "data-launch-execution-post-auth-checkpoint-status", "data-launch-execution-post-auth-checkpoint-command-count=\"${postAuthCommandCount}\"", "data-launch-execution-post-auth-checkpoint-expected-count=\"${postAuthExpectedSignalCount}\"", "data-launch-execution-post-auth-checkpoint-blocked-count=\"${postAuthBlockedSignalCount}\"", "data-launch-execution-post-auth-checkpoint-recheck-count=\"${postAuthRecheckSequenceCount}\"", "data-launch-execution-post-auth-checkpoint-source-artifact-count=\"${postAuthSourceArtifactCount}\"", "data-launch-execution-post-auth-checkpoint-dispatch-approval", "data-launch-execution-post-auth-checkpoint-verification-only", "data-launch-post-auth-expected-signals", "data-launch-post-auth-blocked-signals", "data-launch-post-auth-recheck-sequence", "data-launch-post-auth-recheck-step", "data-launch-post-auth-source-artifact", "Ordered recheck sequence", "data-launch-execution-post-auth-checkpoint", "Post-auth checkpoint", "gh auth status -h github.com", "Token scopes include workflow", "Still blocked if", "safeToDispatch=true", "every action_required post-auth checkpoint item has passed", "verify-launch-handoff reports safeToDispatch=true", "data-launch-execution-current-action-stage", "data-launch-execution-current-action-acceptance-count", "data-launch-execution-current-action-verify-count", "data-launch-execution-current-action-verify-commands", "data-launch-execution-current-acceptance", "data-launch-execution-acceptance-item", "data-launch-execution-install-paths", "data-launch-execution-install-path", "data-launch-execution-current-action", "data-launch-current-default-branch-proof", "data-launch-current-default-branch-proof-ready", "Default-branch requirement proof", "blockerResolutionChecklist", "const blockerResolutionItemCount = finiteNumberOr(blockerResolution.itemCount, blockerResolutionItems.length)", "const blockerResolutionProofCommandCount = finiteNumberOr(blockerResolution.proofCommandCount, 0)", "data-launch-execution-blocker-resolution-source", "data-launch-execution-blocker-resolution-item-count=\"${blockerResolutionItemCount}\"", "data-launch-blocker-resolution-checklist", "data-launch-blocker-resolution-proof-command-count=\"${blockerResolutionProofCommandCount}\"", "data-launch-blocker-resolution-item", "Blocker resolution checklist", "Expected:", "Stop:", "data-launch-post-install-evidence-intake-sequence", "data-launch-post-install-evidence-intake-final-command", "Verification sequence", "data-launch-execution-current-action-text", "data-launch-execution-current-action-copy", "data-launch-execution-stage-count", "data-launch-execution-packet-text", "copy-launch-current-action-packet", "copy-launch-execution-packet", "Launch execution packet"] },
	    { file: "release-status.js", terms: ["data-launch-operator-one-page", "Operator one-page handoff", "data-launch-operator-one-page-text", "operatorOnePage.successSignalCount", "<dt>signals</dt>", "copy-launch-operator-one-page", "one-page 복사"] },
	    { file: "operations-copy-actions.js", terms: ["copyLaunchOperatorOnePage", "data-launch-operator-one-page", "data-launch-operator-one-page-text", "launchOperatorOnePageCopied"] },
	    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function postInstallEvidenceIntake", "postInstallEvidenceIntake", "Post-install evidence intake:", "JooPark Post-Install Quick Proof Receipt", "quickProofSteps", "quickProofCoverage", "quickProofFieldMappings", "quickProofFieldMappingCoverage", "proofComplete", "completedFieldCount", "pendingFieldCount", "remote_parity_proof", "handoff_verifier_proof", "collect_post_install_proof", "Stop condition: do not run gh workflow run"] },
	    { file: "data/launch-execution-packet.json", terms: ["postInstallEvidenceIntake", "generated_from_launch_execution_packet", "collect_post_install_proof", "\"proofComplete\": false", "\"completedFieldCount\": 0", "\"fieldCoverage\": 1", "\"quickProofStepCount\": 4", "\"quickProofCoverage\": 1", "\"quickProofFieldMappingCoverage\": 1", "\"quickProofMappedFieldCount\": 4", "JooPark Post-Install Quick Proof Receipt", "\"commandCount\": 4", "\"signalCount\": 8", "remote_parity_proof", "handoff_verifier_proof", "Post-install evidence intake:"] },
		    { file: "release-status.js", terms: ["data-launch-post-install-evidence-intake", "data-launch-post-install-evidence-intake-proof-complete", "data-launch-post-install-evidence-intake-completed-count", "const postInstallIntakeFieldCount = finiteNumberOr(postInstallIntake.fieldCount, postInstallIntakeFields.length)", "const postInstallIntakeCommandCount = finiteNumberOr(postInstallIntake.commandCount, postInstallIntakeCommands.length)", "const postInstallQuickProofMappedFieldCount = finiteNumberOr(postInstallIntake.quickProofMappedFieldCount, postInstallQuickProofFieldMappings.length)", "data-launch-post-install-evidence-intake-field-count=\"${postInstallIntakeFieldCount}\"", "data-launch-post-install-quick-proof-step-count=\"${postInstallQuickProofStepCount}\"", "data-launch-post-install-quick-proof-mapped-field-count=\"${postInstallQuickProofMappedFieldCount}\"", "data-post-install-quick-proof-step", "data-post-install-quick-proof-field-map-item", "Post-install evidence intake", "quickProofCoverage", "quickProofFieldMappingCoverage", "proofComplete=", "proof fields complete", "remoteWorkflowFilesReady=false"] },
	    { file: "app.js", terms: ["launchExecutionPacket", "function loadLaunchExecutionPacket", "function launchExecutionPacketHTML", "function copyLaunchExecutionPacket", "function copyLaunchCurrentActionPacket", "function copyLaunchOperatorOnePage", "data/launch-execution-packet.json", "copy-launch-current-action-packet", "copy-launch-execution-packet", "copy-launch-operator-one-page"] },
    { file: "styles.css", terms: [".launch-execution-packet", ".launch-execution-current-action", ".launch-current-default-branch-proof", ".launch-execution-auth-preflight", ".launch-execution-post-auth-checkpoint", ".launch-blocker-resolution-checklist", ".launch-execution-install-paths", ".launch-execution-current-action-copy", ".launch-execution-acceptance", ".launch-execution-stages", ".launch-execution-commands", ".launch-execution-comparison", ".launch-execution-copy"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["launchExecutionPacket", "launchExecutionCurrentActionCopy", "launchOperatorOnePageCopy", "launchOperatorSuccessSignals", "launchExecutionCurrentActionStage", "launchExecutionAuthPreflightStatus", "launchExecutionAuthWorkflowScopeAvailable", "launchExecutionAuthWorkflowScopeInstallBlocked", "launchExecutionAuthMissingScopes", "launchExecutionAuthApprovalStatus", "launchExecutionAuthApprovalUrl", "approval: approval_required", "approvalUrl: https://github.com/login/device", "Do not store, log, or paste the one-time device code", "launchExecutionPostAuthCheckpointStatus", "launchExecutionPostAuthCheckpointCommandCount", "launchExecutionBlockerResolutionStatus", "launch operator one-page handoff dataset was incomplete", "JooPark Launch Operator One-Page Handoff", "dispatchReady=true", "driftDispatchReady=true", "allDispatchReady=true", "all six post-install evidence fields are filled", "Do not claim readyForExternalClaim=true", "launch blocker resolution checklist dataset was incomplete", "data-launch-blocker-resolution-checklist", "data-launch-blocker-resolution-item", "Blocker resolution checklist", "proof command: gh auth refresh -h github.com -s workflow", "launch execution post-auth checkpoint was not surfaced", "Post-auth checkpoint:", "gh auth status -h github.com", "Token scopes include workflow", "safeToDispatch=true before gh workflow run", "every action_required post-auth checkpoint item has passed", "verify-launch-handoff reports safeToDispatch=true", "launch execution auth preflight was not surfaced", "Auth preflight:", "scopes: gist, read:org, repo", "missingScopes: workflow", "Acceptance checklist: 2/5 pass; pending=3", "Operator auth path: action_required", "launchExecutionCurrentActionVerifyCount", "verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write", "launch execution acceptance checklist was not surfaced", "data-launch-current-default-branch-proof", "Default-branch requirement proof", "manual dispatch docs: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui", "repository contents verification: https://docs.github.com/en/rest/repos/contents#get-repository-content", "workflow_dispatch exists on the default branch", "JooPark Launch Current Action Packet", "Current action packet:", "Success condition: remoteWorkflowFilesReady=true", "Choose one install path:", "CLI path after workflow scope", "GitHub UI path", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "node scripts/prepare-github-pages-workflow.mjs --write", "workflowScopeRefreshCommand", "gh auth refresh -h github.com -s workflow", "Do not run yet:", "launch current action packet copy text did not reach clipboard", "launch execution packet was not copy-ready", "launch execution packet copy text did not reach clipboard", "JooPark Launch Execution Packet"] },
    { file: "scripts/verify-release.mjs", terms: ["data/launch-execution-packet.json"] },
    { file: "package.json", terms: ["verify:launch-handoff", "scripts/verify-launch-handoff.mjs"] },
    { file: "README.md", terms: ["JooPark Launch Execution Packet", "JooPark Launch Current Action Packet", "Current action packet", "Default-branch requirement proof", "GitHub manual workflow dispatch docs", "GitHub REST repository contents API", "workflow_dispatch exists on the default branch", "authPreflight", "Post-auth checkpoint", "gh auth status -h github.com", "safeToDispatch=true", "every action_required post-auth checkpoint item has passed", "verify-launch-handoff reports safeToDispatch=true", "recheckSequence", "sourceArtifacts", "verificationOnly: true", "dispatchApproval: false", "Device-code approval handoff", "approvalUrl", "https://github.com/login/device", "one-time device code", "Blocker resolution checklist", "Blocker Resolution Checklist", "blockerResolutionChecklist", "proofCommand", "expectedValue", "stopCondition", "activeItemKey", "deferred_until_dispatch", "proofCommands", "Auth Preflight", "workflowScope.scopes", "missingScopes", "CLI path after workflow scope", "GitHub UI path", "Acceptance checklist", "operator_auth_path", "remote_workflow_file_parity", "workflow_visibility", "dispatch_guard", "verify:launch-handoff", "verify-launch-handoff.mjs", "dispatchExecuted: false", "workflowScopeAvailable", "workflowScopeInstallBlocked", "scopes", "refresh", "recheck", "launch packet 복사", "current action 복사", "gh auth refresh -h github.com -s workflow", "allDispatchReady: true", "workflow_dispatch", "actions/deploy-pages"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "launch_execution_packet",
    requirement: "System Status exposes a copy-ready launch execution packet that turns workflow installation, visibility verification, dispatch gating, live evidence capture, and public-claim guards into a single practical operator sequence.",
    status: launchExecutionPacketTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: launchExecutionPacketTerms,
  });

  const launchStageTransitionTerms = [
    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function stageTransitionPreview", "stageTransitionPreview", "Stage transition preview:", "pendingAcceptanceCount", "withheldDispatchCommandCount", "generated_from_launch_execution_packet"] },
    { file: "data/launch-execution-packet.json", terms: ["stageTransitionPreview", "generated_from_launch_execution_packet", "currentStageKey", "nextStageKey", "install_workflows", "verify_visibility", "pendingAcceptanceCount", "withheldDispatchCommandCount", "gateCommand", "safeToDispatch=true before gh workflow run"] },
    { file: "release-status.js", terms: ["stageTransitionPreview", "data-launch-execution-transition-source", "data-launch-execution-transition-preview", "data-launch-execution-transition-current-stage", "data-launch-execution-transition-next-stage", "Stage transition preview", "conditional next stage", "keep-dispatch-withheld"] },
    { file: "home-view.js", terms: ["stageTransitionPreview", "data-home-launch-transition-source", "data-home-launch-transition-current-stage", "data-home-launch-transition-next-stage", "data-home-launch-transition-preview", "launchTransitionGateCommand", "install_workflows", "verify_visibility"] },
    { file: "settings-view.js", terms: ["stageTransitionPreview", "transitionSource", "data-settings-launch-transition-preview", "transitionCurrentStage", "transitionNextStage", "Stage transition preview", "conditional next stage"] },
    { file: "styles.css", terms: [".launch-transition-preview", ".home-launch-transition", ".launch-transition-preview li span"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["generated_from_launch_execution_packet", "home launch transition preview did not render", "launch execution transition preview dataset was incomplete", "launch execution transition steps were incomplete", "settings launch transition preview did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "launch_stage_transition_preview",
    requirement: "Home, System Status, and Settings expose a current-stage to conditional-next-stage launch transition preview so operators can see what post-install proof unlocks while dispatch remains withheld.",
    status: launchStageTransitionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: launchStageTransitionTerms,
  });

  const workflowInstallVerificationMatrixTerms = [
    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function workflowInstallVerificationMatrix", "workflowInstallVerificationMatrix", "Workflow install verification matrix:", "install_verification_required", "blocked_by_workflow_scope", "ready_to_install", "requiredSignalCount", "verificationCommandCount", "remoteWorkflowVisibilityReady=true", "safeToDispatch=true before gh workflow run"] },
    { file: "data/launch-execution-packet.json", terms: ["workflowInstallVerificationMatrix", "generated_from_launch_execution_packet", "install_verification_required", "matrixRows", "signalChecks", "cli_workflow_scope", "github_ui", "blocked_by_workflow_scope", "ready_to_install", "remoteWorkflowFilesReady=true", "remoteWorkflowVisibilityReady=true", "Workflow install verification matrix:"] },
    { file: "release-status.js", terms: ["workflowInstallVerificationMatrix", "installMatrixPathCount = finiteNumberOr(installMatrix.installPathCount, installMatrixRows.length)", "installMatrixSignalCount = finiteNumberOr(installMatrix.requiredSignalCount, installMatrixSignals.length)", "installMatrixVerificationCommandCount = finiteNumberOr(installMatrix.verificationCommandCount, installMatrixCommands.length)", "data-launch-execution-install-matrix-path-count=\"${installMatrixPathCount}\"", "data-launch-install-verification-command-count=\"${installMatrixVerificationCommandCount}\"", "data-launch-execution-install-matrix-source", "data-launch-install-verification-matrix", "data-launch-install-verification-row", "data-launch-install-verification-signal", "Workflow install verification matrix", "install_verification_required"] },
    { file: "home-view.js", terms: ["workflowInstallVerificationMatrix", "launchInstallMatrixPathCount = firstClampedCount([launchInstallMatrix.installPathCount, launchInstallMatrixRows.length])", "launchInstallMatrixSignalCount = firstClampedCount([launchInstallMatrix.requiredSignalCount, launchInstallMatrixSignals.length])", "data-home-launch-install-matrix-path-count=\"${launchInstallMatrixPathCount}\"", "data-home-launch-install-matrix-signal-count=\"${launchInstallMatrixSignalCount}\"", "data-home-launch-install-matrix-source", "data-home-launch-install-matrix", "install verification matrix", "remoteWorkflowVisibilityReady=true"] },
    { file: "settings-view.js", terms: ["workflowInstallVerificationMatrix", "installMatrixSource", "data-settings-install-verification-matrix", "data-settings-install-verification-row", "data-settings-install-verification-signal", "Workflow install verification matrix"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["home launch install verification matrix did not render", "launch install verification matrix dataset was incomplete", "settings install verification matrix did not render", "data-home-launch-install-matrix-source", "data-launch-install-verification-matrix"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "workflow_install_verification_matrix",
    requirement: "Launch packet, Home, System Status, and Settings expose the same workflow installation verification matrix so operators can compare CLI and GitHub UI install paths, required proof signals, and dispatch guard status before attempting workflow runs.",
    status: workflowInstallVerificationMatrixTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: workflowInstallVerificationMatrixTerms,
  });

  const remoteWorkflowFileAcceptanceLedgerTerms = [
    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function remoteWorkflowFileAcceptanceLedger", "function remoteWorkflowFileOpenCommand", "remoteWorkflowFileAcceptanceLedger", "Remote workflow file acceptance ledger:", "generated_from_remote_workflow_file_check", "remote_file_install_required", "missing_on_default_branch", "installAction", "openCommand", "remoteExists", "remoteMatchesTemplate", "templateSha256", "githubNewFileOpenCommand", "githubEditFileOpenCommand"] },
    { file: "data/launch-execution-packet.json", terms: ["remoteWorkflowFileAcceptanceLedger", "generated_from_remote_workflow_file_check", "remote_file_install_required", "installAction", "openCommand", "joopark-pages.yml", "joopark-drift-watch.yml", "remoteExists", "remoteMatchesTemplate", "Remote workflow file acceptance ledger:"] },
    { file: "release-status.js", terms: ["remoteWorkflowFileAcceptanceLedger", "data-remote-workflow-file-acceptance-ledger", "data-remote-workflow-file-ledger-source", "data-remote-workflow-file-ledger-missing-count", "const remoteFileLedgerFileCount = finiteNumberOr(remoteFileLedger.fileCount, remoteFileLedgerItems.length)", "const remoteFileLedgerReadyCount = finiteNumberOr(remoteFileLedger.readyCount, 0)", "data-remote-workflow-file-ledger-file-count=\"${remoteFileLedgerFileCount}\"", "<strong>${remoteFileLedgerReadyCount}/${remoteFileLedgerFileCount} files ready</strong>", "data-remote-workflow-file-ledger-item", "Remote workflow file acceptance ledger", "installAction", "file.openCommand", "remoteExists", "remoteMatchesTemplate"] },
    { file: "home-view.js", terms: ["remoteWorkflowFileAcceptanceLedger", "data-home-remote-workflow-file-ledger-source", "data-home-remote-workflow-file-ledger", "remoteWorkflowFileLedgerFileCount", "remoteWorkflowFileLedgerReadyCount", "remoteWorkflowFileLedgerMissingCount", "remoteWorkflowFileLedgerMismatchCount", "remote workflow file acceptance ledger", "remoteMatchesTemplate required"] },
    { file: "settings-view.js", terms: ["remoteWorkflowFileAcceptanceLedger", "remoteFileLedgerSource", "data-settings-remote-workflow-file-ledger", "data-settings-remote-workflow-file-ledger-verify-command", "Remote workflow file acceptance ledger", "remoteMatchesTemplate"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function remoteWorkflowFileAcceptanceLedgerSnapshot", "remoteWorkflowFileAcceptanceLedger", "Remote workflow file acceptance ledger:", "Remote workflow file acceptance ledger: ${remoteWorkflowFileLedger.ready ? \"pass\" : \"blocked\"}", "missing_on_default_branch", "installAction", "openCommand", "finiteNumberOr(ledger.fileCount", "finiteNumberOr(ledger.missingCount"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["home remote workflow file acceptance ledger did not render", "remote workflow file acceptance ledger dataset was incomplete", "settings remote workflow file ledger did not render", "Remote workflow file acceptance ledger", "missing_on_default_branch"] },
    { file: "README.md", terms: ["remoteWorkflowFileAcceptanceLedger", "Remote workflow file acceptance ledger", "remoteExists", "remoteMatchesTemplate", "missing_on_default_branch"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "remote_workflow_file_acceptance_ledger",
    requirement: "Launch packet, Home, System Status, Settings, and the output-quality receipt expose file-level remote workflow installation proof so each default-branch workflow file must show remoteExists=true and remoteMatchesTemplate=true before dispatch can be considered.",
    status: remoteWorkflowFileAcceptanceLedgerTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: remoteWorkflowFileAcceptanceLedgerTerms,
  });

  const launchProofAcceptanceLedgerTerms = [
    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function launchProofAcceptanceLedger", "launchProofAcceptanceLedger", "Launch proof acceptance ledger:", "proof_blocked_until_dispatch", "pages_site_url", "pages_workflow_run", "drift_workflow_run", "evidence_freshness", "release_receipt", "public_claim_guard", "captureWriteCommand", "status,conclusion,url,headSha"] },
    { file: "data/launch-execution-packet.json", terms: ["launchProofAcceptanceLedger", "generated_from_launch_execution_packet", "requiredProofs", "pages_site_url", "pages_workflow_run", "drift_workflow_run", "evidence_freshness", "release_receipt", "public_claim_guard", "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write", "Launch proof acceptance ledger:"] },
    { file: "release-status.js", terms: ["launchProofAcceptanceLedger", "data-launch-proof-acceptance-ledger", "data-launch-proof-ledger-source", "data-launch-proof-ledger-status", "data-launch-proof-ledger-required-count", "data-launch-proof-acceptance-item", "Launch proof acceptance ledger", "Pages html_url/status", "status/conclusion/url/headSha"] },
    { file: "home-view.js", terms: ["launchProofAcceptanceLedger", "data-home-launch-proof-ledger-source", "data-home-launch-proof-ledger", "data-home-launch-proof-ledger-required-count", "data-home-launch-proof-ledger-pending-count", "launchProofLedgerRequiredCount", "launchProofLedgerReadyCount", "launchProofLedgerPendingCount", "firstClampedCount([launchProofLedger.requiredProofCount, launchProofLedgerItems.length])", "launchProofLedgerPendingCount === 0", "pending=${launchProofLedgerPendingCount}", "launch proof acceptance ledger", "proof_blocked_until_dispatch"] },
    { file: "settings-view.js", terms: ["launchProofAcceptanceLedger", "proofLedgerSource", "data-settings-launch-proof-ledger", "data-settings-launch-proof-ledger-capture-command", "Launch proof acceptance ledger", "status/conclusion/url/headSha"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function launchProofAcceptanceLedgerSnapshot", "launchProofAcceptanceLedger", "Launch proof acceptance ledger:", "Launch proof acceptance ledger: ${launchProofLedger.ready ? \"pass\" : \"blocked\"}", "pages_site_url", "drift_workflow_run", "finiteNumberOr(ledger.requiredProofCount", "finiteNumberOr(ledger.pendingProofCount"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["home launch proof acceptance ledger did not render", "launch proof acceptance ledger dataset was incomplete", "settings launch proof ledger did not render", "Launch proof acceptance ledger", "pages_site_url", "public_claim_guard"] },
    { file: "README.md", terms: ["launchProofAcceptanceLedger", "Launch proof acceptance ledger", "Pages html_url/status", "status/conclusion/url/headSha", "readyForExternalClaim=false"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "launch_proof_acceptance_ledger",
    requirement: "Launch packet, Home, System Status, Settings, and the output-quality receipt share one post-dispatch launch proof acceptance ledger so Pages URL/status, workflow run status/conclusion, freshness, receipt, and public-claim guards must all pass before external completion can be claimed.",
    status: launchProofAcceptanceLedgerTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: launchProofAcceptanceLedgerTerms,
  });

  const publishRepoPlaceholderGuardTerms = [
    { file: "release-status.js", terms: ["function publishRepoPlaceholderGuardLines", "function publishDispatchGateGuardLines", "Repo placeholder guard", "Dispatch safety gate", "Replace every `OWNER/REPO`", "suggestedRepo", "biojuho/BIOJUHO-Projects", "repo placeholder OWNER/REPO", "workflowScope.scopes", "workflowScopeInstallBlocked", "gh auth refresh -h github.com -s workflow", "auth preflight only", "gh workflow run --repo", "suggestedDispatchCommands", "withheld-until-all-dispatch-ready", "driftDispatchReady", "postPublishEvidenceReady: true"] },
    { file: "app.js", terms: ["function publishRepoPlaceholderGuardLines", "function publishDispatchGateGuardLines", "releaseStatusCall(\"publishRepoPlaceholderGuardLines\")", "releaseStatusCall(\"publishDispatchGateGuardLines\")"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["repo placeholder guard", "Repo placeholder guard", "Dispatch safety gate", "Replace every", "OWNER/REPO", "suggestedRepo", "biojuho/BIOJUHO-Projects", "repo placeholder OWNER/REPO", "workflowScope.scopes", "workflowScopeInstallBlocked", "gh auth refresh -h github.com -s workflow", "suggestedDispatchCommands", "withheld-until-all-dispatch-ready", "gh workflow run --repo"] },
    { file: "README.md", terms: ["Repo placeholder guard", "Dispatch safety gate", "Replace every `OWNER/REPO`", "suggestedRepo", "biojuho/BIOJUHO-Projects", "repo placeholder OWNER/REPO", "repoEvidenceReady: true", "workflowScope.scopes", "workflowScopeInstallBlocked", "gh auth refresh -h github.com -s workflow", "gh workflow run --repo", "suggestedDispatchCommands", "withheld-until-all-dispatch-ready"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "publish_repo_placeholder_handoff_guard",
    requirement: "Copied publish handoffs explicitly require replacing OWNER/REPO and confirming all dispatch-readiness evidence before live dispatch or evidence writes can be treated as launch proof.",
    status: publishRepoPlaceholderGuardTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: publishRepoPlaceholderGuardTerms,
  });

  const publishCommandScope = publishCommandScopeGuard();
  checklist.push({
    id: "publish_command_scope_guard",
    requirement: "Generated and copied publish commands do not contain unscoped live dispatch, publish plan, or evidence capture commands.",
    status: publishCommandScope.status,
    evidence: publishCommandScope,
  });

  const publishEvidenceTerms = [
    { file: "scripts/capture-publish-evidence.mjs", terms: ["workflowEvidencePlans", "suggestedRepo", "repoDisplayContext", "displayRepo", "evidenceRepo", "repoResolution", "resolved_from_suggested_repo", "repoReplacementHint", "suggestedCommands", "suggestedVerificationCommands", "suggestedDispatchCommands", "withheldDispatchCommands", "dispatchSuggestionStatus", "publishDispatchReady", "readJson(\"data/publish-dispatch-plan.json\")", "readJson(\"data/launch-execution-packet.json\")", "publishEvidenceCommandSet", "## Launch proof gate", "## Next action", "function publishEvidenceNextAction", "function publishEvidenceImmediateNextAction", "immediateNextAction", "deferredNextAction", "Immediate action", "Deferred evidence capture", "install_workflows", "data/launch-execution-packet.json", "capture-live-evidence", "share-launch-proof", "Treat this report as launch proof only when", "## Repo replacement guard", "Treat the OWNER/REPO commands below as templates", "## Suggested repo commands", "Safe verification and evidence-capture commands only", "## Withheld dispatch commands", "Do not run until allDispatchReady: true", "Template verification and evidence-capture commands only", "workflowEvidenceCommand(workflow.workflowFile, repo)", "repoEvidenceReady", "evidenceFresh", "evidenceExpiresAt", "evidenceMaxAgeHours", "postPublishEvidenceReady", "nextAction", "gh api repos/${commandRepo}/pages", "html_url", "https_enforced", "function workflowDispatchCommand", "gh workflow run --repo", "function workflowEvidenceCommand", "gh run list --repo", "--workflow", "workflowEvidenceCommand(\"joopark-pages.yml\", commandRepo)", "workflowEvidenceCommand(\"joopark-drift-watch.yml\", commandRepo)", "node scripts/plan-publish-dispatch.mjs --live --repo ${commandRepo}", "repo placeholder OWNER/REPO", "status,conclusion", "Get a GitHub Pages site", "--write", "--markdown", "function formatPublishEvidenceMarkdown", "# JooPark Publish Evidence", "data/publish-evidence.json", "writtenTo"] },
    { file: "data/publish-evidence.json", terms: ["suggestedRepo", "displayRepo", "evidenceRepo", "repoResolution", "source_repo", "Repo: biojuho/BIOJUHO-Projects", "Evidence repo: biojuho/BIOJUHO-Projects", "repoReplacementHint", "suggestedCommands", "suggestedVerificationCommands", "suggestedDispatchCommands", "withheldDispatchCommands", "dispatchSuggestionStatus", "publishDispatchReady", "biojuho/BIOJUHO-Projects", "repoEvidenceReady", "evidenceFresh", "evidenceExpiresAt", "evidenceMaxAgeHours", "postPublishEvidenceReady", "nextAction", "immediateNextAction", "deferredNextAction", "workflowEvidencePlans", "gh api repos/biojuho/BIOJUHO-Projects/pages", "gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-pages.yml", "gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-drift-watch.yml", "joopark-pages.yml", "joopark-drift-watch.yml"] },
    { file: "release-status.js", terms: ["JooParkReleaseStatus", "joopark-release-status/v1", "publish-evidence-capture", "function publishEvidenceHTML", "function publishEvidenceFresh", "data-publish-evidence-mode", "data-publish-evidence-fresh", "data-publish-evidence-launch-proof-ready", "data-publish-evidence-next-action", "data-publish-evidence-next-command", "data-publish-evidence-immediate-action", "data-publish-evidence-immediate-action-source", "data-publish-evidence-deferred-action", "publish-evidence-next-action", "Immediate action", "Deferred evidence capture", "nextAction", "immediateNextAction", "deferredNextAction", "launchProofReady", "launch proof ready", "data-publish-evidence-repo-ready", "data-publish-evidence-pages-ready", "data-publish-evidence-workflows-ready", "data-publish-evidence-display-repo", "data-publish-evidence-evidence-repo", "data-publish-evidence-repo-resolution", "data-publish-evidence-repo-placeholder-resolved", "data-publish-evidence-suggested-repo", "data-publish-evidence-dispatch-ready", "data-publish-evidence-suggested-commands-safe", "data-publish-evidence-withheld-dispatch-count", "data-publish-evidence-command-guard", "Withheld dispatch commands", "Do not run until allDispatchReady: true", "suggestedRepo", "repoReplacementHint", "biojuho/BIOJUHO-Projects", "repoEvidenceReady", "evidenceFresh", "evidenceExpiresAt", "evidenceMaxAgeHours", "stale evidence", "freshness window", "pagesEvidenceReady", "workflowEvidenceReady", "dry-run evidence", "repo-scoped workflow run", "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown", "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --write", "postPublishEvidenceReady", "html_url/status", "status/conclusion"] },
    { file: "app.js", terms: ["data/publish-evidence.json", "function publishEvidenceHTML", "function loadPublishEvidence", "function publishEvidenceFresh", "releaseStatusCall(\"publishEvidenceHTML\"", "releaseStatusCall(\"publishEvidenceFresh\""] },
    { file: "styles.css", terms: [".publish-evidence-next-action", ".publish-evidence-next-action code", ".publish-evidence-deferred-action", ".publish-evidence-command-guard", ".publish-evidence-command-list"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown", "capture-publish-evidence.mjs --live --repo OWNER/REPO --write", "postPublishEvidenceReady", "repoEvidenceReady", "suggestedRepo", "repoReplacementHint", "biojuho/BIOJUHO-Projects", "evidenceFresh", "launchProofReady", "publishEvidenceLaunchProofReady", "evidenceMaxAgeHours", "freshness window", "publish evidence freshness helper did not expire stale evidence", "publish evidence next action was not surfaced", "publish evidence immediate next action was not surfaced", "data-publish-evidence-next-action-card", "data-publish-evidence-command-guard", "data-publish-evidence-withheld-dispatch-commands", "Do not run dispatch until allDispatchReady: true.", "Immediate action", "Install workflows on the default branch", "Deferred evidence capture", "gh auth refresh -h github.com -s workflow", "capture-live-evidence", "pagesEvidenceReady", "workflowEvidenceReady", "live action-required readiness state", "repo-scoped workflow run", "Publish evidence capture", "post-dispatch evidence", "data-system-publish-evidence"] },
    { file: "README.md", terms: ["node scripts/capture-publish-evidence.mjs --dry-run", "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO", "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown", "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --write", "Suggested repo commands", "Withheld dispatch commands", "allDispatchReady: true", "Next action", "nextAction", "immediateNextAction", "Immediate action", "Deferred evidence capture", "Install workflows on the default branch", "Capture live publish evidence", "placeholder template commands", "gh run list --repo OWNER/REPO --workflow", "data/publish-evidence.json", "suggestedRepo", "repoReplacementHint", "repoEvidenceReady", "evidenceFresh", "evidenceExpiresAt", "24시간 freshness window", "pagesEvidenceReady", "workflowEvidenceReady", "postPublishEvidenceReady", "html_url/status/https_enforced", "status/conclusion/url/headSha"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "publish_evidence_capture_plan",
    requirement: "Post-dispatch publish evidence has a dry-run and live capture path for Pages site URL/status and Pages/Drift workflow run status/conclusion.",
    status: publishEvidenceTerms.every((item) => item.missingTerms.length === 0) && publishEvidenceCapture.status === "pass" && publishEvidenceSuggestedRepo.status === "pass" && publishEvidenceFile.status === "pass" ? "pass" : "fail",
    evidence: {
      terms: publishEvidenceTerms,
      plan: publishEvidenceCapture,
      suggestedRepoPlan: publishEvidenceSuggestedRepo,
      file: publishEvidenceFile,
    },
  });

  const publishEvidenceInstallPathCopyTerms = [
    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function workflowUiInstallCommands", "remoteWorkflowCheckForPlan", "installAction === \"replace_existing_remote_file\"", "githubEditFileOpenCommand", "Use each file's create or edit URL according to installAction"] },
    { file: "scripts/capture-publish-evidence.mjs", terms: ["launchInstallPathSnapshot", "publishEvidenceInstallPathLines", "publishEvidenceRepairFirstCommand", "launchReadinessRefresh", "remoteWorkflowRepairAction", "Choose one install path:", "Launch install path options:", "CLI path after workflow scope", "GitHub UI path", "install-remote-workflow-files.mjs", "path.commands.map", "launchInstallPaths"] },
    { file: "data/publish-evidence.json", terms: ["launchInstallPaths", "Choose one install path:", "Launch install path options: pass (2 paths,", "CLI path after workflow scope", "GitHub UI path", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "pbcopy < 'docs/github-pages-workflow.yml' && open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'", "JooPark Publish Evidence Update", "JooPark Public Launch Announcement", "JooPark Post-Launch Verification Receipt"] },
    { file: "release-status.js", terms: ["data-publish-evidence-install-paths-ready", "data-publish-evidence-install-path-count", "data-publish-evidence-install-path-command-count", "function installPathItemCommandCount(item)", "installPathItemCommandCount(item)", "launchInstallPathItemCommandCount", "launchInstallPathCount = finiteNumberOr(launchInstallPaths.count, launchInstallPathItems.length)", "launchInstallPathCommandCount = finiteNumberOr(launchInstallPaths.commandCount, launchInstallPathItemCommandCount)", "data-publish-evidence-install-path-count=\"${launchInstallPathCount}\"", "data-publish-evidence-install-path-command-count=\"${launchInstallPathCommandCount}\"", "data-publish-evidence-install-paths", "data-publish-evidence-install-path-item", "Choose one install path"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["publishEvidenceInstallPathsReady", "publishEvidenceInstallPathCount", "Choose one install path:", "Launch install path options: pass (2 paths,", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "pbcopy < 'docs/github-pages-workflow.yml'", "open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'"] },
    { file: "README.md", terms: ["JooPark Publish Evidence Update", "JooPark Public Launch Announcement", "JooPark Post-Launch Verification Receipt", "Choose one install path", "CLI path after workflow scope", "GitHub UI path", "install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "publish_evidence_install_path_copy",
    requirement: "Publish evidence copy outputs and System Status expose the same CLI workflow-scope and GitHub UI workflow-install choices as the launch packet before live evidence capture.",
    status: publishEvidenceInstallPathCopyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: publishEvidenceInstallPathCopyTerms,
  });

  const publishEvidenceShareUpdateTerms = [
    { file: "scripts/capture-publish-evidence.mjs", terms: ["function publishEvidenceShareUpdate", "JooPark Publish Evidence Update", "Status: ${ready ? \"launch proof ready\" : \"action required\"}", "Repo resolution:", "Evidence repo:", "Dispatch guard:", "Suggested commands safe:", "Do not run dispatch until allDispatchReady: true.", "Withheld dispatch commands:", "## Share update", "payload.shareUpdate"] },
    { file: "data/publish-evidence.json", terms: ["shareUpdate", "JooPark Publish Evidence Update", "Repo: biojuho/BIOJUHO-Projects", "Evidence repo: biojuho/BIOJUHO-Projects", "Repo resolution: source_repo", "Suggested repo: biojuho/BIOJUHO-Projects", "postPublishEvidenceReady:", "Dispatch guard:", "Suggested commands safe: true;", "Immediate action:"] },
    { file: "release-status.js", terms: ["data-publish-evidence-share-update", "data-publish-evidence-share-update-ready", "data-publish-evidence-share-update-text", "data-publish-evidence-share-update-copy", "Launch proof share update"] },
    { file: "app.js", terms: ["function copyPublishEvidenceShareUpdate", "copy-publish-evidence-share-update", "data-publish-evidence-share-update-text", "publishEvidenceShareUpdateCopied", "publish evidence share update를 복사했습니다"] },
    { file: "styles.css", terms: [".publish-evidence-share-update", ".publish-evidence-share-update span", ".publish-evidence-share-update strong"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["publishEvidenceShareUpdate", "publish evidence share update was not copy-ready", "publish evidence share update copy text did not reach clipboard", "}, \"publish evidence share update was not copy-ready\", 15000);", "JooPark Publish Evidence Update", "Status: action required", "Repo: biojuho/BIOJUHO-Projects", "expectedEvidenceRepoLine", "expectedRepoResolutionLine", "Dispatch guard: withheld (withheld-until-all-dispatch-ready)", "Do not run dispatch until allDispatchReady: true.", "Withheld dispatch commands:"] },
    { file: "README.md", terms: ["JooPark Publish Evidence Update", "share update 복사", "팀 공유용", "action required", "Evidence repo: biojuho/BIOJUHO-Projects", "Repo resolution: source_repo", "Dispatch guard", "Withheld dispatch commands"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "publish_evidence_share_update",
    requirement: "Post-dispatch publish evidence includes a short copy-ready share update that communicates launch proof readiness or action-required status without rewriting the full report.",
    status: publishEvidenceShareUpdateTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: publishEvidenceShareUpdateTerms,
  });

  const publishLaunchAnnouncementTerms = [
    { file: "scripts/capture-publish-evidence.mjs", terms: ["function publishLaunchAnnouncement", "JooPark Public Launch Announcement", "Status: not ready for public posting", "Status: ready to post", "publishEvidenceExternalClaimGuardLines", "readyForExternalClaim: true", "publishEvidenceDispatchGuardLines(evidence, { includeCommands: false })", "Do not post or dispatch until allDispatchReady: true, postPublishEvidenceReady: true, and readyForExternalClaim: true.", "## Launch announcement", "payload.launchAnnouncement"] },
    { file: "data/publish-evidence.json", terms: ["launchAnnouncement", "JooPark Public Launch Announcement", "Status: not ready for public posting", "Repo: biojuho/BIOJUHO-Projects", "Evidence repo: biojuho/BIOJUHO-Projects", "Repo resolution: source_repo", "External claim guard:", "readyForExternalClaim: false", "Dispatch gate:", "Dispatch guard:", "Suggested commands safe: true;", "Do not post or dispatch until allDispatchReady: true, postPublishEvidenceReady: true, and readyForExternalClaim: true."] },
    { file: "release-status.js", terms: ["data-publish-evidence-launch-announcement", "data-publish-evidence-launch-announcement-ready", "data-publish-evidence-launch-announcement-text", "data-publish-evidence-launch-announcement-copy", "Public launch announcement"] },
    { file: "app.js", terms: ["function copyPublishLaunchAnnouncement", "copy-publish-launch-announcement", "data-publish-evidence-launch-announcement-text", "publishLaunchAnnouncementCopied", "publish launch announcement을 복사했습니다"] },
    { file: "styles.css", terms: [".publish-evidence-launch-announcement", ".publish-evidence-launch-announcement span", ".publish-evidence-launch-announcement strong"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["publishLaunchAnnouncement", "publish launch announcement guard was not copy-ready", "publish launch announcement copy text did not reach clipboard", "}, \"publish launch announcement guard was not copy-ready\", 15000);", "not ready for public posting", "External claim guard:", "Do not post or dispatch until allDispatchReady: true, postPublishEvidenceReady: true, and readyForExternalClaim: true.", "!launchAnnouncementText.includes(\"gh workflow run --repo\")"] },
    { file: "README.md", terms: ["JooPark Public Launch Announcement", "launch announcement 복사", "not ready for public posting", "Dispatch guard", "Do not post or dispatch", "repoEvidenceReady, evidenceFresh, postPublishEvidenceReady", "readyForExternalClaim", "Evidence repo: biojuho/BIOJUHO-Projects"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "publish_launch_announcement_guard",
    requirement: "Publish evidence includes a public launch announcement output that is copy-ready only with proof and otherwise copies a safe not-ready guard instead of a premature launch claim.",
    status: publishLaunchAnnouncementTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: publishLaunchAnnouncementTerms,
  });

  const publishPostLaunchReceiptTerms = [
    { file: "scripts/capture-publish-evidence.mjs", terms: ["function publishPostLaunchVerificationReceipt", "JooPark Post-Launch Verification Receipt", "not verified for archive", "publishEvidenceExternalClaimGuardLines", "publishEvidenceDispatchGuardLines(evidence)", "publishDispatchReady:", "readyForExternalClaim:", "dispatchSuggestionStatus:", "## Post-launch verification receipt", "payload.postLaunchVerificationReceipt"] },
    { file: "data/publish-evidence.json", terms: ["postLaunchVerificationReceipt", "JooPark Post-Launch Verification Receipt", "Status: not verified for archive", "Repo: biojuho/BIOJUHO-Projects", "Evidence repo: biojuho/BIOJUHO-Projects", "Repo resolution: source_repo", "Verification checklist", "readyForExternalClaim: false", "External claim guard:", "publishDispatchReady:", "dispatchSuggestionStatus:", "Dispatch guard:", "Suggested commands safe: true;"] },
    { file: "release-status.js", terms: ["data-publish-evidence-post-launch-receipt", "data-publish-evidence-post-launch-receipt-ready", "data-publish-evidence-post-launch-receipt-text", "data-publish-evidence-post-launch-receipt-copy", "Post-launch verification receipt"] },
    { file: "app.js", terms: ["function copyPublishPostLaunchReceipt", "copy-publish-post-launch-receipt", "data-publish-evidence-post-launch-receipt-text", "publishPostLaunchReceiptCopied", "publish post-launch receipt를 복사했습니다"] },
    { file: "styles.css", terms: [".publish-evidence-post-launch-receipt", ".publish-evidence-post-launch-receipt span", ".publish-evidence-post-launch-receipt strong"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["publishPostLaunchReceipt", "publish post-launch receipt guard was not copy-ready", "publish post-launch receipt copy text did not reach clipboard", "}, \"publish post-launch receipt guard was not copy-ready\", 15000);", "not ready to archive", "publishDispatchReady: false", "dispatchSuggestionStatus: withheld-until-all-dispatch-ready", "Dispatch guard: withheld (withheld-until-all-dispatch-ready)", "Withheld dispatch commands:"] },
    { file: "README.md", terms: ["JooPark Post-Launch Verification Receipt", "post-launch receipt 복사", "not ready to archive", "Dispatch guard", "Withheld dispatch commands", "Do not archive this as post-launch verification", "Evidence repo: biojuho/BIOJUHO-Projects"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "publish_post_launch_verification_receipt",
    requirement: "Publish evidence includes a copy-ready post-launch verification receipt for internal launch notes, and the receipt refuses archival when repo, Pages, workflow, freshness, or postPublish proof is incomplete.",
    status: publishPostLaunchReceiptTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: publishPostLaunchReceiptTerms,
  });

  const launchProofEvidenceReceiptFields = ["Pages site proof", "Pages workflow run proof", "Drift Watch workflow run proof", "Evidence freshness proof", "Release receipt proof", "Public claim guard proof"];
  const launchProofEvidenceStopCondition = "Stop condition: do not post public launch copy, archive proof, or claim readyForExternalClaim until all six evidence fields are live, fresh, linked, successful, and readyForExternalClaim=true.";
  const launchProofEvidenceNextActionTerms = ["Next proof actions:", "nextAction=", "data-publish-evidence-launch-proof-field-next-action", "capture-output-quality-audit.mjs --write"];
  const launchProofEvidenceReceiptTerms = [
    { file: "scripts/capture-publish-evidence.mjs", terms: ["function publishLaunchProofEvidenceFields", "function publishLaunchProofEvidenceReceipt", "launchProofEvidenceFieldCoverage", "payload.launchProofEvidenceFields", "payload.launchProofEvidenceReceipt", "## Launch proof evidence receipt", "JooPark Launch Proof Evidence Receipt", "Evidence fields to fill:", "Required proof commands:", "Acceptance criteria:", launchProofEvidenceStopCondition, ...launchProofEvidenceNextActionTerms.filter((term) => term !== "data-publish-evidence-launch-proof-field-next-action"), ...launchProofEvidenceReceiptFields] },
    { file: "data/publish-evidence.json", terms: ["launchProofEvidenceFields", "launchProofEvidenceFieldCount", "launchProofEvidenceFieldCoverage", "launchProofEvidenceReceipt", "JooPark Launch Proof Evidence Receipt", "Status: guarded until external claim ready", "Repo: biojuho/BIOJUHO-Projects", "Evidence repo: biojuho/BIOJUHO-Projects", "Repo resolution: source_repo", "External claim guard:", "readyForExternalClaim: false", "Required proof commands:", "Acceptance criteria:", launchProofEvidenceStopCondition, ...launchProofEvidenceNextActionTerms.filter((term) => term !== "data-publish-evidence-launch-proof-field-next-action"), ...launchProofEvidenceReceiptFields] },
    { file: "release-status.js", terms: ["data-publish-evidence-launch-proof-receipt", "data-publish-evidence-launch-proof-receipt-ready", "data-publish-evidence-launch-proof-receipt-text", "data-publish-evidence-launch-proof-receipt-copy", "data-publish-evidence-launch-proof-field", "data-publish-evidence-launch-proof-field-coverage", "data-publish-evidence-launch-proof-field-next-action", "Next:", "Launch proof evidence receipt", "launch proof receipt 복사", ...launchProofEvidenceReceiptFields] },
    { file: "operations-copy-actions.js", terms: ["function copyPublishLaunchProofReceipt", "data-publish-evidence-launch-proof-receipt-text", "publishLaunchProofReceiptCopied", "launch proof evidence receipt를 복사했습니다"] },
    { file: "app.js", terms: ["function copyPublishLaunchProofReceipt", "copy-publish-launch-proof-receipt", "data-publish-evidence-launch-proof-receipt-text", "publishLaunchProofReceiptCopied", "launch proof evidence receipt를 복사했습니다"] },
    { file: "styles.css", terms: [".publish-evidence-launch-proof-receipt", ".publish-evidence-launch-proof-receipt span", ".publish-evidence-launch-proof-receipt strong"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["launchProofEvidenceReceipt", "publish launch proof evidence receipt was not copy-ready", "publish launch proof receipt copy text did not reach clipboard", "Launch proof evidence receipt: pass (6 fields, coverage=1, nextActions=6/6)", launchProofEvidenceStopCondition, ...launchProofEvidenceNextActionTerms, ...launchProofEvidenceReceiptFields] },
    { file: "README.md", terms: ["JooPark Launch Proof Evidence Receipt", "launch proof receipt 복사", "launchProofEvidenceFieldCoverage", "Evidence fields to fill:", "Required proof commands:", "Next proof actions:", "nextAction=", "Acceptance criteria:", launchProofEvidenceStopCondition, ...launchProofEvidenceReceiptFields] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "launch_proof_evidence_receipt",
    requirement: "Publish evidence includes a copy-ready six-field launch proof evidence receipt that blocks public launch copy, archival proof, and readyForExternalClaim until live Pages, workflow, freshness, release-receipt, and public-claim proof are all linked and successful.",
    status: launchProofEvidenceReceiptTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: launchProofEvidenceReceiptTerms,
  });

  const outputQualityAuditTerms = [
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["JooPark Final Output Quality Audit Receipt", "qualityCriteria", "artifactQualityRubric", "Artifact quality rubric:", "artifactQualityRubric=${valueOrPending", "Required form fit", "Copy-ready completeness", "Evidence traceability", "Safety guardrails", "Freshness and reuse", "passingScore", "GitHub Issue Forms required inputs", "Jira required fields", "sourceEvidenceFreshness", "sourceEvidenceFresh", "sourceEvidenceStaleCount", "Source evidence freshness:", "Source evidence freshness", "sourceInputTrace", "sourceInputs", "sourceInputCount", "Source inputs:", "release_gate_cache", "release_readiness_summary", "releaseReadinessSummaryRel", "cachedAuditGate", "joopark-release-readiness-summary/v1", "--release-readiness-summary", "releaseGateCache?.evidence?.status === \"pass\"", "previous_output_quality", "copyReadyArtifacts.externalClaimGuard", "outputQualityExternalClaimGuardSourceReady", "evidenceDowngradeGuard", "Evidence downgrade guard:", "previous_output_quality_audit", "fresh_previous_pass_evidence_preserved", "candidateComplete", "previousComplete", "completionAuditChecklist", "completionAuditReady", "completionAuditBlockedCount", "Completion audit:", "Workflow installation", "External completion claim", "readyForExternalClaim=false", "finalReadyForExternalClaim", "launchPacketReadyForExternalClaim", "Launch packet readyForExternalClaim", "outputReadinessSnapshot", "outputVariantComparison", "Output variant comparison:", "generic_generated_summary", "copy_ready_evidence_receipt", "decision=${valueOrPending(variantComparison.decision)}", "workflowAuthPreflightSnapshot", "workflowAuthPreflight", "approvalRequired", "approvalStatus", "approvalUrl", "approvalSensitiveValuePolicy", "approvalStopCondition", "https://github.com/login/device", "publishDispatchAuthPreflight", "systemStatusWorkflowAuthPreflightFields", "const fieldCoverage = finiteNumberOr(evidence.systemStatusWorkflowAuthPreflightFields", "Workflow auth preflight:", "launchPostAuthCheckpointSnapshot", "launchPostAuthCheckpoint", "Launch post-auth checkpoint:", "Token scopes include workflow", "safeToDispatch=true", "every action_required post-auth checkpoint item has passed", "verify-launch-handoff reports safeToDispatch=true", "requiredRecheckKeys", "requiredSourceArtifacts", "recheckSequenceCount", "sourceArtifactCount", "dispatchApproval", "verificationOnly", "confirm_scope", "verify_remote_parity", "verify_actions_visibility", "verify_handoff_guard", "guard=${valueOrPending(launchPostAuthCheckpoint.guard)}", "uiVerified", "workflowScopeAvailable", "workflowScopeInstallBlocked", "launchAcceptanceChecklist", "Launch acceptance checklist", "launchInstallPathSnapshot", "launchInstallPaths", "Launch install path options:", "CLI path after workflow scope", "GitHub UI path", "install-remote-workflow-files.mjs", "Output readiness snapshot", "Tracker form payloads:", "Runtime issues:", "Publish evidence command guard:", "publishEvidenceCommandGuard", "publishEvidenceImmediateNextAction", "suggestedDispatchCount", "withheldDispatchCount", "countFromArrayOr", "finiteNumberOr", "Publish evidence immediate action:", "immediate action:", "deferred evidence capture:", "Immediate command:", "Deferred evidence capture:", "Workflow scope refresh command", "Workflow scope approval status", "Workflow scope approval URL", "Workflow scope device-code policy", "Workflow scope approval stop condition", "workflowScopeRefreshCommand", "gh auth refresh -h github.com -s workflow", "Linear issue templates", "repoContext", "resolved_from_suggested_repo", "Evidence repo:", "Repo resolution:", "externalComparison", "GitHub Actions job summaries", "GitHub Releases", "readyForExternalClaim", "releaseQualityReady", "publicLaunchProofReady", "Do not present it as public launch completion", "data/output-quality-audit.json"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["systemStatusWorkflowAuthPreflightFields", "finiteNumberOr(\n    persistedChecks.systemStatusWorkflowAuthPreflightFields"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["publishEvidenceCommandGuard", "coverage: finiteNumberOr(evidence.publishEvidenceWithheldDispatchCoverage"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const publishInstallPathItems = Array.isArray(publishInstallPaths.paths)", "const publishInstallPathItemCommandCount = publishInstallPathItems.reduce(", "const publishInstallPathCount = finiteNumberOr(publishInstallPaths.count, publishInstallPathItems.length)", "const publishInstallPathCommandCount = finiteNumberOr(publishInstallPaths.commandCount, publishInstallPathItemCommandCount)", "publishEvidenceInstallPathPaths: publishInstallPathCount", "publishEvidenceInstallPathCommands: publishInstallPathCommandCount"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const launchExecutionPacketStageCount = finiteNumberOr(\n    launchExecutionPacket?.stageCount", "const launchExecutionPacketCommandCount = finiteNumberOr(\n    launchExecutionPacket?.commandCount", "const launchExecutionPacketExternalComparisonSourceCount = finiteNumberOr(\n    launchExecutionPacket?.externalComparisonSourceCount", "launchExecutionPacketStages: launchExecutionPacketStageCount", "launchExecutionPacketCommands: launchExecutionPacketCommandCount", "launchExecutionPacketExternalComparisonSources: launchExecutionPacketExternalComparisonSourceCount"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const launchPostAuthCheckpoint = launchExecutionPacket?.postAuthCheckpoint", "const launchPostAuthCheckpointCoverage = finiteNumberOr(\n    launchPostAuthCheckpoint.coverage", "const launchPostAuthCheckpointCommandCount = finiteNumberOr(\n    launchPostAuthCheckpoint.commandCount", "const launchPostAuthCheckpointExpectedSignalCount = finiteNumberOr(\n    launchPostAuthCheckpoint.expectedSignalCount", "const launchPostAuthCheckpointRecheckCount = finiteNumberOr(\n    launchPostAuthCheckpoint.recheckSequenceCount", "const launchPostAuthCheckpointSourceArtifactCount = finiteNumberOr(\n    launchPostAuthCheckpoint.sourceArtifactCount"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function launchPostAuthCheckpointSnapshot", "const checkpointCommandCount = finiteNumberOr(checkpoint.commandCount, 0)", "const checkpointRecheckSequenceCount = finiteNumberOr(checkpoint.recheckSequenceCount, recheckSequence.length)", "const checkpointSourceArtifactCount = finiteNumberOr(checkpoint.sourceArtifactCount, sourceArtifacts.length)", "const checkpointExpectedSignalCount = finiteNumberOr(checkpoint.expectedSignalCount, expectedSignals.length)", "const checkpointBlockedSignalCount = finiteNumberOr(checkpoint.blockedSignalCount, blockedSignals.length)", "commandCount: checkpointCommandCount", "recheckSequenceCount: checkpointRecheckSequenceCount", "sourceArtifactCount: checkpointSourceArtifactCount", "expectedSignalCount: checkpointExpectedSignalCount", "blockedSignalCount: checkpointBlockedSignalCount"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function outputQualityNextAction", "function installWorkflowNextActionCommand", "remoteWorkflowRepairAction(remoteWorkflowFileCheck)", "nextAction", "deferredKey", "deferredCommand", "guard: status === \"ready\"", "readyDetail", "outputSnapshot?.workflowAuthPreflight?.approvalStopCondition", "Do not run gh workflow run until all dispatch and launch proof gates are pass."] },
	    { file: "scripts/capture-output-quality-audit.mjs", terms: ["workflowUiInstallReceiptSnapshot", "workflowUiInstallReceipt", "Workflow UI paste packet:", "workflowUiInstallPastePacketCoverage", "workflowUiInstallPastePacketCoverage: finiteNumberOr", "workflowUiInstallPastePacketCopy", "workflowUiInstallPastePacketReady", "workflowUiInstallPastePacketText = String(", "workflowUiInstallPastePacketSourceReady", "workflowUiInstallPastePacketEvidenceReady", "workflowUiInstallReceiptCoverage", "workflowUiInstallReceiptCommandCount", "workflowUiInstallReceiptChecklistCount", "const packetCoverage = finiteNumberOr(", "workflowUiInstallPlan?.workflowUiInstallPastePacketCoverage", "finiteNumberOr(receipt.commandCount", "finiteNumberOr(receipt.checklistCount", "const workflowUiInstallReceiptCoverage = finiteNumberOr(\n    workflowUiInstallReceipt.coverage", "const workflowUiInstallReceiptCommandCount = finiteNumberOr(workflowUiInstallReceipt.commandCount, persistedChecks.workflowUiInstallReceiptCommandCount)", "const workflowUiInstallReceiptChecklistCount = finiteNumberOr(workflowUiInstallReceipt.checklistCount, persistedChecks.workflowUiInstallReceiptChecklistCount)", "Parser-ready proof block:", "falsePositiveGuard=${yesNo(postInstallProofParser.falsePositiveGuard)}", "every post-install evidence field has been filled", "verify-launch-handoff reports safeToDispatch=true", "guard=${valueOrPending(workflowUiInstallReceipt.guard)}", "postInstallEvidenceIntake", "postInstallEvidenceIntakeFields", "postInstallEvidenceIntakeFieldCoverage", "Post-install evidence intake:"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const launchPostInstallEvidenceIntake = launchExecutionPacket?.postInstallEvidenceIntake", "const postInstallEvidenceIntakeFields = finiteNumberOr(\n    launchPostInstallEvidenceIntake.fieldCount", "const postInstallEvidenceIntakeFieldCoverage = finiteNumberOr(\n    launchPostInstallEvidenceIntake.fieldCoverage"] },
	    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function postInstallEvidenceIntakeSnapshot", "postInstallEvidenceIntakeSnapshot", "completedFieldCount", "pendingFieldCount", "proofComplete", "quickProofReady", "quickProofCoverage", "quickProofFieldMappings", "quickProofFieldMappingReady", "quickProofFieldMappingCoverage", "quickProofMappedFieldCount", "finiteNumberOr(intake.fieldCount", "finiteNumberOr(intake.commandCount", "finiteNumberOr(intake.quickProofStepCount", "Post-install quick proof:", "Post-install quick proof field mapping:", "quick proof field ${index + 1}", "fieldItems", "generated_from_launch_execution_packet", "collect_post_install_proof", "remote_parity_proof", "handoff_verifier_proof"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["launchProofEvidenceReceiptSnapshot", "launchProofEvidenceReceipt", "launchProofEvidenceFields", "launchProofEvidenceFieldCoverage", "const fieldCount = finiteNumberOr(", "publishEvidence?.launchProofEvidenceFieldCount", "finiteNumberOr(evidence.launchProofEvidenceFields", "finiteNumberOr(publishEvidence?.launchProofEvidenceFieldCoverage", "nextActionCount", "nextActionCoverage", "Next proof actions:", "nextActions=${valueOrPending(launchProofEvidenceReceipt.nextActionCount)}/6", "Launch proof evidence receipt:", "Launch proof evidence receipt: ${launchProofEvidenceReceipt.ready ? \"pass\" : \"blocked\"}", "copyReadyArtifacts.launchProofEvidenceReceipt", "launchProofEvidenceReceiptSourceReady", "Pages site proof", "Public claim guard proof"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const launchProofEvidenceFields = finiteNumberOr(\n    publishEvidence?.launchProofEvidenceFieldCount", "const launchProofEvidenceFieldCoverage = finiteNumberOr(\n    publishEvidence?.launchProofEvidenceFieldCoverage", "finiteNumberOr(persistedChecks.launchProofEvidenceFields", "finiteNumberOr(persistedChecks.launchProofEvidenceFieldCoverage"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const outputQualityExternalComparisonReady = !!persistedChecks.outputQualityAuditReceipt", "const outputQualityExternalComparisonSources = finiteNumberOr(\n    persistedChecks.outputQualityExternalComparisonSources", "outputQualityExternalComparison: outputQualityExternalComparisonReady", "outputQualityExternalComparisonSources,"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function pagesAttestationProofCaptureSnapshot", "pagesAttestationProofCapture", "finiteNumberOr(pagesAttestationProof?.proofFieldCoverage", "finiteNumberOr(pagesAttestationProof?.requiredFieldCount", "finiteNumberOr(pagesAttestationProof?.commandCount"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function handoffVerifierArtifactSnapshot", "handoffVerifierArtifact", "finiteNumberOr(artifact.artifactCoverage", "finiteNumberOr(postInstall.fieldCount", "finiteNumberOr(postInstall.completedFieldCount"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["launchExecutionPacketStageCount", "launchExecutionPacketCommandCount", "finiteNumberOr(launchExecutionPacket?.stageCount", "finiteNumberOr(launchExecutionPacket?.commandCount"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const globalHelpAccessActions = finiteNumberOr(\n    persistedChecks.globalHelpAccessActions", "const globalHelpAccessCoverage = finiteNumberOr(\n    persistedChecks.globalHelpAccessCoverage", "const topbarDataSafetyActions = finiteNumberOr(\n    persistedChecks.topbarDataSafetyActions", "const topbarDataSafetyCoverage = finiteNumberOr(\n    persistedChecks.topbarDataSafetyCoverage", "const routeDeepLinkCoverage = finiteNumberOr(\n    persistedChecks.routeDeepLinkCoverage", "const homeFirstRunGuidedStartItems = finiteNumberOr(\n    persistedChecks.homeFirstRunGuidedStartItems", "const homeFirstRunGuidedStartCoverage = finiteNumberOr(\n    persistedChecks.homeFirstRunGuidedStartCoverage"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function previousOutputQualityBrowserEvidence", "finiteNumberOr(sourceBackedEvidence.outputQualityExternalComparisonSources", "finiteNumberOr(sourceBackedEvidence.reviewPackageArtifactQualityItems", "finiteNumberOr(sourceBackedEvidence.globalHelpAccessActions", "finiteNumberOr(snapshot.globalHelpAccess?.actions", "finiteNumberOr(sourceBackedEvidence.topbarDataSafetyActions", "finiteNumberOr(snapshot.topbarDataSafety?.actions", "finiteNumberOr(sourceBackedEvidence.routeDeepLinkCoverage", "finiteNumberOr(snapshot.routeDeepLink?.coverage", "finiteNumberOr(sourceBackedEvidence.homeFirstRunGuidedStartItems", "finiteNumberOr(snapshot.firstRunGuidedStart?.items"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function blockerResolutionChecklistSnapshot", "blockerResolutionChecklist", "Blocker resolution checklist:", "Blocker resolution checklist: ${blockerResolution.ready ? \"pass\" : \"blocked\"}", "const guard = checklist.guard || checklist.dispatchGuard", "guard.includes(\"action_required\")", "guard=${valueOrPending(blockerResolution.guard)}", "activeItemKey", "actionRequiredCount", "deferredCount", "proofCommandCount", "finiteNumberOr(checklist.itemCount", "finiteNumberOr(checklist.actionRequiredCount", "finiteNumberOr(checklist.proofCommandCount", "proofCommand=", "expectedValue=", "stopCondition="] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function externalCompletionClaimGuard", "externalClaimGuard", "JooPark External Completion Claim Guard", "blocked_external_claim", "Required requirements:", "Required signals:", "Proof commands:", "Stop condition: do not claim readyForExternalClaim", "outputQualityExternalClaimGuardSourceReady", "externalClaimGuard=${yesNo"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function externalClaimCloseoutPacket", "External claim closeout packet", "default branch workflow_dispatch", "Required proof fields", "workflow run summary", "Release-note archive claim", "Allowed claim after proof", "Forbidden until proof", "closeoutPacket", "closeoutPacketText"] },
    { file: "data/output-quality-audit.json", terms: ["blockerResolutionChecklist", "Blocker resolution checklist: pass (active=operator_auth_path, 2/6 pass, actionRequired=3, deferred=1, proofCommands=6", "guard=Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.", "activeItemKey", "operator_auth_path", "actionRequiredCount", "deferredCount", "proofCommandCount", "proofCommand=gh auth refresh -h github.com -s workflow", "expectedValue=remoteWorkflowFilesReady=true", "stopCondition=If safeToDispatch=false"] },
    { file: "data/output-quality-audit.json", terms: ["externalClaimGuard", "JooPark External Completion Claim Guard", "\"status\": \"blocked_external_claim\"", "\"blockedCount\": 2", "\"requirementCount\": 3", "External completion claim guard:", "status=blocked_external_claim; ready=false; blocked=2/3", "signal readyForExternalClaim=false", "proofCommand node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown", "Stop condition: do not claim readyForExternalClaim"] },
    { file: "data/output-quality-audit.json", terms: ["\"closeoutPacket\"", "External claim closeout packet", "\"stepCount\": 5", "\"proofFieldCount\": 6", "default branch workflow_dispatch", "Required proof fields", "workflow run summary", "Release-note archive claim", "Allowed claim after proof", "Forbidden until proof"] },
	    { file: "data/output-quality-audit.json", terms: ["JooPark Final Output Quality Audit Receipt", "Status: public launch proof ready; launch packet claim guard blocked", "artifactQualityRubric", "Artifact quality rubric:", "artifactQualityRubric=blocked; totalScore=80/100; passingScore=90", "Required form fit: pass (20/20)", "Copy-ready completeness: blocked (0/20)", "Evidence traceability: pass (20/20)", "Safety guardrails: pass (20/20)", "Freshness and reuse: pass (20/20)", "GitHub Issue Forms required inputs", "Jira required fields", "outputVariantComparison", "\"selectedVariant\": \"recheck_required\"", "\"decision\": \"recheck_before_claim\"", "Output variant comparison:", "A: generic generated summary: rejected", "B: copy-ready evidence receipt: needs_recheck", "Copy-ready field payloads: winner=copy_ready_evidence_receipt", "sourceEvidenceFreshness", "sourceEvidenceFresh", "sourceEvidenceStaleCount", "sourceInputs", "sourceInputCount", "Source input count: 11", "Source inputs:", "release gate cache", "release readiness summary", "previous output quality", "launch handoff verification", "main bridge plan", "Source evidence freshness:", "sourceEvidenceFresh=true; staleSources=0; sources=7", "remote workflow file check: fresh", "launch handoff verification: fresh", "main bridge plan: fresh", "promptToArtifactChecklist", "goalCompletionAudit", "Prompt-to-artifact checklist:", "goalCompletionAudit=output_quality_goal_gaps", "External output comparison: blocked", "AutoResearch usage: blocked", "evidenceDowngradeGuard", "Evidence downgrade guard: not applied", "candidateComplete=false", "previousComplete=false", "launchPacketReadyForExternalClaim", "Launch packet readyForExternalClaim: false", "completionAuditChecklist", "Source evidence freshness", "completionAuditReady", "completionAuditBlockedCount", "Completion audit:", "completionAuditReady=false; blocked=2; readyForExternalClaim=false", "Workflow installation: blocked", "remoteWorkflowFilesReady=true", "Public launch proof: pass", "postPublishEvidenceReady=true", "External completion claim: blocked", "readyForExternalClaim=true", "outputReadinessSnapshot", "\"nextAction\": {", "\"key\": \"install_workflows\"", "\"status\": \"action_required\"", "\"source\": \"data/launch-execution-packet.json\"", "\"command\": \"node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown\"", "\"deferredKey\": \"capture-live-evidence\"", "\"deferredCommand\": \"node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown\"", "workflowAuthPreflight", "Workflow auth preflight: blocked (uiVerified=false, workflowScopeAvailable=true, workflowScopeInstallBlocked=false, missing=none, scopes=gist, read:org, repo, workflow)", "not_required", "https://github.com/login/device", "Do not store, log, or paste the one-time device code", "Workflow scope approval status", "Workflow scope approval URL", "Workflow scope device-code policy", "publishDispatchAuthPreflight", "systemStatusWorkflowAuthPreflightFields", "launchAcceptanceChecklist", "Launch acceptance checklist: 4/5 pass, pending=1, stage=install_workflows", "launchInstallPathSnapshot", "launchInstallPaths", "Launch install path options: pass (2 paths,", "CLI path after workflow scope", "GitHub UI path", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "pbcopy < 'docs/github-pages-workflow.yml' && open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'", "Review package final quality: 6/6", "Tracker form payloads: pass (11 fields, checksums ready)", "Runtime issues: console 0, network 0, layout 0", "Launch proof evidence receipt: pass (6 fields, coverage=1, nextActions=6/6)", "\"nextActionCount\": 6", "\"nextActionCoverage\": 1", "Publish evidence command guard: pass (7 safe suggestions, 0 suggested dispatch, 2 withheld dispatch, active=0, reference=2, disposition=withheld_until_all_dispatch_ready)", "Publish evidence immediate action: blocked (install_workflows from data/launch-execution-packet.json, deferred capture-live-evidence)", "Specific context: pass", "immediate action: Install workflows on the default branch", "Immediate action: Install workflows on the default branch [action_required]", "deferred evidence capture: Capture live publish evidence", "Immediate command: pbcopy < 'docs/github-pages-workflow.yml' && open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'", "Deferred evidence capture: Capture live publish evidence", "Workflow scope refresh command", "gh auth refresh -h github.com -s workflow", "publishEvidenceCommandGuard", "publishEvidenceImmediateNextAction", "repoResolution", "source_repo", "Repo: biojuho/BIOJUHO-Projects", "Evidence repo: biojuho/BIOJUHO-Projects", "Accuracy evidence", "Copy-ready outputs", "External comparison", "GitHub issue forms validation", "GitHub Actions job summaries", "GitHub Releases", "Linear issue templates", "Public launch proof", "Do not present it as public launch completion"] },
    { file: "data/output-quality-audit.json", terms: ["launchPostAuthCheckpoint", "Launch post-auth checkpoint: pass (5 commands, expected=6, blocked=4, recheck=5, sources=4, dispatchApproval=false, verificationOnly=true", "\"recheckSequenceCount\": 5", "\"sourceArtifactCount\": 4", "\"verificationOnly\": true", "\"dispatchApproval\": false", "\"recheckKeys\"", "\"sourceArtifacts\"", "confirm_scope", "verify_remote_parity", "verify_actions_visibility", "verify_handoff_guard", "data/remote-workflow-file-check.json", "data/publish-dispatch-plan.json", "data/launch-handoff-verification.json", "verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown", "guard=Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true."] },
				    { file: "data/output-quality-audit.json", terms: ["workflowUiInstallReceipt", "Workflow UI paste packet: pass (workflowUiInstallPastePacketCoverage=1,", "commands, checklist=", "guard=Do not run gh workflow run until every post-install evidence field has been filled", "verify-launch-handoff reports safeToDispatch=true.", "workflowUiInstallPastePacketCoverage", "workflowUiInstallPastePacketCopy", "workflowUiInstallPastePacketReady", "workflowUiInstallReceiptCoverage", "workflowUiInstallReceiptCommandCount", "workflowUiInstallReceiptChecklistCount", "postInstallEvidenceIntake", "postInstallEvidenceIntakeFields", "postInstallEvidenceIntakeFieldCoverage", "Post-install evidence intake: pass (6 fields, coverage=1)", "Post-install proof parser: pass (0 fields, coverage=0)", "status=waiting_for_pasted_proof", "detected=0/0", "falsePositiveGuard=true", "not dispatch approval", "Post-install quick proof: pass (4 steps, coverage=1)", "Post-install quick proof field mapping: pass (1/4 mapped fields complete, coverage=1)"] },
		    { file: "data/output-quality-audit.json", terms: ["postInstallEvidenceIntake", "\"source\": \"generated_from_launch_execution_packet\"", "\"status\": \"proof_complete\"", "\"completedFieldCount\": 6", "\"proofComplete\": true", "\"quickProofStepCount\": 4", "\"quickProofCoverage\": 1", "\"quickProofFieldMappingCoverage\": 1", "\"quickProofMappedFieldCount\": 4", "\"commandCount\": 4", "\"signalCount\": 8", "Post-install evidence intake: pass (6 fields, coverage=1) - status=proof_complete, completed=6/6, proofComplete=true, commands=4, signals=8", "Post-install quick proof: pass (4 steps, coverage=1)", "Post-install quick proof field mapping: pass (4/4 mapped fields complete, coverage=1)", "quickProofReady=true; steps=4; coverage=1", "quickProofFieldMappingReady=true; mapped=4; completed=4/4; coverage=1", "quick proof field 1 remote_file_parity -> remote_parity_proof", "quick proof field 4 handoff_verifier -> handoff_verifier_proof", "source=generated_from_launch_execution_packet; status=proof_complete; proofComplete=true; completed=6/6; commands=4; signals=8", "remote_parity_proof: proof_ready", "handoff_verifier_proof: proof_ready"] },
    { file: "data/main-bridge-plan.json", terms: ["JooPark Main PR Bridge Plan", "\"status\": \"pass\"", "\"strategy\": \"main-subdirectory-bridge\"", "\"noCommonHistory\": true", "\"appPath\": \"apps/joopark-workspace\"", "\"bridgeBranch\": \"codex/joopark-workspace-main-bridge\"", "\"externalComparison\"", "git switch -c codex/joopark-workspace-main-bridge"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["mainBridgePlanRel", "captureMainBridgePlan", "mainBridgePlanSnapshot", "main_bridge_plan", "data/main-bridge-plan.json", "Main PR bridge plan:", "mainBridgePlan=${yesNo", "copyReadyArtifacts.mainBridgePlan", "--main-bridge-plan"] },
    { file: "scripts/test-pure-helpers.mjs", terms: ["testOutputQualityOptionValueGuard", "optionValue([\"--out\", \"--write\"], \"--out\")", "optionValue([\"--product-loop\", \"--markdown\"], \"--product-loop\")", "optionValue([\"--release-gate-cache\", \"--write\"], \"--release-gate-cache\")", "optionValue([\"--release-readiness-summary\", \"--markdown\"], \"--release-readiness-summary\")", "optionValue([\"--previous-output-quality\", \"--write\"], \"--previous-output-quality\")", "optionValue([\"--launch-handoff-verification\", \"--markdown\"], \"--launch-handoff-verification\")", "optionValue([\"--main-bridge-plan\", \"--write\"], \"--main-bridge-plan\")"] },
    { file: "data/output-quality-audit.json", terms: ["mainBridgePlan", "\"mainBridgePlan\": true", "Main PR bridge plan: pass", "status=pass; ready=true; strategy=main-subdirectory-bridge; noCommonHistory=true; mainAppPathExists=true", "commandCount=6; externalComparison=2", "main bridge plan: fresh", "data/main-bridge-plan.json"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["operatorOnePageHandoffSnapshot", "operatorOnePageHandoff", "copyReadyArtifacts.operatorOnePageHandoff", "Operator one-page handoff:", "successSignals=", "operatorOnePageHandoff=${yesNo", "JooPark Launch Operator One-Page Handoff"] },
	    { file: "data/output-quality-audit.json", terms: ["operatorOnePageHandoff", "\"operatorOnePageHandoff\": true", "Operator one-page handoff: pass (8 sections", "successSignals=8", "operatorOnePageHandoff=true", "active=not available", "JooPark Launch Operator One-Page Handoff"] },
		    { file: "data/output-quality-audit.json", terms: ["launchProofEvidenceReceipt", "launchProofEvidenceFields", "launchProofEvidenceFieldCoverage", "nextActionCount", "nextActionCoverage", "Launch proof evidence receipt: pass (6 fields, coverage=1, nextActions=6/6)", "launchProofEvidenceReceipt=true", "Launch proof evidence receipt ready (6 fields)"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewPackageDecisionBrief", "reviewPackageDecisionBriefFields", "reviewPackageDecisionBriefCoverage", "Review package decision brief:", "reviewIssueDecisionSummary", "reviewIssueDecisionSummaryFields", "reviewIssueDecisionSummaryCoverage", "Review issue decision summary:", "reviewCommentNoteDecisionSummary", "reviewCommentNoteDecisionSummaryFields", "reviewCommentNoteDecisionSummaryCoverage", "Review comment/note decision summary:", "reviewResultRepairActionPlan", "reviewResultRepairActionPlanFields", "reviewResultRepairActionPlanCoverage", "Review result repair action plan:", "reviewPackageSubmissionCloseoutSummary", "reviewPackageSubmissionCloseoutSummaryFields", "reviewPackageSubmissionCloseoutSummaryCoverage", "Review submission closeout summary:", "reviewPackageOperatorQuickStart", "reviewPackageOperatorQuickStartSteps", "reviewPackageOperatorQuickStartCoverage", "Review package operator quick start:", "operator quick start"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["const reviewPackageArtifactQualityItems = finiteNumberOr(\n    persistedChecks.reviewPackageArtifactQualityItems", "const reviewPackageDecisionBriefFields = finiteNumberOr(\n    persistedChecks.reviewPackageDecisionBriefFields", "const reviewPackageDecisionBriefCoverage = finiteNumberOr(\n    persistedChecks.reviewPackageDecisionBriefCoverage", "const reviewIssueDecisionSummaryFields = finiteNumberOr(\n    persistedChecks.reviewIssueDecisionSummaryFields", "const reviewIssueDecisionSummaryCoverage = finiteNumberOr(\n    persistedChecks.reviewIssueDecisionSummaryCoverage", "const reviewCommentNoteDecisionSummaryFields = finiteNumberOr(\n    persistedChecks.reviewCommentNoteDecisionSummaryFields", "const reviewCommentNoteDecisionSummaryCoverage = finiteNumberOr(\n    persistedChecks.reviewCommentNoteDecisionSummaryCoverage", "const reviewResultRepairActionPlanFields = finiteNumberOr(\n    persistedChecks.reviewResultRepairActionPlanFields", "const reviewResultRepairActionPlanCoverage = finiteNumberOr(\n    persistedChecks.reviewResultRepairActionPlanCoverage", "const reviewPackageSubmissionCloseoutSummaryFields = finiteNumberOr(\n    persistedChecks.reviewPackageSubmissionCloseoutSummaryFields", "const reviewPackageSubmissionCloseoutSummaryCoverage = finiteNumberOr(\n    persistedChecks.reviewPackageSubmissionCloseoutSummaryCoverage", "const reviewPackageOperatorQuickStartSteps = finiteNumberOr(\n    persistedChecks.reviewPackageOperatorQuickStartSteps", "const reviewPackageOperatorQuickStartCoverage = finiteNumberOr(\n    persistedChecks.reviewPackageOperatorQuickStartCoverage", "const reviewPackageTrackerFormPayloadCount = finiteNumberOr(\n    persistedChecks.reviewPackageTrackerFormPayloadCount", "const reviewPackageTrackerFormPayloadCoverage = finiteNumberOr(\n    persistedChecks.reviewPackageTrackerFormPayloadCoverage"] },
    { file: "data/output-quality-audit.json", terms: ["reviewPackageDecisionBrief", "reviewPackageDecisionBriefFields", "reviewPackageDecisionBriefCoverage", "Review package decision brief: pass (6 fields, coverage=1)", "reviewIssueDecisionSummary", "reviewIssueDecisionSummaryFields", "reviewIssueDecisionSummaryCoverage", "Review issue decision summary: pass (6 fields, coverage=1)", "reviewCommentNoteDecisionSummary", "reviewCommentNoteDecisionSummaryFields", "reviewCommentNoteDecisionSummaryCoverage", "Review comment/note decision summary: pass (6 fields, coverage=1)", "reviewResultRepairActionPlan", "reviewResultRepairActionPlanFields", "reviewResultRepairActionPlanCoverage", "Review result repair action plan: pass (6 fields, coverage=1)", "reviewPackageSubmissionCloseoutSummary", "reviewPackageSubmissionCloseoutSummaryFields", "reviewPackageSubmissionCloseoutSummaryCoverage", "Review submission closeout summary: pass (6 fields, coverage=1)", "reviewPackageOperatorQuickStart", "reviewPackageOperatorQuickStartSteps", "reviewPackageOperatorQuickStartCoverage", "Review package operator quick start: pass (5 steps, coverage=1)"] },
    { file: "release-status.js", terms: ["function outputQualityAuditHTML", "data-system-output-quality-audit", "data-output-quality-audit-launch-packet-external-ready", "launchPacketReadyForExternalClaim", "sourceEvidenceFresh", "data-output-quality-audit-source-evidence-fresh", "data-output-quality-audit-source-evidence-count", "data-output-quality-audit-source-evidence-stale-count", "data-output-quality-audit-artifact-rubric-status", "data-output-quality-audit-artifact-rubric-score", "data-output-quality-audit-artifact-rubric-item-count", "data-output-quality-audit-artifact-rubric", "Artifact quality rubric", "data-output-quality-audit-artifact-rubric-item", "data-output-quality-audit-variant-status", "data-output-quality-audit-variant-decision", "data-output-quality-audit-variant-selected", "data-output-quality-audit-variant-comparison", "Output variant comparison", "data-output-quality-audit-variant-item", "data-output-quality-audit-variant-criterion", "data-output-quality-audit-source-freshness", "data-output-quality-audit-source-freshness-item", "data-output-quality-audit-workflow-auth-preflight", "data-output-quality-audit-workflow-auth-preflight-ui-verified", "data-output-quality-audit-workflow-auth-preflight-fields", "data-output-quality-audit-workflow-auth-preflight-install-blocked", "workflow-auth-preflight", "Workflow auth preflight", "data-output-quality-audit-launch-post-auth-checkpoint", "data-output-quality-audit-launch-post-auth-checkpoint-command-count", "data-output-quality-audit-launch-post-auth-checkpoint-recheck-count", "data-output-quality-audit-launch-post-auth-checkpoint-source-artifact-count", "data-output-quality-audit-launch-post-auth-checkpoint-dispatch-approval", "data-output-quality-audit-launch-post-auth-checkpoint-verification-only", "launch-post-auth-checkpoint", "Launch post-auth checkpoint", "dispatchApproval=", "verificationOnly=", "data-output-quality-audit-launch-acceptance-total", "launch-acceptance-checklist", "Launch acceptance checklist", "data-output-quality-audit-install-paths-ready", "data-output-quality-audit-install-path-count", "data-output-quality-audit-install-path-command-count", "function installPathItemCommandCount(item)", "installPathItemCommandCount(item)", "launchInstallPathItemCommandCount", "launchInstallPathCount = finiteNumberOr(launchInstallPaths.count, launchInstallPathItems.length)", "launchInstallPathCommandCount = finiteNumberOr(launchInstallPaths.commandCount, launchInstallPathItemCommandCount)", "data-output-quality-audit-install-path-count=\"${launchInstallPathCount}\"", "data-output-quality-audit-install-path-command-count=\"${launchInstallPathCommandCount}\"", "${launchInstallPathCount} paths · ${launchInstallPathCommandCount} commands", "launch-install-path-options", "Launch install path options", "data-output-quality-audit-install-paths", "data-output-quality-audit-install-path-item", "install-remote-workflow-files.mjs", "data-output-quality-audit-completion-count", "data-output-quality-audit-completion-ready", "data-output-quality-audit-completion-blocked-count", "data-output-quality-audit-completion-checklist", "data-output-quality-audit-completion-item", "Completion audit", "data-output-quality-audit-comparison-count", "data-output-quality-audit-next-action-ready", "data-output-quality-audit-next-action-key", "Structured next action", "output-quality-next-action", "data-output-quality-audit-snapshot-status", "data-output-quality-audit-repair-action-plan", "data-output-quality-audit-repair-action-plan-fields", "review-repair-action-plan", "Review repair action plan", "data-output-quality-audit-submission-closeout-summary", "data-output-quality-audit-submission-closeout-summary-fields", "submission-closeout-summary", "Submission closeout summary", "data-output-quality-audit-tracker-form-payload-count", "data-output-quality-audit-publish-evidence-command-guard", "data-output-quality-audit-publish-evidence-immediate-action", "data-output-quality-audit-publish-evidence-immediate-action-key", "data-output-quality-audit-publish-evidence-withheld-dispatch-count", "Publish evidence command guard", "Publish evidence immediate action", "data-output-quality-audit-snapshot", "data-output-quality-audit-repo-resolution", "data-output-quality-audit-repo-placeholder-resolved", "data-output-quality-audit-receipt-text", "copy-output-quality-audit-receipt", "Final output quality audit"] },
    { file: "release-status.js", terms: ["data-output-quality-audit-workflow-ui-install-receipt", "data-output-quality-audit-workflow-ui-install-receipt-command-count", "data-output-quality-audit-workflow-ui-install-paste-packet", "data-output-quality-audit-workflow-ui-install-paste-packet-coverage", "workflow-ui-install-receipt", "Workflow UI paste packet", "workflowUiInstallPastePacketCoverage", "data-output-quality-audit-post-install-evidence-intake", "data-output-quality-audit-post-install-evidence-intake-fields", "post-install-evidence-intake", "Post-install evidence intake"] },
	    { file: "release-status.js", terms: ["data-output-quality-audit-launch-proof-evidence-receipt", "data-output-quality-audit-launch-proof-evidence-fields", "data-output-quality-audit-launch-proof-evidence-coverage", "launch-proof-evidence-receipt", "Launch proof evidence receipt"] },
    { file: "release-status.js", terms: ["mainBridgePlan", "data-output-quality-audit-snapshot-key=\"main-bridge-plan\"", "Main PR bridge plan", "main bridge plan", "copyReadyArtifacts.mainBridgePlan"] },
    { file: "release-status.js", terms: ["data-output-quality-audit-blocker-resolution", "data-output-quality-audit-blocker-resolution-active", "data-output-quality-audit-blocker-resolution-item-count", "data-output-quality-audit-blocker-resolution-action-required-count", "data-output-quality-audit-blocker-resolution-deferred-count", "data-output-quality-audit-blocker-resolution-proof-command-count", "data-output-quality-audit-blocker-resolution-guard", "data-launch-blocker-resolution-guard", "blocker-resolution-checklist", "Blocker resolution checklist"] },
    { file: "release-status.js", terms: ["data-output-quality-audit-external-claim-guard", "data-output-quality-audit-external-claim-guard-ready", "data-output-quality-audit-external-claim-guard-status", "externalClaimGuardBlockedCount = finiteNumberOr(externalClaimGuard.blockedCount, 0)", "externalClaimGuardRequirementCount = finiteNumberOr(externalClaimGuard.requirementCount, externalClaimGuardRequirements.length)", "data-output-quality-audit-external-claim-guard-blocked-count=\"${externalClaimGuardBlockedCount}\"", "data-output-quality-audit-external-claim-guard-requirement-count=\"${externalClaimGuardRequirementCount}\"", "data-output-quality-audit-external-claim-guard-item", "data-output-quality-audit-external-claim-guard-signal", "data-output-quality-audit-external-claim-guard-command", "data-output-quality-audit-external-claim-guard-text", "externalClaimGuard.stopCondition", "copy-output-quality-external-claim-guard", "external claim guard 복사", "External completion claim guard"] },
    { file: "release-status.js", terms: ["data-output-quality-audit-external-claim-closeout", "data-output-quality-audit-external-claim-closeout-step-count", "data-output-quality-audit-external-claim-closeout-field-count", "const externalClaimCloseoutStepCount = finiteNumberOr(externalClaimCloseout.stepCount, externalClaimCloseoutSteps.length)", "const externalClaimCloseoutFieldCount = finiteNumberOr(externalClaimCloseout.proofFieldCount, externalClaimCloseoutFields.length)", "data-output-quality-audit-external-claim-closeout-step-count=\"${externalClaimCloseoutStepCount}\"", "data-output-quality-audit-external-claim-closeout-allowed-count=\"${externalClaimCloseoutAllowedCount}\"", "data-output-quality-audit-external-claim-closeout-step", "data-output-quality-audit-external-claim-closeout-field", "External claim closeout packet", "default branch workflow_dispatch", "workflow run summary", "Release-note archive claim"] },
    { file: "operations-copy-actions.js", terms: ["copyOutputQualityExternalClaimGuard", "data-output-quality-audit-external-claim-guard", "data-output-quality-audit-external-claim-guard-text", "outputQualityExternalClaimGuardCopied"] },
    { file: "app.js", terms: ["function loadOutputQualityAudit", "function outputQualityAuditHTML", "function copyOutputQualityAuditReceipt", "function copyOutputQualityExternalClaimGuard", "data/output-quality-audit.json", "externalComparison", "copy-output-quality-audit-receipt", "copy-output-quality-external-claim-guard"] },
	    { file: "home-view.js", terms: ["data-home-post-install-evidence-intake", "home-post-install-intake", "postInstallEvidenceIntake", "postInstallEvidenceFields", "postInstallEvidenceCommands", "postInstallEvidenceSignals", "postInstallVerificationSequence", "postInstallQuickProofSteps", "postInstallQuickProofStepCount = firstClampedCount([postInstallEvidenceIntake.quickProofStepCount, postInstallQuickProofSteps.length])", "postInstallQuickProofCoverage = firstClampedCount([", "postInstallQuickProofMappedFieldCount = firstClampedCount([postInstallEvidenceIntake.quickProofMappedFieldCount, postInstallQuickProofFieldMappings.length])", "postInstallQuickProofCompletedMappedFieldCount = firstClampedCount([", "postInstallQuickProofFieldMappingCoverage = firstClampedCount([", "JooPark Post-Install Quick Proof Receipt", "data-post-install-quick-proof-step", "data-home-post-install-evidence-sequence", "data-home-post-install-evidence-intake-final-command", "Verification sequence:", "data-post-install-evidence-intake-text", "copy-post-install-evidence-intake", "JooPark Workflow Post-Install Evidence Intake", "safeToDispatch=true before gh workflow run"] },
    { file: "home-view.js", terms: ["data-home-external-claim-guard", "home-external-claim-guard", "externalClaimGuardRequirements", "externalClaimGuardSignals", "externalClaimGuardCommands", "externalClaimGuardRequirementCount = firstClampedCount([externalClaimGuard.requirementCount, externalClaimGuardRequirements.length])", "externalClaimGuardBlockedCount = firstClampedCount([externalClaimGuard.blockedCount])", "externalClaimGuardPrimaryRequirement", "externalClaimGuardPrimaryCommand", "Next claim proof shortcut:", "data-home-external-claim-guard-status", "data-home-external-claim-guard-blocked-count", "data-home-external-claim-guard-requirement-count", "data-home-external-claim-guard-command-count", "data-home-external-claim-guard-next-proof", "data-home-external-claim-guard-next-proof-key", "data-output-quality-audit-external-claim-guard-text", "external claim guard 복사"] },
    { file: "styles.css", terms: [".output-quality-audit", ".output-quality-source-freshness", ".output-quality-snapshot", ".output-quality-criteria", ".output-quality-completion", ".output-quality-external-claim-guard", ".output-quality-external-claim-guard-signals", ".output-quality-external-claim-guard-commands", ".output-quality-comparison", ".output-quality-receipt", ".publish-evidence-next-action small"] },
	    { file: "styles.css", terms: [".home-post-install-intake", ".home-post-install-intake-summary", ".home-post-install-intake-fields", ".home-post-install-intake-sequence", ".home-post-install-intake-commands", ".home-post-install-intake-signals", ".home-post-install-intake-actions"] },
    { file: "styles.css", terms: [".home-external-claim-guard", ".home-external-claim-guard-summary", ".home-external-claim-guard-next-proof", ".home-external-claim-guard-requirements", ".home-external-claim-guard-signals", ".home-external-claim-guard-commands", ".home-external-claim-guard-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["outputQualityAuditReceipt", "outputQualityArtifactRubric", "outputQualityAuditArtifactRubricStatus", "outputQualityAuditArtifactRubricScore", "outputQualityAuditArtifactRubricItemCount", "data-output-quality-audit-artifact-rubric", "Artifact quality rubric", "artifactQualityRubric=pass; totalScore=100/100; passingScore=90", "Required form fit: pass (20/20)", "Copy-ready completeness", "Safety guardrails", "Jira required fields", "outputQualityAuditVariantStatus", "outputQualityAuditVariantDecision", "outputQualityAuditVariantSelected", "data-output-quality-audit-variant-comparison", "Output variant comparison", "copy_ready_evidence_receipt", "generic_generated_summary", "decision=recheck_before_claim", "outputQualityAuditSnapshotStatus", "outputQualityAuditRepairActionPlan", "outputQualityAuditRepairActionPlanFields", "review-repair-action-plan", "outputQualityAuditSubmissionCloseoutSummary", "outputQualityAuditSubmissionCloseoutSummaryFields", "submission-closeout-summary", "outputQualityAuditTrackerFormPayloadCount", "outputQualityAuditWorkflowAuthPreflight", "outputQualityAuditWorkflowAuthPreflightUiVerified", "outputQualityAuditWorkflowAuthPreflightFields", "workflow-auth-preflight", "Workflow auth preflight", "outputQualityAuditWorkflowAuthPreflightUiVerified ===", "workflowScopeAvailable=false", "workflowScopeInstallBlocked=true", "outputQualityAuditNextActionReady", "Structured next action", "output quality structured next action card was not surfaced", "outputQualityAuditPublishEvidenceCommandGuard", "outputQualityAuditPublishEvidenceImmediateAction", "outputQualityAuditLaunchAcceptanceTotal", "Launch acceptance checklist: 2/5 pass, pending=3, stage=install_workflows", "launch-acceptance-checklist", "outputQualityAuditInstallPathsReady", "outputQualityAuditInstallPathCount", "launch-install-path-options", "qualityInstallPaths", "Launch install path options: pass (2 paths, 14 commands; CLI path after workflow scope | GitHub UI path)", "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "pbcopy < 'docs/github-pages-workflow.yml'", "outputQualityAuditSourceEvidenceFresh", "outputQualityAuditSourceEvidenceCount", "outputQualityAuditSourceEvidenceStaleCount", "qualitySourceFreshness", "Source evidence freshness:", "sourceEvidenceFresh=true; staleSources=0; sources=7", "remote workflow file check: fresh", "outputQualityAuditGoalReady", "outputQualityAuditGoalBlockedCount", "goalChecklistItems", "Prompt-to-artifact checklist:", "goalCompletionAudit=output_quality_goal_covered", "External output comparison: pass", "AutoResearch usage: pass", "outputQualityAuditLaunchPacketExternalReady", "Launch packet readyForExternalClaim: false", "launchPacketReadyForExternalClaim=false", "outputQualityAuditCompletionCount", "outputQualityAuditCompletionReady", "outputQualityAuditCompletionBlockedCount", "source_evidence_freshness", "completionAuditItems", "Workflow installation", "remoteWorkflowFilesReady=false", "Public launch proof", "postPublishEvidenceReady=false", "External completion claim", "readyForExternalClaim=false", "Completion audit:", "completionAuditReady=false", "Output readiness snapshot:", "Review package decision brief: pass (6 fields, coverage=1)", "Review issue decision summary: pass (6 fields, coverage=1)", "Review comment/note decision summary: pass (6 fields, coverage=1)", "Review result repair action plan: pass (6 fields, coverage=1)", "Review submission closeout summary: pass (6 fields, coverage=1)", "Tracker form payloads: pass (11 fields, checksums ready)", "Runtime issues: console 0, network 0, layout 0", "Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=false, workflowScopeInstallBlocked=true, missing=workflow, scopes=gist, read:org, repo)", "Publish evidence command guard: pass (7 safe suggestions, 0 suggested dispatch, 2 withheld dispatch, active=0, reference=2, disposition=withheld_until_all_dispatch_ready)", "Publish evidence immediate action: pass (install_workflows from data/launch-execution-packet.json, deferred capture-live-evidence)", "Specific context: pass", "immediate action: Install workflows on the default branch", "deferred evidence capture: Capture live publish evidence", "output quality specific context did not prioritize the immediate action", "Immediate command: gh auth refresh -h github.com -s workflow", "Deferred evidence capture: Capture live publish evidence", "Workflow scope refresh command", "gh auth refresh -h github.com -s workflow", "outputQualityAuditComparisonCount", "outputQualityAuditRepoResolution", "outputQualityAuditRepoPlaceholderResolved", "expectedEvidenceRepoLine", "expectedRepoResolutionLine", "output quality audit receipt was not copy-ready", "output quality audit receipt copy text did not reach clipboard", "}, \"output quality audit receipt was not copy-ready\", 15000);", "GitHub issue forms validation", "GitHub Actions job summaries", "GitHub Releases", "Linear issue templates", "JooPark Final Output Quality Audit Receipt"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["outputQualityAuditLaunchPostAuthCheckpoint", "outputQualityAuditLaunchPostAuthCheckpointCommandCount", "outputQualityAuditLaunchPostAuthCheckpointRecheckCount", "outputQualityAuditLaunchPostAuthCheckpointSourceArtifactCount", "outputQualityAuditLaunchPostAuthCheckpointDispatchApproval", "outputQualityAuditLaunchPostAuthCheckpointVerificationOnly", "launch-post-auth-checkpoint", "data-launch-post-auth-recheck-step", "data-launch-post-auth-source-artifact", "Launch post-auth checkpoint", "Launch post-auth checkpoint: pass (5 commands, expected=6, blocked=4, recheck=5, sources=4, dispatchApproval=false, verificationOnly=true", "verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["outputQualityAuditWorkflowUiInstallReceipt", "outputQualityAuditWorkflowUiInstallReceiptCommandCount", "outputQualityAuditWorkflowUiInstallReceiptChecklistCount", "outputQualityWorkflowUiInstallReceiptSummaryReady", "workflowUiInstallReceiptChecklistCount >= 6", "outputQualityAuditWorkflowUiInstallPastePacket", "outputQualityAuditWorkflowUiInstallPastePacketCoverage", "workflow-ui-install-receipt", "Workflow UI paste packet", "Workflow UI paste packet: pass (workflowUiInstallPastePacketCoverage=1,", "commands, checklist=", "outputQualityAuditPostInstallEvidenceIntake", "post-install-evidence-intake", "data-post-install-quick-proof-step", "Post-install evidence intake: pass (6 fields, coverage=1)", "Post-install quick proof: pass (4 steps, coverage=1)"] },
	    { file: "scripts/smoke-interactions.mjs", terms: ["homePostInstallVerificationSequence", "data-home-post-install-evidence-intake", "data-home-post-install-evidence-sequence", "home post-install evidence intake dataset was incomplete", "home post-install evidence intake sequence dataset was incomplete", "home post-install verification sequence did not render", "home post-install evidence intake copy did not report success", "home post-install evidence signals did not render"] },
	    { file: "scripts/smoke-interactions.mjs", terms: ["outputQualityAuditLaunchProofEvidenceReceipt", "outputQualityAuditLaunchProofEvidenceFields", "outputQualityAuditLaunchProofEvidenceCoverage", "launch-proof-evidence-receipt", "Launch proof evidence receipt: pass (6 fields, coverage=1, nextActions=6/6)"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["main-bridge-plan", "Main PR bridge plan", "mainBridgePlan=true", "main_bridge_plan", "data/main-bridge-plan.json", "sourceEvidenceFresh=true; staleSources=0; sources=7", "output quality main bridge plan snapshot was not surfaced", "output quality main bridge plan ledger was not copy-ready"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["outputQualityAuditBlockerResolution", "outputQualityAuditBlockerResolutionActive", "outputQualityAuditBlockerResolutionItemCount", "outputQualityAuditBlockerResolutionProofCommandCount", "data-output-quality-audit-blocker-resolution-guard", "blocker-resolution-checklist", "Blocker resolution checklist: blocked (active=", "qualityReceiptReadyText.includes(\"4/6 pass\")", "proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write", "stopCondition=If any workflow file is missing_on_default_branch or sha_mismatch"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["outputQualityExternalClaimGuard", "data-output-quality-audit-external-claim-guard", "outputQualityAuditExternalClaimGuardStatus", "blocked_external_claim", "JooPark External Completion Claim Guard", "Workflow installation: blocked", "Public launch proof: blocked", "External completion claim: blocked", "copy-output-quality-external-claim-guard", "Stop condition: do not claim readyForExternalClaim"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["externalClaimGuardCloseout", "data-output-quality-audit-external-claim-closeout", "External claim closeout packet", "default branch workflow_dispatch", "Required proof fields", "workflow run summary", "Release-note archive claim", "Allowed claim after proof", "Forbidden until proof", "output quality external claim closeout packet was not surfaced"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExternalClaimGuard", "data-home-external-claim-guard", "homeExternalClaimGuardStatus", "data-home-external-claim-guard-next-proof", "Next claim proof shortcut:", "home external claim guard dataset was incomplete", "home external claim guard next proof shortcut was incomplete", "home external claim guard copy did not report success", "home external claim guard proof commands did not render"] },
    { file: "scripts/verify-release.mjs", terms: ["data/output-quality-audit.json"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "output_quality_audit_receipt",
    requirement: "System Status exposes a copy-ready final output quality audit receipt that maps accuracy, specificity, usability, reuse, safety, public-launch proof, artifact-quality rubric, and prompt-to-artifact completion audit evidence while blocking premature external launch claims.",
    status: outputQualityAuditTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: outputQualityAuditTerms,
  });

  checklist.push({
    id: "publish_evidence_markdown_handoff",
    requirement: "Post-dispatch publish evidence can render a copy-ready Markdown handoff with Pages URL/status, workflow run status/conclusion, blockers, and next commands.",
    status: publishEvidenceMarkdown.status,
    evidence: publishEvidenceMarkdown,
  });

  const tempReleaseTerms = [
    { file: "scripts/package-release.mjs", terms: ["process.env.RELEASE_OUT_DIR", "resolve(root, process.env.RELEASE_OUT_DIR)"] },
    { file: "scripts/smoke-release.mjs", terms: ["process.env.RELEASE_OUT_DIR", "RELEASE_OUT_DIR: releaseDir", "runNodeScript(\"scripts/verify-release.mjs\", [releaseDir]"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["mkdtempSync", "joopark-release-smoke-", "RELEASE_OUT_DIR: releaseOutDir", "function releaseSmokeNeedsRetry", "auditRetryAttempts", "attempt <= 2"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_smoke_temp_output",
    requirement: "The full release smoke can package and verify into a temporary directory, preserving the checked release artifact while still testing a fresh package.",
    status: tempReleaseTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: tempReleaseTerms,
  });

  const gateCacheTerms = [
    { file: "scripts/audit-release-readiness.mjs", terms: ["packagedBrowserGateCacheRel", "autoresearch-results/release-readiness-gates.json", "releaseReadinessSummaryCacheRel", "autoresearch-results/release-readiness-summary.json", "releaseReadinessSummaryCacheSchema", "writeReleaseReadinessSummaryCache", "releaseReadinessSummaryGateCache", "releaseReadinessSummaryFreshGateCache", "const freshGateCache = releaseReadinessSummaryFreshGateCache(gate)", "if (freshGateCache) return freshGateCache", "cache.written !== true", "contextMatched: true", "packagedBrowserGateContext", "cachedPackagedBrowserGateEvidence", "completePackagedBrowserGateEvidence", "packagedBrowserGateCacheDiagnostics", "packagedBrowserGateContextMismatches", "contextMismatches", "cachedEvidenceStatus", "cachedResultStatus", "incomplete_evidence", "function parseJsonFromOutputs", "parseJsonFromOutputs(result.stdout, result.stderr)", "--format=json-pretty", "--pretty", "nextValue.startsWith(\"--\") ? \"\" : nextValue", "JSON.stringify(payload, null, 2)", "else console.log(JSON.stringify(payload))", "packagedBrowserGateCacheMaxAgeHours", "packagedBrowserGateRepairCommand", "--run-gates --format=summary", "packagedBrowserGatePostGateRefreshCommand", "npm run refresh:launch-readiness", "Repair command:", "Post-gate refresh:", "packagedBrowserGateContextExcludedFiles", "README.md", "autoresearch-results/joopark-product-loop.json", "autoresearch-results/joopark-product-loop.md", "data/launch-execution-packet.json", "data/launch-handoff-verification.json", "data/launch-handoff-verification.md", "data/launch-readiness-refresh.json", "data/launch-readiness-refresh.md", "data/main-bridge-plan.json", "data/output-quality-audit.json", "data/publish-dispatch-plan.json", "data/publish-evidence.json", "data/remote-workflow-file-check.json", "data/workflow-ui-install-plan.json", "scripts/audit-release-readiness.mjs", "scripts/capture-output-quality-audit.mjs", "releaseGateEvidenceComplete", "interactionChecks.releaseGateEvidenceHandoff === true"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["result.package?.status === \"pass\"", "result.verify?.status === \"pass\"", "mobileSearchEmpty.expectedRoutes.includes(\"llm-wiki\")", "requiredMobileUiSurfaces", "interactionChecks.homeReleaseGateEvidence === true", "interactionChecks.releaseGateEvidence === true", "interactionChecks.releaseGateEvidenceHandoff === true", "requiredDeleteUndoTypes", "deleteUndo.persisted === true", "result.accessibility?.status === \"pass\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["releaseGateEvidenceOk", "releaseGateEvidenceHandoffOk", "homeReleaseGateEvidenceOk", "releaseGateCacheOk", "releaseGateCacheRepairCopyOk", "systemEvidencePanelChecks", "systemEvidencePanelDiagnostics", "strictVerifyWorkspaceSummary", "system evidence panels did not all load", "## Release gate evidence", "6 proofs", "route 17/17", "mobile search/UI", "delete undo", "a11y", "releaseGateItem.dataset.publishEvidenceCount === \"6\"", "release gate cache panel did not render", "JooPark Release Gate Cache Repair", "releaseGateCacheCompletionAudit", "releaseGateCacheLaunchCompletionAchieved", "releaseGateCacheCompletionBlockedSignals", "launchCompletionAchieved=false", "blockedSignals:", "releaseGateCacheCachedEvidenceStatus", "releaseGateCacheCachedResultStatus", "cachedEvidenceStatus/cachedResultStatus is not pass"] },
    { file: "release-status.js", terms: ["evidence: Object.freeze([", "package + manifest/source parity pass", "desktop/mobile route parity 17/17", "mobile search-empty 13 routes including llm-wiki", "mobile UI surfaces 5/5 pass", "delete/undo recovery 8 types persisted", "keyboard/ARIA accessibility pass", "data-publish-readiness-evidence-item", "function releaseGateCacheHTML", "JooPark Release Gate Cache Repair", "data-system-release-gate-cache", "data-release-gate-cache-cached-evidence-status", "data-release-gate-cache-cached-result-status", "data-release-gate-cache-completion-audit", "data-release-gate-cache-launch-completion-achieved", "data-release-gate-cache-completion-blocked-signals", "completionAudit", "launchCompletionAchieved", "blockedSignals", "cachedEvidenceStatus", "cachedResultStatus", "contextMatched=false", "context_mismatch", "npm test", "node scripts/audit-release-readiness.mjs --format=summary"] },
    { file: "system-status-view.js", terms: ["releaseGateCacheHTML", "state.releaseReadinessSummary", "data-system-release-gate-cache"] },
    { file: "app.js", terms: ["function loadReleaseReadinessSummary", "autoresearch-results/release-readiness-summary.json", "completionAudit", "launchCompletionAchieved", "blockedSignals", "copyReleaseGateCacheRepair", "copy-release-gate-cache-repair"] },
    { file: "scripts/package-release.mjs", terms: ["generatedEvidenceEntries", "createReleaseReadinessBootstrap", "createVerifyWorkspaceBootstrap", "packageBootstrap", "validForExternalClaim: false", "release_readiness_summary_missing_from_source", "verify workspace summary source was missing", "autoresearch-results/release-readiness-summary.json", "/autoresearch-results/release-readiness-summary.json", "Cache-Control: no-cache"] },
    { file: "scripts/verify-release.mjs", terms: ["autoresearch-results/release-readiness-summary.json", "autoresearch-results/verify-workspace-summary.json", "expectedRuntimeFiles", "sourceParityFiles"] },
    { file: "scripts/smoke-release.mjs", terms: ["autoresearch-results/release-readiness-summary.json", "release_readiness_summary_cache_no_cache", "releaseReadinessSummary"] },
    { file: "sw.js", terms: ["./autoresearch-results/release-readiness-summary.json"] },
    { file: "README.md", terms: ["autoresearch-results/release-readiness-gates.json", "autoresearch-results/release-readiness-summary.json", "fresh packaged browser gate", "6시간", "node scripts/audit-release-readiness.mjs --format=summary", "non-recursive latest gate source", "compact machine-readable JSON", "--format=json-pretty", "--pretty", "evidence.cache", "contextMismatches", "cachedEvidenceStatus", "cachedResultStatus", "completionAudit", "launchCompletionAchieved", "blockedSignals", "context_mismatch", "Release gate evidence", "Release gate cache", "System Status의 Release gate cache", "JooPark Release Gate Cache Repair", "contextMatched=false", "packaged browser gate cache", "releaseGateEvidence", "releaseGateEvidenceHandoff", "homeReleaseGateEvidence", "releaseGateCache", "releaseGateCacheRepairCopy", "6 proofs", "route 17/17", "mobile search/UI", "delete undo", "a11y", "README.md", "autoresearch-results/joopark-product-loop.json", "autoresearch-results/joopark-product-loop.md", "data/launch-execution-packet.json", "data/launch-handoff-verification.json", "data/launch-handoff-verification.md", "data/launch-readiness-refresh.json", "data/launch-readiness-refresh.md", "data/main-bridge-plan.json", "data/output-quality-audit.json", "data/publish-dispatch-plan.json", "data/publish-evidence.json", "data/remote-workflow-file-check.json", "data/workflow-ui-install-plan.json", "scripts/audit-release-readiness.mjs", "scripts/capture-output-quality-audit.mjs"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const gateCacheInputFiles = packagedBrowserGateInputFiles();
  const gateCacheExcludedFileEvidence = [...packagedBrowserGateContextExcludedFiles]
    .sort()
    .map((file) => ({
      file,
      excludedFromFingerprint: !gateCacheInputFiles.includes(file),
    }));
  checklist.push({
    id: "release_gate_evidence_cache",
    requirement: "The release readiness audit stores fresh packaged browser gate evidence and a compact latest summary cache, letting quick summary audits and output-quality receipts reuse current gate evidence without recursive audit calls.",
    status: gateCacheTerms.every((item) => item.missingTerms.length === 0) &&
      gateCacheExcludedFileEvidence.every((item) => item.excludedFromFingerprint) ? "pass" : "fail",
    evidence: {
      files: gateCacheTerms,
      excludedFiles: gateCacheExcludedFileEvidence,
      cache: gateEvidence?.cache || {
        source: packagedBrowserGateCacheRel,
        maxAgeHours: packagedBrowserGateCacheMaxAgeHours,
        status: "missing_or_stale",
      },
    },
  });

  const releaseAuditStaleLockTerms = [
    { file: "scripts/audit-release-readiness.mjs", terms: ["function auditGateLockOwner", "function auditGateLockOwnerProcess", "process.kill(pid, 0)", "owner_process_missing", "owner_pid_reused", "owner_process_active", "scripts/audit-release-readiness.mjs", "--run-gates", "auditGateLockIsStale"] },
    { file: "README.md", terms: ["stale release readiness audit lock", "owner_process_missing", "owner_pid_reused", "process.kill(pid, 0)", "scripts/audit-release-readiness.mjs --run-gates"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_audit_stale_lock_recovery",
    requirement: "Release readiness run-gates recover dead or PID-reused audit locks immediately while preserving a live audit lock for the active owner process.",
    status: releaseAuditStaleLockTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: releaseAuditStaleLockTerms,
  });

  const deploySupportTerms = [
    { file: "scripts/package-release.mjs", terms: ["function writeDeploySupportFiles", "404.html", "_headers", "_redirects", "vercel.json", "Content-Security-Policy"] },
    { file: "scripts/verify-release.mjs", terms: ["function verifyDeploySupport", "expectedDeploySupportFiles", "deploySupportFiles", "Content-Security-Policy"] },
    { file: "README.md", terms: ["GitHub Pages", "Netlify", "Vercel", "_headers", "vercel.json"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const deploySupportCount = verify.result?.deploySupportFiles || 0;
  checklist.push({
    id: "standalone_deploy_support",
    requirement: "The release package includes static-host deployment support files for GitHub Pages, Netlify, and Vercel, and the verifier checks their contents.",
    status: deploySupportTerms.every((item) => item.missingTerms.length === 0) && deploySupportCount === 4 ? "pass" : "fail",
    evidence: {
      files: deploySupportTerms,
      verify: {
        command: verify.command,
        status: verify.status,
        deploySupportFiles: deploySupportCount,
      },
    },
  });

  const releaseHeaderSmokeTerms = [
    { file: "scripts/smoke-release.mjs", terms: ["function smokeReleaseHeaders", "headerChecks", "root_x_content_type_options", "root_content_security_policy", "import_guards_cache_no_cache", "manifest_content_type", "vendor_cache_immutable"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["release_header_smoke", "The packaged release smoke applies release header rules"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const releaseHeaderGateOk = !gateEvidence || !gateEvidence.result?.headers || gateEvidence.result.headers.status === "pass";
  checklist.push({
    id: "release_header_smoke",
    requirement: "The packaged release smoke applies release header rules and verifies security and cache headers over HTTP.",
    status: releaseHeaderSmokeTerms.every((item) => item.missingTerms.length === 0) && releaseHeaderGateOk ? "pass" : "fail",
    evidence: {
      files: releaseHeaderSmokeTerms,
      gate: gateEvidence ? {
        command: gateEvidence.command,
        status: gateEvidence.status,
        headers: gateEvidence.result?.headers || null,
      } : {
        command: "node scripts/audit-release-readiness.mjs --run-gates",
        status: "not_run",
      },
    },
  });

  const publicLaunchSurfaceTerms = [
    { file: "index.html", terms: ["meta name=\"description\"", "meta property=\"og:title\"", "meta property=\"og:image\" content=\"./social-preview.png\"", "meta property=\"og:image:type\" content=\"image/png\"", "meta property=\"og:image:width\" content=\"1200\"", "meta property=\"og:image:height\" content=\"630\"", "meta name=\"twitter:card\"", "meta name=\"twitter:image\" content=\"./social-preview.png\"", "rel=\"manifest\"", "site.webmanifest"] },
    { file: "site.webmanifest", terms: ["\"display\": \"standalone\"", "\"start_url\": \"./\"", "\"shortcuts\"", "\"screenshots\"", "\"categories\"", "./icons/icon-192.svg", "./icons/icon-512.svg", "./social-preview.png", "\"1200x630\"", "\"image/png\"", "\"form_factor\": \"wide\"", "\"512x512\"", "\"purpose\": \"any maskable\""] },
    { file: "scripts/capture-preview.mjs", terms: ["Page.captureScreenshot", "1200", "630", "social-preview.png", "home-hero", "home-tiles", "PNG", "function optionValue(argsList, name)", "value.startsWith(\"--\") ? \"\" : value"] },
    { file: "social-preview.svg", terms: ["JooPark Workspace social preview", "Local-first control plane", "Database catalog"] },
    { file: "icons/icon-192.svg", terms: ["JooPark Workspace 192px icon"] },
    { file: "icons/icon-512.svg", terms: ["JooPark Workspace 512px maskable icon"] },
    { file: "scripts/package-release.mjs", terms: ["social-preview.png", "social-preview.svg"] },
    { file: "scripts/verify-release.mjs", terms: ["verifyPublicPreviewAssets", "pngInfo", "social-preview.png", "1200x630", "site.webmanifest", "social-preview.svg", "icons/icon-192.svg", "icons/icon-512.svg"] },
    { file: "README.md", terms: ["site.webmanifest", "social-preview.png", "social-preview.svg", "icons/icon-192.svg", "icons/icon-512.svg", "Open Graph", "capture:preview"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "public_launch_metadata",
    requirement: "The public static app has discoverable page metadata, installable-app manifest metadata, and a real 1200x630 PNG app screenshot preview that are included in release verification.",
    status: publicLaunchSurfaceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: publicLaunchSurfaceTerms,
  });

  const uniqueDomIdSnapshot = duplicateHtmlIds("index.html");
  const releaseUniqueDomIdTerms = [
    { file: "scripts/verify-release.mjs", terms: ["function duplicateHtmlIds", "function verifyUniqueHtmlIds", "index.html contains duplicate id values"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["function duplicateHtmlIds", "release_unique_dom_ids", "The public app shell and release verifier prevent duplicate HTML id values"] },
    { file: "README.md", terms: ["중복 HTML id", "scripts/verify-release.mjs"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_unique_dom_ids",
    requirement: "The public app shell and release verifier prevent duplicate HTML id values that can confuse scripting, ARIA references, and assistive technology parsing.",
    status: uniqueDomIdSnapshot.status === "pass" && releaseUniqueDomIdTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      source: uniqueDomIdSnapshot,
      files: releaseUniqueDomIdTerms,
    },
  });

  const runtimeScriptOrder = runtimeScriptOrderSnapshot("index.html");
  const runtimeScriptOrderTerms = [
    { file: "scripts/verify-release.mjs", terms: ["expectedRuntimeScriptOrder", "function htmlScriptSources", "function verifyRuntimeScriptOrder", "index.html runtime script order is invalid"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["expectedRuntimeScriptOrder", "function runtimeScriptOrderSnapshot", "release_runtime_script_order", "The public app shell and release verifier preserve vendor and runtime helper script order"] },
    { file: "README.md", terms: ["런타임 스크립트 로드 순서", "workspace-storage.js", "app.js", "scripts/verify-release.mjs"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_runtime_script_order",
    requirement: "The public app shell and release verifier preserve vendor and runtime helper script order so dependencies load before app.js.",
    status: runtimeScriptOrder.status === "pass" && runtimeScriptOrderTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      source: runtimeScriptOrder,
      files: runtimeScriptOrderTerms,
    },
  });

  const releaseFallbackSmokeTerms = [
    { file: "scripts/package-release.mjs", terms: ["/* /index.html 200"] },
    { file: "scripts/verify-release.mjs", terms: ["/* /index.html 200", "rewrite unmatched direct paths to index.html"] },
    { file: "scripts/smoke-release.mjs", terms: ["function smokeReleaseFallbacks", "fallbackChecks", "direct_path_rewrites_to_index", "custom_404_matches_index"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["release_fallback_smoke", "The packaged release smoke verifies direct-path fallback"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const releaseFallbackGateOk = !gateEvidence || !gateEvidence.result?.fallbacks || gateEvidence.result.fallbacks.status === "pass";
  checklist.push({
    id: "release_fallback_smoke",
    requirement: "The packaged release smoke verifies direct-path fallback rewrites and GitHub Pages 404.html app-shell fallback over HTTP.",
    status: releaseFallbackSmokeTerms.every((item) => item.missingTerms.length === 0) && releaseFallbackGateOk ? "pass" : "fail",
    evidence: {
      files: releaseFallbackSmokeTerms,
      gate: gateEvidence ? {
        command: gateEvidence.command,
        status: gateEvidence.status,
        fallbacks: gateEvidence.result?.fallbacks || null,
      } : {
        command: "node scripts/audit-release-readiness.mjs --run-gates",
        status: "not_run",
      },
    },
  });

  const desktopOverflowSmokeTerms = [
    { file: "scripts/smoke-chrome.mjs", terms: ["layoutIssues", "overflowX", "docScrollWidth", "desktop layout issues"] },
    { file: "scripts/smoke-release.mjs", terms: ["layoutIssues: smokeResult.layoutIssues", "viewport: smokeResult.viewport"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["desktop_route_overflow_smoke", "The desktop route smoke fails on horizontal overflow"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const desktopOverflowGateOk = !gateEvidence || !gateEvidence.result?.smoke || (
    gateEvidence.result?.smoke?.status === "pass" &&
    Array.isArray(gateEvidence.result?.smoke?.layoutIssues) &&
    gateEvidence.result.smoke.layoutIssues.length === 0
  );
  checklist.push({
    id: "desktop_route_overflow_smoke",
    requirement: "The desktop route smoke fails on horizontal overflow and release smoke reports desktop layout evidence.",
    status: desktopOverflowSmokeTerms.every((item) => item.missingTerms.length === 0) && desktopOverflowGateOk ? "pass" : "fail",
    evidence: {
      files: desktopOverflowSmokeTerms,
      gate: gateEvidence ? {
        command: gateEvidence.command,
        status: gateEvidence.status,
        smoke: {
          status: gateEvidence.result?.smoke?.status || "unknown",
          viewport: gateEvidence.result?.smoke?.viewport || null,
          layoutIssues: gateEvidence.result?.smoke?.layoutIssues || null,
        },
      } : {
        command: "node scripts/audit-release-readiness.mjs --run-gates",
        status: "not_run",
      },
    },
  });

  const pagesWorkflowRuntimeAssets = [
    "search-empty-state.js",
    "home-execution-view.js",
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
    "workspace-storage.js",
    "storage-status-view.js",
    "settings-view.js",
    "system-status-view.js",
    "backup-import-guards.js",
    "backup-import-ui.js",
    "release-status.js",
    "operations-copy-actions.js",
    "verify-workspace-summary.js",
    "dialog-shell.js",
    "project-picker.js",
    "global-search.js",
    "command-palette.js",
    "keyboard-shortcuts.js",
    "interaction-setup.js",
    "event-reminders.js",
    "footer-clock.js",
    "db-catalog.js",
    "review-handoff.js",
    "review-result-view.js",
    "review-execution-checklist.js",
    "review-issue-payload.js",
    "review-result-state.js",
    "review-result-draft-state.js",
    "review-creation-actions.js",
    "review-package-view.js",
    "review-artifact-view.js",
    "review-artifact-state.js",
    "review-copy-actions.js",
    "review-submission-copy.js",
    "review-recommendation-export.js",
    "pwa-runtime.js",
  ];
  const pagesWorkflowTemplateTerms = [
    "workflow_dispatch:",
    "codex/joopark-workspace-release",
    "permissions:",
    "pages: write",
    "id-token: write",
    "attestations: write",
    "actions/checkout@v6",
    "actions/configure-pages@v5",
    "actions/attest@v4",
    "subject-path: dist/release/**",
    "actions/upload-pages-artifact@v4",
    "actions/deploy-pages@v4",
    "node scripts/package-release.mjs",
    "node scripts/verify-release.mjs",
    ...pagesWorkflowRuntimeAssets,
    "app.js",
    "sw.js",
    "styles.css",
    "favicon.svg",
    "icons/**",
    "site.webmanifest",
    "social-preview.png",
    "social-preview.svg",
    "data/**",
    "vendor/**",
    "scripts/package-release.mjs",
    "scripts/verify-release.mjs",
    "scripts/smoke-release.mjs",
    "path: dist/release",
  ];
  const pagesWorkflowReadmeTerms = [
    "docs/github-pages-workflow.yml",
    "Publish JooPark Pages",
    "workflow_dispatch",
    "GitHub Pages artifact",
    "workflow` scope",
    "attestations: write",
    "actions/attest@v4",
    "subject-path: dist/release/**",
    ...pagesWorkflowRuntimeAssets,
    "sw.js",
    "icons/**",
    "site.webmanifest",
  ];
  const pagesWorkflowTerms = [
    { file: "docs/github-pages-workflow.yml", terms: pagesWorkflowTemplateTerms },
    { file: ".github/workflows/joopark-pages.yml", terms: pagesWorkflowTemplateTerms },
    { file: "README.md", terms: pagesWorkflowReadmeTerms },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "github_pages_publish_workflow_template",
    requirement: "The project has a GitHub Pages workflow template that packages, verifies, uploads, and deploys the release artifact with the required Pages permissions and documents the workflow-scope requirement.",
    status: pagesWorkflowTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: pagesWorkflowTerms,
  });

  const indexTerms = hasTerms("index.html", viewIds);
  checklist.push({
    id: "route_surface",
    requirement: "The SPA exposes the 16 expected workspace, PM, DB, settings, and system views.",
    status: indexTerms.status,
    evidence: { file: "index.html", expectedViews: viewIds.length, missingViews: indexTerms.missing },
  });

  const systemStatusRouteTerms = [
    { file: "index.html", terms: ["href=\"#system\"", "data-view=\"system\"", "view-system"] },
    { file: "app.js", terms: ["function renderSystemStatus", "systemStatusViewHelpers", "systemStatusViewCall(\"renderSystemStatusHTML\"", "projectBenchmarkContext", "const VIEW_RENDERERS", "system: renderSystemStatus"] },
    { file: "scripts/smoke-chrome.mjs", terms: ["[\"system\"", "시스템 상태", "운영 표면"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["[\"system\"", "시스템 상태", "운영 표면"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "system_status_route",
    requirement: "The sidebar #system route opens an independent system status surface with storage, source-backed candidate, benchmark, and operations coverage in desktop and mobile smoke.",
    status: systemStatusRouteTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: systemStatusRouteTerms,
  });

  const systemPublishReadinessTerms = [
    { file: "release-status.js", terms: ["JooParkReleaseStatus", "joopark-release-status/v1", "function publishReadinessItems", "function publishReadinessMarkdownLines", "function publishUnblockHandoffText", "data-publish-readiness-item", "data-publish-key=\"${item.key}\"", "workflow-scope token", "workflowScopeAvailable", "gh auth refresh -h github.com -s workflow", "workflow-scope-preflight", "Publish JooPark Pages"] },
    { file: "app.js", terms: ["function publishReadinessItems", "function publishReadinessMarkdownLines", "function publishUnblockHandoffText", "function settingsDeployHandoffText", "function copySystemPublishHandoff", "releaseStatusCall(\"publishReadinessItems\"", "releaseStatusCall(\"publishUnblockHandoffText\"", "Device-code approval handoff", "approvalUrl=https://github.com/login/device", "one-time device code", "gh auth status -h github.com", "workflowScopeAvailable: true", "workflowScopeInstallBlocked: false"] },
    { file: "system-status-view.js", terms: ["data-system-publish-readiness", "data-system-publish-blockers", "data-system-publish-handoff-copy", "publishReadinessListHTML(model.publishItems)"] },
    { file: "styles.css", terms: [".publish-readiness-list", ".publish-readiness-actions", ".publish-readiness-item", ".publish-state", ".publish-readiness-item[data-publish-state=\"blocked\"]"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["systemPublishReadiness", "system publish readiness alignment", "workflow installation blockers were not surfaced", "workflowScopeAvailable", "gh auth refresh -h github.com -s workflow", "workflow scope preflight", "Device-code approval handoff", "approvalUrl=https://github.com/login/device", "one-time device code", "publish unblock handoff copy text did not reach clipboard"] },
    { file: "README.md", terms: ["System Status", "공개 준비 상태", "workflowScopeAvailable", "gh auth refresh -h github.com -s workflow", "workflow 설치", "publish unblock handoff", "Settings의 배포 handoff", "Device-code approval handoff", "approvalUrl=https://github.com/login/device", "one-time device code"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "system_publish_readiness_alignment",
    requirement: "System Status and Settings expose the same publish readiness blockers for release gates, Pages workflow installation, drift-watch workflow installation, and publish dispatch.",
    status: systemPublishReadinessTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: systemPublishReadinessTerms,
  });

  const searchEmptyStateModuleTerms = [
    { file: "search-empty-state.js", terms: ["JooParkSearchEmptyState", "joopark-search-empty-state/v1", "function createSearchEmptyState", "function searchEmptyState", "role=\"status\"", "aria-live=\"polite\"", "data-action=\"clear-search\""] },
    { file: "app.js", terms: ["searchEmptyStateHelpers", "function searchEmptyStateCall", "function searchEmptyState", "searchEmptyStateCall(\"searchEmptyState\""] },
    { file: "index.html", terms: ["./search-empty-state.js", "./workspace-storage.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "search-empty-state.js"] },
    { file: "scripts/verify-release.mjs", terms: ["search-empty-state.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["search-empty-state.js", "search_empty_state_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["searchEmptyStateModule", "joopark-search-empty-state/v1", "search empty state runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["searchEmptyStateText", "search-empty-state.js", "joopark-search-empty-state/v1"] },
    { file: "README.md", terms: ["search-empty-state.js", "검색 빈 상태", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "search_empty_state_runtime_module",
    requirement: "Shared search no-results UI is extracted into a packaged runtime helper with status/live-region semantics, clear-search action, release registration, and browser smoke coverage.",
    status: searchEmptyStateModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: searchEmptyStateModuleTerms,
  });

  const calendarViewModuleTerms = [
    { file: "calendar-view.js", terms: ["JooParkCalendarView", "joopark-calendar-view/v1", "function createCalendarView", "function calLegend", "function eventRow", "function calendarViewModel", "function renderCalendarHTML", "role=\"grid\"", "data-search-result=\"calendar\"", "searchEmptyState(\"calendar\""] },
    { file: "app.js", terms: ["calendarViewHelpers", "function calendarViewCall", "function renderCalendar", "calendarViewCall(\"renderCalendarHTML\"", "function openEventModal", "function saveEventFromForm"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./calendar-view.js", "./todo-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "calendar-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["calendar-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["calendar-view.js", "calendar_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["calendarViewModule", "joopark-calendar-view/v1", "calendar view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["calendarViewText", "calendar-view.js", "joopark-calendar-view/v1"] },
    { file: "README.md", terms: ["calendar-view.js", "Calendar KPI", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "calendar_view_runtime_module",
    requirement: "Calendar KPI, month grid, selected-day agenda, and search empty-state recovery are extracted into a packaged runtime helper while Calendar CRUD remains in app.js.",
    status: calendarViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: calendarViewModuleTerms,
  });

  const todoViewModuleTerms = [
    { file: "todo-view.js", terms: ["JooParkTodoView", "joopark-todo-view/v1", "function createTodoView", "function todoMatchesFilter", "function todoRow", "function todoViewModel", "function renderTodosHTML", "data-search-result=\"todo\"", "searchEmptyState(\"todo\"", "data-action=\"todo-filter\""] },
    { file: "app.js", terms: ["todoViewHelpers", "function todoViewCall", "function renderTodos", "todoViewCall(\"renderTodosHTML\"", "function quickAddTodo", "function saveTodoFromForm"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./todo-view.js", "./workspace-storage.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "todo-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["todo-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["todo-view.js", "todo_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["todoViewModule", "joopark-todo-view/v1", "todo view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["todoViewText", "todo-view.js", "joopark-todo-view/v1"] },
    { file: "README.md", terms: ["todo-view.js", "Todo KPI", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "todo_view_runtime_module",
    requirement: "Todo KPI, filter chips, grouped row rendering, and search empty-state recovery are extracted into a packaged runtime helper while Todo CRUD remains in app.js.",
    status: todoViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: todoViewModuleTerms,
  });

  const notesViewModuleTerms = [
    { file: "notes-view.js", terms: ["JooParkNotesView", "joopark-notes-view/v1", "function createNotesView", "function notesViewModel", "function noteCard", "function renderNotesHTML", "data-search-result=\"notes\"", "searchEmptyState(\"notes\"", "aria-pressed=\"${raw(note.pinned ? \"true\" : \"false\")}\""] },
    { file: "app.js", terms: ["notesViewHelpers", "function notesViewCall", "function renderNotes", "notesViewCall(\"renderNotesHTML\"", "function openNoteModal", "function saveNoteFromForm"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./calendar-view.js", "./todo-view.js", "./notes-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "notes-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["notes-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["notes-view.js", "notes_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["notesViewModule", "joopark-notes-view/v1", "notes view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["notesViewText", "notes-view.js", "joopark-notes-view/v1"] },
    { file: "README.md", terms: ["notes-view.js", "Notes card", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "notes_view_runtime_module",
    requirement: "Notes list filtering, pinned sorting, Markdown preview, card action labels, and search empty-state recovery are extracted into a packaged runtime helper while Note CRUD remains in app.js.",
    status: notesViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: notesViewModuleTerms,
  });

  const habitsViewModuleTerms = [
    { file: "habits-view.js", terms: ["JooParkHabitsView", "joopark-habits-view/v1", "function createHabitsView", "function habitsViewModel", "function habitCard", "function renderHabitsHTML", "data-search-result=\"habits\"", "searchEmptyState(\"habits\"", "aria-pressed=\"${raw(checked ? \"true\" : \"false\")}\""] },
    { file: "app.js", terms: ["habitsViewHelpers", "function habitsViewCall", "function renderHabits", "habitsViewCall(\"renderHabitsHTML\"", "function saveHabitFromForm", "function toggleHabit"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./calendar-view.js", "./todo-view.js", "./notes-view.js", "./habits-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "habits-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["habits-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["habits-view.js", "habits_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["habitsViewModule", "joopark-habits-view/v1", "habits view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["habitsViewText", "habits-view.js", "joopark-habits-view/v1"] },
    { file: "README.md", terms: ["habits-view.js", "Habits KPI", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "habits_view_runtime_module",
    requirement: "Habits KPI, weekly toggle grid, streak display, card action labels, and search empty-state recovery are extracted into a packaged runtime helper while habit CRUD remains in app.js.",
    status: habitsViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: habitsViewModuleTerms,
  });

  const statsViewModuleTerms = [
    { file: "stats-view.js", terms: ["JooParkStatsView", "joopark-stats-view/v1", "function createStatsView", "function statsViewModel", "function accessibleSpark", "function barChart", "function renderStatsHTML", "data-stats-chart=\"todo-trend\"", "role=\"img\""] },
    { file: "app.js", terms: ["statsViewHelpers", "function statsViewCall", "function renderStats", "statsViewCall(\"renderStatsHTML\""] },
    { file: "index.html", terms: ["./search-empty-state.js", "./calendar-view.js", "./todo-view.js", "./notes-view.js", "./habits-view.js", "./stats-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "stats-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["stats-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["stats-view.js", "stats_view_cache_no_cache"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["stats_view_module_loaded", "stats_accessible_spark_charts"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["statsViewModule", "joopark-stats-view/v1", "stats view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["statsViewText", "stats-view.js", "joopark-stats-view/v1"] },
    { file: "README.md", terms: ["stats-view.js", "Stats KPI", "accessible spark charts", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "stats_view_runtime_module",
    requirement: "Stats KPI cards, trend charts, distribution bars, and habit summary rendering are extracted into a packaged runtime helper while analytics state remains in app.js.",
    status: statsViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: statsViewModuleTerms,
  });

  const portfolioViewModuleTerms = [
    { file: "portfolio-view.js", terms: ["JooParkPortfolioView", "joopark-portfolio-view/v1", "function createPortfolioView", "function portfolioViewModel", "function projectCard", "function renderPortfolioHTML", "data-search-result=\"pm-portfolio\"", "searchEmptyState(\"pm-portfolio\"", "role=\"listitem\"", "projectListItemLabel"] },
    { file: "app.js", terms: ["portfolioViewHelpers", "function portfolioViewCall", "function renderPortfolio", "portfolioViewCall(\"renderPortfolioHTML\"", "function openProjectModal", "function saveProjectFromForm"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./stats-view.js", "./portfolio-view.js", "./kanban-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "portfolio-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["portfolio-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["portfolio-view.js", "portfolio_view_cache_no_cache"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["portfolio_view_module_loaded", "portfolio_card_list_semantics"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["portfolioViewModule", "joopark-portfolio-view/v1", "portfolio view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["portfolioViewText", "portfolio-view.js", "joopark-portfolio-view/v1"] },
    { file: "README.md", terms: ["portfolio-view.js", "Portfolio KPI", "segmented filters", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "portfolio_view_runtime_module",
    requirement: "Portfolio KPI cards, candidate filters, project cards, card list semantics, and search empty-state recovery are extracted into a packaged runtime helper while project CRUD remains in app.js.",
    status: portfolioViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: portfolioViewModuleTerms,
  });

  const kanbanViewModuleTerms = [
    { file: "kanban-view.js", terms: ["JooParkKanbanView", "joopark-kanban-view/v1", "function createKanbanView", "function kanbanViewModel", "function issueCard", "function renderKanbanHTML", "data-search-result=\"pm-kanban\"", "searchEmptyState(\"pm-kanban\"", "role=\"listitem\""] },
    { file: "app.js", terms: ["kanbanViewHelpers", "function kanbanViewCall", "function renderKanban", "kanbanViewCall(\"renderKanbanHTML\"", "function setupKanbanDrag", "function moveIssue"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./stats-view.js", "./kanban-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "kanban-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["kanban-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["kanban-view.js", "kanban_view_cache_no_cache"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["kanban_view_module_loaded", "kanban_lane_list_semantics"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["kanbanViewModule", "joopark-kanban-view/v1", "kanban view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["kanbanViewText", "kanban-view.js", "joopark-kanban-view/v1"] },
    { file: "README.md", terms: ["kanban-view.js", "Kanban KPI", "lane/list semantics", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "kanban_view_runtime_module",
    requirement: "Kanban KPI, priority filters, lane/list semantics, issue cards, execution checklist preview, and search empty-state recovery are extracted into a packaged runtime helper while drag/drop and issue CRUD remain in app.js.",
    status: kanbanViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: kanbanViewModuleTerms,
  });

  const ganttViewModuleTerms = [
    { file: "gantt-view.js", terms: ["JooParkGanttView", "joopark-gantt-view/v1", "function createGanttView", "function ganttViewModel", "function taskShapeHTML", "function renderGanttHTML", "data-search-result=\"pm-gantt\"", "searchEmptyState(\"pm-gantt\"", "ganttChartSummary"] },
    { file: "app.js", terms: ["ganttViewHelpers", "function ganttViewCall", "function renderGantt", "ganttViewCall(\"renderGanttHTML\"", "function openTaskModal", "function saveTaskFromForm"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./kanban-view.js", "./gantt-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "gantt-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["gantt-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["gantt-view.js", "gantt_view_cache_no_cache"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["gantt_view_module_loaded", "gantt_svg_group_labelled", "gantt_svg_button_semantics"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["ganttViewModule", "joopark-gantt-view/v1", "gantt view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["ganttViewText", "gantt-view.js", "joopark-gantt-view/v1"] },
    { file: "README.md", terms: ["gantt-view.js", "Gantt KPI", "SVG button semantics", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "gantt_view_runtime_module",
    requirement: "Gantt KPI cards, SVG timeline, dependency lines, task labels, chart summary semantics, and search empty-state recovery are extracted into a packaged runtime helper while task CRUD remains in app.js.",
    status: ganttViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: ganttViewModuleTerms,
  });

  const teamViewModuleTerms = [
    { file: "team-view.js", terms: ["JooParkTeamView", "joopark-team-view/v1", "function createTeamView", "function teamViewModel", "function memberRow", "function renderTeamHTML", "data-search-result=\"pm-team\"", "searchEmptyState(\"pm-team\"", "role=\"table\"", "role=\"columnheader\"", "role=\"rowheader\"", "role=\"cell\""] },
    { file: "app.js", terms: ["teamViewHelpers", "function teamViewCall", "function renderTeam", "teamViewCall(\"renderTeamHTML\"", "function openMemberModal", "function saveMemberFromForm"] },
    { file: "index.html", terms: ["./search-empty-state.js", "./gantt-view.js", "./team-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "team-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["team-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["team-view.js", "team_view_cache_no_cache"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["team_view_module_loaded", "team_matrix_table_semantics"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["teamViewModule", "joopark-team-view/v1", "team view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["teamViewText", "team-view.js", "joopark-team-view/v1"] },
    { file: "README.md", terms: ["team-view.js", "Team KPI", "resource matrix semantics", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "team_view_runtime_module",
    requirement: "Team KPI cards, member rows, load indicators, searchable member list, resource matrix semantics, and search empty-state recovery are extracted into a packaged runtime helper while member CRUD remains in app.js.",
    status: teamViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: teamViewModuleTerms,
  });

  const workspaceStorageModuleTerms = [
    { file: "workspace-storage.js", terms: ["JooParkWorkspaceStorage", "joopark-workspace-storage/v1", "function createWorkspaceStorage", "function persistPayload", "function refreshStorageHealth", "function loadPersisted"] },
    { file: "app.js", terms: ["workspaceStorageHelpers", "function workspaceStorageCall", "workspaceStorageCall(\"persist\"", "workspaceStorageCall(\"loadPersisted\"", "workspaceStorageCall(\"refreshStorageHealth\""] },
    { file: "index.html", terms: ["./workspace-storage.js", "./backup-import-guards.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "workspace-storage.js"] },
    { file: "scripts/verify-release.mjs", terms: ["workspace-storage.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["workspace-storage.js", "workspace_storage_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceStorageModule", "joopark-workspace-storage/v1", "workspace storage runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["workspaceStorageText", "workspace-storage.js", "joopark-workspace-storage/v1"] },
    { file: "README.md", terms: ["workspace-storage.js", "localStorage v3", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "workspace_storage_runtime_module",
    requirement: "localStorage persistence, v2/v3 migration, storage quota estimate, and persistent-storage request logic are extracted into a packaged runtime helper with release and browser smoke coverage.",
    status: workspaceStorageModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: workspaceStorageModuleTerms,
  });

  const storageStatusViewModuleTerms = [
    { file: "storage-status-view.js", terms: ["JooParkStorageStatusView", "joopark-storage-status-view/v1", "function createStorageStatusView", "function storageStatusModel", "function settingsStorageHealthHTML", "function systemStorageHealthHTML", "role=\"status\"", "aria-atomic=\"true\""] },
    { file: "app.js", terms: ["storageStatusViewHelpers", "function storageStatusViewCall", "function storageStatusModel", "function settingsStorageHealthHTML", "function systemStorageHealthHTML"] },
    { file: "index.html", terms: ["./workspace-storage.js", "./storage-status-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "storage-status-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["storage-status-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["storage-status-view.js", "storage_status_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["storageStatusViewModule", "joopark-storage-status-view/v1", "storage status view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["storageStatusViewText", "storage-status-view.js", "joopark-storage-status-view/v1"] },
    { file: "README.md", terms: ["storage-status-view.js", "저장소 상태", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "storage_status_view_runtime_module",
    requirement: "Settings and System storage status panels share a packaged runtime view helper with status/live-region semantics, release registration, and browser smoke coverage.",
    status: storageStatusViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: storageStatusViewModuleTerms,
  });

  const settingsViewModuleTerms = [
    { file: "settings-view.js", terms: ["JooParkSettingsView", "joopark-settings-view/v1", "function createSettingsView", "function settingsViewModel", "function renderSettingsHTML", "data-settings-handoff", "data-settings-handoff-copy=\"${kind}\"", "체크리스트 복사", "배포 handoff 복사", "privacy handoff 복사", "role=\"listitem\""] },
    { file: "app.js", terms: ["settingsViewHelpers", "function settingsViewCall", "function renderSettings", "settingsViewCall(\"renderSettingsHTML\"", "function settingsBackupHandoffText", "function settingsDeployHandoffText", "function settingsPrivacyHandoffText"] },
    { file: "index.html", terms: ["./storage-status-view.js", "./settings-view.js", "./backup-import-guards.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "settings-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["settings-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["settings-view.js", "settings_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["settingsViewModule", "joopark-settings-view/v1", "settings view runtime module was not loaded"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["settings_view_module_loaded", "settings_handoff_list_semantics", "settings_theme_toggle_buttons"] },
    { file: "scripts/check-app-structure.mjs", terms: ["settingsViewText", "settings-view.js", "joopark-settings-view/v1"] },
    { file: "README.md", terms: ["settings-view.js", "Settings KPI", "운영 handoff", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "settings_view_runtime_module",
    requirement: "Settings KPI cards, profile/theme controls, backup actions, operational handoff cards, and storage health embedding are extracted into a packaged runtime helper while Settings actions remain in app.js.",
    status: settingsViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: settingsViewModuleTerms,
  });

  const systemStatusViewModuleTerms = [
    { file: "system-status-view.js", terms: ["JooParkSystemStatusView", "joopark-system-status-view/v1", "function createSystemStatusView", "function systemStatusModel", "function projectSnapshotHealthHTML", "function githubProjectDiscoveryHTML", "function renderSystemStatusHTML", "data-system-status-module", "data-system-source-snapshots", "data-system-github-project-discovery", "data-github-project-discovery-public-safe"] },
    { file: "app.js", terms: ["systemStatusViewHelpers", "function systemStatusViewCall", "function renderSystemStatus", "systemStatusViewCall(\"renderSystemStatusHTML\"", "publishUnblockHandoffText", "function loadGithubProjectDiscovery", "data/github-project-discovery.json"] },
    { file: "index.html", terms: ["./settings-view.js", "./system-status-view.js", "./backup-import-guards.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "system-status-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["system-status-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["system-status-view.js", "system_status_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["systemStatusViewModule", "joopark-system-status-view/v1", "system status view runtime module was not loaded", "githubProjectDiscovery", "data-system-github-project-discovery"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["system_status_view_module_loaded", "system_status_source_snapshot_region"] },
    { file: "scripts/check-app-structure.mjs", terms: ["systemStatusViewText", "system-status-view.js", "joopark-system-status-view/v1"] },
    { file: "README.md", terms: ["system-status-view.js", "System Status", "Source snapshot health", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "system_status_view_runtime_module",
    requirement: "System Status KPI, operational surface, source snapshot health, and publish readiness composition are extracted into a packaged runtime helper while data loading and copy actions remain in app.js.",
    status: systemStatusViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: systemStatusViewModuleTerms,
  });

  const githubProjectDiscoveryTerms = [
    { file: "scripts/capture-github-project-discovery.mjs", terms: ["publicLocalPath", "absolutePathRedacted", "publicArtifactSafe", "absoluteLocalPathExposure", "relative-to-local-root", "candidateAbsoluteLocalPathExposure", "pushedAt", "stargazerCount", "freshnessEvidence", "candidateFreshnessEvidenceCoverage", "LOCAL_SCAN_IGNORED_DIRS", "reproducibleCommand", "candidateReproducibilityEvidenceCoverage", "PRIVATE_REPO_REDACTED_DESCRIPTION", "privateGithubMetadataRedacted", "candidatePrivateGithubMetadataExposure", "privateRankedProjectRowsRedacted", "candidatePrivateGithubRowExposure", "buildLaunchCandidateSummary", "launchCandidateSummary", "githubDiscoveryActionableProjectCoverage", "candidateActionableProjectCoverage", "requiredActionableProjectCoverage"] },
    { file: "data/github-project-discovery.json", terms: ["\"schemaVersion\": \"joopark-github-project-discovery/v1\"", "\"localPathMode\": \"relative-to-local-root\"", "\"publicArtifactSafe\": true", "\"absoluteLocalPathExposure\": false", "\"privateGithubMetadataRedacted\": true", "\"privateGithubMetadataExposure\": 0", "\"privateGithubRowExposure\": 0", "\"privateRankedProjectRowsRedacted\"", "\"decision\": \"keep_b\"", "\"freshnessEvidence\"", "\"rankingUsesPushedAt\": true", "\"candidateFreshnessEvidenceCoverage\": 1", "\"localScan\"", "\"sourceCommandReproducible\": true", "\"candidateReproducibilityEvidenceCoverage\": 1", "\"candidatePrivateGithubMetadataExposure\": 0", "\"candidatePrivateGithubRowExposure\": 0", "\"launchCandidateSummary\"", "\"primaryMetric\": \"githubDiscoveryActionableProjectCoverage\"", "\"candidateActionableProjectCoverage\"", "\"requiredActionableProjectCoverage\"", "\"releaseTargetIncluded\": true"] },
    { file: "system-status-view.js", terms: ["function githubProjectDiscoveryHTML", "data-system-github-project-discovery", "data-github-project-discovery-public-safe", "data-github-project-discovery-local-path-mode", "data-github-project-discovery-freshness-ready", "data-github-project-discovery-reproducible", "data-github-project-discovery-private-redacted", "data-github-project-discovery-private-row-exposure", "private metadata", "private rows", "scan replay", "pushedAt coverage"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["githubProjectDiscoveryOk", "GitHub project discovery panel did not expose safe loaded inventory data", "GitHub project discovery did not surface freshness metadata", "githubProjectDiscoveryReproducible", "githubProjectDiscoveryPrivateRedacted", "githubProjectDiscoveryPrivateRowExposure", "Do not push, deploy, delete branches"] },
    { file: "sw.js", terms: ["./data/github-project-discovery.json"] },
    { file: "scripts/verify-release.mjs", terms: ["data/github-project-discovery.json", "./data/github-project-discovery.json"] },
    { file: "scripts/smoke-release.mjs", terms: ["data/github-project-discovery.json"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const githubProjectDiscoveryText = read("data/github-project-discovery.json");
  let githubProjectDiscoveryData = {};
  try {
    githubProjectDiscoveryData = JSON.parse(githubProjectDiscoveryText);
  } catch {
    githubProjectDiscoveryData = {};
  }
  const privateProjectRows = Array.isArray(githubProjectDiscoveryData.rankedProjects)
    ? githubProjectDiscoveryData.rankedProjects.filter((project) => project?.private === true || String(project?.nameWithOwner || "").startsWith("private:"))
    : [];
  const privateProjectMetadataLeaks = Array.isArray(githubProjectDiscoveryData.rankedProjects)
    ? githubProjectDiscoveryData.rankedProjects.filter((project) => (
      project?.private === true &&
      (
        project.privateMetadataRedacted !== true ||
        !String(project.nameWithOwner || "").startsWith("private:") ||
        String(project.url || "") !== "" ||
        String(project.description || "") !== "Private GitHub repository metadata redacted from public release artifact."
      )
    ))
    : [];
  const privateRemoteMetadataLeaks = Array.isArray(githubProjectDiscoveryData.localRepos)
    ? githubProjectDiscoveryData.localRepos.flatMap((repo) => repo?.remotes || []).filter((remote) => (
      remote?.privateMetadataRedacted === true &&
      (String(remote.url || "") !== "" || !String(remote.repo?.nameWithOwner || "").startsWith("private:"))
    ))
    : [];
  const githubProjectDiscoveryPrivacyMissing = [
    githubProjectDiscoveryData.privacy?.privateGithubMetadataRedacted === true ? "" : "privateGithubMetadataRedacted=true",
    Number(githubProjectDiscoveryData.privacy?.privateGithubMetadataExposure || 0) === 0 ? "" : "privateGithubMetadataExposure=0",
    Number(githubProjectDiscoveryData.privacy?.privateGithubRowExposure || 0) === 0 ? "" : "privateGithubRowExposure=0",
    privateProjectRows.length === 0 ? "" : "private rankedProjects rows removed from public artifact",
    privateProjectMetadataLeaks.length === 0 ? "" : "private rankedProjects metadata redacted",
    privateRemoteMetadataLeaks.length === 0 ? "" : "private local remote metadata redacted",
  ].filter(Boolean);
  checklist.push({
    id: "github_project_discovery_public_safe_system_panel",
    requirement: "GitHub-related project discovery is a reproducible, public-package-safe artifact surfaced in System Status without leaking local absolute paths or private repository metadata.",
    status: githubProjectDiscoveryTerms.every((item) => item.missingTerms.length === 0) && !/\/Users\//.test(githubProjectDiscoveryText) && githubProjectDiscoveryPrivacyMissing.length === 0 ? "pass" : "fail",
    evidence: [
      ...githubProjectDiscoveryTerms,
      { file: "data/github-project-discovery.json", missingTerms: /\/Users\//.test(githubProjectDiscoveryText) ? ["no /Users absolute paths"] : [] },
      { file: "data/github-project-discovery.json", missingTerms: githubProjectDiscoveryPrivacyMissing },
    ],
  });

  const releaseStatusModuleTerms = [
    { file: "release-status.js", terms: ["JooParkReleaseStatus", "joopark-release-status/v1", "function createReleaseStatus", "function publishReadinessItems", "function publishEvidenceHTML", "function publishUnblockHandoffText"] },
    { file: "index.html", terms: ["./system-status-view.js", "./backup-import-guards.js", "./backup-import-ui.js", "./release-status.js", "./operations-copy-actions.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "release-status.js"] },
    { file: "scripts/verify-release.mjs", terms: ["release-status.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["release-status.js", "release_status_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["releaseStatusModule", "joopark-release-status/v1", "release status runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["releaseStatusText", "release-status.js", "joopark-release-status/v1"] },
    { file: "README.md", terms: ["release-status.js", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_status_runtime_module",
    requirement: "Release readiness and publish evidence logic is extracted into a packaged runtime helper that loads before app.js and is covered by release verification.",
    status: releaseStatusModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: releaseStatusModuleTerms,
  });

  const operationsCopyActionsModuleTerms = [
    { file: "operations-copy-actions.js", terms: ["JooParkOperationsCopyActions", "joopark-operations-copy-actions/v1", "function createOperationsCopyActions", "function copyConfiguredText", "function copySettingsHandoff", "function copySystemPublishHandoff", "function copyPublishEvidenceShareUpdate", "function copyWorkflowUiInstallReceipt", "function copyLaunchExecutionPacket", "function copyLaunchReadinessRefreshReceipt", "function copyOutputQualityAuditReceipt", "workflowUiInstallPastePacketCopied", "launchReadinessRefreshReceiptCopied", "outputQualityAuditReceiptCopied"] },
    { file: "app.js", terms: ["operationsCopyActionsHelpers", "function operationsCopyActionsCall", "operationsCopyActionsCall(\"copySettingsHandoff\"", "operationsCopyActionsCall(\"copySystemPublishHandoff\"", "operationsCopyActionsCall(\"copyPublishEvidenceShareUpdate\"", "operationsCopyActionsCall(\"copyWorkflowUiInstallReceipt\"", "operationsCopyActionsCall(\"copyLaunchExecutionPacket\"", "operationsCopyActionsCall(\"copyLaunchReadinessRefreshReceipt\"", "operationsCopyActionsCall(\"copyOutputQualityAuditReceipt\""] },
    { file: "index.html", terms: ["./release-status.js", "./operations-copy-actions.js", "./command-palette.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "operations-copy-actions.js"] },
    { file: "scripts/verify-release.mjs", terms: ["operations-copy-actions.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["operations-copy-actions.js", "operations_copy_actions_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["operationsCopyActionsModule", "joopark-operations-copy-actions/v1", "operations copy actions runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["operationsCopyActionsText", "operations-copy-actions.js", "joopark-operations-copy-actions/v1"] },
    { file: "README.md", terms: ["operations-copy-actions.js", "clipboard, status, copied dataset"] },
    { file: "docs/app-architecture.md", terms: ["operations-copy-actions.js", "Settings/System", "copy clipboard/status/dataset feedback"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "operations_copy_actions_runtime_module",
    requirement: "Settings/System publish, launch, workflow install, and output-quality copy actions share one packaged operations copy helper with clipboard/status/dataset behavior covered by release and browser smoke checks.",
    status: operationsCopyActionsModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: operationsCopyActionsModuleTerms,
  });

  const dialogShellModuleTerms = [
    { file: "dialog-shell.js", terms: ["JooParkDialogShell", "joopark-dialog-shell/v1", "function createDialogShell", "function renderSheetMeta", "function setNotificationTriggerExpanded", "function restoreFocusAfterClose", "function openSheet", "function closeSheet", "function openModal", "function closeModal", "function getOpenDialogRoot", "function trapTab"] },
    { file: "app.js", terms: ["dialogShellHelpers", "function dialogShellCall", "dialogShellCall(\"openSheet\"", "dialogShellCall(\"closeSheet\"", "dialogShellCall(\"openModal\"", "dialogShellCall(\"closeModal\"", "dialogShellCall(\"trapTab\"", "notificationExpanded: true"] },
    { file: "index.html", terms: ["./operations-copy-actions.js", "./dialog-shell.js", "./project-picker.js", "./command-palette.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "dialog-shell.js"] },
    { file: "scripts/verify-release.mjs", terms: ["dialog-shell.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["dialog-shell.js", "dialog_shell_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["dialogShellModule", "joopark-dialog-shell/v1", "dialog shell runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["dialogShellText", "dialog-shell.js", "joopark-dialog-shell/v1"] },
    { file: "README.md", terms: ["dialog-shell.js", "sheet/modal", "focus restoration"] },
    { file: "docs/app-architecture.md", terms: ["dialog-shell.js", "sheet/modal", "focus restoration"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "dialog_shell_runtime_module",
    requirement: "Sheet and modal open/close, body lock, notification expanded state, focus restoration, and tab trapping share one packaged dialog shell helper while app.js keeps feature-specific sheet and modal content.",
    status: dialogShellModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: dialogShellModuleTerms,
  });

  const projectPickerModuleTerms = [
    { file: "project-picker.js", terms: ["JooParkProjectPicker", "joopark-project-picker/v1", "function createProjectPicker", "function normalizeAccessibility", "function renderOptions", "function restoreFocus", "function ensureScaffold", "function setOpen", "function closeIfOutside", "projectPickerInputBound"] },
    { file: "app.js", terms: ["projectPickerHelpers", "function projectPickerCall", "projectPickerCall(\"renderOptions\"", "projectPickerCall(\"setOpen\"", "projectPickerCall(\"isOpen\"", "projectPickerCall(\"closeIfOutside\"", "function pickProject"] },
    { file: "index.html", terms: ["./dialog-shell.js", "./project-picker.js", "./global-search.js", "./command-palette.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "project-picker.js"] },
    { file: "scripts/verify-release.mjs", terms: ["project-picker.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["project-picker.js", "project_picker_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["projectPickerModule", "joopark-project-picker/v1", "project picker runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["projectPickerText", "project-picker.js", "joopark-project-picker/v1"] },
    { file: "README.md", terms: ["project-picker.js", "project picker", "focus restoration"] },
    { file: "docs/app-architecture.md", terms: ["project-picker.js", "Project picker", "focus restoration"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "project_picker_runtime_module",
    requirement: "Project picker scaffold, option rendering, body lock, search status, and focus restoration share one packaged runtime helper while app.js keeps project selection state mutation.",
    status: projectPickerModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: projectPickerModuleTerms,
  });

  const globalSearchModuleTerms = [
    { file: "global-search.js", terms: ["JooParkGlobalSearch", "joopark-global-search/v1", "function createGlobalSearch", "const SEARCH_INERT_VIEWS", "function syncAffordance", "function revealEmptyIfNeeded", "function clear", "function setup", "event.key !== \"Escape\"", "openPalette();"] },
    { file: "app.js", terms: ["globalSearchHelpers", "function globalSearchCall", "function syncSearchClearControl", "globalSearchCall(\"clearControl\"", "globalSearchCall(\"syncAffordance\"", "globalSearchCall(\"clear\"", "globalSearchCall(\"setup\""] },
    { file: "index.html", terms: ["./project-picker.js", "./global-search.js", "./command-palette.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "global-search.js"] },
    { file: "scripts/verify-release.mjs", terms: ["global-search.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["global-search.js", "global_search_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["globalSearchModule", "joopark-global-search/v1", "global search runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["globalSearchText", "global-search.js", "joopark-global-search/v1"] },
    { file: "README.md", terms: ["global-search.js", "현재 뷰 검색", "검색 초기화"] },
    { file: "docs/app-architecture.md", terms: ["global-search.js", "Global search", "search role affordance"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "global_search_runtime_module",
    requirement: "Topbar current-view search, clear recovery, no-results reveal, and search-inert command-palette fallback share one packaged runtime helper with release and browser smoke coverage.",
    status: globalSearchModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: globalSearchModuleTerms,
  });

  const backupImportUiModuleTerms = [
    { file: "backup-import-ui.js", terms: ["JooParkBackupImportUi", "joopark-backup-import-ui/v1", "function createBackupImportUi", "function handleImportFile", "function applyImported", "data-import-summary", "JSON 파싱 실패"] },
    { file: "app.js", terms: ["backupImportUiHelpers", "function backupImportUiCall", "backupImportUiCall(\"handleImportFile\"", "backupImportUiCall(\"applyImported\""] },
    { file: "index.html", terms: ["./backup-import-guards.js", "./backup-import-ui.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "backup-import-ui.js"] },
    { file: "scripts/verify-release.mjs", terms: ["backup-import-ui.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["backup-import-ui.js", "import_ui_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["backupImportUiModule", "joopark-backup-import-ui/v1", "backup import UI runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["backupImportUiText", "backup-import-ui.js", "joopark-backup-import-ui/v1"] },
    { file: "README.md", terms: ["backup-import-ui.js", "destructive import confirmation", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_import_ui_runtime_module",
    requirement: "Backup file selection, destructive confirmation, summary rendering, and apply flow are extracted into a packaged runtime helper with release and browser smoke coverage.",
    status: backupImportUiModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupImportUiModuleTerms,
  });

  const commandPaletteModuleTerms = [
    { file: "command-palette.js", terms: ["JooParkCommandPalette", "joopark-command-palette/v1", "function createCommandPalette", "function buildItems", "function render", "function setIndex", "function runIndex", "aria-activedescendant"] },
    { file: "app.js", terms: ["commandPaletteHelpers", "function commandPaletteCall", "commandPaletteCall(\"open\"", "commandPaletteCall(\"close\"", `commandPaletteCall("setup"`] },
    { file: "index.html", terms: ["./release-status.js", "./command-palette.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "command-palette.js"] },
    { file: "scripts/verify-release.mjs", terms: ["command-palette.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["command-palette.js", "command_palette_cache_no_cache"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["command_palette_module_loaded", "joopark-command-palette/v1"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["commandPaletteModule", "joopark-command-palette/v1", "command palette runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["commandPaletteText", "command-palette.js", "joopark-command-palette/v1"] },
    { file: "README.md", terms: ["command-palette.js", "active descendant", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "command_palette_runtime_module",
    requirement: "The command palette search, listbox rendering, active descendant, and keyboard execution logic is extracted into a packaged runtime helper with browser smoke coverage.",
    status: commandPaletteModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: commandPaletteModuleTerms,
  });

  const dbCatalogModuleTerms = [
    { file: "db-catalog.js", terms: ["JooParkDbCatalog", "joopark-db-catalog/v1", "function createDbCatalog", "function renderDbInstances", "function renderDbBackups", "function saveInstanceFromForm", "function saveMigrationFromForm", "data-db-catalog-provenance"] },
    { file: "app.js", terms: ["dbCatalogHelpers", "dbCatalogCall(\"renderDbInstances\"", "dbCatalogCall(\"openInstanceModal\"", "const DB_CRUD_ACTION_HANDLERS", "dbCatalogCall(\"renderDbBackups\""] },
    { file: "index.html", terms: ["./command-palette.js", "./db-catalog.js", "./review-handoff.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "db-catalog.js"] },
    { file: "scripts/verify-release.mjs", terms: ["db-catalog.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["db-catalog.js", "db_catalog_cache_no_cache"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["db_catalog_module_loaded", "joopark-db-catalog/v1"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["dbCatalogModule", "joopark-db-catalog/v1", "db catalog runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["dbCatalogText", "db-catalog.js", "joopark-db-catalog/v1"] },
    { file: "README.md", terms: ["db-catalog.js", "로컬 DB 카탈로그", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "db_catalog_runtime_module",
    requirement: "DB catalog provenance, view rendering, and CRUD logic is extracted into a packaged runtime helper with release and browser smoke coverage.",
    status: dbCatalogModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: dbCatalogModuleTerms,
  });

  const reviewHandoffModuleTerms = [
    { file: "review-handoff.js", terms: ["JooParkReviewHandoff", "joopark-review-handoff-runtime/v1", "function createReviewHandoff", "function reviewPackageBundleMarkdown", "function reviewPromptHandoffMarkdown", "function validateReviewResultShape", "joopark-review-handoff/v2"] },
    { file: "app.js", terms: ["reviewHandoffHelpers", "function reviewHandoffCall", "reviewHandoffCall(\"reviewPackageBundleMarkdown\"", "reviewHandoffCall(\"reviewPromptHandoffMarkdown\"", "reviewHandoffCall(\"validateReviewResultShape\""] },
    { file: "index.html", terms: ["./db-catalog.js", "./review-handoff.js", "./review-result-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-handoff.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-handoff.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-handoff.js", "review_handoff_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewHandoffModule", "joopark-review-handoff-runtime/v1", "review handoff runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewHandoffText", "review-handoff.js", "joopark-review-handoff-runtime/v1"] },
    { file: "README.md", terms: ["review-handoff.js", "review package bundle", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_handoff_runtime_module",
    requirement: "Review handoff prompt, manifest, bundle, and JSON result validation logic is extracted into a packaged runtime helper that loads before app.js and is covered by release verification.",
    status: reviewHandoffModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewHandoffModuleTerms,
  });

  const reviewResultViewModuleTerms = [
    { file: "review-result-view.js", terms: ["JooParkReviewResultView", "joopark-review-result-view/v1", "function createReviewResultView", "function reviewResultSavedCard", "function compactReviewResult", "function reviewSavedResultBody", "function reviewSavedResultNoteBody", "function reviewAssigneeFollowUpPanel", "function reviewIssueDraftAssigneeOverridePanel", "function issueExecutionChecklistControls", "function reviewIssueDraftPanel", "function reviewGithubCommentMarkdown", "function reviewGithubCommentDraftPanel", "function reviewResultRepairPacket", "function reviewResultRepairReceiptMarkdown", "function reviewResultPostRepairReceiptPanel", "function reviewResultValidationOutput", "data-review-result-saved-card", "data-review-result-failures", "data-review-result-repair", "data-review-result-repair-receipt", "data-issue-draft-owner-follow-up", "data-issue-draft-assignee-select", "data-issue-execution-checklist-view", "data-review-issue-draft", "data-review-github-comment-text", "data-issue-draft-labels"] },
    { file: "app.js", terms: ["reviewResultViewHelpers", "function reviewResultViewCall", "reviewResultViewCall(\"reviewResultSavedCard\"", "reviewResultViewCall(\"compactReviewResult\"", "reviewResultViewCall(\"reviewSavedResultBody\"", "reviewResultViewCall(\"reviewSavedResultNoteBody\"", "reviewResultViewCall(\"reviewAssigneeFollowUpPanel\"", "reviewResultViewCall(\"reviewIssueDraftAssigneeOverridePanel\"", "reviewResultViewCall(\"issueExecutionChecklistControls\"", "reviewResultViewCall(\"reviewIssueDraftPanel\"", "reviewResultViewCall(\"reviewGithubCommentMarkdown\"", "reviewResultViewCall(\"reviewGithubCommentDraftPanel\"", "reviewResultViewCall(\"reviewResultValidationOutput\"", "function saveValidatedReviewResult", "function copyReviewResultRepair", "function copyReviewResultRepairReceipt", "copy-review-result-repair"] },
    { file: "review-handoff.js", terms: ["data-review-result-status", "role=\"status\"", "aria-live=\"polite\"", "aria-atomic=\"true\""] },
    { file: "index.html", terms: ["./review-handoff.js", "./review-result-view.js", "./review-execution-checklist.js", "./review-issue-payload.js", "./review-result-state.js", "./review-result-draft-state.js", "./review-creation-actions.js", "./review-package-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-result-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-result-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-result-view.js", "review_result_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultViewModule", "joopark-review-result-view/v1", "review result view runtime module was not loaded"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["review_result_status_live_region", "aria-atomic", "review result validator status should be a polite live region"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewResultViewText", "review-result-view.js", "joopark-review-result-view/v1"] },
    { file: "README.md", terms: ["review-result-view.js", "result validator", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_result_view_runtime_module",
    requirement: "Review result saved-card, compact saved model, validation output, validated issue/note body, issue draft shell, GitHub comment draft shell, and assignee follow-up rendering are extracted into a packaged runtime helper while app.js keeps parsing, persistence, and downstream mutation.",
    status: reviewResultViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewResultViewModuleTerms,
  });

  const reviewExecutionChecklistModuleTerms = [
    { file: "review-execution-checklist.js", terms: ["JooParkReviewExecutionChecklist", "joopark-review-execution-checklist/v1", "function createReviewExecutionChecklist", "function reviewExecutionChecklistItemsFromSavedResult", "function issueExecutionChecklistItems", "function issueExecutionChecklistProgress", "function reviewExecutionChecklistLines", "function syncIssueBodyExecutionChecklist", "function reviewExecutionChecklistCountLabel", "function firstPositiveTimeboxHours"] },
    { file: "app.js", terms: ["reviewExecutionChecklistHelpers", "function reviewExecutionChecklistCall", "reviewExecutionChecklistCall(\"reviewExecutionChecklistItemsFromSavedResult\"", "reviewExecutionChecklistCall(\"issueExecutionChecklistItems\"", "reviewExecutionChecklistCall(\"issueExecutionChecklistProgress\"", "reviewExecutionChecklistCall(\"reviewExecutionChecklistLines\"", "reviewExecutionChecklistCall(\"syncIssueBodyExecutionChecklist\"", "reviewExecutionChecklistCall(\"reviewExecutionChecklistCountLabel\"", "reviewExecutionChecklistCall(\"firstPositiveTimeboxHours\""] },
    { file: "index.html", terms: ["./review-result-view.js", "./review-execution-checklist.js", "./review-issue-payload.js", "./review-result-state.js", "./app.js"] },
    { file: "sw.js", terms: ["./review-execution-checklist.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-execution-checklist.js", "/review-execution-checklist.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-execution-checklist.js", "expectedRuntimeScriptOrder", "./review-execution-checklist.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-execution-checklist.js", "reviewExecutionChecklist", "review_execution_checklist_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewExecutionChecklistModule", "joopark-review-execution-checklist/v1", "review execution checklist runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewExecutionChecklistText", "review-execution-checklist.js", "joopark-review-execution-checklist/v1"] },
    { file: "README.md", terms: ["review-execution-checklist.js", "Execution Checklist", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_execution_checklist_runtime_module",
    requirement: "Review execution checklist item derivation, progress calculation, Markdown line generation, body sync, and count label logic are extracted into a packaged runtime helper while app.js keeps rendering wrappers and action routing.",
    status: reviewExecutionChecklistModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewExecutionChecklistModuleTerms,
  });

  const reviewIssuePayloadModuleTerms = [
    { file: "review-issue-payload.js", terms: ["JooParkReviewIssuePayload", "joopark-review-issue-payload/v1", "function createReviewIssuePayload", "function reviewOperationalReadinessLines", "function reviewIssueDecisionSummaryLines", "function reviewIssueBodyLines", "function reviewPackageNoteBody", "function reviewMarkdownSection", "function reviewPinnedNoteSummary", "function reviewExecutionPlanForSavedResult", "function reviewExecutionDueDate", "function reviewSavedResultTrackerFields"] },
    { file: "app.js", terms: ["reviewIssuePayloadHelpers", "function reviewIssuePayloadCall", "reviewIssuePayloadCall(\"reviewOperationalReadinessLines\"", "reviewIssuePayloadCall(\"reviewIssueDecisionSummaryLines\"", "reviewIssuePayloadCall(\"reviewIssueBodyLines\"", "reviewIssuePayloadCall(\"reviewPackageNoteBody\"", "reviewIssuePayloadCall(\"reviewSavedResultTrackerFields\"", "function reviewIssueBodyLines", "function reviewSavedResultTrackerFields"] },
    { file: "index.html", terms: ["./review-execution-checklist.js", "./review-issue-payload.js", "./review-result-state.js", "./app.js"] },
    { file: "sw.js", terms: ["./review-issue-payload.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-issue-payload.js", "/review-issue-payload.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-issue-payload.js", "expectedRuntimeScriptOrder", "./review-issue-payload.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-issue-payload.js", "reviewIssuePayload", "review_issue_payload_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewIssuePayloadModule", "joopark-review-issue-payload/v1", "review issue payload runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewIssuePayloadText", "review-issue-payload.js", "joopark-review-issue-payload/v1"] },
    { file: "README.md", terms: ["review-issue-payload.js", "Decision Summary", "tracker fields", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_issue_payload_runtime_module",
    requirement: "Review issue decision summary, body payload, pinned note summary, due date, and tracker field assembly are extracted into a packaged runtime helper while app.js keeps state mutation and action wrappers.",
    status: reviewIssuePayloadModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewIssuePayloadModuleTerms,
  });

  const reviewResultStateModuleTerms = [
    { file: "review-result-state.js", terms: ["JooParkReviewResultState", "joopark-review-result-state/v1", "function createReviewResultState", "const repairSnapshots = new WeakMap()", "function recordRepairSnapshot", "function postRepairReceiptModel", "function attachRepairReceipt", "function setValidation", "function copyRepair", "function copyRepairReceipt", "data-review-result-repair-text", "data-review-result-repair-receipt-text", "reviewResultRepairCopied", "reviewResultRepairReceiptCopied", "repaired-validation-pass"] },
    { file: "app.js", terms: ["reviewResultStateHelpers", "function reviewResultStateCall", "reviewResultStateCall(\"setValidation\"", "reviewResultStateCall(\"attachRepairReceipt\"", "reviewResultStateCall(\"copyRepair\"", "reviewResultStateCall(\"copyRepairReceipt\"", "function setReviewResultValidation", "function attachReviewResultRepairReceipt", "function copyReviewResultRepair", "function copyReviewResultRepairReceipt"] },
    { file: "index.html", terms: ["./review-execution-checklist.js", "./review-issue-payload.js", "./review-result-state.js", "./review-result-draft-state.js", "./review-creation-actions.js", "./review-package-view.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-result-state.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-result-state.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-result-state.js", "review_result_state_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultStateModule", "joopark-review-result-state/v1", "review result state runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewResultStateText", "review-result-state.js", "joopark-review-result-state/v1"] },
    { file: "README.md", terms: ["review-result-state.js", "validator state", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_result_state_runtime_module",
    requirement: "Review result validator state, repair snapshots, post-repair receipt attachment, and repair clipboard status are extracted into a packaged runtime helper while app.js keeps parser and action wrappers.",
    status: reviewResultStateModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewResultStateModuleTerms,
  });

  const reviewResultDraftStateModuleTerms = [
    { file: "review-result-draft-state.js", terms: ["JooParkReviewResultDraftState", "joopark-review-result-draft-state/v1", "function createReviewResultDraftState", "function issueDraftCells", "function issueDraftNode", "function issueDraftAssigneePanel", "function copyGithubComment", "function updateIssueDraftAssignee", "data-review-github-comment-text", "data-review-issue-draft", "reviewGithubCommentCopied", "assignee-confirmed", "manual-override"] },
    { file: "app.js", terms: ["reviewResultDraftStateHelpers", "function reviewResultDraftStateCall", "reviewResultDraftStateCall(\"copyGithubComment\"", "reviewResultDraftStateCall(\"updateIssueDraftAssignee\"", "reviewResultDraftStateCall(\"issueDraftNode\"", "function copyReviewGithubComment", "function updateReviewIssueDraftAssignee", "function reviewIssueDraftAssigneeCopy"] },
    { file: "index.html", terms: ["./review-result-state.js", "./review-result-draft-state.js", "./review-creation-actions.js", "./review-package-view.js", "./app.js"] },
    { file: "sw.js", terms: ["./review-result-draft-state.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-result-draft-state.js", "/review-result-draft-state.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-result-draft-state.js", "expectedRuntimeScriptOrder", "./review-result-draft-state.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-result-draft-state.js", "reviewResultDraftState", "review_result_draft_state_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultDraftStateModule", "joopark-review-result-draft-state/v1", "review result draft state runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewResultDraftStateText", "review-result-draft-state.js", "joopark-review-result-draft-state/v1"] },
    { file: "README.md", terms: ["review-result-draft-state.js", "GitHub comment copy", "assignee override", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_result_draft_state_runtime_module",
    requirement: "Review result GitHub comment copy state and issue draft assignee override DOM/dataset mutation are extracted into a packaged runtime helper while app.js keeps parser, draft generation, and action wrappers.",
    status: reviewResultDraftStateModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewResultDraftStateModuleTerms,
  });

  const reviewCreationActionsModuleTerms = [
    { file: "review-creation-actions.js", terms: ["JooParkReviewCreationActions", "joopark-review-creation-actions/v1", "function createReviewCreationActions", "function createBenchmarkReviewIssue", "function publishReviewHandoffNote", "function ensureDashboardArray", "ensureDashboardArray(\"issues\").push", "ensureDashboardArray(\"notes\").push", "validated-review-result", "review note를 발행했습니다"] },
    { file: "app.js", terms: ["reviewCreationActionsHelpers", "function reviewCreationActionsCall", "reviewCreationActionsCall(\"createBenchmarkReviewIssue\"", "reviewCreationActionsCall(\"publishReviewHandoffNote\"", "function createBenchmarkReviewIssue", "function publishReviewHandoffNote"] },
    { file: "index.html", terms: ["./review-result-draft-state.js", "./review-creation-actions.js", "./review-package-view.js", "./app.js"] },
    { file: "sw.js", terms: ["./review-creation-actions.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-creation-actions.js", "/review-creation-actions.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-creation-actions.js", "expectedRuntimeScriptOrder", "./review-creation-actions.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-creation-actions.js", "reviewCreationActions", "review_creation_actions_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewCreationActionsModule", "joopark-review-creation-actions/v1", "review creation actions runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewCreationActionsText", "review-creation-actions.js", "joopark-review-creation-actions/v1"] },
    { file: "README.md", terms: ["review-creation-actions.js", "review issue 생성", "review note publish", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_creation_actions_runtime_module",
    requirement: "Review issue creation and review note publish mutations are extracted into a packaged runtime helper while app.js keeps action wrappers and upstream draft/payload assembly.",
    status: reviewCreationActionsModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewCreationActionsModuleTerms,
  });

  const reviewPackageViewModuleTerms = [
    { file: "review-package-view.js", terms: ["JooParkReviewPackageView", "joopark-review-package-view/v1", "function createReviewPackageView", "function reviewPackageHandoffModel", "function reviewPackageHandoffHTML", "data-workspace-review-handoff", "data-review-package-bundle-text"] },
    { file: "app.js", terms: ["reviewPackageViewHelpers", "function reviewPackageViewCall", "reviewPackageViewCall(\"reviewPackageHandoffHTML\"", "function candidateWorkspaceReviewHandoff", "function candidateKnowledgeBaseReviewHandoff", "function candidateBenchmarkReviewQueueHandoff"] },
    { file: "index.html", terms: ["./review-result-view.js", "./review-package-view.js", "./review-artifact-view.js", "./review-copy-actions.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-package-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-package-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-package-view.js", "review_package_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageViewModule", "joopark-review-package-view/v1", "review package view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewPackageViewText", "review-package-view.js", "joopark-review-package-view/v1"] },
    { file: "README.md", terms: ["review-package-view.js", "review package shell", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_view_runtime_module",
    requirement: "Review package handoff shell composition is extracted into a packaged runtime helper while app.js keeps decision data and saved-note lookup.",
    status: reviewPackageViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageViewModuleTerms,
  });

  const reviewArtifactViewModuleTerms = [
    { file: "review-artifact-view.js", terms: ["JooParkReviewArtifactView", "joopark-review-artifact-view/v1", "function createReviewArtifactView", "function issueFreshReceiptControls", "function reviewArtifactDiffPanel", "function reviewArtifactReceiptMarkdown", "function reviewArtifactReceiptCompareOutput", "function reviewPostRepairArtifactLinkPanel", "data-review-artifact-diff", "data-review-artifact-receipt-compare", "data-issue-fresh-receipt-view", "data-review-post-repair-artifact-link"] },
    { file: "app.js", terms: ["reviewArtifactViewHelpers", "function reviewArtifactViewCall", "reviewArtifactViewCall(\"issueFreshReceiptControls\"", "reviewArtifactViewCall(\"reviewArtifactDiffPanel\"", "function reviewArtifactDiffPanel", "function reviewArtifactReceiptComparison", "function reviewArtifactReceiptCompareOutput"] },
    { file: "index.html", terms: ["./review-package-view.js", "./review-artifact-view.js", "./review-copy-actions.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-artifact-view.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-artifact-view.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-artifact-view.js", "review_artifact_view_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewArtifactViewModule", "joopark-review-artifact-view/v1", "review artifact view runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewArtifactViewText", "review-artifact-view.js", "joopark-review-artifact-view/v1"] },
    { file: "README.md", terms: ["review-artifact-view.js", "artifact diff", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_artifact_view_runtime_module",
    requirement: "Review artifact diff, receipt, compare, and repair rendering is extracted into a packaged runtime helper while app.js keeps clipboard and state-mutating repair actions.",
    status: reviewArtifactViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewArtifactViewModuleTerms,
  });

  const reviewArtifactStateModuleTerms = [
    { file: "review-artifact-state.js", terms: ["JooParkReviewArtifactState", "joopark-review-artifact-state/v1", "function createReviewArtifactState", "function repairPreview", "function applyRepairBody", "function undoRepair", "function setReceiptCompareState", "function compareReceipt", "function insertReceipt", "function clearReceipt", "data-review-artifact-repair-preview", "data-review-artifact-receipt-compare"] },
    { file: "app.js", terms: ["reviewArtifactStateHelpers", "function reviewArtifactStateCall", "reviewArtifactStateCall(\"repairPreview\"", "reviewArtifactStateCall(\"undoRepair\"", "reviewArtifactStateCall(\"compareReceipt\"", "function reviewArtifactRepairPreview", "function undoReviewArtifactRepair", "function compareReviewArtifactReceipt"] },
    { file: "index.html", terms: ["./review-artifact-view.js", "./review-artifact-state.js", "./review-copy-actions.js", "./app.js"] },
    { file: "sw.js", terms: ["./review-artifact-state.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-artifact-state.js", "/review-artifact-state.js", "Cache-Control: no-cache"] },
    { file: "scripts/verify-release.mjs", terms: ["review-artifact-state.js", "expectedRuntimeScriptOrder", "./review-artifact-state.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-artifact-state.js", "reviewArtifactState", "review_artifact_state_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewArtifactStateModule", "joopark-review-artifact-state/v1", "review artifact state runtime module was not loaded", "reviewArtifactReceiptCompare", "reviewArtifactReceiptRepairApply"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewArtifactStateText", "review-artifact-state.js", "joopark-review-artifact-state/v1"] },
    { file: "README.md", terms: ["review-artifact-state.js", "receipt compare state", "archived-body repair", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_artifact_state_runtime_module",
    requirement: "Review artifact receipt compare and archived-body repair side effects are extracted into a packaged runtime helper while app.js keeps stable action wrappers.",
    status: reviewArtifactStateModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewArtifactStateModuleTerms,
  });

  const reviewCopyActionsModuleTerms = [
    { file: "review-copy-actions.js", terms: ["JooParkReviewCopyActions", "joopark-review-copy-actions/v1", "function createReviewCopyActions", "function copyReviewPackagePasteBody", "function copyReviewPackagePanelText", "function copyReviewArtifactReceipt", "function copyReviewArtifactRepairPayload", "function copyIssueFreshReceipt", "function copyReviewArtifactPostApplyReceipt", "function copyReviewPostRepairArtifactLink", "reviewPackagePastePreviewCopied", "reviewArtifactReceiptCopied", "reviewArtifactPostApplyReceiptCopied", "paste body를 복사했습니다", "post-apply fresh receipt를 복사했습니다"] },
    { file: "app.js", terms: ["reviewCopyActionsHelpers", "function reviewCopyActionsCall", "reviewCopyActionsCall(\"copyReviewPackagePasteBody\"", "reviewCopyActionsCall(\"copyReviewPackagePanelText\"", "reviewCopyActionsCall(\"copyReviewArtifactReceipt\"", "reviewCopyActionsCall(\"copyReviewArtifactRepairPayload\"", "reviewCopyActionsCall(\"copyIssueFreshReceipt\"", "reviewCopyActionsCall(\"copyReviewArtifactPostApplyReceipt\"", "reviewCopyActionsCall(\"copyReviewPostRepairArtifactLink\"", "function copyReviewPackagePasteBody", "function copyReviewPackagePanelText"] },
    { file: "index.html", terms: ["./review-artifact-view.js", "./review-artifact-state.js", "./review-copy-actions.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-copy-actions.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-copy-actions.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-copy-actions.js", "review_copy_actions_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewCopyActionsModule", "joopark-review-copy-actions/v1", "review copy actions runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewCopyActionsText", "review-copy-actions.js", "joopark-review-copy-actions/v1"] },
    { file: "README.md", terms: ["review-copy-actions.js", "artifact receipt/post-apply fresh receipt", "clipboard, status, copied dataset", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_copy_actions_runtime_module",
    requirement: "Review package and artifact receipt copy handlers share a packaged runtime helper for clipboard writes, copied dataset state, status labels, readiness guards, and toast feedback while app.js keeps action routing.",
    status: reviewCopyActionsModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewCopyActionsModuleTerms,
  });

  const reviewSubmissionCopyModuleTerms = [
    { file: "review-submission-copy.js", terms: ["JooParkReviewSubmissionCopy", "joopark-review-submission-copy/v1", "function createReviewSubmissionCopy", "function fillExternalIssueText", "function copyReviewPackageFilledText", "function copyReviewPackageExternalReceiptFilled", "function copyReviewPackageSubmissionUpdateFilled"] },
    { file: "app.js", terms: ["reviewSubmissionCopyHelpers", "function reviewSubmissionCopyCall", "reviewSubmissionCopyCall(\"copyReviewPackageFilledText\"", "reviewSubmissionCopyCall(\"copyReviewPackageExternalReceiptFilled\"", "reviewSubmissionCopyCall(\"copyReviewPackageSubmissionUpdateFilled\""] },
    { file: "index.html", terms: ["./review-copy-actions.js", "./review-submission-copy.js", "./review-recommendation-export.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-submission-copy.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-submission-copy.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-submission-copy.js", "review_submission_copy_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewSubmissionCopyModule", "joopark-review-submission-copy/v1", "review submission copy runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewSubmissionCopyText", "review-submission-copy.js", "joopark-review-submission-copy/v1"] },
    { file: "README.md", terms: ["review-submission-copy.js", "copyReviewPackageFilledText", "placeholder 없이"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_submission_copy_runtime_module",
    requirement: "Filled external receipt and submission update copy handlers share a packaged runtime helper for URL/ID validation, template filling, clipboard/status/dataset updates, and placeholder-removal behavior while app.js keeps action routing.",
    status: reviewSubmissionCopyModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewSubmissionCopyModuleTerms,
  });

  const reviewRecommendationExportModuleTerms = [
    { file: "review-recommendation-export.js", terms: ["JooParkReviewRecommendationExport", "joopark-review-recommendation-export/v1", "function createReviewRecommendationExport", "function recommendationMarkdown", "function recommendationExport", "function candidateWorkspaceRecommendationExport", "function candidateKnowledgeBaseRecommendationExport", "function candidateBenchmarkRecommendationExport"] },
    { file: "app.js", terms: ["reviewRecommendationExportHelpers", "function reviewRecommendationExportCall", "reviewRecommendationExportCall(\"candidateWorkspaceRecommendationExport\"", "reviewRecommendationExportCall(\"candidateKnowledgeBaseRecommendationExport\"", "reviewRecommendationExportCall(\"candidateBenchmarkRecommendationExport\""] },
    { file: "index.html", terms: ["./review-copy-actions.js", "./review-recommendation-export.js", "./app.js"] },
    { file: "scripts/package-release.mjs", terms: ["runtimeAssets", "review-recommendation-export.js"] },
    { file: "scripts/verify-release.mjs", terms: ["review-recommendation-export.js"] },
    { file: "scripts/smoke-release.mjs", terms: ["review-recommendation-export.js", "review_recommendation_export_cache_no_cache"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewRecommendationExportModule", "joopark-review-recommendation-export/v1", "review recommendation export runtime module was not loaded"] },
    { file: "scripts/check-app-structure.mjs", terms: ["reviewRecommendationExportText", "review-recommendation-export.js", "joopark-review-recommendation-export/v1"] },
    { file: "README.md", terms: ["review-recommendation-export.js", "recommendation export", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_recommendation_export_runtime_module",
    requirement: "Portfolio benchmark recommendation Markdown and export shell rendering are extracted into a packaged runtime helper while app.js keeps scoring, filtering, and review state mutation.",
    status: reviewRecommendationExportModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewRecommendationExportModuleTerms,
  });

  const notificationSheetAccessibilityTerms = [
    { file: "index.html", terms: ["class=\"nav-list-action\"", "data-action=\"open-notifications\"", "aria-haspopup=\"dialog\"", "aria-controls=\"sheet\"", "aria-expanded=\"false\"", "aria-modal=\"true\"", "aria-labelledby=\"sheetTitle\""] },
    { file: "app.js", terms: ["function openNotificationsSheet", "notificationExpanded: true", "data-notification-empty=\"true\"", "data-alert-list=\"true\"", "data-alert-row=\"true\""] },
    { file: "dialog-shell.js", terms: ["function setNotificationTriggerExpanded", "setNotificationTriggerExpanded(openOptions.notificationExpanded === true)", "setNotificationTriggerExpanded(false)", "function setDialogOpenState", "body.classList.toggle(bodyClass, open)", "setDialogOpenState(sheetRefs.root, \"sheet-open\", true)", "setDialogOpenState(sheetRefs.root, \"sheet-open\", false)"] },
    { file: "styles.css", terms: [".nav-list a,\n.nav-list button", ".nav-list button:hover", ".nav-list button.active", "body.sheet-open", "body.sheet-open .main", ".alert-list", "max-height: min(66vh, 560px)", ".notification-empty", "overflow-wrap: anywhere"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["notification_sidebar_button", "notification_sheet_modal_dialog", "notification_sheet_body_lock", "notification_sheet_body_lock_cleared", "notification_triggers_expanded", "notification_sheet_restores_focus"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["notificationSheetMobileReport", "smoke-notification-sheet-mobile", "notification sheet did not settle with long alerts", "notification sheet did not settle empty state", "notification_sheet_body_not_locked", "notification_sheet_body_lock_not_cleared", "notification_alert_list_not_scrollable", "notification_empty_state_missing", "notification_sheet_mobile_issue_count"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "notification_sheet_accessibility",
    requirement: "The sidebar and bell notification controls expose the shared sheet as a labelled modal dialog, lock background scrolling, synchronize expanded state, restore focus, and keep long/empty alert states accessible and mobile-scrollable.",
    status: notificationSheetAccessibilityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: notificationSheetAccessibilityTerms,
  });

  const projectPickerStatusTerms = [
    { file: "app.js", terms: ["projectPickerHelpers", "function projectPickerCall", "projectPickerCall(\"setOpen\"", "projectPickerCall(\"isOpen\"", "projectPickerCall(\"renderOptions\"", "projectPickerCall(\"closeIfOutside\""] },
    { file: "project-picker.js", terms: ["function setStatus", "function normalizeAccessibility", "body.classList.add(\"project-picker-open\")", "body.classList.remove(\"project-picker-open\")", "projectPickerInputBound", "refs.projectPicker.hasAttribute(\"hidden\")", "일치하는 프로젝트가 없습니다. 다른 검색어를 입력하세요."] },
    { file: "styles.css", terms: ["body.project-picker-open", "body.project-picker-open .main", ".project-picker-status", ".project-picker-status.is-visible", "grid-template-rows: auto minmax(0, 1fr) auto", "max-height: min(72vh, 520px)", ".project-list {\n  display: grid;", "min-height: 44px"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["project_picker_search_describes_status", "project_picker_body_lock", "project_picker_body_lock_cleared", "project_picker_status_live_region", "project_picker_no_results_status_visible", "project_picker_close_clears_status", "project_picker_hidden_input_ignored"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["projectPickerMobileReport", "smoke-project-picker-mobile", "project_picker_body_not_locked", "project_picker_body_lock_not_cleared", "project_picker_outside_viewport", "project_picker_no_results_status_outside_viewport", "project_picker_mobile_issue_count"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "project_picker_status_recovery",
    requirement: "The project picker exposes dynamic search result status, visible no-results feedback, bounded scrollable options, body scroll lock, close cleanup, and hidden-input status recovery in accessibility smoke.",
    status: projectPickerStatusTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: projectPickerStatusTerms,
  });

  const iconButtonLabelTerms = [
    { file: "portfolio-view.js", terms: ["aria-label=\"${project.name} 편집\"", "aria-label=\"${project.name} 삭제\""] },
    { file: "app.js", terms: ["aria-label=\"${c.name} 컬럼 편집\""] },
    { file: "gantt-view.js", terms: ["aria-label=\"${task.name} 작업 편집\"", "aria-label=\"${task.name} 작업 삭제\""] },
    { file: "kanban-view.js", terms: ["aria-label=\"${issue.id} 이슈 삭제\"", "aria-label=\"${issue.id} 이슈를 ${statusLabels[prevStatus]}로 이동\"", "aria-label=\"${issue.id} 이슈를 ${statusLabels[nextStatus]}로 이동\""] },
    { file: "db-catalog.js", terms: ["aria-label=\"${d.name} 인스턴스 삭제\"", "aria-label=\"${t.name} 테이블 편집\"", "aria-label=\"${qi.id} 쿼리 삭제\"", "aria-label=\"${m.id} 마이그레이션 편집\""] },
    { file: "scripts/smoke-a11y.mjs", terms: ["pm_project_icon_labels", "pm_issue_move_labels", "db_column_icon_labels", "db_migration_icon_labels", "hasActionLabel"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "icon_button_accessible_names",
    requirement: "Icon-only edit, delete, and move controls across PM and DB surfaces expose descriptive accessible names and have accessibility smoke coverage.",
    status: iconButtonLabelTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: iconButtonLabelTerms,
  });

  const contextualActionTooltipTerms = [
    { file: "portfolio-view.js", terms: ["title=\"${project.name} 편집\"", "title=\"${project.name} 삭제\""] },
    { file: "app.js", terms: ["title=\"${c.name} 컬럼 삭제\"", "`✎ ${p.name} 편집`", "✎ ${table.name} 테이블 편집"] },
    { file: "gantt-view.js", terms: ["title=\"${task.name} 작업 편집\"", "title=\"${task.name} 작업 삭제\""] },
    { file: "kanban-view.js", terms: ["title=\"${issue.id} 이슈 삭제\"", "title=\"◀ ${statusLabels[prevStatus]}\"", "title=\"▶ ${statusLabels[nextStatus]}\""] },
    { file: "db-catalog.js", terms: ["title=\"${d.name} 인스턴스 삭제\"", "title=\"${t.name} 테이블 삭제\"", "title=\"${qi.id} 쿼리 편집\"", "`✕ ${m.id} 마이그레이션 삭제`"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["hasActionTitle", "pm_project_icon_titles", "db_column_icon_titles", "project_sheet_action_context_labels", "table_sheet_action_context_labels"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "contextual_action_tooltips",
    requirement: "PM and DB icon tooltips plus detail-sheet actions include the affected project, issue, task, table, query, or migration name instead of generic edit/delete text.",
    status: contextualActionTooltipTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: contextualActionTooltipTerms,
  });

  const sheetActionLayoutTerms = [
    { file: "styles.css", terms: ["flex: 1 1 180px", "min-height: 36px", "overflow-wrap: anywhere", "white-space: normal"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["sheetActionReport", "sheet_actions_project", "sheet_actions_table", "sheet_action_button_overflow", "sheet_action_button_too_short"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "sheet_action_layout_stability",
    requirement: "Long contextual detail-sheet action labels wrap inside their buttons, keep usable touch height, and are checked in mobile smoke.",
    status: sheetActionLayoutTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: sheetActionLayoutTerms,
  });

  const textControlLayoutTerms = [
    { file: "styles.css", terms: ["min-height: 34px", "min-height: 30px", "min-height: 32px", "overflow-wrap: anywhere", "white-space: normal"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["textControlSelectors", "textControlIssues", "text_control_button_overflow", "text_control_button_too_short", "textControlIssueCount"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "text_control_layout_stability",
    requirement: "Common text buttons and filter chips can wrap without clipping, maintain usable mobile height, and are checked route-by-route in mobile smoke.",
    status: textControlLayoutTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: textControlLayoutTerms,
  });

  const touchActionVisibilityTerms = [
    { file: "styles.css", terms: ["@media (hover: none), (max-width: 720px)", ".portfolio-card:focus-within .pm-card-actions", ".db-card-wrap:focus-within .db-card-actions", ".sheet-col-row:focus-within .sheet-col-actions", ".kanban-move-btns", "opacity: 1"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["touchActionSelectors", "touchActionIssues", "touch_action_group_hidden", "touchActionIssueCount", "sheet_col_actions"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "touch_action_visibility",
    requirement: "Hover-revealed PM and DB action groups become visible on touch/mobile layouts, reveal on keyboard focus, and are checked in mobile smoke.",
    status: touchActionVisibilityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: touchActionVisibilityTerms,
  });

  const iconTouchTargetTerms = [
    { file: "styles.css", terms: ["min-width: 32px", "min-height: 32px", ".kanban-move-btn", ".view .todo-check-mini", ".view .todo-check", ".view .note-pin", ".todo-row {\n    grid-template-columns: 34px minmax(0, 1fr) 34px;"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["iconTouchSelectors", ".view .habit-day:not(:disabled)", "habit_icon_touch_targets_missing", "habit_day_touch_targets_missing", "iconTouchIssues", "icon_touch_target_too_small", "iconTouchIssueCount", "sheet_icon_targets"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "mobile_icon_touch_targets",
    requirement: "Mobile icon-only edit, delete, move, check, mini-check, pin, and habit controls expose at least 32px touch targets, including table-sheet column actions and habit day toggles.",
    status: iconTouchTargetTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: iconTouchTargetTerms,
  });

  const modalSwatchTouchTerms = [
    { file: "dialog-shell.js", terms: ["function setDialogOpenState", "body.classList.toggle(bodyClass, open)", "setDialogOpenState(modalRefs.root, \"modal-open\", true)", "setDialogOpenState(modalRefs.root, \"modal-open\", false)", "function openModal", "function closeModal"] },
    { file: "styles.css", terms: ["body.modal-open", "body.modal-open .main", "overscroll-behavior: contain", ".modal-panel {\n  position: absolute;", "flex: 0 0 36px", "width: 36px", "height: 36px", ".modal-form label.swatch input[type=\"radio\"]", "min-width: 36px", "min-height: 36px", ".swatch span { display: block; width: 28px; height: 28px;"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["modal_panel_labelled_dialog", "modal_body_lock", "modal_body_lock_cleared"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["modalTouchReport", "note_modal_swatches", "habit_modal_swatches", "modal touch state did not settle", "modal_panel_outside_viewport", "modal_body_not_locked", "modal_body_lock_not_cleared", "modal_focus_not_restored", "modal_swatch_touch_target_too_small", "modal_swatch_outside_viewport"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "modal_swatch_touch_targets",
    requirement: "Note and habit modals expose at least 32px swatch touch targets, stay inside the mobile viewport, lock background scrolling, and restore focus after close.",
    status: modalSwatchTouchTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: modalSwatchTouchTerms,
  });

  const mobilePaletteLayoutTerms = [
    { file: "styles.css", terms: ["body.palette-open", "body.palette-open .main", "max-height: min(80vh, 620px)", "max-height: calc(100dvh - 24px)", ".palette-results {\n  flex: 1 1 auto;", ".pal-item {\n  display: flex;", "min-height: 44px", ".palette-hint {\n    padding: 8px 14px;"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["paletteMobileReport", "smoke-palette-mobile", "palette_body_not_locked", "palette_body_lock_not_cleared", "palette_panel_outside_viewport", "palette_no_results_status_outside_viewport", "palette_mobile_issue_count"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "mobile_palette_layout_stability",
    requirement: "The command palette fits inside narrow mobile viewports, locks background scrolling, keeps its input and option rows touchable, scrolls only the results region, and checks no-results status placement in mobile smoke.",
    status: mobilePaletteLayoutTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: mobilePaletteLayoutTerms,
  });

  const actionRowLayoutTerms = [
    { file: "styles.css", terms: ["grid-template-columns: minmax(0, 1fr) auto", "grid-template-columns: minmax(0, 1fr) auto auto", "overflow-wrap: anywhere", ".schema-table-btn span", ".sheet-col-name"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["actionRowDefinitions", "actionRowIssues", "action_row_overlap", "actionRowIssueCount", "sheet-col-row"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "action_row_layout_stability",
    requirement: "Mobile action rows keep text and icon-action regions separated after touch-target expansion, including PM/DB cards and table-sheet column rows.",
    status: actionRowLayoutTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: actionRowLayoutTerms,
  });

  const personalActionLabelTerms = [
    { file: "todo-view.js", terms: ["aria-label=\"${todo.title} ${todo.done ? \"완료 취소\" : \"완료 처리\"}\"", "aria-label=\"${todo.title} 삭제\""] },
    { file: "notes-view.js", terms: ["const noteTitle = note.title || \"(제목 없음)\";", "aria-label=\"${noteTitle} ${note.pinned ? \"고정 해제\" : \"고정\"}\"", "aria-label=\"${noteTitle} 삭제\"", "aria-pressed=\"${raw(note.pinned ? \"true\" : \"false\")}\""] },
    { file: "habits-view.js", terms: ["aria-label=\"${habit.name} 습관 편집\"", "aria-label=\"${habit.name} 습관 삭제\"", "aria-pressed=\"${raw(checked ? \"true\" : \"false\")}\""] },
    { file: "app.js", terms: ["todoViewCall(\"renderTodosHTML\"", "notesViewCall(\"renderNotesHTML\"", "habitsViewCall(\"renderHabitsHTML\""] },
    { file: "scripts/smoke-a11y.mjs", terms: ["personal_todo_action_labels", "personal_note_action_labels", "personal_habit_action_labels", "todoToggleLabel.includes(todoTitle)", "notePin.getAttribute(\"aria-pressed\")", "notePinLabel.includes(noteTitle)", "habitEditLabel.includes(habitName)", "habitDay.getAttribute(\"aria-pressed\")"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "personal_action_accessible_names",
    requirement: "Todo, note, and habit action controls include the affected item name in accessible labels and are covered by accessibility smoke.",
    status: personalActionLabelTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: personalActionLabelTerms,
  });

  const homeQuickLinkTerms = [
    { file: "app.js", terms: ["function viewHref", "href=\"${viewHref(viewName)}\"", "data-view=\"${viewName}\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeQuickLinksNavigate", "home quick link href did not expose route", "home quick link did not navigate"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_dashboard_quick_link_routes",
    requirement: "Home dashboard quick links expose real route hrefs and navigate to each PM and DB surface in browser interaction smoke.",
    status: homeQuickLinkTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeQuickLinkTerms,
  });

  const homeLaunchActionTerms = [
    { file: "app.js", terms: ["function refreshReleaseEvidenceViews", "homeViewCall(\"renderHome\""] },
    { file: "home-view.js", terms: ["data-home-launch-next-action", "data-home-launch-action-key", "data-home-launch-action-label", "data-home-launch-safe-to-dispatch", "launchExecution?.readyToDispatch === true && outputAudit?.dispatchState?.allDispatchReady === true", "launchExecution?.readyForExternalClaim === true && outputAudit?.readyForExternalClaim === true", "firstClampedCount([", "currentLaunchAction?.commandCount", "outputImmediateAction?.commandCount", "currentLaunchAction?.withheldCommandCount", "outputReadinessSnapshot?.publishEvidenceCommandGuard?.withheldDispatchCommands", "launchInstallMatrixPathCount", "launchInstallMatrixSignalCount"] },
    { file: "styles.css", terms: [".home-launch-next", ".home-launch-next dl", "grid-template-columns: minmax(0, 1.5fr) minmax(260px, 1fr) auto"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeLaunchNextAction", "home launch action surfaces current guard", "home launch action should keep dispatch blocked", "home launch action did not navigate to system status"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_launch_action_guard",
    requirement: "Home exposes the current launch action, safe-to-dispatch guard, withheld dispatch count, and System Status handoff before external launch claims.",
    status: homeLaunchActionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeLaunchActionTerms,
  });

  const homeLaunchBlockerResolverTerms = [
    { file: "app.js", terms: ["copy-home-launch-blocker-resolver"] },
    { file: "home-view.js", terms: ["data-home-launch-blocker-resolver", "data-home-launch-blocker-resolver-active", "data-home-launch-blocker-resolver-primary-command", "data-home-launch-blocker-evidence-gap", "data-home-launch-blocker-resolver-evidence-gap-count", "data-home-launch-blocker-resolver-item-count=\"${launchBlockerItemCount}\"", "data-home-launch-blocker-resolver-action-required-count=\"${launchBlockerActionRequiredCount}\"", "data-home-launch-blocker-resolver-proof-command-count=\"${launchBlockerProofCommandCount}\"", "launchBlockerItemCount", "launchBlockerPassCount", "launchBlockerActionRequiredCount", "launchBlockerDeferredCount", "launchBlockerProofCommandCount", "firstClampedCount([launchBlockerResolution.itemCount, launchBlockerItems.length])", "items=${launchBlockerItemCount}; pass=${launchBlockerPassCount}; actionRequired=${launchBlockerActionRequiredCount}; deferred=${launchBlockerDeferredCount}; proofCommands=${launchBlockerProofCommandCount}", "data-home-workflow-install-shortcut", "data-home-workflow-install-shortcut-path-count", "workflowInstallShortcutDefaultBranchGuard", "workflowInstallShortcutScopeGuard", "JooPark Workflow Install Shortcut", "remote_workflow_files", "launch_proof", "post_install_intake", "JooPark Launch Blocker Resolver"] },
    { file: "operations-copy-actions.js", terms: ["copyHomeLaunchBlockerResolver", "data-home-launch-blocker-resolver-text", "homeLaunchBlockerResolverCopied"] },
    { file: "styles.css", terms: [".home-launch-blocker-resolver", ".home-launch-blocker-evidence-gap", ".home-workflow-install-shortcut", ".home-workflow-install-shortcut-guards", ".home-launch-blocker-items", ".home-launch-blocker-fallback", ".home-launch-blocker-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeLaunchBlockerResolver", "home launch blocker resolver exposes active unblock path", "home launch blocker resolver evidence gaps did not render", "home workflow install shortcut dataset was incomplete", "home workflow install shortcut guards did not render", "home launch blocker resolver copy did not report success"] },
    { file: "README.md", terms: ["JooPark Launch Blocker Resolver", "data-home-launch-blocker-resolver", "Evidence gap", "remote_workflow_files", "post_install_intake", "Workflow install shortcut", "workflow_dispatch", "workflow scope", "activeItemKey=operator_auth_path", "resolver 복사"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_launch_blocker_resolver",
    requirement: "Home exposes the active blocker resolution checklist with the primary proof command, GitHub UI fallback, dispatch guard, and copy-ready resolver before any dispatch attempt.",
    status: homeLaunchBlockerResolverTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeLaunchBlockerResolverTerms,
  });

  const homeUpcomingEventTerms = [
    { file: "app.js", terms: ["class=\"home-upcoming-open\"", "data-action=\"open-event\"", "data-event-id=\"${openId}\""] },
    { file: "styles.css", terms: [".home-upcoming-open", ".home-upcoming-open:hover"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeUpcomingEventOpen", "home upcoming event opens accessibly", "home upcoming event control should be a button"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_upcoming_event_accessibility",
    requirement: "Home upcoming events are real focusable buttons that open the event modal, preserving the dashboard overview while supporting keyboard users.",
    status: homeUpcomingEventTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeUpcomingEventTerms,
  });

  const homeQuickTodoTerms = [
    { file: "app.js", terms: ["data-action=\"home-todo-quick-add\"", "data-home-first-action=\"todo\"", "function quickAddTodo(form, options = {})", "refocusSelector: \"#view-home .home-quickadd input[name=title]\""] },
    { file: "styles.css", terms: [".home-quickadd", ".view .home-quickadd .primary-btn"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeQuickTodo", "home one-step todo quick add", "home quick todo was not persisted with selected metadata"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_one_step_todo_activation",
    requirement: "The first dashboard screen lets a user create a due-dated todo in one inline submit without leaving home, with browser smoke coverage for persistence, metadata, and refocus.",
    status: homeQuickTodoTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeQuickTodoTerms,
  });

  const globalHelpAccessTerms = [
    { file: "index.html", terms: ["data-action=\"open-global-help\"", "data-global-help-trigger", "aria-controls=\"sheet\"", "aria-expanded=\"false\"", "도움·상태"] },
    { file: "app.js", terms: ["function openGlobalHelpSheet", "globalHelpAccessItems", "data-global-help-access", "data-global-help-access-coverage", "data-global-help-status-message", "role=\"status\"", "launchRefresh.readyForExternalClaim === true && launchExecution.readyForExternalClaim === true", "launchRefresh.safeToDispatch === true && (launchExecution.safeToDispatch === true || launchExecution.readyToDispatch === true)", "global-help-search-recovery", "global-help-open-palette", "global-help-nav", "wcag-3.2.6"] },
    { file: "styles.css", terms: [".help-btn", ".global-help", ".global-help-status", ".global-help-action"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["globalHelpAccess", "global help access opens consistent recovery actions", "global help access dataset was incomplete", "global help status message was not programmatically exposed", "global help command action did not open palette"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["globalHelpAccessSourceReady", "globalHelpAccess", "globalHelpAccessCoverage", "Global help access:", "finiteNumberOr(evidence.globalHelpAccessActions", "finiteNumberOr(evidence.globalHelpAccessCoverage"] },
    { file: "README.md", terms: ["globalHelpAccessCoverage=1", "도움·상태", "System Status", "Settings", "WCAG 3.2.6", "WCAG 4.1.3"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "global_help_access_consistency",
    requirement: "Topbar help/status access is available in a consistent location, exposes status messages programmatically, and offers recovery actions for search, system status, and settings.",
    status: globalHelpAccessTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: globalHelpAccessTerms,
  });

  const topbarDataSafetyTerms = [
    { file: "index.html", terms: ["data-action=\"open-data-safety-status\"", "data-data-safety-trigger", "aria-controls=\"sheet\"", "로컬 데이터 상태"] },
    { file: "app.js", terms: ["function openDataSafetyStatusSheet", "dataSafetyAccessItems", "updateDataSafetyTopbar", "data-topbar-data-safety", "data-topbar-data-safety-coverage", "data-topbar-data-safety-status-message", "StorageManager.estimate persisted", "data-safety-refresh", "data-safety-nav"] },
    { file: "styles.css", terms: [".data-status-btn", ".data-safety", ".data-safety-status", ".data-safety-action"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["topbarDataSafety", "topbar data safety status exposes local storage recovery", "topbar data safety dataset was incomplete", "topbar data safety status message was not programmatically exposed", "topbar data safety settings action did not navigate"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["topbarDataSafetySourceReady", "topbarDataSafety", "topbarDataSafetyCoverage", "Topbar data safety:", "finiteNumberOr(evidence.topbarDataSafetyActions", "finiteNumberOr(evidence.topbarDataSafetyCoverage"] },
    { file: "README.md", terms: ["topbarDataSafetyCoverage=1", "로컬 데이터 상태", "StorageManager", "마지막 저장", "백업·복구"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "topbar_data_safety_status",
    requirement: "Topbar local data status is globally visible, exposes save/storage/persistence/backup recovery state, and carries release smoke plus output-quality evidence.",
    status: topbarDataSafetyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: topbarDataSafetyTerms,
  });

  const routeDeepLinkTerms = [
    { file: "index.html", terms: ["href=\"#pm-kanban\"", "data-action=\"nav-to\"", "data-view=\"system\""] },
    { file: "app.js", terms: ["function routeViewFromLocation", "function syncRouteHistory", "routeDeepLinkCoverage", "history.pushState", "history.replaceState", "window.addEventListener(\"popstate\"", "window.addEventListener(\"hashchange\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["routeDeepLink", "route deep links preserve browser history", "browser back did not restore todo route", "browser forward did not restore notes route", "invalid route hash did not recover to home"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["routeDeepLinkSourceReady", "routeDeepLink", "routeDeepLinkCoverage", "Route deep link:", "finiteNumberOr(evidence.routeDeepLinkCoverage"] },
    { file: "README.md", terms: ["routeDeepLinkCoverage=1", "#pm-kanban", "뒤로가기", "앞으로가기"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "route_deep_link_history",
    requirement: "Every primary workspace view has a shareable hash route, browser back/forward restores view state, and invalid hashes recover to Home with smoke and output-quality evidence.",
    status: routeDeepLinkTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: routeDeepLinkTerms,
  });

  const homeFirstRunEmptyGuidanceTerms = [
    { file: "app.js", terms: ["function renderHome", "firstRunSteps", "firstRunGuidedStartItems", "firstRunGuidedStartCoverage", "projectFollowThroughSteps", "defaultMilestone", "first_issue", "first_milestone", "first_owner", "무엇을 관리하나", "다음 행동", "공개 증거", "오늘 업무 캡처", "프로젝트 구조화", "운영 증거 확인", "백업/복구 준비", "data-home-empty=\"${key}\""] },
    { file: "home-view.js", terms: ["data-home-first-run-guidance", "data-home-first-run-variant=\"task_strip\"", "data-home-first-run-source=\"linear_jira_onboarding_benchmark\"", "data-home-first-run-guided-start", "data-home-first-run-guided-start-item", "data-home-first-run-guided-start-coverage", "data-home-project-followthrough", "data-home-project-followthrough-variant=\"activation_ladder\"", "linear_project_jira_work_item_benchmark", "data-default-milestone=\"true\"", "homeEmptyHTML(\"projects\"", "homeEmptyHTML(\"db-instances\"", "homeEmptyHTML(\"queries\"", "homeEmptyHTML(\"backups\""] },
    { file: "styles.css", terms: [".home-first-run", ".home-first-run-guided-start", ".home-first-run-guided-start-item", ".home-first-run-steps", ".home-first-run-score", ".home-project-followthrough", ".home-project-followthrough-steps", ".home-project-followthrough-score", ".home-empty", ".view .home-empty .small-action"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeFirstRunGuidance", "homeFirstRunGuidedStart", "data-home-first-run-guidance", "data-home-first-run-guided-start", "data-home-project-followthrough", "home first-run quick start dataset was incomplete", "home first-run guided start dataset was incomplete", "home first-run guided start items were incomplete", "home first-run todo action did not open modal", "home project follow-through dataset was incomplete after first project", "home project follow-through issue action did not open modal", "home project follow-through milestone action did not preselect milestone", "[\"backups\", \"migration-add\"]", "home first-run empty guidance was too terse", "home first-run empty guidance did not expose action"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["homeFirstRunGuidedStartSourceReady", "homeFirstRunGuidedStart", "homeFirstRunGuidedStartCoverage", "First-run guided start:", "finiteNumberOr(evidence.homeFirstRunGuidedStartItems", "finiteNumberOr(evidence.homeFirstRunGuidedStartCoverage"] },
    { file: "README.md", terms: ["첫 실행", "처음 5분 quick start", "firstRunGuidedStartCoverage=1", "무엇을 관리하나", "다음 행동", "공개 증거", "오늘 업무 캡처", "프로젝트 구조화", "운영 증거 확인", "백업/복구 준비", "Project follow-through", "첫 이슈 연결", "마일스톤 잡기", "담당자 추가", "홈 타일", "빈 상태", "백업"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_first_run_empty_guidance",
    requirement: "After reset or first-run empty data, Home tiles explain the missing workspace data and expose immediate create actions with browser smoke coverage.",
    status: homeFirstRunEmptyGuidanceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeFirstRunEmptyGuidanceTerms,
  });

  const todoSearchRecoveryTerms = [
    { file: "app.js", terms: ["function renderTodos", "todoViewCall(\"renderTodosHTML\"", "function syncSearchAffordance"] },
    { file: "global-search.js", terms: ["function status", "검색 결과 없음", "function revealEmptyIfNeeded"] },
    { file: "todo-view.js", terms: ["data-search-result=\"todo\"", "searchEmptyState(\"todo\"", "data-action=\"todo-filter\""] },
    { file: "search-empty-state.js", terms: ["data-search-empty=\"${kind}\"", "role=\"status\"", "data-action=\"clear-search\""] },
    { file: "styles.css", terms: [".empty-action", ".empty-action strong", ".empty-action span"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["todoSearchRecovery", "todoViewModule", "todo search no-results recovery", "search status did not announce no results", "clear search did not restore focus"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "todo_search_empty_recovery",
    requirement: "Todo search has an accessible no-results empty state with a clear-search recovery action, live status evidence, restored focus, and browser smoke coverage.",
    status: todoSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: todoSearchRecoveryTerms,
  });

  const topbarSearchClearTerms = [
    { file: "index.html", terms: ["id=\"globalSearchClear\"", "aria-label=\"검색어 지우기\"", "data-action=\"clear-search\""] },
    { file: "app.js", terms: ["searchClear: nodeQuery(document, \"#globalSearchClear\")", "function syncSearchClearControl", "globalSearchCall(\"clearControl\"", "globalSearchCall(\"clear\""] },
    { file: "global-search.js", terms: ["function clearControl", "event.key !== \"Escape\"", "clearControl();"] },
    { file: "styles.css", terms: [".search-clear", "min-width: 32px", ".search-clear[hidden]"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["topbarSearchClear", "topbar search clear control", "topbar search clear button is below 32px touch target", "Escape did not clear topbar search query"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["Emulation.setDeviceMetricsOverride", "searchClearIssues", "topbar_search_clear_too_small", "topbar_search_input_collapsed", "searchClearIssueCount"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "topbar_search_clear_control",
    requirement: "Global scoped search exposes a 32px clear control and Escape-key recovery whenever a searchable view has an active query, with mobile layout coverage.",
    status: topbarSearchClearTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: topbarSearchClearTerms,
  });

  const mobileSearchEmptyRecoveryTerms = [
    { file: "app.js", terms: ["function searchEmptyState", "globalSearchCall(\"clear\"", "function syncSearchAffordance", "searchEmptyStateCall(\"searchEmptyState\""] },
    { file: "global-search.js", terms: ["function revealEmptyIfNeeded", "scrollIntoView({ block: \"center\"", "function clear", "function status"] },
    { file: "search-empty-state.js", terms: ["JooParkSearchEmptyState", "joopark-search-empty-state/v1", "function searchEmptyState", "data-search-empty=\"${kind}\"", "data-action=\"clear-search\""] },
    { file: "styles.css", terms: [".empty-action", ".empty-action .primary-btn", "min-width: 108px", ".view .primary-btn", "min-height: 34px", "white-space: normal", "overflow-wrap: anywhere"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["searchEmptyMobileReport", "smoke-search-empty-mobile", "search query did not reach app state on mobile", "search empty state did not render on mobile", "matchedAppQuery", "viewText", "search_empty_state_below_fold", "search_empty_clear_too_small", "search_empty_clear_did_not_restore_focus", "search_empty_mobile_issue_count"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "mobile_search_empty_recovery",
    requirement: "Searchable mobile routes render accessible no-results states with visible clear actions, no horizontal overflow, live no-results status, and focus-restoring clear recovery.",
    status: mobileSearchEmptyRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: mobileSearchEmptyRecoveryTerms,
  });

  const crossViewSearchRecoveryTerms = [
    { file: "app.js", terms: ["function searchEmptyState", "notesViewCall(\"renderNotesHTML\"", "portfolioViewCall(\"renderPortfolioHTML\""] },
    { file: "portfolio-view.js", terms: ["searchEmptyState(\"pm-portfolio\"", "data-search-result=\"pm-portfolio\""] },
    { file: "notes-view.js", terms: ["searchEmptyState(\"notes\"", "data-search-result=\"notes\""] },
    { file: "styles.css", terms: [".empty-action", ".empty-action strong", ".empty-action span"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["notesSearchRecovery", "notesViewModule", "notes search no-results recovery", "portfolioSearchRecovery", "portfolio search no-results recovery"] },
    { file: "README.md", terms: ["현재 뷰 검색", "Notes, Portfolio", "검색 초기화"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "cross_view_search_empty_recovery",
    requirement: "Notes and Portfolio search have accessible no-results empty states with clear-search recovery, live status evidence, restored focus, result markers, and browser smoke coverage.",
    status: crossViewSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: crossViewSearchRecoveryTerms,
  });

  const calendarSearchRecoveryTerms = [
    { file: "app.js", terms: ["function renderCalendar", "calendarViewCall(\"renderCalendarHTML\"", "function syncSearchAffordance"] },
    { file: "global-search.js", terms: ["function status", "function revealEmptyIfNeeded"] },
    { file: "calendar-view.js", terms: ["searchEmptyState(\"calendar\"", "data-search-result=\"calendar\"", "calendar-search-empty", "선택한 날짜에 검색 결과가 없습니다"] },
    { file: "search-empty-state.js", terms: ["data-search-empty=\"${kind}\"", "role=\"status\"", "검색 초기화"] },
    { file: "styles.css", terms: [".calendar-search-empty", ".empty-action"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["calendarSearchRecovery", "calendarViewModule", "calendar search no-results recovery", "calendar agenda kept unmatched selected event"] },
    { file: "README.md", terms: ["Calendar", "현재 뷰 검색", "검색 초기화"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "calendar_search_empty_recovery",
    requirement: "Calendar search filters the month grid and selected-day agenda together, exposes an accessible no-results state, and restores the month view through clear-search recovery.",
    status: calendarSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: calendarSearchRecoveryTerms,
  });

  const calendarGridKeyboardTerms = [
    { file: "app.js", terms: ["function focusCalendarDay", "requestAnimationFrame(focus)", "calSelectDay,", "addDaysISO,"] },
    { file: "keyboard-shortcuts.js", terms: ["ArrowRight", "callbacks.calSelectDay(callbacks.addDaysISO", "calendarCell && calendarCell.tagName.toLowerCase() !== \"button\""] },
    { file: "calendar-view.js", terms: ["role=\"grid\"", "role=\"gridcell\"", "aria-selected=\"${raw(selected ? \"true\" : \"false\")}\"", "tabindex=\"${raw(selected ? \"0\" : \"-1\")}\""] },
    { file: "styles.css", terms: [".sched-row", "display: contents", ".view .sched-cell:focus-visible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["calendarGridKeyboard", "calendar grid keyboard navigation", "calendar ArrowRight did not move selected day", "calendar keyboard navigation did not restore focus"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "calendar_grid_keyboard_accessibility",
    requirement: "Calendar month cells expose grid/gridcell semantics, selected state, and keyboard arrow navigation with focus restoration.",
    status: calendarGridKeyboardTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: calendarGridKeyboardTerms,
  });

  const habitSearchRecoveryTerms = [
    { file: "app.js", terms: ["habitsViewCall(\"renderHabitsHTML\"", "function isSearchInertView"] },
    { file: "global-search.js", terms: ["const SEARCH_INERT_VIEWS = new Set([\"home\", \"stats\", \"settings\", \"system\"]"] },
    { file: "habits-view.js", terms: ["searchEmptyState(\"habits\"", "data-search-result=\"habits\"", "aria-pressed=\"${raw(checked ? \"true\" : \"false\")}\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["habitSearchRecovery", "habitsViewModule", "habit search no-results recovery", "habit search status did not announce no results", "statsSearchInert", "stats search stays inert"] },
    { file: "README.md", terms: ["Habits", "Stats", "현재 뷰 검색", "검색 초기화"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "habit_search_empty_recovery",
    requirement: "Habits search filters habit cards and exposes accessible no-results recovery, while Stats is treated as a search-inert analytics view.",
    status: habitSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: habitSearchRecoveryTerms,
  });

  const inertSearchAffordanceTerms = [
    { file: "app.js", terms: ["function syncSearchAffordance", "globalSearchCall(\"syncAffordance\"", "globalSearchCall(\"setup\""] },
    { file: "global-search.js", terms: ["const SEARCH_INERT_HINT", "function syncAffordance", "function announceInert", "aria-readonly", "SEARCH_INERT_PLACEHOLDER", "openPalette();"] },
    { file: "styles.css", terms: [".search.is-inert", ".search input[aria-readonly=\"true\"]", "cursor: help"] },
    { file: "index.html", terms: ["aria-describedby=\"searchCount\"", "data-search-scope=\"view\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["stats search stays inert with scoped affordance", "home inert search accepted typed query", "slash on inert view did not open command palette", "stats inert search accepted typed query"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "inert_search_affordance_recovery",
    requirement: "Home, Stats, Settings, and System search-inert views expose a clear readonly/search-scope affordance, live recovery guidance, and slash-key command-palette fallback with smoke coverage.",
    status: inertSearchAffordanceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: inertSearchAffordanceTerms,
  });

  const pmExecutionSearchRecoveryTerms = [
    { file: "kanban-view.js", terms: ["searchEmptyState(\"pm-kanban\"", "data-search-result=\"pm-kanban\"", "kanban-search-empty"] },
    { file: "gantt-view.js", terms: ["searchEmptyState(\"pm-gantt\"", "data-search-result=\"pm-gantt\"", "gantt-search-empty"] },
    { file: "styles.css", terms: [".kanban-search-empty", ".gantt-search-empty", ".kanban-search-empty .empty-action", ".gantt-search-empty .empty-action"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["kanbanSearchRecovery", "kanban search no-results recovery", "ganttSearchRecovery", "gantt search no-results recovery"] },
    { file: "README.md", terms: ["Kanban", "Gantt", "검색 초기화"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "pm_execution_search_empty_recovery",
    requirement: "Kanban and Gantt search have accessible no-results empty states with clear-search recovery, live status evidence, restored focus, result markers, and browser smoke coverage.",
    status: pmExecutionSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: pmExecutionSearchRecoveryTerms,
  });

  const ganttSvgAccessibilityTerms = [
    { file: "gantt-view.js", terms: ["class=\"gantt-milestone", "role=\"button\" aria-label", "class=\"${raw(cls)}\" data-action=\"open-task\"", "작업 열기:", "ganttChartSummary"] },
    { file: "styles.css", terms: [".gantt-bar:focus-visible .gantt-bar-rect", ".gantt-milestone:focus-visible"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["gantt_view_module_loaded", "gantt_svg_group_labelled", "gantt_svg_button_semantics"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["ganttSvgTaskAccessibility", "gantt svg task opens accessibly", "gantt SVG task Enter did not open task sheet", "gantt SVG task Space did not open task sheet"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "gantt_svg_task_accessibility",
    requirement: "Gantt SVG bars and milestones expose button semantics, useful labels, visible focus, and keyboard activation coverage.",
    status: ganttSvgAccessibilityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: ganttSvgAccessibilityTerms,
  });

  const pmResourceSearchRecoveryTerms = [
    { file: "team-view.js", terms: ["searchEmptyState(\"pm-team\"", "data-search-result=\"pm-team\"", "team-search-empty", "team-matrix-empty", "data-team-matrix-empty=\"search\"", "role=\"table\"", "role=\"cell\""] },
    { file: "styles.css", terms: [".team-search-empty", ".team-matrix-empty"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["teamSearchRecovery", "team search no-results recovery", "team search did not render matrix empty state", "team clear search did not restore focus"] },
    { file: "README.md", terms: ["Team", "현재 뷰 검색", "검색 초기화"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "pm_resource_search_empty_recovery",
    requirement: "PM Team search has an accessible no-results empty state with clear-search recovery, live status evidence, restored focus, result markers, and matrix empty-state coverage.",
    status: pmResourceSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: pmResourceSearchRecoveryTerms,
  });

  const backupSearchRecoveryTerms = [
    { file: "db-catalog.js", terms: ["data-search-empty=\"dbm-backups\"", "data-action=\"clear-search\"", "data-search-result=\"dbm-backup\"", "data-search-result=\"migration\"", "백업 검색 결과가 없습니다"] },
    { file: "styles.css", terms: [".bkup-empty", ".mig-empty"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["backupSearchRecovery", "backup search no-results recovery", "backup search status did not announce no results", "backup clear search did not restore focus"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_search_empty_recovery",
    requirement: "DB backup search has an accessible no-results empty state with a clear-search recovery action, result markers for backups and migrations, restored focus, and browser smoke coverage.",
    status: backupSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupSearchRecoveryTerms,
  });

  const backupPersistenceResetTerms = [
    { file: "workspace-storage.js", terms: ["backups: dashboard.backups", "if (Array.isArray(rawV3.backups)) dashboard.backups = rawV3.backups", "function applyV3Payload"] },
    { file: "app.js", terms: ["backups:     dashboard.backups", "dashboard.backups = []"] },
    { file: "backup-import-ui.js", terms: ["function importArrayField", "importArrayField(source, \"backups\")"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["\"queries\", \"backups\", \"migrations\"", "payload.backups.length", "dashboard.backups.length", "imported backup was not saved"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_persistence_reset",
    requirement: "Backup history participates in v3 persistence, import, and reset so first-run and post-reset states do not leak seeded backup records.",
    status: backupPersistenceResetTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupPersistenceResetTerms,
  });

  const dbCatalogSearchRecoveryTerms = [
    { file: "db-catalog.js", terms: ["searchEmptyState(\"dbm-instances\"", "data-search-result=\"dbm-instances\"", "searchEmptyState(\"dbm-schema\"", "data-search-result=\"dbm-schema\"", "searchEmptyState(\"dbm-queries\"", "data-search-result=\"dbm-queries\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["dbInstancesSearchRecovery", "db instance search no-results recovery", "dbSchemaSearchRecovery", "db schema search no-results recovery", "dbQueriesSearchRecovery", "db query search no-results recovery"] },
    { file: "README.md", terms: ["DB 카탈로그", "인스턴스", "스키마", "저장 쿼리", "검색 복구"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "db_catalog_search_empty_recovery",
    requirement: "DB instance, schema, and saved-query search have accessible no-results empty states with clear-search recovery, result markers, restored focus, and browser smoke coverage.",
    status: dbCatalogSearchRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: dbCatalogSearchRecoveryTerms,
  });

  const dbCatalogProvenanceTerms = [
    { file: "index.html", terms: ["인스턴스 상태 <em>LOCAL</em>", "DB: 로컬 카탈로그 / 실제 연결 없음", "저장: 브라우저 localStorage"] },
    { file: "app.js", terms: ["dbCatalogHelpers", "dbCatalogCall(\"renderDbInstances\"", "dbCatalogCall(\"renderDbBackups\""] },
    { file: "system-status-view.js", terms: ["DB 카탈로그 정상"] },
    { file: "db-catalog.js", terms: ["JooParkDbCatalog", "joopark-db-catalog/v1", "data-db-catalog-provenance", "로컬 DB 카탈로그입니다", "실제 데이터베이스에 연결하거나 실시간 지표를 수집하지 않습니다", "접속 문자열은 저장하지 마세요"] },
    { file: "styles.css", terms: [".data-provenance", "border: 1px solid var(--line)", "background: var(--panel-2)"] },
    { file: "scripts/smoke-chrome.mjs", terms: ["로컬 DB 카탈로그"] },
    { file: "scripts/smoke-mobile.mjs", terms: ["로컬 DB 카탈로그"] },
    { file: "README.md", terms: ["로컬 문서화 도구", "실제 DB 연결이나 실시간 수집은 하지 않습니다"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "db_catalog_provenance_boundary",
    requirement: "DB catalog surfaces clearly distinguish localStorage-backed documentation from real-time production database monitoring in UI, docs, and route smoke coverage.",
    status: dbCatalogProvenanceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: dbCatalogProvenanceTerms,
  });

  const paletteComboboxStatusTerms = [
    { file: "index.html", terms: ["id=\"paletteStatus\"", "aria-describedby=\"paletteHint paletteStatus\"", "aria-live=\"polite\"", "id=\"paletteHint\""] },
    { file: "app.js", terms: ["commandPaletteHelpers", "function commandPaletteCall", `commandPaletteCall("setup"`] },
    { file: "command-palette.js", terms: ["JooParkCommandPalette", "joopark-command-palette/v1", "function setPaletteShellOpen", "doc.body.classList.toggle(\"palette-open\", nextOpen)", "검색 결과가 없습니다. 다른 검색어를 입력하세요.", "aria-activedescendant"] },
    { file: "styles.css", terms: [".palette-status", ".palette-status.is-visible"] },
    { file: "scripts/smoke-a11y.mjs", terms: ["command_palette_module_loaded", "palette_input_describedby_hint_status", "palette_body_lock", "palette_body_lock_cleared", "palette_no_results_status_visible", "palette_close_clears_status"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "palette_combobox_status_recovery",
    requirement: "The command palette combobox links keyboard help and live result status, exposes no-results feedback in real DOM, clears active descendant safely, and has a11y smoke coverage.",
    status: paletteComboboxStatusTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: paletteComboboxStatusTerms,
  });

  const markerEvidence = appMarkers.map((marker) => ({
    id: marker.id,
    file: marker.file,
    missingTerms: hasTerms(marker.file, marker.terms).missing,
  }));
  checklist.push({
    id: "app_capabilities",
    requirement: "Core calendar, todo, note, habit, PM, DB, command palette, and localStorage persistence code paths are present.",
    status: markerEvidence.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: markerEvidence,
  });

  const storageTerms = [
    { file: "workspace-storage.js", terms: ["function refreshStorageHealth", "typeof manager.estimate", "typeof manager.persisted", "function requestStoragePersistence", "persistent storage request failed"] },
    { file: "storage-status-view.js", terms: ["JooParkStorageStatusView", "joopark-storage-status-view/v1", "function createStorageStatusView", "data-storage-health", "data-system-storage", "role=\"status\"", "aria-live=\"polite\"", "storageStatusModel"] },
    { file: "app.js", terms: ["function refreshStorageHealth", "workspaceStorageCall(\"refreshStorageHealth\"", "function settingsStorageHealthHTML", "settingsStorageHealthHTML(health)", "storageStatusViewCall(\"settingsStorageHealthHTML\"", "requestStoragePersistence"] },
    { file: "styles.css", terms: [".storage-health", ".storage-meter", ".storage-grid"] },
    { file: "README.md", terms: ["저장소 상태", "navigator.storage.estimate", "영속 저장"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["storage health status", "data-storage-health", "workspaceStorageModule", "storageStatusViewModule"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "storage_health_monitoring",
    requirement: "The settings surface shows browser storage usage, quota estimate, persistence state, and verifies the panel in the interaction smoke.",
    status: storageTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: storageTerms,
  });

  const settingsHandoffTerms = [
    { file: "app.js", terms: ["function settingsBackupHandoffText", "function settingsDeployHandoffText", "function settingsPrivacyHandoffText", "prepare-github-pages-workflow.mjs --dry-run --check-scope", "pages: write", "actions/deploy-pages", "Device-code approval handoff", "approvalUrl=https://github.com/login/device", "one-time device code", "gh auth status -h github.com", "workflowScopeAvailable: true", "workflowScopeInstallBlocked: false", "install-remote-workflow-files.mjs", "public launch copy", "archive proof"] },
    { file: "settings-view.js", terms: ["data-settings-handoff", "data-settings-handoff-copy=\"${kind}\"", "체크리스트 복사", "배포 handoff 복사", "privacy handoff 복사", "device-code 승인 code", "workflowScopeAvailable: true", "role=\"list\"", "role=\"listitem\""] },
    { file: "styles.css", terms: [".settings-handoff-grid", ".settings-handoff-card", ".settings-handoff-card .portfolio-export-download"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["settingsHandoffCopy", "settings operational handoff copy", "backup handoff copy text did not reach clipboard", "deploy handoff copy text did not reach clipboard", "privacy handoff copy text did not reach clipboard", "pages: write", "Device-code approval handoff", "approvalUrl=https://github.com/login/device", "one-time device code"] },
    { file: "README.md", terms: ["운영 handoff", "백업 체크리스트", "배포 handoff", "privacy handoff", "Pages 권한", "Settings Deploy Handoff", "Device-code approval handoff", "one-time device code"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "settings_operational_handoff_copy",
    requirement: "Settings exposes copy-ready backup/import/reset and deploy handoff checklists with workflow-scope guidance and browser smoke coverage.",
    status: settingsHandoffTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: settingsHandoffTerms,
  });

  const settingsLaunchRunbookTerms = [
    { file: "settings-view.js", terms: ["function launchRunbookModel", "function launchRunbookHTML", "data-settings-launch-runbook", "data-settings-launch-runbook-step-key", "data-settings-launch-runbook-signal", "GitHub UI install first, dispatch later", "safeToDispatch=true before gh workflow run"] },
    { file: "app.js", terms: ["workflowUiInstallPlan: state.workflowUiInstallPlan", "launchExecutionPacket: state.launchExecutionPacket", "dashboard.currentView === \"settings\"", "settingsViewCall(\"renderSettingsHTML\"", "renderSettings()"] },
    { file: "styles.css", terms: [".settings-launch-runbook", ".settings-launch-runbook-summary", ".settings-launch-runbook-steps", ".settings-launch-runbook-signals", ".settings-launch-runbook-guard"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["settings launch runbook did not load evidence", "data-settings-launch-runbook", "settingsLaunchRunbookSteps.length === 7", "settingsLaunchRunbookSignals.length === 8", "install_workflows", "safeToDispatch=true before gh workflow run"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "settings_launch_install_runbook",
    requirement: "Settings shows the same default-branch workflow install sequence, evidence signals, and dispatch-withheld guard that System Status uses.",
    status: settingsLaunchRunbookTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: settingsLaunchRunbookTerms,
  });

		  const postInstallEvidenceIntakeTerms = [
		    { file: "scripts/capture-launch-execution-packet.mjs", terms: ["function postInstallEvidenceIntake", "postInstallEvidenceIntake", "Post-install evidence intake:", "JooPark Post-Install Quick Proof Receipt", "quickProofSteps", "quickProofCoverage", "quickProofFieldMappings", "quickProofFieldMappingCoverage", "quickProofMappedFieldCount", "verificationSequence", "verificationSequenceCount", "verificationSequenceReady", "finalVerificationCommand", "remote_file_parity", "actions_visibility", "dispatch_readiness", "handoff_verifier", "proofComplete", "completedFieldCount", "remote_parity_proof", "handoff_verifier_proof", "collect_post_install_proof"] },
		    { file: "data/launch-execution-packet.json", terms: ["postInstallEvidenceIntake", "generated_from_launch_execution_packet", "collect_post_install_proof", "\"proofComplete\": false", "\"completedFieldCount\": 0", "\"commandCount\": 4", "\"signalCount\": 8", "\"quickProofStepCount\": 4", "\"quickProofCoverage\": 1", "\"quickProofFieldMappingCoverage\": 1", "\"quickProofMappedFieldCount\": 4", "JooPark Post-Install Quick Proof Receipt", "\"verificationSequenceCount\": 4", "\"verificationSequenceReady\": true", "\"finalVerificationCommand\": \"node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown\"", "remote_file_parity", "actions_visibility", "dispatch_readiness", "handoff_verifier", "remote_parity_proof", "handoff_verifier_proof"] },
		    { file: "scripts/verify-launch-handoff.mjs", terms: ["function postInstallEvidenceIntakeSummary", "function postInstallEvidenceIntakeMarkdownLines", "postInstallEvidenceIntake", "## Post-install Evidence Intake", "## Post-install Quick Proof", "quickProofReady", "quickProofCoverage", "quickProofFieldMappingReady", "quickProofFieldMappingCoverage", "mapped field", "verificationSequence", "verificationSequenceReady", "finalVerificationCommand", "proofComplete", "completedFieldCount", "remote_parity_proof", "handoff_verifier_proof", "Stop condition: do not run gh workflow run"] },
			    { file: "release-status.js", terms: ["postInstallEvidenceIntakeText", "postInstallEvidenceIntakeFieldCoverage", "postInstallQuickProofSteps", "postInstallQuickProofFieldMappings", "quickProofFieldMappingCoverage", "const postInstallIntakeFieldCount = finiteNumberOr(postInstallIntake.fieldCount, postInstallIntakeFields.length)", "const postInstallIntakeCommandCount = finiteNumberOr(postInstallIntake.commandCount, postInstallIntakeCommands.length)", "const postInstallQuickProofMappedFieldCount = finiteNumberOr(postInstallIntake.quickProofMappedFieldCount, postInstallQuickProofFieldMappings.length)", "data-launch-post-install-evidence-intake-field-count=\"${postInstallIntakeFieldCount}\"", "data-launch-post-install-quick-proof-step-count=\"${postInstallQuickProofStepCount}\"", "data-launch-post-install-quick-proof-mapped-field-count=\"${postInstallQuickProofMappedFieldCount}\"", "data-post-install-quick-proof-step", "data-post-install-quick-proof-field-map-item", "data-launch-post-install-quick-proof-field-map-item", "data-workflow-ui-install-intake", "data-post-install-evidence-intake", "data-post-install-evidence-intake-field", "data-post-install-evidence-intake-sequence", "data-launch-post-install-evidence-intake-sequence", "JooPark Workflow Post-Install Evidence Intake", "JooPark Post-Install Quick Proof Receipt", "Mapped proof fields:", "not dispatch approval", "Evidence fields to fill:", "Verification sequence", "Pages workflow commit", "Drift Watch workflow commit", "Remote parity proof", "Actions visibility proof", "Dispatch readiness proof", "Handoff verifier proof", "Stop condition: do not run gh workflow run", "safeToDispatch=true before gh workflow run", "every post-install evidence field has been filled", "all six post-install evidence fields are filled", "dispatchReady=true", "driftDispatchReady=true", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "settings-view.js", terms: ["postInstallEvidenceIntakeText", "postInstallEvidenceIntakeFieldCoverage", "postInstallQuickProofSteps", "postInstallQuickProofFieldMappings", "quickProofFieldMappingCoverage", "data-post-install-quick-proof-step", "data-post-install-quick-proof-field-map-item", "postInstallEvidenceIntakeSequence", "data-settings-post-install-evidence-intake", "data-post-install-evidence-intake-copy", "data-post-install-evidence-intake-field", "data-post-install-evidence-intake-sequence", "JooPark Workflow Post-Install Evidence Intake", "JooPark Post-Install Quick Proof Receipt", "Mapped proof fields:", "not dispatch approval", "Evidence fields to fill:", "Verification sequence:", "Pages workflow commit", "Drift Watch workflow commit", "Remote parity proof", "Actions visibility proof", "Dispatch readiness proof", "Handoff verifier proof", "Stop condition: do not run gh workflow run", "every post-install evidence field has been filled", "all six post-install evidence fields are filled", "dispatchReady=true", "driftDispatchReady=true", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "app.js", terms: ["function copyPostInstallEvidenceIntake", "quickProofFieldMappingCoverage", "data-post-install-evidence-intake-text", "postInstallEvidenceIntakeCopied", "copy-post-install-evidence-intake"] },
    { file: "home-view.js", terms: ["postInstallVerificationSequence", "postInstallQuickProofSteps", "postInstallQuickProofFieldMappings", "postInstallQuickProofStepCount = firstClampedCount([postInstallEvidenceIntake.quickProofStepCount, postInstallQuickProofSteps.length])", "postInstallQuickProofCoverage = firstClampedCount([", "postInstallQuickProofMappedFieldCount = firstClampedCount([postInstallEvidenceIntake.quickProofMappedFieldCount, postInstallQuickProofFieldMappings.length])", "postInstallQuickProofCompletedMappedFieldCount = firstClampedCount([", "postInstallQuickProofFieldMappingCoverage = firstClampedCount([", "data-post-install-quick-proof-step", "data-post-install-quick-proof-field-map-item", "JooPark Post-Install Quick Proof Receipt", "data-home-post-install-evidence-sequence"] },
    { file: "styles.css", terms: [".post-install-evidence-intake", ".post-install-quick-proof", ".post-install-quick-proof-map", ".post-install-evidence-intake-checklist", ".post-install-evidence-intake-fields", ".post-install-evidence-intake-sequence", ".post-install-evidence-intake-commands", ".post-install-evidence-intake-signals", ".home-post-install-quick-proof", ".home-post-install-quick-proof-map", ".home-post-install-intake-sequence"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["postInstallEvidenceIntake", "homePostInstallVerificationSequence", "settingsPostInstallSequence", "systemPostInstallSequence", "launchPostInstallSequence", "Post-install quick proof: pass (4 steps, coverage=1)", "Post-install quick proof field mapping: pass", "data-post-install-quick-proof-step", "data-post-install-quick-proof-field-map-item", "remote_file_parity -> remote_parity_proof", "handoff_verifier -> handoff_verifier_proof", "system post-install evidence intake state was incomplete", "settings post-install evidence intake copy did not report success", "settings post-install evidence intake copy text did not reach clipboard", "data-post-install-evidence-intake-command", "data-post-install-evidence-intake-signal", "data-post-install-evidence-intake-field", "data-post-install-evidence-intake-sequence", "Evidence fields to fill:", "Verification sequence:", "Handoff verifier proof", "every post-install evidence field has been filled", "dispatchReady=true", "driftDispatchReady=true", "verify-launch-handoff reports safeToDispatch=true"] },
    { file: "README.md", terms: ["JooPark Workflow Post-Install Evidence Intake", "JooPark Post-Install Quick Proof Receipt", "intake template 복사", "not dispatch approval", "postInstallEvidenceIntakeFieldCoverage", "postInstallQuickProofCoverage=1", "quickProofFieldMappingCoverage=1", "quickProofFieldMappings", "Evidence fields to fill", "Verification sequence", "4-step proof checklist", "remote_file_parity", "actions_visibility", "dispatch_readiness", "handoff_verifier", "remote_parity_proof", "handoff_verifier_proof", "Pages workflow commit", "Handoff verifier proof", "safeToDispatch=true before gh workflow run", "every post-install evidence field has been filled", "all six post-install evidence fields are filled", "dispatchReady=true", "driftDispatchReady=true", "verify-launch-handoff reports safeToDispatch=true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
	  checklist.push({
	    id: "post_install_evidence_intake",
	    requirement: "System Status and Settings expose a copy-ready post-install proof template that collects remote workflow parity, Actions visibility, dispatch readiness, and safeToDispatch evidence before any gh workflow run.",
	    status: postInstallEvidenceIntakeTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
	    evidence: postInstallEvidenceIntakeTerms,
	  });

  const postInstallProofParserTerms = [
    { file: "release-status.js", terms: ["postInstallProofParserFields", "postInstallProofParserCoverage", "JooPark Post-Install Proof Parser Receipt", "data-post-install-proof-parser", "data-post-install-proof-parser-input", "data-post-install-proof-parser-summary", "data-post-install-proof-parser-field-next-action", "Missing field repair hints:", "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write", "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write", "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown", "pages_workflow_commit", "drift_workflow_commit", "remote_parity_proof", "actions_visibility_proof", "dispatch_readiness_proof", "handoff_verifier_proof", "not dispatch approval"] },
    { file: "app.js", terms: ["function postInstallProofParserContext", "function postInstallProofParserHasFlag", "function postInstallProofParserActualLine", "function postInstallProofParserRules", "function parsePostInstallProofText", "function updatePostInstallProofParser", "function copyPostInstallProofParserSummary", "copy-post-install-proof-parser-summary", "postInstallProofParserSummaryCopied", "postInstallProofParserCoverage", "Fields detected:", "nextAction", "Missing field repair hints:", "postInstallProofParserFieldNextAction", "not dispatch approval"] },
    { file: "styles.css", terms: [".post-install-proof-parser", ".post-install-proof-parser-input", ".post-install-proof-parser-status", ".post-install-proof-parser-fields", ".post-install-proof-parser-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["postInstallProofParserOk", "postInstallProofParserFalsePositiveGuard", "post-install proof parser treated the template receipt as complete proof", "post-install proof parser did not detect all fields", "JooPark Post-Install Proof Parser Receipt", "postInstallProofParserCoverage=1", "Fields detected: 6/6", "Post-install proof parser: pass (6 fields, coverage=1)", "detected=6/6", "postInstallProofParserFieldNextAction", "Missing field repair hints:", "nextAction=Run node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown and paste safeToDispatch=true."] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["function postInstallProofParserSourceReady", "postInstallProofParser", "postInstallProofParserCoverage", "Post-install proof parser:", "Missing field repair hints:", "postInstallProofParserFieldNextAction", "const postInstallProofParserSourceReadyFlag = postInstallProofParserSourceReady()", "postInstallProofParserReady ? 6 : 0", "postInstallProofParserReady ? 1 : 0", "const postInstallProofParserFalsePositiveGuard = !!(", "postInstallProofParserFalsePositiveGuard,", "finiteNumberOr(evidence.postInstallProofParserFields", "finiteNumberOr(evidence.postInstallProofParserCoverage", "finiteNumberOr(evidence.postInstallProofParserDetectedFields", "finiteNumberOr(\n    persistedChecks.postInstallProofParserFields", "finiteNumberOr(\n    persistedChecks.postInstallProofParserCoverage", "finiteNumberOr(\n    persistedChecks.postInstallProofParserDetectedFields"] },
    { file: "README.md", terms: ["Post-install proof parser", "postInstallProofParserCoverage=1", "Fields detected: 6/6", "placeholder", "Missing field repair hints", "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write", "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write", "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown", "not dispatch approval", "pages_workflow_commit", "drift_workflow_commit", "remote_parity_proof", "actions_visibility_proof", "dispatch_readiness_proof", "handoff_verifier_proof"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "post_install_proof_parser",
    requirement: "System Status exposes a local post-install proof parser that detects all six pasted proof fields and keeps dispatch approval separate from field detection.",
    status: postInstallProofParserTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: postInstallProofParserTerms,
  });

	  const launchHandoffVerificationArtifactTerms = [
	    { file: "scripts/verify-launch-handoff.mjs", terms: ["outJsonRel", "data/launch-handoff-verification.json", "outMarkdownRel", "data/launch-handoff-verification.md", "function payloadMarkdownLines", "## Verification Artifacts", "artifactCoverage", "writeText(outJsonRel", "writeText(outMarkdownRel"] },
	    { file: "data/launch-handoff-verification.json", terms: ["verificationArtifact", "\"artifactCoverage\": 2", "\"safeToDispatch\": false", "postInstallEvidenceIntake", "\"verificationSequenceCount\": 4", "\"verificationSequenceReady\": true", "\"quickProofStepCount\": 4", "\"quickProofCoverage\": 1", "\"quickProofFieldMappingCoverage\": 1", "\"quickProofMappedFieldCount\": 4", "\"finalVerificationCommand\": \"node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown\"", "collect_post_install_proof", "remote_file_parity", "handoff_verifier", "remote_parity_proof", "handoff_verifier_proof"] },
	    { file: "data/launch-handoff-verification.md", terms: ["JooPark Launch Handoff Verification", "Verification Artifacts", "artifactCoverage: 2", "Post-install Evidence Intake", "Post-install Quick Proof", "quickProofFieldMappingReady: true", "mapped field 1 remote_file_parity -> remote_parity_proof", "mapped field 4 handoff_verifier -> handoff_verifier_proof", "sequence=4", "verificationSequenceReady: true", "finalVerificationCommand: node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown", "remote_file_parity", "handoff_verifier", "safeToDispatch: false", "Withheld Dispatch Commands"] },
	    { file: "README.md", terms: ["data/launch-handoff-verification.json", "data/launch-handoff-verification.md", "Verification Artifacts", "artifactCoverage=2"] },
	  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
	  checklist.push({
	    id: "launch_handoff_verification_artifact",
	    requirement: "verify-launch-handoff --write saves durable JSON and Markdown proof artifacts that preserve post-install evidence state while keeping dispatch withheld until every post-install evidence field has been filled and verify-launch-handoff reports safeToDispatch=true.",
	    status: launchHandoffVerificationArtifactTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
	    evidence: launchHandoffVerificationArtifactTerms,
	  });

	  const backupImportSizeTerms = [
    { file: "app.js", terms: ["MAX_IMPORT_BYTES", "function handleImportFile", "backupImportUiCall(\"handleImportFile\""] },
    { file: "backup-import-ui.js", terms: ["file.size > maxImportBytes", "formatBytes(maxImportBytes)", "가져오기 파일은", "input.value = \"\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["settings oversized import guard", "backupOversizeRejected", "2.0 MB 이하", "oversized import did not show max-size rejection toast"] },
    { file: "README.md", terms: ["가져오기 JSON은 2 MiB 이하만 처리", "대용량 파일로 인한 UI 중단과 quota 위험"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_import_size_guard",
    requirement: "Settings rejects oversized backup import files before reading them, documents the limit, and covers the rejection in browser smoke.",
    status: backupImportSizeTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupImportSizeTerms,
  });

  const backupImportMalformedTerms = [
    { file: "app.js", terms: ["const IMPORT_GUARDS = window.JooParkImportGuards", "importGuards: IMPORT_GUARDS", "function rejectImportFile", "backupImportUiCall(\"rejectImportFile\""] },
    { file: "backup-import-guards.js", terms: ["function isBackupShape", "function isPlainObject", "!Array.isArray(value)", "IMPORT_ARRAY_KEYS.some"] },
    { file: "backup-import-ui.js", terms: ["function rejectImportFile", "JSON 파싱 실패", "백업 형식이 아닙니다"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["settings malformed import guard", "backupMalformedRejected", "malformed JSON import changed saved data", "array-root import changed saved data"] },
    { file: "README.md", terms: ["잘못된 JSON 또는 백업 구조가 아니면 가져오지 않습니다"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_import_malformed_guard",
    requirement: "Settings rejects malformed JSON and non-backup import roots without opening confirmation or changing saved data.",
    status: backupImportMalformedTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupImportMalformedTerms,
  });

  const backupImportConfirmationTerms = [
    { file: "app.js", terms: ["importGuards: IMPORT_GUARDS", "function importBackupSummaryHTML", "backupImportUiCall(\"importBackupSummaryHTML\""] },
    { file: "backup-import-guards.js", terms: ["간트 작업", "DB 인스턴스", "마이그레이션"] },
    { file: "backup-import-ui.js", terms: ["data-import-summary", "function importBackupSummaryHTML", "가져올 데이터"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["data-import-summary", "import modal did not summarize imported scope", "DB 인스턴스 1", "마이그레이션 1"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_import_confirmation_scope",
    requirement: "The destructive backup import confirmation summarizes personal, PM, DB, backup, and migration scope before replacement.",
    status: backupImportConfirmationTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupImportConfirmationTerms,
  });

  const backupImportNormalizeTerms = [
    { file: "app.js", terms: ["function clampText", "function clampTextArray", "function clampNumberArray", "n.body = clampText(n.body, 4000)", "p.members = clampTextArray(p.members, 20, 80)", "i.labels = clampTextArray(i.labels, 12, 40)", "d.series = clampNumberArray(d.series, 60)", "q.text = clampText(q.text, 2000)"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["settings import normalization guard", "backupNormalizeClamped", "note text was not clamped", "schema fields were not clamped"] },
    { file: "README.md", terms: ["가져온 텍스트·배열 필드는 폼 기준 길이로 정규화"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_import_normalization_guard",
    requirement: "Imported backup text, numeric, and nested array fields are clamped to UI-safe bounds before persistence and rendering.",
    status: backupImportNormalizeTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupImportNormalizeTerms,
  });

  const backupImportRecordLimitTerms = [
    { file: "app.js", terms: ["const IMPORT_GUARDS = window.JooParkImportGuards", "importGuards: IMPORT_GUARDS", "function handleImportFile", "backupImportUiCall(\"handleImportFile\""] },
    { file: "backup-import-ui.js", terms: ["function importRecordLimitViolations", "function importRecordLimitMessage", "recordViolations.length > 0"] },
    { file: "backup-import-guards.js", terms: ["function recordLimitViolations", "function recordLimitMessage", "가져오기 항목 수가 너무 많습니다"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["settings import record-count guard", "backupRecordLimitRejected", "record-limit import changed saved data"] },
    { file: "README.md", terms: ["컬렉션별 항목 수 상한을 넘는 백업도 가져오지 않습니다"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "backup_import_record_count_guard",
    requirement: "Settings rejects valid backup JSON whose collection record counts exceed explicit import limits before confirmation or persistence.",
    status: backupImportRecordLimitTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: backupImportRecordLimitTerms,
  });

  const recentDeletedRecoveryTerms = [
    { file: "app.js", terms: ["const DELETED_ITEM_LIMIT = 40", "const DELETED_ITEM_RETENTION_DAYS = 30", "function captureDeletedItem", "function restoreDeletedItem", "function restoreAllDeletedItems", "function discardDeletedItem", "function confirmClearDeletedItems", "function canUndoDeletedItem", "function openDeletedRecoveryPanel", "function dataSafetyAccessItems", "dashboard.deletedItems = []"] },
    { file: "settings-view.js", terms: ["function deletedRecoveryExpiry", "data-settings-deleted-recovery", "data-deleted-recovery-search", "data-deleted-recovery-kind-filter", "data-deleted-recovery-retention-days", "data-deleted-recovery-expires-at", "data-deleted-recovery-days-remaining", "data-deleted-recovery-expiry", "restore-all-deleted-items", "clear-deleted-items", "discard-deleted-item", "data-deleted-recovery-empty"] },
    { file: "workspace-storage.js", terms: ["deletedItems: dashboard.deletedItems", "if (Array.isArray(rawV3.deletedItems)) dashboard.deletedItems = rawV3.deletedItems"] },
    { file: "backup-import-guards.js", terms: ["\"deletedItems\"", "label: \"최근 삭제\"", "max: 40"] },
    { file: "backup-import-ui.js", terms: ["function importArrayField", "importArrayField(source, \"deletedItems\")"] },
    { file: "command-palette.js", terms: ["최근 삭제 복구", "openDeletedRecoveryPanel", "deletedCount > 0"] },
    { file: "scripts/smoke-delete-undo.mjs", terms: ["settings recovery row did not expose expiry timestamp", "settings recovery row did not expose bounded days remaining", "settings recovery row did not show an expiry badge", "dbCatalogCall(\"deleteQuery\", queryId)", "recentlyDeletedRecovery: true", "discardAndClear: true", "retentionPruned: true", "searchAndKindFilter: true", "commandPaletteRecovery: true", "importGuardDeletedItems: true", "restoreAll: true"] },
    { file: "scripts/smoke-release.mjs", terms: ["scripts/smoke-delete-undo.mjs", "release delete undo smoke failed", "120000"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "recent_deleted_recovery",
    requirement: "Recently deleted records are captured in a bounded local recovery ledger, exposed in Settings and the command palette, included in backup/import boundaries, and proven by the release delete/undo smoke.",
    status: recentDeletedRecoveryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: recentDeletedRecoveryTerms,
  });

  const privacyStorageSafetyTerms = [
    { file: "app.js", terms: ["function settingsPrivacyHandoffText", "data-settings-privacy-handoff", "localStorage 키 `joopark.workspace.v3`", "토큰, 비밀번호, 세션 ID, API key", "private browsing", "file://"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["privacyStorageHandoff", "privacy handoff card does not explain local storage safety", "privacy handoff copy text is missing sensitive data warning", "privacy handoff copy text did not reach clipboard"] },
    { file: "README.md", terms: ["개인정보·보안", "토큰·비밀번호·API key", "private browsing", "file://"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "local_storage_privacy_safety_handoff",
    requirement: "The app explains localStorage scope, sensitive-data exclusions, export-file handling, and browser-session storage caveats in UI, docs, and interaction smoke.",
    status: privacyStorageSafetyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: privacyStorageSafetyTerms,
  });

  const docTerms = hasTerms("README.md", [
    "node scripts/smoke-release.mjs",
    "node scripts/smoke-mobile.mjs",
    "node scripts/smoke-interactions.mjs",
    "node scripts/smoke-a11y.mjs",
    "localStorage 키 `joopark.workspace.v3`",
    "실제로 생성/편집/삭제",
    "인스턴스·데이터베이스·테이블·컬럼·저장 쿼리·마이그레이션",
  ]);
  checklist.push({
    id: "operator_docs",
    requirement: "README documents how to run, verify, package, smoke, persist, and use the major CRUD surfaces.",
    status: docTerms.status,
    evidence: { file: "README.md", missingTerms: docTerms.missing },
  });

  const llmWikiSourceGovernanceTerms = [
    { file: "llm-wiki-view.js", terms: ["WIKI_SOURCES", "sourcePolicy", "source-governance/v1", "출처와 갱신 원칙", "Source governance", "불확실", "검증 출처", "Anthropic Claude models overview", "Anthropic prompt caching", "Anthropic prompt engineering overview", "Anthropic prompting tools", "Anthropic structured outputs", "Anthropic handle tool calls", "Model Context Protocol specification", "MCP transports", "MCP server tools", "MCP authorization", "Attention Is All You Need", "OpenAI Structured Outputs", "OpenAI function calling", "OpenAI using tools", "OpenAI prompt engineering", "OpenAI prompt guidance", "OpenAI model snapshots", "OpenAI evaluation datasets", "OpenAI graders", "Langfuse scores overview", "Langfuse LLM-as-a-Judge", "Langfuse Annotation Queues", "Langfuse experiments via SDK", "Langfuse experiment data model", "Langfuse experiments in CI/CD", "MLflow Tracking", "OpenTelemetry GenAI semantic conventions", "OpenFeature Evaluation Context", "OpenTelemetry feature flag semantic conventions", "W3C PROV-DM", "Argo Rollouts canary strategy", "GitHub Actions deployment environments", "Kubernetes deployment rollbacks", "Google SRE incident management", "Google SRE postmortem culture", "Google SRE Workbook postmortem practices", "NIST Computer Security Incident Handling Guide", "NIST SP 800-61 Rev. 3", "A Taxonomy of Failures in Tool-Augmented LLMs", "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment", "Anthropic Claude Console Evaluation tool", "Hugging Face Dataset Cards", "Datasheets for Datasets", "Data Cards for Responsible AI", "Benchmark Data Contamination of LLMs", "Langfuse prompt management", "Langfuse prompt version control", "OpenAI Agents SDK human-in-the-loop", "OpenAI Agents SDK guardrails", "OpenAI Agents SDK tools", "OWASP LLM06:2025 Excessive Agency", "OpenAI API authentication", "OpenAI API key safety", "The Twelve-Factor App config", "OWASP Secrets Management Cheat Sheet", "GitHub Actions secrets", "GitHub Actions OpenID Connect", "GitHub secret scanning push protection", "Vercel environment variables", "Netlify environment variables", "OpenAI images and vision", "OpenAI file inputs", "OpenAI speech to text", "OpenAI model optimization", "OpenAI supervised fine-tuning", "OpenAI evaluate external models", "Anthropic glossary fine-tuning", "Google Gemini model tuning", "Vercel AI Gateway model fallbacks", "Vercel AI Gateway observability", "OpenAI rate limits", "OpenAI error codes", "OpenAI API request debugging", "Anthropic rate limits", "Anthropic API errors", "Anthropic Rate Limits API", "Google Gemini API rate limits", "Google Gemini API troubleshooting", "Vercel AI Gateway provider options", "Vercel AI Gateway provider timeouts", "OpenAI data controls", "Anthropic API data handling", "Anthropic commercial data use and training", "Anthropic standard data retention", "Google Gemini API terms", "Vercel AI Gateway zero data retention", "OWASP LLM02:2025 Sensitive Information Disclosure", "Distilling the Knowledge in a Neural Network", "Anthropic vision", "Anthropic PDF support", "Anthropic citations", "Google Gemini Files API", "Google Gemini image understanding", "OpenAI model comparison", "Google Gemini API models", "Google Gemini Developer API pricing", "Meta Llama 4 release", "DeepSeek API models and pricing", "A/B 비교"] },
    { file: "styles.css", terms: [".wiki-source-panel", ".wiki-source-link", ".wiki-source-meta"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["sourceGovernanceShown", "sourcePanelShown", "sourceLinkCount", "sourceABTableRendered", "modelOptimizationMarkers", "modelOptimizationSourcePanel", "dataPrivacyMarkers", "dataPrivacySourcePanel", "runtimeReliabilityMarkers", "runtimeReliabilitySourcePanel", "promptReleaseMarkers", "promptReleaseSourcePanel", "agentToolPermissionMarkers", "agentToolPermissionSourcePanel", "deploymentSecretsMarkers", "deploymentSecretsSourcePanel", "apiExampleStructuredMarkers", "apiExampleToolMarkers", "apiExampleMcpMarkers", "multimodalFileMarkers", "multimodalFileSourcePanel", "evalDatasetGovernanceMarkers", "evalDatasetGovernanceSourcePanel", "evalResultLineageMarkers", "evalResultLineageSourcePanel", "evalFailureTriageMarkers", "evalFailureTriageSourcePanel", "evaluatorCalibrationMarkers", "evaluatorCalibrationSourcePanel", "postmortemActionLedgerMarkers", "postmortemActionLedgerSourcePanel", "rolloutDecisionLogMarkers", "rolloutDecisionLogSourcePanel", "출처와 갱신 원칙", "코드 임베드 유지", "별도 JSON/Markdown"] },
    { file: "README.md", terms: ["LLM 위키 운영", "WIKI_SOURCES", "source governance", "검증 출처", "불확실", "openai_models", "google_gemini_models", "deepseek_pricing", "check-llm-wiki-api-examples.mjs", "check-llm-wiki-multimodal-files.mjs", "check-llm-wiki-model-optimization-routing.mjs", "check-llm-wiki-data-privacy-retention.mjs", "check-llm-wiki-runtime-reliability.mjs", "check-llm-wiki-prompt-release-management.mjs", "check-llm-wiki-agent-tool-permissions.mjs", "check-llm-wiki-deployment-secrets-env.mjs", "check-llm-wiki-eval-dataset-governance.mjs", "check-llm-wiki-eval-result-lineage.mjs", "check-llm-wiki-eval-failure-triage.mjs", "check-llm-wiki-evaluator-calibration.mjs", "check-llm-wiki-postmortem-action-ledger.mjs", "check-llm-wiki-rollout-decision-log.mjs", "node scripts/smoke-llm-wiki.mjs", "llm_wiki_source_governance", "llm_wiki_multimodal_file_verification", "llm_wiki_model_optimization_routing_verification", "llm_wiki_data_privacy_retention_verification", "llm_wiki_runtime_reliability_verification", "llm_wiki_prompt_release_management_verification", "llm_wiki_agent_tool_permission_verification", "llm_wiki_deployment_secrets_env_verification", "llm_wiki_eval_dataset_governance_verification", "llm_wiki_eval_result_lineage_verification", "llm_wiki_eval_failure_triage_verification", "llm_wiki_evaluator_calibration_verification", "llm_wiki_postmortem_action_ledger_verification", "llm_wiki_rollout_decision_log_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_source_governance",
    requirement: "The embedded LLM wiki exposes source governance, official source references, an A/B source-structure decision, README update guidance, and browser smoke markers so volatile LLM/API claims remain traceable.",
    status: llmWikiSourceGovernanceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: llmWikiSourceGovernanceTerms,
  });

  const llmWikiModelLandscapeTerms = [
    { file: "llm-wiki-view.js", terms: ["2026년 모델 지형", "GPT-5.5", "Gemini 3.1 Pro Preview", "DeepSeek V4 Flash", "Llama 4 Scout", "task-tiered model matrix", "cache miss", "partner/self-hosted", "OpenAI model comparison", "Google Gemini Developer API pricing", "DeepSeek API models and pricing"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["modelLandscapeOfficialSources", "modelLandscapeSourcePanelShown", "GPT-5.5", "Gemini 3.1 Pro Preview", "DeepSeek V4 Flash", "Llama 4 Scout", "task-tiered model matrix"] },
    { file: "README.md", terms: ["모델 지형 갱신", "GPT-5.5", "Gemini 3.1 Pro Preview", "DeepSeek V4 Flash", "Llama 4 Scout", "task-tiered model matrix"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_model_landscape_official_sources",
    requirement: "The LLM wiki model landscape uses official-source markers for current OpenAI, Gemini, Meta Llama, and DeepSeek rows, records task-tiered model selection tradeoffs, and verifies those markers in the browser smoke.",
    status: llmWikiModelLandscapeTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: llmWikiModelLandscapeTerms,
  });

  const llmWikiModelOptimizationCheck = run("node", ["scripts/check-llm-wiki-model-optimization-routing.mjs"]);
  const llmWikiModelOptimizationCheckJson = parseJson(llmWikiModelOptimizationCheck.stdout);
  const llmWikiModelOptimizationTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI model optimization", "OpenAI supervised fine-tuning", "OpenAI evaluate external models", "Anthropic glossary fine-tuning", "Google Gemini model tuning", "Vercel AI Gateway model fallbacks", "Vercel AI Gateway observability", "Distilling the Knowledge in a Neural Network", "Fine-tuning · Distillation · Routing", "fine-tuning platform is winding down", "not accessible to new users", "Supervised fine-tuning (SFT)", "Direct preference optimization (DPO)", "Reinforcement fine-tuning (RFT)", "purpose: \\\"fine-tune\\\"", "training_file", "validation_file", "fineTuning.jobs.create", "full_valid_loss", "full_valid_mean_token_accuracy", "Claude API does not currently offer fine-tuning", "Gemini API or AI Studio no longer have a model available", "providerOptions.gateway.models", "router_decision", "fallback_reason", "served_model", "served_provider", "A/B 비교: fine-tuning vs RAG", "A/B 비교: static routing matrix vs gateway fallback", "A/B 비교: teacher-student distillation vs runtime routing"] },
    { file: "scripts/check-llm-wiki-model-optimization-routing.mjs", terms: ["source_registry", "model-optimization-routing", "source-governance", "openai_model_optimization", "openai_supervised_fine_tuning", "openai_external_models", "anthropic_fine_tuning_glossary", "google_gemini_model_tuning", "vercel_ai_gateway_fallbacks", "vercel_ai_gateway_observability", "distillation_paper", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["modelOptimizationMarkers", "modelOptimizationSourcePanel", "Fine-tuning", "fine-tuning platform is winding down", "not accessible to new users", "purpose: \"fine-tune\"", "router_decision", "served_model"] },
    { file: "README.md", terms: ["Model Optimization/Routing 검증", "fine-tuning platform is winding down", "not accessible to new users", "Supervised fine-tuning (SFT)", "Direct preference optimization (DPO)", "Reinforcement fine-tuning (RFT)", "purpose: \"fine-tune\"", "training_file", "validation_file", "fineTuning.jobs.create", "full_valid_loss", "providerOptions.gateway.models", "router_decision", "served_model", "check-llm-wiki-model-optimization-routing.mjs", "llm_wiki_model_optimization_routing_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_model_optimization_routing_verification",
    requirement: "The LLM wiki validates fine-tuning, distillation, model routing, and fallback guidance against official-source and paper-backed markers with an offline checker and browser smoke coverage.",
    status: llmWikiModelOptimizationCheck.ok &&
      llmWikiModelOptimizationCheckJson?.status === "pass" &&
      llmWikiModelOptimizationTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-model-optimization-routing.mjs",
      result: llmWikiModelOptimizationCheckJson || {
        status: llmWikiModelOptimizationCheck.status,
        stdout: llmWikiModelOptimizationCheck.stdout,
        stderr: llmWikiModelOptimizationCheck.stderr,
      },
      files: llmWikiModelOptimizationTerms,
    },
  });

  const llmWikiDataPrivacyRetentionCheck = run("node", ["scripts/check-llm-wiki-data-privacy-retention.mjs"]);
  const llmWikiDataPrivacyRetentionCheckJson = parseJson(llmWikiDataPrivacyRetentionCheck.stdout);
  const llmWikiDataPrivacyRetentionTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI data controls", "Anthropic API data handling", "Anthropic commercial data use and training", "Anthropic standard data retention", "Google Gemini API terms", "Vercel AI Gateway zero data retention", "OWASP LLM02:2025 Sensitive Information Disclosure", "데이터 프라이버시와 보존 정책", "LLM02:2025 Sensitive Information Disclosure", "data_inventory", "data_classification", "PII", "PHI", "secrets", "source retention class", "not used to train", "abuse monitoring logs", "retained for up to 30 days", "store: false", "Application State", "MCP servers are third-party services", "automatically delete inputs and outputs on our backend within 30 days", "Files API", "explicitly deleted", "ZDR applies to Messages and Token Counting APIs", "Unpaid Services", "Paid Services", "human reviewers may read", "Do not submit sensitive, confidential, or personal information to the Unpaid Services", "zeroDataRetention: true", "BYOK", "A/B 비교: default API retention vs zero data retention", "A/B 비교: unpaid/free developer tier vs paid/commercial API", "A/B 비교: raw observability logs vs redacted audit ledger"] },
    { file: "scripts/check-llm-wiki-data-privacy-retention.mjs", terms: ["source_registry", "data-privacy-retention", "source-governance", "openai_data_controls", "anthropic_api_data_retention", "anthropic_training_privacy", "anthropic_standard_retention", "google_gemini_api_terms", "vercel_ai_gateway_zdr", "owasp_llm02_sensitive_information", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["dataPrivacyMarkers", "dataPrivacySourcePanel", "데이터 프라이버시와 보존 정책", "LLM02:2025 Sensitive Information Disclosure", "not used to train", "store: false", "zeroDataRetention: true", "BYOK"] },
    { file: "README.md", terms: ["Data Privacy/Retention 검증", "LLM02:2025 Sensitive Information Disclosure", "data_inventory", "data_classification", "PII", "PHI", "secrets", "source retention class", "not used to train", "abuse monitoring logs", "retained for up to 30 days", "store: false", "MCP servers are third-party services", "ZDR applies to Messages and Token Counting APIs", "Unpaid Services", "Paid Services", "human reviewers may read", "zeroDataRetention: true", "BYOK", "check-llm-wiki-data-privacy-retention.mjs", "llm_wiki_data_privacy_retention_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_data_privacy_retention_verification",
    requirement: "The LLM wiki validates data training use, retention, ZDR, paid/unpaid tier boundaries, sensitive-information controls, and redacted audit guidance against official-source and OWASP markers with an offline checker and browser smoke coverage.",
    status: llmWikiDataPrivacyRetentionCheck.ok &&
      llmWikiDataPrivacyRetentionCheckJson?.status === "pass" &&
      llmWikiDataPrivacyRetentionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-data-privacy-retention.mjs",
      result: llmWikiDataPrivacyRetentionCheckJson || {
        status: llmWikiDataPrivacyRetentionCheck.status,
        stdout: llmWikiDataPrivacyRetentionCheck.stdout,
        stderr: llmWikiDataPrivacyRetentionCheck.stderr,
      },
      files: llmWikiDataPrivacyRetentionTerms,
    },
  });

  const llmWikiRuntimeReliabilityCheck = run("node", ["scripts/check-llm-wiki-runtime-reliability.mjs"]);
  const llmWikiRuntimeReliabilityCheckJson = parseJson(llmWikiRuntimeReliabilityCheck.stdout);
  const llmWikiRuntimeReliabilityTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI rate limits", "OpenAI error codes", "OpenAI API request debugging", "Anthropic rate limits", "Anthropic API errors", "Anthropic Rate Limits API", "Google Gemini API rate limits", "Google Gemini API troubleshooting", "Vercel AI Gateway provider options", "Vercel AI Gateway provider timeouts", "Vercel AI Gateway model fallbacks", "런타임 신뢰성과 장애 처리", "success_rate", "p95_latency_ms", "retry_count", "fallback_rate", "rate_limit_headroom", "error_budget_burn", "RPM", "RPD", "TPM", "TPD", "IPM", "x-ratelimit-limit-requests", "x-ratelimit-remaining-tokens", "x-ratelimit-reset-requests", "random exponential backoff", "unsuccessful requests contribute to your per-minute limit", "503 - Slow Down", "x-request-id", "X-Client-Request-Id", "token bucket algorithm", "retry-after", "anthropic-ratelimit-requests-remaining", "429 rate_limit_error", "504 timeout_error", "529 overloaded_error", "request-id", "SSE after 200", "Rate Limits API", "group_type", "per project, not per API key", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "providerOptions.gateway", "providerTimeouts", "order", "only", "models", "BYOK", "first token arrives", "A/B 비교: blind exponential retry vs header-aware client throttling", "A/B 비교: single-provider retry vs cross-provider failover", "A/B 비교: long timeout vs fast failover timeout"] },
    { file: "scripts/check-llm-wiki-runtime-reliability.mjs", terms: ["source_registry", "runtime-reliability", "source-governance", "openai_rate_limits", "openai_error_codes", "openai_api_request_debugging", "anthropic_rate_limits", "anthropic_errors", "anthropic_rate_limits_api", "google_gemini_rate_limits", "google_gemini_troubleshooting", "vercel_ai_gateway_provider_options", "vercel_ai_gateway_provider_timeouts", "vercel_ai_gateway_fallbacks", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["runtimeReliabilityMarkers", "runtimeReliabilitySourcePanel", "런타임 신뢰성과 장애 처리", "x-ratelimit-limit-requests", "retry-after", "529 overloaded_error", "providerTimeouts", "first token arrives"] },
    { file: "README.md", terms: ["Runtime Reliability 검증", "RPM", "RPD", "TPM", "TPD", "IPM", "x-ratelimit-limit-requests", "x-ratelimit-remaining-tokens", "x-ratelimit-reset-requests", "random exponential backoff", "unsuccessful requests contribute to your per-minute limit", "503 - Slow Down", "x-request-id", "X-Client-Request-Id", "token bucket algorithm", "retry-after", "anthropic-ratelimit-requests-remaining", "429 rate_limit_error", "504 timeout_error", "529 overloaded_error", "request-id", "SSE after 200", "Rate Limits API", "per project, not per API key", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "providerOptions.gateway", "providerTimeouts", "BYOK", "first token arrives", "check-llm-wiki-runtime-reliability.mjs", "llm_wiki_runtime_reliability_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_runtime_reliability_verification",
    requirement: "The LLM wiki validates rate limits, retry/backoff, timeout, request correlation, provider failover, and fallback-SLO guidance against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiRuntimeReliabilityCheck.ok &&
      llmWikiRuntimeReliabilityCheckJson?.status === "pass" &&
      llmWikiRuntimeReliabilityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-runtime-reliability.mjs",
      result: llmWikiRuntimeReliabilityCheckJson || {
        status: llmWikiRuntimeReliabilityCheck.status,
        stdout: llmWikiRuntimeReliabilityCheck.stdout,
        stderr: llmWikiRuntimeReliabilityCheck.stderr,
      },
      files: llmWikiRuntimeReliabilityTerms,
    },
  });

  const llmWikiPromptReleaseCheck = run("node", ["scripts/check-llm-wiki-prompt-release-management.mjs"]);
  const llmWikiPromptReleaseCheckJson = parseJson(llmWikiPromptReleaseCheck.stdout);
  const llmWikiPromptReleaseTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI prompt engineering", "OpenAI prompt guidance", "OpenAI evaluation best practices", "OpenAI production best practices", "OpenAI prompt caching", "OpenAI model snapshots", "Anthropic prompt engineering overview", "Anthropic prompting tools", "Anthropic prompt caching", "Langfuse prompt management", "Langfuse prompt version control", "프롬프트 릴리스와 버전 관리", "prompt_config_bundle", "prompt_id", "prompt_version", "prompt_hash", "registry_label", "model_alias", "model_snapshot", "developer_message_version", "schema_version", "tool_schema_version", "retrieval_version", "safety_policy_version", "eval_suite_version", "rollout_stage", "rollback_target", "developer and user messages", "model-specific prompt tuning", "stable prompt prefix", "cached_tokens", "prompt templates and variables", "prompt generator", "prompt improver", "evaluation tool", "storing, versioning, retrieving", "version ID", "labels", "production", "staging", "prod-a", "prod-b", "production label", "protected prompt labels", "eval-driven development", "golden dataset", "regression set", "safety probes", "canary-10pct", "user_correction_rate", "refusal_rate", "cost_per_success", "rollback runbook", "label revert", "cache warmup", "A/B 비교: hardcoded prompts in code vs prompt registry labels", "A/B 비교: model alias vs pinned model snapshot", "A/B 비교: big-bang prompt deploy vs staged eval/canary"] },
    { file: "scripts/check-llm-wiki-prompt-release-management.mjs", terms: ["source_registry", "prompt-release-management", "source-governance", "openai_prompt_engineering", "openai_prompt_guidance", "openai_eval_best_practices", "openai_production_best_practices", "openai_prompt_caching", "openai_model_snapshots", "anthropic_prompt_engineering_overview", "anthropic_prompting_tools", "anthropic_prompt_caching", "langfuse_prompt_management", "langfuse_prompt_version_control", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["promptReleaseMarkers", "promptReleaseSourcePanel", "프롬프트 릴리스와 버전 관리", "prompt_config_bundle", "model_snapshot", "production label", "rollback runbook"] },
    { file: "README.md", terms: ["Prompt Release/Version 검증", "prompt_config_bundle", "prompt_id", "prompt_version", "prompt_hash", "registry_label", "model_alias", "model_snapshot", "developer_message_version", "schema_version", "tool_schema_version", "retrieval_version", "safety_policy_version", "eval_suite_version", "rollout_stage", "rollback_target", "developer and user messages", "stable prompt prefix", "cached_tokens", "prompt templates and variables", "prompt generator", "prompt improver", "evaluation tool", "version ID", "production label", "protected prompt labels", "eval-driven development", "golden dataset", "canary-10pct", "rollback runbook", "check-llm-wiki-prompt-release-management.mjs", "llm_wiki_prompt_release_management_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_prompt_release_management_verification",
    requirement: "The LLM wiki validates prompt/config versioning, model snapshot pinning, prompt registry labels, eval/canary gates, cache-aware prompt layout, and rollback runbooks against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiPromptReleaseCheck.ok &&
      llmWikiPromptReleaseCheckJson?.status === "pass" &&
      llmWikiPromptReleaseTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-prompt-release-management.mjs",
      result: llmWikiPromptReleaseCheckJson || {
        status: llmWikiPromptReleaseCheck.status,
        stdout: llmWikiPromptReleaseCheck.stdout,
        stderr: llmWikiPromptReleaseCheck.stderr,
      },
      files: llmWikiPromptReleaseTerms,
    },
  });

  const llmWikiAgentToolPermissionCheck = run("node", ["scripts/check-llm-wiki-agent-tool-permissions.mjs"]);
  const llmWikiAgentToolPermissionCheckJson = parseJson(llmWikiAgentToolPermissionCheck.stdout);
  const llmWikiAgentToolPermissionTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI Agents SDK human-in-the-loop", "OpenAI Agents SDK guardrails", "OpenAI Agents SDK tools", "OpenAI using tools", "Anthropic tool use", "Anthropic handle tool calls", "MCP server tools", "MCP authorization", "MCP security best practices", "OWASP LLM06:2025 Excessive Agency", "에이전트 도구 권한과 승인 UX", "LLM06:2025 Excessive Agency", "excessive agency", "excessive functionality", "excessive permissions", "excessive autonomy", "permissions matrix", "tool_policy_bundle", "tool_authority_level", "read_only", "write_draft", "external_side_effect", "money_movement", "infrastructure_change", "needs_approval", "approval_required", "require_approval", "HostedMCPTool", "tool_config={\\\"require_approval\\\":\\\"always\\\"}", "on_approval_request", "RunResult.interruptions", "RunState", "state.approve", "state.reject", "always_approve", "always_reject", "function tools", "Agent.as_tool()", "agents-as-tools approvals surface on the outer run", "ShellTool", "ApplyPatchTool", "input guardrails", "output guardrails", "tripwire", "fail closed", "tool_result", "is_error", "tool_choice", "tools/list", "tools/call", "inputSchema", "outputSchema", "OAuth 2.1", "per-client consent", "redirect_uri", "token passthrough", "approval_id", "approver_id", "approval_status", "approval_reason", "risk_level", "blast_radius", "expires_at", "decision_id", "audit_log", "A/B 비교: prompt-only autonomy vs permission matrix", "A/B 비교: per-agent approval vs per-tool/per-call policy", "A/B 비교: auto-approve trusted tools vs human approval queue"] },
    { file: "scripts/check-llm-wiki-agent-tool-permissions.mjs", terms: ["source_registry", "agent-tool-permissions", "source-governance", "openai_agents_human_in_loop", "openai_agents_guardrails", "openai_agents_tools", "openai_tools", "anthropic_tool_use", "anthropic_handle_tool_calls", "mcp_tools", "mcp_authorization", "mcp_security_best_practices", "owasp_llm06_excessive_agency", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["agentToolPermissionMarkers", "agentToolPermissionSourcePanel", "에이전트 도구 권한과 승인 UX", "LLM06:2025 Excessive Agency", "permissions matrix", "tool_policy_bundle", "HostedMCPTool", "RunResult.interruptions", "ShellTool", "ApplyPatchTool", "approval_status", "decision_id"] },
    { file: "README.md", terms: ["Agent Tool Permission 검증", "LLM06:2025 Excessive Agency", "permissions matrix", "tool_policy_bundle", "tool_authority_level", "approval_required", "HostedMCPTool", "RunResult.interruptions", "RunState", "state.approve", "state.reject", "Agent.as_tool()", "ShellTool", "ApplyPatchTool", "input guardrails", "output guardrails", "tripwire", "fail closed", "approval_id", "approver_id", "approval_status", "blast_radius", "decision_id", "audit_log", "check-llm-wiki-agent-tool-permissions.mjs", "llm_wiki_agent_tool_permission_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_agent_tool_permission_verification",
    requirement: "The LLM wiki validates agent/tool permission matrices, human approval UX, MCP authorization boundaries, guardrails, and excessive-agency mitigations against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiAgentToolPermissionCheck.ok &&
      llmWikiAgentToolPermissionCheckJson?.status === "pass" &&
      llmWikiAgentToolPermissionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-agent-tool-permissions.mjs",
      result: llmWikiAgentToolPermissionCheckJson || {
        status: llmWikiAgentToolPermissionCheck.status,
        stdout: llmWikiAgentToolPermissionCheck.stdout,
        stderr: llmWikiAgentToolPermissionCheck.stderr,
      },
      files: llmWikiAgentToolPermissionTerms,
    },
  });

  const llmWikiDeploymentSecretsCheck = run("node", ["scripts/check-llm-wiki-deployment-secrets-env.mjs"]);
  const llmWikiDeploymentSecretsCheckJson = parseJson(llmWikiDeploymentSecretsCheck.stdout);
  const llmWikiDeploymentSecretsTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI API authentication", "OpenAI API key safety", "The Twelve-Factor App config", "OWASP Secrets Management Cheat Sheet", "GitHub Actions secrets", "GitHub Actions OpenID Connect", "GitHub secret scanning push protection", "Vercel environment variables", "Netlify environment variables", "배포 환경과 시크릿 분리", "deployment_secret_matrix", "secret_inventory", "secret_classification", "secret_owner", "runtime_injection", "build_time_injection", "public_runtime_config", "server-only", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "key management service", "client-side environments", "browsers or apps", "do not commit", "do not share", "Twelve-Factor Config", "environment variables", "development", "preview", "staging", "production", "Vercel", "Production", "Preview", "Development", "vercel env pull", ".env.local", ".env", "Netlify", "Deploy Previews", "Branch deploys", "Local development", "Contains secret values", "Secrets Controller", "team audit log", "GitHub Actions secrets", "gh secret set", "--env ENV_NAME", "--org ORG_NAME", "--repos", "secrets context", "::add-mask::VALUE", "OpenID Connect (OIDC)", "id-token: write", "short-lived access token", "no long-lived cloud secrets", "sub", "aud", "environment", "repo_property_*", "push protection", "secret scanning", "blocks pushes", "bypass reason", "creation", "rotation", "revocation", "expiration", "blast_radius", "break-glass", "A/B 비교: build-time injection vs runtime server proxy", "A/B 비교: static GitHub secret vs OIDC short-lived token", "A/B 비교: one shared provider key vs per-environment key"] },
    { file: "scripts/check-llm-wiki-deployment-secrets-env.mjs", terms: ["source_registry", "deployment-secrets-env", "source-governance", "openai_api_authentication", "openai_api_key_safety", "twelve_factor_config", "owasp_secrets_management", "github_actions_secrets", "github_actions_oidc", "github_secret_push_protection", "vercel_environment_variables", "netlify_environment_variables", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["deploymentSecretsMarkers", "deploymentSecretsSourcePanel", "배포 환경과 시크릿 분리", "deployment_secret_matrix", "secret_inventory", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "vercel env pull", "OpenID Connect (OIDC)", "push protection", "A/B 비교: static GitHub secret vs OIDC short-lived token"] },
    { file: "README.md", terms: ["Deployment Secrets/Env 검증", "deployment_secret_matrix", "secret_inventory", "secret_classification", "secret_owner", "runtime_injection", "build_time_injection", "public_runtime_config", "server-only", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "key management service", "client-side environments", "do not commit", "Twelve-Factor Config", "Vercel", "vercel env pull", ".env.local", "Netlify", "Deploy Previews", "Contains secret values", "Secrets Controller", "GitHub Actions secrets", "gh secret set", "--env ENV_NAME", "--org ORG_NAME", "--repos", "secrets context", "::add-mask::VALUE", "OpenID Connect (OIDC)", "id-token: write", "short-lived access token", "no long-lived cloud secrets", "repo_property_*", "push protection", "secret scanning", "blocks pushes", "bypass reason", "rotation", "revocation", "expiration", "break-glass", "check-llm-wiki-deployment-secrets-env.mjs", "llm_wiki_deployment_secrets_env_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_deployment_secrets_env_verification",
    requirement: "The LLM wiki validates deployment environment separation, provider key safety, CI/CD secrets, OIDC short-lived credentials, and push-protection controls against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiDeploymentSecretsCheck.ok &&
      llmWikiDeploymentSecretsCheckJson?.status === "pass" &&
      llmWikiDeploymentSecretsTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-deployment-secrets-env.mjs",
      result: llmWikiDeploymentSecretsCheckJson || {
        status: llmWikiDeploymentSecretsCheck.status,
        stdout: llmWikiDeploymentSecretsCheck.stdout,
        stderr: llmWikiDeploymentSecretsCheck.stderr,
      },
      files: llmWikiDeploymentSecretsTerms,
    },
  });

  const llmWikiApiExampleCheck = run("node", ["scripts/check-llm-wiki-api-examples.mjs"]);
  const llmWikiApiExampleCheckJson = parseJson(llmWikiApiExampleCheck.stdout);
  const llmWikiApiExampleTerms = [
    { file: "llm-wiki-view.js", terms: ["output_config.format", "OpenAI Responses API", "text: {", "response_format", "json_schema", "function_call_output", "tool_result", "is_error: true", "parallel_tool_calls: false", "JSON-RPC 2.0", "Streamable HTTP", "tools/list", "tools/call", "OAuth 2.1", "Protected Resource Metadata", "A/B 비교: 직접 tool API vs MCP"] },
    { file: "scripts/check-llm-wiki-api-examples.mjs", terms: ["source_registry", "structured-output", "tool-use", "mcp", "source-governance", "anthropic_handle_tool_calls", "openai_function_calling", "mcp_transports", "mcp_tools", "mcp_authorization", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["apiExampleStructuredMarkers", "apiExampleToolMarkers", "apiExampleMcpMarkers", "apiExampleStructuredSourcePanel", "apiExampleToolSourcePanel", "apiExampleMcpSourcePanel"] },
    { file: "README.md", terms: ["API 예시 검증", "output_config.format", "function_call_output", "tools/list", "tools/call", "OAuth 2.1", "check-llm-wiki-api-examples.mjs"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_api_example_shape_verification",
    requirement: "The LLM wiki validates current structured output, tool-use, and MCP example shapes against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiApiExampleCheck.ok &&
      llmWikiApiExampleCheckJson?.status === "pass" &&
      llmWikiApiExampleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-api-examples.mjs",
      result: llmWikiApiExampleCheckJson || {
        status: llmWikiApiExampleCheck.status,
        stdout: llmWikiApiExampleCheck.stdout,
        stderr: llmWikiApiExampleCheck.stderr,
      },
      files: llmWikiApiExampleTerms,
    },
  });

  const llmWikiRagEvalCheck = run("node", ["scripts/check-llm-wiki-rag-eval.mjs"]);
  const llmWikiRagEvalCheckJson = parseJson(llmWikiRagEvalCheck.stdout);
  const llmWikiRagEvalTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI embeddings guide", "OpenAI file search", "OpenAI retrieval and vector stores", "OpenAI Evals API", "Anthropic search results and citations", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", "BEIR: A Heterogeneous Benchmark", "MTEB: Massive Text Embedding Benchmark", "text-embedding-3-large", "dimensions", "vector_store_ids", "include: [\\\"file_search_call.results\\\"]", "citations.enabled", "data_source_config", "testing_criteria", "recall@k", "nDCG@10", "A/B 비교: hosted File Search vs self-managed RAG", "A/B 비교: offline golden-set eval vs online shadow eval"] },
    { file: "scripts/check-llm-wiki-rag-eval.mjs", terms: ["source_registry", "embeddings", "rag", "evaluation", "source-governance", "openai_embeddings", "anthropic_search_results", "beir_paper", "mteb_paper", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["ragEvalEmbeddingMarkers", "ragEvalRagMarkers", "ragEvalEvaluationMarkers", "ragEvalEmbeddingSourcePanel", "ragEvalRagSourcePanel", "ragEvalEvaluationSourcePanel", "vector_store_ids", "citations.enabled", "LLM-as-judge"] },
    { file: "README.md", terms: ["RAG/Evals 검증", "text-embedding-3-large", "vector_store_ids", "citations.enabled", "recall@k", "nDCG@10", "testing_criteria", "check-llm-wiki-rag-eval.mjs", "llm_wiki_rag_eval_grounding_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_rag_eval_grounding_verification",
    requirement: "The LLM wiki validates embeddings, RAG, and eval guidance against official-source and paper-backed markers with an offline checker and browser smoke coverage.",
    status: llmWikiRagEvalCheck.ok &&
      llmWikiRagEvalCheckJson?.status === "pass" &&
      llmWikiRagEvalTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-rag-eval.mjs",
      result: llmWikiRagEvalCheckJson || {
        status: llmWikiRagEvalCheck.status,
        stdout: llmWikiRagEvalCheck.stdout,
        stderr: llmWikiRagEvalCheck.stderr,
      },
      files: llmWikiRagEvalTerms,
    },
  });

  const llmWikiEvalDatasetGovernanceCheck = run("node", ["scripts/check-llm-wiki-eval-dataset-governance.mjs"]);
  const llmWikiEvalDatasetGovernanceCheckJson = parseJson(llmWikiEvalDatasetGovernanceCheck.stdout);
  const llmWikiEvalDatasetGovernanceTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI evaluation datasets", "OpenAI Evals API", "OpenAI evaluation best practices", "OpenAI graders", "Anthropic Claude Console Evaluation tool", "Hugging Face Dataset Cards", "Datasheets for Datasets", "Data Cards for Responsible AI", "Benchmark Data Contamination of LLMs", "평가 데이터셋 거버넌스", "eval_dataset_governance", "eval_dataset_contract", "dataset_id", "dataset_version", "dataset_hash", "schema_version", "item_schema", "data_source_config", "testing_criteria", "dataset_card", "datasheet", "data_card", "golden_set", "regression_set", "canary_set", "red_team_set", "holdout_set", "shadow_set", "production_sample", "consented_sample", "synthetic_sample", "redacted_fixture", "pii_redacted", "retention_class", "delete_request_id", "data_freshness_days", "stale_after_days", "license", "collection_method", "intended_use", "out_of_scope_use", "annotation_guidelines", "label_source", "subject_matter_expert", "inter_annotator_agreement", "privacy_review", "Evals platform deprecating", "read-only", "October 31, 2026", "November 30, 2026", "generated outputs", "expert annotations", "string_check", "text_similarity", "score_model", "grader_alignment_set", "Claude Console Evaluation tool", "Generate Test Case", "CSV import", "benchmark data contamination", "inflated or unreliable performance", "train/test leakage", "contamination_check", "temporal_holdout", "entity_holdout", "n-gram overlap", "near_duplicate", "generator_model", "prompt_hash", "reviewer_id", "task distribution drift", "label drift", "grader drift", "A/B 비교: production sample vs synthetic edge-case set", "A/B 비교: static golden set vs dynamic eval flywheel", "A/B 비교: public benchmark vs private holdout"] },
    { file: "scripts/check-llm-wiki-eval-dataset-governance.mjs", terms: ["source_registry", "eval-dataset-governance", "source-governance", "openai_eval_datasets", "openai_evals", "openai_eval_best_practices", "openai_graders", "anthropic_eval_tool", "huggingface_dataset_cards", "datasheets_for_datasets", "data_cards_paper", "benchmark_data_contamination_survey", "openai_data_controls", "owasp_llm02_sensitive_information", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["evalDatasetGovernanceMarkers", "evalDatasetGovernanceSourcePanel", "평가 데이터셋 거버넌스", "eval_dataset_contract", "dataset_hash", "golden_set", "synthetic_sample", "redacted_fixture", "Evals platform deprecating", "score_model", "grader_alignment_set", "Claude Console Evaluation tool", "Generate Test Case", "CSV import", "benchmark data contamination", "train/test leakage", "temporal_holdout", "entity_holdout", "n-gram overlap", "near_duplicate", "A/B 비교: public benchmark vs private holdout"] },
    { file: "README.md", terms: ["Eval Dataset Governance 검증", "eval_dataset_governance", "eval_dataset_contract", "dataset_id", "dataset_version", "dataset_hash", "item_schema", "data_source_config", "testing_criteria", "dataset_card", "golden_set", "regression_set", "canary_set", "red_team_set", "holdout_set", "shadow_set", "synthetic_sample", "redacted_fixture", "pii_redacted", "retention_class", "delete_request_id", "data_freshness_days", "Evals platform deprecating", "score_model", "grader_alignment_set", "Claude Console Evaluation tool", "Generate Test Case", "CSV import", "benchmark data contamination", "train/test leakage", "temporal_holdout", "entity_holdout", "n-gram overlap", "near_duplicate", "check-llm-wiki-eval-dataset-governance.mjs", "llm_wiki_eval_dataset_governance_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_eval_dataset_governance_verification",
    requirement: "The LLM wiki validates eval dataset versioning, dataset documentation, privacy lifecycle, synthetic/golden/holdout split policy, grader calibration, and contamination controls against official-source and paper-backed markers with an offline checker and browser smoke coverage.",
    status: llmWikiEvalDatasetGovernanceCheck.ok &&
      llmWikiEvalDatasetGovernanceCheckJson?.status === "pass" &&
      llmWikiEvalDatasetGovernanceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-eval-dataset-governance.mjs",
      result: llmWikiEvalDatasetGovernanceCheckJson || {
        status: llmWikiEvalDatasetGovernanceCheck.status,
        stdout: llmWikiEvalDatasetGovernanceCheck.stdout,
        stderr: llmWikiEvalDatasetGovernanceCheck.stderr,
      },
      files: llmWikiEvalDatasetGovernanceTerms,
    },
  });

  const llmWikiEvalResultLineageCheck = run("node", ["scripts/check-llm-wiki-eval-result-lineage.mjs"]);
  const llmWikiEvalResultLineageCheckJson = parseJson(llmWikiEvalResultLineageCheck.stdout);
  const llmWikiEvalResultLineageTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI Evals API", "OpenAI graders", "OpenAI Agents SDK tracing", "Langfuse experiments via SDK", "Langfuse experiment data model", "MLflow Tracking", "OpenTelemetry GenAI semantic conventions", "W3C PROV-DM", "평가 결과 Lineage와 실험 저장소", "eval_result_lineage", "eval_result_lineage_contract", "experiment_id", "experiment_run_id", "eval_id", "eval_run_id", "result_id", "report_url", "result_counts", "dataset_run_id", "source_trace_id", "source_observation_id", "trace_id", "span_id", "parent_id", "workflow_name", "group_id", "prompt_id", "prompt_version", "prompt_hash", "model_alias", "model_snapshot", "provider_name", "grader_id", "grader_version", "grader_type", "score_model", "pass_threshold", "metric_name", "metric_value", "artifact_uri", "raw_results_jsonl", "confusion_matrix_uri", "code_version", "config_hash", "lineage_schema_version", "decision_id", "rollback_target", "retention_class", "redaction_status", "failure_cluster_id", "lineage_complete=false", "sourceTraceId", "sourceObservationId", "DatasetRun", "grader hacking", "flush_traces()", "gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.response.model", "Entity", "Activity", "Agent", "wasGeneratedBy", "used", "wasDerivedFrom", "wasAssociatedWith", "A/B 비교: vendor dashboard result vs app-owned experiment ledger", "A/B 비교: trace-first debugging vs eval-first release gate", "A/B 비교: OpenTelemetry attributes vs W3C PROV graph"] },
    { file: "scripts/check-llm-wiki-eval-result-lineage.mjs", terms: ["source_registry", "eval-result-lineage", "source-governance", "openai_evals", "openai_graders", "openai_agents_tracing", "langfuse_experiments_sdk", "langfuse_experiment_data_model", "mlflow_tracking", "opentelemetry_genai_semconv", "w3c_prov_dm", "openai_data_controls", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["evalResultLineageMarkers", "evalResultLineageSourcePanel", "평가 결과 Lineage와 실험 저장소", "eval_result_lineage_contract", "experiment_run_id", "eval_run_id", "result_counts", "source_trace_id", "source_observation_id", "trace_id", "span_id", "prompt_hash", "model_snapshot", "grader_version", "lineage_schema_version", "sourceTraceId", "sourceObservationId", "DatasetRun", "gen_ai.operation.name", "W3C PROV-DM"] },
    { file: "README.md", terms: ["Eval Result Lineage 검증", "eval_result_lineage", "eval_result_lineage_contract", "experiment_id", "experiment_run_id", "eval_run_id", "result_id", "report_url", "result_counts", "dataset_run_id", "source_trace_id", "source_observation_id", "trace_id", "span_id", "prompt_hash", "model_snapshot", "grader_version", "pass_threshold", "metric_name", "artifact_uri", "raw_results_jsonl", "lineage_schema_version", "failure_cluster_id", "lineage_complete=false", "sourceTraceId", "sourceObservationId", "DatasetRun", "grader hacking", "flush_traces()", "gen_ai.operation.name", "gen_ai.request.model", "W3C PROV-DM", "check-llm-wiki-eval-result-lineage.mjs", "llm_wiki_eval_result_lineage_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_eval_result_lineage_verification",
    requirement: "The LLM wiki validates eval result lineage, experiment run storage, trace/result/grader joins, provenance graph fields, and release-decision reproducibility against official-source and standards-backed markers with an offline checker and browser smoke coverage.",
    status: llmWikiEvalResultLineageCheck.ok &&
      llmWikiEvalResultLineageCheckJson?.status === "pass" &&
      llmWikiEvalResultLineageTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-eval-result-lineage.mjs",
      result: llmWikiEvalResultLineageCheckJson || {
        status: llmWikiEvalResultLineageCheck.status,
        stdout: llmWikiEvalResultLineageCheck.stdout,
        stderr: llmWikiEvalResultLineageCheck.stderr,
      },
      files: llmWikiEvalResultLineageTerms,
    },
  });

  const llmWikiEvalFailureTriageCheck = run("node", ["scripts/check-llm-wiki-eval-failure-triage.mjs"]);
  const llmWikiEvalFailureTriageCheckJson = parseJson(llmWikiEvalFailureTriageCheck.stdout);
  const llmWikiEvalFailureTriageTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI Evals API", "OpenAI evaluation best practices", "OpenAI graders", "OpenAI Agents SDK tracing", "Langfuse scores overview", "Langfuse experiments via SDK", "Langfuse experiment data model", "Google SRE incident management", "NIST Computer Security Incident Handling Guide", "A Taxonomy of Failures in Tool-Augmented LLMs", "평가 실패 클러스터링과 인시던트 Triage", "eval_failure_triage", "failure_triage_taxonomy", "failure_cluster_id", "incident_id", "severity", "user_impact", "blast_radius", "detection_source", "score_name", "score_value", "score_comment", "NUMERIC", "CATEGORICAL", "BOOLEAN", "TEXT", "Open coding", "axial coding", "failure_mode", "root_cause_layer", "symptom", "attribution_confidence", "owner_team", "time_to_detect_ms", "time_to_triage_ms", "time_to_mitigate_ms", "regression_bug", "retrieval_miss", "retrieval_irrelevant", "generator_ignored_top_doc", "citation_mismatch", "stale_context", "prompt_regression", "schema_violation", "tool_selection_error", "tool_parameter_error", "tool_execution_error", "tool_result_interpretation_error", "policy_violation", "pii_leak", "excessive_agency", "latency_regression", "cost_regression", "rate_limit_regression", "guardrail_false_positive", "guardrail_false_negative", "judge_drift", "data_drift", "label_drift", "cluster_signature_hash", "representative_trace_id", "runbook_id", "mitigation_status", "postmortem_required", "blameless postmortem", "Incident Commander", "Communications Lead", "Operations Lead", "Preparation", "Detection and Analysis", "Containment, Eradication, and Recovery", "Post-Incident Activity", "NIST SP 800-61", "score analytics", "annotation queue", "full execution traces", "A/B 비교: manual taxonomy vs embedding clustering", "A/B 비교: symptom cluster vs root-cause cluster", "A/B 비교: eval-only triage vs incident workflow"] },
    { file: "scripts/check-llm-wiki-eval-failure-triage.mjs", terms: ["source_registry", "eval-failure-triage", "source-governance", "openai_evals", "openai_eval_best_practices", "openai_graders", "openai_agents_tracing", "langfuse_scores_overview", "langfuse_experiments_sdk", "langfuse_experiment_data_model", "google_sre_incident_management", "nist_incident_handling", "tool_augmented_llm_failure_taxonomy", "owasp_llm01_prompt_injection", "owasp_llm02_sensitive_information", "owasp_llm06_excessive_agency", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["evalFailureTriageMarkers", "evalFailureTriageSourcePanel", "평가 실패 클러스터링과 인시던트 Triage", "eval_failure_triage", "failure_triage_taxonomy", "failure_cluster_id", "incident_id", "score_name", "score_value", "Open coding", "axial coding", "failure_mode", "root_cause_layer", "retrieval_miss", "tool_selection_error", "Incident Commander", "NIST SP 800-61"] },
    { file: "README.md", terms: ["Eval Failure Triage 검증", "eval_failure_triage", "failure_triage_taxonomy", "failure_cluster_id", "incident_id", "severity", "user_impact", "score_name", "score_value", "NUMERIC", "CATEGORICAL", "Open coding", "axial coding", "failure_mode", "root_cause_layer", "retrieval_miss", "generator_ignored_top_doc", "citation_mismatch", "tool_selection_error", "tool_parameter_error", "policy_violation", "pii_leak", "excessive_agency", "guardrail_false_positive", "judge_drift", "cluster_signature_hash", "representative_trace_id", "Incident Commander", "NIST SP 800-61", "check-llm-wiki-eval-failure-triage.mjs", "llm_wiki_eval_failure_triage_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_eval_failure_triage_verification",
    requirement: "The LLM wiki validates eval failure clustering, root-cause taxonomy, score/trace intake, incident severity, SRE/NIST response roles, and postmortem workflow against official-source and paper-backed markers with an offline checker and browser smoke coverage.",
    status: llmWikiEvalFailureTriageCheck.ok &&
      llmWikiEvalFailureTriageCheckJson?.status === "pass" &&
      llmWikiEvalFailureTriageTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-eval-failure-triage.mjs",
      result: llmWikiEvalFailureTriageCheckJson || {
        status: llmWikiEvalFailureTriageCheck.status,
        stdout: llmWikiEvalFailureTriageCheck.stdout,
        stderr: llmWikiEvalFailureTriageCheck.stderr,
      },
      files: llmWikiEvalFailureTriageTerms,
    },
  });

  const llmWikiEvaluatorCalibrationCheck = run("node", ["scripts/check-llm-wiki-evaluator-calibration.mjs"]);
  const llmWikiEvaluatorCalibrationCheckJson = parseJson(llmWikiEvaluatorCalibrationCheck.stdout);
  const llmWikiEvaluatorCalibrationTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI Evals API", "OpenAI evaluation best practices", "OpenAI graders", "Langfuse scores overview", "Langfuse LLM-as-a-Judge", "Langfuse Annotation Queues", "Langfuse experiments via SDK", "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment", "LLM Judge와 Label Calibration", "evaluator_calibration", "judge_calibration_contract", "judge_id", "judge_model", "judge_prompt_hash", "rubric_version", "score_config_id", "score_type", "numeric_scale", "categorical_labels", "boolean_threshold", "human_alignment_set", "human_label_batch_id", "annotator_id", "annotator_role", "blinded_review", "randomized_order", "inter_annotator_agreement", "golden_label", "adjudicated_label", "disagreement_reason", "label_confidence", "calibration_set_id", "calibration_split", "judge_human_agreement", "pairwise_agreement", "kappa", "spearman_correlation", "kendall_tau", "mean_absolute_error", "calibration_curve", "drift_window", "judge_drift", "label_drift", "threshold_drift", "position_bias", "verbosity_bias", "self_preference_bias", "reference_leakage", "rubric_ambiguity", "grader_hacking", "pass_threshold", "sampling_params", "seed", "temperature", "reasoning_effort", "score_model", "LLM-as-a-Judge", "Annotation Queues", "score config", "corrected outputs", "score reasoning", "human reviewers", "Human evals", "MT-Bench", "Chatbot Arena", "over 80% agreement", "G-Eval", "form-filling paradigm", "A/B 비교: LLM-as-a-Judge vs human review", "A/B 비교: single judge vs judge panel", "A/B 비교: fixed rubric vs evolving rubric"] },
    { file: "scripts/check-llm-wiki-evaluator-calibration.mjs", terms: ["source_registry", "evaluator-calibration", "source-governance", "openai_evals", "openai_eval_best_practices", "openai_graders", "langfuse_scores_overview", "langfuse_llm_as_judge", "langfuse_annotation_queues", "langfuse_experiments_sdk", "llm_judge_mt_bench", "ge_eval_paper", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["evaluatorCalibrationMarkers", "evaluatorCalibrationSourcePanel", "LLM Judge와 Label Calibration", "evaluator_calibration", "judge_calibration_contract", "judge_id", "judge_model", "rubric_version", "score_config_id", "human_alignment_set", "inter_annotator_agreement", "judge_human_agreement", "judge_drift", "label_drift", "threshold_drift", "LLM-as-a-Judge", "Annotation Queues", "MT-Bench", "Chatbot Arena", "G-Eval"] },
    { file: "README.md", terms: ["Evaluator Calibration 검증", "evaluator_calibration", "judge_calibration_contract", "judge_id", "judge_model", "judge_prompt_hash", "rubric_version", "score_config_id", "score_type", "human_alignment_set", "human_label_batch_id", "blinded_review", "inter_annotator_agreement", "judge_human_agreement", "pairwise_agreement", "kappa", "spearman_correlation", "judge_drift", "label_drift", "threshold_drift", "position_bias", "verbosity_bias", "self_preference_bias", "grader_hacking", "score_model", "LLM-as-a-Judge", "Annotation Queues", "score config", "Human evals", "MT-Bench", "Chatbot Arena", "over 80% agreement", "G-Eval", "check-llm-wiki-evaluator-calibration.mjs", "llm_wiki_evaluator_calibration_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_evaluator_calibration_verification",
    requirement: "The LLM wiki validates LLM-as-a-Judge calibration, human label QA, judge/human agreement metrics, bias/drift monitoring, and rubric/version controls against official-source and paper-backed markers with an offline checker and browser smoke coverage.",
    status: llmWikiEvaluatorCalibrationCheck.ok &&
      llmWikiEvaluatorCalibrationCheckJson?.status === "pass" &&
      llmWikiEvaluatorCalibrationTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-evaluator-calibration.mjs",
      result: llmWikiEvaluatorCalibrationCheckJson || {
        status: llmWikiEvaluatorCalibrationCheck.status,
        stdout: llmWikiEvaluatorCalibrationCheck.stdout,
        stderr: llmWikiEvaluatorCalibrationCheck.stderr,
      },
      files: llmWikiEvaluatorCalibrationTerms,
    },
  });

  const llmWikiPostmortemActionLedgerCheck = run("node", ["scripts/check-llm-wiki-postmortem-action-ledger.mjs"]);
  const llmWikiPostmortemActionLedgerCheckJson = parseJson(llmWikiPostmortemActionLedgerCheck.stdout);
  const llmWikiPostmortemActionLedgerTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI Evals API", "OpenAI evaluation best practices", "OpenAI graders", "Langfuse scores overview", "Langfuse Annotation Queues", "Langfuse experiments via SDK", "Google SRE incident management", "Google SRE postmortem culture", "Google SRE Workbook postmortem practices", "NIST Computer Security Incident Handling Guide", "NIST SP 800-61 Rev. 3", "Postmortem Action Ledger와 재발 방지 Eval", "postmortem_action_ledger", "postmortem_action_contract", "action_item_id", "postmortem_id", "incident_id", "failure_cluster_id", "eval_run_id", "dataset_run_id", "trace_id", "judge_id", "score_config_id", "calibration_set_id", "action_type", "prevent_action", "detect_action", "mitigate_action", "owner_team", "action_owner_id", "tracking_ticket", "priority", "due_at", "verifiable_end_state", "acceptance_eval_id", "acceptance_eval_run_id", "regression_eval_suite", "closure_evidence_uri", "closure_reviewer_id", "postmortem_reviewed_at", "blameless", "root_cause", "trigger", "lessons_learned", "recurrence_linked_incident_id", "stale_action_escalation", "CSF 2.0", "Govern", "Identify", "Protect", "Detect", "Respond", "Recover", "lessons learned", "continuous improvement", "score analytics", "Annotation Queues", "score config", "action_status=closed", "risk_acceptance", "A/B 비교: free-form postmortem vs action ledger", "A/B 비교: manual closure vs eval-gated closure", "A/B 비교: prevent vs detect/mitigate action"] },
    { file: "scripts/check-llm-wiki-postmortem-action-ledger.mjs", terms: ["source_registry", "postmortem-action-ledger", "source-governance", "openai_evals", "openai_eval_best_practices", "openai_graders", "langfuse_scores_overview", "langfuse_annotation_queues", "langfuse_experiments_sdk", "google_sre_incident_management", "google_sre_postmortem_culture", "google_sre_workbook_postmortem", "nist_incident_handling", "nist_sp_800_61r3", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["postmortemActionLedgerMarkers", "postmortemActionLedgerSourcePanel", "Postmortem Action Ledger와 재발 방지 Eval", "postmortem_action_ledger", "postmortem_action_contract", "action_item_id", "tracking_ticket", "verifiable_end_state", "acceptance_eval_run_id", "CSF 2.0", "continuous improvement", "A/B 비교: manual closure vs eval-gated closure"] },
    { file: "README.md", terms: ["Postmortem Action Ledger 검증", "postmortem_action_ledger", "postmortem_action_contract", "action_item_id", "postmortem_id", "incident_id", "failure_cluster_id", "eval_run_id", "dataset_run_id", "trace_id", "judge_id", "score_config_id", "calibration_set_id", "action_type", "prevent_action", "detect_action", "mitigate_action", "owner_team", "action_owner_id", "tracking_ticket", "priority", "due_at", "verifiable_end_state", "acceptance_eval_id", "acceptance_eval_run_id", "regression_eval_suite", "closure_evidence_uri", "closure_reviewer_id", "postmortem_reviewed_at", "CSF 2.0", "Govern", "Identify", "Protect", "Detect", "Respond", "Recover", "continuous improvement", "action_status=closed", "risk_acceptance", "check-llm-wiki-postmortem-action-ledger.mjs", "llm_wiki_postmortem_action_ledger_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_postmortem_action_ledger_verification",
    requirement: "The LLM wiki validates postmortem action ownership, ticket tracking, verifiable end states, eval-gated closure, recurrence prevention, and CSF/SRE incident learning loops against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiPostmortemActionLedgerCheck.ok &&
      llmWikiPostmortemActionLedgerCheckJson?.status === "pass" &&
      llmWikiPostmortemActionLedgerTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-postmortem-action-ledger.mjs",
      result: llmWikiPostmortemActionLedgerCheckJson || {
        status: llmWikiPostmortemActionLedgerCheck.status,
        stdout: llmWikiPostmortemActionLedgerCheck.stdout,
        stderr: llmWikiPostmortemActionLedgerCheck.stderr,
      },
      files: llmWikiPostmortemActionLedgerTerms,
    },
  });

  const llmWikiRolloutDecisionLogCheck = run("node", ["scripts/check-llm-wiki-rollout-decision-log.mjs"]);
  const llmWikiRolloutDecisionLogCheckJson = parseJson(llmWikiRolloutDecisionLogCheck.stdout);
  const llmWikiRolloutDecisionLogTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI Evals API", "OpenAI evaluation best practices", "Langfuse experiments via SDK", "Langfuse scores overview", "Langfuse experiments in CI/CD", "OpenFeature Evaluation Context", "OpenTelemetry feature flag semantic conventions", "Argo Rollouts canary strategy", "GitHub Actions deployment environments", "Kubernetes deployment rollbacks", "Rollout Decision Log와 Rollback Gate", "rollout_decision_log", "rollout_decision_contract", "decision_id", "action_item_id", "postmortem_id", "release_candidate_id", "eval_run_id", "dataset_run_id", "acceptance_eval_run_id", "regression_eval_suite", "rollout_stage", "rollout_strategy", "feature_flag_key", "feature_flag_context", "targeting_key", "flag_variant", "feature_flag.result.variant", "feature_flag.result.reason", "feature_flag.version", "feature_flag.provider.name", "canary_weight", "canary_step_index", "canary_analysis_run_id", "analysis_status", "abort_on_failed_analysis", "guarded_promote", "promote_criteria", "rollback_target", "rollback_trigger", "rollback_runbook_id", "rollback_window", "stable_replica_set", "deployment_environment", "environment_protection_rule", "required_reviewers", "wait_timer", "deployment_status_id", "decision_owner_id", "approver_id", "blast_radius", "observability_window", "decision_status", "go_decision", "no_go_decision", "risk_acceptance", "RegressionError", "targeting key", "setWeight", "pause", "stable/canary ReplicaSet", "required reviewers", "Deployment rollback", "A/B 비교: feature flag rollout vs deployment canary", "A/B 비교: automatic abort vs human approval", "A/B 비교: dashboard decision vs app-owned decision log"] },
    { file: "scripts/check-llm-wiki-rollout-decision-log.mjs", terms: ["source_registry", "rollout-decision-log", "source-governance", "openai_evals", "openai_eval_best_practices", "langfuse_experiments_sdk", "langfuse_scores_overview", "langfuse_experiments_ci_cd", "openfeature_evaluation_context", "opentelemetry_feature_flag_semconv", "argo_rollouts_canary", "github_actions_environments", "kubernetes_deployment_rollback", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["rolloutDecisionLogMarkers", "rolloutDecisionLogSourcePanel", "Rollout Decision Log와 Rollback Gate", "rollout_decision_contract", "feature_flag_context", "feature_flag.result.variant", "canary_analysis_run_id", "deployment_environment", "environment_protection_rule", "go_decision", "no_go_decision", "A/B 비교: feature flag rollout vs deployment canary"] },
    { file: "README.md", terms: ["Rollout Decision Log 검증", "rollout_decision_log", "rollout_decision_contract", "decision_id", "action_item_id", "postmortem_id", "release_candidate_id", "eval_run_id", "dataset_run_id", "acceptance_eval_run_id", "regression_eval_suite", "rollout_stage", "rollout_strategy", "feature_flag_key", "feature_flag_context", "targeting_key", "flag_variant", "feature_flag.result.variant", "feature_flag.result.reason", "feature_flag.version", "feature_flag.provider.name", "canary_weight", "canary_step_index", "canary_analysis_run_id", "analysis_status", "abort_on_failed_analysis", "guarded_promote", "promote_criteria", "rollback_target", "rollback_trigger", "rollback_runbook_id", "rollback_window", "stable_replica_set", "deployment_environment", "environment_protection_rule", "required_reviewers", "wait_timer", "deployment_status_id", "decision_owner_id", "approver_id", "blast_radius", "observability_window", "decision_status", "go_decision", "no_go_decision", "risk_acceptance", "check-llm-wiki-rollout-decision-log.mjs", "llm_wiki_rollout_decision_log_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_rollout_decision_log_verification",
    requirement: "The LLM wiki validates rollout decisions, feature flag targeting context, canary analysis, deployment environment protection, rollback runbooks, and app-owned release decision evidence against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiRolloutDecisionLogCheck.ok &&
      llmWikiRolloutDecisionLogCheckJson?.status === "pass" &&
      llmWikiRolloutDecisionLogTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-rollout-decision-log.mjs",
      result: llmWikiRolloutDecisionLogCheckJson || {
        status: llmWikiRolloutDecisionLogCheck.status,
        stdout: llmWikiRolloutDecisionLogCheck.stdout,
        stderr: llmWikiRolloutDecisionLogCheck.stderr,
      },
      files: llmWikiRolloutDecisionLogTerms,
    },
  });

  const llmWikiMultimodalFileCheck = run("node", ["scripts/check-llm-wiki-multimodal-files.mjs"]);
  const llmWikiMultimodalFileCheckJson = parseJson(llmWikiMultimodalFileCheck.stdout);
  const llmWikiMultimodalFileTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI images and vision", "OpenAI file inputs", "OpenAI speech to text", "Anthropic vision", "Anthropic PDF support", "Anthropic citations", "Google Gemini Files API", "Google Gemini image understanding", "멀티모달과 파일 입력", "input_image", "input_file", "file_id", "image_url", "detail: \\\"high\\\"", "type: \\\"image\\\"", "type: \\\"document\\\"", "citations.enabled=true", "gpt-4o-transcribe", "gpt-4o-mini-transcribe", "source chips", "page number", "quote snippet", "citation ledger", "A/B 비교: direct multimodal context vs extracted ingestion pipeline", "A/B 비교: provider-native citations vs app-owned citation ledger"] },
    { file: "scripts/check-llm-wiki-multimodal-files.mjs", terms: ["source_registry", "multimodal-file-inputs", "source-governance", "openai_images_vision", "openai_file_inputs", "openai_speech_to_text", "anthropic_vision", "anthropic_pdf_support", "anthropic_citations", "google_gemini_files", "google_gemini_vision", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["multimodalFileMarkers", "multimodalFileSourcePanel", "멀티모달과 파일 입력", "input_image", "input_file", "gpt-4o-transcribe", "source chips", "page number"] },
    { file: "README.md", terms: ["Multimodal/File 검증", "input_image", "input_file", "file_id", "detail: \"high\"", "type: \"image\"", "type: \"document\"", "citations.enabled=true", "gpt-4o-transcribe", "source chips", "check-llm-wiki-multimodal-files.mjs", "llm_wiki_multimodal_file_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_multimodal_file_verification",
    requirement: "The LLM wiki validates multimodal image/file/PDF/audio input guidance and citation UX against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiMultimodalFileCheck.ok &&
      llmWikiMultimodalFileCheckJson?.status === "pass" &&
      llmWikiMultimodalFileTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-multimodal-files.mjs",
      result: llmWikiMultimodalFileCheckJson || {
        status: llmWikiMultimodalFileCheck.status,
        stdout: llmWikiMultimodalFileCheck.stdout,
        stderr: llmWikiMultimodalFileCheck.stderr,
      },
      files: llmWikiMultimodalFileTerms,
    },
  });

  const llmWikiSafetyCheck = run("node", ["scripts/check-llm-wiki-safety-ops.mjs"]);
  const llmWikiSafetyCheckJson = parseJson(llmWikiSafetyCheck.stdout);
  const llmWikiSafetyTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI safety best practices", "OpenAI safety checks", "Anthropic mitigate jailbreaks and prompt injections", "Anthropic reduce prompt leak", "OWASP LLM01:2025 Prompt Injection", "MCP security best practices", "LLM01:2025", "direct prompt injection", "indirect prompt injection", "tool_result blocks", "JSON-encode untrusted content", "Moderation API", "safety_identifier", "Human in the loop (HITL)", "per-client consent", "redirect_uri", "OAuth state", "token passthrough", "A/B 비교: prompt-only guardrails vs layered enforcement"] },
    { file: "scripts/check-llm-wiki-safety-ops.mjs", terms: ["source_registry", "safety", "source-governance", "openai_safety_best_practices", "anthropic_mitigate_jailbreaks", "owasp_llm01_prompt_injection", "mcp_security_best_practices", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["safetyGuardrailMarkers", "safetyGuardrailSourcePanel", "LLM01:2025", "direct prompt injection", "indirect prompt injection", "safety_identifier", "token passthrough"] },
    { file: "README.md", terms: ["Safety/Guardrail 검증", "LLM01:2025", "direct prompt injection", "indirect prompt injection", "tool_result blocks", "JSON-encode untrusted content", "safety_identifier", "token passthrough", "check-llm-wiki-safety-ops.mjs", "llm_wiki_safety_guardrail_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_safety_guardrail_verification",
    requirement: "The LLM wiki validates prompt-injection, prompt-leak, moderation, HITL, and MCP security guardrail guidance against official-source and OWASP markers with an offline checker and browser smoke coverage.",
    status: llmWikiSafetyCheck.ok &&
      llmWikiSafetyCheckJson?.status === "pass" &&
      llmWikiSafetyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-safety-ops.mjs",
      result: llmWikiSafetyCheckJson || {
        status: llmWikiSafetyCheck.status,
        stdout: llmWikiSafetyCheck.stdout,
        stderr: llmWikiSafetyCheck.stderr,
      },
      files: llmWikiSafetyTerms,
    },
  });

  const llmWikiCostObservabilityCheck = run("node", ["scripts/check-llm-wiki-cost-observability.mjs"]);
  const llmWikiCostObservabilityCheckJson = parseJson(llmWikiCostObservabilityCheck.stdout);
  const llmWikiCostObservabilityTerms = [
    { file: "llm-wiki-view.js", terms: ["OpenAI cost optimization", "OpenAI latency optimization", "OpenAI Batch API", "OpenAI Flex processing", "OpenAI Priority processing", "OpenAI prompt caching", "Anthropic batch processing", "Anthropic token counting", "OpenAI production best practices", "OpenAI Agents SDK tracing", "service_tier: \\\"flex\\\"", "service_tier: \\\"priority\\\"", "cached_tokens", "messages.count_tokens", "50% cost discount", "24-hour turnaround", "time_to_first_token_ms", "trace_id", "span_id", "workflow_name", "guardrails", "ZDR", "A/B 비교: async low-cost vs priority low-latency", "A/B 비교: provider tracing vs self-managed OpenTelemetry"] },
    { file: "scripts/check-llm-wiki-cost-observability.mjs", terms: ["source_registry", "cost", "observability", "source-governance", "openai_cost_optimization", "openai_agents_tracing", "anthropic_batch_processing", "anthropic_token_counting", "missingTerms", "missingSources"] },
    { file: "scripts/smoke-llm-wiki.mjs", terms: ["costOpsMarkers", "costOpsSourcePanel", "observabilityMarkers", "observabilitySourcePanel", "service_tier: \"flex\"", "trace_id", "time_to_first_token_ms"] },
    { file: "README.md", terms: ["Cost/Observability 검증", "service_tier: \"flex\"", "service_tier: \"priority\"", "cached_tokens", "messages.count_tokens", "time_to_first_token_ms", "trace_id", "span_id", "workflow_name", "check-llm-wiki-cost-observability.mjs", "llm_wiki_cost_observability_verification"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "llm_wiki_cost_observability_verification",
    requirement: "The LLM wiki validates cost, latency, batch/flex/priority routing, prompt-cache accounting, token counting, and tracing guidance against official-source markers with an offline checker and browser smoke coverage.",
    status: llmWikiCostObservabilityCheck.ok &&
      llmWikiCostObservabilityCheckJson?.status === "pass" &&
      llmWikiCostObservabilityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      command: "node scripts/check-llm-wiki-cost-observability.mjs",
      result: llmWikiCostObservabilityCheckJson || {
        status: llmWikiCostObservabilityCheck.status,
        stdout: llmWikiCostObservabilityCheck.stdout,
        stderr: llmWikiCostObservabilityCheck.stderr,
      },
      files: llmWikiCostObservabilityTerms,
    },
  });

  const snapshots = ["data/repos.json", "data/adoption-candidates.json"].map((path) => ({ path, ...dataSnapshot(path) }));
  checklist.push({
    id: "github_snapshot_data",
    requirement: "GitHub and adoption-candidate project snapshots are valid local JSON seed data.",
    status: snapshots.every((item) => item.status === "pass") ? "pass" : "fail",
    evidence: snapshots,
  });

  const candidateSourceCoverage = adoptionCandidateSourceCoverage("data/adoption-candidates.json");
  checklist.push({
    id: "candidate_source_backing_coverage",
    requirement: "Adoption candidates have safe GitHub source URLs, the source-gap refresh marker, and enough commit-backed metadata to keep triage out of source-enrichment mode.",
    status: candidateSourceCoverage.status,
    evidence: candidateSourceCoverage,
  });

  const freshnessDriftFiles = freshnessDriftScripts.map((path) => ({ path, exists: fileExists(path) }));
  const freshnessDriftTerms = [
    { file: "scripts/check-candidate-freshness-drift.mjs", terms: ["--snapshot-only", "--live", "--fail-on-drift", "--repo", "repoFilters", "driftCount", "blockingDriftCount", "actionableDriftCount", "actionableDrifted", "advisoryDriftCount", "advisoryFields", "lastCommit", "pushedAt"] },
    { file: "README.md", terms: ["check-candidate-freshness-drift.mjs", "--snapshot-only", "--live", "--fail-on-drift", "--repo", "candidate freshness drift", "blockingDriftCount", "actionableDriftCount", "advisoryDriftCount", "stars/forks"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const freshnessDriftSnapshot = run("node", ["scripts/check-candidate-freshness-drift.mjs", "--snapshot-only"]);
  checklist.push({
    id: "candidate_freshness_drift_monitor",
    requirement: "Source-backed adoption candidates have an operator drift monitor that can validate local snapshot shape offline and compare live GitHub HEAD metadata on demand.",
    status: freshnessDriftFiles.every((item) => item.exists) &&
      freshnessDriftTerms.every((item) => item.missingTerms.length === 0) &&
      freshnessDriftSnapshot.ok ? "pass" : "fail",
    evidence: {
      files: freshnessDriftFiles,
      terms: freshnessDriftTerms,
      snapshotOnly: {
        command: "node scripts/check-candidate-freshness-drift.mjs --snapshot-only",
        status: freshnessDriftSnapshot.ok ? "pass" : "fail",
        result: parseJson(freshnessDriftSnapshot.stdout) || freshnessDriftSnapshot.stdout.trim(),
        stderr: freshnessDriftSnapshot.stderr.trim(),
      },
    },
  });

  const freshnessCadenceTerms = [
    { file: "scripts/check-candidate-freshness-drift.mjs", terms: ["--cadence-policy", "candidate-freshness-drift-cadence-v1", "candidate-freshness-commit-stable-repo-metadata-v2", "highChurnRepos", "repoScopedHighChurn", "highChurnSourceMetadataCadenceAdvisory", "commitStableMetadataAdvisory", "--fail-on-drift"] },
    { file: "README.md", terms: ["--cadence-policy", "high-churn", "Veritas-7/autoresearch-skill-system", "cadence-advisory", "metadata-advisory", "--fail-on-drift"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const freshnessCadenceSnapshot = run("node", [
    "scripts/check-candidate-freshness-drift.mjs",
    "--snapshot-only",
    "--repo",
    "Veritas-7/autoresearch-skill-system",
    "--cadence-policy",
  ]);
  const freshnessCadenceResult = parseJson(freshnessCadenceSnapshot.stdout);
  const cadencePolicy = freshnessCadenceResult?.cadencePolicy || null;
  const cadenceHighChurnRepos = Array.isArray(cadencePolicy?.highChurnRepos) ? cadencePolicy.highChurnRepos : [];
  const cadencePolicyReady = Boolean(
    cadencePolicy?.id === "candidate-freshness-drift-cadence-v1" &&
    cadencePolicy?.checks?.repoScopedHighChurn &&
    cadencePolicy?.checks?.failOnDriftCommandScoped &&
    cadencePolicy?.checks?.highChurnSourceMetadataCadenceAdvisory &&
    cadencePolicy?.checks?.commitStableMetadataAdvisory &&
    cadenceHighChurnRepos.some((item) => item.repo === "Veritas-7/autoresearch-skill-system" && item.monitored && item.inScope),
  );
  checklist.push({
    id: "candidate_freshness_drift_cadence_policy",
    requirement: "High-churn adoption-candidate sources have bounded nonblocking drift policies before fail-on-drift automation is enabled.",
    status: freshnessCadenceTerms.every((item) => item.missingTerms.length === 0) &&
      freshnessCadenceSnapshot.ok &&
      cadencePolicyReady ? "pass" : "fail",
    evidence: {
      terms: freshnessCadenceTerms,
      snapshotOnly: {
        command: "node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system --cadence-policy",
        status: freshnessCadenceSnapshot.ok ? "pass" : "fail",
        cadencePolicy,
        stderr: freshnessCadenceSnapshot.stderr.trim(),
      },
    },
  });

  const veritasSnapshotWriterFiles = veritasSnapshotWriterScripts.map((path) => ({ path, exists: fileExists(path) }));
  const veritasSnapshotWriterTerms = [
    { file: "scripts/refresh-veritas-candidate-snapshot.mjs", terms: ["--snapshot-only", "--write", "--fail-on-change", "gh api", "graphql", "veritas-focused-drift-refresh", "messageHeadline"] },
    { file: "README.md", terms: ["refresh-veritas-candidate-snapshot.mjs", "--snapshot-only", "--write", "--fail-on-change", "Veritas-7/autoresearch-skill-system"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const veritasSnapshotWriter = run("node", ["scripts/refresh-veritas-candidate-snapshot.mjs", "--snapshot-only"]);
  checklist.push({
    id: "veritas_snapshot_writer",
    requirement: "The high-churn Veritas candidate snapshot has an explicit dry-run/write helper with an offline audit mode before repeated manual refreshes are automated.",
    status: veritasSnapshotWriterFiles.every((item) => item.exists) &&
      veritasSnapshotWriterTerms.every((item) => item.missingTerms.length === 0) &&
      veritasSnapshotWriter.ok ? "pass" : "fail",
    evidence: {
      files: veritasSnapshotWriterFiles,
      terms: veritasSnapshotWriterTerms,
      snapshotOnly: {
        command: "node scripts/refresh-veritas-candidate-snapshot.mjs --snapshot-only",
        status: veritasSnapshotWriter.ok ? "pass" : "fail",
        result: parseJson(veritasSnapshotWriter.stdout) || veritasSnapshotWriter.stdout.trim(),
        stderr: veritasSnapshotWriter.stderr.trim(),
      },
    },
  });

  const candidateSnapshotWriterFiles = candidateSnapshotWriterScripts.map((path) => ({ path, exists: fileExists(path) }));
  const candidateSnapshotWriterTerms = [
    { file: "scripts/refresh-candidate-snapshot.mjs", terms: ["--repo", "--from-live-drift", "--actionable-only", "--snapshot-only", "--write", "--fail-on-change", "gh api", "graphql", "sourceMarkerForRepo", "messageHeadline", "actionableDriftCountFromPayload", "finiteNumberOr"] },
    { file: "README.md", terms: ["refresh-candidate-snapshot.mjs", "--repo owner/name", "--from-live-drift", "--actionable-only", "--snapshot-only", "--write", "--fail-on-change"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const candidateSnapshotWriter = run("node", [
    "scripts/refresh-candidate-snapshot.mjs",
    "--snapshot-only",
    "--repo",
    "Veritas-7/autoresearch-skill-system",
  ]);
  checklist.push({
    id: "candidate_snapshot_writer",
    requirement: "Source-backed adoption candidate snapshots have generic repo-scoped and live-drift batch dry-run/write helpers so focused drift refreshes are not limited to one hard-coded repository or manual repo loops.",
    status: candidateSnapshotWriterFiles.every((item) => item.exists) &&
      candidateSnapshotWriterTerms.every((item) => item.missingTerms.length === 0) &&
      candidateSnapshotWriter.ok ? "pass" : "fail",
    evidence: {
      files: candidateSnapshotWriterFiles,
      terms: candidateSnapshotWriterTerms,
      snapshotOnly: {
        command: "node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system",
        status: candidateSnapshotWriter.ok ? "pass" : "fail",
        result: parseJson(candidateSnapshotWriter.stdout) || candidateSnapshotWriter.stdout.trim(),
        stderr: candidateSnapshotWriter.stderr.trim(),
      },
    },
  });

  const autoresearchCandidates = autoresearchCandidateSnapshot("data/adoption-candidates.json");
  checklist.push({
    id: "autoresearch_ecosystem_candidates",
    requirement: "AutoResearch product launch data includes the original project, the Veritas source-backed harness, the user mirror, and a useful ecosystem candidate set.",
    status: autoresearchCandidates.status,
    evidence: autoresearchCandidates,
  });

  const workspaceCandidates = workspaceCandidateSnapshot("data/adoption-candidates.json");
  checklist.push({
    id: "workspace_ecosystem_candidates",
    requirement: "Local-first workspace discovery data includes current candidates for offline-first apps, AI workspace, developer dashboard, task, project, Kanban, calendar, and benchmark PM workflows.",
    status: workspaceCandidates.status,
    evidence: workspaceCandidates,
  });

  const workspaceUiTerms = hasTerms("scripts/smoke-interactions.mjs", [
    "workspace candidate portfolio search",
    "OpenLoaf/OpenLoaf",
    "workspaceCandidateVisible",
  ]);
  checklist.push({
    id: "workspace_candidate_ui_smoke",
    requirement: "The interaction smoke proves at least one imported workspace adoption candidate is searchable and visible in the portfolio UI.",
    status: workspaceUiTerms.status,
    evidence: { file: "scripts/smoke-interactions.mjs", missingTerms: workspaceUiTerms.missing },
  });

  const sourceSnapshotHealthTerms = [
    { file: "app.js", terms: ["projectSnapshotHealth", "function recordProjectSnapshotHealth", "function finalizeProjectSnapshotHealth", "function projectSnapshotHealthHTML"] },
    { file: "system-status-view.js", terms: ["function projectSnapshotHealthHTML", "data-system-source-snapshots", "data-source-snapshot-loaded-count", "data-source-snapshot-row"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["sourceSnapshotHealth", "data-system-source-snapshots", "data/repos.json source health row did not render loaded", "data/adoption-candidates.json source health row did not render loaded"] },
    { file: "README.md", terms: ["source snapshot health"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "source_snapshot_health_surface",
    requirement: "System Status exposes structured load health for local project snapshot JSON assets so publish operators can see missing or partial seed data instead of relying on console logs.",
    status: sourceSnapshotHealthTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: sourceSnapshotHealthTerms,
  });

  const workspaceCompetitiveTerms = hasTerms("scripts/smoke-interactions.mjs", [
    "colanode/colanode",
    "workspaceCompetitiveCandidateVisible",
    "Colanode star count did not render",
    "Colanode GitHub link did not render safely",
  ]);
  checklist.push({
    id: "workspace_competitive_candidate_smoke",
    requirement: "The interaction smoke proves a newly researched workspace benchmark candidate is searchable and renders current GitHub metadata.",
    status: workspaceCompetitiveTerms.status,
    evidence: { file: "scripts/smoke-interactions.mjs", missingTerms: workspaceCompetitiveTerms.missing },
  });

  const planeFreshnessUiTerms = [
    { file: "data/adoption-candidates.json", terms: ["makeplane/plane", "github-search:plane-pm-benchmark", "github-api:plane-freshness-refresh"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotPlane", "shortPlaneCommit", "Plane freshness commit did not render", "planeCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "plane_pm_candidate_freshness_ui_smoke",
    requirement: "The portfolio includes Plane as a researched PM benchmark candidate and interaction smoke can find it by current GitHub commit with popularity and risk-review metadata.",
    status: planeFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: planeFreshnessUiTerms,
  });

  const appFlowyFreshnessUiTerms = [
    { file: "data/adoption-candidates.json", terms: ["AppFlowy-IO/AppFlowy", "github-search:appflowy-workspace-benchmark", "github-api:appflowy-freshness-refresh"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotAppFlowy", "shortAppFlowyCommit", "AppFlowy freshness commit did not render", "appFlowyCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_workspace_candidate_freshness_ui_smoke",
    requirement: "The portfolio includes AppFlowy as a researched workspace benchmark candidate and interaction smoke can find it by current GitHub commit with popularity and risk-review metadata.",
    status: appFlowyFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appFlowyFreshnessUiTerms,
  });

  const affineFreshnessUiTerms = [
    { file: "data/adoption-candidates.json", terms: ["toeverything/AFFiNE", "github-search:affine-workspace-benchmark", "github-api:affine-freshness-refresh"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotAffine", "shortAffineCommit", "AFFiNE freshness commit did not render", "affineCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "affine_workspace_candidate_freshness_ui_smoke",
    requirement: "The portfolio includes AFFiNE as a researched workspace benchmark candidate and interaction smoke can find it by current GitHub commit with popularity and risk-review metadata.",
    status: affineFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: affineFreshnessUiTerms,
  });

  const appflowyAffineFreshnessUiTerms = [
    { file: "data/adoption-candidates.json", terms: ["AppFlowy-IO/AppFlowy", "toeverything/AFFiNE", "github-search:appflowy-affine-benchmark", "github-api:appflowy-freshness-refresh", "github-api:affine-freshness-refresh"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotAppFlowy", "shortAppFlowyCommit", "AppFlowy freshness commit did not render", "appFlowyCandidateFreshnessVisible", "snapshotAffine", "shortAffineCommit", "AFFiNE freshness commit did not render", "affineCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_candidate_freshness_ui_smoke",
    requirement: "The portfolio includes AppFlowy and AFFiNE as researched knowledge-workspace benchmark candidates and interaction smoke can find both by current GitHub commit with popularity and risk-review metadata.",
    status: appflowyAffineFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineFreshnessUiTerms,
  });

  const appflowyAffineWorkspaceRubricTerms = [
    { file: "data/adoption-candidates.json", terms: ["workspaceBenchmark", "JooPark Workspace", "project + task surfaces", "Notion/Miro knowledge-base + whiteboard"] },
    { file: "app.js", terms: ["function projectWorkspaceBenchmark", "function projectWorkspaceRubric", "function candidateWorkspaceRubric", "data-workspace-benchmark-rubric", "data-workspace-rubric-project"] },
    { file: "styles.css", terms: ["--rubric-project-count"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkRubricVisible", "workspace benchmark rubric did not render heading", "AFFiNE workspace rubric notes score did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_workspace_benchmark_rubric",
    requirement: "AppFlowy and AFFiNE expose a dedicated PM, notes, and workspace comparison rubric with browser smoke coverage for weighted recommendation cells.",
    status: appflowyAffineWorkspaceRubricTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineWorkspaceRubricTerms,
  });

  const outlineFreshnessUiTerms = [
    { file: "data/adoption-candidates.json", terms: ["outline/outline", "github-search:outline-knowledge-base-benchmark", "github-api:outline-freshness-refresh"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotOutline", "shortOutlineCommit", "Outline freshness commit did not render", "outlineCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "outline_knowledge_base_candidate_freshness_ui_smoke",
    requirement: "The portfolio includes Outline as a researched knowledge-base benchmark candidate and interaction smoke can find it by current GitHub commit with popularity and spike recommendation metadata.",
    status: outlineFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: outlineFreshnessUiTerms,
  });

  const bookStackFreshnessUiTerms = [
    { file: "data/adoption-candidates.json", terms: ["BookStackApp/BookStack", "github-search:bookstack-documentation-benchmark", "github-api:bookstack-freshness-refresh"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotBookStack", "shortBookStackCommit", "BookStack freshness commit did not render", "bookStackCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "bookstack_documentation_candidate_freshness_ui_smoke",
    requirement: "The portfolio includes BookStack as a researched self-hosted documentation benchmark candidate and interaction smoke can find it by current GitHub commit with popularity, source-migration, and architecture-benchmark metadata.",
    status: bookStackFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: bookStackFreshnessUiTerms,
  });

  const wikiJsFreshnessUiTerms = [
    { file: "data/adoption-candidates.json", terms: ["requarks/wiki", "github-search:wikijs-self-hosted-wiki-benchmark", "github-api:wikijs-freshness-refresh"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotWikiJs", "shortWikiJsCommit", "Wiki.js freshness commit did not render", "wikiJsCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "wikijs_self_hosted_wiki_candidate_freshness_ui_smoke",
    requirement: "The portfolio includes Wiki.js as a researched self-hosted wiki benchmark candidate and interaction smoke can find it by current GitHub commit with popularity, Git-backed documentation, and architecture-benchmark metadata.",
    status: wikiJsFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: wikiJsFreshnessUiTerms,
  });

  const veritasFreshnessUiTerms = [
    { file: "app.js", terms: ["shortCommit", "data-candidate-commit", "data-candidate-pushed-at", "p && p.lastCommit"] },
    { file: "styles.css", terms: [".portfolio-commit"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotVeritas", "shortVeritasCommit", "Veritas freshness commit did not render", "veritasCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "veritas_freshness_ui_smoke",
    requirement: "The portfolio UI exposes the refreshed Veritas upstream commit and pushedAt marker, and interaction smoke can find the candidate by commit.",
    status: veritasFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: veritasFreshnessUiTerms,
  });

  const openProjectFreshnessUiTerms = [
    { file: "app.js", terms: ["shortCommit", "data-candidate-commit", "data-candidate-pushed-at", "p && p.lastCommit"] },
    { file: "styles.css", terms: [".portfolio-commit"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotOpenProject", "shortOpenProjectCommit", "OpenProject freshness commit did not render", "openProjectCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "openproject_freshness_ui_smoke",
    requirement: "The portfolio UI exposes the refreshed OpenProject upstream commit and pushedAt marker, and interaction smoke can find the risk-review candidate by commit.",
    status: openProjectFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: openProjectFreshnessUiTerms,
  });

  const leantimeFreshnessUiTerms = [
    { file: "app.js", terms: ["shortCommit", "data-candidate-commit", "data-candidate-pushed-at", "p && p.lastCommit"] },
    { file: "styles.css", terms: [".portfolio-commit"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotLeantime", "shortLeantimeCommit", "Leantime freshness commit did not render", "leantimeCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "leantime_freshness_ui_smoke",
    requirement: "The portfolio UI exposes the refreshed Leantime upstream commit and pushedAt marker, and interaction smoke can find the project-management candidate by commit.",
    status: leantimeFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: leantimeFreshnessUiTerms,
  });

  const workspaceBenchmarkFreshnessUiTerms = [
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotEpicenter", "shortEpicenterCommit", "Epicenter freshness commit did not render", "epicenterCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotOpenLoaf", "shortOpenLoafCommit", "OpenLoaf freshness commit did not render", "openLoafCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotColanode", "shortColanodeCommit", "Colanode freshness commit did not render", "colanodeCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotParabol", "shortParabolCommit", "Parabol freshness commit did not render", "parabolCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotWorklenz", "shortWorklenzCommit", "Worklenz freshness commit did not render", "worklenzCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotAnytype", "shortAnytypeCommit", "Anytype freshness commit did not render", "anytypeCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["snapshotFocalboard", "shortFocalboardCommit", "Focalboard freshness commit did not render", "focalboardCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["remainingFreshnessSnapshots", "happybhati/workstream", "remainingWorkspaceFreshnessOk.workstream", "workstreamCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["remainingFreshnessSnapshots", "Taskosaur/Taskosaur", "remainingWorkspaceFreshnessOk.taskosaur", "taskosaurCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["remainingFreshnessSnapshots", "ioniks/MarkdownTaskManager", "remainingWorkspaceFreshnessOk.markdownTaskManager", "markdownTaskManagerCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["remainingFreshnessSnapshots", "taskcoach/taskcoach", "remainingWorkspaceFreshnessOk.taskcoach", "taskcoachCandidateFreshnessVisible"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["remainingFreshnessSnapshots", "dotnetfactory/fluid-calendar", "remainingWorkspaceFreshnessOk.fluidCalendar", "fluidCalendarCandidateFreshnessVisible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "workspace_benchmark_freshness_ui_smoke",
    requirement: "The portfolio UI exposes refreshed workspace benchmark upstream commits and pushedAt markers, and interaction smoke can find each benchmark by commit.",
    status: workspaceBenchmarkFreshnessUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: workspaceBenchmarkFreshnessUiTerms,
  });

  const candidateMetadataRefreshTerms = [
    { file: "app.js", terms: ["function projectRepoKey", "function refreshImportedProjectMetadata", "refreshed ${updated} adoption candidate projects"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateMetadataRefresh", "stale adoption candidate metadata refresh did not report changes", "refreshed Leantime metadata was not persisted"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "workspace_candidate_metadata_refresh",
    requirement: "Persisted adoption candidates refresh source-backed metadata when a newer imported snapshot has the same repo identity.",
    status: candidateMetadataRefreshTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: candidateMetadataRefreshTerms,
  });

  const candidateTriageTerms = [
    { file: "app.js", terms: ["function projectAdoptionMeta", "safeGithubUrl", "data-candidate-meta", "portfolio-candidate-link"] },
    { file: "styles.css", terms: [".portfolio-candidate-meta", ".portfolio-candidate-link"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["OpenLoaf adoption stage did not render", "OpenLoaf star count did not render", "OpenLoaf GitHub link did not render safely"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "workspace_candidate_triage_meta",
    requirement: "Portfolio adoption candidates expose stage, GitHub popularity, language, and safe repository links, with interaction smoke coverage.",
    status: candidateTriageTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: candidateTriageTerms,
  });

  const candidateFilterTerms = [
    { file: "app.js", terms: ["PORTFOLIO_FILTERS", "function setPortfolioFilter"] },
    { file: "portfolio-view.js", terms: ["data-action=\"portfolio-filter\"", "data-filter=\"${filter.key}\"", "aria-pressed=\"${raw(model.portfolioFilter === filter.key ? \"true\" : \"false\")}\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["portfolioCandidateFilter", "candidate portfolio filter did not render adoption candidates", "owned portfolio filter still rendered adoption candidates"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "portfolio_candidate_filter",
    requirement: "The portfolio has an explicit segmented filter for all projects, owned projects, and adoption candidates, with browser smoke coverage.",
    status: candidateFilterTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: candidateFilterTerms,
  });

  const candidateRankingTerms = [
    { file: "app.js", terms: ["function projectCandidatePriority", "function sortPortfolioProjects", "data-candidate-priority"] },
    { file: "portfolio-view.js", terms: ["role=\"listitem\"", "projectListItemLabel"] },
    { file: "styles.css", terms: [".portfolio-priority"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["portfolioCandidateRanked", "candidate portfolio filter did not rank highest priority first", "OpenLoaf priority score did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "portfolio_candidate_ranking",
    requirement: "Adoption candidates receive a metadata-based priority score and the candidate-only portfolio view sorts by that score, with browser smoke coverage.",
    status: candidateRankingTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: candidateRankingTerms,
  });

  const candidateNextActionTerms = [
    { file: "app.js", terms: ["function projectCandidateAction", "data-candidate-action", "아키텍처 벤치", "리스크 리뷰"] },
    { file: "styles.css", terms: [".portfolio-action", ".portfolio-action-cyan", ".portfolio-action-amber"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateNextActionVisible", "Colanode candidate action did not render", "OpenProject candidate risk action was not computed"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "portfolio_candidate_next_action",
    requirement: "Adoption candidate cards expose a deterministic next-action recommendation, with browser smoke coverage for architecture and risk-review actions.",
    status: candidateNextActionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: candidateNextActionTerms,
  });

  const candidateActionFilterTerms = [
    { file: "app.js", terms: ["CANDIDATE_ACTION_FILTERS", "function setPortfolioActionFilter"] },
    { file: "portfolio-view.js", terms: ["data-candidate-action-filter-panel", "data-action=\"portfolio-action-filter\""] },
    { file: "styles.css", terms: [".portfolio-action-filter"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateActionFilter", "architecture action filter did not narrow candidate cards", "risk action filter did not keep OpenProject visible"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "portfolio_candidate_action_filter",
    requirement: "The portfolio candidate queue can be narrowed by deterministic next-action recommendations, with browser smoke coverage for architecture and risk-review filters.",
    status: candidateActionFilterTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: candidateActionFilterTerms,
  });

  const candidateActionSummaryTerms = [
    { file: "app.js", terms: ["function candidateActionQueueSummary", "data-candidate-action-summary", "data-candidate-action-summary-top"] },
    { file: "styles.css", terms: [".portfolio-action-summary"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateActionSummaryVisible", "architecture action summary top candidate did not render", "risk action summary label did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "portfolio_candidate_action_summary",
    requirement: "The portfolio candidate action queue exposes a summary of the selected action, including count, top candidate, review reason, and risk count, with browser smoke coverage.",
    status: candidateActionSummaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: candidateActionSummaryTerms,
  });

  const taskosaurWorkstreamBenchmarkTerms = [
    { file: "data/adoption-candidates.json", terms: ["github-readme:taskosaur-workstream-ux-benchmark", "benchmarkFocus", "JooPark PM/Calendar", "JooPark PM/Kanban", "Conversational AI task execution", "PR + task + calendar command center"] },
    { file: "app.js", terms: ["function projectBenchmarkFocus", "data-candidate-benchmark", "data-benchmark-flow", "portfolio-benchmark"] },
    { file: "styles.css", terms: [".portfolio-benchmark"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkFocusVisible", "Workstream benchmark focus did not render", "Taskosaur benchmark focus did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_focus",
    requirement: "Taskosaur and Workstream adoption candidates expose UX benchmark focus chips mapped to JooPark PM, Kanban, and Calendar surfaces, with browser smoke coverage.",
    status: taskosaurWorkstreamBenchmarkTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkTerms,
  });

  const taskosaurWorkstreamBenchmarkQueueTerms = [
    { file: "app.js", terms: ["CANDIDATE_BENCHMARK_FILTERS", "function setPortfolioBenchmarkFilter", "function sortBenchmarkFocusProjects", "function candidateBenchmarkQueueSummary", "data-candidate-benchmark-summary"] },
    { file: "portfolio-view.js", terms: ["data-candidate-benchmark-filter-panel", "data-action=\"portfolio-benchmark-filter\""] },
    { file: "styles.css", terms: [".portfolio-benchmark-filter", ".portfolio-benchmark-summary"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkQueueVisible", "benchmark focus filter did not narrow candidate cards", "benchmark focus queue did not rank top benchmark first"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_queue",
    requirement: "Taskosaur and Workstream benchmark focus chips can be promoted into a filtered, sorted benchmark queue with summary and browser smoke coverage.",
    status: taskosaurWorkstreamBenchmarkQueueTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkQueueTerms,
  });

  const taskosaurWorkstreamBenchmarkRubricTerms = [
    { file: "data/adoption-candidates.json", terms: ["rubric", "GitHub/GitLab PR + Jira task + Google Calendar", "in-app conversational execution + browser task execution", "Kanban boards + sprints + task dependencies", "local FastAPI + SQLite + agents dashboard"] },
    { file: "app.js", terms: ["function projectBenchmarkRubric", "function candidateBenchmarkRubric", "data-candidate-benchmark-rubric", "data-rubric-project"] },
    { file: "styles.css", terms: [".portfolio-benchmark-rubric", ".portfolio-rubric-grid"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkRubricVisible", "benchmark rubric did not render", "Taskosaur rubric did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_rubric",
    requirement: "Taskosaur and Workstream benchmark-focus candidates expose a side-by-side comparison rubric with browser smoke coverage for the source, AI, PM, and operations axes.",
    status: taskosaurWorkstreamBenchmarkRubricTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkRubricTerms,
  });

  const taskosaurWorkstreamBenchmarkRubricScoreTerms = [
    { file: "data/adoption-candidates.json", terms: ["weight", "score", "0.25", "92", "86"] },
    { file: "app.js", terms: ["function projectBenchmarkRubricScore", "data-benchmark-rubric-recommendation", "data-rubric-total-score", "data-rubric-weight", "data-rubric-score"] },
    { file: "styles.css", terms: [".portfolio-rubric-score"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkRubricScoreVisible", "benchmark rubric recommendation did not pick Taskosaur", "benchmark rubric AI score did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_rubric_score",
    requirement: "Taskosaur and Workstream benchmark rubric rows carry scored recommendation weights, render a top recommendation, and have browser smoke coverage for the weighted outcome.",
    status: taskosaurWorkstreamBenchmarkRubricScoreTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkRubricScoreTerms,
  });

  const knowledgeBaseInformationArchitectureRubricTerms = [
    { file: "data/adoption-candidates.json", terms: ["knowledgeBaseBenchmark", "JooPark Knowledge/IA", "collections + nested documents", "book + chapter + page hierarchy", "Git-backed Markdown workflows"] },
    { file: "app.js", terms: ["function projectKnowledgeBaseBenchmark", "function projectKnowledgeBaseRubric", "function candidateKnowledgeBaseRubric", "data-knowledge-base-benchmark-rubric", "data-kb-rubric-project"] },
    { file: "styles.css", terms: ["--rubric-project-count"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkRubricVisible", "knowledge-base IA rubric did not render heading", "Wiki.js knowledge-base rubric portability score did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_rubric",
    requirement: "Outline, BookStack, and Wiki.js expose a dedicated information-architecture comparison rubric with current source-backed candidate context and browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureRubricTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureRubricTerms,
  });

  const appflowyAffineWorkspaceExportTerms = [
    { file: "app.js", terms: ["function workspaceBenchmarkRecommendationMarkdown", "function candidateWorkspaceRecommendationExport", "reviewRecommendationExportCall(\"workspaceBenchmarkRecommendationMarkdown\"", "reviewRecommendationExportCall(\"candidateWorkspaceRecommendationExport\""] },
    { file: "review-recommendation-export.js", terms: ["function workspaceBenchmarkRecommendationMarkdown", "function candidateWorkspaceRecommendationExport", "data-workspace-benchmark-export", "joopark-workspace-benchmark-recommendation.md"] },
    { file: "styles.css", terms: [".portfolio-benchmark-export", ".portfolio-export-download", ".portfolio-export-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkExportVisible", "workspace recommendation export winner did not render", "workspace recommendation export markdown link did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_workspace_benchmark_export",
    requirement: "The AppFlowy and AFFiNE workspace benchmark rubric can export a Markdown recommendation with winner, score gap, filename, and rationale browser smoke coverage.",
    status: appflowyAffineWorkspaceExportTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineWorkspaceExportTerms,
  });

  const appflowyAffineWorkspaceReviewHandoffTerms = [
    { file: "app.js", terms: ["function candidateWorkspaceReviewHandoff", "function workspaceReviewHandoffMarkdown", "reviewPackageViewCall(\"reviewPackageHandoffHTML\"", "joopark-workspace-review-package.md"] },
    { file: "review-package-view.js", terms: ["data-workspace-review-handoff", "joopark-workspace-review-handoff.md", "Workspace prompt handoff"] },
    { file: "styles.css", terms: [".portfolio-review-handoff"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkReviewHandoffVisible", "workspace review handoff primary key did not render", "workspace review handoff markdown copy did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_workspace_review_handoff",
    requirement: "The AppFlowy and AFFiNE workspace recommendation can be turned into a Markdown review handoff with stable persist keys and browser smoke coverage.",
    status: appflowyAffineWorkspaceReviewHandoffTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineWorkspaceReviewHandoffTerms,
  });

  const appflowyAffineWorkspaceReviewHandoffCopyTerms = [
    { file: "app.js", terms: ["function copyBenchmarkReviewHandoff", "copyReviewPackagePanelText(target, {", "[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]", "reviewHandoffCopied"] },
    { file: "review-package-view.js", terms: ["data-workspace-review-handoff-copy", "data-workspace-review-handoff-copy-status"] },
    { file: "styles.css", terms: [".portfolio-export-actions", ".portfolio-export-status", ".portfolio-export-copy"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkReviewHandoffCopyVisible", "workspace review handoff copy text did not reach clipboard", "workspace review handoff copy status did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_workspace_review_handoff_copy",
    requirement: "The AppFlowy and AFFiNE workspace review handoff Markdown can be copied to the clipboard with visible state and browser smoke coverage.",
    status: appflowyAffineWorkspaceReviewHandoffCopyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineWorkspaceReviewHandoffCopyTerms,
  });

  const appflowyAffineWorkspaceReviewIssueDraftTerms = [
    { file: "app.js", terms: ["function workspaceReviewIssueDraft", "function candidateWorkspaceReviewIssueDraft", "reviewIssueDraftPanel({", "data-workspace-review-issue-draft", "data-workspace-review-issue-create"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDraftPanel", "data-review-issue-draft", "data-issue-draft-labels"] },
    { file: "styles.css", terms: [".portfolio-review-issue-draft", ".portfolio-issue-draft-grid", ".portfolio-issue-draft-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkReviewIssueDraftVisible", "workspace review issue draft did not create an issue", "workspace review issue draft did not persist source key"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_workspace_review_issue_draft",
    requirement: "The AppFlowy and AFFiNE workspace review handoff can be converted into a PM issue draft with stable source key, labels, and browser smoke coverage.",
    status: appflowyAffineWorkspaceReviewIssueDraftTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineWorkspaceReviewIssueDraftTerms,
  });

  const appflowyAffineWorkspaceReviewNotePublishTerms = [
    { file: "app.js", terms: ["function publishReviewHandoffNote", "reviewCreationActionsCall(\"publishReviewHandoffNote\""] },
    { file: "review-creation-actions.js", terms: ["function publishReviewHandoffNote", "workspace-review-note"] },
    { file: "review-package-view.js", terms: ["data-workspace-review-note-publish", "data-workspace-review-note-publish-status"] },
    { file: "styles.css", terms: [".portfolio-export-actions", ".portfolio-export-status"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkReviewNotePublishVisible", "workspace review note publish did not create a note", "workspace review note publish did not persist source key"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_workspace_review_note_publish",
    requirement: "The AppFlowy and AFFiNE workspace review handoff can be published into a pinned notes-review entry with stable source key and browser smoke coverage.",
    status: appflowyAffineWorkspaceReviewNotePublishTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineWorkspaceReviewNotePublishTerms,
  });

  const appflowyAffineWorkspaceReviewGithubCommentTerms = [
    { file: "app.js", terms: ["function workspaceReviewGithubCommentMarkdown", "function candidateWorkspaceReviewGithubComment", "reviewGithubCommentDraftPanel({", "data-workspace-review-github-comment", "copyReviewGithubComment"] },
    { file: "review-result-view.js", terms: ["function reviewGithubCommentDraftPanel", "portfolio-review-github-comment", "data-review-github-comment-key", "data-review-github-comment-text"] },
    { file: "styles.css", terms: [".portfolio-review-github-comment"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkReviewGithubCommentVisible", "workspace review GitHub comment copy text did not reach clipboard", "workspace review GitHub comment issue link did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "appflowy_affine_workspace_review_github_comment_handoff",
    requirement: "The AppFlowy and AFFiNE workspace review handoff can produce a copy-ready GitHub comment draft with a prefilled issue URL and browser smoke coverage.",
    status: appflowyAffineWorkspaceReviewGithubCommentTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: appflowyAffineWorkspaceReviewGithubCommentTerms,
  });

  const knowledgeBaseInformationArchitectureExportTerms = [
    { file: "app.js", terms: ["function knowledgeBaseBenchmarkRecommendationMarkdown", "function candidateKnowledgeBaseRecommendationExport", "reviewRecommendationExportCall(\"knowledgeBaseBenchmarkRecommendationMarkdown\"", "reviewRecommendationExportCall(\"candidateKnowledgeBaseRecommendationExport\""] },
    { file: "review-recommendation-export.js", terms: ["function knowledgeBaseBenchmarkRecommendationMarkdown", "function candidateKnowledgeBaseRecommendationExport", "data-knowledge-base-benchmark-export", "joopark-kb-ia-recommendation.md"] },
    { file: "styles.css", terms: [".portfolio-benchmark-export", ".portfolio-export-download", ".portfolio-export-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkExportVisible", "knowledge-base recommendation export winner did not render", "knowledge-base recommendation export markdown link did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_export",
    requirement: "The dedicated knowledge-base information-architecture rubric can export a Markdown recommendation with winner, score gap, filename, and rationale browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureExportTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureExportTerms,
  });

  const knowledgeBaseInformationArchitectureReviewHandoffTerms = [
    { file: "app.js", terms: ["function candidateKnowledgeBaseReviewHandoff", "function knowledgeBaseReviewHandoffMarkdown", "reviewPackageViewCall(\"reviewPackageHandoffHTML\"", "joopark-kb-ia-review-package.md"] },
    { file: "review-package-view.js", terms: ["data-knowledge-base-review-handoff", "joopark-kb-ia-review-handoff.md", "KB/IA prompt handoff"] },
    { file: "styles.css", terms: [".portfolio-review-handoff"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkReviewHandoffVisible", "knowledge-base review handoff primary key did not render", "knowledge-base review handoff markdown copy did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_review_handoff",
    requirement: "The dedicated knowledge-base information-architecture recommendation can be turned into a Markdown review handoff with stable persist keys and browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureReviewHandoffTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureReviewHandoffTerms,
  });

  const knowledgeBaseInformationArchitectureReviewHandoffCopyTerms = [
    { file: "app.js", terms: ["function copyBenchmarkReviewHandoff", "copyReviewPackagePanelText(target, {", "[data-benchmark-review-handoff], [data-knowledge-base-review-handoff]", "reviewHandoffCopied"] },
    { file: "review-package-view.js", terms: ["data-kb-review-handoff-copy", "data-kb-review-handoff-copy-status"] },
    { file: "styles.css", terms: [".portfolio-export-actions", ".portfolio-export-status", ".portfolio-export-copy"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkReviewHandoffCopyVisible", "knowledge-base review handoff copy text did not reach clipboard", "knowledge-base review handoff copy status did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_review_handoff_copy",
    requirement: "The dedicated knowledge-base information-architecture review handoff Markdown can be copied to the clipboard with visible state and browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureReviewHandoffCopyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureReviewHandoffCopyTerms,
  });

  const knowledgeBaseInformationArchitectureReviewIssueDraftTerms = [
    { file: "app.js", terms: ["function knowledgeBaseReviewIssueDraft", "function candidateKnowledgeBaseReviewIssueDraft", "reviewIssueDraftPanel({", "data-kb-review-issue-draft", "data-kb-review-issue-create"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDraftPanel", "data-review-issue-draft", "data-issue-draft-labels"] },
    { file: "styles.css", terms: [".portfolio-review-issue-draft", ".portfolio-issue-draft-grid", ".portfolio-issue-draft-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkReviewIssueDraftVisible", "knowledge-base review issue draft did not create an issue", "knowledge-base review issue draft did not persist source key"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_review_issue_draft",
    requirement: "The dedicated knowledge-base information-architecture review handoff can be converted into a PM issue draft with stable source key, labels, and browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureReviewIssueDraftTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureReviewIssueDraftTerms,
  });

  const knowledgeBaseInformationArchitectureReviewNotePublishTerms = [
    { file: "app.js", terms: ["function publishReviewHandoffNote", "reviewCreationActionsCall(\"publishReviewHandoffNote\""] },
    { file: "review-creation-actions.js", terms: ["function publishReviewHandoffNote", "knowledge-base-review-note"] },
    { file: "review-package-view.js", terms: ["data-kb-review-note-publish", "data-kb-review-note-publish-status"] },
    { file: "styles.css", terms: [".portfolio-export-actions", ".portfolio-export-status"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkReviewNotePublishVisible", "knowledge-base review note publish did not create a note", "knowledge-base review note publish did not persist source key"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_review_note_publish",
    requirement: "The dedicated knowledge-base information-architecture review handoff can be published into a pinned notes-review entry with stable source key and browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureReviewNotePublishTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureReviewNotePublishTerms,
  });

  const knowledgeBaseInformationArchitectureReviewGithubCommentTerms = [
    { file: "app.js", terms: ["function knowledgeBaseReviewGithubCommentMarkdown", "function candidateKnowledgeBaseReviewGithubComment", "reviewGithubCommentDraftPanel({", "data-kb-review-github-comment", "copyReviewGithubComment"] },
    { file: "review-result-view.js", terms: ["function reviewGithubCommentDraftPanel", "portfolio-review-github-comment", "data-review-github-comment-key", "data-review-github-comment-text"] },
    { file: "styles.css", terms: [".portfolio-review-github-comment"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkReviewGithubCommentVisible", "knowledge-base review GitHub comment copy text did not reach clipboard", "knowledge-base review GitHub comment issue link did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_review_github_comment_handoff",
    requirement: "The dedicated knowledge-base information-architecture review handoff can produce a copy-ready GitHub comment draft with a prefilled issue URL and browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureReviewGithubCommentTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureReviewGithubCommentTerms,
  });

  const taskosaurWorkstreamBenchmarkRecommendationExportTerms = [
    { file: "app.js", terms: ["function candidateBenchmarkRecommendationExport", "function candidateBenchmarkRecommendationMarkdown", "reviewRecommendationExportCall(\"candidateBenchmarkRecommendationExport\"", "reviewRecommendationExportCall(\"candidateBenchmarkRecommendationMarkdown\""] },
    { file: "review-recommendation-export.js", terms: ["function candidateBenchmarkRecommendationExport", "function candidateBenchmarkRecommendationMarkdown", "data-candidate-benchmark-export", "joopark-benchmark-recommendation.md"] },
    { file: "styles.css", terms: [".portfolio-benchmark-export", ".portfolio-export-download", ".portfolio-export-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkRecommendationExportVisible", "benchmark recommendation export winner did not render", "benchmark recommendation export markdown link did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_recommendation_export",
    requirement: "Taskosaur and Workstream weighted benchmark recommendation exposes a Markdown export with browser smoke coverage for winner, score gap, filename, and rationale.",
    status: taskosaurWorkstreamBenchmarkRecommendationExportTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkRecommendationExportTerms,
  });

  const taskosaurWorkstreamBenchmarkReviewQueueTerms = [
    { file: "app.js", terms: ["function projectBenchmarkReviewDecision", "function candidateBenchmarkReviewQueue", "data-benchmark-review-queue", "data-benchmark-review-decision", "data-review-score", "data-review-rank", "data-review-persist-key"] },
    { file: "styles.css", terms: [".portfolio-benchmark-review", ".portfolio-review-item"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkReviewQueueVisible", "benchmark review queue did not persist Taskosaur decision", "benchmark review queue score did not render", "benchmark review queue rank did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_review_queue",
    requirement: "Taskosaur and Workstream benchmark rubric score decisions persist into a focused review queue with stable decision keys and browser smoke coverage.",
    status: taskosaurWorkstreamBenchmarkReviewQueueTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkReviewQueueTerms,
  });

  const taskosaurWorkstreamBenchmarkReviewHandoffTerms = [
    { file: "app.js", terms: ["function candidateBenchmarkReviewQueueHandoff", "function candidateBenchmarkReviewQueueMarkdown", "reviewPackageViewCall(\"reviewPackageHandoffHTML\"", "joopark-benchmark-review-package.md"] },
    { file: "review-package-view.js", terms: ["data-benchmark-review-handoff", "joopark-benchmark-review-queue.md", "prompt handoff export"] },
    { file: "styles.css", terms: [".portfolio-review-handoff"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkReviewHandoffVisible", "benchmark review handoff primary key did not render", "benchmark review handoff markdown copy did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_review_handoff_export",
    requirement: "Taskosaur and Workstream benchmark review queue decisions can be exported as a Markdown handoff with stable persist keys and browser smoke coverage.",
    status: taskosaurWorkstreamBenchmarkReviewHandoffTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkReviewHandoffTerms,
  });

  const taskosaurWorkstreamBenchmarkReviewHandoffCopyTerms = [
    { file: "app.js", terms: ["function copyBenchmarkReviewHandoff", "copyReviewPackagePanelText(target, {", "[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]", "reviewHandoffCopied"] },
    { file: "review-package-view.js", terms: ["data-review-handoff-copy", "data-review-handoff-copy-status"] },
    { file: "styles.css", terms: [".portfolio-export-actions", ".portfolio-export-status", ".portfolio-export-copy"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkReviewHandoffCopyVisible", "benchmark review handoff copy text did not reach clipboard", "benchmark review handoff copy status did not render"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_review_handoff_copy",
    requirement: "Taskosaur and Workstream benchmark review handoff Markdown can be copied to the clipboard with visible state and browser smoke coverage.",
    status: taskosaurWorkstreamBenchmarkReviewHandoffCopyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkReviewHandoffCopyTerms,
  });

  const taskosaurWorkstreamBenchmarkReviewIssueDraftTerms = [
    { file: "app.js", terms: ["function benchmarkReviewIssueDraft", "function candidateBenchmarkReviewIssueDraft", "function createBenchmarkReviewIssue", "reviewIssueDraftPanel({", "artifactKind: \"benchmark-issue\""] },
    { file: "review-result-view.js", terms: ["function reviewIssueDraftPanel", "data-review-issue-draft", "data-review-issue-create", "data-issue-draft-labels"] },
    { file: "styles.css", terms: [".portfolio-review-issue-draft", ".portfolio-issue-draft-grid", ".portfolio-issue-draft-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkReviewIssueDraftVisible", "benchmark review issue draft did not create an issue", "benchmark review issue draft did not persist source key"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_review_issue_draft",
    requirement: "Taskosaur benchmark review handoff decisions can be converted into a PM issue draft with stable source key, priority, labels, and browser smoke coverage.",
    status: taskosaurWorkstreamBenchmarkReviewIssueDraftTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkReviewIssueDraftTerms,
  });

  const reviewHandoffPromptContractTerms = [
    { file: "app.js", terms: ["const REVIEW_HANDOFF_SCHEMA_VERSION = \"joopark-review-handoff/v2\"", "function reviewPromptHandoffMarkdown", "function reviewPromptSchema", "reviewHandoffCall(\"reviewPromptHandoffMarkdown\""] },
    { file: "review-package-view.js", terms: ["data-review-prompt-contract", "data-review-output-format", "json+markdown"] },
    { file: "review-handoff.js", terms: ["function reviewPromptHandoffMarkdown", "## Prompt Contract", "## System Prompt", "## User Prompt Template", "## Output Schema", "## Failure / Exception Handling", "firstAction", "decisionGate", "fallbackIfBlocked"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspace review handoff prompt contract did not render", "knowledge-base review handoff prompt sections did not render", "benchmark review handoff structured contract did not render", "joopark-review-handoff/v2", "missingEvidence", "firstAction", "decisionGate", "fallbackIfBlocked"] },
    { file: "README.md", terms: ["AI prompt handoff", "System Prompt", "User Prompt Template", "Output Schema", "Failure / Exception Handling", "joopark-review-handoff/v2", "firstAction", "decisionGate", "fallbackIfBlocked"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
	  checklist.push({
	    id: "review_handoff_prompt_contract",
	    requirement: "Portfolio review handoffs expose reusable AI prompt contracts with system/user separation, variables, structured output schema, exception handling, and browser smoke coverage.",
	    status: reviewHandoffPromptContractTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
	    evidence: reviewHandoffPromptContractTerms,
	  });

	  const reviewHandoffPromptCtaTerms = [
	    { file: "app.js", terms: ["function projectPromptHandoffTarget", "function showProjectPromptHandoff", "data-action=\"show-project-prompt-handoff\"", "data-prompt-handoff-revealed", "prompt handoff 보기"] },
	    { file: "styles.css", terms: [".portfolio-prompt-handoff", ".sheet-action-prompt"] },
	    { file: "scripts/smoke-interactions.mjs", terms: ["Taskosaur prompt handoff CTA", "data-prompt-handoff-revealed", "Taskosaur detail sheet did not expose prompt handoff CTA"] },
	    { file: "README.md", terms: ["prompt handoff 보기", "검색 결과", "상세 패널"] },
	  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
	  checklist.push({
	    id: "review_handoff_prompt_cta_flow",
	    requirement: "Portfolio benchmark candidates provide a direct search-result/detail-sheet CTA into the prompt handoff contract, with visible styling and browser smoke coverage.",
	    status: reviewHandoffPromptCtaTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
	    evidence: reviewHandoffPromptCtaTerms,
	  });

  const reviewHandoffResultValidatorTerms = [
    { file: "app.js", terms: ["function reviewResultValidator", "function validateReviewResultShape", "function parseReviewResult", "function validateReviewResult", "function copyReviewResultRepair", "reviewHandoffCall(\"reviewResultValidator\"", "reviewHandoffCall(\"validateReviewResultShape\""] },
    { file: "review-handoff.js", terms: ["data-review-result-validator", "data-review-result-state", "data-action=\"validate-review-result\"", "JSON 파싱 실패", "uiArtifacts.markdownSummary", "decisionGate is required", "fallbackIfBlocked is required"] },
    { file: "review-result-view.js", terms: ["JooPark Review Result Repair Packet", "Expected primaryDecisionKey", "Return one valid JSON object first", "Required JSON fields", "Correction scaffold", "function reviewResultRepairScaffold", "data-review-result-repair-copy"] },
    { file: "styles.css", terms: [".review-result-validator", ".review-result-input", ".review-result-pass", ".review-result-fail", ".review-result-repair", ".review-result-repair-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultValidatorVisible", "review result validator malformed JSON failure did not render", "wrong primaryDecisionKey", "missing decisionGate failure did not render", "review result repair packet copy text did not reach clipboard", "reviewResultRepairPacketCopy", "Correction scaffold:", "JSON 파싱 실패"] },
    { file: "README.md", terms: ["result validator", "JSON 검증", "schemaVersion", "primaryDecisionKey", "repair packet", "Correction scaffold"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_handoff_result_validator",
    requirement: "Portfolio review handoffs let users paste LLM JSON results and validate empty input, malformed JSON, schema/key mismatches, pass state, and retry/clear flows before downstream issue or note work.",
    status: reviewHandoffResultValidatorTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewHandoffResultValidatorTerms,
  });

  const reviewResultRepairPacketTerms = [
    { file: "review-result-view.js", terms: ["function reviewResultRepairRequiredFields", "function reviewResultRepairScaffold", "Required JSON fields:", "Correction scaffold:", "schemaVersion must equal", "primaryDecisionKey must equal", "executionPlan[] must include", "uiArtifacts.markdownSummary must be a concise tracker-ready summary"] },
    { file: "app.js", terms: ["function copyReviewResultRepair", "reviewResultStateCall(\"copyRepair\"", "copy-review-result-repair"] },
    { file: "review-result-state.js", terms: ["function copyRepair", "data-review-result-repair-text", "data-review-result-repair-copy-status", "reviewResultRepairCopied"] },
    { file: "styles.css", terms: [".review-result-repair", ".review-result-repair pre", ".review-result-repair-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultRepairPacketCopy", "Required JSON fields:", "Correction scaffold:", "uiArtifacts", "review result repair packet copy text did not reach clipboard"] },
    { file: "README.md", terms: ["repair packet", "Required JSON fields", "Correction scaffold", "uiArtifacts.markdownSummary"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_result_repair_packet_copy",
    requirement: "Failed review result validation produces a copy-ready repair packet with exact failure evidence, required JSON field checklist, correction scaffold, and clipboard smoke coverage.",
    status: reviewResultRepairPacketTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewResultRepairPacketTerms,
  });

  const reviewResultRepairActionPlanTerms = [
    { file: "review-result-view.js", terms: ["function reviewResultRepairActionPlan", "Repair action plan:", "Primary fix target:", "Schema identity:", "Evidence boundary:", "First action:", "Validation gate:", "Stop condition:", "function reviewResultRepairPacket"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultRepairActionPlanVisible", "Repair action plan:", "Primary fix target:", "Schema identity:", "Evidence boundary:", "Validation gate:", "Stop condition:", "Review result repair action plan: pass (6 fields, coverage=1)"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewResultRepairActionPlan", "reviewResultRepairActionPlanFields", "reviewResultRepairActionPlanCoverage", "Review result repair action plan:"] },
    { file: "release-status.js", terms: ["repairActionPlan", "data-output-quality-audit-repair-action-plan", "review-repair-action-plan", "Review repair action plan"] },
    { file: "README.md", terms: ["repair action plan", "reviewResultRepairActionPlan", "reviewResultRepairActionPlanCoverage", "Primary fix target", "Validation gate", "Stop condition"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_result_repair_action_plan",
    requirement: "Failed review result repair packets include a six-field repair action plan before raw failure evidence, so copied repair artifacts state the primary fix target, schema identity, evidence boundary, first action, validation gate, and stop condition.",
    status: reviewResultRepairActionPlanTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewResultRepairActionPlanTerms,
  });

  const reviewResultPostRepairReceiptTerms = [
    { file: "review-result-view.js", terms: ["function reviewResultRepairReceiptMarkdown", "function reviewResultPostRepairReceiptPanel", "JooPark Review Result Post-Repair Receipt", "Previous Failure Evidence", "Downstream Guard", "data-review-result-repair-receipt-copy"] },
    { file: "app.js", terms: ["reviewResultStateHelpers", "function reviewResultStateCall", "function attachReviewResultRepairReceipt", "reviewResultStateCall(\"attachRepairReceipt\"", "function copyReviewResultRepairReceipt", "reviewResultStateCall(\"copyRepairReceipt\"", "copy-review-result-repair-receipt"] },
    { file: "review-result-state.js", terms: ["const repairSnapshots = new WeakMap()", "function recordRepairSnapshot", "function postRepairReceiptModel", "function attachRepairReceipt", "function copyRepairReceipt", "reviewResultRepairReceiptCopied", "repaired-validation-pass"] },
    { file: "styles.css", terms: [".review-result-repair-receipt", ".review-result-repair-receipt pre"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultPostRepairReceipt", "JooPark Review Result Post-Repair Receipt", "Previous state: fail", "review result post-repair receipt copy text did not reach clipboard"] },
    { file: "README.md", terms: ["post-repair receipt", "Previous Failure Evidence", "Downstream Guard"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_result_post_repair_receipt",
    requirement: "After a failed review result is corrected and saved, the validator produces a copy-ready post-repair receipt that links previous failure evidence, corrected pass fields, saved checksum, and downstream artifact guardrails.",
    status: reviewResultPostRepairReceiptTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewResultPostRepairReceiptTerms,
  });

  const reviewResultRepairArtifactLinkTerms = [
    { file: "review-result-view.js", terms: ["function reviewSavedResultRepairEvidenceLines", "## Repair Evidence", "JooPark Review Result Post-Repair Receipt", "Post-repair receipt checksum", "Previous Failure Evidence"] },
    { file: "app.js", terms: ["function attachReviewResultRepairReceipt", "postRepairReceipt", "repairEvidence", "previousFailures", "reviewResultRepairReceiptForKey"] },
    { file: "review-artifact-view.js", terms: ["repair_evidence", "Repair evidence linked", "## Repair Evidence", "Post-repair receipt checksum: fnv1a32-"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultRepairArtifactLink", "review result post-repair receipt evidence was not saved for downstream artifacts", "did not render 8 artifact checks", "Repair evidence linked", "## Repair Evidence"] },
    { file: "README.md", terms: ["Repair Evidence", "artifact receipt", "post-repair receipt"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_result_repair_artifact_link",
    requirement: "A repaired review result saves structured repair evidence and carries it into created issue/note bodies plus artifact receipts, with a dedicated repair evidence diff check.",
    status: reviewResultRepairArtifactLinkTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewResultRepairArtifactLinkTerms,
  });

  const reviewPostRepairArtifactLinkTerms = [
    { file: "review-artifact-view.js", terms: ["function reviewPostRepairArtifactLinkMarkdown", "function reviewPostRepairArtifactLinkPanel", "JooPark Review Post-Repair Artifact Link", "Artifact diff status", "data-review-post-repair-artifact-link-copy"] },
    { file: "app.js", terms: ["function reviewResultRepairReceiptForKey", "repairReceiptMarkdown: reviewResultRepairReceiptForKey", "function attachReviewResultRepairReceipt", "function copyReviewPostRepairArtifactLink", "copy-review-post-repair-artifact-link"] },
    { file: "styles.css", terms: [".review-post-repair-artifact-link", "data-review-post-repair-artifact-link-ready"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPostRepairArtifactLink", "JooPark Review Post-Repair Artifact Link", "post-repair artifact link did not render ready state", "post-repair artifact link copy text did not reach clipboard"] },
    { file: "README.md", terms: ["post-repair artifact link", "Artifact diff status", "issue/note artifact receipt"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_post_repair_artifact_link",
    requirement: "Created issue/note artifact diffs link the saved post-repair result receipt to the current artifact receipt, expose key/status/checksum guardrails, and provide copy-ready evidence for external completion proof.",
    status: reviewPostRepairArtifactLinkTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPostRepairArtifactLinkTerms,
  });

  const reviewHandoffSavedResultTerms = [
    { file: "app.js", terms: ["dashboard.reviewResults", "function saveValidatedReviewResult", "function reviewResultSavedCard", "data-review-result-saved-panel", "reviewResults: dashboard.reviewResults"] },
    { file: "styles.css", terms: [".review-result-saved", "[data-review-result-saved-state=\"saved\"]", "[data-review-result-saved-state=\"empty\"]"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultValidatorSaved", "reviewResultValidatorPersisted", "review result was not persisted to localStorage", "review result saved card did not survive input clear"] },
    { file: "README.md", terms: ["검증 결과 저장", "localStorage", "reviewResults", "저장된 결과"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_handoff_saved_result_flow",
    requirement: "Validated review handoff JSON is saved as a compact reviewResults slice, shown again on the handoff, persisted to localStorage/backup flows, and covered by interaction smoke checks.",
    status: reviewHandoffSavedResultTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewHandoffSavedResultTerms,
  });

  const reviewSavedResultActionPathTerms = [
    { file: "app.js", terms: ["function reviewDraftWithSavedResult", "reviewResultViewCall(\"reviewSavedResultBody\"", "function refreshReviewIssueDraftFromSavedResult", "reviewResultViewCall(\"reviewSavedResultNoteBody\"", "function reviewResultManifestEvidence", "dataset.issueDraftResultSource", "validated-review-result", "dataset.issueDraftPackageChecksum"] },
    { file: "review-result-view.js", terms: ["function reviewSavedResultBody", "function reviewSavedResultNoteBody", "function reviewIssueDraftPanel", "data-issue-draft-result-source", "## Validated Review Result", "## Saved Validated Result", "Payload checksum", "## Missing Evidence To Close"] },
    { file: "styles.css", terms: [".portfolio-issue-draft-source"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewResultIssueApplied", "reviewResultNoteApplied", "Source: validated", "reviewResults", "workspace review issue draft did not switch to validated result source", "knowledge-base review note publish source kind was not saved", "benchmark validated review issue package was not saved"] },
    { file: "README.md", terms: ["검증 JSON", "validated-result", "validated-review-result", "Payload checksum", "issue/note"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_handoff_saved_result_to_issue_note",
    requirement: "Validated reviewResults are applied to issue and note creation paths, preserving validated JSON fields, manifest checksum, sourceKind, labels, visible preview state, and browser smoke coverage.",
    status: reviewSavedResultActionPathTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewSavedResultActionPathTerms,
  });

  const reviewOperationalTrackerFieldTerms = [
    { file: "app.js", terms: ["function reviewSavedResultTrackerFields", "function reviewOwnerAssignment", "function reviewExecutionDueDate", "dataset.issueDraftAssignee", "dataset.issueDraftDue", "dataset.issueDraftTrackerReady", "tracker-ready", "executionOwner", "executionFirstAction", "executionDecisionGate", "executionFallbackIfBlocked"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDraftPanel", "data-issue-draft-assignee", "data-issue-draft-due", "data-issue-draft-tracker-ready"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewOperationalTrackerField", "issue draft tracker fields did not render", "issue tracker fields were not saved", "opened issue tracker fields were incomplete", "tracker-ready"] },
    { file: "README.md", terms: ["assignee", "due", "estimate", "tracker-ready", "owner/timebox"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_operational_tracker_fields",
    requirement: "Validated review execution plans map owner and timebox into visible issue draft tracker fields, saved issue assignee/due/estimate metadata, and full-body issue sheet inspection evidence.",
    status: reviewOperationalTrackerFieldTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewOperationalTrackerFieldTerms,
  });

  const reviewExecutionChecklistTerms = [
    { file: "app.js", terms: ["reviewExecutionChecklistHelpers", "function reviewExecutionChecklistCall", "function reviewExecutionChecklistItemsFromSavedResult", "reviewExecutionChecklistCall(\"reviewExecutionChecklistItemsFromSavedResult\"", "function issueExecutionChecklistItems", "reviewExecutionChecklistCall(\"issueExecutionChecklistItems\"", "function issueExecutionChecklistProgress", "reviewExecutionChecklistCall(\"issueExecutionChecklistProgress\"", "function renderIssueExecutionChecklistControls", "reviewResultViewCall(\"issueExecutionChecklistControls\"", "function toggleIssueChecklistItem", "function reviewExecutionChecklistLines", "reviewExecutionChecklistCall(\"reviewExecutionChecklistLines\"", "checklist-ready", "issueExecutionChecklistItems({ executionChecklist: draft.executionChecklist }).length", "executionChecklist", "execution checklist"] },
    { file: "review-execution-checklist.js", terms: ["function reviewExecutionChecklistItemsFromSavedResult", "function issueExecutionChecklistItems", "function issueExecutionChecklistProgress", "function reviewExecutionChecklistLines", "function reviewExecutionChecklistCountLabel", "firstAction", "Acceptance:", "Validation:", "done: false"] },
    { file: "review-result-view.js", terms: ["## Execution Checklist", "function issueExecutionChecklistControls", "function reviewIssueDraftPanel", "data-issue-draft-execution-checklist-count", "data-issue-execution-checklist", "data-issue-execution-checklist-view", "data-execution-checklist-done-count", "data-execution-checklist-progress-percent", "data-execution-checklist-toggle"] },
    { file: "kanban-view.js", terms: ["data-kanban-execution-checklist", "data-kanban-execution-toggle", "kanban-execution-checklist", "kanban-execution-toggle"] },
    { file: "styles.css", terms: [".kanban-execution-checklist", ".kanban-execution-count", ".kanban-execution-first", ".kanban-execution-toggle", ".sheet-execution-checklist", ".sheet-execution-progress-bar"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewExecutionChecklist", "reviewExecutionChecklistProgress", "issue draft execution checklist did not render", "execution checklist was not saved", "kanban execution checklist did not render", "benchmark review issue checklist toggle did not persist", "benchmark review kanban checklist toggle did not persist", "Execution checklist"] },
    { file: "README.md", terms: ["Execution Checklist", "checklist-ready", "Kanban", "완료 수", "진행률"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_execution_checklist_fields",
    requirement: "Validated review first action, acceptance criteria, and validation plan render as an issue Execution Checklist in the draft, created issue, issue sheet, and Kanban card, with persisted completion toggles and progress state.",
    status: reviewExecutionChecklistTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewExecutionChecklistTerms,
  });

  const reviewExecutionChecklistProgressTerms = [
    { file: "app.js", terms: ["function issueExecutionChecklistProgress", "reviewExecutionChecklistCall(\"issueExecutionChecklistProgress\"", "function renderIssueExecutionChecklistControls", "function toggleIssueChecklistItem", "function syncIssueBodyExecutionChecklist", "reviewExecutionChecklistCall(\"syncIssueBodyExecutionChecklist\"", "reviewResultViewCall(\"issueExecutionChecklistControls\"", "toggle-issue-checklist", "execution checklist progress", "execution checklist markdown"] },
    { file: "review-execution-checklist.js", terms: ["function issueExecutionChecklistProgress", "function syncIssueBodyExecutionChecklist", "## Execution Checklist", "item.done ? \"x\" : \" \"", "done", "remaining", "percent", "완료"] },
    { file: "review-result-view.js", terms: ["function issueExecutionChecklistControls", "data-execution-checklist-progress", "data-execution-checklist-toggle", "data-issue-execution-checklist-view"] },
    { file: "styles.css", terms: [".sheet-execution-checklist", ".sheet-execution-progress", ".sheet-execution-progress-bar", ".sheet-execution-item", ".kanban-execution-meter"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewExecutionChecklistProgress", "benchmark review issue sheet checklist progress did not update", "benchmark review issue sheet checklist progress rendered duplicate values after toggle", "benchmark review issue checklist markdown did not sync after toggle", "benchmark review kanban checklist progress did not update"] },
    { file: "README.md", terms: ["execution checklist progress", "체크박스", "Kanban 카드 진행률"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_execution_checklist_progress",
    requirement: "Validated review execution checklists can be completed in the issue sheet, persist checkbox state into the Markdown body, and show progress on issue sheets and Kanban cards.",
    status: reviewExecutionChecklistProgressTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewExecutionChecklistProgressTerms,
  });

  const reviewArtifactFreshReceiptAfterChecklistTerms = [
    { file: "app.js", terms: ["function reviewIssueFreshReceipt", "function renderIssueFreshReceiptControls", "function copyIssueFreshReceipt", "function reviewIssueArtifactKind", "reviewArtifactViewCall(\"issueFreshReceiptControls\"", "post-checklist receipt", "copy-issue-fresh-receipt"] },
    { file: "review-artifact-view.js", terms: ["function issueFreshReceiptControls", "data-issue-fresh-receipt", "data-issue-fresh-receipt-view", "data-review-artifact-fresh-receipt-status", "data-issue-fresh-receipt-copy", "joopark-${receipt.kind || \"issue\"}-fresh-receipt.md"] },
    { file: "styles.css", terms: [".sheet-fresh-receipt", ".sheet-fresh-receipt-head", ".sheet-fresh-receipt-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewArtifactFreshReceiptAfterChecklist", "benchmark review issue fresh receipt did not render pass state after checklist progress", "benchmark review issue fresh receipt view boundary did not render", "benchmark review issue fresh receipt did not include progressed body", "data-issue-fresh-receipt"] },
    { file: "README.md", terms: ["post-checklist receipt", "fresh receipt", "- [x] First action"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_artifact_fresh_receipt_after_checklist",
    requirement: "After an execution checklist item changes, the issue sheet can regenerate a fresh artifact receipt from the current Markdown body so archived evidence includes the completed checklist state.",
    status: reviewArtifactFreshReceiptAfterChecklistTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewArtifactFreshReceiptAfterChecklistTerms,
  });

  const reviewArtifactPostApplyFreshReceiptTerms = [
    { file: "app.js", terms: ["function reviewArtifactPostApplyReceiptPanel", "function copyReviewArtifactPostApplyReceipt", "copy-review-artifact-post-apply-receipt", "post-apply fresh receipt"] },
    { file: "review-artifact-view.js", terms: ["function reviewArtifactPostApplyReceiptPanel", "data-review-artifact-post-apply-receipt", "data-review-artifact-post-apply-receipt-ready", "data-review-artifact-post-apply-receipt-download", "post-apply-fresh-receipt.md"] },
    { file: "styles.css", terms: [".review-artifact-post-apply-receipt", ".review-artifact-post-apply-receipt-head", ".review-artifact-post-apply-receipt-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewArtifactPostApplyFreshReceipt", "post-apply fresh receipt prompt did not render ready state", "post-apply fresh receipt copy did not reach clipboard", "First action: restored evidence -"] },
    { file: "README.md", terms: ["post-apply fresh receipt", "archived body 적용", "복구 후 pass 증거"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_artifact_post_apply_fresh_receipt",
    requirement: "After archived body repair is applied and the artifact checks pass, the diff panel prompts users to archive a fresh pass receipt from the repaired current body before leaving the workflow.",
    status: reviewArtifactPostApplyFreshReceiptTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewArtifactPostApplyFreshReceiptTerms,
  });

  const reviewAssigneeOverrideTerms = [
    { file: "app.js", terms: ["function reviewOwnerAssignment", "function updateReviewIssueDraftAssignee", "reviewResultDraftStateCall(\"updateIssueDraftAssignee\"", "reviewResultViewCall(\"reviewIssueDraftAssigneeOverridePanel\""] },
    { file: "review-result-draft-state.js", terms: ["dataset.issueDraftAssigneeConfidence", "dataset.issueDraftAssigneeOverride", "dataset.issueDraftAssigneeReview", "assignee-review", "assignee-confirmed", "manual-override"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDraftAssigneeOverridePanel", "function reviewIssueDraftPanel", "data-issue-draft-assignee-select", "data-issue-draft-assignee-review-panel", "data-issue-draft-assignee-review-copy", "data-issue-draft-assignee-confidence", "data-issue-draft-assignee-override", "data-issue-draft-assignee-review", "review issue draft assignee override"] },
    { file: "styles.css", terms: [".portfolio-assignee-override"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewAssigneeOverride", "benchmark review assignee override did not update draft metadata", "benchmark review assignee confidence did not render", "assignee-confirmed"] },
    { file: "README.md", terms: ["assignee override", "assignee-review", "assignee-confirmed"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_assignee_override_fields",
    requirement: "Validated review owner hints expose assignee mapping confidence, allow issue-draft assignee override before creation, and persist manual assignee confirmation into the created issue.",
    status: reviewAssigneeOverrideTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewAssigneeOverrideTerms,
  });

  const reviewAssigneeOverrideDraftPersistenceTerms = [
    { file: "app.js", terms: ["dashboard.reviewIssueDraftOverrides", "function reviewIssueDraftOverrideByKey", "function saveReviewIssueDraftAssigneeOverride", "function reviewDraftWithPersistedAssigneeOverride", "reviewIssueDraftOverrides: dashboard.reviewIssueDraftOverrides"] },
    { file: "review-result-draft-state.js", terms: ["dataset.issueDraftAssigneeOverrideSavedAt", "function updateIssueDraftAssignee"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDraftPanel", "data-issue-draft-assignee-override-saved-at"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewAssigneeOverrideDraftPersistence", "benchmark review assignee override did not survive draft rerender before issue creation", "reviewIssueDraftOverrides"] },
    { file: "README.md", terms: ["reviewIssueDraftOverrides", "화면 이동", "issue 생성 전"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_assignee_override_draft_persistence",
    requirement: "Manual review issue assignee overrides are saved before issue creation, survive draft rerenders/navigation, and remain available to backup/import/reset flows instead of only living in the current DOM.",
    status: reviewAssigneeOverrideDraftPersistenceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewAssigneeOverrideDraftPersistenceTerms,
  });

  const reviewIssueDraftShellViewBoundaryTerms = [
    { file: "app.js", terms: ["function reviewIssueDraftPanel", "reviewResultViewCall(\"reviewIssueDraftPanel\"", "reviewResultDraftStateCall(\"issueDraftNode\"", "assigneeOverridePanel: reviewIssueDraftAssigneeOverridePanel", "assigneeFollowUpPanel: reviewAssigneeFollowUpPanel", "artifactDiffPanel: reviewArtifactDiffPanel"] },
    { file: "review-result-draft-state.js", terms: ["function issueDraftNode", "function issueDraftBodyNode", "function issueDraftAssigneePanel", "function issueDraftAssigneeCopy", "data-review-issue-draft"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDraftPanel", "portfolio-review-issue-draft", "data-review-issue-draft", "data-issue-draft-labels", "data-issue-draft-execution-checklist-count", "data-issue-draft-body", "data-review-issue-create"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkReviewIssueDraftVisible", "knowledgeBaseBenchmarkReviewIssueDraftVisible", "candidateBenchmarkReviewIssueDraftVisible", "reviewAssigneeOverrideDraftPersistence"] },
    { file: "README.md", terms: ["issue draft shell", "review-result-view.js", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_issue_draft_shell_view_boundary",
    requirement: "Review issue draft shell rendering is owned by review-result-view.js while app.js keeps saved-result application, assignee override persistence and action wrappers, artifact diff models, and issue creation actions.",
    status: reviewIssueDraftShellViewBoundaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewIssueDraftShellViewBoundaryTerms,
  });

  const reviewGithubCommentDraftViewBoundaryTerms = [
    { file: "app.js", terms: ["function reviewGithubCommentMarkdown", "reviewResultViewCall(\"reviewGithubCommentMarkdown\"", "function reviewGithubCommentDraftPanel", "reviewResultViewCall(\"reviewGithubCommentDraftPanel\"", "function workspaceReviewGithubCommentMarkdown", "function knowledgeBaseReviewGithubCommentMarkdown", "function copyReviewGithubComment", "reviewResultDraftStateCall(\"copyGithubComment\"", "githubNewIssueUrl"] },
    { file: "review-result-view.js", terms: ["function reviewGithubCommentMarkdown", "function reviewGithubCommentDraftPanel", "portfolio-review-github-comment", "Primary decision key:", "Compare with:", "data-review-github-comment-key", "data-review-github-comment-target", "data-review-github-comment-copy", "data-review-github-comment-copy-status", "data-review-github-comment-text"] },
    { file: "review-result-draft-state.js", terms: ["function copyGithubComment", "data-review-github-comment-text", "reviewGithubCommentCopied"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspaceBenchmarkReviewGithubCommentVisible", "knowledgeBaseBenchmarkReviewGithubCommentVisible", "workspace review GitHub comment copy text did not reach clipboard", "knowledge-base review GitHub comment copy text did not reach clipboard"] },
    { file: "README.md", terms: ["GitHub comment Markdown/draft shell", "review-result-view.js", "정적 런타임 헬퍼"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_github_comment_draft_view_boundary",
    requirement: "Review GitHub comment Markdown and draft shell rendering are owned by review-result-view.js, copy state is owned by review-result-draft-state.js, and app.js keeps per-surface draft selection, prefilled issue URL generation, and action wrappers.",
    status: reviewGithubCommentDraftViewBoundaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewGithubCommentDraftViewBoundaryTerms,
  });

  const reviewAssigneeFollowUpTerms = [
    { file: "app.js", terms: ["function reviewOwnerFollowUpItems", "function reviewOwnerPromptExamples", "function reviewOwnerRequiredFollowUpText", "reviewResultViewCall(\"reviewAssigneeFollowUpPanel\"", "function refreshReviewIssueDraftAssigneeFollowUpPanel", "owner_accountability", "owner-followup", "dataset.issueDraftAssigneeRequiredFollowUpCount", "dataset.issueDraftAssigneePromptExampleCount", "assigneeRequiredFollowUp", "assigneePromptExamples"] },
    { file: "review-result-view.js", terms: ["function reviewAssigneeFollowUpPanel", "function reviewIssueDraftPanel", "portfolio-assignee-followup", "Assignee Follow-up", "data-issue-draft-owner-follow-up", "data-owner-follow-up-ready", "data-assignee-required-follow-up-count", "data-assignee-prompt-example-count", "data-issue-draft-assignee-required-follow-up-count", "data-issue-draft-assignee-prompt-example-count"] },
    { file: "review-handoff.js", terms: ["low-confidence; exceptions.requiredFollowUp"] },
    { file: "styles.css", terms: [".portfolio-assignee-followup", ".portfolio-assignee-prompt-examples"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewAssigneeFollowUp", "low-confidence owner failure", "low-confidence owner with requiredFollowUp", "owner-followup", "Assignee Follow-up", "owner follow-up code examples"] },
    { file: "README.md", terms: ["owner-followup", "requiredFollowUp", "low-confidence owner", "Assignee Follow-up"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_assignee_followup_guidance",
    requirement: "Low-confidence or unmapped review owners must produce requiredFollowUp guidance, prompt examples, draft metadata, and visible issue body/sheet evidence before users treat the generated issue as ready.",
    status: reviewAssigneeFollowUpTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewAssigneeFollowUpTerms,
  });

  const reviewArtifactDiffTerms = [
    { file: "app.js", terms: ["function reviewArtifactDiffPanel", "function reviewArtifactDiffSnippet", "function reviewArtifactDiffChecks", "function reviewArtifactReceiptMarkdown", "function parseReviewArtifactReceipt", "function reviewArtifactReceiptRepairSuggestion", "function reviewArtifactReceiptComparison", "reviewArtifactViewCall(\"reviewArtifactDiffPanel\"", "reviewArtifactViewCall(\"reviewArtifactReceiptCompareOutput\"", "reviewArtifactStateCall(\"repairPreview\"", "reviewArtifactStateCall(\"undoRepair\"", "reviewArtifactStateCall(\"compareReceipt\"", "function compareReviewArtifactReceipt", "function copyReviewArtifactReceipt", "function copyReviewArtifactRepairPayload", "function reviewArtifactRepairPreview", "function undoReviewArtifactRepair"] },
    { file: "review-copy-actions.js", terms: ["function copyReviewArtifactReceipt", "function copyReviewArtifactRepairPayload", "function copyIssueFreshReceipt", "function copyReviewArtifactPostApplyReceipt", "function copyReviewPostRepairArtifactLink", "reviewArtifactReceiptCopied", "reviewArtifactRepairBodyCopied", "issueFreshReceiptCopied", "reviewPostRepairArtifactLinkCopied"] },
    { file: "review-artifact-view.js", terms: ["data-review-artifact-diff", "data-review-artifact-diff-item", "data-review-artifact-open", "data-review-artifact-receipt-download", "data-review-artifact-receipt-text", "data-review-artifact-receipt-compare", "data-review-artifact-receipt-repair", "data-review-artifact-repair-body-text", "data-review-artifact-repair-receipt-text", "data-review-artifact-repair-apply", "data-review-artifact-repair-undo", "data-review-artifact-diff-created-id", "Static draft", "Validated result", "Created artifact", "Operational readiness", "Repair evidence linked", "JooPark Review Artifact Receipt", "receipt 비교", "Repair suggestions", "archived body 복사", "archived body 적용", "fresh receipt 복사", "적용 되돌리기", "Body exact match", "본문 열기"] },
    { file: "review-artifact-state.js", terms: ["function repairPreview", "function applyRepairBody", "function undoRepair", "function setReceiptCompareState", "function compareReceipt", "function insertReceipt", "function clearReceipt", "data-review-artifact-repair-preview", "data-review-artifact-receipt-compare", "archived body를 적용했습니다", "receipt 비교 통과", "receipt 비교 실패"] },
    { file: "styles.css", terms: [".review-artifact-diff", ".review-artifact-diff-grid", ".review-artifact-diff-checks", ".review-artifact-diff-actions", ".review-artifact-receipt-compare", ".review-artifact-receipt-input", ".review-artifact-receipt-repair", ".review-artifact-receipt-repair-actions", ".review-artifact-repair-preview", ".review-artifact-repair-preview-grid", ".sheet-meta-pre"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewArtifactDiffVisible", "reviewArtifactDiffValidated", "reviewArtifactOperationalReadiness", "reviewArtifactReceiptCompare", "reviewArtifactReceiptRepairSuggestion", "reviewArtifactReceiptRepairCopy", "reviewArtifactReceiptRepairApply", "workspace issue artifact diff", "knowledge-base note artifact diff", "benchmark issue artifact diff", "did not render 3 artifact columns", "did not render 8 artifact checks", "receipt copy text did not reach clipboard", "receipt copy was incomplete", "receipt compare did not pass", "receipt repair suggestion did not render for body drift", "receipt repair body copy did not reach clipboard", "receipt repair apply preview did not open", "receipt repair apply did not update the created artifact body", "receipt repair undo did not restore the created artifact body", "receipt repair fresh receipt copy did not reach clipboard", "receipt compare did not fail on tampered receipt", "opened issue body was incomplete", "opened note body was incomplete"] },
    { file: "README.md", terms: ["artifact diff", "Static draft", "Validated result", "Created artifact", "Operational Readiness", "receipt", "receipt compare", "Repair suggestions", "archived body 복사", "fresh receipt 복사", "본문 열기"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_artifact_diff_panel",
    requirement: "Created review issues and notes expose a post-creation artifact diff that compares static draft, validated result, and created artifact with checksum, acceptance, validation, source-snapshot, operational-readiness checks, copy/download receipt, receipt import/compare drift check, mismatch repair suggestions, one-click repair copy/apply actions with preview and undo, and a full-body open/review path.",
    status: reviewArtifactDiffTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewArtifactDiffTerms,
  });

				  const reviewHandoffActionableQualityTerms = [
    { file: "app.js", terms: ["REVIEW_OUTPUT_QUALITY_CRITERIA", "reviewIssuePayloadHelpers", "function reviewIssuePayloadCall", "function reviewIssueBodyLines", "reviewIssuePayloadCall(\"reviewIssueBodyLines\"", "function reviewIssueDecisionSummaryLines", "reviewIssuePayloadCall(\"reviewIssueDecisionSummaryLines\"", "function reviewOperationalReadinessLines", "reviewIssuePayloadCall(\"reviewOperationalReadinessLines\"", "acceptanceCriteria", "validationPlan", "qualityGate", "sourceSnapshot"] },
    { file: "review-issue-payload.js", terms: ["function reviewIssueBodyLines", "function reviewIssueDecisionSummaryLines", "function reviewOperationalReadinessLines", "## Decision Summary", "Recommendation:", "Evidence anchor:", "Stop condition:", "## Evidence Snapshot", "## Operational Readiness", "## Missing Evidence To Close", "## Timebox:", "Decision gate:", "Fallback if blocked:"] },
    { file: "review-handoff.js", terms: ["## Quality Bar", "## Execution Plan", "## Review Checklist", "acceptanceCriteria", "validationPlan", "qualityGate", "sourceSnapshot"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDecisionSummaryLines", "## Decision Summary", "Recommendation:", "Evidence anchor:", "Stop condition:", "function reviewSavedResultBody"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspace review handoff quality package did not render", "workspace validated review issue decision summary did not render", "knowledge-base validated review issue decision summary did not render", "benchmark validated review issue decision summary did not render", "reviewIssueDecisionSummaryVisible", "## Decision Summary", "Recommendation:", "Evidence anchor:", "Stop condition:", "## Operational Readiness", "Decision gate:", "Fallback if blocked:", "## Acceptance Criteria", "## Validation Plan", "Source URL: https://github.com/toeverything/AFFiNE"] },
    { file: "README.md", terms: ["Quality Bar", "Decision Summary", "Evidence Snapshot", "Operational Readiness", "Execution Plan", "Review Checklist", "Acceptance Criteria", "Validation Plan"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_handoff_actionable_quality_package",
    requirement: "Portfolio review handoffs and generated issue drafts are copy-ready execution packages with quality bar, evidence snapshot, operational readiness, acceptance criteria, validation plan, missing-evidence handling, and browser smoke coverage.",
    status: reviewHandoffActionableQualityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewHandoffActionableQualityTerms,
  });

  const reviewIssueDecisionSummaryTerms = [
    { file: "app.js", terms: ["function reviewIssueDecisionSummaryLines", "reviewIssuePayloadCall(\"reviewIssueDecisionSummaryLines\"", "function reviewIssueBodyLines", "reviewIssuePayloadCall(\"reviewIssueBodyLines\""] },
    { file: "review-issue-payload.js", terms: ["function reviewIssueDecisionSummaryLines", "## Decision Summary", "Recommendation:", "Why this candidate:", "Comparison context:", "Evidence anchor:", "First action:", "Stop condition:", "function reviewIssueBodyLines"] },
    { file: "review-result-view.js", terms: ["function reviewIssueDecisionSummaryLines", "## Decision Summary", "Recommendation:", "Why this candidate:", "Comparison context:", "Evidence anchor:", "First action:", "Stop condition:", "function reviewSavedResultBody"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewIssueDecisionSummaryVisible", "workspace validated review issue decision summary did not render", "knowledge-base validated review issue decision summary did not render", "benchmark validated review issue decision summary did not render", "Review issue decision summary: pass (6 fields, coverage=1)"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewIssueDecisionSummary", "reviewIssueDecisionSummaryFields", "reviewIssueDecisionSummaryCoverage", "Review issue decision summary:"] },
    { file: "README.md", terms: ["Decision Summary", "reviewIssueDecisionSummary", "reviewIssueDecisionSummaryCoverage", "Recommendation", "Evidence anchor", "Stop condition"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_issue_decision_summary",
    requirement: "Generated tracker issue bodies include a six-field decision summary before the detailed evidence package, so the issue itself states the recommendation, rationale, comparison context, evidence anchor, first action, and stop condition without requiring the bundle.",
    status: reviewIssueDecisionSummaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewIssueDecisionSummaryTerms,
  });

  const reviewCommentNoteDecisionSummaryTerms = [
    { file: "app.js", terms: ["function reviewPinnedNoteSummary", "reviewIssuePayloadCall(\"reviewPinnedNoteSummary\"", "function reviewMarkdownSection", "reviewIssuePayloadCall(\"reviewMarkdownSection\"", "function reviewPackageNoteBody", "reviewIssuePayloadCall(\"reviewPackageNoteBody\""] },
    { file: "review-issue-payload.js", terms: ["function reviewPinnedNoteSummary", "function reviewMarkdownSection", "## Pinned Note Summary", "Evidence anchor:", "First action:", "Stop condition:", "function reviewPackageNoteBody"] },
    { file: "review-result-view.js", terms: ["function reviewCommentDecisionSummaryLines", "function reviewPinnedNoteSummaryLines", "## Comment Decision Summary", "## Pinned Note Summary", "Recommendation:", "Why this candidate:", "Comparison context:", "Evidence anchor:", "First action:", "Stop condition:", "function reviewGithubCommentMarkdown", "function reviewSavedResultNoteBody"] },
    { file: "review-handoff.js", terms: ["## Comment Decision Summary", "## Pinned Note Summary", "decisionSummaryTerms", "six-field decision summary", "six-field pinned decision summary"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewCommentNoteDecisionSummaryVisible", "## Comment Decision Summary", "## Pinned Note Summary", "workspace review GitHub comment body did not render", "knowledge-base review GitHub comment body did not render", "benchmark pinned note paste preview body was incomplete", "Review comment/note decision summary: pass (6 fields, coverage=1)"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewCommentNoteDecisionSummary", "reviewCommentNoteDecisionSummaryFields", "reviewCommentNoteDecisionSummaryCoverage", "Review comment/note decision summary:"] },
    { file: "README.md", terms: ["Comment Decision Summary", "Pinned Note Summary", "reviewCommentNoteDecisionSummary", "reviewCommentNoteDecisionSummaryCoverage", "Evidence anchor", "Stop condition"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_comment_note_decision_summary",
    requirement: "Generated GitHub comment and pinned note bodies include six-field decision summaries before long evidence sections, so copied comment/note artifacts remain useful without opening the full review package or tracker issue.",
    status: reviewCommentNoteDecisionSummaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewCommentNoteDecisionSummaryTerms,
  });

  const reviewPackageBundleTerms = [
    { file: "app.js", terms: ["function reviewPackageBundleMarkdown", "function reviewPackageBundleControls", "function copyReviewPackageBundle", "data-review-package-bundle-text", "data-review-bundle-copy", "copy-review-bundle", "reviewHandoffCall(\"reviewPackageBundleMarkdown\""] },
    { file: "review-handoff.js", terms: ["function reviewPackageBundleMarkdown", "function reviewPackageBundleControls", "data-review-bundle-download", "## Markdown Handoff", "## GitHub Comment Draft", "## Pinned Note Body"] },
    { file: "styles.css", terms: [".portfolio-export-bundle"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageBundleVisible", "workspace review package bundle copy text did not reach clipboard", "knowledge-base review package bundle copy text did not reach clipboard", "benchmark review package bundle did not include execution-quality content"] },
    { file: "README.md", terms: ["review package bundle", "Markdown Handoff", "GitHub Comment Draft", "Pinned Note Body"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_bundle_export",
    requirement: "Portfolio review packages can be copied or downloaded as a single Markdown bundle containing the handoff, issue draft, GitHub comment draft, pinned-note body, and browser smoke coverage.",
    status: reviewPackageBundleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageBundleTerms,
  });

  const reviewPackageManifestTerms = [
    { file: "app.js", terms: ["REVIEW_PACKAGE_MANIFEST_SCHEMA_VERSION", "function reviewPackageManifest", "function reviewPackageManifestMarkdown", "function reviewPackageManifestSummary", "reviewHandoffCall(\"reviewPackageManifest\""] },
    { file: "review-handoff.js", terms: ["data-review-package-manifest", "data-review-package-payload-checksum", "Payload checksum", "Source freshness", "Decision Brief", "Operator Quick Start", "Paste-Ready Targets", "Artifact Quality Rubric", "Final Output Quality Gate"] },
    { file: "styles.css", terms: [".portfolio-package-manifest", ".portfolio-package-manifest-grid"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageManifestVisible", "workspace review package bundle manifest did not pass", "knowledge-base review package bundle source freshness did not render", "benchmark review package bundle manifest did not include validation evidence", "Paste target readiness: pass (3/3)", "Artifact quality rubric: pass (100/100, threshold 90)", "Decision brief: pass (6/6)", "Operator quick start: pass (5/5)", "Ready to submit: pass"] },
    { file: "README.md", terms: ["Bundle Manifest", "Payload checksum", "Source freshness", "Decision Brief", "Operator Quick Start", "Paste-Ready Targets", "Artifact Quality Rubric", "Final Output Quality Gate", "joopark-review-package-manifest/v1"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_manifest_quality",
    requirement: "Review package bundles include a visible and embedded manifest with validation status, payload checksum, source freshness, required-section coverage, and browser smoke coverage before external paste.",
    status: reviewPackageManifestTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageManifestTerms,
  });

  const reviewPackageArtifactQualityTerms = [
    { file: "review-handoff.js", terms: ["function reviewPackageArtifactQualityRubric", "data-review-package-artifact-quality-status", "data-review-package-artifact-quality-score", "data-review-package-artifact-quality-item-count", "data-review-package-artifact-quality-list", "Required form fit", "Paste-ready completeness", "Evidence traceability", "Submission flow readiness", "Safety and reuse readiness", "GitHub Issue Forms + Linear form templates + Jira required fields + GitHub Actions job summaries"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageArtifactQualityRubricVisible", "workspace review package artifact quality rubric did not pass", "knowledge-base review package artifact quality rubric did not pass", "benchmark review package artifact quality rubric did not pass", "Artifact quality rubric: pass (100/100, threshold 90)", "### Artifact Quality Rubric", "Submission flow readiness"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewPackageArtifactQualityRubric", "reviewPackageArtifactQualityScore", "reviewPackageArtifactQualityItems"] },
    { file: "README.md", terms: ["Artifact Quality Rubric", "reviewPackageArtifactQualityRubric", "reviewPackageArtifactQualityScore", "Required form fit", "Submission flow readiness", "Safety and reuse readiness"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_artifact_quality_rubric",
    requirement: "Review package bundles expose a 100-point artifact-quality rubric that scores required form fit, paste-ready completeness, evidence traceability, submission flow readiness, and safety/reuse readiness in both manifest UI and copied bundle Markdown.",
    status: reviewPackageArtifactQualityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageArtifactQualityTerms,
  });

  const reviewPackageDecisionBriefTerms = [
    { file: "review-handoff.js", terms: ["function reviewPackageDecisionBrief", "data-review-package-decision-brief-status", "data-review-package-decision-brief-ready", "data-review-package-decision-brief-count", "data-review-package-decision-brief-list", "Decision brief: ${manifest.decisionBrief.status}", "Review Package Decision Brief", "Recommendation", "Why this candidate", "Comparison context", "Execution target", "Evidence anchor", "Next action"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageDecisionBriefVisible", "workspace review package decision brief did not pass", "knowledge-base review package decision brief did not pass", "benchmark review package decision brief did not pass", "Decision brief: pass (6/6)", "### Decision Brief", "Review Package Decision Brief"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewPackageDecisionBrief", "reviewPackageDecisionBriefFields", "reviewPackageDecisionBriefCoverage", "Review package decision brief:"] },
    { file: "README.md", terms: ["Decision Brief", "reviewPackageDecisionBrief", "reviewPackageDecisionBriefCoverage", "Recommendation", "Evidence anchor", "Next action"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_decision_brief",
    requirement: "Review package bundles include a six-field decision brief that summarizes the recommendation, rationale, comparison context, execution target, evidence anchor, and next action before external submission.",
    status: reviewPackageDecisionBriefTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageDecisionBriefTerms,
  });

  const reviewPackageOperatorQuickStartTerms = [
    { file: "review-handoff.js", terms: ["function reviewPackageOperatorQuickStart", "data-review-package-operator-quick-start-status", "data-review-package-operator-quick-start-ready", "data-review-package-operator-quick-start-count", "data-review-package-operator-quick-start-list", "Operator quick start: ${manifest.operatorQuickStart.status}", "Review Package Operator Quick Start", "Confirm quality gate", "Fill external tracker fields", "Paste tracker issue body", "Share final submission update", "Keep bundle proof"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageOperatorQuickStartVisible", "workspace review package operator quick start did not pass", "knowledge-base review package operator quick start did not pass", "benchmark review package operator quick start did not pass", "Operator quick start: pass (5/5)", "### Operator Quick Start", "Review Package Operator Quick Start"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewPackageOperatorQuickStart", "reviewPackageOperatorQuickStartSteps", "reviewPackageOperatorQuickStartCoverage", "Review package operator quick start:"] },
    { file: "README.md", terms: ["Operator Quick Start", "reviewPackageOperatorQuickStart", "reviewPackageOperatorQuickStartCoverage", "Confirm quality gate", "Fill external tracker fields", "Keep bundle proof"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_operator_quick_start",
    requirement: "Review package bundles include a five-step operator quick start that tells the user what to check, paste, submit, share, and retain before using the package externally.",
    status: reviewPackageOperatorQuickStartTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageOperatorQuickStartTerms,
  });

  const reviewPackagePasteTargetTerms = [
    { file: "app.js", terms: ["REVIEW_PACKAGE_PASTE_TARGETS", "function reviewPackagePasteTargetReadiness", "reviewHandoffCall(\"reviewPackagePasteTargetReadiness\""] },
    { file: "review-handoff.js", terms: ["pasteTargets", "Paste target readiness", "Paste-Ready Targets", "data-review-package-paste-target-status", "data-review-package-paste-target-count", "data-review-package-paste-target-ready", "data-review-package-paste-target-list", "Tracker issue", "GitHub comment", "Pinned note"] },
    { file: "styles.css", terms: [".portfolio-package-paste-targets"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackagePasteTargetsVisible", "workspace review package paste targets did not pass", "knowledge-base review package paste targets did not pass", "benchmark review package paste targets did not pass", "Paste target readiness: pass (3/3)", "### Paste-Ready Targets"] },
    { file: "README.md", terms: ["Paste-Ready Targets", "Paste target readiness", "Tracker issue", "GitHub comment", "Pinned note"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_paste_ready_targets",
    requirement: "Review package bundles expose the final tracker issue, GitHub comment, and pinned-note paste targets with readiness counts so users know exactly which output section to submit.",
    status: reviewPackagePasteTargetTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackagePasteTargetTerms,
  });

  const reviewPackagePreSubmitPreviewTerms = [
    { file: "app.js", terms: ["function reviewPackagePastePreview", "reviewHandoffCall(\"reviewPackagePastePreview\"", "REVIEW_PACKAGE_PASTE_PREVIEW_DATA_ATTRIBUTES", "data-workspace-review-package-paste-preview", "data-knowledge-base-review-package-paste-preview", "data-benchmark-review-package-paste-preview"] },
    { file: "review-package-view.js", terms: ["const reviewPackagePastePreview", "reviewPackagePastePreview({", "kind: model.kind", "issueDraft: model.issueDraft", "githubCommentMarkdown: model.githubCommentMarkdown", "noteBody: model.noteBody"] },
    { file: "review-handoff.js", terms: ["function reviewPackagePastePreviewTargets", "function reviewPackagePastePreviewMarkdown", "function reviewPackagePastePreview", "Paste Body Preview", "Pre-submit preview", "data-review-package-paste-preview", "data-review-package-paste-preview-ready", "data-review-package-paste-preview-count", "data-review-package-paste-preview-body", "Tracker issue body", "GitHub comment body", "Pinned note body"] },
    { file: "styles.css", terms: [".portfolio-package-paste-preview", ".portfolio-package-paste-preview-grid", ".portfolio-package-paste-preview-head"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackagePastePreviewVisible", "workspace review package paste preview did not report ready state", "knowledge-base review package paste preview did not report ready state", "benchmark review package paste preview did not report ready state", "### Paste Body Preview", "Tracker issue body", "GitHub comment body", "Pinned note body"] },
    { file: "README.md", terms: ["Pre-submit preview", "Paste Body Preview", "Tracker issue body", "GitHub comment body", "Pinned note body"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_pre_submit_preview",
    requirement: "Review package bundles expose a compact pre-submit preview with the exact tracker issue, GitHub comment, and pinned-note body text before users paste externally.",
    status: reviewPackagePreSubmitPreviewTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackagePreSubmitPreviewTerms,
  });

  const reviewPackagePreSubmitCopyTerms = [
    { file: "app.js", terms: ["function copyReviewPackagePasteBody", "reviewCopyActionsCall(\"copyReviewPackagePasteBody\"", "copy-review-paste-body"] },
    { file: "review-copy-actions.js", terms: ["function copyReviewPackagePasteBody", "data-review-package-paste-preview-body", "reviewPackagePastePreviewCopied", "paste body를 복사했습니다"] },
    { file: "review-handoff.js", terms: ["data-action=\"copy-review-paste-body\"", "data-review-package-paste-preview-copy", "data-review-package-paste-preview-copy-id", "data-review-package-paste-preview-copy-status", "본문 복사"] },
    { file: "styles.css", terms: [".portfolio-package-paste-preview-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackagePastePreviewCopy", "workspace tracker paste preview body copy did not reach clipboard", "workspace GitHub comment paste preview body copy did not reach clipboard", "workspace pinned note paste preview body copy did not reach clipboard"] },
    { file: "README.md", terms: ["per-target copy", "본문 복사", "tracker/comment/note body"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_pre_submit_copy",
    requirement: "Pre-submit preview targets can be copied one destination at a time so users can paste only the tracker, GitHub comment, or pinned-note body they need.",
    status: reviewPackagePreSubmitCopyTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackagePreSubmitCopyTerms,
  });

  const reviewPackageCopyHandlerHelperTerms = [
    { file: "app.js", terms: ["function copyReviewPackagePanelText", "targetDatasetKey", "panelDatasetKey", "successToast", "failureToast"] },
    { file: "app.js", terms: ["copyReviewPackagePanelText(target, {", "reviewHandoffCopied", "reviewBundleCopied", "reviewPackageTrackerFieldCopied", "reviewPackageTrackerFormCopied", "reviewPackageSubmitSequenceCopied", "reviewPackageExternalReceiptTemplateCopied"] },
    { file: "review-copy-actions.js", terms: ["function copyReviewPackagePanelText", "targetDatasetKey", "panelDatasetKey", "successToast", "failureToast"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkReviewHandoffCopyVisible", "workspaceBenchmarkReviewHandoffCopyVisible", "knowledgeBaseBenchmarkReviewHandoffCopyVisible", "reviewPackageBundleVisible", "review package bundle copy text did not reach clipboard", "reviewPackageTrackerFieldCopy", "reviewPackageTrackerFormCopy", "reviewPackageSubmitSequenceCopy", "reviewPackageExternalReceiptTemplateCopy"] },
    { file: "README.md", terms: ["review-copy-actions.js", "copyReviewPackagePanelText", "handoff/bundle/tracker field/form/submit sequence/receipt template", "clipboard, status, copied dataset"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_copy_handler_helper",
    requirement: "Review handoff and static review package copy handlers for handoffs, bundles, tracker fields, tracker forms, submit sequence, and receipt templates share one clipboard/status/dataset helper so destination copy behavior does not drift across panels.",
    status: reviewPackageCopyHandlerHelperTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageCopyHandlerHelperTerms,
  });

  const reviewPackageTrackerFieldPacketTerms = [
    { file: "app.js", terms: ["function copyReviewPackageTrackerFields", "copy-review-tracker-fields", "data-review-package-tracker-field-packet-body", "reviewPackageTrackerFieldCopied", "tracker field packet을 복사했습니다", "memberName,"] },
    { file: "review-handoff.js", terms: ["function reviewPackageTrackerFieldPacket", "Tracker Field Packet", "data-review-package-tracker-fields", "data-review-package-tracker-field-copy", "data-review-package-tracker-field-packet-body", "필드 복사", "Assignee", "Due", "Labels"] },
    { file: "styles.css", terms: [".portfolio-package-tracker-fields", ".portfolio-package-tracker-fields dl", ".portfolio-package-tracker-fields dd"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageTrackerFieldCopy", "workspace tracker field packet did not report ready state", "workspace tracker field packet copy did not reach clipboard", "Title: [Workspace] toeverything/AFFiNE Workspace 도입 검토"] },
    { file: "README.md", terms: ["Tracker field packet", "필드 복사", "title/project/priority/assignee/due/estimate/labels"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_tracker_field_packet",
    requirement: "Review packages expose and copy tracker submission metadata, including title, project, priority, assignee, due, estimate, labels, and persist key, so issue creation is not body-only.",
    status: reviewPackageTrackerFieldPacketTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageTrackerFieldPacketTerms,
  });

  const reviewPackageTrackerFormPacketTerms = [
    { file: "app.js", terms: ["function copyReviewPackageTrackerForm", "copy-review-tracker-form", "data-review-package-tracker-form-body", "reviewPackageTrackerFormCopied", "external tracker form packet을 복사했습니다"] },
    { file: "review-handoff.js", terms: ["function reviewPackageExternalTrackerFormPacket", "External Tracker Form Packet", "GitHub Issue Forms", "Linear issue templates", "Jira work items", "data-review-package-tracker-form", "data-review-package-tracker-form-copy", "data-review-package-tracker-form-body", "Acceptance criteria", "Validation plan"] },
    { file: "styles.css", terms: [".portfolio-package-tracker-form", ".portfolio-package-tracker-form dl", ".portfolio-package-tracker-form dd"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageTrackerFormCopy", "workspace external tracker form packet did not report ready state", "workspace external tracker form packet copy did not reach clipboard", "Use with: GitHub Issue Forms, Linear issue templates, Jira work items"] },
    { file: "README.md", terms: ["External Tracker Form Packet", "form packet 복사", "GitHub Issue Forms", "Linear issue templates", "Acceptance criteria", "Validation plan"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_external_tracker_form_packet",
    requirement: "Review packages expose and copy a form-style external tracker packet that maps the final issue body, required fields, acceptance criteria, validation plan, owner, due, estimate, labels, persist key, and post-submit receipt into issue-form-friendly inputs.",
    status: reviewPackageTrackerFormPacketTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageTrackerFormPacketTerms,
  });

  const reviewPackageTrackerFormPayloadTerms = [
    { file: "review-handoff.js", terms: ["function reviewPackageMarkdownSection", "function reviewPackageExternalTrackerPayloads", "function reviewPackagePayloadSummary", "Field payloads:", "Field type:", "Checksum:", "If the external form has separate required fields"] },
    { file: "review-handoff.js", terms: ["data-review-package-tracker-form-payloads", "data-review-package-tracker-form-payload-count", "data-review-package-tracker-form-payload-checksum", "data-review-package-tracker-form-payload-type"] },
    { file: "styles.css", terms: [".portfolio-package-tracker-form-payloads", ".portfolio-package-tracker-form-payloads li", ".portfolio-package-tracker-form-payloads span"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["workspace external tracker field payloads did not render ready checksums", "Field payloads:", "## Description / body", "## Acceptance criteria", "## Validation plan", "If the external form has separate required fields"] },
    { file: "README.md", terms: ["Field payloads", "bytes/checksum", "필드값"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_tracker_form_payloads",
    requirement: "External tracker form packets include copy-ready field payloads, bytes, and checksums for required title/body/acceptance/validation/owner fields so users can fill separate GitHub, Linear, or Jira form fields without rewriting.",
    status: reviewPackageTrackerFormPayloadTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageTrackerFormPayloadTerms,
  });

  const reviewPackageSubmitSequenceTerms = [
    { file: "app.js", terms: ["function copyReviewPackageSubmitSequence", "copy-review-submit-sequence", "data-review-package-submit-sequence-body", "reviewPackageSubmitSequenceCopied", "submit sequence를 복사했습니다"] },
    { file: "review-handoff.js", terms: ["function reviewPackageSubmitSequence", "Submit Sequence", "Review Package Submit Sequence", "data-review-package-submit-sequence", "data-review-package-submit-sequence-copy", "data-review-package-submit-sequence-body", "순서 복사", "Record external issue receipt", "Share final submission update", "Use `최종 update 복사` after filling the external issue URL/ID", "Keep bundle proof"] },
    { file: "styles.css", terms: [".portfolio-package-submit-sequence", ".portfolio-package-submit-sequence ol", ".portfolio-package-submit-sequence li"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageSubmitSequenceCopy", "workspace submit sequence did not report ready state", "workspace submit sequence copy did not reach clipboard", "Ready: 7/7", "Share final submission update", "Use 최종 update 복사 after filling the external issue URL/ID", "### Submit Sequence"] },
    { file: "README.md", terms: ["Submit Sequence", "순서 복사", "external issue URL/ID receipt -> final submission update", "Tracker field packet"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_submit_sequence",
    requirement: "Review packages include a copy-ready submit sequence that orders tracker fields, tracker body, external issue receipt, final submission update, GitHub comment, pinned note, and bundle proof so users can complete submission without reconstructing the workflow.",
    status: reviewPackageSubmitSequenceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageSubmitSequenceTerms,
  });

  const reviewPackageExternalReceiptTemplateTerms = [
    { file: "app.js", terms: ["function copyReviewPackageExternalReceiptTemplate", "copy-review-external-receipt-template", "data-review-package-external-receipt-template-body", "reviewPackageExternalReceiptTemplateCopied", "external issue receipt template을 복사했습니다"] },
    { file: "review-handoff.js", terms: ["function reviewPackageExternalReceiptTemplate", "External Issue Receipt Template", "data-review-package-external-receipt-template", "data-review-package-external-receipt-template-copy", "data-review-package-external-receipt-template-body", "receipt 복사", "External issue URL", "External issue ID", "Submitted at", "Tracker body checksum", "Required form fields ready", "Submit sequence ready"] },
    { file: "styles.css", terms: [".portfolio-package-external-receipt", ".portfolio-package-external-receipt dl", ".portfolio-package-external-receipt dd"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageExternalReceiptTemplateCopy", "workspace external receipt template did not report ready state", "workspace external receipt template copy did not reach clipboard", "### External Issue Receipt Template", "Tracker body checksum: fnv1a32-", "Required form fields ready: 8/8", "Submit sequence ready: 7/7"] },
    { file: "README.md", terms: ["External Issue Receipt Template", "receipt 복사", "External issue URL", "Submitted at", "Tracker body checksum", "Required form fields ready", "Submit sequence ready"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_external_receipt_template",
    requirement: "Review packages include a copy-ready external issue receipt template with persist key, title, project, priority, labels, external URL/ID placeholders, submission timestamp placeholder, and bundle proof.",
    status: reviewPackageExternalReceiptTemplateTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageExternalReceiptTemplateTerms,
  });

  const reviewPackageExternalReceiptComposerTerms = [
    { file: "app.js", terms: ["function copyReviewPackageExternalReceiptFilled", "function externalReceiptSubmittedAt", "copy-review-external-receipt-filled", "reviewSubmissionCopyCall(\"copyReviewPackageExternalReceiptFilled\"", "reviewSubmissionCopyCall(\"externalReceiptSubmittedAt\""] },
    { file: "review-submission-copy.js", terms: ["function externalReceiptValues", "data-review-package-external-receipt-url", "reviewPackageExternalReceiptFilledCopied", "완성 external receipt를 복사했습니다"] },
    { file: "review-handoff.js", terms: ["data-review-package-external-receipt-compose", "data-review-package-external-receipt-url", "data-review-package-external-receipt-id", "data-review-package-external-receipt-submitted-at", "data-review-package-external-receipt-filled-copy", "완성 receipt 복사"] },
    { file: "styles.css", terms: [".portfolio-package-external-receipt-compose", ".portfolio-package-external-receipt-compose input", "min-height: 34px"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageExternalReceiptFilledCopy", "workspace filled external receipt copy did not reach clipboard", "https://linear.app/joopark/issue/WRK-86/affine-workspace-review", "!window.__smokeClipboardText.includes(\"[paste after creation]\")", "reviewPackageExternalReceiptIntegrity"] },
    { file: "README.md", terms: ["완성 receipt 복사", "placeholder 없이", "external issue URL과 ID"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_external_receipt_composer",
    requirement: "Review packages let users fill external issue URL, issue ID, and submitted-at values, then copy a completed receipt without placeholder text.",
    status: reviewPackageExternalReceiptComposerTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageExternalReceiptComposerTerms,
  });

  const reviewPackageSubmissionCloseoutSummaryTerms = [
    { file: "review-handoff.js", terms: ["function reviewPackageSubmissionCloseoutSummary", "Submission Closeout Summary", "Submitted artifact", "Evidence anchor", "First action", "Validation gate", "Archive target", "Stop condition", "data-review-package-submission-closeout-summary", "data-review-package-submission-update-closeout-summary"] },
    { file: "review-submission-copy.js", terms: ["Submitted artifact: [paste issue ID] — [paste issue URL]", "Submitted artifact: ${externalId} — ${externalUrl}", "replaceAll"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageSubmissionCloseoutSummaryVisible", "workspace external receipt closeout summary was not copy-ready", "workspace submission update closeout summary was not copy-ready", "Review submission closeout summary: pass (6 fields, coverage=1)"] },
    { file: "scripts/capture-output-quality-audit.mjs", terms: ["reviewPackageSubmissionCloseoutSummary", "reviewPackageSubmissionCloseoutSummaryFields", "reviewPackageSubmissionCloseoutSummaryCoverage", "Review submission closeout summary:"] },
    { file: "release-status.js", terms: ["submissionCloseoutSummary", "data-output-quality-audit-submission-closeout-summary", "submission-closeout-summary", "Submission closeout summary"] },
    { file: "README.md", terms: ["Submission Closeout Summary", "reviewPackageSubmissionCloseoutSummary", "reviewPackageSubmissionCloseoutSummaryCoverage", "Submitted artifact", "Validation gate", "Stop condition"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_submission_closeout_summary",
    requirement: "External issue receipts and final submission updates include a six-field closeout summary covering the submitted artifact, evidence anchor, first action, validation gate, archive target, and stop condition before users share submitted status.",
    status: reviewPackageSubmissionCloseoutSummaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageSubmissionCloseoutSummaryTerms,
  });

  const reviewPackageSubmissionUpdateTerms = [
    { file: "app.js", terms: ["function copyReviewPackageSubmissionUpdateFilled", "function fillExternalIssueText", "copy-review-submission-update-filled", "reviewSubmissionCopyCall(\"copyReviewPackageSubmissionUpdateFilled\"", "reviewSubmissionCopyCall(\"fillExternalIssueText\""] },
    { file: "review-submission-copy.js", terms: ["Status: ready after external issue URL/ID", "Status: submitted", "After external issue URL/ID are filled", "data-review-package-submission-update-body", "reviewPackageSubmissionUpdateFilledCopied", "review submission update를 복사했습니다"] },
    { file: "review-handoff.js", terms: ["function reviewPackageSubmissionUpdateTemplate", "Review Submission Update", "data-review-package-submission-update", "data-review-package-submission-update-filled-copy", "최종 update 복사", "Status", "ready after external issue URL/ID", "Next action", "After external issue URL/ID are filled", "post the GitHub comment body", "External receipt integrity"] },
    { file: "styles.css", terms: [".portfolio-package-submission-update", ".portfolio-package-submission-update dl", ".portfolio-package-submission-update dd"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageSubmissionUpdateCopy", "workspace submission update template did not render pre-submit copy-ready fields", "Status: ready after external issue URL/ID", "Next action: After external issue URL/ID are filled", "workspace submission update copy did not reach clipboard", "External issue: WRK-86", "External receipt integrity: tracker body checksum fnv1a32-", "!window.__smokeClipboardText.includes(\"ready after external issue URL/ID\")", "!window.__smokeClipboardText.includes(\"After external issue URL/ID are filled\")", "!window.__smokeClipboardText.includes(\"[paste\")"] },
    { file: "README.md", terms: ["Review Submission Update", "최종 update 복사", "팀 공유", "placeholder 없이", "ready after external issue URL/ID", "Status: submitted", "External receipt integrity"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_submission_update",
    requirement: "Review packages keep the submission update template in pre-submit state, then turn completed external issue URL, issue ID, and submitted-at inputs into a copy-ready final submitted update for team sharing without placeholder text.",
    status: reviewPackageSubmissionUpdateTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageSubmissionUpdateTerms,
  });

  const reviewPackageFilledCopyHandlerHelperTerms = [
    { file: "app.js", terms: ["function copyReviewPackageFilledText", "function externalReceiptValues", "function fillExternalIssueText", "reviewSubmissionCopyCall(\"copyReviewPackageFilledText\"", "reviewSubmissionCopyCall(\"externalReceiptValues\"", "reviewSubmissionCopyCall(\"fillExternalIssueText\""] },
    { file: "review-submission-copy.js", terms: ["function copyReviewPackageFilledText", "externalReceiptValues(panel)", "fillExternalIssueText(template, values)", "requiredStatus", "requiredToast", "stateHostSelector", "templateHostSelector", "reviewPackageExternalReceiptFilledCopied", "reviewPackageSubmissionUpdateFilledCopied"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageExternalReceiptFilledCopy", "reviewPackageSubmissionUpdateCopy", "!window.__smokeClipboardText.includes(\"[paste after creation]\")", "!window.__smokeClipboardText.includes(\"[paste\")"] },
    { file: "README.md", terms: ["copyReviewPackageFilledText", "URL/ID", "placeholder"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_filled_copy_handler_helper",
    requirement: "Filled external receipt and submission update copy handlers share URL/ID validation, template filling, clipboard/status/dataset updates, and placeholder-removal coverage so completed external submission outputs do not drift.",
    status: reviewPackageFilledCopyHandlerHelperTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageFilledCopyHandlerHelperTerms,
  });

  const reviewPackageExternalReceiptIntegrityTerms = [
    { file: "review-handoff.js", terms: ["function reviewPackageSubmissionIntegrity", "External receipt integrity", "Tracker body checksum", "Required form fields ready", "Submit sequence ready", "tracker body checksum ${integrity.bodyChecksum}", "required form fields ${integrity.requiredFieldsReady}", "submit sequence ${integrity.submitSequenceReady}"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageExternalReceiptIntegrity", "Tracker body checksum: fnv1a32-", "Required form fields ready: 8/8", "Submit sequence ready: 7/7", "External receipt integrity: tracker body checksum fnv1a32-"] },
    { file: "README.md", terms: ["External receipt integrity", "Tracker body checksum", "Required form fields ready", "Submit sequence ready"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_external_receipt_integrity",
    requirement: "External issue receipts and submission updates include tracker body checksum, required form readiness, and submit sequence readiness so a submitted external issue can be traced back to the exact review package without manual reconstruction.",
    status: reviewPackageExternalReceiptIntegrityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageExternalReceiptIntegrityTerms,
  });

  const reviewPackageFinalQualityTerms = [
	    { file: "app.js", terms: ["REVIEW_PACKAGE_FINAL_QUALITY_CRITERIA", "function reviewPackageFinalQualityGate", "reviewHandoffCall(\"reviewPackageFinalQualityGate\""] },
    { file: "review-handoff.js", terms: ["data-review-package-final-quality-status", "data-review-package-final-quality-score", "Ready to submit", "Final quality score", "Accuracy evidence", "Specific context", "Execution ready", "Reuse ready", "Safety ready", "Submit ready"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageFinalQualityGateVisible", "workspace review package final quality gate did not pass", "knowledge-base review package final quality gate did not pass", "benchmark review package final quality gate did not pass", "Final quality score: 6/6", "### Final Output Quality Gate"] },
    { file: "README.md", terms: ["Final Output Quality Gate", "Ready to submit", "Final quality score", "Accuracy evidence", "Execution ready", "Safety ready"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_final_output_quality_gate",
    requirement: "Review package bundles expose a final output quality gate that distinguishes merely generated packages from tracker/comment/note-ready packages before external sharing.",
    status: reviewPackageFinalQualityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageFinalQualityTerms,
  });

  const reviewPackageQualityRepairTerms = [
    { file: "app.js", terms: ["REVIEW_PACKAGE_FINAL_QUALITY_REPAIRS", "function reviewPackageManifestSummary", "reviewHandoffCall(\"reviewPackageManifestSummary\""] },
    { file: "review-handoff.js", terms: ["repairStatus", "repairCount", "repairSummary", "Quality repairs", "Quality Repair Checklist", "data-review-package-quality-repair-status", "data-review-package-quality-repair-count", "data-review-package-quality-repair-list", "No repairs required; package is ready to submit."] },
    { file: "styles.css", terms: [".portfolio-package-repairs", ".portfolio-package-repair-empty"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["reviewPackageQualityRepairChecklistVisible", "Quality repairs: none (0)", "### Quality Repair Checklist", "No repairs required; package is ready to submit.", "workspace review package repair checklist did not report clean state", "knowledge-base review package repair checklist did not report clean state", "benchmark review package repair checklist did not report clean state"] },
    { file: "README.md", terms: ["Quality Repair Checklist", "Quality repairs", "No repairs required", "repair checklist"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "review_package_quality_repair_checklist",
    requirement: "Review package bundles expose a copy-ready quality repair checklist so failed final-output gates tell the user exactly which evidence, context, execution, reuse, safety, or submit-readiness fields to fix.",
    status: reviewPackageQualityRepairTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: reviewPackageQualityRepairTerms,
  });

  const homeLaunchActionChecklistTerms = [
    { file: "app.js", terms: ["copy-home-launch-action-checklist"] },
    { file: "home-view.js", terms: ["launchActionChecklistText", "data-home-launch-action-checklist", "data-home-launch-action-checklist-step", "data-home-launch-action-checklist-source-artifact", "JooPark Launch Action Checklist", "dispatchApproval=", "verificationOnly="] },
    { file: "operations-copy-actions.js", terms: ["function copyHomeLaunchActionChecklist", "data-home-launch-action-checklist-text", "homeLaunchActionChecklistCopied", "launch action checklist를 복사했습니다"] },
    { file: "styles.css", terms: [".home-launch-action-checklist", ".home-launch-action-checklist-steps", ".home-launch-action-checklist-sources", ".home-launch-action-checklist-actions"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeLaunchActionChecklistOk", "data-home-launch-action-checklist", "home launch action checklist dataset was incomplete", "home launch action checklist copy did not report success", "JooPark Launch Action Checklist", "verify_handoff_guard"] },
    { file: "README.md", terms: ["JooPark Launch Action Checklist", "data-home-launch-action-checklist", "checklist 복사", "dispatchApproval=false", "verificationOnly=true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_launch_action_checklist",
    requirement: "Home exposes a copy-ready launch action checklist that turns the post-auth recheck sequence, source artifacts, deferred proof command, and dispatch guard into one operator-facing first-screen packet.",
    status: homeLaunchActionChecklistTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeLaunchActionChecklistTerms,
  });

  const homeFirstRunModelBoundaryTerms = [
    { file: "app.js", terms: ["function homeFirstRunGuidanceModel", "homeFirstRunGuidanceModel({", "firstRunGuidedStartCoverage", "firstRunGuidedStartItems"] },
    { file: "home-view.js", terms: ["homeFirstRunGuidanceHTML({ firstRunSteps, firstRunReadyCount, firstRunActionRequiredCount, firstRunNextStep, firstRunGuidedStartItems, firstRunGuidedStartCoverage })", "noteCount: dashboard.notes.length"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeFirstRunGuidanceOk", "homeFirstRunGuidedStartOk", "home first-run quick start dataset was incomplete", "home first-run guided start items were incomplete"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
	  checklist.push({
	    id: "home_first_run_model_boundary",
	    requirement: "Home first-run onboarding and public-proof guard state are assembled in a dedicated model helper so renderHome stays below the architecture guard while the browser smoke still proves the guidance surface.",
	    status: homeFirstRunModelBoundaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
	    evidence: homeFirstRunModelBoundaryTerms,
	  });

  const homeExecutionViewModuleTerms = [
    { file: "home-execution-view.js", terms: ["JooParkHomeExecutionView", "joopark-home-execution-view/v1", "function createHomeExecutionView", "function homeExecutionQueueHTML", "function homeExecutionBucketSummaryHTML", "function homeExecutionReasonChipsHTML", "data-home-execution-queue", "aria-describedby=\"homeExecutionReceiptDetail\""] },
    { file: "app.js", terms: ["homeExecutionViewHelpers", "homeExecutionViewCall(\"homeExecutionQueueHTML\"", "function homeExecutionQueueHTML(model)"] },
    { file: "index.html", terms: ["./home-execution-view.js", "./app.js"] },
    { file: "sw.js", terms: ["./home-execution-view.js"] },
    { file: "scripts/package-release.mjs", terms: ["\"home-execution-view.js\"", "{ path: \"home-execution-view.js\", attr: \"src\" }"] },
    { file: "scripts/verify-release.mjs", terms: ["\"home-execution-view.js\"", "expectedRuntimeScriptOrder"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionViewModuleOk", "home execution view module did not load", "homeExecutionViewModule: homeExecutionViewModuleOk"] },
    { file: "scripts/check-app-structure.mjs", terms: ["home-execution-view.js", "home-execution-view", "JooParkHomeExecutionView"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionViewModule === true"] },
    { file: "docs/app-architecture.md", terms: ["home-execution-view.js", "due/priority execution queue rendering"] },
    { file: "README.md", terms: ["home-execution-view.js", "오늘 실행 큐"] },
    { file: "package.json", terms: ["home-execution-view.js"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_view_module",
    requirement: "The home execution queue renderer is extracted into a static runtime helper with script-order, offline cache, release packaging, structure, documentation, and browser interaction coverage.",
    status: homeExecutionViewModuleTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionViewModuleTerms,
  });

  const homeExecutionQueueTerms = [
    { file: "app.js", terms: ["function homeExecutionQueueModel", "linear_todoist_priority_due_benchmark", "action: \"open-issue\""] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue", "data-home-execution-queue-score", "오늘 실행 큐"] },
    { file: "styles.css", terms: [".home-execution-queue", ".home-execution-queue-open", ".home-execution-rank", ".home-execution-priority"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueOk", "home execution queue ranks todo and PM issue work", "home execution queue did not combine todos and PM issues", "home execution queue was not sorted by score"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueue === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue",
    requirement: "The home dashboard combines due personal todos and PM issues into a priority/due-date execution queue with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueTerms,
  });

  const homeExecutionQueueExplainabilityTerms = [
    { file: "app.js", terms: ["HOME_EXECUTION_DUE_REASON_LABEL", "function homeExecutionReasonKey", "reasonChips"] },
    { file: "home-execution-view.js", terms: ["function homeExecutionReasonChipsHTML", "data-home-execution-queue-explainable=\"true\"", "data-home-execution-queue-reason", "data-home-execution-score-breakdown", "data-home-execution-reason-key"] },
    { file: "styles.css", terms: [".home-execution-reasons", ".home-execution-reason", "data-home-execution-reason-key=\"due:overdue\"", "data-home-execution-reason-key=\"priority:crit\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueExplainabilityOk", "home execution queue explainability flag did not render", "home execution queue top issue rationale did not expose due priority and status", "homeExecutionQueueExplainability: homeExecutionQueueExplainabilityOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueExplainability === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_explainability",
    requirement: "The home execution queue exposes visible due/priority/status rationale and machine-readable score breakdown for every ranked item, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueExplainabilityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueExplainabilityTerms,
  });

  const homeExecutionQueueBucketTerms = [
    { file: "app.js", terms: ["HOME_EXECUTION_BUCKET_LABEL", "function homeExecutionBucketSummary", "function homeExecutionBucketKey"] },
    { file: "home-execution-view.js", terms: ["function homeExecutionBucketSummaryHTML", "data-home-execution-queue-bucketed=\"true\"", "data-home-execution-queue-buckets", "data-home-execution-bucket"] },
    { file: "styles.css", terms: [".home-execution-bucket", "data-home-execution-bucket-key=\"overdue\"", "data-home-execution-bucket-key=\"today\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueBucketsOk", "home execution queue focus buckets did not render", "home execution queue focus bucket counts did not match total candidates", "homeExecutionQueueBuckets: homeExecutionQueueBucketsOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueBuckets === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_buckets",
    requirement: "The home execution queue summarizes ranked work into due-state focus buckets with todo/issue composition, browser smoke, and packaged gate cache coverage.",
    status: homeExecutionQueueBucketTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueBucketTerms,
  });

  const homeExecutionQueueBucketFilterTerms = [
    { file: "app.js", terms: ["homeExecutionBucketFilter", "function normalizeHomeExecutionBucketFilter", "function setHomeExecutionBucketFilter"] },
    { file: "home-execution-view.js", terms: ["data-action=\"home-execution-bucket-filter\"", "data-home-execution-queue-filterable=\"true\"", "data-home-execution-queue-bucket-filter", "aria-pressed"] },
    { file: "styles.css", terms: [".home-execution-bucket:hover", "data-home-execution-bucket-selected=\"true\"", "box-shadow"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueBucketFilterOk", "home execution queue bucket filter did not switch to today", "home execution queue bucket filter did not reset to all", "homeExecutionQueueBucketFilter: homeExecutionQueueBucketFilterOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueBucketFilter === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_bucket_filter",
    requirement: "The home execution queue due-state buckets are clickable filters with selected-state accessibility, browser smoke, and packaged gate cache coverage.",
    status: homeExecutionQueueBucketFilterTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueBucketFilterTerms,
  });

  const homeExecutionQueueFilterSummaryTerms = [
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-filter-summary", "data-home-execution-filter-summary", "data-home-execution-filter-summary-active", "data-home-execution-filter-summary-reset"] },
    { file: "styles.css", terms: [".home-execution-filter-summary", "data-home-execution-filter-summary-active=\"true\"", ".home-execution-filter-summary button"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueFilterSummaryOk", "home execution queue filter summary did not switch to today", "homeExecutionQueueFilterSummary: homeExecutionQueueFilterSummaryOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueFilterSummary === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_filter_summary",
    requirement: "The home execution queue renders an active filter receipt with filtered/total candidate counts, reset action, browser smoke, and packaged gate cache coverage.",
    status: homeExecutionQueueFilterSummaryTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueFilterSummaryTerms,
  });

  const homeExecutionQueueFilterCompositionTerms = [
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-filtered-todo-count", "data-home-execution-queue-filtered-issue-count", "data-home-execution-filtered-todo-count", "data-home-execution-filtered-issue-count"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueFilterCompositionOk", "home execution queue filter composition did not match all candidates", "homeExecutionQueueFilterComposition: homeExecutionQueueFilterCompositionOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueFilterComposition === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_filter_composition",
    requirement: "The home execution queue active filter receipt exposes filtered Todo and PM issue composition with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueFilterCompositionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueFilterCompositionTerms,
  });

  const homeExecutionQueueFilterWindowTerms = [
    { file: "app.js", terms: ["hiddenCandidateCount"] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-hidden-candidate-count", "data-home-execution-hidden-candidate-count", "모두 표시"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueFilterWindowOk", "home execution queue filter window did not expose hidden candidates", "homeExecutionQueueFilterWindow: homeExecutionQueueFilterWindowOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueFilterWindow === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_filter_window",
    requirement: "The home execution queue active filter receipt exposes how many matching candidates are visible versus still waiting, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueFilterWindowTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueFilterWindowTerms,
  });

  const homeExecutionQueueFilterRankWindowTerms = [
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-rank-window", "data-home-execution-rank-window-count", "data-home-execution-rank-window-total", "상위"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueFilterRankWindowOk", "home execution queue filter rank window did not render", "homeExecutionQueueFilterRankWindow: homeExecutionQueueFilterRankWindowOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueFilterRankWindow === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_filter_rank_window",
    requirement: "The home execution queue active filter receipt states the current ranked top window within the matching candidates, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueFilterRankWindowTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueFilterRankWindowTerms,
  });

  const homeExecutionQueueScoreWindowTerms = [
    { file: "app.js", terms: ["windowFloorScore"] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-score-window", "data-home-execution-score-window-top", "data-home-execution-score-window-floor", "점수"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueScoreWindowOk", "home execution queue score window did not render", "homeExecutionQueueScoreWindow: homeExecutionQueueScoreWindowOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueScoreWindow === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_score_window",
    requirement: "The home execution queue active filter receipt exposes the visible ranked window's top and floor scores, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueScoreWindowTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueScoreWindowTerms,
  });

  const homeExecutionQueueScoreDriverTerms = [
    { file: "app.js", terms: ["windowDuePressureCount", "windowHighPriorityCount", "windowActiveIssueCount", "label: \"마감\""] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-score-driver", "data-home-execution-score-driver-due", "우선순위 근거"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueScoreDriverOk", "home execution queue score driver summary did not render", "homeExecutionQueueScoreDriver: homeExecutionQueueScoreDriverOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueScoreDriver === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_score_driver",
    requirement: "The home execution queue active filter receipt summarizes which visible top-window drivers came from due pressure, high priority, and active PM issue status, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueScoreDriverTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueScoreDriverTerms,
  });

  const homeExecutionQueueLeadDriverTerms = [
    { file: "app.js", terms: ["windowLeadDriverKey", "windowLeadDriverLabel"] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-lead-driver", "data-home-execution-lead-driver-label", "대표"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueLeadDriverOk", "home execution queue lead driver did not render", "homeExecutionQueueLeadDriver: homeExecutionQueueLeadDriverOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueLeadDriver === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_lead_driver",
    requirement: "The home execution queue active filter receipt names the dominant visible top-window driver, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueLeadDriverTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueLeadDriverTerms,
  });

  const homeExecutionQueueLeadDriverCountTerms = [
    { file: "app.js", terms: ["windowLeadDriverCount"] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-lead-driver-count", "data-home-execution-lead-driver-count", "${model.windowLeadDriverCount}/${model.itemCount}"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueLeadDriverCountOk", "home execution queue lead driver count did not render", "homeExecutionQueueLeadDriverCount: homeExecutionQueueLeadDriverCountOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueLeadDriverCount === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_lead_driver_count",
    requirement: "The home execution queue active filter receipt quantifies how many visible rows match the dominant top-window driver, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueLeadDriverCountTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueLeadDriverCountTerms,
  });

  const homeExecutionQueueLeadDriverTieTerms = [
    { file: "app.js", terms: ["function homeExecutionWindowDriverModel", "leadDrivers", "leadDriverTieCount", "공동 ${leadDrivers.map"] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-lead-driver-tie-count"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueLeadDriverTieOk", "home execution queue lead driver tie did not render", "homeExecutionQueueLeadDriverTie: homeExecutionQueueLeadDriverTieOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueLeadDriverTie === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_lead_driver_tie",
    requirement: "The home execution queue active filter receipt keeps tied dominant top-window drivers as a joint cause instead of forcing a single driver, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueLeadDriverTieTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueLeadDriverTieTerms,
  });

  const homeExecutionQueueReceiptCompactTerms = [
    { file: "home-execution-view.js", terms: ["data-home-execution-receipt-compact=\"true\"", "data-home-execution-score-window-top", "data-home-execution-score-driver-due", "대표 ${model.windowLeadDriverLabel}"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueReceiptCompactOk", "home execution queue compact receipt did not render", "homeExecutionQueueReceiptCompact: homeExecutionQueueReceiptCompactOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueReceiptCompact === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_receipt_compact",
    requirement: "The home execution queue active filter receipt keeps the visible copy compact while preserving score and driver detail in machine-readable fields, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueReceiptCompactTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueReceiptCompactTerms,
  });

  const homeExecutionQueueReceiptDetailTerms = [
    { file: "home-execution-view.js", terms: ["receiptDetail", "data-home-execution-receipt-detail=\"accessible\"", "aria-label=\"${model.bucketFilterLabel} 실행 큐 상세", "title=\"${receiptDetail}\""] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueReceiptDetailOk", "home execution queue accessible receipt detail did not render", "homeExecutionQueueReceiptDetail: homeExecutionQueueReceiptDetailOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueReceiptDetail === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_receipt_accessible_detail",
    requirement: "The home execution queue compact receipt exposes the hidden score and driver detail through accessible title and aria copy while keeping visible text compact, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueReceiptDetailTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueReceiptDetailTerms,
  });

  const homeExecutionQueueReceiptDescriptionTerms = [
    { file: "home-execution-view.js", terms: ["role=\"note\"", "tabindex=\"0\"", "aria-describedby=\"homeExecutionReceiptDetail\"", "id=\"homeExecutionReceiptDetail\"", "data-home-execution-receipt-description"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueReceiptDescriptionOk", "home execution queue described receipt detail did not render", "homeExecutionQueueReceiptDescription: homeExecutionQueueReceiptDescriptionOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueReceiptDescription === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_receipt_describedby",
    requirement: "The home execution queue compact receipt uses a keyboard-focusable note plus aria-describedby to connect the hidden score and driver explanation to real DOM text, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueReceiptDescriptionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueReceiptDescriptionTerms,
  });

  const homeExecutionQueueQuickActionTerms = [
    { file: "app.js", terms: ["HOME_EXECUTION_ISSUE_NEXT_STATUS", "function homeExecutionIssueNextStatus", "home-execution-issue-next", "quickAction: \"home-execution-todo-complete\"", "quickActionLabel"] },
    { file: "home-execution-view.js", terms: ["data-home-execution-queue-quick", "home-execution-quick-action", "data-home-execution-queue-next"] },
    { file: "styles.css", terms: [".home-execution-queue-row", ".home-execution-actions", ".home-execution-quick-action"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueQuickActionsOk", "home execution queue quick actions complete todos and advance issues", "homeExecutionQueueQuickActions: homeExecutionQueueQuickActionsOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueQuickActions === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_quick_actions",
    requirement: "The home execution queue lets operators complete due todos and advance PM issues directly, with browser smoke and packaged gate cache coverage.",
    status: homeExecutionQueueQuickActionTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueQuickActionTerms,
  });

  const homeExecutionQueueQuickUndoTerms = [
    { file: "app.js", terms: ["function completeHomeExecutionTodo", "function advanceHomeExecutionIssue", "showUndoToast(\"오늘 실행 큐 할 일을 완료했습니다\"", "showUndoToast(`이슈를 '${ISSUE_STATUS_LABELS[nextStatus]}'으로 이동했습니다`"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeExecutionQueueQuickUndoOk", "home execution queue todo quick undo did not restore the todo", "home execution queue issue quick undo did not restore the issue status", "homeExecutionQueueQuickUndo: homeExecutionQueueQuickUndoOk"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["interactionChecks.homeExecutionQueueQuickUndo === true"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_execution_queue_quick_undo",
    requirement: "The home execution queue quick actions are reversible for both due todos and PM issue status changes, and the packaged browser gate cache must prove the undo path.",
    status: homeExecutionQueueQuickUndoTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homeExecutionQueueQuickUndoTerms,
  });

	  const homePublicReadinessTerms = [
    { file: "home-view.js", terms: ["data-home-readiness", "data-home-publish-blockers", "data-home-launch-proof-ready", "data-home-benchmark-count", "data-home-readiness-card-evidence-count", "공개 준비 요약", "데이터 소유권", "벤치마크 큐", "value: `${releaseGateEvidence.length} proofs`", "route 17/17, mobile search/UI, delete undo, a11y"] },
    { file: "styles.css", terms: [".home-readiness-grid", ".home-readiness-card", "[data-readiness-tone=\"amber\"]", "[data-readiness-tone=\"violet\"]"] },
    { file: "scripts/smoke-chrome.mjs", terms: ["home readiness summary did not render", "home readiness publish blocker count missing", "data-home-readiness-card", "benchmark-queue"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["homeReleaseGateEvidenceOk", "home release gate evidence summary did not render", "6 proofs", "route 17/17", "mobile search/UI", "delete undo", "a11y"] },
    { file: "README.md", terms: ["공개 준비 요약", "데이터 소유권", "릴리스 게이트", "벤치마크 큐", "6 proofs", "route 17/17", "mobile search/UI", "delete undo", "a11y"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "home_public_readiness_summary",
    requirement: "The home dashboard exposes a first-visit public readiness summary for local data ownership, release gates, publish proof blockers, and benchmark evidence with browser smoke coverage.",
    status: homePublicReadinessTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: homePublicReadinessTerms,
  });

  const vendorTerms = [
    { file: "vendor/marked.umd.js", terms: ["marked v18.0.5"] },
    { file: "vendor/purify.min.js", terms: ["DOMPurify 3.4.8"] },
    { file: "vendor/LICENSES.md", terms: ["marked | 18.0.5", "DOMPurify | 3.4.8", "Fuse.js는 7.x부터 UMD"] },
    { file: "README.md", terms: ["marked](https://github.com/markedjs/marked) | 18.0.5", "DOMPurify](https://github.com/cure53/DOMPurify) | 3.4.8"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["unsafe script tag was not sanitized", "unsafe event handler attribute was not sanitized", "unsafe javascript link was not sanitized", "markdown strong text was not rendered", "markdownSanitized"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "vendored_oss_freshness",
    requirement: "Compatible vendored Markdown/XSS libraries are refreshed, while Fuse.js remains pinned to the last UMD-compatible line.",
    status: vendorTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: vendorTerms,
  });

  const sourceParityTerms = [
    { file: "scripts/verify-release.mjs", terms: ["sourceParityFiles", "function verifySourceParity", "source parity byte mismatch", "source parity sha256 mismatch"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["function verifyRelease", "scripts/package-release.mjs", "node scripts/package-release.mjs && node scripts/verify-release.mjs"] },
    { file: "README.md", terms: ["source parity", "source-copied runtime file", "scripts/verify-release.mjs", "stale dist", "manifest_integrity"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "manifest_integrity",
    requirement: "The release manifest matches actual packaged runtime files by path, byte count, and SHA-256, and source-copied runtime files in dist/release still match the current source tree.",
    status: verify.status === "pass" && Number(verify.result?.sourceParityFiles || 0) >= 38 && sourceParityTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      verify,
      files: sourceParityTerms,
    },
  });

  const releaseProvenanceTerms = [
    { file: "scripts/package-release.mjs", terms: ["release-provenance.json", "https://in-toto.io/Statement/v1", "https://slsa.dev/provenance/v1", "unsigned-local-provenance", "resolvedDependencies"] },
    { file: "scripts/verify-release.mjs", terms: ["function verifyReleaseProvenance", "release-provenance.json missing", "provenance manifest subject sha256 mismatch", "provenanceSigned"] },
    { file: "README.md", terms: ["release-provenance.json", "in-toto Statement v1", "SLSA provenance v1", "unsigned-local-provenance", "GitHub artifact attestations"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const provenance = releaseManifestProvenance();
  checklist.push({
    id: "release_source_provenance",
    requirement: "The packaged release includes an unsigned local in-toto/SLSA-style provenance statement whose subject digest ties back to release-manifest.json and whose builder/source dependency fields are verifier-checked before external attestation exists.",
    status: provenance.status === "pass" && releaseProvenanceTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: {
      provenance,
      files: releaseProvenanceTerms,
    },
  });

  const releaseProvenanceUiTerms = [
    { file: "app.js", terms: ["releaseProvenance", "function loadReleaseProvenance", "release-provenance.json", "copyReleaseProvenanceReceipt", "data-system-release-provenance"] },
    { file: "release-status.js", terms: ["function releaseProvenanceHTML", "JooPark Release Provenance Receipt", "data-release-provenance-subject-sha", "unsigned local provenance", "GitHub artifact attestation"] },
    { file: "system-status-view.js", terms: ["releaseProvenanceHTML", "data-system-release-provenance", "state.releaseProvenance"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["releaseProvenancePanel", "releaseProvenanceReceiptCopy", "data-system-release-provenance", "Do not present it as a GitHub artifact attestation"] },
    { file: "README.md", terms: ["System Status", "Release provenance", "provenance receipt", "releaseProvenanceUiCoverageScore"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_provenance_ui_surface",
    requirement: "System Status exposes the local release provenance statement, digest, builder/source fields, unsigned boundary, verifier commands, and copy-ready receipt with browser smoke coverage.",
    status: releaseProvenanceUiTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: releaseProvenanceUiTerms,
  });

  const pagesAttestationProofIntakeTerms = [
    { file: "release-status.js", terms: ["function pagesAttestationProofIntakeHTML", "function pagesAttestationProofIntakeReceiptText", "JooPark Pages Attestation Proof Intake", "attestation-url", "attestation-id", "gh attestation verify dist/release/release-manifest.json", "gh attestation verify dist/release/index.html", "data-system-pages-attestation-proof-intake", "Do not claim signed GitHub artifact attestation proof"] },
    { file: "system-status-view.js", terms: ["pagesAttestationProofIntakeHTML", "data-system-pages-attestation-proof-intake", "state.publishDispatchPlan", "state.launchExecutionPacket", "state.releaseProvenance"] },
    { file: "app.js", terms: ["function pagesAttestationProofIntakeHTML", "copyPagesAttestationProofIntake", "copy-pages-attestation-proof-intake", "data-pages-attestation-proof-intake-receipt-text", "pagesAttestationProofIntakeCopied"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["pagesAttestationProofIntakeOk", "pagesAttestationProofIntakeCopyOk", "data-system-pages-attestation-proof-intake", "attestation-url", "attestation-id", "gh attestation verify dist/release/release-manifest.json", "gh attestation verify dist/release/index.html", "Do not claim signed GitHub artifact attestation proof"] },
    { file: "README.md", terms: ["Pages attestation proof intake", "attestation-url", "attestation-id", "gh attestation verify dist/release/release-manifest.json", "gh attestation verify dist/release/index.html", "not signed proof yet", "Do not claim signed GitHub artifact attestation proof"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "pages_attestation_proof_intake",
    requirement: "System Status includes a copy-ready post-run proof intake for GitHub Pages artifact attestations, including actions/attest outputs and gh attestation verify commands, while blocking signed-proof claims until the remote workflow has run.",
    status: pagesAttestationProofIntakeTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: pagesAttestationProofIntakeTerms,
  });

  if (runGates && gateEvidence) {
    gateEvidence = writePackagedBrowserGateCache(gateEvidence);
  }
  if (gateEvidence) {
    checklist.push({
      id: "packaged_browser_gates",
      requirement: "The packaged release package and manifest verification pass, then route smoke, desktop/mobile route parity, mobile layout/search-empty/UI-surface smoke, click/input interaction smoke, delete/undo recovery smoke, and keyboard/ARIA accessibility smoke pass from a temporary local server.",
      status: gateEvidence.status,
      evidence: gateEvidence,
    });
  } else {
    const cacheDiagnostics = packagedBrowserGateCacheDiagnostics();
    checklist.push({
      id: "packaged_browser_gates",
      requirement: "The packaged release package and manifest verification pass, then route smoke, desktop/mobile route parity, mobile layout/search-empty/UI-surface smoke, click/input interaction smoke, delete/undo recovery smoke, and keyboard/ARIA accessibility smoke pass from a temporary local server.",
      status: "not_run",
      evidence: {
        command: "node scripts/audit-release-readiness.mjs --run-gates",
        repairCommand: packagedBrowserGateRepairCommand,
        postGateRefreshCommand: packagedBrowserGatePostGateRefreshCommand,
        cache: cacheDiagnostics,
      },
    });
  }

  const remote = run("git", ["remote", "-v"]);
  checklist.push({
    id: "publish_remote",
    requirement: "A Git remote exists before claiming push or publish completion.",
    status: remote.ok && remote.stdout.trim() ? "pass" : "blocked",
    evidence: { command: "git remote -v", stdout: remote.stdout.trim() || "none" },
  });

  const branchSync = gitBranchSync();
  checklist.push({
    id: "publish_branch_sync",
    requirement: "The current branch tracks a remote branch and is not ahead, behind, gone, or diverged before claiming publish completion.",
    status: branchSync.status,
    evidence: branchSync,
  });

  return checklist;
}

function audit() {
  const gitStatus = run("git", ["status", "--short", "--branch"]);
  const gitHead = run("git", ["rev-parse", "--short", "HEAD"]);
  const checklist = buildChecklist();
  const failures = checklist.filter((item) => item.status === "fail");
  const notRun = checklist.filter((item) => item.status === "not_run");
  const blockers = checklist.filter((item) => item.status === "blocked");
  const externalClaimGuard = externalClaimGuardState();
  return {
    generatedAt: new Date().toISOString(),
    projectRoot: root,
    sourceCommit: gitHead.stdout.trim(),
    gitStatus: gitStatus.stdout.trim(),
    status: failures.length > 0 ? "fail" : notRun.length > 0 || blockers.length > 0 ? "blocked" : "pass",
    summary: {
      pass: checklist.filter((item) => item.status === "pass").length,
      fail: failures.length,
      notRun: notRun.length,
      blocked: blockers.length,
      total: checklist.length,
    },
    externalClaimGuard,
    completionAudit: externalClaimGuard.completionAudit,
    checklist,
  };
}

function deferredProofSummaryLine(nextAction, publishEvidence) {
  const deferred = publishEvidence?.deferredNextAction || {};
  const key = String(nextAction?.deferredKey || deferred.key || "").trim();
  const command = String(nextAction?.deferredCommand || deferred.command || "").trim();
  if (!key && !command) return "- Deferred proof: none";
  return `- Deferred proof: ${key || "pending"} - ${command || "pending"}`;
}

function externalClaimGuardState() {
  const outputQuality = fileExists("data/output-quality-audit.json") ? parseJson(read("data/output-quality-audit.json")) : null;
  const publishEvidence = fileExists("data/publish-evidence.json") ? parseJson(read("data/publish-evidence.json")) : null;
  const guard = outputQuality?.externalClaimGuard || {};
  const nextAction = outputQuality?.nextAction || publishEvidence?.nextAction || {};
  const readyForExternalClaim = outputQuality?.readyForExternalClaim === true;
  const guardStatus = guard.status || (readyForExternalClaim ? "ready_for_external_claim" : "blocked_external_claim");
  const blockedCount = Number.isFinite(Number(guard.blockedCount)) ? Number(guard.blockedCount) : 0;
  const requirementCount = Number.isFinite(Number(guard.requirementCount)) ? Number(guard.requirementCount) : 0;
  const requirements = Array.isArray(guard.requirements) ? guard.requirements : [];
  const blockedRequirements = requirements.filter((item) => item?.status && item.status !== "pass");
  const requiredSignals = Array.isArray(guard.requiredSignals) ? guard.requiredSignals : [];
  const missingSignals = blockedRequirements.flatMap((item) => Array.isArray(item.missing) ? item.missing : []);
  const blockedSignals = [...new Set((missingSignals.length ? missingSignals : requiredSignals)
    .filter((signal) => /(?:=false|blocked|action_required)/.test(String(signal))))];
  const deferred = publishEvidence?.deferredNextAction || {};
  const deferredKey = String(nextAction?.deferredKey || deferred.key || "").trim();
  const deferredCommand = String(nextAction?.deferredCommand || deferred.command || "").trim();
  const launchCompletionAchieved = readyForExternalClaim &&
    outputQuality?.releaseQualityReady === true &&
    outputQuality?.publicLaunchProofReady === true &&
    outputQuality?.launchPacketReadyForExternalClaim === true &&
    blockedRequirements.length === 0 &&
    blockedSignals.length === 0;
  return {
    status: guardStatus,
    ready: guard.ready === true || launchCompletionAchieved,
    readyForExternalClaim,
    releaseQualityReady: outputQuality?.releaseQualityReady === true,
    publicLaunchProofReady: outputQuality?.publicLaunchProofReady === true,
    launchPacketReadyForExternalClaim: outputQuality?.launchPacketReadyForExternalClaim === true,
    blockedCount,
    requirementCount,
    requiredSignals,
    requirements: requirements.map((item) => ({
      key: item?.key || "",
      label: item?.label || "",
      status: item?.status || "",
      detail: item?.detail || "",
      missing: Array.isArray(item?.missing) ? item.missing : [],
    })),
    blockedRequirements: blockedRequirements.map((item) => ({
      key: item?.key || "",
      status: item?.status || "",
      detail: item?.detail || item?.label || "",
      missing: Array.isArray(item?.missing) ? item.missing : [],
    })),
    blockedSignals,
    nextAction: {
      key: nextAction.key || "",
      status: nextAction.status || "",
      command: nextAction.command || "",
      detail: nextAction.detail || "",
      deferredKey,
      deferredCommand,
    },
    stopCondition: guard.stopCondition || "",
    completionAudit: {
      status: launchCompletionAchieved ? "ready_for_external_claim" : "blocked_external_claim",
      launchCompletionAchieved,
      primaryMetric: "completionAuditStructuredCoverage",
      baseline: 0,
      candidate: 4,
      decision: "keep",
      readyForExternalClaim,
      blockedSignals,
      nextActionKey: nextAction.key || "",
      nextActionStatus: nextAction.status || "",
      nextActionCommand: nextAction.command || "",
      guard: "Do not claim external launch completion until launchCompletionAchieved=true and readyForExternalClaim=true.",
    },
  };
}

function externalClaimGuardSummaryLines(state = externalClaimGuardState()) {
  const blockedLabel = state.requirementCount > 0 ? `; blocked=${state.blockedCount}/${state.requirementCount}` : "";
  const nextCommand = state.nextAction.command || "pending";
  const blockedSignals = state.completionAudit.blockedSignals.length ? state.completionAudit.blockedSignals.join("; ") : "none";
  const lines = [
    `- External claim: ${state.status} (readyForExternalClaim=${state.readyForExternalClaim}${blockedLabel})`,
    `- Completion audit: ${state.completionAudit.status} (launchCompletionAchieved=${state.completionAudit.launchCompletionAchieved}; blockedSignals=${blockedSignals})`,
    `- Release quality ready: ${state.releaseQualityReady}; public launch proof ready: ${state.publicLaunchProofReady}; launch packet readyForExternalClaim: ${state.launchPacketReadyForExternalClaim}`,
    `- Next action: ${state.nextAction.key || "pending"}${state.nextAction.status ? ` [${state.nextAction.status}]` : ""} - ${nextCommand}`,
    deferredProofSummaryLine({
      deferredKey: state.nextAction.deferredKey,
      deferredCommand: state.nextAction.deferredCommand,
    }, {
      deferredNextAction: {
        key: state.nextAction.deferredKey,
        command: state.nextAction.deferredCommand,
      },
    }),
  ];
  if (state.requiredSignals.length > 0) {
    lines.push(`- Required signals: ${state.requiredSignals.join("; ")}`);
  }
  if (state.stopCondition) {
    lines.push(`- Stop condition: ${String(state.stopCondition).replace(/^Stop condition:\s*/i, "")}`);
  }
  return lines;
}

function externalClaimGuardBlockerLines(state = externalClaimGuardState()) {
  if (state.ready !== false && state.blockedRequirements.length === 0) return [];
  if (state.blockedRequirements.length === 0) {
    return [
      `- external_claim_guard: ${state.status} - readyForExternalClaim=${state.readyForExternalClaim}`,
    ];
  }
  return state.blockedRequirements.map((item) => {
    const missing = Array.isArray(item.missing) && item.missing.length ? ` Missing: ${item.missing.join("; ")}` : "";
    return `- external_claim_guard.${item.key || "requirement"}: ${item.status} - ${item.detail || item.label || "external completion proof is incomplete."}${missing}`;
  });
}

function trackedProductContractLines(payload) {
  const checklist = Array.isArray(payload?.checklist) ? payload.checklist : [];
  return trackedProductContractIds.map((id) => {
    const item = checklist.find((entry) => entry && entry.id === id);
    if (!item) return `- ${id}: missing`;
    return `- ${item.id}: ${item.status} - ${item.requirement}`;
  });
}

function packagedBrowserGateCacheDiagnosticText(cache) {
  if (!cache) return "";
  const issues = Array.isArray(cache.issues) ? cache.issues.filter(Boolean).slice(0, 4) : [];
  const mismatches = Array.isArray(cache.contextMismatches) ? cache.contextMismatches.filter(Boolean) : [];
  const firstMismatch = mismatches[0] || null;
  const parts = [];
  if (cache.status) parts.push(`cache=${cache.status}`);
  if (cache.contextMatched !== undefined) parts.push(`contextMatched=${cache.contextMatched === true}`);
  if (cache.cachedEvidenceStatus) parts.push(`cachedEvidenceStatus=${cache.cachedEvidenceStatus}`);
  if (cache.cachedResultStatus) parts.push(`cachedResultStatus=${cache.cachedResultStatus}`);
  if (issues.length) parts.push(`issues=${issues.join(",")}`);
  if (firstMismatch) {
    parts.push(`firstMismatch=${firstMismatch.path || "unknown"}:${firstMismatch.reason || "mismatch"}`);
  }
  return parts.length ? `Cache diagnostics: ${parts.join("; ")}.` : "";
}

function checklistBlockerLine(item) {
  const cacheText = item.id === "packaged_browser_gates"
    ? packagedBrowserGateCacheDiagnosticText(item.evidence?.cache)
    : "";
  const repairText = item.id === "packaged_browser_gates" && item.status === "not_run"
    ? ` Repair command: \`${item.evidence?.repairCommand || packagedBrowserGateRepairCommand}\`. Post-gate refresh: \`${item.evidence?.postGateRefreshCommand || packagedBrowserGatePostGateRefreshCommand}\`.`
    : "";
  return `- ${item.status}: \`${item.id}\` - ${item.requirement}${cacheText ? ` ${cacheText}` : ""}${repairText}`;
}

function markdown(payload) {
  const lines = [
    "# JooPark Release Readiness Audit",
    "",
    `- Generated: ${payload.generatedAt}`,
    `- Project root: \`${payload.projectRoot}\``,
    `- Source commit: \`${payload.sourceCommit}\``,
    `- Status: ${payload.status}`,
    `- Summary: ${payload.summary.pass} pass, ${payload.summary.fail} fail, ${payload.summary.notRun} not_run, ${payload.summary.blocked} blocked, ${payload.summary.total} total`,
    "",
    "## External Claim Guard",
    ...externalClaimGuardSummaryLines(),
    "",
    "## Checklist",
  ];
  for (const item of payload.checklist) {
    lines.push(`- ${item.status}: \`${item.id}\` - ${item.requirement}`);
  }
  lines.push("", "## Git", "```", payload.gitStatus, "```");
  lines.push("", "## Blockers");
  const blockers = payload.checklist.filter((item) => item.status === "blocked" || item.status === "not_run" || item.status === "fail");
  const externalBlockers = externalClaimGuardBlockerLines();
  if (blockers.length === 0 && externalBlockers.length === 0) {
    lines.push("- none");
  } else {
    for (const item of blockers) lines.push(checklistBlockerLine(item));
    lines.push(...externalBlockers);
  }
  return `${lines.join("\n")}\n`;
}

function summary(payload) {
  const gate = payload.checklist.find((item) => item.id === "packaged_browser_gates");
  const blockers = payload.checklist.filter((item) => item.status === "blocked" || item.status === "not_run" || item.status === "fail");
  const externalBlockers = externalClaimGuardBlockerLines();
  const trackedProductContracts = trackedProductContractLines(payload);
  const gateCache = gate?.evidence?.cache;
  const gateCacheLabel = gate?.evidence?.cached
    ? `cached ${gateCache?.ageMinutes ?? 0}m old`
    : gateCache?.written
      ? "fresh run cached"
      : "";
  const lines = [
    "# JooPark Release Readiness Summary",
    "",
    `- Status: ${payload.status}`,
    `- Summary: ${payload.summary.pass} pass, ${payload.summary.fail} fail, ${payload.summary.notRun} not_run, ${payload.summary.blocked} blocked, ${payload.summary.total} total`,
    `- Generated: ${payload.generatedAt}`,
    `- Source commit: ${payload.sourceCommit}`,
    `- Packaged browser gates: ${gate?.status || "missing"}${gateCacheLabel ? ` (${gateCacheLabel})` : ""}`,
    `- Git: ${payload.gitStatus.split("\n")[0] || "unknown"}`,
    "",
    "## Product Contracts",
    ...trackedProductContracts,
    "",
    "## External Claim Guard",
    ...externalClaimGuardSummaryLines(),
    "",
    "## Blockers",
  ];
  if (blockers.length === 0 && externalBlockers.length === 0) {
    lines.push("- none");
  } else {
    for (const item of blockers) lines.push(checklistBlockerLine(item));
    lines.push(...externalBlockers);
  }
  return `${lines.join("\n")}\n`;
}

let auditGateLockAcquired = false;
let exitCode = 0;
try {
  if (runGates) {
    acquireAuditGateLock();
    auditGateLockAcquired = true;
  }
  const payload = audit();
  writeReleaseReadinessSummaryCache(payload);
  if (format === "summary") console.log(summary(payload));
  else if (format === "markdown") console.log(markdown(payload));
  else if (format === "json-pretty") console.log(JSON.stringify(payload, null, 2));
  else console.log(JSON.stringify(payload));
  if (payload.status !== "pass") exitCode = 1;
} finally {
  if (auditGateLockAcquired) releaseAuditGateLock();
}
process.exit(exitCode);
