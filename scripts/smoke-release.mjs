#!/usr/bin/env node

import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:http";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { readFile } from "node:fs/promises";
import {
  dirname,
  extname,
  join,
  relative,
  resolve,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const releaseDir = process.env.RELEASE_OUT_DIR
  ? resolve(root, process.env.RELEASE_OUT_DIR)
  : join(root, "dist", "release");
const host = "127.0.0.1";
const requestedPort = Number(process.env.RELEASE_SMOKE_PORT || process.env.PORT || 0);
const shouldPackage = process.env.RELEASE_SMOKE_SKIP_PACKAGE !== "1";
const packagedBrowserGateCacheRel = "autoresearch-results/release-readiness-gates.json";
const packagedBrowserGateCacheSchema = "joopark-packaged-browser-gates/v1";
const packagedBrowserGateCacheMaxAgeHours = 6;
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
  "data/output-quality-audit.json",
  "data/publish-dispatch-plan.json",
  "data/publish-evidence.json",
  "data/remote-workflow-file-check.json",
  "data/workflow-ui-install-plan.json",
  "scripts/audit-release-readiness.mjs",
  "scripts/capture-output-quality-audit.mjs",
]);
const packagedBrowserGateRuntimeFiles = [
  "index.html",
  "search-empty-state.js",
  "home-execution-view.js",
  "calendar-view.js",
  "todo-view.js",
  "notes-view.js",
  "habits-view.js",
  "stats-view.js",
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
const packagedBrowserGateReleaseScripts = [
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
  "scripts/smoke-release.mjs",
  "scripts/plan-workflow-ui-install.mjs",
  "scripts/plan-publish-dispatch.mjs",
  "scripts/install-remote-workflow-files.mjs",
  "scripts/check-remote-workflow-files.mjs",
  "scripts/capture-publish-evidence.mjs",
  "scripts/capture-launch-execution-packet.mjs",
  "scripts/capture-output-quality-audit.mjs",
];

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".svg": "image/svg+xml; charset=utf-8",
  ".webmanifest": "application/manifest+json; charset=utf-8",
};

function parseJsonOutput(stdout, fallbackStatus = "unknown") {
  try {
    return JSON.parse(stdout);
  } catch {
    return {
      status: fallbackStatus,
      output: stdout.trim(),
    };
  }
}

function progress(message) {
  console.error(`[smoke-release] ${message}`);
}

function runGitShortHead() {
  const result = spawnSync("git", ["rev-parse", "--short", "HEAD"], {
    cwd: root,
    encoding: "utf-8",
    stdio: ["ignore", "pipe", "ignore"],
  });
  return result.status === 0 ? result.stdout.trim() : "unknown";
}

