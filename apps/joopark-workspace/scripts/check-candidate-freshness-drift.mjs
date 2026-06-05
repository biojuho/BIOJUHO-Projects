#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const live = args.has("--live");
const snapshotOnly = args.has("--snapshot-only") || !live;
const failOnDrift = args.has("--fail-on-drift");
const dataPath = join(root, "data/adoption-candidates.json");
const commitPattern = /^[0-9a-f]{40}$/i;
const repoFilters = collectOptionValues("--repo").map(normalizeRepoFilter).filter(Boolean);

function collectOptionValues(flag) {
  const values = [];
  for (let index = 0; index < rawArgs.length; index += 1) {
    const item = rawArgs[index];
    if (item === flag && rawArgs[index + 1] && !rawArgs[index + 1].startsWith("--")) {
      values.push(rawArgs[index + 1]);
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

function matchesRepoFilter(project) {
  if (repoFilters.length === 0) return true;
  return repoFilters.includes(String(project.repo?.nameWithOwner || "").toLowerCase());
}

function readSnapshot() {
  const payload = JSON.parse(readFileSync(dataPath, "utf-8"));
  const projects = Array.isArray(payload.projects) ? payload.projects : [];
  const monitored = projects
    .map((project) => ({ ...project, repo: githubRepo(project.url) }))
    .filter((project) => project.sourceKind === "adoption-candidate" && project.repo && matchesRepoFilter(project) && commitPattern.test(String(project.lastCommit || "")));
  const invalid = projects
    .map((project) => ({ ...project, repo: githubRepo(project.url) }))
    .filter((project) => project.sourceKind === "adoption-candidate" && project.repo && matchesRepoFilter(project) && project.lastCommit != null && !commitPattern.test(String(project.lastCommit || "")))
    .map((project) => project.name);
  const sourceMarkers = String(payload.source || "")
    .split("+")
    .filter((item) => item.startsWith("github-api:"));
  return {
    payload,
    monitored,
    invalid,
    sourceMarkers,
  };
}

function githubRepo(url) {
  const match = String(url || "").match(/^https:\/\/github\.com\/([^/\s]+)\/([^/\s#?]+)\/?$/i);
  if (!match) return null;
  return {
    owner: match[1],
    name: match[2],
    nameWithOwner: `${match[1]}/${match[2]}`,
  };
}

function graphqlString(value) {
  return JSON.stringify(String(value));
}

function fetchLiveSnapshots(monitored) {
  const aliases = monitored.map((project, index) => {
    const alias = `repo${index}`;
    return `${alias}: repository(owner: ${graphqlString(project.repo.owner)}, name: ${graphqlString(project.repo.name)}) {
      nameWithOwner
      stargazerCount
      forkCount
      diskUsage
      pushedAt
      openIssues: issues(states: OPEN) { totalCount }
      openPRs: pullRequests(states: OPEN) { totalCount }
      defaultBranchRef {
        name
        target {
          oid
          ... on Commit { committedDate }
        }
      }
    }`;
  });
  const query = `query CandidateFreshnessDrift {\n${aliases.join("\n")}\n}`;
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
      stdout: result.stdout.trim(),
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
    data: payload.data || {},
  };
}

function liveValue(repo) {
  const openIssueCount = repo?.openIssues?.totalCount;
  const openPrCount = repo?.openPRs?.totalCount;
  const restOpenIssueCount = Number.isFinite(openIssueCount) && Number.isFinite(openPrCount) ? openIssueCount + openPrCount : undefined;
  return {
    lastCommit: repo?.defaultBranchRef?.target?.oid || "",
    pushedAt: repo?.pushedAt || "",
    stars: repo?.stargazerCount,
    forks: repo?.forkCount,
    openIssues: openIssueCount,
    openIssuesWithPRs: restOpenIssueCount,
    openPRs: openPrCount,
    diskKb: repo?.diskUsage,
    defaultBranch: repo?.defaultBranchRef?.name || "",
    committedAt: repo?.defaultBranchRef?.target?.committedDate || "",
  };
}

function fieldDrift(project, current, field) {
  if (field === "openIssues" && current.openIssuesWithPRs === project.openIssues) return null;
  if (project[field] === current[field]) return null;
  const drift = {
    field,
    snapshot: project[field],
    live: current[field],
  };
  if (field === "openIssues") drift.liveWithPRs = current.openIssuesWithPRs;
  return drift;
}

function compare(monitored, liveData) {
  return monitored.map((project, index) => {
    const repo = liveData[`repo${index}`];
    const current = liveValue(repo);
    const fields = ["lastCommit", "pushedAt", "stars", "forks", "openIssues", "openPRs", "diskKb"];
    const drift = fields
      .map((field) => fieldDrift(project, current, field))
      .filter(Boolean);
    return {
      name: project.name,
      url: project.url,
      defaultBranch: current.defaultBranch,
      committedAt: current.committedAt,
      drift,
      ok: drift.length === 0,
    };
  });
}

function finish(payload) {
  console.log(JSON.stringify(payload, null, 2));
  if (payload.status === "fail" || payload.status === "blocked") process.exit(1);
  if (payload.status === "drift" && failOnDrift) process.exit(1);
  process.exit(0);
}

const snapshot = readSnapshot();
if (snapshot.invalid.length > 0 || snapshot.monitored.length === 0) {
  finish({
    status: "fail",
    mode: snapshotOnly ? "snapshot-only" : "live",
    generatedAt: snapshot.payload.generatedAt || "",
    repoFilters,
    monitored: snapshot.monitored.length,
    sourceMarkers: snapshot.sourceMarkers.length,
    invalidSnapshots: snapshot.invalid,
  });
}

if (snapshotOnly) {
  finish({
    status: "pass",
    mode: "snapshot-only",
    generatedAt: snapshot.payload.generatedAt || "",
    repoFilters,
    monitored: snapshot.monitored.length,
    sourceMarkers: snapshot.sourceMarkers.length,
    checks: {
      githubUrls: true,
      commitShape: true,
      sourceMarkers: snapshot.sourceMarkers.length > 0,
      liveNetwork: false,
    },
  });
}

const liveResult = fetchLiveSnapshots(snapshot.monitored);
if (!liveResult.ok) {
  finish({
    status: "blocked",
    mode: "live",
    generatedAt: snapshot.payload.generatedAt || "",
    repoFilters,
    monitored: snapshot.monitored.length,
    reason: liveResult.error,
    stderr: liveResult.stderr || "",
  });
}

const comparisons = compare(snapshot.monitored, liveResult.data);
const drifted = comparisons.filter((item) => item.drift.length > 0);
finish({
  status: drifted.length === 0 ? "pass" : "drift",
  mode: "live",
  generatedAt: snapshot.payload.generatedAt || "",
  repoFilters,
  monitored: snapshot.monitored.length,
  driftCount: drifted.length,
  failOnDrift,
  drifted,
});
