#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = gitRoot();
const templateRel = "docs/github-drift-watch-workflow.yml";
const targetRel = ".github/workflows/joopark-drift-watch.yml";
const templatePath = join(root, templateRel);
const targetPath = join(repositoryRoot, targetRel);
const targetDisplayPath = relative(root, targetPath).replaceAll("\\", "/") || targetRel;
const args = new Set(process.argv.slice(2));
const stageLocal = args.has("--stage-local");
const dryRun = args.has("--dry-run") || (!args.has("--write") && !stageLocal);
const write = args.has("--write") && !dryRun;
const localStage = stageLocal && !dryRun && !write;
const force = args.has("--force");
const checkScope = args.has("--check-scope") || write;
const workflowScope = checkScope ? inspectWorkflowScope() : {
  checked: false,
  available: null,
  scopes: [],
  source: "not-requested",
};

const requiredTerms = [
  "workflow_dispatch:",
  "schedule:",
  "cron: \"23 2 * * 1\"",
  "permissions:",
  "contents: read",
  "actions/checkout@v6",
  "actions/setup-node@v4",
  "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
  "node scripts/check-candidate-freshness-drift.mjs --snapshot-only",
  "node scripts/check-candidate-freshness-drift.mjs --live",
  "node scripts/check-candidate-freshness-drift.mjs --live --fail-on-drift",
  "DRIFT_REPO",
  "fail-on-drift",
];

function gitRoot() {
  try {
    return execFileSync("git", ["rev-parse", "--show-toplevel"], {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return root;
  }
}

function inspectWorkflowScope() {
  try {
    const output = execFileSync("gh", ["api", "-i", "user"], {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    const scopeHeader = output.split(/\r?\n/).find((line) => /^x-oauth-scopes:/i.test(line)) || "";
    const scopes = scopeHeader
      .replace(/^x-oauth-scopes:\s*/i, "")
      .split(",")
      .map((scope) => scope.trim())
      .filter(Boolean);
    return {
      checked: true,
      available: scopes.includes("workflow"),
      scopes,
      source: "gh-api-header",
    };
  } catch (error) {
    return {
      checked: true,
      available: false,
      scopes: [],
      source: "gh-api-header",
      error: String(error?.message || error).slice(0, 240),
    };
  }
}

function result(status, extra = {}) {
  const payload = {
    status,
    mode: dryRun ? "dry-run" : localStage ? "stage-local" : "write",
    template: templateRel,
    target: targetDisplayPath,
    targetRepositoryPath: targetRel,
    repositoryRoot,
    willWrite: write || localStage,
    localStage,
    remoteWriteReady: write && workflowScope.available === true,
    force,
    workflowScopeRequired: true,
    workflowScopeChecked: workflowScope.checked,
    workflowScopeAvailable: workflowScope.available,
    workflowScope,
    workflowScopeHint: "Commit or push the repository-root workflow only with a GitHub token or UI session that has workflow scope.",
    localStageHint: "The --stage-local mode only copies the workflow into this working tree; pushing it to GitHub still requires a workflow-scope token or a GitHub UI session.",
    ...extra,
  };
  console.log(JSON.stringify(payload, null, 2));
  process.exit(status === "pass" ? 0 : 1);
}

if (!existsSync(templatePath)) {
  result("fail", { reason: "missing template" });
}

const template = readFileSync(templatePath, "utf-8");
const missingTerms = requiredTerms.filter((term) => !template.includes(term));
if (missingTerms.length > 0) {
  result("fail", { reason: "template missing required terms", missingTerms });
}

if (!write) {
  if (localStage) {
    mkdirSync(dirname(targetPath), { recursive: true });
    try {
      writeFileSync(targetPath, template, { encoding: "utf-8", flag: force ? "w" : "wx" });
    } catch (error) {
      if (error && error.code === "EEXIST" && !force) {
        result("fail", {
          reason: "target already exists; pass --force to overwrite",
          targetExists: true,
        });
      }
      throw error;
    }
    result("pass", {
      targetExists: true,
      wrote: targetDisplayPath,
      checks: {
        templateExists: true,
        requiredTerms: true,
        targetPath: true,
        localStage: true,
        workflowScopePreflight: workflowScope.checked ? workflowScope.available : null,
      },
    });
  }
  const targetExists = existsSync(targetPath);
  result("pass", {
    targetExists,
    checks: {
      templateExists: true,
      requiredTerms: true,
      targetPath: true,
      noImplicitWrite: true,
      workflowScopePreflight: workflowScope.checked ? workflowScope.available : null,
    },
  });
}

if (!workflowScope.available) {
  result("fail", {
    reason: "missing workflow scope",
    targetExists: existsSync(targetPath),
    checks: {
      templateExists: true,
      requiredTerms: true,
      targetPath: true,
      explicitWrite: true,
      workflowScopePreflight: false,
    },
  });
}

mkdirSync(dirname(targetPath), { recursive: true });
try {
  writeFileSync(targetPath, template, { encoding: "utf-8", flag: force ? "w" : "wx" });
} catch (error) {
  if (error && error.code === "EEXIST" && !force) {
    result("fail", {
      reason: "target already exists; pass --force to overwrite",
      targetExists: true,
    });
  }
  throw error;
}
result("pass", {
  targetExists: true,
  wrote: targetDisplayPath,
  checks: {
    templateExists: true,
    requiredTerms: true,
    targetPath: true,
    explicitWrite: true,
  },
});
