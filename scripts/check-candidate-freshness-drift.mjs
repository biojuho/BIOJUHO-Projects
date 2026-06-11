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
const includeCadencePolicy = args.has("--cadence-policy");
const dataPath = join(root, "data/adoption-candidates.json");
const commitPattern = /^[0-9a-f]{40}$/i;
const repoFilters = collectOptionValues("--repo").map(normalizeRepoFilter).filter(Boolean);
const cadencePolicyId = "candidate-freshness-drift-cadence-v1";
const metadataPolicyId = "candidate-freshness-commit-stable-repo-metadata-v2";
const advisoryFields = new Set(["stars", "forks"]);
const blockingFields = ["lastCommit", "pushedAt", "openIssues", "openPRs", "diskKb"];
const highChurnCadenceFields = new Set(["lastCommit", "pushedAt", "diskKb"]);
const commitStableMetadataFields = new Set(["pushedAt", "diskKb"]);
const highChurnRepoPolicies = [
  {
    repo: "Veritas-7/autoresearch-skill-system",
    cadenceHours: 4,
    sourceMetadataDriftAdvisory: true,
    reason: "Fast-moving AutoResearch source used directly by the launch candidate snapshot.",
  },
];

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
    severity: advisoryFields.has(field) ? "advisory" : "blocking",
    snapshot: project[field],
    live: current[field],
  };
  if (field === "openIssues") drift.liveWithPRs = current.openIssuesWithPRs;
  return drift;
}

function highChurnPolicyFor(project) {
  const repo = String(project.repo?.nameWithOwner || "").toLowerCase();
  return highChurnRepoPolicies.find((policy) => normalizeRepoFilter(policy.repo) === repo) || null;
}

function minutesBetween(start, end) {
  const startMs = Date.parse(start || "");
  const endMs = Date.parse(end || "");
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return null;
  return (endMs - startMs) / 60000;
}

function cadenceAdvisoryFor(project, current, blockingDrift) {
  const policy = highChurnPolicyFor(project);
  if (!policy?.sourceMetadataDriftAdvisory || blockingDrift.length === 0) return null;
  if (!blockingDrift.every((item) => highChurnCadenceFields.has(item.field))) return null;

  const driftMinutes = minutesBetween(project.pushedAt, current.pushedAt);
  const maxDriftMinutes = policy.cadenceHours * 60;
  if (driftMinutes == null || driftMinutes < 0 || driftMinutes > maxDriftMinutes) return null;

  return {
    id: cadencePolicyId,
    repo: policy.repo,
    cadenceHours: policy.cadenceHours,
    driftMinutes: Math.round(driftMinutes * 10) / 10,
    maxDriftMinutes,
    condition: "high-churn-source-metadata",
    reason: policy.reason,
  };
}

function commitStableMetadataAdvisoryFor(project, current, drift) {
  const metadataDrift = drift.filter((item) => commitStableMetadataFields.has(item.field));
  if (metadataDrift.length === 0) return null;
  if (project.lastCommit !== current.lastCommit) return null;
  return {
    id: metadataPolicyId,
    fields: Array.from(commitStableMetadataFields),
    condition: "commit-stable-metadata",
    reason: "GitHub repository metadata can move while the default-branch source HEAD remains unchanged.",
  };
}

