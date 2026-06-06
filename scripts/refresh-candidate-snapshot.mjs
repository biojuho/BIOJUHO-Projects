#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dataPath = join(root, "data/adoption-candidates.json");
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const write = args.has("--write");
const snapshotOnly = args.has("--snapshot-only");
const failOnChange = args.has("--fail-on-change");
const commitPattern = /^[0-9a-f]{40}$/i;
const repoFilter = normalizeRepoFilter(optionValue("--repo") || "");

function optionValue(flag) {
  for (let index = 0; index < rawArgs.length; index += 1) {
    const item = rawArgs[index];
    if (item === flag && rawArgs[index + 1] && !rawArgs[index + 1].startsWith("--")) return rawArgs[index + 1];
    if (item.startsWith(`${flag}=`)) return item.slice(flag.length + 1);
  }
  return "";
}

function normalizeRepoFilter(value) {
  return String(value || "")
    .trim()
    .replace(/^https:\/\/github\.com\//i, "")
    .replace(/\/+$/g, "")
    .toLowerCase();
}

function githubRepo(url) {
  const match = String(url || "").match(/^https:\/\/github\.com\/([^/\s]+)\/([^/\s#?]+)\/?$/i);
  if (!match) return null;
  return {
    owner: match[1],
    name: match[2],
    nameWithOwner: `${match[1]}/${match[2]}`,
    filter: `${match[1]}/${match[2]}`.toLowerCase(),
  };
}

function repoSlug(repo) {
  return String(repo?.nameWithOwner || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function toKstTimestamp(date = new Date()) {
  const kst = new Date(date.getTime() + 9 * 60 * 60 * 1000);
  return kst.toISOString().replace(/\.\d{3}Z$/, "+09:00");
}

function readSnapshot() {
  const text = readFileSync(dataPath, "utf-8");
  const payload = JSON.parse(text);
  const projects = Array.isArray(payload.projects) ? payload.projects : [];
  const enriched = projects.map((project, index) => ({ project, index, repo: githubRepo(project.url) }));
  const match = enriched.find((item) => item.repo && item.repo.filter === repoFilter);
  return {
    text,
    payload,
    projects,
    projectIndex: match ? match.index : -1,
    project: match ? match.project : null,
    repo: match ? match.repo : null,
    sourceMarkers: String(payload.source || "")
      .split("+")
      .filter((item) => item.startsWith("github-api:")),
  };
}

function graphqlString(value) {
  return JSON.stringify(String(value));
}

function fetchLiveSnapshot(repo) {
  const query = `query CandidateSnapshot {
    repository(owner: ${graphqlString(repo.owner)}, name: ${graphqlString(repo.name)}) {
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

function sourceMarkerForRepo(repo) {
  return `github-api:${repoSlug(repo)}-candidate-refresh`;
}

function repoSourceAliases(repo) {
  return [
    repoSlug(repo),
    String(repo?.owner || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
    String(repo?.owner || "").toLowerCase().replace(/[^a-z]+/g, ""),
    String(repo?.name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
  ].filter(Boolean);
}

function addSourceMarker(source, marker) {
  const parts = String(source || "").split("+").filter(Boolean);
  if (!parts.includes(marker)) parts.push(marker);
  return parts.join("+");
}

function projectSummary(project) {
  if (!project) return null;
  return {
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

function replaceProjectFields(text, targetProject, nextProject) {
  const nameNeedle = `"name": "${targetProject.name}"`;
  const nameIndex = text.indexOf(nameNeedle);
  if (nameIndex < 0) throw new Error("missing target project block");
  const start = text.lastIndexOf("\n    {", nameIndex);
  const nextStart = text.indexOf("\n    {", nameIndex + nameNeedle.length);
  const arrayEnd = text.indexOf("\n  ]", nameIndex);
  const end = nextStart >= 0 && nextStart < arrayEnd ? nextStart : arrayEnd;
  if (start < 0 || end < 0) throw new Error("invalid target project block bounds");
  let block = text.slice(start, end);
  for (const field of ["pushedAt", "createdAt", "lastCommit"]) {
    block = replaceStringField(block, field, nextProject[field]);
  }
  for (const field of ["openIssues", "openPRs", "stars", "forks", "diskKb"]) {
    block = replaceNumberField(block, field, nextProject[field]);
  }
  return `${text.slice(0, start)}${block}${text.slice(end)}`;
}

function formatSnapshotText(snapshot, nextPayload) {
  let text = snapshot.text;
  text = replaceStringField(text, "generatedAt", nextPayload.generatedAt);
  text = replaceStringField(text, "source", nextPayload.source);
  text = replaceProjectFields(text, snapshot.project, nextPayload.projects[snapshot.projectIndex]);
  return text.endsWith("\n") ? text : `${text}\n`;
}

function finish(status, extra = {}) {
  console.log(JSON.stringify({
    status,
    mode: snapshotOnly ? "snapshot-only" : (write ? "write" : "dry-run"),
    repo: repoFilter,
    willWrite: write && !snapshotOnly,
    failOnChange: failOnChange && !snapshotOnly,
    ...extra,
  }, null, 2));
  process.exit(status === "pass" ? 0 : 1);
}

if (!repoFilter) {
  finish("fail", {
    reason: "missing --repo owner/name",
  });
}

const snapshot = readSnapshot();
if (!snapshot.project || !snapshot.repo) {
  finish("fail", {
    reason: "missing source-backed adoption candidate",
    generatedAt: snapshot.payload?.generatedAt || "",
  });
}

const marker = sourceMarkerForRepo(snapshot.repo);
if (snapshotOnly) {
  const aliases = repoSourceAliases(snapshot.repo);
  const sourceMarked = snapshot.sourceMarkers.some((item) => item === marker || aliases.some((alias) => item.toLowerCase().includes(alias)));
  finish(commitPattern.test(String(snapshot.project.lastCommit || "")) && sourceMarked ? "pass" : "fail", {
    generatedAt: snapshot.payload.generatedAt || "",
    sourceMarker: marker,
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

const live = fetchLiveSnapshot(snapshot.repo);
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

const nextPayload = JSON.parse(JSON.stringify(snapshot.payload));
const nextProject = nextPayload.projects[snapshot.projectIndex];
for (const field of ["openIssues", "openPRs", "stars", "forks", "diskKb", "pushedAt", "createdAt", "lastCommit"]) {
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
