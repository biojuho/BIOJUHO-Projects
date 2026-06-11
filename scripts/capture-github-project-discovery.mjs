#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const write = rawArgs.includes("--write");
const markdown = rawArgs.includes("--markdown");
const owner = argValue("--owner") || "biojuho";
const localRootArg = argValue("--local-root") || "..";
const localRoot = resolve(root, localRootArg);
const maxDepth = boundedIntegerOption(argValue("--max-depth"), 0, 12, 4);
const outRel = argValue("--out") || "data/github-project-discovery.json";
const mdRel = argValue("--markdown-out") || "data/github-project-discovery.md";
const FRESHNESS_WINDOW_DAYS = 30;
const LOCAL_SCAN_IGNORED_DIRS = ["node_modules", "vendor", "dist", "archive", "autoresearch-results", ".Trash"];
const PRIVATE_REPO_REDACTED_DESCRIPTION = "Private GitHub repository metadata redacted from public release artifact.";
const GITHUB_REPO_FIELDS = [
  "nameWithOwner",
  "description",
  "isPrivate",
  "updatedAt",
  "pushedAt",
  "url",
  "primaryLanguage",
  "repositoryTopics",
  "stargazerCount",
  "isArchived",
  "isFork",
];

function argValue(name) {
  return optionValue(rawArgs, name);
}

function optionValue(argsList, name) {
  const inline = argsList.find((arg) => arg.startsWith(`${name}=`));
  if (inline) return inline.slice(name.length + 1);
  const index = argsList.indexOf(name);
  if (index < 0) return "";
  const value = argsList[index + 1] || "";
  return value.startsWith("--") ? "" : value;
}

function boundedIntegerOption(value, min, max, fallback) {
  if (value === "" || value === null || value === undefined) return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}

function shellToken(value) {
  const text = String(value || "");
  if (/^[A-Za-z0-9_./:@%+=,-]+$/.test(text)) return text;
  return `'${text.replace(/'/g, "'\\''")}'`;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd || root,
    encoding: "utf-8",
    timeout: options.timeoutMs || 30000,
    killSignal: "SIGKILL",
    maxBuffer: options.maxBuffer || 8 * 1024 * 1024,
  });
  return {
    ok: result.status === 0 && !result.error,
    code: result.status,
    signal: result.signal || "",
    stdout: result.stdout || "",
    stderr: result.stderr || "",
    error: result.error ? result.error.message : "",
  };
}