function packagedBrowserGateInputFiles() {
  return [...new Set([
    ...packagedBrowserGateRuntimeFiles,
    ...packagedBrowserGateReleaseScripts,
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
  return {
    sourceCommit: runGitShortHead(),
    inputFiles: packagedBrowserGateInputFiles().map((file) => fileStatEvidence(file)),
  };
}

function writePackagedBrowserGateCache(resultPayload) {
  const context = packagedBrowserGateContext();
  const generatedAt = new Date().toISOString();
  const cache = {
    source: packagedBrowserGateCacheRel,
    generatedAt,
    maxAgeHours: packagedBrowserGateCacheMaxAgeHours,
    inputFiles: context.inputFiles.length,
  };
  let tempCachePath = "";
  try {
    const cachePath = join(root, packagedBrowserGateCacheRel);
    tempCachePath = `${cachePath}.${process.pid}.${Date.now()}.${Math.random().toString(36).slice(2)}.tmp`;
    mkdirSync(dirname(cachePath), { recursive: true });
    writeFileSync(tempCachePath, `${JSON.stringify({
      schemaVersion: packagedBrowserGateCacheSchema,
      generatedAt,
      maxAgeHours: packagedBrowserGateCacheMaxAgeHours,
      context,
      evidence: {
        status: resultPayload.status,
        command: "node scripts/smoke-release.mjs",
        result: resultPayload,
      },
    }, null, 2)}\n`, "utf-8");
    renameSync(tempCachePath, cachePath);
    return { ...cache, written: true };
  } catch (error) {
    if (tempCachePath) {
      try {
        rmSync(tempCachePath, { force: true });
      } catch {}
    }
    return { ...cache, written: false, error: error.message };
  }
}

function runNodeScript(scriptPath, scriptArgs = [], env = {}, timeoutMs = 90000) {
  const result = spawnSync(process.execPath, [join(root, scriptPath), ...scriptArgs], {
    cwd: root,
    env: { ...process.env, ...env },
    encoding: "utf-8",
    killSignal: "SIGKILL",
    timeout: timeoutMs,
  });

  if (result.error) {
    const error = new Error(`${scriptPath} failed: ${result.error.message}`);
    error.step = scriptPath;
    error.stdout = result.stdout || "";
    error.stderr = result.stderr || "";
    throw error;
  }

  if (result.status !== 0) {
    const error = new Error(`${scriptPath} failed with exit code ${result.status}`);
    error.step = scriptPath;
    error.stdout = result.stdout || "";
    error.stderr = result.stderr || "";
    throw error;
  }

  return {
    stdout: result.stdout || "",
    stderr: result.stderr || "",
  };
}

function runNodeScriptAsync(scriptPath, env = {}, timeoutMs = 120000) {
  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(process.execPath, [join(root, scriptPath)], {
      cwd: root,
      env: { ...process.env, ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let didTimeout = false;

    const timer = setTimeout(() => {
      didTimeout = true;
      child.kill("SIGKILL");
    }, timeoutMs);
    const heartbeat = setInterval(() => {
      progress(`waiting for ${scriptPath}`);
    }, 5000);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      clearInterval(heartbeat);
      error.step = scriptPath;
      error.stdout = stdout;
      error.stderr = stderr;
      rejectRun(error);
    });
    child.on("close", (code, signal) => {
      clearTimeout(timer);
      clearInterval(heartbeat);
      if (didTimeout) {
        const error = new Error(`${scriptPath} timed out after ${timeoutMs}ms`);
        error.step = scriptPath;
        error.stdout = stdout;
        error.stderr = stderr;
        rejectRun(error);
        return;
      }
      if (code !== 0) {
        const error = new Error(`${scriptPath} failed with exit code ${code}${signal ? ` (${signal})` : ""}`);
        error.step = scriptPath;
        error.stdout = stdout;
        error.stderr = stderr;
        rejectRun(error);
        return;
      }
      resolveRun({ stdout, stderr });
    });
  });
}

function isRetryableRuntimeTimeout(error) {
  const details = [
    error && error.message,
    error && error.stdout,
    error && error.stderr,
  ].filter(Boolean).join("\n");
  return details.includes("Timed out waiting for Runtime.evaluate") ||
    details.includes("route not ready");
}

async function runRetryableBrowserScript(scriptPath, env = {}, timeoutMs = 120000, retries = 1) {
  const attempts = [];
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const result = await runNodeScriptAsync(scriptPath, env, timeoutMs);
      return { ...result, attempts };
    } catch (error) {
      const retryable = isRetryableRuntimeTimeout(error);
      attempts.push({
        attempt: attempt + 1,
        retryable,
        message: error.message,
      });
      if (!retryable || attempt === retries) {
        error.attempts = attempts;
        throw error;
      }
    }
  }
  throw new Error(`${scriptPath} retry loop exited unexpectedly`);
}

function safeTarget(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }

  const requestPath = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
  const target = resolve(releaseDir, requestPath);
  const allowedPrefix = `${releaseDir}${sep}`;
  if (target !== releaseDir && !target.startsWith(allowedPrefix)) return null;
  if (existsSync(target) && statSync(target).isDirectory()) return join(target, "index.html");
  return target;
}

function readReleaseHeaderRules() {
  const path = join(releaseDir, "_headers");
  if (!existsSync(path)) return [];
  const rules = [];
  let current = null;
  for (const line of readFileSync(path, "utf-8").split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    if (/^\s/.test(line)) {
      if (!current) continue;
      const index = line.indexOf(":");
      if (index < 0) continue;
      current.headers.push({
        name: line.slice(0, index).trim(),
        value: line.slice(index + 1).trim(),
      });
      continue;
    }
    current = { pattern: line.trim(), headers: [] };
    rules.push(current);
  }
  return rules;
}

