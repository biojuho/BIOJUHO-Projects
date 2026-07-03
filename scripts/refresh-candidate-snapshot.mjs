#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { closeSync, mkdtempSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dataPath = join(root, "data/adoption-candidates.json");
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const write = args.has("--write");
const snapshotOnly = args.has("--snapshot-only");
const failOnChange = args.has("--fail-on-change");
const fromLiveDrift = args.has("--from-live-drift");
const actionableOnly = args.has("--actionable-only");
const commitPattern = /^[0-9a-f]{40}$/i;
const liveDriftOutputTailBytes = 2000;
const repoFilters = collectOptionValues("--repo").map(normalizeRepoFilter).filter(Boolean);
const repoFilter = repoFilters[0] || "";

function collectOptionValues(flag, argsList = rawArgs) {
  const values = [];
  for (let index = 0; index < argsList.length; index += 1) {
    const item = argsList[index];
    if (item === flag && argsList[index + 1] && !argsList[index + 1].startsWith("--")) {
      values.push(argsList[index + 1]);
      index += 1;
    } else if (item.startsWith(`${flag}=`)) {
      values.push(item.slice(flag.length + 1));
    }
  }
  return values;
}

function normalizeRepoFilter(value) {
  return String(value || "")
    .trim()
    .replace(/^https:\/\/github\.com\//i, "")
    .replace(/\/+$/g, "")
    .toLowerCase();
}

function finiteNumberOr(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function actionableDriftCountFromPayload(payload) {
  return finiteNumberOr(payload?.actionableDriftCount, finiteNumberOr(payload?.blockingDriftCount, 0));
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
  const match = repoFilter ? enriched.find((item) => item.repo && item.repo.filter === repoFilter) : null;
  return {
    text,
    payload,
    projects,
    enriched,
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

function fetchLiveDriftSnapshot(filters) {
  const commandArgs = ["scripts/check-candidate-freshness-drift.mjs", "--live"];
  for (const filter of filters) commandArgs.push("--repo", filter);
  const tempDir = mkdtempSync(join(tmpdir(), "joopark-live-drift-"));
  const stdoutPath = join(tempDir, "stdout.json");
  const stderrPath = join(tempDir, "stderr.log");
  const stdoutFd = openSync(stdoutPath, "w");
  const stderrFd = openSync(stderrPath, "w");
  let result;
  try {
    result = spawnSync("node", commandArgs, {
      cwd: root,
      timeout: 60000,
      killSignal: "SIGKILL",
      stdio: ["ignore", stdoutFd, stderrFd],
    });
  } finally {
    closeSync(stdoutFd);
    closeSync(stderrFd);
  }
  const stdout = readFileSync(stdoutPath, "utf-8");
  const stderr = readFileSync(stderrPath, "utf-8").trim();
  rmSync(tempDir, { recursive: true, force: true });
  if (result.status !== 0 || result.error) {
    return {
      ok: false,
      error: result.error ? result.error.message : stderr || "live drift check failed",
      stdoutLength: stdout.length,
      stdoutTail: stdout.slice(-liveDriftOutputTailBytes),
      stderr,
    };
  }
  try {
    return {
      ok: true,
      payload: JSON.parse(stdout),
    };
  } catch (error) {
    return {
      ok: false,
      error: error.message,
      stdoutLength: stdout.length,
      stdoutTail: stdout.slice(-liveDriftOutputTailBytes),
      stderr,
    };
  }
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

function formatBatchSnapshotText(snapshot, nextPayload, targetIndexes) {
  let text = snapshot.text;
  text = replaceStringField(text, "generatedAt", nextPayload.generatedAt);
  text = replaceStringField(text, "source", nextPayload.source);
  for (const index of targetIndexes) {
    text = replaceProjectFields(text, snapshot.projects[index], nextPayload.projects[index]);
  }
  return text.endsWith("\n") ? text : `${text}\n`;
}

function projectRefForRepo(snapshot, repo) {
  const filter = normalizeRepoFilter(repo?.nameWithOwner || "");
  return snapshot.enriched.find((item) => item.repo && item.repo.filter === filter) || null;
}

function reposFromLiveDrift(snapshot, driftPayload, options = {}) {
  const sourceRows = options.actionableOnly
    ? (Array.isArray(driftPayload?.actionableDrifted) ? driftPayload.actionableDrifted : (Array.isArray(driftPayload?.blockingDrifted) ? driftPayload.blockingDrifted : []))
    : (Array.isArray(driftPayload?.drifted) ? driftPayload.drifted : []);
  const driftFilters = new Set(
    sourceRows
      .map((item) => githubRepo(item.url))
      .filter(Boolean)
      .map((repo) => repo.filter),
  );
  return snapshot.enriched
    .filter((item) => item.repo && driftFilters.has(item.repo.filter))
    .map((item) => item.repo);
}

function refreshProjects(snapshot, targetRepos) {
  const nextPayload = JSON.parse(JSON.stringify(snapshot.payload));
  const targetIndexes = [];
  const refreshed = [];
  const failures = [];

  for (const targetRepo of targetRepos) {
    const target = projectRefForRepo(snapshot, targetRepo);
    if (!target) {
      failures.push({
        repo: targetRepo.nameWithOwner,
        reason: "missing source-backed adoption candidate",
      });
      continue;
    }

    const live = fetchLiveSnapshot(target.repo);
    if (!live.ok || !live.repo) {
      failures.push({
        repo: target.repo.nameWithOwner,
        reason: live.error || "missing live repository",
        stderr: live.stderr || "",
      });
      continue;
    }

    const fields = liveFields(live.repo);
    if (!commitPattern.test(fields.lastCommit)) {
      failures.push({
        repo: target.repo.nameWithOwner,
        reason: "live default branch commit is invalid",
        live: fields,
      });
      continue;
    }

    const nextProject = nextPayload.projects[target.index];
    for (const field of ["openIssues", "openPRs", "stars", "forks", "diskKb", "pushedAt", "createdAt", "lastCommit"]) {
      nextProject[field] = fields[field];
    }
    nextPayload.source = addSourceMarker(nextPayload.source, sourceMarkerForRepo(target.repo));
    targetIndexes.push(target.index);
    refreshed.push({
      repo: target.repo.nameWithOwner,
      sourceMarker: sourceMarkerForRepo(target.repo),
      defaultBranch: fields.defaultBranch,
      committedAt: fields.committedAt,
      messageHeadline: fields.messageHeadline,
      before: projectSummary(snapshot.projects[target.index]),
      after: projectSummary(nextProject),
    });
  }

  const changedBeforeTimestamp = JSON.stringify(nextPayload) !== JSON.stringify(snapshot.payload);
  if (changedBeforeTimestamp) nextPayload.generatedAt = toKstTimestamp();
  const changed = JSON.stringify(nextPayload) !== JSON.stringify(snapshot.payload);
  return {
    changed,
    nextPayload,
    targetIndexes,
    refreshed,
    failures,
  };
}

function finish(status, extra = {}) {
  console.log(JSON.stringify({
    status,
    mode: snapshotOnly ? "snapshot-only" : (fromLiveDrift ? "from-live-drift" : (write ? "write" : "dry-run")),
    repo: fromLiveDrift ? repoFilters : repoFilter,
    actionableOnly: fromLiveDrift ? actionableOnly : false,
    willWrite: write && !snapshotOnly,
    failOnChange: failOnChange && !snapshotOnly,
    ...extra,
  }, null, 2));
  process.exit(status === "pass" ? 0 : 1);
}

const snapshot = readSnapshot();
if (fromLiveDrift) {
  if (snapshotOnly) {
    finish("fail", {
      reason: "--from-live-drift requires live mode; omit --snapshot-only",
    });
  }
  const driftSnapshot = fetchLiveDriftSnapshot(repoFilters);
  if (!driftSnapshot.ok) {
    finish("blocked", {
      reason: driftSnapshot.error,
      stdoutLength: driftSnapshot.stdoutLength || 0,
      stdoutTail: driftSnapshot.stdoutTail || "",
      stderr: driftSnapshot.stderr || "",
    });
  }
  const targetRepos = reposFromLiveDrift(snapshot, driftSnapshot.payload, { actionableOnly });
  if (targetRepos.length === 0) {
    finish("pass", {
      changed: false,
      wrote: "",
      generatedAt: snapshot.payload.generatedAt || "",
      driftCount: driftSnapshot.payload?.driftCount || 0,
      blockingDriftCount: driftSnapshot.payload?.blockingDriftCount || 0,
      actionableDriftCount: actionableDriftCountFromPayload(driftSnapshot.payload),
      advisoryDriftCount: driftSnapshot.payload?.advisoryDriftCount || 0,
      cadenceAdvisoryDriftCount: driftSnapshot.payload?.cadenceAdvisoryDriftCount || 0,
      metadataAdvisoryDriftCount: driftSnapshot.payload?.metadataAdvisoryDriftCount || 0,
      refreshedRepos: [],
    });
  }

  const batch = refreshProjects(snapshot, targetRepos);
  if (batch.failures.length > 0) {
    finish("blocked", {
      reason: "one or more live snapshot refreshes failed",
      failures: batch.failures,
    });
  }
  if (write && batch.changed) {
    writeFileSync(dataPath, formatBatchSnapshotText(snapshot, batch.nextPayload, batch.targetIndexes), "utf-8");
  }

  finish(failOnChange && batch.changed ? "drift" : "pass", {
    changed: batch.changed,
    wrote: write && batch.changed ? "data/adoption-candidates.json" : "",
    generatedAt: batch.changed ? batch.nextPayload.generatedAt : snapshot.payload.generatedAt || "",
    driftCount: driftSnapshot.payload?.driftCount || 0,
    blockingDriftCount: driftSnapshot.payload?.blockingDriftCount || 0,
    actionableDriftCount: actionableDriftCountFromPayload(driftSnapshot.payload),
    advisoryDriftCount: driftSnapshot.payload?.advisoryDriftCount || 0,
    cadenceAdvisoryDriftCount: driftSnapshot.payload?.cadenceAdvisoryDriftCount || 0,
    metadataAdvisoryDriftCount: driftSnapshot.payload?.metadataAdvisoryDriftCount || 0,
    refreshedRepos: batch.refreshed.map((item) => item.repo),
    refreshed: batch.refreshed,
  });
}

if (actionableOnly) {
  finish("fail", {
    reason: "--actionable-only requires --from-live-drift",
  });
}

if (!repoFilter) {
  finish("fail", {
    reason: "missing --repo owner/name",
  });
}

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
