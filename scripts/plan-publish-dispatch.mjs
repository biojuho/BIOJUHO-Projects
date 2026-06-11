#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = gitRoot();
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const live = args.has("--live");
const write = args.has("--write");
const outputRelativePath = "data/publish-dispatch-plan.json";
const outputPath = join(root, outputRelativePath);
const suggestedRepo = suggestedRepoFromRemote();
const repo = argValue("--repo") || (live ? currentRepo() || suggestedRepo : "OWNER/REPO");
const repoEvidenceReady = !!repo && repo !== "OWNER/REPO";
const workflowDispatchPrefix = "gh workflow run --repo";
const workflowListFixture = argValue("--workflow-list-fixture") || process.env.JOOPARK_WORKFLOW_LIST_FIXTURE || "";
const commandRepo = repoEvidenceReady ? repo : "OWNER/REPO";
const defaultBranch = defaultBranchCandidate();
const workflowScope = inspectWorkflowScope();
const repositoryUrl = repoEvidenceReady
  ? `https://github.com/${repo.replace(/\.git$/i, "")}`
  : suggestedRepo
    ? `https://github.com/${suggestedRepo.replace(/\.git$/i, "")}`
    : "";
const repoReplacementHint = suggestedRepo ? `Replace OWNER/REPO with ${suggestedRepo}` : "Replace OWNER/REPO with the exact GitHub owner/name repo";
const placeholderVerificationCommand = "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO";
const nextVerificationRepo = repoEvidenceReady ? repo : suggestedRepo || "OWNER/REPO";
const nextVerificationCommand = `node scripts/plan-publish-dispatch.mjs --live --repo ${nextVerificationRepo}`;
const workflowScopeRefreshCommand = "gh auth refresh -h github.com -s workflow";
const workflowScopeRefreshClipboardCommand = `${workflowScopeRefreshCommand} --clipboard`;
const workflowScopeInteractiveApprovalNote = "This is an interactive OAuth device flow; keep the terminal session open until gh reports success. If the browser approval is not completed, gh auth status will still omit workflow.";
const workflowScopeRecheckCommand = nextVerificationCommand;
const pagesWorkflowDispatchRef = pagesWorkflowRefFromTemplate();

function workflowDispatchCommand(workflowFile, targetRepo, fields = []) {
  return [workflowDispatchPrefix, targetRepo || "OWNER/REPO", workflowFile, ...fields].join(" ");
}

const workflows = [
  {
    key: "pages",
    workflowName: "Publish JooPark Pages",
    workflowFile: "joopark-pages.yml",
    workflowPath: ".github/workflows/joopark-pages.yml",
    template: "docs/github-pages-workflow.yml",
    installCommand: "node scripts/prepare-github-pages-workflow.mjs --write",
    scopeCheckCommand: "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope",
    requiredTerms: [
      "workflow_dispatch:",
      "pages: write",
      "id-token: write",
      "attestations: write",
      "actions/attest@v4",
      "subject-path: dist/release/**",
      "actions/upload-pages-artifact@v4",
      "actions/deploy-pages@v4",
      "node scripts/package-release.mjs",
      "node scripts/verify-release.mjs",
      "search-empty-state.js",
      "calendar-view.js",
      "todo-view.js",
      "notes-view.js",
      "habits-view.js",
      "stats-view.js",
      "portfolio-view.js",
      "kanban-view.js",
      "gantt-view.js",
      "team-view.js",
      "workspace-storage.js",
      "dashboard-storage.js",
      "dashboard-prioritization.js",
      "dashboard-evidence-receipts.js",
      "dashboard-insights-engine.js",
      "dashboard-autoresearch-loop.js",
      "dashboard-view.js",
      "storage-status-view.js",
      "settings-view.js",
      "system-status-view.js",
      "dialog-shell.js",
      "project-picker.js",
      "global-search.js",
      "command-palette.js",
      "review-result-view.js",
      "review-package-view.js",
      "review-artifact-view.js",
      "pwa-runtime.js",
      "sw.js",
    ],
  },
  {
    key: "drift-watch",
    workflowName: "Watch JooPark Candidate Drift",
    workflowFile: "joopark-drift-watch.yml",
    workflowPath: ".github/workflows/joopark-drift-watch.yml",
    template: "docs/github-drift-watch-workflow.yml",
    installCommand: "node scripts/prepare-github-drift-watch-workflow.mjs --write",
    scopeCheckCommand: "node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope",
    requiredTerms: [
      "workflow_dispatch:",
      "schedule:",
      "contents: read",
      "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
      "node scripts/check-candidate-freshness-drift.mjs --live",
      "fail-on-drift",
    ],
  },
].map((workflow) => ({
  ...workflow,
  dispatchCommand: workflow.key === "drift-watch"
    ? workflowDispatchCommand(workflow.workflowFile, repo, ["-f", "mode=advisory"])
    : workflowDispatchCommand(workflow.workflowFile, repo, ["-f", `ref=${pagesWorkflowDispatchRef}`]),
  followupCommand: workflow.key === "drift-watch"
    ? workflowDispatchCommand(workflow.workflowFile, repo, ["-f", "mode=fail-on-drift", "-f", `repo=${commandRepo}`])
    : null,
}));
const workflowStageFiles = workflows.map((workflow) => workflow.workflowPath);
const remoteWorkflowFileCheck = readJson("data/remote-workflow-file-check.json", {});
const remoteWorkflowFileCheckMatchesTarget = remoteWorkflowFileCheck?.repo === repo &&
  remoteWorkflowFileCheck?.defaultBranch === defaultBranch.branch;