function readReleaseRedirectRules() {
  const path = join(releaseDir, "_redirects");
  if (!existsSync(path)) return [];
  const rules = [];
  for (const line of readFileSync(path, "utf-8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const [from, to, status = "301"] = trimmed.split(/\s+/);
    if (!from || !to) continue;
    rules.push({ from, to, status: Number(status) || 301 });
  }
  return rules;
}

function headerRuleMatches(pattern, pathname) {
  if (pattern === "/*") return true;
  if (pattern.endsWith("*")) return pathname.startsWith(pattern.slice(0, -1));
  return pathname === pattern;
}

function headersForPath(pathname, rules) {
  const headers = {};
  for (const rule of rules) {
    if (!headerRuleMatches(rule.pattern, pathname)) continue;
    for (const header of rule.headers) headers[header.name] = header.value;
  }
  return headers;
}

function redirectRuleMatches(pattern, pathname) {
  if (pattern === "/*") return true;
  if (pattern.endsWith("*")) return pathname.startsWith(pattern.slice(0, -1));
  return pathname === pattern;
}

function redirectForPath(pathname, rules) {
  return rules.find((rule) => redirectRuleMatches(rule.from, pathname)) || null;
}

function mergeHeaders(base, custom) {
  const headers = { ...base };
  for (const [key, value] of Object.entries(custom)) {
    for (const existing of Object.keys(headers)) {
      if (existing.toLowerCase() === key.toLowerCase()) delete headers[existing];
    }
    headers[key] = value;
  }
  return headers;
}

function createReleaseServer() {
  const sockets = new Set();
  const releaseHeaderRules = readReleaseHeaderRules();
  const releaseRedirectRules = readReleaseRedirectRules();
  const server = createServer(async (request, response) => {
    const url = new URL(request.url || "/", `http://${request.headers.host || host}`);
    let target = safeTarget(url.pathname);

    if (!target) {
      response.writeHead(403, { "content-type": "text/plain; charset=utf-8" });
      response.end("Forbidden");
      return;
    }

    try {
      const body = await readFile(target);
      response.writeHead(200, mergeHeaders({
        "cache-control": "no-store",
        "content-type": contentTypes[extname(target)] || "application/octet-stream",
      }, headersForPath(url.pathname, releaseHeaderRules)));
      response.end(body);
    } catch {
      const redirectRule = redirectForPath(url.pathname, releaseRedirectRules);
      const redirectTarget = redirectRule ? safeTarget(redirectRule.to) : null;
      if (redirectRule?.status === 200 && redirectTarget) {
        try {
          target = redirectTarget;
          const body = await readFile(target);
          response.writeHead(200, mergeHeaders({
            "cache-control": "no-store",
            "content-type": contentTypes[extname(target)] || "application/octet-stream",
          }, headersForPath(redirectRule.to, releaseHeaderRules)));
          response.end(body);
          return;
        } catch {
          // Fall through to the 404 response below.
        }
      }
      if (redirectRule && redirectRule.status >= 300 && redirectRule.status < 400) {
        response.writeHead(redirectRule.status, {
          "content-type": "text/plain; charset=utf-8",
          location: redirectRule.to,
        });
        response.end("Redirect");
        return;
      }
      response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      response.end("Not found");
    }
  });
  server.keepAliveTimeout = 1000;
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.setTimeout(10000);
    socket.on("close", () => sockets.delete(socket));
  });
  server.destroyOpenSockets = () => {
    for (const socket of sockets) socket.destroy();
    sockets.clear();
  };
  return server;
}

async function fetchHeaderMap(url) {
  const response = await fetch(url);
  const headers = {};
  for (const [key, value] of response.headers.entries()) headers[key.toLowerCase()] = value;
  return { status: response.status, headers };
}

