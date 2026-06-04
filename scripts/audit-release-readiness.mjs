#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
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
  const result = run(process.execPath, ["scripts/smoke-release.mjs"], { timeout: 180000 });
  const payload = parseJson(result.stdout);
  return {
    status: result.ok && payload && payload.status === "pass" ? "pass" : "fail",
    command: "node scripts/smoke-release.mjs",
    result: payload || { stdout: result.stdout.trim(), stderr: result.stderr.trim(), error: result.error },
  };
}

function buildChecklist() {
  const checklist = [];
  const gateEvidence = runGates ? smokeRelease() : null;

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
    requirement: "Release packaging, manifest verification, route smoke, mobile layout smoke, interaction smoke, and full release gate scripts exist.",
    status: scriptEvidence.every((item) => item.exists) ? "pass" : "fail",
    evidence: scriptEvidence,
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

  const docTerms = hasTerms("README.md", [
    "node scripts/smoke-release.mjs",
    "node scripts/smoke-mobile.mjs",
    "node scripts/smoke-interactions.mjs",
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

  const verify = verifyRelease();
  checklist.push({
    id: "manifest_integrity",
    requirement: "The release manifest matches actual packaged runtime files by path, byte count, and SHA-256.",
    status: verify.status,
    evidence: verify,
  });

  if (gateEvidence) {
    checklist.push({
      id: "packaged_browser_gates",
      requirement: "The packaged release passes route smoke, mobile layout smoke, and click/input interaction smoke from a temporary local server.",
      status: gateEvidence.status,
      evidence: gateEvidence,
    });
  } else {
    checklist.push({
      id: "packaged_browser_gates",
      requirement: "The packaged release passes route smoke, mobile layout smoke, and click/input interaction smoke from a temporary local server.",
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
