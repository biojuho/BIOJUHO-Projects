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
  return {
    status: matches.length >= 8 && missing.length === 0 ? "pass" : "fail",
    source: payload?.source || "",
    generatedAt: payload?.generatedAt || "",
    candidates: matches.length,
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
  return {
    status: matches.length >= 14 && missing.length === 0 && sourceMarked && apiMarked ? "pass" : "fail",
    source,
    generatedAt: payload?.generatedAt || "",
    candidates: matches.length,
    sourceMarked,
    apiMarked,
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

function smokeRelease() {
  const releaseOutDir = mkdtempSync(join(tmpdir(), "joopark-release-smoke-"));
  let result;
  try {
    result = run(process.execPath, ["scripts/smoke-release.mjs"], {
      timeout: 180000,
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