async function smokeReleaseHeaders(baseUrl) {
  const root = await fetchHeaderMap(`${baseUrl}/`);
  const searchEmptyState = await fetchHeaderMap(`${baseUrl}/search-empty-state.js`);
  const calendarView = await fetchHeaderMap(`${baseUrl}/calendar-view.js`);
  const todoView = await fetchHeaderMap(`${baseUrl}/todo-view.js`);
  const notesView = await fetchHeaderMap(`${baseUrl}/notes-view.js`);
  const habitsView = await fetchHeaderMap(`${baseUrl}/habits-view.js`);
  const statsView = await fetchHeaderMap(`${baseUrl}/stats-view.js`);
  const llmWikiView = await fetchHeaderMap(`${baseUrl}/llm-wiki-view.js`);
  const portfolioView = await fetchHeaderMap(`${baseUrl}/portfolio-view.js`);
  const kanbanView = await fetchHeaderMap(`${baseUrl}/kanban-view.js`);
  const ganttView = await fetchHeaderMap(`${baseUrl}/gantt-view.js`);
  const teamView = await fetchHeaderMap(`${baseUrl}/team-view.js`);
  const workspaceStorage = await fetchHeaderMap(`${baseUrl}/workspace-storage.js`);
  const storageStatusView = await fetchHeaderMap(`${baseUrl}/storage-status-view.js`);
  const settingsView = await fetchHeaderMap(`${baseUrl}/settings-view.js`);
  const systemStatusView = await fetchHeaderMap(`${baseUrl}/system-status-view.js`);
  const importGuards = await fetchHeaderMap(`${baseUrl}/backup-import-guards.js`);
  const importUi = await fetchHeaderMap(`${baseUrl}/backup-import-ui.js`);
  const releaseStatus = await fetchHeaderMap(`${baseUrl}/release-status.js`);
  const operationsCopyActions = await fetchHeaderMap(`${baseUrl}/operations-copy-actions.js`);
  const verifyWorkspaceSummaryRuntime = await fetchHeaderMap(`${baseUrl}/verify-workspace-summary.js`);
  const dialogShell = await fetchHeaderMap(`${baseUrl}/dialog-shell.js`);
  const projectPicker = await fetchHeaderMap(`${baseUrl}/project-picker.js`);
  const globalSearch = await fetchHeaderMap(`${baseUrl}/global-search.js`);
  const commandPalette = await fetchHeaderMap(`${baseUrl}/command-palette.js`);
  const dbCatalog = await fetchHeaderMap(`${baseUrl}/db-catalog.js`);
  const reviewHandoff = await fetchHeaderMap(`${baseUrl}/review-handoff.js`);
  const reviewResultView = await fetchHeaderMap(`${baseUrl}/review-result-view.js`);
  const reviewExecutionChecklist = await fetchHeaderMap(`${baseUrl}/review-execution-checklist.js`);
  const reviewIssuePayload = await fetchHeaderMap(`${baseUrl}/review-issue-payload.js`);
  const reviewResultState = await fetchHeaderMap(`${baseUrl}/review-result-state.js`);
  const reviewResultDraftState = await fetchHeaderMap(`${baseUrl}/review-result-draft-state.js`);
  const reviewCreationActions = await fetchHeaderMap(`${baseUrl}/review-creation-actions.js`);
  const reviewPackageView = await fetchHeaderMap(`${baseUrl}/review-package-view.js`);
  const reviewArtifactView = await fetchHeaderMap(`${baseUrl}/review-artifact-view.js`);
  const reviewArtifactState = await fetchHeaderMap(`${baseUrl}/review-artifact-state.js`);
  const reviewCopyActions = await fetchHeaderMap(`${baseUrl}/review-copy-actions.js`);
  const reviewSubmissionCopy = await fetchHeaderMap(`${baseUrl}/review-submission-copy.js`);
  const reviewRecommendationExport = await fetchHeaderMap(`${baseUrl}/review-recommendation-export.js`);
  const pwaRuntime = await fetchHeaderMap(`${baseUrl}/pwa-runtime.js`);
  const app = await fetchHeaderMap(`${baseUrl}/app.js`);
  const serviceWorker = await fetchHeaderMap(`${baseUrl}/sw.js`);
  const vendor = await fetchHeaderMap(`${baseUrl}/vendor/fuse.min.js`);
  const manifest = await fetchHeaderMap(`${baseUrl}/site.webmanifest`);
  const releaseReadinessSummary = await fetchHeaderMap(`${baseUrl}/autoresearch-results/release-readiness-summary.json`);
  const verifyWorkspaceSummary = await fetchHeaderMap(`${baseUrl}/autoresearch-results/verify-workspace-summary.json`);
  const csp = root.headers["content-security-policy"] || "";
  const headerChecks = {
    root_x_content_type_options: root.headers["x-content-type-options"] === "nosniff",
    root_frame_options: root.headers["x-frame-options"] === "DENY",
    root_referrer_policy: root.headers["referrer-policy"] === "strict-origin-when-cross-origin",
    root_permissions_policy: root.headers["permissions-policy"] === "camera=(), microphone=(), geolocation=()",
    root_content_security_policy: csp.includes("default-src 'self'") && csp.includes("object-src 'none'") && csp.includes("frame-ancestors 'none'"),
    search_empty_state_cache_no_cache: searchEmptyState.headers["cache-control"] === "no-cache",
    calendar_view_cache_no_cache: calendarView.headers["cache-control"] === "no-cache",
    todo_view_cache_no_cache: todoView.headers["cache-control"] === "no-cache",
    notes_view_cache_no_cache: notesView.headers["cache-control"] === "no-cache",
    habits_view_cache_no_cache: habitsView.headers["cache-control"] === "no-cache",
    stats_view_cache_no_cache: statsView.headers["cache-control"] === "no-cache",
    llm_wiki_view_cache_no_cache: llmWikiView.headers["cache-control"] === "no-cache",
    portfolio_view_cache_no_cache: portfolioView.headers["cache-control"] === "no-cache",
    kanban_view_cache_no_cache: kanbanView.headers["cache-control"] === "no-cache",
    gantt_view_cache_no_cache: ganttView.headers["cache-control"] === "no-cache",
    team_view_cache_no_cache: teamView.headers["cache-control"] === "no-cache",
    workspace_storage_cache_no_cache: workspaceStorage.headers["cache-control"] === "no-cache",
    storage_status_view_cache_no_cache: storageStatusView.headers["cache-control"] === "no-cache",
    settings_view_cache_no_cache: settingsView.headers["cache-control"] === "no-cache",
    system_status_view_cache_no_cache: systemStatusView.headers["cache-control"] === "no-cache",
    import_guards_cache_no_cache: importGuards.headers["cache-control"] === "no-cache",
    import_ui_cache_no_cache: importUi.headers["cache-control"] === "no-cache",
    release_status_cache_no_cache: releaseStatus.headers["cache-control"] === "no-cache",
    operations_copy_actions_cache_no_cache: operationsCopyActions.headers["cache-control"] === "no-cache",
    verify_workspace_summary_runtime_cache_no_cache: verifyWorkspaceSummaryRuntime.headers["cache-control"] === "no-cache",
    dialog_shell_cache_no_cache: dialogShell.headers["cache-control"] === "no-cache",
    project_picker_cache_no_cache: projectPicker.headers["cache-control"] === "no-cache",
    global_search_cache_no_cache: globalSearch.headers["cache-control"] === "no-cache",
    command_palette_cache_no_cache: commandPalette.headers["cache-control"] === "no-cache",
    db_catalog_cache_no_cache: dbCatalog.headers["cache-control"] === "no-cache",
    review_handoff_cache_no_cache: reviewHandoff.headers["cache-control"] === "no-cache",
    review_result_view_cache_no_cache: reviewResultView.headers["cache-control"] === "no-cache",
    review_execution_checklist_cache_no_cache: reviewExecutionChecklist.headers["cache-control"] === "no-cache",
    review_issue_payload_cache_no_cache: reviewIssuePayload.headers["cache-control"] === "no-cache",
    review_result_state_cache_no_cache: reviewResultState.headers["cache-control"] === "no-cache",
    review_result_draft_state_cache_no_cache: reviewResultDraftState.headers["cache-control"] === "no-cache",
    review_creation_actions_cache_no_cache: reviewCreationActions.headers["cache-control"] === "no-cache",
    review_package_view_cache_no_cache: reviewPackageView.headers["cache-control"] === "no-cache",
    review_artifact_view_cache_no_cache: reviewArtifactView.headers["cache-control"] === "no-cache",
    review_artifact_state_cache_no_cache: reviewArtifactState.headers["cache-control"] === "no-cache",
    review_copy_actions_cache_no_cache: reviewCopyActions.headers["cache-control"] === "no-cache",
    review_submission_copy_cache_no_cache: reviewSubmissionCopy.headers["cache-control"] === "no-cache",
    review_recommendation_export_cache_no_cache: reviewRecommendationExport.headers["cache-control"] === "no-cache",
    pwa_runtime_cache_no_cache: pwaRuntime.headers["cache-control"] === "no-cache",
    app_cache_no_cache: app.headers["cache-control"] === "no-cache",
    service_worker_cache_no_cache: serviceWorker.headers["cache-control"] === "no-cache",
    release_readiness_summary_cache_no_cache: releaseReadinessSummary.headers["cache-control"] === "no-cache",
    verify_workspace_summary_cache_no_cache: verifyWorkspaceSummary.headers["cache-control"] === "no-cache",
    service_worker_content_type: String(serviceWorker.headers["content-type"] || "").startsWith("text/javascript"),
    manifest_content_type: String(manifest.headers["content-type"] || "").startsWith("application/manifest+json"),
    vendor_cache_immutable: vendor.headers["cache-control"] === "public, max-age=31536000, immutable",
  };
  return {
    status: Object.values(headerChecks).every(Boolean) ? "pass" : "fail",
    checks: headerChecks,
    responses: {
      root: root.status,
      searchEmptyState: searchEmptyState.status,
      calendarView: calendarView.status,
      todoView: todoView.status,
      notesView: notesView.status,
      habitsView: habitsView.status,
      statsView: statsView.status,
      llmWikiView: llmWikiView.status,
      portfolioView: portfolioView.status,
      kanbanView: kanbanView.status,
      ganttView: ganttView.status,
      teamView: teamView.status,
      workspaceStorage: workspaceStorage.status,
      storageStatusView: storageStatusView.status,
      settingsView: settingsView.status,
      systemStatusView: systemStatusView.status,
      importGuards: importGuards.status,
      importUi: importUi.status,
      releaseStatus: releaseStatus.status,
      operationsCopyActions: operationsCopyActions.status,
      verifyWorkspaceSummaryRuntime: verifyWorkspaceSummaryRuntime.status,
      dialogShell: dialogShell.status,
      projectPicker: projectPicker.status,
      globalSearch: globalSearch.status,
      commandPalette: commandPalette.status,
      dbCatalog: dbCatalog.status,
      reviewHandoff: reviewHandoff.status,
      reviewResultView: reviewResultView.status,
      reviewExecutionChecklist: reviewExecutionChecklist.status,
      reviewIssuePayload: reviewIssuePayload.status,
      reviewResultState: reviewResultState.status,
      reviewResultDraftState: reviewResultDraftState.status,
      reviewCreationActions: reviewCreationActions.status,
      reviewPackageView: reviewPackageView.status,
      reviewArtifactView: reviewArtifactView.status,
      reviewArtifactState: reviewArtifactState.status,
      reviewCopyActions: reviewCopyActions.status,
      reviewSubmissionCopy: reviewSubmissionCopy.status,
      reviewRecommendationExport: reviewRecommendationExport.status,
      pwaRuntime: pwaRuntime.status,
      app: app.status,
      serviceWorker: serviceWorker.status,
      releaseReadinessSummary: releaseReadinessSummary.status,
      verifyWorkspaceSummary: verifyWorkspaceSummary.status,
      manifest: manifest.status,
      vendor: vendor.status,
    },
  };
}

