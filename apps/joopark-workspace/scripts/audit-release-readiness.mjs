#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const args = new Set(process.argv.slice(2));
const format = args.has("--format=markdown") || args.has("--markdown") ? "markdown" : "json";
const runGates = args.has("--run-gates");

const runtimeFiles = [
  "index.html",
  "app.js",
  "styles.css",
  "favicon.svg",
  "README.md",
  "data/repos.json",
  "data/adoption-candidates.json",
  "vendor/LICENSES.md",
  "vendor/fuse.min.js",
  "vendor/marked.umd.js",
  "vendor/purify.min.js",
];

const releaseScripts = [
  "scripts/package-release.mjs",
  "scripts/verify-release.mjs",
  "scripts/smoke-chrome.mjs",
  "scripts/smoke-mobile.mjs",
  "scripts/smoke-interactions.mjs",
  "scripts/smoke-a11y.mjs",
  "scripts/smoke-release.mjs",
];

const workflowFiles = [
  "docs/github-pages-workflow.yml",
];

const workflowHandoffScripts = [
  "scripts/prepare-github-pages-workflow.mjs",
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

const appMarkers = [
  { id: "calendar_crud", file: "app.js", terms: ["function openEventModal", "function saveEventFromForm", "function deleteEvent"] },
  { id: "todo_crud", file: "app.js", terms: ["function quickAddTodo", "function saveTodoFromForm", "function toggleTodo", "function deleteTodo"] },
  { id: "notes_markdown", file: "app.js", terms: ["function renderMarkdown", "function saveNoteFromForm", "DOMPurify.sanitize"] },
  { id: "habit_tracker", file: "app.js", terms: ["function saveHabitFromForm", "function toggleHabit", "function habitStreak"] },
  { id: "pm_crud", file: "app.js", terms: ["function saveProjectFromForm", "function saveIssueFromForm", "function saveTaskFromForm", "function saveMemberFromForm"] },
  { id: "db_catalog_crud", file: "app.js", terms: ["function saveInstanceFromForm", "function saveTableFromForm", "function saveQueryFromForm", "function saveMigrationFromForm"] },
  { id: "command_palette", file: "app.js", terms: ["function openPalette", "function renderPaletteResults", "_buildPaletteItems"] },
  { id: "persistence", file: "app.js", terms: ["joopark.workspace.v3", "function persist", "function loadPersisted"] },
  { id: "storage_health", file: "app.js", terms: ["function refreshStorageHealth", "navigator.storage", "data-storage-health", "requestStoragePersistence"] },
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
];

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: root,
    env: { ...process.env, ...(options.env || {}) },
    encoding: "utf-8",
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

function read(relPath) {
  return readFileSync(join(root, relPath), "utf-8");
}

function fileExists(relPath) {
  const path = join(root, relPath);
  return existsSync(path) && statSync(path).isFile();
}

function hasTerms(relPath, terms) {
  if (!fileExists(relPath)) return { status: "fail", missing: terms };
  const text = read(relPath);
  const missing = terms.filter((term) => !text.includes(term));
  return { status: missing.length === 0 ? "pass" : "fail", missing };
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
  if (!fileExists(relPath)) return { status: "fail", reason: "missing" };
  const manifest = parseJson(read(relPath));
  const missing = [];
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return { status: "fail", reason: "invalid JSON object" };
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
  return {
    status: missing.length === 0 ? "pass" : "fail",
    sourceCommit: manifest.sourceCommit || "",
    source: manifest.source || null,
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
  const result = run(process.execPath, ["scripts/verify-release.mjs"], { timeout: 30000 });
  const payload = parseJson(result.stdout);
  return {
    status: result.ok && payload && payload.status === "pass" ? "pass" : "fail",
    command: "node scripts/verify-release.mjs",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function githubPagesWorkflowHandoffDryRun() {
  const result = run(process.execPath, ["scripts/prepare-github-pages-workflow.mjs", "--dry-run"], { timeout: 15000 });
  const payload = parseJson(result.stdout);
  return {
    status: result.ok && payload && payload.status === "pass" && payload.mode === "dry-run" && payload.willWrite === false && payload.targetRepositoryPath === ".github/workflows/joopark-pages.yml" ? "pass" : "fail",
    command: "node scripts/prepare-github-pages-workflow.mjs --dry-run",
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

function smokeRelease() {
  const releaseOutDir = mkdtempSync(join(tmpdir(), "joopark-release-smoke-"));
  let result;
  try {
    result = run(process.execPath, ["scripts/smoke-release.mjs"], {
      timeout: 300000,
      env: { RELEASE_OUT_DIR: releaseOutDir },
    });
  } finally {
    rmSync(releaseOutDir, { recursive: true, force: true });
  }
  const payload = parseJson(result.stdout);
  return {
    status: result.ok && payload && payload.status === "pass" ? "pass" : "fail",
    command: "RELEASE_OUT_DIR=<temp> node scripts/smoke-release.mjs",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function buildChecklist() {
  const checklist = [];
  const gateEvidence = runGates ? smokeRelease() : null;
  const verify = verifyRelease();

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

  const workflowEvidence = workflowFiles.map((path) => ({ path, exists: fileExists(path) }));
  checklist.push({
    id: "release_publish_workflow_template_files",
    requirement: "GitHub Pages publish workflow template files exist before claiming publish workflow readiness.",
    status: workflowEvidence.every((item) => item.exists) ? "pass" : "fail",
    evidence: workflowEvidence,
  });

  const workflowHandoffDryRun = githubPagesWorkflowHandoffDryRun();
  const workflowHandoffTerms = [
    { file: "scripts/prepare-github-pages-workflow.mjs", terms: ["--dry-run", "--write", "--check-scope", "workflowScopeRequired", "workflowScopeAvailable", "missing workflow scope", "docs/github-pages-workflow.yml", ".github/workflows/joopark-pages.yml", "willWrite", "gitRoot", "rev-parse", "--show-toplevel", "targetRepositoryPath"] },
    { file: "README.md", terms: ["node scripts/prepare-github-pages-workflow.mjs --dry-run", "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope", "node scripts/prepare-github-pages-workflow.mjs --write", "repository root", "workflowScopeAvailable", "workflow` scope"] },
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

  const bridgePlan = mainBridgePlan();
  const prBridgeTerms = [
    { file: "scripts/plan-main-bridge.mjs", terms: ["merge-base", "noCommonHistory", "apps/joopark-workspace", "codex/joopark-workspace-main-bridge", "main-subdirectory-bridge", "pr-ready-main-history"] },
    { file: "README.md", terms: ["node scripts/plan-main-bridge.mjs", "no common history", "apps/joopark-workspace", "codex/joopark-workspace-main-bridge"] },
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

  const tempReleaseTerms = [
    { file: "scripts/package-release.mjs", terms: ["process.env.RELEASE_OUT_DIR", "resolve(root, process.env.RELEASE_OUT_DIR)"] },
    { file: "scripts/smoke-release.mjs", terms: ["process.env.RELEASE_OUT_DIR", "RELEASE_OUT_DIR: releaseDir", "runNodeScript(\"scripts/verify-release.mjs\", [releaseDir]"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["mkdtempSync", "joopark-release-smoke-", "RELEASE_OUT_DIR: releaseOutDir"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "release_smoke_temp_output",
    requirement: "The full release smoke can package and verify into a temporary directory, preserving the checked release artifact while still testing a fresh package.",
    status: tempReleaseTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: tempReleaseTerms,
  });

  const deploySupportTerms = [
    { file: "scripts/package-release.mjs", terms: ["function writeDeploySupportFiles", "404.html", "_headers", "_redirects", "vercel.json"] },
    { file: "scripts/verify-release.mjs", terms: ["function verifyDeploySupport", "expectedDeploySupportFiles", "deploySupportFiles"] },
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
    { file: "scripts/smoke-release.mjs", terms: ["function smokeReleaseHeaders", "headerChecks", "root_x_content_type_options", "vendor_cache_immutable"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["release_header_smoke", "The packaged release smoke applies release header rules"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const releaseHeaderGateOk = !gateEvidence || gateEvidence.result?.headers?.status === "pass";
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

  const releaseFallbackSmokeTerms = [
    { file: "scripts/package-release.mjs", terms: ["/* /index.html 200"] },
    { file: "scripts/verify-release.mjs", terms: ["/* /index.html 200", "rewrite unmatched direct paths to index.html"] },
    { file: "scripts/smoke-release.mjs", terms: ["function smokeReleaseFallbacks", "fallbackChecks", "direct_path_rewrites_to_index", "custom_404_matches_index"] },
    { file: "scripts/audit-release-readiness.mjs", terms: ["release_fallback_smoke", "The packaged release smoke verifies direct-path fallback"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  const releaseFallbackGateOk = !gateEvidence || gateEvidence.result?.fallbacks?.status === "pass";
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

  const pagesWorkflowTerms = [
    { file: "docs/github-pages-workflow.yml", terms: ["workflow_dispatch:", "codex/joopark-workspace-release", "permissions:", "pages: write", "id-token: write", "actions/configure-pages@v5", "actions/upload-pages-artifact@v3", "actions/deploy-pages@v4", "node scripts/package-release.mjs", "node scripts/verify-release.mjs", "path: dist/release"] },
    { file: "README.md", terms: ["docs/github-pages-workflow.yml", "Publish JooPark Pages", "workflow_dispatch", "GitHub Pages artifact", "workflow` scope"] },
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
    requirement: "The SPA exposes the 15 expected workspace, PM, DB, and settings views.",
    status: indexTerms.status,
    evidence: { file: "index.html", expectedViews: viewIds.length, missingViews: indexTerms.missing },
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
    { file: "app.js", terms: ["function refreshStorageHealth", "typeof manager.estimate", "typeof manager.persisted", "data-storage-health"] },
    { file: "styles.css", terms: [".storage-health", ".storage-meter", ".storage-grid"] },
    { file: "README.md", terms: ["저장소 상태", "navigator.storage.estimate", "영속 저장"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["storage health status", "data-storage-health"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "storage_health_monitoring",
    requirement: "The settings surface shows browser storage usage, quota estimate, persistence state, and verifies the panel in the interaction smoke.",
    status: storageTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: storageTerms,
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

  const snapshots = ["data/repos.json", "data/adoption-candidates.json"].map((path) => ({ path, ...dataSnapshot(path) }));
  checklist.push({
    id: "github_snapshot_data",
    requirement: "GitHub and adoption-candidate project snapshots are valid local JSON seed data.",
    status: snapshots.every((item) => item.status === "pass") ? "pass" : "fail",
    evidence: snapshots,
  });

  const freshnessDriftFiles = freshnessDriftScripts.map((path) => ({ path, exists: fileExists(path) }));
  const freshnessDriftTerms = [
    { file: "scripts/check-candidate-freshness-drift.mjs", terms: ["--snapshot-only", "--live", "--fail-on-drift", "--repo", "repoFilters", "driftCount", "lastCommit", "pushedAt"] },
    { file: "README.md", terms: ["check-candidate-freshness-drift.mjs", "--snapshot-only", "--live", "--fail-on-drift", "--repo", "candidate freshness drift"] },
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
    { file: "scripts/check-candidate-freshness-drift.mjs", terms: ["--cadence-policy", "candidate-freshness-drift-cadence-v1", "highChurnRepos", "repoScopedHighChurn", "--fail-on-drift"] },
    { file: "README.md", terms: ["--cadence-policy", "high-churn", "Veritas-7/autoresearch-skill-system", "--fail-on-drift"] },
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
    cadenceHighChurnRepos.some((item) => item.repo === "Veritas-7/autoresearch-skill-system" && item.monitored && item.inScope),
  );
  checklist.push({
    id: "candidate_freshness_drift_cadence_policy",
    requirement: "High-churn adoption-candidate sources have a repo-scoped refresh cadence before fail-on-drift automation is enabled.",
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
    { file: "app.js", terms: ["PORTFOLIO_FILTERS", "function setPortfolioFilter", "data-action=\"portfolio-filter\""] },
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
    { file: "app.js", terms: ["CANDIDATE_ACTION_FILTERS", "function setPortfolioActionFilter", "data-candidate-action-filter-panel", "data-action=\"portfolio-action-filter\""] },
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
    { file: "app.js", terms: ["CANDIDATE_BENCHMARK_FILTERS", "function setPortfolioBenchmarkFilter", "function sortBenchmarkFocusProjects", "function candidateBenchmarkQueueSummary", "data-candidate-benchmark-filter-panel", "data-candidate-benchmark-summary"] },
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

  const knowledgeBaseInformationArchitectureExportTerms = [
    { file: "app.js", terms: ["function knowledgeBaseBenchmarkRecommendationMarkdown", "function candidateKnowledgeBaseRecommendationExport", "data-knowledge-base-benchmark-export", "joopark-kb-ia-recommendation.md"] },
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
    { file: "app.js", terms: ["function candidateKnowledgeBaseReviewHandoff", "function knowledgeBaseReviewHandoffMarkdown", "data-knowledge-base-review-handoff", "joopark-kb-ia-review-handoff.md"] },
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
    { file: "app.js", terms: ["data-kb-review-handoff-copy", "data-kb-review-handoff-copy-status", "[data-benchmark-review-handoff], [data-knowledge-base-review-handoff]"] },
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
    { file: "app.js", terms: ["function knowledgeBaseReviewIssueDraft", "function candidateKnowledgeBaseReviewIssueDraft", "data-kb-review-issue-draft", "data-kb-review-issue-create", "data-issue-draft-labels"] },
    { file: "styles.css", terms: [".portfolio-review-issue-draft", ".portfolio-issue-draft-grid", ".portfolio-issue-draft-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["knowledgeBaseBenchmarkReviewIssueDraftVisible", "knowledge-base review issue draft did not create an issue", "knowledge-base review issue draft did not persist source key"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "knowledge_base_information_architecture_review_issue_draft",
    requirement: "The dedicated knowledge-base information-architecture review handoff can be converted into a PM issue draft with stable source key, labels, and browser smoke coverage.",
    status: knowledgeBaseInformationArchitectureReviewIssueDraftTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: knowledgeBaseInformationArchitectureReviewIssueDraftTerms,
  });

  const taskosaurWorkstreamBenchmarkRecommendationExportTerms = [
    { file: "app.js", terms: ["function candidateBenchmarkRecommendationExport", "function candidateBenchmarkRecommendationMarkdown", "data-candidate-benchmark-export", "joopark-benchmark-recommendation.md"] },
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
    { file: "app.js", terms: ["function candidateBenchmarkReviewQueueHandoff", "function candidateBenchmarkReviewQueueMarkdown", "data-benchmark-review-handoff", "joopark-benchmark-review-queue.md"] },
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
    { file: "app.js", terms: ["function copyBenchmarkReviewHandoff", "function writeClipboardText", "data-review-handoff-copy", "data-review-handoff-copy-status"] },
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
    { file: "app.js", terms: ["function benchmarkReviewIssueDraft", "function candidateBenchmarkReviewIssueDraft", "function createBenchmarkReviewIssue", "data-review-issue-draft", "data-review-issue-create"] },
    { file: "styles.css", terms: [".portfolio-review-issue-draft", ".portfolio-issue-draft-grid", ".portfolio-issue-draft-body"] },
    { file: "scripts/smoke-interactions.mjs", terms: ["candidateBenchmarkReviewIssueDraftVisible", "benchmark review issue draft did not create an issue", "benchmark review issue draft did not persist source key"] },
  ].map((item) => ({ file: item.file, missingTerms: hasTerms(item.file, item.terms).missing }));
  checklist.push({
    id: "taskosaur_workstream_benchmark_review_issue_draft",
    requirement: "Taskosaur benchmark review handoff decisions can be converted into a PM issue draft with stable source key, priority, labels, and browser smoke coverage.",
    status: taskosaurWorkstreamBenchmarkReviewIssueDraftTerms.every((item) => item.missingTerms.length === 0) ? "pass" : "fail",
    evidence: taskosaurWorkstreamBenchmarkReviewIssueDraftTerms,
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

  checklist.push({
    id: "manifest_integrity",
    requirement: "The release manifest matches actual packaged runtime files by path, byte count, and SHA-256.",
    status: verify.status,
    evidence: verify,
  });

  const provenance = releaseManifestProvenance();
  checklist.push({
    id: "release_source_provenance",
    requirement: "The release manifest records source commit, branch, dirty state, and dirty file paths so packaged artifacts remain traceable even before commit.",
    status: provenance.status,
    evidence: provenance,
  });

  if (gateEvidence) {
    checklist.push({
      id: "packaged_browser_gates",
      requirement: "The packaged release passes route smoke, mobile layout smoke, click/input interaction smoke, and keyboard/ARIA accessibility smoke from a temporary local server.",
      status: gateEvidence.status,
      evidence: gateEvidence,
    });
  } else {
    checklist.push({
      id: "packaged_browser_gates",
      requirement: "The packaged release passes route smoke, mobile layout smoke, click/input interaction smoke, and keyboard/ARIA accessibility smoke from a temporary local server.",
      status: "not_run",
      evidence: { command: "node scripts/audit-release-readiness.mjs --run-gates" },
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
    checklist,
  };
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
    "## Checklist",
  ];
  for (const item of payload.checklist) {
    lines.push(`- ${item.status}: \`${item.id}\` - ${item.requirement}`);
  }
  lines.push("", "## Git", "```", payload.gitStatus, "```");
  lines.push("", "## Blockers");
  const blockers = payload.checklist.filter((item) => item.status === "blocked" || item.status === "not_run" || item.status === "fail");
  if (blockers.length === 0) {
    lines.push("- none");
  } else {
    for (const item of blockers) lines.push(`- ${item.id}: ${item.status}`);
  }
  return `${lines.join("\n")}\n`;
}

const payload = audit();
if (format === "markdown") console.log(markdown(payload));
else console.log(JSON.stringify(payload, null, 2));
if (payload.status !== "pass") process.exit(1);
