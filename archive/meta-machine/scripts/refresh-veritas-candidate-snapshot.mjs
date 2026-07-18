#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dataPath = join(root, "data/adoption-candidates.json");
const args = new Set(process.argv.slice(2));
const write = args.has("--write");
const snapshotOnly = args.has("--snapshot-only");
const failOnChange = args.has("--fail-on-change");
const repoName = "Veritas-7/autoresearch-skill-system";
const commitPattern = /^[0-9a-f]{40}$/i;

function readSnapshot() {
  const text = readFileSync(dataPath, "utf-8");
  const payload = JSON.parse(text);
  const projects = Array.isArray(payload.projects) ? payload.projects : [];
  const projectIndex = projects.findIndex((project) => project.name === repoName);
  return {
    text,
    payload,
    projects,
    projectIndex,
    project: projectIndex >= 0 ? projects[projectIndex] : null,
    sourceMarkers: String(payload.source || "")
      .split("+")
      .filter((item) => item.startsWith("github-api:")),
  };
}

function versionFromHeadline(headline) {
  const match = String(headline || "").match(/^v(\d+\.\d+)\b/);
  return match ? match[1] : "";
}

function markerForVersion(version) {
  if (!version) return "github-api:veritas-focused-drift-refresh";
  return `github-api:veritas-focused-drift-refresh-v${version.replace(/\D/g, "")}`;
}

function descriptionFromHeadline(headline) {
  const version = versionFromHeadline(headline);
  const title = String(headline || "").replace(/^v\d+\.\d+\s*/, "").trim() || "upstream HEAD";
  if (!version) return `최신 ${title}을 갖춘 제품화 기준 AutoResearch 스킬 진화 하네스`;
  return `v${version} 최신 ${title}을 갖춘 제품화 기준 AutoResearch 스킬 진화 하네스`;
}

function toKstTimestamp(date = new Date()) {
  const kst = new Date(date.getTime() + 9 * 60 * 60 * 1000);
  return kst.toISOString().replace(/\.\d{3}Z$/, "+09:00");
}

function fetchLiveSnapshot() {
  const query = `query VeritasCandidateSnapshot {
    repository(owner: "Veritas-7", name: "autoresearch-skill-system") {
      nameWithOwner
      stargazerCount
      forkCount
      diskUsage
      pushedAt
      createdAt
      openIssues: issues(states: OPEN) { totalCount }
      openPRs: pullRequests(states: OPEN) { totalCount }
      defaultBranchRef {
        name
        target {
          oid
          ... on Commit {
            committedDate
            messageHeadline
          }
        }
      }
    }
  }`;
  const result = spawnSync("gh", ["api", "graphql", "-f", `query=${query}`], {
    cwd: root,
    encoding: "utf-8",
    timeout: 45000,
    killSignal: "SIGKILL",
  });
  if (result.status !== 0 || result.error) {
    return {
      ok: false,
      error: result.error ? result.error.message : result.stderr.trim() || "gh api graphql failed",
      stderr: result.stderr.trim(),
    };
  }
  const payload = JSON.parse(result.stdout);
  if (Array.isArray(payload.errors) && payload.errors.length > 0) {
    return {
      ok: false,
      error: "graphql errors",
      errors: payload.errors,
    };
  }
  return {
    ok: true,
    repo: payload.data?.repository || null,
  };
}

function liveFields(repo) {
  const commit = repo?.defaultBranchRef?.target || {};
  return {
    description: descriptionFromHeadline(commit.messageHeadline),
    openIssues: repo?.openIssues?.totalCount,
    openPRs: repo?.openPRs?.totalCount,
    stars: repo?.stargazerCount,
    forks: repo?.forkCount,
    diskKb: repo?.diskUsage,
    pushedAt: repo?.pushedAt || "",
    createdAt: repo?.createdAt || "",
    lastCommit: commit.oid || "",
    defaultBranch: repo?.defaultBranchRef?.name || "",
    committedAt: commit.committedDate || "",
    messageHeadline: commit.messageHeadline || "",
  };
}

function addSourceMarker(source, marker) {
  const parts = String(source || "").split("+").filter(Boolean);
  if (!parts.includes(marker)) parts.push(marker);
  return parts.join("+");
}

function projectSummary(project) {
  if (!project) return null;
  return {
    description: project.description || "",
    openIssues: project.openIssues,
    openPRs: project.openPRs,
    stars: project.stars,
    forks: project.forks,
    diskKb: project.diskKb,
    pushedAt: project.pushedAt || "",
    createdAt: project.createdAt || "",
    lastCommit: project.lastCommit || "",
  };
}

function replaceStringField(text, field, value) {
  const pattern = new RegExp(`("${field}"\\s*:\\s*)"[^"]*"`);
  if (!pattern.test(text)) throw new Error(`missing string field ${field}`);
  return text.replace(pattern, `$1${JSON.stringify(value)}`);
}