async function fetchTextResponse(url) {
  const response = await fetch(url, { redirect: "manual" });
  return {
    status: response.status,
    headers: Object.fromEntries([...response.headers.entries()].map(([key, value]) => [key.toLowerCase(), value])),
    body: await response.text(),
  };
}

async function smokeReleaseFallbacks(baseUrl) {
  const root = await fetchTextResponse(`${baseUrl}/`);
  const direct = await fetchTextResponse(`${baseUrl}/workspace/direct-link-check`);
  const notFound = await fetchTextResponse(`${baseUrl}/404.html`);
  const fallbackChecks = {
    direct_path_rewrites_to_index: direct.status === 200 && direct.body === root.body,
    direct_path_keeps_url_without_redirect: !direct.headers.location,
    custom_404_matches_index: notFound.status === 200 && notFound.body === root.body,
    fallback_html_content_type: String(direct.headers["content-type"] || "").startsWith("text/html"),
  };
  return {
    status: Object.values(fallbackChecks).every(Boolean) ? "pass" : "fail",
    checks: fallbackChecks,
    responses: {
      root: root.status,
      direct: direct.status,
      notFound: notFound.status,
    },
  };
}

function listen(server) {
  return new Promise((resolveListen, rejectListen) => {
    server.once("error", rejectListen);
    server.listen(requestedPort, host, () => {
      server.off("error", rejectListen);
      resolveListen(server.address().port);
    });
  });
}