function compare(monitored, liveData) {
  return monitored.map((project, index) => {
    const repo = liveData[`repo${index}`];
    const current = liveValue(repo);
    const fields = ["lastCommit", "pushedAt", "stars", "forks", "openIssues", "openPRs", "diskKb"];
    const rawDrift = fields
      .map((field) => fieldDrift(project, current, field))
      .filter(Boolean);
    const metadataAdvisory = commitStableMetadataAdvisoryFor(project, current, rawDrift);
    const metadataAdvisoryFields = new Set(metadataAdvisory ? rawDrift.filter((item) => commitStableMetadataFields.has(item.field)).map((item) => item.field) : []);
    const metadataAdjustedDrift = rawDrift.map((item) => {
      if (!metadataAdvisoryFields.has(item.field)) return item;
      return {
        ...item,
        severity: "metadata-advisory",
        originalSeverity: item.severity,
        metadataAdvisory,
      };
    });
    const rawBlockingDrift = metadataAdjustedDrift.filter((item) => item.severity === "blocking");
    const cadenceAdvisory = cadenceAdvisoryFor(project, current, rawBlockingDrift);
    const cadenceAdvisoryFields = new Set(cadenceAdvisory ? rawBlockingDrift.map((item) => item.field) : []);
    const drift = metadataAdjustedDrift.map((item) => {
      if (!cadenceAdvisoryFields.has(item.field)) return item;
      return {
        ...item,
        severity: "cadence-advisory",
        originalSeverity: item.severity,
        cadenceAdvisory,
      };
    });
    const blockingDrift = drift.filter((item) => item.severity === "blocking");
    const advisoryDrift = drift.filter((item) => item.severity === "advisory");
    const cadenceAdvisoryDrift = drift.filter((item) => item.severity === "cadence-advisory");
    const metadataAdvisoryDrift = drift.filter((item) => item.severity === "metadata-advisory");
    return {
      name: project.name,
      url: project.url,
      defaultBranch: current.defaultBranch,
      committedAt: current.committedAt,
      drift,
      blockingDrift,
      advisoryDrift,
      cadenceAdvisoryDrift,
      metadataAdvisoryDrift,
      ok: blockingDrift.length === 0,
    };
  });
}

function cadenceCommand(repo, mode, blocking = false) {
  const args = ["node", "scripts/check-candidate-freshness-drift.mjs", mode, "--repo", repo];
  if (mode === "--snapshot-only") args.push("--cadence-policy");
  if (blocking) args.push("--fail-on-drift");
  return args.join(" ");
}

function buildCadencePolicy(snapshot) {
  const monitoredRepos = new Set(snapshot.monitored.map((project) => String(project.repo?.nameWithOwner || "").toLowerCase()));
  const highChurnRepos = highChurnRepoPolicies.map((policy) => {
    const normalizedRepo = normalizeRepoFilter(policy.repo);
    const inScope = repoFilters.length === 0 || repoFilters.includes(normalizedRepo);
    return {
      repo: policy.repo,
      repoFilter: normalizedRepo,
      monitored: monitoredRepos.has(normalizedRepo),
      inScope,
      cadenceHours: policy.cadenceHours,
      sourceMetadataDriftPolicy: policy.sourceMetadataDriftAdvisory
        ? `Treat drift confined to lastCommit, pushedAt, and diskKb as cadence-advisory for ${policy.cadenceHours} hours when issue and PR metadata is unchanged.`
        : "disabled",
      trigger: "Before release gates, after upstream movement, and before enabling fail-on-drift automation.",
      reason: policy.reason,
      snapshotCommand: cadenceCommand(policy.repo, "--snapshot-only"),
      liveCommand: cadenceCommand(policy.repo, "--live"),
      blockingCommand: cadenceCommand(policy.repo, "--live", true),
    };
  });
  const monitoredHighChurn = highChurnRepos.filter((item) => item.monitored).length;
  const scopedHighChurn = highChurnRepos.filter((item) => item.monitored && item.inScope).length;
  return {
    id: cadencePolicyId,
    repoFilters,
    scope: repoFilters.length > 0 ? "repo-filtered" : "all-monitored",
    snapshotOnlyCadence: "every release audit",
    liveCadence: "before release gates and after high-churn upstream movement",
    automationRule: "Run the repo-scoped live check, refresh the snapshot, then use repo-scoped --fail-on-drift for that source.",
    highChurnRepos,
    commitStableMetadataPolicy: {
      id: metadataPolicyId,
      fields: Array.from(commitStableMetadataFields),
      condition: "Treat pushedAt and diskKb metadata drift as metadata-advisory when lastCommit is unchanged.",
      reason: "GitHub pushedAt and diskUsage can move independently from default-branch source HEAD freshness.",
    },
    standardRepos: {
      monitored: Math.max(0, snapshot.monitored.length - monitoredHighChurn),
      liveCadence: "weekly, before release gates, or after planned benchmark refresh work",
      blockingCadence: "after the corresponding snapshot refresh has been committed",
    },
    checks: {
      snapshotOnlyRequired: true,
      repoScopedHighChurn: scopedHighChurn > 0,
      failOnDriftCommandScoped: highChurnRepos.every((item) => item.blockingCommand.includes("--repo")),
      highChurnSourceMetadataCadenceAdvisory: highChurnRepos.some((item) => item.monitored && item.inScope && item.sourceMetadataDriftPolicy !== "disabled"),
      commitStableMetadataAdvisory: commitStableMetadataFields.size > 0,
    },
  };
}

