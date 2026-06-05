#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const remote = process.env.PR_BRIDGE_REMOTE || "biojuho-projects";
const mainRef = process.env.PR_BRIDGE_MAIN_REF || `${remote}/main`;
const releaseRef = process.env.PR_BRIDGE_RELEASE_REF || "HEAD";
const appPath = process.env.PR_BRIDGE_APP_PATH || "apps/joopark-workspace";
const bridgeBranch = process.env.PR_BRIDGE_BRANCH || "codex/joopark-workspace-main-bridge";

function git(args) {
  return execFileSync("git", args, {
    cwd: root,
    encoding: "utf-8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
}

function gitMaybe(args) {
  try {
    return git(args);
  } catch {
    return "";
  }
}

function gitPathExists(ref, path) {
  try {
    execFileSync("git", ["cat-file", "-e", `${ref}:${path}`], {
      cwd: root,
      stdio: ["ignore", "ignore", "ignore"],
    });
    return true;
  } catch {
    return false;
  }
}

const releaseCommit = gitMaybe(["rev-parse", "--short", releaseRef]);
const mainCommit = gitMaybe(["rev-parse", "--short", mainRef]);
const mergeBase = gitMaybe(["merge-base", releaseRef, mainRef]);
const mainAppPathExists = gitPathExists(mainRef, appPath);
const noCommonHistory = mergeBase.length === 0;
const strategy = noCommonHistory ? "main-subdirectory-bridge" : "pr-ready-main-history";

const bridgeCommands = [
  `git fetch ${remote} main`,
  `git switch -c ${bridgeBranch} ${mainRef}`,
  `sync the release branch runtime files into ${appPath}/ while preserving repository-root .github workflows`,
  `cd ${appPath} && node scripts/audit-release-readiness.mjs --run-gates`,
  `git push ${remote} ${bridgeBranch}`,
  `open the PR from ${bridgeBranch} to main`,
];
const prReadyCommands = [
  `cd ${appPath} && node scripts/audit-release-readiness.mjs --run-gates`,
  `git push ${remote} ${bridgeBranch}`,
  `open the PR from ${bridgeBranch} to main`,
];

const blockers = [];
if (!mainCommit) blockers.push(`missing main ref ${mainRef}`);
if (!releaseCommit) blockers.push(`missing release ref ${releaseRef}`);
if (!mainAppPathExists) blockers.push(`missing ${appPath} on ${mainRef}`);

const payload = {
  status: blockers.length === 0 ? "pass" : "blocked",
  remote,
  mainRef,
  mainCommit,
  releaseRef,
  releaseCommit,
  mergeBase: mergeBase || null,
  noCommonHistory,
  appPath,
  mainAppPathExists,
  bridgeBranch,
  strategy,
  notes: noCommonHistory ? [
    "Do not open a PR from an orphan release branch when GitHub reports no common history.",
    `Use a branch based on ${mainRef} and sync the app into ${appPath}/.`,
    "Keep repository-root .github workflows under the main branch ownership boundary.",
  ] : [
    "This branch has common history with main and is PR-ready after the app subdirectory gates pass.",
    `Keep syncing only ${appPath}/ unless a repository-root workflow change is explicitly authorized.`,
    "Keep repository-root .github workflows under the main branch ownership boundary.",
  ],
  commands: noCommonHistory ? bridgeCommands : prReadyCommands,
  blockers,
};

console.log(JSON.stringify(payload, null, 2));
if (payload.status !== "pass") process.exit(1);