function replaceNumberField(text, field, value) {
  const pattern = new RegExp(`("${field}"\\s*:\\s*)-?\\d+`);
  if (!pattern.test(text)) throw new Error(`missing number field ${field}`);
  return text.replace(pattern, `$1${Number(value)}`);
}

function replaceProjectFields(text, nextProject) {
  const nameNeedle = `"name": "${repoName}"`;
  const nameIndex = text.indexOf(nameNeedle);
  if (nameIndex < 0) throw new Error("missing Veritas project block");
  const start = text.lastIndexOf("\n    {", nameIndex);
  const nextStart = text.indexOf("\n    {", nameIndex + nameNeedle.length);
  const arrayEnd = text.indexOf("\n  ]", nameIndex);
  const end = nextStart >= 0 && nextStart < arrayEnd ? nextStart : arrayEnd;
  if (start < 0 || end < 0) throw new Error("invalid Veritas project block bounds");
  let block = text.slice(start, end);
  block = replaceStringField(block, "description", nextProject.description);
  block = replaceNumberField(block, "openIssues", nextProject.openIssues);
  block = replaceNumberField(block, "openPRs", nextProject.openPRs);
  block = replaceNumberField(block, "stars", nextProject.stars);
  block = replaceNumberField(block, "forks", nextProject.forks);
  block = replaceNumberField(block, "diskKb", nextProject.diskKb);
  block = replaceStringField(block, "pushedAt", nextProject.pushedAt);
  block = replaceStringField(block, "createdAt", nextProject.createdAt);
  block = replaceStringField(block, "lastCommit", nextProject.lastCommit);
  return `${text.slice(0, start)}${block}${text.slice(end)}`;
}

function formatSnapshotText(snapshot, nextPayload) {
  let text = snapshot.text;
  text = replaceStringField(text, "generatedAt", nextPayload.generatedAt);
  text = replaceStringField(text, "source", nextPayload.source);
  text = replaceProjectFields(text, nextPayload.projects[snapshot.projectIndex]);
  return text.endsWith("\n") ? text : `${text}\n`;
}

function finish(status, extra = {}) {
  console.log(JSON.stringify({
    status,
    mode: snapshotOnly ? "snapshot-only" : (write ? "write" : "dry-run"),
    repo: repoName,
    willWrite: write && !snapshotOnly,
    failOnChange: failOnChange && !snapshotOnly,
    ...extra,
  }, null, 2));
  process.exit(status === "pass" ? 0 : 1);
}

const snapshot = readSnapshot();
if (!snapshot.project) {
  finish("fail", {
    reason: "missing Veritas adoption candidate",
    generatedAt: snapshot.payload.generatedAt || "",
  });
}

if (snapshotOnly) {
  const sourceMarked = snapshot.sourceMarkers.some((marker) => marker.startsWith("github-api:veritas"));
  finish(commitPattern.test(String(snapshot.project.lastCommit || "")) && sourceMarked ? "pass" : "fail", {
    generatedAt: snapshot.payload.generatedAt || "",
    sourceMarkers: snapshot.sourceMarkers.length,
    checks: {
      projectExists: true,
      commitShape: commitPattern.test(String(snapshot.project.lastCommit || "")),
      sourceMarked,
      liveNetwork: false,
      explicitWrite: false,
    },
    snapshot: projectSummary(snapshot.project),
  });
}

const live = fetchLiveSnapshot();
if (!live.ok || !live.repo) {
  finish("blocked", {
    reason: live.error || "missing live repository",
    stderr: live.stderr || "",
  });
}

const fields = liveFields(live.repo);
if (!commitPattern.test(fields.lastCommit)) {
  finish("fail", {
    reason: "live default branch commit is invalid",
    live: fields,
  });
}

const version = versionFromHeadline(fields.messageHeadline);
const marker = markerForVersion(version);
const nextPayload = JSON.parse(JSON.stringify(snapshot.payload));
const nextProject = nextPayload.projects[snapshot.projectIndex];
for (const field of ["description", "openIssues", "openPRs", "stars", "forks", "diskKb", "pushedAt", "createdAt", "lastCommit"]) {
  nextProject[field] = fields[field];
}
nextPayload.source = addSourceMarker(nextPayload.source, marker);
const changedBeforeTimestamp = JSON.stringify(nextPayload) !== JSON.stringify(snapshot.payload);
if (changedBeforeTimestamp) nextPayload.generatedAt = toKstTimestamp();
const changed = JSON.stringify(nextPayload) !== JSON.stringify(snapshot.payload);

if (write && changed) {
  writeFileSync(dataPath, formatSnapshotText(snapshot, nextPayload), "utf-8");
}

finish(failOnChange && changed ? "drift" : "pass", {
  changed,
  wrote: write && changed ? "data/adoption-candidates.json" : "",
  generatedAt: changed ? nextPayload.generatedAt : snapshot.payload.generatedAt || "",
  sourceMarker: marker,
  defaultBranch: fields.defaultBranch,
  committedAt: fields.committedAt,
  messageHeadline: fields.messageHeadline,
  before: projectSummary(snapshot.project),
  after: projectSummary(nextProject),
});