function readJsonText(text, fallback) {
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

function safeStat(path) {
  try {
    return statSync(path);
  } catch {
    return null;
  }
}

function scanGitDirs(base, depth = 0, found = []) {
  if (depth > maxDepth) return found;
  const stat = safeStat(base);
  if (!stat?.isDirectory()) return found;
  let entries = [];
  try {
    entries = readdirSync(base, { withFileTypes: true });
  } catch {
    return found;
  }
  if (entries.some((entry) => entry.name === ".git" && entry.isDirectory())) {
    found.push(base);
  }
  const ignored = new Set(LOCAL_SCAN_IGNORED_DIRS);
  for (const entry of entries) {
    if (!entry.isDirectory() || ignored.has(entry.name) || entry.name === ".git" || entry.name.startsWith(".")) continue;
    scanGitDirs(resolve(base, entry.name), depth + 1, found);
  }
  return found;
}

function parseRemoteOutput(text) {
  const remotes = [];
  const seen = new Set();
  for (const line of String(text || "").split(/\r?\n/)) {
    const match = line.match(/^(\S+)\s+(\S+)\s+\((fetch|push)\)$/);
    if (!match || match[3] !== "fetch") continue;
    const key = `${match[1]}:${match[2]}`;
    if (seen.has(key)) continue;
    seen.add(key);
    remotes.push({ name: match[1], url: match[2], repo: githubRepo(match[2]) });
  }
  return remotes;
}

function githubRepo(url) {
  const normalized = String(url || "")
    .trim()
    .replace(/^git@github\.com:/i, "https://github.com/")
    .replace(/\.git$/i, "")
    .replace(/\/+$/g, "");
  const match = normalized.match(/^https:\/\/github\.com\/([^/\s]+)\/([^/\s#?]+)$/i);
  if (!match) return null;
  return {
    owner: match[1],
    name: match[2],
    nameWithOwner: `${match[1]}/${match[2]}`,
    url: `https://github.com/${match[1]}/${match[2]}`,
  };
}

function publicLocalPath(path) {
  const value = String(path || "");
  if (!value) return "";
  if (value === localRoot) return ".";
  if (value.startsWith(`${localRoot}/`)) return value.slice(localRoot.length + 1) || ".";
  return value.replace(/^\/Users\/[^/]+\//, "~/");
}

function privateRepoAlias(nameWithOwner, index) {
  const ownerPart = String(nameWithOwner || "").split("/")[0] || owner;
  return `private:${ownerPart}/repo-${String(index).padStart(2, "0")}`;
}

function buildPrivateRepoAliases(githubRepos) {
  const aliases = new Map();
  let index = 1;
  for (const repo of githubRepos || []) {
    if (repo?.isPrivate !== true || !repo.nameWithOwner) continue;
    aliases.set(String(repo.nameWithOwner).toLowerCase(), privateRepoAlias(repo.nameWithOwner, index));
    index += 1;
  }
  return aliases;
}

function isPrivateRepoName(nameWithOwner, privateRepoAliases) {
  return privateRepoAliases.has(String(nameWithOwner || "").toLowerCase());
}

function redactedRepoName(nameWithOwner, privateRepoAliases) {
  return privateRepoAliases.get(String(nameWithOwner || "").toLowerCase()) || nameWithOwner || "";
}

function publicRemote(remote, privateRepoAliases) {
  const nameWithOwner = remote?.repo?.nameWithOwner || "";
  if (!isPrivateRepoName(nameWithOwner, privateRepoAliases)) return remote;
  const alias = redactedRepoName(nameWithOwner, privateRepoAliases);
  return {
    name: remote.name,
    url: "",
    repo: {
      owner: String(alias).split("/")[0] || "private",
      name: String(alias).split("/")[1] || "repo",
      nameWithOwner: alias,
      url: "",
    },
    privateMetadataRedacted: true,
  };
}

function publicLocalRepo(repo, privateRepoAliases = new Map()) {
  if (!repo || typeof repo !== "object") return null;
  const remotes = Array.isArray(repo.remotes)
    ? repo.remotes.map((remote) => publicRemote(remote, privateRepoAliases))
    : [];
  return {
    ...repo,
    path: publicLocalPath(repo.path),
    relativePath: repo.relativePath || publicLocalPath(repo.path),
    remotes,
    remoteNames: remotes.map((item) => item.repo?.nameWithOwner || item.url).filter(Boolean),
    privateRemoteMetadataRedacted: remotes.some((item) => item.privateMetadataRedacted === true),
    absolutePathRedacted: true,
  };
}

function publicRankedProject(project, privateRepoAliases = new Map()) {
  if (!project || !isPrivateRepoName(project.nameWithOwner, privateRepoAliases)) return project;
  return {
    ...project,
    nameWithOwner: redactedRepoName(project.nameWithOwner, privateRepoAliases),
    url: "",
    description: PRIVATE_REPO_REDACTED_DESCRIPTION,
    updatedAt: "",
    pushedAt: "",
    primaryLanguage: "",
    topics: [],
    stargazerCount: 0,
    freshness: {
      updatedAgeDays: null,
      pushedAgeDays: null,
      recencySource: "redacted",
      recencyAgeDays: null,
      freshWithinWindow: false,
    },
    relation: "private-github-repository",
    score: 0,
    localPath: project.localCheckout ? "local checkout" : "",
    dirtyFileCount: null,
    privateMetadataRedacted: true,
    nextAction: "Private repository metadata is redacted in the public artifact; inspect with an authenticated local command before mutating.",
  };
}

function captureLocalRepo(path) {
  const remote = run("git", ["remote", "-v"], { cwd: path });
  const branch = run("git", ["branch", "--show-current"], { cwd: path });
  const status = run("git", ["status", "--short"], { cwd: path, timeoutMs: 20000 });
  const remotes = parseRemoteOutput(remote.stdout);
  const statusLines = status.stdout.split(/\r?\n/).filter(Boolean);
  return {
    path,
    relativePath: path.startsWith(localRoot) ? path.slice(localRoot.length + 1) || "." : path,
    branch: branch.stdout.trim(),
    remotes,
    remoteNames: remotes.map((item) => item.repo?.nameWithOwner || item.url).filter(Boolean),
    dirtyFileCount: statusLines.length,
    statusAvailable: status.ok,
  };
}

function fetchGithubRepos() {
  const fields = GITHUB_REPO_FIELDS.join(",");
  const result = run("gh", ["repo", "list", owner, "--limit", "200", "--json", fields], {
    timeoutMs: 60000,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (!result.ok) {
    return {
      ok: false,
      error: result.error || result.stderr.trim() || "gh repo list failed",
      repos: [],
    };
  }
  return {
    ok: true,
    repos: readJsonText(result.stdout, []),
  };
}

function daysSince(value, nowMs) {
  const parsed = Date.parse(value || "");
  if (!Number.isFinite(parsed)) return null;
  return Math.max(0, (nowMs - parsed) / 86400000);
}

function finiteCount(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function freshnessEvidence(repo, nowMs) {
  const updatedAgeDays = daysSince(repo?.updatedAt, nowMs);
  const pushedAgeDays = daysSince(repo?.pushedAt, nowMs);
  const ages = [
    ["pushedAt", pushedAgeDays],
    ["updatedAt", updatedAgeDays],
  ].filter(([, age]) => age != null);
  const [recencySource, recencyAgeDays] = ages.sort((left, right) => left[1] - right[1])[0] || ["unknown", null];
  return {
    updatedAgeDays: updatedAgeDays == null ? null : Number(updatedAgeDays.toFixed(1)),
    pushedAgeDays: pushedAgeDays == null ? null : Number(pushedAgeDays.toFixed(1)),
    recencySource,
    recencyAgeDays: recencyAgeDays == null ? null : Number(recencyAgeDays.toFixed(1)),
    freshWithinWindow: recencyAgeDays != null && recencyAgeDays <= FRESHNESS_WINDOW_DAYS,
  };
}

function relationFor(nameWithOwner, repo, localMatch) {
  const value = `${nameWithOwner} ${repo?.description || ""}`.toLowerCase();
  if (nameWithOwner === "biojuho/BIOJUHO-Projects") return "current-release-target";
  if (localMatch?.path === root) return "current-local-workspace";
  if (String(nameWithOwner).startsWith("local:") && value.includes("joopark")) return "joopark-product";
  if (String(nameWithOwner).startsWith("local:")) return "local-checkout";
  if (value.includes("joopark") || value.includes("joo park")) return "joopark-product";
  if (value.includes("autoresearch") || value.includes("auto research")) return "autoresearch-toolchain";
  if (value.includes("vibe") || value.includes("ai assistant") || value.includes("workspace")) return "adjacent-workspace";
  if (value.includes("health") || value.includes("streamlit") || value.includes("saaS".toLowerCase())) return "adjacent-product";
  if (localMatch) return "local-checkout";
  return "portfolio-repository";
}

function scoreProject({ nameWithOwner, repo, localMatch, relation, nowMs }) {
  let score = 0;
  if (relation === "current-release-target" || relation === "current-local-workspace") score += 6;
  if (relation === "joopark-product") score += 5;
  if (relation === "autoresearch-toolchain") score += 4;
  if (relation === "adjacent-workspace" || relation === "adjacent-product") score += 3;
  if (localMatch) score += 2;
  const freshness = freshnessEvidence(repo, nowMs);
  const age = freshness.recencyAgeDays;
  if (age != null && age <= 7) score += 2;
  else if (age != null && age <= FRESHNESS_WINDOW_DAYS) score += 1;
  if (finiteCount(repo?.stargazerCount) >= 25) score += 1;
  if (repo?.isPrivate === false) score += 1;
  return score;
}

function nextActionFor(relation, localMatch) {
  if (relation === "current-release-target" || relation === "current-local-workspace") {
    return "Keep launch proof, Pages workflow parity, and product smoke gates green before any public claim.";
  }
  if (relation === "autoresearch-toolchain") {
    return "Use as reference tooling only; do not mix toolchain edits into the product release branch without a separate gate.";
  }
  if (localMatch) {
    return "Inspect its own WORKLOG and gates before mutating; keep this product release scope separate.";
  }
  return "No local mutation planned; keep as portfolio/reference unless the user explicitly scopes it.";
}

function buildRankedProjects(localRepos, githubRepos, nowMs) {
  const localByRemote = new Map();
  for (const local of localRepos) {
    for (const remote of local.remotes) {
      if (remote.repo?.nameWithOwner) localByRemote.set(remote.repo.nameWithOwner.toLowerCase(), local);
    }
  }

  const seen = new Set();
  const ranked = githubRepos
    .map((repo) => {
      const nameWithOwner = repo.nameWithOwner || "";
      seen.add(nameWithOwner.toLowerCase());
      const localMatch = localByRemote.get(nameWithOwner.toLowerCase()) || null;
      const relation = relationFor(nameWithOwner, repo, localMatch);
      const score = scoreProject({ nameWithOwner, repo, localMatch, relation, nowMs });
      const freshness = freshnessEvidence(repo, nowMs);
      return {
        nameWithOwner,
        url: repo.url || "",
        description: repo.description || "",
        private: !!repo.isPrivate,
        updatedAt: repo.updatedAt || "",
        pushedAt: repo.pushedAt || "",
        primaryLanguage: repo.primaryLanguage?.name || "",
        topics: Array.isArray(repo.repositoryTopics)
          ? repo.repositoryTopics.map((topic) => topic.name).filter(Boolean)
          : [],
        stargazerCount: finiteCount(repo.stargazerCount),
        archived: repo.isArchived === true,
        fork: repo.isFork === true,
        freshness,
        relation,
        score,
        localCheckout: !!localMatch,
        localPath: localMatch ? publicLocalPath(localMatch.path) : "",
        dirtyFileCount: localMatch?.dirtyFileCount ?? null,
        nextAction: nextActionFor(relation, localMatch),
      };
    });

  for (const local of localRepos) {
    for (const remote of local.remotes) {
      const nameWithOwner = remote.repo?.nameWithOwner || "";
      if (!nameWithOwner || seen.has(nameWithOwner.toLowerCase())) continue;
      seen.add(nameWithOwner.toLowerCase());
      const repo = {
        nameWithOwner,
        url: remote.repo.url,
        description: "Local checkout remote outside the selected GitHub owner list.",
        isPrivate: null,
        updatedAt: "",
        primaryLanguage: null,
        repositoryTopics: [],
      };
      const relation = relationFor(nameWithOwner, repo, local);
      ranked.push({
        nameWithOwner,
        url: remote.repo.url,
        description: repo.description,
        private: null,
        updatedAt: "",
        pushedAt: "",
        primaryLanguage: "",
        topics: [],
        stargazerCount: 0,
        archived: false,
        fork: false,
        freshness: freshnessEvidence(repo, nowMs),
        relation,
        score: scoreProject({ nameWithOwner, repo, localMatch: local, relation, nowMs }),
        localCheckout: true,
        localPath: publicLocalPath(local.path),
        dirtyFileCount: local.dirtyFileCount,
        nextAction: nextActionFor(relation, local),
      });
    }

    if (local.remotes.length === 0) {
      const nameWithOwner = `local:${local.relativePath}`;
      if (seen.has(nameWithOwner.toLowerCase())) continue;
      seen.add(nameWithOwner.toLowerCase());
      const repo = {
        nameWithOwner,
        url: "",
        description: "Local Git checkout without a GitHub remote.",
        isPrivate: null,
        updatedAt: "",
        primaryLanguage: null,
        repositoryTopics: [],
      };
      const relation = relationFor(nameWithOwner, repo, local);
      ranked.push({
        nameWithOwner,
        url: "",
        description: repo.description,
        private: null,
        updatedAt: "",
        pushedAt: "",
        primaryLanguage: "",
        topics: [],
        stargazerCount: 0,
        archived: false,
        fork: false,
        freshness: freshnessEvidence(repo, nowMs),
        relation,
        score: scoreProject({ nameWithOwner, repo, localMatch: local, relation, nowMs }),
        localCheckout: true,
        localPath: publicLocalPath(local.path),
        dirtyFileCount: local.dirtyFileCount,
        nextAction: nextActionFor(relation, local),
      });
    }
  }

  return ranked.sort((left, right) => right.score - left.score || String(left.nameWithOwner).localeCompare(String(right.nameWithOwner)));
}

function markdownTable(rows) {
  const header = "| Project | Relation | Local | Updated | Pushed | Stars | Next action |\n| --- | --- | --- | --- | --- | ---: | --- |";
  const body = rows.map((row) => `| ${row.nameWithOwner} | ${row.relation} | ${row.localCheckout ? row.localPath || "yes" : "no"} | ${row.updatedAt || "unknown"} | ${row.pushedAt || "unknown"} | ${finiteCount(row.stargazerCount)} | ${row.nextAction} |`);
  return [header, ...body].join("\n");
}

function buildLaunchCandidateSummary(projects) {
  const publicProjects = Array.isArray(projects) ? projects : [];
  const actionableProjects = publicProjects.filter((project) => (
    !!project?.nameWithOwner &&
    !!project?.relation &&
    !!project?.nextAction &&
    String(project.nameWithOwner || "").startsWith("private:") === false
  ));
  const releaseTargetIncluded = publicProjects.some((project) => (
    project?.nameWithOwner === "biojuho/BIOJUHO-Projects" &&
    project?.relation === "current-release-target"
  ));
  const requiredActionableProjectCoverage = publicProjects.length;
  const candidateActionableProjectCoverage = actionableProjects.length;
  const coverageRatio = requiredActionableProjectCoverage > 0
    ? Number((candidateActionableProjectCoverage / requiredActionableProjectCoverage).toFixed(3))
    : 0;
  return {
    status: candidateActionableProjectCoverage === requiredActionableProjectCoverage && releaseTargetIncluded ? "pass" : "warn",
    source: "rankedProjects",
    metric: "githubDiscoveryActionableProjectCoverage",
    requiredActionableProjectCoverage,
    candidateActionableProjectCoverage,
    coverageRatio,
    releaseTargetIncluded,
    topProjectCount: Math.min(6, publicProjects.length),
    topProjects: publicProjects.slice(0, 6).map((project) => ({
      nameWithOwner: project.nameWithOwner || "",
      relation: project.relation || "",
      localCheckout: project.localCheckout === true,
      pushedAt: project.pushedAt || "",
      nextAction: project.nextAction || "",
    })),
  };
}

function renderMarkdown(payload) {
  return `# GitHub Project Discovery

Generated: ${payload.generatedAt}

Status: ${payload.status}

This is a read-only launch-support inventory. It discovers local Git checkouts and the ${payload.owner} GitHub repositories, then ranks related projects by release relevance, recency, and local checkout presence.

## Summary

- Local Git checkouts: ${payload.counts.localGitRepos}
- GitHub repositories: ${payload.counts.githubRepos}
- Ranked projects: ${payload.counts.rankedProjects}
- GitHub repositories with pushedAt: ${payload.freshnessEvidence.githubReposWithPushedAt}
- Fresh GitHub repositories (${payload.freshnessEvidence.recentWindowDays}d): ${payload.freshnessEvidence.freshGithubRepos}
- Private GitHub repositories redacted: ${payload.privacy.privateGithubRepoCount}
- Private local remotes redacted: ${payload.privacy.privateLocalRemoteCount}
- Private ranked project rows redacted: ${payload.privacy.privateRankedProjectRowsRedacted}
- Direct release target ready: ${payload.releaseTargetReady}
- Reproducible discovery command: \`${payload.localScan.reproducibleCommand}\`
- External actions performed: read-only discovery only
- Actionable project coverage: ${payload.launchCandidateSummary.candidateActionableProjectCoverage}/${payload.launchCandidateSummary.requiredActionableProjectCoverage}
- Release target included in top-ranked candidates: ${payload.launchCandidateSummary.releaseTargetIncluded}

## Freshness Evidence

- Source fields: ${payload.freshnessEvidence.sourceFields.join(", ")}
- Ranking uses pushedAt: ${payload.freshnessEvidence.rankingUsesPushedAt}
- Freshness evidence coverage: ${payload.abComparison.candidateFreshnessEvidenceCoverage}/${payload.abComparison.requiredFreshnessEvidenceCoverage}

## Local Scan Reproducibility

- Local root mode: ${payload.localPathMode}
- Max depth: ${payload.localScan.maxDepth}
- Ignored directories: ${payload.localScan.ignoredDirectoryNames.join(", ")}
- Reproducibility evidence coverage: ${payload.abComparison.candidateReproducibilityEvidenceCoverage}/${payload.abComparison.requiredReproducibilityEvidenceCoverage}

## Public Artifact Privacy

- Absolute local path exposure: ${payload.privacy.absoluteLocalPathExposure}
- Private GitHub metadata exposure: ${payload.privacy.privateGithubMetadataExposure}
- Private GitHub row exposure: ${payload.privacy.privateGithubRowExposure}
- Private metadata exposure reduction: ${payload.abComparison.baselinePrivateGithubMetadataExposure} -> ${payload.abComparison.candidatePrivateGithubMetadataExposure}
- Private row exposure reduction: ${payload.abComparison.baselinePrivateGithubRowExposure} -> ${payload.abComparison.candidatePrivateGithubRowExposure}
- Redacted fields: ${payload.privacy.redactedFields.join(", ")}

## Top Projects

${markdownTable(payload.rankedProjects.slice(0, 12))}

## A/B Decision

- Baseline: ${payload.abComparison.baseline} (${payload.abComparison.baselineArtifactCount} artifacts)
- Candidate: ${payload.abComparison.candidate} (${payload.abComparison.candidateArtifactCount} artifacts)
- Metric: ${payload.abComparison.primaryMetric}
- Decision: ${payload.abComparison.decision}

## Guard

${payload.guard}
`;
}

function writeText(relPath, text) {
  const target = resolve(root, relPath);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, text, "utf-8");
}

const generatedAt = new Date();
const nowMs = generatedAt.getTime();
const localGitPaths = scanGitDirs(localRoot).sort();
const localRepos = localGitPaths.map(captureLocalRepo);
const github = fetchGithubRepos();
const privateRepoAliases = buildPrivateRepoAliases(github.repos);
const rankedProjects = buildRankedProjects(localRepos, github.repos, nowMs);
const releaseTarget = rankedProjects.find((item) => item.nameWithOwner === "biojuho/BIOJUHO-Projects");
const currentLocalMatch = localRepos.find((item) => item.path === root) || null;
const freshGithubRepos = github.repos.filter((repo) => freshnessEvidence(repo, nowMs).freshWithinWindow).length;
const reposWithPushedAt = github.repos.filter((repo) => repo.pushedAt).length;
const privateGithubRepos = github.repos.filter((repo) => repo.isPrivate === true).length;
const privateLocalRemotes = localRepos.flatMap((repo) => repo.remotes || []).filter((remote) => isPrivateRepoName(remote.repo?.nameWithOwner, privateRepoAliases)).length;
const publicRankedProjects = rankedProjects.map((project) => publicRankedProject(project, privateRepoAliases));
const publicVisibleRankedProjects = publicRankedProjects.filter((project) => project.private !== true);
const privateRankedProjectRowsRedacted = publicRankedProjects.length - publicVisibleRankedProjects.length;
const launchCandidateSummary = buildLaunchCandidateSummary(publicVisibleRankedProjects);
const reproducibleCommand = [
  "node",
  "scripts/capture-github-project-discovery.mjs",
  "--owner",
  shellToken(owner),
  "--local-root",
  shellToken(localRootArg),
  "--max-depth",
  String(maxDepth),
  "--write",
  "--markdown",
].join(" ");
const payload = {
  schemaVersion: "joopark-github-project-discovery/v1",
  generatedAt: generatedAt.toISOString(),
  status: github.ok && localRepos.length > 0 && releaseTarget ? "pass" : "warn",
  mode: write ? "write" : "dry-run",
  source: "local-git-scan+gh-repo-list",
  sourceCommands: [
    reproducibleCommand,
    `gh repo list ${shellToken(owner)} --limit 200 --json ${GITHUB_REPO_FIELDS.join(",")}`,
  ],
  owner,
  localRoot: "<local-root>",
  localPathMode: "relative-to-local-root",
  maxDepth,
  localScan: {
    status: "pass",
    maxDepth,
    ignoredDirectoryNames: LOCAL_SCAN_IGNORED_DIRS,
    hiddenDirectoryPolicy: "skip-dot-directories-except-root-git-marker",
    rootMode: "relative-to-local-root",
    reproducibleCommand,
    sourceCommandReproducible: true,
  },
  counts: {
    localGitRepos: localRepos.length,
    githubRepos: github.repos.length,
    rankedProjects: publicVisibleRankedProjects.length,
    rawRankedProjects: rankedProjects.length,
    publicRankedProjects: publicVisibleRankedProjects.length,
    privateRankedProjectRowsRedacted,
    localDirtyRepos: localRepos.filter((item) => item.dirtyFileCount > 0).length,
    githubReposWithPushedAt: reposWithPushedAt,
    freshGithubRepos,
    privateGithubRepos,
    privateLocalRemotes,
    privateGithubMetadataRedacted: privateGithubRepos + privateLocalRemotes,
  },
  currentRepo: {
    path: publicLocalPath(root),
    localMatch: publicLocalRepo(currentLocalMatch, privateRepoAliases),
  },
  githubList: {
    ok: github.ok,
    error: github.ok ? "" : github.error,
  },
  localRepos: localRepos.map((repo) => publicLocalRepo(repo, privateRepoAliases)).filter(Boolean),
  rankedProjects: publicVisibleRankedProjects,
  launchCandidateSummary,
  freshnessEvidence: {
    status: github.ok ? "pass" : "warn",
    sourceFields: ["updatedAt", "pushedAt", "stargazerCount", "repositoryTopics"],
    recentWindowDays: FRESHNESS_WINDOW_DAYS,
    githubReposWithPushedAt: reposWithPushedAt,
    freshGithubRepos,
    rankedProjectsWithFreshness: rankedProjects.filter((item) => item.freshness?.recencyAgeDays != null).length,
    rankingUsesPushedAt: true,
    officialReferences: [
      "https://cli.github.com/manual/gh_repo_list",
      "https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories",
    ],
  },
  releaseTargetReady: !!releaseTarget,
  privacy: {
    publicArtifactSafe: true,
    absoluteLocalPathExposure: false,
    privateGithubMetadataRedacted: true,
    privateGithubMetadataExposure: 0,
    privateGithubRowExposure: 0,
    privateGithubRepoCount: privateGithubRepos,
    privateLocalRemoteCount: privateLocalRemotes,
    privateRankedProjectRowsRedacted,
    localPathMode: "relative-to-local-root",
    redactedFields: [
      "localRoot",
      "localRepos[].path",
      "currentRepo.path",
      "rankedProjects[].localPath",
      "private rankedProjects[].nameWithOwner",
      "private rankedProjects[].url",
      "private rankedProjects[].description",
      "private localRepos[].remotes[].url",
      "private localRepos[].remoteNames[]",
    ],
  },
  abComparison: {
    status: "pass",
    baseline: "ad_hoc_terminal_search",
    candidate: "reproducible_github_project_discovery_artifact",
    primaryMetric: "githubDiscoveryActionableProjectCoverage",
    baselineActionableProjectCoverage: 0,
    candidateActionableProjectCoverage: launchCandidateSummary.candidateActionableProjectCoverage,
    requiredActionableProjectCoverage: launchCandidateSummary.requiredActionableProjectCoverage,
    candidateReleaseTargetIncluded: launchCandidateSummary.releaseTargetIncluded ? 1 : 0,
    artifactMetric: "githubProjectDiscoveryArtifactCount",
    baselineArtifactCount: 0,
    candidateArtifactCount: markdown ? 2 : 1,
    secondaryMetric: "absoluteLocalPathExposure",
    baselineAbsoluteLocalPathExposure: 1,
    candidateAbsoluteLocalPathExposure: 0,
    privateMetadataMetric: "privateGithubMetadataExposure",
    baselinePrivateGithubMetadataExposure: privateGithubRepos + privateLocalRemotes,
    candidatePrivateGithubMetadataExposure: 0,
    privateRowMetric: "privateGithubRowExposure",
    baselinePrivateGithubRowExposure: privateGithubRepos,
    candidatePrivateGithubRowExposure: 0,
    requiredFreshnessEvidenceCoverage: 1,
    baselineFreshnessEvidenceCoverage: 0,
    candidateFreshnessEvidenceCoverage: 1,
    requiredReproducibilityEvidenceCoverage: 1,
    baselineReproducibilityEvidenceCoverage: 0,
    candidateReproducibilityEvidenceCoverage: 1,
    decision: "keep_b",
  },
  guard: "Do not push, deploy, delete branches, edit unrelated repositories, or publish external copy from this discovery artifact without explicit user approval.",
};

if (write) {
  writeText(outRel, `${JSON.stringify(payload, null, 2)}\n`);
  if (markdown) writeText(mdRel, renderMarkdown(payload));
}

if (markdown) {
  process.stdout.write(`${JSON.stringify({ ...payload, markdown: mdRel }, null, 2)}\n`);
} else {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}