const remoteWorkflowFileFixtureReady = !!workflowListFixture;
const remoteWorkflowFileChecks = remoteWorkflowFileCheckMatchesTarget && Array.isArray(remoteWorkflowFileCheck?.checks)
  ? remoteWorkflowFileCheck.checks
  : [];
const remoteWorkflowFilesChecked = remoteWorkflowFileFixtureReady || (
  remoteWorkflowFileCheckMatchesTarget &&
  remoteWorkflowFileCheck?.remoteWorkflowFilesChecked === true
);
const remoteWorkflowFilesReady = remoteWorkflowFileFixtureReady || (remoteWorkflowFilesChecked &&
  remoteWorkflowFileCheck?.remoteWorkflowFilesReady === true);

function readJson(relativePath, fallback = {}) {
  try {
    return JSON.parse(readFileSync(join(root, relativePath), "utf-8"));
  } catch {
    return fallback;
  }
}

function pagesWorkflowRefFromTemplate() {
  try {
    const template = readFileSync(join(root, "docs/github-pages-workflow.yml"), "utf-8");
    return template.match(/default:\s*([^\s#]+)/)?.[1] || "codex/joopark-workspace-release";
  } catch {
    return "codex/joopark-workspace-release";
  }
}
const workflowGitAddCommand = `git add ${workflowStageFiles.join(" ")}`;
const workflowGitCommitCommand = "git commit -m 'Add JooPark publish workflows'";

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

function currentRepo() {
  try {
    const output = execFileSync("gh", ["repo", "view", "--json", "nameWithOwner"], {
      cwd: repositoryRoot,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    const payload = JSON.parse(output || "{}");
    return payload?.nameWithOwner || "";
  } catch {
    return "";
  }
}

function gitText(argsList) {
  try {
    return execFileSync("git", argsList, {
      cwd: repositoryRoot,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function inspectWorkflowScope() {
  try {
    const output = execFileSync("gh", ["api", "-i", "user"], {
      cwd: repositoryRoot,
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

function defaultBranchCandidate() {
  const remotes = gitText(["remote"]).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const remoteName = remotes.includes("biojuho-projects") ? "biojuho-projects" : remotes.includes("origin") ? "origin" : remotes[0] || "";
  const candidates = ["main", "master"];
  const branch = remoteName
    ? candidates.find((candidate) => !!gitText(["show-ref", "--verify", `refs/remotes/${remoteName}/${candidate}`]))
    : "";
  return {
    branch: branch || "main",
    source: branch ? `local refs/remotes/${remoteName}/${branch}` : "fallback-main",
  };
}

function githubNameWithOwner(remoteUrl) {
  const trimmed = String(remoteUrl || "").trim();
  const httpsMatch = trimmed.match(/^https:\/\/github\.com\/([^/]+)\/(.+?)(?:\.git)?$/i);
  if (httpsMatch) return `${httpsMatch[1]}/${httpsMatch[2].replace(/\.git$/i, "")}`;
  const sshMatch = trimmed.match(/^(?:git@github\.com:|ssh:\/\/git@github\.com\/)([^/]+)\/(.+?)(?:\.git)?$/i);
  if (sshMatch) return `${sshMatch[1]}/${sshMatch[2].replace(/\.git$/i, "")}`;
  return "";
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function fileDigest(path) {
  if (!existsSync(path)) {
    return {
      exists: false,
      bytes: 0,
      sha256: null,
      text: "",
    };
  }
  const text = readFileSync(path, "utf-8");
  return {
    exists: true,
    bytes: Buffer.byteLength(text),
    sha256: sha256(text),
    text,
  };
}

function shellQuote(value) {
  return `'${String(value || "").replace(/'/g, "'\\''")}'`;
}

function githubWorkflowUrls(targetRepo, workflowPath) {
  if (!targetRepo || targetRepo === "OWNER/REPO") {
    return {
      githubNewFileUrl: null,
      githubWorkflowUrl: null,
    };
  }
  const repoUrl = `https://github.com/${targetRepo.replace(/\.git$/i, "")}`;
  return {
    githubNewFileUrl: `${repoUrl}/new/${encodeURIComponent(defaultBranch.branch)}?filename=${encodeURIComponent(workflowPath)}`,
    githubEditFileUrl: `${repoUrl}/edit/${encodeURIComponent(defaultBranch.branch)}/${workflowPath}`,
    githubWorkflowUrl: `${repoUrl}/actions/workflows/${workflowPath.split("/").pop()}`,
  };
}

function workflowUiInstallAction(remoteFileCheck) {
  const remediation = remoteFileCheck?.remediation && typeof remoteFileCheck.remediation === "object"
    ? remoteFileCheck.remediation
    : {};
  if (remoteFileCheck?.installAction) return remoteFileCheck.installAction;
  if (remediation.installAction) return remediation.installAction;
  if (remoteFileCheck?.remoteExists && remoteFileCheck?.remoteMatchesTemplate) return "verified_remote_matches_template";
  if (remoteFileCheck?.remoteExists) return "replace_existing_remote_file";
  if (remoteFileCheck) return "create_missing_remote_file";
  return "create_missing_remote_file";
}

function workflowUiInstallInstruction({ installAction, workflowPath, defaultBranch: branch }) {
  if (installAction === "replace_existing_remote_file") {
    return `Open the existing GitHub edit-file page for ${workflowPath}, replace the entire file with the copied template, and commit to ${branch}.`;
  }
  if (installAction === "verified_remote_matches_template") {
    return `No GitHub UI edit is required for ${workflowPath}; the remote file already matches the local template.`;
  }
  return `Open the GitHub new-file page, set the file name to ${workflowPath}, paste the copied template, and commit to ${branch}.`;
}

function workflowUiInstallPlan(entry, remoteFileCheck = null) {
  const templatePath = join(root, entry.template);
  const targetPath = join(repositoryRoot, entry.workflowPath);
  const templateDigest = fileDigest(templatePath);
  const targetDigest = fileDigest(targetPath);
  const templateText = templateDigest.text;
  const missingTerms = (entry.requiredTerms || []).filter((term) => !templateText.includes(term));
  const urls = githubWorkflowUrls(repoEvidenceReady ? repo : suggestedRepo, entry.workflowPath);
  const remediation = remoteFileCheck?.remediation && typeof remoteFileCheck.remediation === "object" ? remoteFileCheck.remediation : {};
  const installAction = workflowUiInstallAction(remoteFileCheck);
  const templateCopyCommand = `pbcopy < ${shellQuote(entry.template)}`;
  const githubNewFileUrl = remediation.githubNewFileUrl || remoteFileCheck?.githubNewFileUrl || urls.githubNewFileUrl;
  const githubEditFileUrl = remediation.githubEditFileUrl || remoteFileCheck?.githubEditFileUrl || urls.githubEditFileUrl;
  const githubNewFileOpenCommand = remediation.githubNewFileOpenCommand || remoteFileCheck?.githubNewFileOpenCommand || (githubNewFileUrl ? `open ${shellQuote(githubNewFileUrl)}` : "");
  const githubEditFileOpenCommand = remediation.githubEditFileOpenCommand || remoteFileCheck?.githubEditFileOpenCommand || (githubEditFileUrl ? `open ${shellQuote(githubEditFileUrl)}` : "");
  const githubWorkflowOpenCommand = urls.githubWorkflowUrl ? `open ${shellQuote(urls.githubWorkflowUrl)}` : "";
  const targetMatchesTemplate = templateDigest.exists && targetDigest.exists && templateDigest.sha256 === targetDigest.sha256;
  const uiInstallRequired = installAction !== "verified_remote_matches_template";
  const uiInstallOpenCommand = installAction === "replace_existing_remote_file"
    ? githubEditFileOpenCommand
    : installAction === "create_missing_remote_file"
      ? githubNewFileOpenCommand
      : "";
  return {
    key: entry.key,
    workflowName: entry.workflowName,
    workflowFile: entry.workflowFile,
    template: entry.template,
    targetRepositoryPath: entry.workflowPath,
    defaultBranch: defaultBranch.branch,
    defaultBranchSource: defaultBranch.source,
    repositoryUrl,
    suggestedRepo,
    repoReplacementHint,
    githubNewFileUrl,
    githubEditFileUrl,
    githubWorkflowUrl: urls.githubWorkflowUrl,
    templateCopyCommand,
    githubNewFileOpenCommand,
    githubEditFileOpenCommand,
    githubWorkflowOpenCommand,
    uiInstallOpenCommand,
    uiInstallCommand: uiInstallOpenCommand,
    uiInstallRequired,
    installAction,
    remoteExists: remoteFileCheck?.remoteExists === true,
    remoteMatchesTemplate: remoteFileCheck?.remoteMatchesTemplate === true,
    templateExists: templateDigest.exists,
    targetExists: targetDigest.exists,
    templateSha256: templateDigest.sha256,
    targetSha256: targetDigest.sha256,
    targetMatchesTemplate,
    localTargetParityReady: targetMatchesTemplate,
    requiredTerms: entry.requiredTerms || [],
    missingTerms,
    uiInstallReady: templateDigest.exists && missingTerms.length === 0 && !!urls.githubNewFileUrl && !!urls.githubWorkflowUrl,
    workflowScopeRequired: true,
    workflowScopeCheckCommand: entry.scopeCheckCommand,
    workflowScopeRefreshCommand,
    workflowScopeRecheckCommand,
    cliInstallCommand: entry.installCommand,
    nextVerificationCommand,
    placeholderVerificationCommand,
    manualDispatchRequirement: "workflow_dispatch must be present on the repository default branch before GitHub UI, CLI, or REST dispatch can run it",
    uiSteps: [
      uiInstallRequired ? `Run ${templateCopyCommand} to copy ${entry.template}` : `No copy is required for ${entry.workflowPath} while installAction=${installAction}`,
      `installAction=${installAction}: ${workflowUiInstallInstruction({ installAction, workflowPath: entry.workflowPath, defaultBranch: defaultBranch.branch })}`,
      uiInstallRequired ? `Run ${uiInstallOpenCommand || "open the GitHub repository default branch create/edit page"} before committing ${entry.workflowPath}` : `Skip GitHub create/edit pages for ${entry.workflowPath}`,
      uiInstallRequired ? `Paste the copied template contents from ${entry.template}` : `No paste is required because ${entry.workflowPath} is already verified on ${defaultBranch.branch}`,
      uiInstallRequired ? `Commit to default branch ${defaultBranch.branch} with a workflow-scope capable GitHub UI session` : `Keep the verified remote file unchanged on ${defaultBranch.branch}`,
      `Run ${githubWorkflowOpenCommand || "open the GitHub Actions workflow page"} and confirm the workflow appears`,
      `Run ${nextVerificationCommand} after the workflow appears in Actions`,
      `Treat ${placeholderVerificationCommand} as a template only if the suggested repo is unavailable or wrong`,
    ],
  };
}

function suggestedRepoFromRemote() {
  const remotes = gitText(["remote"]).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const remoteName = remotes.includes("biojuho-projects") ? "biojuho-projects" : remotes.includes("origin") ? "origin" : remotes[0] || "";
  if (!remoteName) return "";
  return githubNameWithOwner(gitText(["config", "--get", `remote.${remoteName}.url`]));
}

function workflowList(targetRepo) {
  if (!live || !repoEvidenceReady) {
    return {
      checked: false,
      workflows: [],
      source: live ? "repo-not-ready" : "not-requested",
      command: "gh workflow list --repo OWNER/REPO --all --json name,path,state,id",
    };
  }
  if (workflowListFixture) {
    try {
      const fixturePath = resolve(root, workflowListFixture);
      const payload = JSON.parse(readFileSync(fixturePath, "utf-8"));
      const workflows = Array.isArray(payload) ? payload : Array.isArray(payload?.workflows) ? payload.workflows : [];
      return {
        checked: true,
        workflows,
        source: "workflow-list-fixture",
        command: `fixture:${workflowListFixture}`,
        fixture: workflowListFixture,
      };
    } catch (error) {
      return {
        checked: true,
        workflows: [],
        source: "workflow-list-fixture",
        command: `fixture:${workflowListFixture}`,
        fixture: workflowListFixture,
        error: String(error?.message || error).slice(0, 240),
      };
    }
  }
  try {
    const output = execFileSync("gh", ["workflow", "list", "--repo", targetRepo, "--all", "--json", "name,path,state,id"], {
      cwd: repositoryRoot,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    const workflows = JSON.parse(output);
    return {
      checked: true,
      workflows: Array.isArray(workflows) ? workflows : [],
      source: "gh-workflow-list",
      command: `gh workflow list --repo ${targetRepo} --all --json name,path,state,id`,
    };
  } catch (error) {
    return {
      checked: true,
      workflows: [],
      source: "gh-workflow-list",
      command: `gh workflow list --repo ${targetRepo} --all --json name,path,state,id`,
      error: String(error?.message || error).slice(0, 240),
    };
  }
}

const remote = workflowList(repo);
function planWorkflow(entry) {
  const targetPath = join(repositoryRoot, entry.workflowPath);
  const targetDisplayPath = relative(root, targetPath).replaceAll("\\", "/") || entry.workflowPath;
  const remoteFileCheck = remoteWorkflowFileChecks.find((check) => check.key === entry.key || check.path === entry.workflowPath) || null;
  const uiInstallPlan = workflowUiInstallPlan(entry, remoteFileCheck);
  const installAction = remoteFileCheck?.installAction || remoteFileCheck?.remediation?.installAction || "";
  const remoteFileReady = remoteWorkflowFileFixtureReady || !!(remoteWorkflowFilesChecked && remoteFileCheck?.remoteExists && remoteFileCheck?.remoteMatchesTemplate);
  const targetExists = uiInstallPlan.targetExists === true;
  const targetMatchesTemplate = uiInstallPlan.targetMatchesTemplate === true;
  const remoteWorkflow = remote.workflows.find((workflow) => {
    return workflow.name === entry.workflowName || workflow.path === entry.workflowPath || workflow.path === `./${entry.workflowPath}`;
  }) || null;
  const remoteReady = remote.checked ? !!remoteWorkflow && remoteWorkflow.state !== "disabled_manually" : null;
  const blockers = [];
  if (live && !repoEvidenceReady) blockers.push(`${entry.key}: repo placeholder OWNER/REPO must be replaced before live dispatch planning`);
  if (!targetExists) blockers.push(`${entry.key}: workflow file is not installed at repository root`);
  if (targetExists && !targetMatchesTemplate) blockers.push(`${entry.key}: local workflow target differs from template`);
  if (live && !remoteWorkflowFilesChecked) blockers.push(`${entry.key}: remote workflow file parity was not checked for ${commandRepo}; run node scripts/check-remote-workflow-files.mjs --repo ${commandRepo} --write`);
  if (live && remoteWorkflowFilesChecked && !remoteFileReady) blockers.push(`${entry.key}: remote workflow file does not match the local template on ${defaultBranch.branch}`);
  if (remote.checked && !remoteWorkflow) blockers.push(`${entry.key}: workflow is not visible in GitHub Actions`);
  if (remoteWorkflow && remoteWorkflow.state === "disabled_manually") blockers.push(`${entry.key}: workflow is disabled in GitHub Actions`);
  if (!remote.checked) blockers.push(`${entry.key}: remote workflow visibility was not checked; pass --live before dispatch`);
  const dispatchReady = targetExists && targetMatchesTemplate && remoteFileReady && (remoteReady === null ? false : remoteReady) && blockers.length === 0;
  return {
    key: entry.key,
    workflowName: entry.workflowName,
    workflowFile: entry.workflowFile,
    workflowPath: entry.workflowPath,
    target: targetDisplayPath,
    targetExists,
    targetSha256: uiInstallPlan.targetSha256,
    templateSha256: uiInstallPlan.templateSha256,
    targetMatchesTemplate,
    localTargetParityReady: targetMatchesTemplate,
    remoteFileChecked: remoteWorkflowFilesChecked,
    remoteFileReady,
    installAction,
    remoteFileSha256: remoteFileCheck?.remoteSha256 || "",
    remoteFileMatchesTemplate: !!remoteFileCheck?.remoteMatchesTemplate,
    dispatchReady,
    dispatchCommand: entry.dispatchCommand,
    installCommand: entry.installCommand,
    scopeCheckCommand: entry.scopeCheckCommand,
    uiInstallPlan,
    followupCommand: entry.followupCommand || null,
    remoteWorkflow: remoteWorkflow ? {
      id: remoteWorkflow.id,
      name: remoteWorkflow.name,
      path: remoteWorkflow.path,
      state: remoteWorkflow.state,
    } : null,
    checks: {
      targetExists,
      targetMatchesTemplate,
      remoteFileChecked: remoteWorkflowFilesChecked,
      remoteFileReady,
      installAction,
      remoteFileMatchesTemplate: !!remoteFileCheck?.remoteMatchesTemplate,
      workflowListChecked: remote.checked,
      workflowVisible: remote.checked ? !!remoteWorkflow : null,
      dispatchCommandGuarded: true,
    },
    blockers,
  };
}

const workflowPlans = workflows.map(planWorkflow);
function workflowScopeFallbackText(plans = []) {
  const actions = (Array.isArray(plans) ? plans : [])
    .map((plan) => plan.installAction || plan.checks?.installAction || "")
    .filter(Boolean);
  if (actions.some((action) => action === "replace_existing_remote_file")) {
    return "If browser approval cannot be completed, use each workflow row's installAction: open GitHub edit-file pages for existing mismatched files and new-file pages only for missing files.";
  }
  if (actions.some((action) => action === "create_missing_remote_file")) {
    return "If browser approval cannot be completed, use the GitHub new-file pages only for workflow files that are missing on the default branch.";
  }
  if (actions.length > 0 && actions.every((action) => action === "verified_remote_matches_template")) {
    return "No GitHub UI file change is required; both remote workflow files already match the local templates.";
  }
  return "If browser approval cannot be completed, use each workflow row's installAction to choose the GitHub create or edit page before rerunning verification.";
}
const pagesPlan = workflowPlans.find((plan) => plan.key === "pages");
const driftPlan = workflowPlans.find((plan) => plan.key === "drift-watch");
const blockers = workflowPlans.flatMap((plan) => plan.blockers);
const workflowUiInstallPlans = workflowPlans.map((plan) => plan.uiInstallPlan);
const workflowUiInstallReady = workflowUiInstallPlans.length > 0 && workflowUiInstallPlans.every((plan) => plan.uiInstallReady);
const localTargetParityReady = workflowPlans.length > 0 && workflowPlans.every((plan) => plan.targetMatchesTemplate);
const localWorkflowTargetsReady = workflowPlans.length > 0 && workflowPlans.every((plan) => plan.targetExists && plan.targetMatchesTemplate);
const remoteWorkflowVisibilityReady = workflowPlans.length > 0 && workflowPlans.every((plan) => plan.checks.workflowVisible === true);
const workflowScopeInstallBlocked = !remoteWorkflowVisibilityReady && workflowScope.checked && workflowScope.available === false;
const workflowDefaultBranchHandoff = {
  localStageReady: localWorkflowTargetsReady,
  localStageFiles: workflowStageFiles,
  defaultBranch: defaultBranch.branch,
  defaultBranchSource: defaultBranch.source,
  workflowScopeRefreshCommand,
  workflowScopeRecheckCommand,
  gitAddCommand: workflowGitAddCommand,
  gitCommitCommand: workflowGitCommitCommand,
  remoteVisibilityVerificationCommand: nextVerificationCommand,
  requirement: `Land ${workflowStageFiles.join(" and ")} on the repository default branch ${defaultBranch.branch} with a workflow-scope token or GitHub UI session before dispatch. If the GitHub CLI token lacks workflow scope, run ${workflowScopeRefreshCommand}, then rerun ${workflowScopeRecheckCommand}.`,
};
const workflowScopeApprovalHandoff = {
  requiredWhenInstallBlocked: workflowScopeInstallBlocked,
  status: workflowScopeInstallBlocked ? "approval_required" : "not_required",
  command: workflowScopeRefreshCommand,
  clipboardCommand: workflowScopeRefreshClipboardCommand,
  approvalUrl: "https://github.com/login/device",
  expectedPrompt: "First copy your one-time code, then open https://github.com/login/device to approve the workflow scope; keep the terminal session open until gh reports success.",
  interactiveApprovalRequired: workflowScopeInstallBlocked,
  terminalWaitRequired: workflowScopeInstallBlocked,
  interactiveApprovalNote: workflowScopeInteractiveApprovalNote,
  sensitiveValuePolicy: "Do not store, log, or paste the one-time device code into project files; the operator copies it from the local CLI prompt only.",
  recheckCommand: workflowScopeRecheckCommand,
  authStatusCommand: "gh auth status -h github.com",
  postApprovalAuthStatusCommand: "gh auth status -h github.com",
  incompleteApprovalSignal: "Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.",
  successSignals: [
    "Token scopes include workflow",
    "workflowScopeAvailable=true",
    "workflowScopeInstallBlocked=false",
  ],
  fallback: workflowScopeFallbackText(workflowPlans),
  stopCondition: "Do not run install-remote-workflow-files.mjs, gh workflow run, publish copy, or archive proof until the recheck reports workflowScopeAvailable=true or the GitHub UI path has applied each workflow row's installAction on the default branch.",
};
const workflowScopeRefreshHandoff = {
  requiredWhenInstallBlocked: workflowScopeInstallBlocked,
  command: workflowScopeRefreshCommand,
  clipboardCommand: workflowScopeRefreshClipboardCommand,
  recheckCommand: workflowScopeRecheckCommand,
  helpCommand: "gh auth refresh --help",
  approval: workflowScopeApprovalHandoff,
  note: "Run this only as an operator handoff when the current GitHub CLI token lacks workflow scope; it opens the GitHub auth flow, requires browser approval while the terminal waits, and must not be treated as workflow dispatch.",
};
const installBlockers = workflowScopeInstallBlocked
  ? [`workflow scope: current GitHub CLI token cannot create or update workflow files; run ${workflowScopeRefreshCommand} and rerun ${workflowScopeRecheckCommand}, or use GitHub UI for default-branch installation`]
  : [];
const allBlockers = [...blockers, ...installBlockers];
const nextActions = allBlockers.length
  ? localWorkflowTargetsReady
    ? [
        workflowScopeInstallBlocked
          ? `Current CLI token lacks workflow scope; run ${workflowScopeRefreshCommand}, then rerun ${workflowScopeRecheckCommand}, or use the GitHub UI links for default-branch workflow installation.`
          : "",
        "Push or commit the staged repository-root workflows to the default branch with a workflow-scope token or GitHub UI session.",
        `Local handoff: ${workflowGitAddCommand} then ${workflowGitCommitCommand}.`,
        `Run ${nextVerificationCommand} until GitHub Actions lists both workflows and allDispatchReady is true.`,
        "Dispatch only after every workflow plan reports dispatchReady: true.",
      ].filter(Boolean)
    : [
        workflowScopeInstallBlocked
          ? `Current CLI token lacks workflow scope; run ${workflowScopeRefreshCommand}, then rerun ${workflowScopeRecheckCommand}, or use a GitHub UI session for workflow file installation.`
          : "",
        "Install missing repository-root workflows using the workflowUiInstallPlans GitHub UI links, --stage-local, or a workflow-scope token.",
        `Run ${nextVerificationCommand} until dispatchReady and allDispatchReady are true.`,
        "Dispatch only after every workflow plan reports dispatchReady: true.",
      ].filter(Boolean)
  : [
      pagesPlan?.dispatchCommand,
      driftPlan?.dispatchCommand,
      `Capture launch proof with node scripts/capture-publish-evidence.mjs --live --repo ${commandRepo} --markdown and --write.`,
    ].filter(Boolean);
const dispatchReady = !!pagesPlan && pagesPlan.dispatchReady;
const driftDispatchReady = !!driftPlan && driftPlan.dispatchReady;
const allDispatchReady = workflowPlans.every((plan) => plan.dispatchReady);
const suggestedVerificationCommands = suggestedRepo ? [
  `node scripts/plan-publish-dispatch.mjs --live --repo ${suggestedRepo}`,
] : [];
const suggestedDispatchCommands = allDispatchReady && repoEvidenceReady ? [
  pagesPlan.dispatchCommand,
  driftPlan.dispatchCommand,
] : [];
const withheldDispatchCommands = suggestedDispatchCommands.length ? [] : [
  pagesPlan.dispatchCommand,
  driftPlan.dispatchCommand,
].filter(Boolean);
const dispatchSuggestionStatus = suggestedDispatchCommands.length
  ? "ready"
  : "withheld-until-all-dispatch-ready";
const suggestedCommands = [
  ...suggestedVerificationCommands,
  ...suggestedDispatchCommands,
];
const payload = {
  status: "pass",
  mode: live ? "live" : "dry-run",
  generatedAt: new Date().toISOString(),
  workflowName: pagesPlan.workflowName,
  workflowFile: pagesPlan.workflowFile,
  workflowPath: pagesPlan.workflowPath,
  target: pagesPlan.target,
  repositoryRoot,
  suggestedRepo,
  repoReplacementHint,
  repo,
  repoEvidenceReady,
  workflowScopeRequiredForInstall: true,
  workflowScopeChecked: workflowScope.checked,
  workflowScopeAvailable: workflowScope.available,
  workflowScope,
  workflowScopeInstallBlocked,
  pagesWorkflowDispatchRef,
  dispatchCommandExplicitRefReady: pagesPlan.dispatchCommand.includes(`-f ref=${pagesWorkflowDispatchRef}`),
  workflowScopeRefreshCommand,
  workflowScopeRecheckCommand,
  workflowScopeRefreshHandoff,
  workflowScopeApprovalHandoff,
  workflowListCommand: remote.command,
  workflowListFixture: workflowListFixture || null,
  workflowListSource: remote.source,
  localWorkflowTargetsReady,
  localTargetParityReady,
  remoteWorkflowFileCheckSource: remoteWorkflowFileCheckMatchesTarget
    ? "data/remote-workflow-file-check.json"
    : "missing_or_mismatched_target",
  remoteWorkflowFilesChecked,
  remoteWorkflowFilesReady,
  remoteWorkflowVisibilityReady,
  workflowDefaultBranchHandoff,
  workflowUiInstallReady,
  workflowUiInstallPlans,
  nextVerificationCommand,
  placeholderVerificationCommand,
  targetExists: pagesPlan.targetExists,
  dispatchReady,
  driftDispatchReady,
  allDispatchReady,
  dispatchCommand: pagesPlan.dispatchCommand,
  driftDispatchCommand: driftPlan.dispatchCommand,
  driftFollowupCommand: driftPlan.followupCommand,
  remoteWorkflow: pagesPlan.remoteWorkflow,
  workflowPlans,
  checks: pagesPlan.checks,
  blockers: allBlockers,
  nextActions,
  commands: [
    "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope",
    "node scripts/prepare-github-pages-workflow.mjs --stage-local",
    "node scripts/prepare-github-pages-workflow.mjs --write",
    "node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope",
    "node scripts/prepare-github-drift-watch-workflow.mjs --stage-local",
    "node scripts/prepare-github-drift-watch-workflow.mjs --write",
    workflowScopeRefreshCommand,
    workflowScopeRecheckCommand,
    workflowGitAddCommand,
    workflowGitCommitCommand,
    "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO",
    pagesPlan.dispatchCommand,
    driftPlan.dispatchCommand,
    driftPlan.followupCommand,
  ],
  suggestedVerificationCommands,
  suggestedDispatchCommands,
  withheldDispatchCommands,
  suggestedDispatchCommandCount: suggestedDispatchCommands.length,
  withheldDispatchCommandCount: withheldDispatchCommands.length,
  dispatchSuggestionStatus,
  suggestedCommands,
};

if (write) {
  payload.writtenTo = outputRelativePath;
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

console.log(JSON.stringify(payload, null, 2));