function withCadencePolicy(payload, snapshot) {
  if (!includeCadencePolicy) return payload;
  return {
    ...payload,
    cadencePolicy: buildCadencePolicy(snapshot),
  };
}

function finish(payload) {
  console.log(JSON.stringify(payload, null, 2));
  if (payload.status === "fail" || payload.status === "blocked") process.exit(1);
  if (payload.status === "drift" && failOnDrift) process.exit(1);
  process.exit(0);
}

const snapshot = readSnapshot();
if (snapshot.invalid.length > 0 || snapshot.monitored.length === 0) {
  finish(withCadencePolicy({
    status: "fail",
    mode: snapshotOnly ? "snapshot-only" : "live",
    generatedAt: snapshot.payload.generatedAt || "",
    repoFilters,
    monitored: snapshot.monitored.length,
    sourceMarkers: snapshot.sourceMarkers.length,
    invalidSnapshots: snapshot.invalid,
  }, snapshot));
}

if (snapshotOnly) {
  finish(withCadencePolicy({
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
  }, snapshot));
}

const liveResult = fetchLiveSnapshots(snapshot.monitored);
if (!liveResult.ok) {
  finish(withCadencePolicy({
    status: "blocked",
    mode: "live",
    generatedAt: snapshot.payload.generatedAt || "",
    repoFilters,
    monitored: snapshot.monitored.length,
    reason: liveResult.error,
    stderr: liveResult.stderr || "",
  }, snapshot));
}

const comparisons = compare(snapshot.monitored, liveResult.data);
const drifted = comparisons.filter((item) => item.drift.length > 0);
const blockingDrifted = comparisons.filter((item) => item.blockingDrift.length > 0);
const actionableDrifted = blockingDrifted;
const cadenceAdvisoryDrifted = comparisons.filter((item) => item.cadenceAdvisoryDrift.length > 0 && item.blockingDrift.length === 0);
const metadataAdvisoryDrifted = comparisons.filter((item) => item.metadataAdvisoryDrift.length > 0 && item.blockingDrift.length === 0);
const advisoryDrifted = comparisons.filter((item) => item.advisoryDrift.length > 0 && item.blockingDrift.length === 0);
finish(withCadencePolicy({
  status: blockingDrifted.length === 0 ? "pass" : "drift",
  mode: "live",
  generatedAt: snapshot.payload.generatedAt || "",
  repoFilters,
  monitored: snapshot.monitored.length,
  driftCount: drifted.length,
  blockingDriftCount: blockingDrifted.length,
  actionableDriftCount: actionableDrifted.length,
  advisoryDriftCount: advisoryDrifted.length,
  cadenceAdvisoryDriftCount: cadenceAdvisoryDrifted.length,
  metadataAdvisoryDriftCount: metadataAdvisoryDrifted.length,
  failOnDrift,
  driftPolicy: {
    blockingFields,
    actionableFields: blockingFields,
    advisoryFields: Array.from(advisoryFields),
    cadenceAdvisoryFields: Array.from(highChurnCadenceFields),
    metadataAdvisoryFields: Array.from(commitStableMetadataFields),
    metadataPolicyId,
    highChurnRepoPolicies,
  },
  drifted,
  blockingDrifted,
  actionableDrifted,
  advisoryDrifted,
  cadenceAdvisoryDrifted,
  metadataAdvisoryDrifted,
}, snapshot));