function close(server) {
  return new Promise((resolveClose, rejectClose) => {
    const timer = setTimeout(() => {
      if (typeof server.destroyOpenSockets === "function") server.destroyOpenSockets();
      resolveClose();
    }, 1000);
    server.close((error) => {
      clearTimeout(timer);
      if (error) rejectClose(error);
      else resolveClose();
    });
    if (typeof server.closeIdleConnections === "function") server.closeIdleConnections();
    if (typeof server.closeAllConnections === "function") server.closeAllConnections();
    if (typeof server.destroyOpenSockets === "function") server.destroyOpenSockets();
  });
}

async function main() {
  progress(shouldPackage ? "packaging release files" : "using existing release package");
  const packageResult = shouldPackage
    ? parseJsonOutput(runNodeScript("scripts/package-release.mjs", [], {
      RELEASE_OUT_DIR: releaseDir,
    }).stdout, "fail")
    : { status: "skipped" };
  if (packageResult.status !== "pass" && packageResult.status !== "skipped") {
    throw Object.assign(new Error("release package generation failed"), {
      step: "scripts/package-release.mjs",
      stdout: JSON.stringify(packageResult, null, 2),
      stderr: "",
    });
  }

  progress("verifying release manifest");
  const verifyResult = parseJsonOutput(
    runNodeScript("scripts/verify-release.mjs", [releaseDir], {}, 90000).stdout,
    "fail",
  );
  if (verifyResult.status !== "pass") {
    throw Object.assign(new Error("release manifest verification failed"), {
      step: "scripts/verify-release.mjs",
      stdout: JSON.stringify(verifyResult, null, 2),
      stderr: "",
    });
  }

  const server = createReleaseServer();
  progress("starting release smoke server");
  const port = await listen(server);
  const baseUrl = `http://${host}:${port}`;

  let smokeResult;
  let mobileResult;
  let interactionResult;
  let deleteUndoResult;
  let accessibilityResult;
  let headerResult;
  let fallbackResult;
  try {
    progress("checking release headers");
    headerResult = await smokeReleaseHeaders(baseUrl);
    progress("checking static route fallbacks");
    fallbackResult = await smokeReleaseFallbacks(baseUrl);
    progress("running desktop route smoke");
    const smokeRun = await runRetryableBrowserScript("scripts/smoke-chrome.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
      SMOKE_RUNTIME_TIMEOUT_MS: "90000",
    }, 180000);
    smokeResult = parseJsonOutput(smokeRun.stdout, "fail");
    if (smokeRun.attempts.length > 0) smokeResult.retryAttempts = smokeRun.attempts;
    progress("running mobile layout smoke");
    const mobileRun = await runRetryableBrowserScript("scripts/smoke-mobile.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
    }, 120000);
    mobileResult = parseJsonOutput(mobileRun.stdout, "fail");
    if (mobileRun.attempts.length > 0) mobileResult.retryAttempts = mobileRun.attempts;
    progress("running interaction smoke");
    const interactionRun = await runRetryableBrowserScript("scripts/smoke-interactions.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
      SMOKE_RUNTIME_TIMEOUT_MS: "150000",
    }, 180000);
    interactionResult = parseJsonOutput(interactionRun.stdout, "fail");
    if (interactionRun.attempts.length > 0) interactionResult.retryAttempts = interactionRun.attempts;
    progress("running delete undo smoke");
    const deleteUndoRun = await runRetryableBrowserScript("scripts/smoke-delete-undo.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
    }, 120000);
    deleteUndoResult = parseJsonOutput(deleteUndoRun.stdout, "fail");
    if (deleteUndoRun.attempts.length > 0) deleteUndoResult.retryAttempts = deleteUndoRun.attempts;
    progress("running accessibility smoke");
    const accessibilityRun = await runRetryableBrowserScript("scripts/smoke-a11y.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
    }, 120000);
    accessibilityResult = parseJsonOutput(accessibilityRun.stdout, "fail");
    if (accessibilityRun.attempts.length > 0) accessibilityResult.retryAttempts = accessibilityRun.attempts;
  } finally {
    progress("stopping release smoke server");
    await close(server);
  }

  if (headerResult.status !== "pass") {
    throw Object.assign(new Error("release header smoke failed"), {
      step: "scripts/smoke-release.mjs:headers",
      stdout: JSON.stringify(headerResult, null, 2),
      stderr: "",
    });
  }
  if (fallbackResult.status !== "pass") {
    throw Object.assign(new Error("release fallback smoke failed"), {
      step: "scripts/smoke-release.mjs:fallbacks",
      stdout: JSON.stringify(fallbackResult, null, 2),
      stderr: "",
    });
  }
  if (smokeResult.status !== "pass") {
    throw Object.assign(new Error("release browser smoke failed"), {
      step: "scripts/smoke-chrome.mjs",
      stdout: JSON.stringify(smokeResult, null, 2),
      stderr: "",
    });
  }
  if (mobileResult.status !== "pass") {
    throw Object.assign(new Error("release mobile smoke failed"), {
      step: "scripts/smoke-mobile.mjs",
      stdout: JSON.stringify(mobileResult, null, 2),
      stderr: "",
    });
  }
  const desktopRouteCount = Number(smokeResult.routeCount || 0);
  const mobileRouteCount = Number(mobileResult.routeCount || 0);
  const routeParity = {
    status: desktopRouteCount >= 17 && mobileRouteCount >= 17 && desktopRouteCount === mobileRouteCount ? "pass" : "fail",
    minimumRouteCount: 17,
    desktopRouteCount,
    mobileRouteCount,
  };
  if (routeParity.status !== "pass") {
    throw Object.assign(new Error("release route smoke parity failed"), {
      step: "scripts/smoke-release.mjs:route-parity",
      stdout: JSON.stringify(routeParity, null, 2),
      stderr: "",
    });
  }
  if (interactionResult.status !== "pass") {
    throw Object.assign(new Error("release interaction smoke failed"), {
      step: "scripts/smoke-interactions.mjs",
      stdout: JSON.stringify(interactionResult, null, 2),
      stderr: "",
    });
  }
  if (deleteUndoResult.status !== "pass") {
    throw Object.assign(new Error("release delete undo smoke failed"), {
      step: "scripts/smoke-delete-undo.mjs",
      stdout: JSON.stringify(deleteUndoResult, null, 2),
      stderr: "",
    });
  }
  if (accessibilityResult.status !== "pass") {
    throw Object.assign(new Error("release accessibility smoke failed"), {
      step: "scripts/smoke-a11y.mjs",
      stdout: JSON.stringify(accessibilityResult, null, 2),
      stderr: "",
    });
  }

  const resultPayload = {
    status: "pass",
    releaseDir: relative(root, releaseDir),
    baseUrl,
    package: packageResult,
    verify: verifyResult,
    headers: headerResult,
    fallbacks: fallbackResult,
    routeParity,
    smoke: {
      status: smokeResult.status,
      routeCount: smokeResult.routeCount,
      retryAttempts: smokeResult.retryAttempts || [],
      viewport: smokeResult.viewport,
      layoutIssues: smokeResult.layoutIssues,
      consoleIssues: smokeResult.consoleIssues,
      networkIssues: smokeResult.networkIssues,
      failures: smokeResult.failures,
    },
    mobile: {
      status: mobileResult.status,
      routeCount: mobileResult.routeCount,
      retryAttempts: mobileResult.retryAttempts || [],
      viewport: mobileResult.viewport,
      searchEmpty: mobileResult.searchEmptyMobileReport ? {
        status: mobileResult.searchEmptyMobileReport.status,
        expectedRouteCount: mobileResult.searchEmptyMobileReport.expectedRouteCount,
        expectedRoutes: mobileResult.searchEmptyMobileReport.expectedRoutes || [],
        searchInertRoutes: mobileResult.searchEmptyMobileReport.searchInertRoutes || [],
        issueCount: mobileResult.search_empty_mobile_issue_count || 0,
      } : null,
      uiSurfaces: {
        palette: mobileResult.paletteMobileReport?.status || "missing",
        projectPicker: mobileResult.projectPickerMobileReport?.status || "missing",
        notificationSheet: mobileResult.notificationSheetMobileReport?.status || "missing",
        sheetActions: mobileResult.sheetActionReport?.status || "missing",
        modalTouch: mobileResult.modalTouchReport?.status || "missing",
      },
      layoutIssues: mobileResult.layoutIssues,
      consoleIssues: mobileResult.consoleIssues,
      networkIssues: mobileResult.networkIssues,
      failures: mobileResult.failures,
    },
    interactions: {
      status: interactionResult.status,
      stepCount: interactionResult.steps ? interactionResult.steps.length : 0,
      retryAttempts: interactionResult.retryAttempts || [],
      persistedChecks: interactionResult.persistedChecks,
      consoleIssues: interactionResult.consoleIssues,
      networkIssues: interactionResult.networkIssues,
      failures: interactionResult.failures,
    },
    deleteUndo: {
      status: deleteUndoResult.status,
      retryAttempts: deleteUndoResult.retryAttempts || [],
      checkedTypes: deleteUndoResult.checkedTypes || [],
      persisted: deleteUndoResult.persisted === true,
      failures: deleteUndoResult.failures || [],
    },
    accessibility: {
      status: accessibilityResult.status,
      retryAttempts: accessibilityResult.retryAttempts || [],
      checks: accessibilityResult.checks,
      consoleIssues: accessibilityResult.consoleIssues,
      networkIssues: accessibilityResult.networkIssues,
      failures: accessibilityResult.failures,
    },
  };
  const cache = writePackagedBrowserGateCache(resultPayload);

  console.log(JSON.stringify({
    ...resultPayload,
    cache,
  }, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({
    status: "fail",
    step: error.step || "scripts/smoke-release.mjs",
    message: error.message,
    stdout: error.stdout || "",
    stderr: error.stderr || "",
    attempts: error.attempts || [],
  }, null, 2));
  process.exit(1);
});
