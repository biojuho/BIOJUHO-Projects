#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const write = args.has("--write");
const markdown = args.has("--markdown");
const verify = args.has("--verify");
const force = args.has("--force");
const suggestedRepo = suggestedRepoFromRemote();
const repo = argValue("--repo") || suggestedRepo || "OWNER/REPO";
const repoEvidenceReady = !!repo && repo !== "OWNER/REPO";
const workflowScope = inspectWorkflowScope();
const defaultBranch = argValue("--branch") || remoteDefaultBranch(repo) || defaultBranchCandidate().branch;
const commitMessage = argValue("--message") || "Install JooPark publish workflows";
const workflowScopeRefreshCommand = "gh auth refresh -h github.com -s workflow";
const workflowScopeRefreshClipboardCommand = `${workflowScopeRefreshCommand} --clipboard`;
const workflowScopeInteractiveApprovalNote = "This is an interactive OAuth device flow; keep the terminal session open until gh reports success. If the browser approval is not completed, gh auth status will still omit workflow.";
const workflowScopeRecheckCommand = `node scripts/install-remote-workflow-files.mjs --repo ${repoEvidenceReady ? repo : suggestedRepo || "OWNER/REPO"} --write --verify`;
const remoteFileCheckCommand = `node scripts/check-remote-workflow-files.mjs --repo ${repoEvidenceReady ? repo : "OWNER/REPO"} --write`;
const dispatchPlanCommand = `node scripts/plan-publish-dispatch.mjs --live --repo ${repoEvidenceReady ? repo : suggestedRepo || "OWNER/REPO"} --write`;
const repositoryContentsApiUrl = "https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents";

const workflows = [
  {
    key: "pages",
    name: "Publish JooPark Pages",
    template: "docs/github-pages-workflow.yml",
    path: ".github/workflows/joopark-pages.yml",
    requiredTerms: [
      "workflow_dispatch:",
      "permissions:",
      "pages: write",
      "id-token: write",
      "attestations: write",
      "actions/attest@v4",
      "subject-path: dist/release/**",
      "actions/upload-pages-artifact@v4",
      "actions/deploy-pages@v4",
      "node scripts/package-release.mjs",
      "node scripts/verify-release.mjs",
    ],
  },
  {
    key: "drift-watch",
    name: "Watch JooPark Candidate Drift",
    template: "docs/github-drift-watch-workflow.yml",
    path: ".github/workflows/joopark-drift-watch.yml",
    requiredTerms: [
      "workflow_dispatch:",
      "schedule:",
      "permissions:",
      "contents: read",
      "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
      "node scripts/check-candidate-freshness-drift.mjs --live",
      "fail-on-drift",
    ],
  },
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

function gitText(argsList) {
  try {
    return execFileSync("git", argsList, {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function githubNameWithOwner(remoteUrl) {
  const trimmed = String(remoteUrl || "").trim();
  const httpsMatch = trimmed.match(/^https:\/\/github\.com\/([^/]+)\/(.+?)(?:\.git)?$/i);
  if (httpsMatch) return `${httpsMatch[1]}/${httpsMatch[2].replace(/\.git$/i, "")}`;
  const sshMatch = trimmed.match(/^(?:git@github\.com:|ssh:\/\/git@github\.com\/)([^/]+)\/(.+?)(?:\.git)?$/i);
  if (sshMatch) return `${sshMatch[1]}/${sshMatch[2].replace(/\.git$/i, "")}`;
  return "";
}

function suggestedRepoFromRemote() {
  const remotes = gitText(["remote"]).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const remoteName = remotes.includes("biojuho-projects") ? "biojuho-projects" : remotes.includes("origin") ? "origin" : remotes[0] || "";
  if (!remoteName) return "";
  return githubNameWithOwner(gitText(["config", "--get", `remote.${remoteName}.url`]));
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

function inspectWorkflowScope() {
  try {
    const output = execFileSync("gh", ["api", "-i", "user"], {
      cwd: root,
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

function workflowUiFallbackText(operationRows = []) {
  const operationsList = Array.isArray(operationRows) ? operationRows : [];
  const hasUpdate = operationsList.some((operation) => operation.operation === "update");
  const hasCreate = operationsList.some((operation) => operation.operation === "create");
  const allReady = operationsList.length > 0 && operationsList.every((operation) => operation.operation === "noop");
  if (hasUpdate) {
    return "If browser approval cannot be completed, use each operation value: open GitHub edit-file pages for update rows, new-file pages for create rows, and do not use new-file links for update rows.";
  }
  if (hasCreate) {
    return "If browser approval cannot be completed, use each operation value: open GitHub new-file pages only for create rows before rerunning verification.";
  }
  if (allReady) {
    return "No GitHub UI file change is required; both remote workflow files already match the local templates.";
  }
  return "If browser approval cannot be completed, resolve blocked operations first, then use each operation value to choose the GitHub create or edit page before rerunning verification.";
}

function workflowScopeApprovalHandoff({ workflowScopeInstallBlocked, operations: operationRows = [] }) {
  return {
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
    remoteFileCheckCommand,
    dispatchPlanCommand,
    authStatusCommand: "gh auth status -h github.com",
    postApprovalAuthStatusCommand: "gh auth status -h github.com",
    incompleteApprovalSignal: "Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.",
    fallback: workflowUiFallbackText(operationRows),
    successSignals: [
      "Token scopes include workflow",
      "workflowScopeAvailable=true",
      "workflowScopeInstallBlocked=false",
      "remoteWorkflowFilesReady=true",
    ],
    stopCondition: "Do not run remote install, gh workflow run, publish copy, or archive proof until workflowScopeAvailable=true or GitHub UI installation makes remoteWorkflowFilesReady=true.",
  };
}

function remoteDefaultBranch(targetRepo) {
  if (!targetRepo || targetRepo === "OWNER/REPO") return "";
  try {
    return execFileSync("gh", ["api", `repos/${targetRepo}`, "--jq", ".default_branch"], {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
  } catch {
    return "";
  }
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function decodeContent(payload) {
  if (!payload || payload.type !== "file" || payload.encoding !== "base64" || typeof payload.content !== "string") {
    return null;
  }
  return Buffer.from(payload.content.replace(/\s/g, ""), "base64").toString("utf-8");
}

function shellQuote(value) {
  return `'${String(value || "").replace(/'/g, "'\\''")}'`;
}

function readTemplate(entry) {
  const path = join(root, entry.template);
  if (!existsSync(path)) {
    return {
      exists: false,
      text: "",
      sha256: null,
      bytes: 0,
      missingTerms: entry.requiredTerms,
    };
  }
  const text = readFileSync(path, "utf-8");
  return {
    exists: true,
    text,
    sha256: sha256(text),
    bytes: Buffer.byteLength(text),
    missingTerms: entry.requiredTerms.filter((term) => !text.includes(term)),
  };
}

function fetchRemoteFile(targetRepo, path, branch) {
  if (!repoEvidenceReady) {
    return {
      checked: false,
      exists: false,
      command: "gh api --method GET repos/OWNER/REPO/contents/PATH -f ref=BRANCH",
      text: "",
      githubBlobSha: "",
      error: "repo placeholder OWNER/REPO must be replaced before remote install",
    };
  }
  const command = `gh api --method GET repos/${targetRepo}/contents/${path} -f ref=${branch}`;
  try {
    const output = execFileSync("gh", ["api", "--method", "GET", `repos/${targetRepo}/contents/${path}`, "-f", `ref=${branch}`], {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    const payload = JSON.parse(output || "{}");
    const text = decodeContent(payload);
    return {
      checked: true,
      exists: !!text,
      command,
      text: text || "",
      githubBlobSha: payload?.sha || "",
      size: Number(payload?.size || 0),
      htmlUrl: payload?.html_url || "",
      error: text ? "" : "GitHub contents response did not contain base64 file content",
    };
  } catch (error) {
    const message = String(error?.stderr || error?.message || error).slice(0, 360);
    return {
      checked: true,
      exists: false,
      command,
      text: "",
      githubBlobSha: "",
      size: 0,
      htmlUrl: `https://github.com/${targetRepo}/blob/${encodeURIComponent(branch)}/${path}`,
      error: message.includes("Not Found") || message.includes("404") ? "not found on default branch" : message,
    };
  }
}

function installRemoteFile(operation) {
  const argsList = [
    "api",
    "--method",
    "PUT",
    `repos/${repo}/contents/${operation.path}`,
    "-f",
    `message=${commitMessage}: ${operation.name}`,
    "-f",
    `content=${Buffer.from(operation.templateText, "utf-8").toString("base64")}`,
    "-f",
    `branch=${defaultBranch}`,
  ];
  if (operation.githubBlobSha) argsList.push("-f", `sha=${operation.githubBlobSha}`);
  const command = `gh api --method PUT repos/${repo}/contents/${operation.path} -f message=${shellQuote(`${commitMessage}: ${operation.name}`)} -f content=<base64> -f branch=${shellQuote(defaultBranch)}${operation.githubBlobSha ? " -f sha=<remote sha>" : ""}`;
  try {
    const output = execFileSync("gh", argsList, {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    const payload = JSON.parse(output || "{}");
    return {
      status: "pass",
      command,
      commitSha: payload?.commit?.sha || "",
      contentSha: payload?.content?.sha || "",
      htmlUrl: payload?.content?.html_url || "",
    };
  } catch (error) {
    return {
      status: "fail",
      command,
      error: String(error?.stderr || error?.message || error).slice(0, 640),
    };
  }
}

function operationFor(entry) {
  const template = readTemplate(entry);
  const remote = fetchRemoteFile(repo, entry.path, defaultBranch);
  const remoteSha256 = remote.exists ? sha256(remote.text) : null;
  const remoteMatchesTemplate = !!(template.sha256 && remoteSha256 && template.sha256 === remoteSha256);
  const targetOperation = !template.exists || template.missingTerms.length > 0
    ? "blocked"
    : !repoEvidenceReady
      ? "blocked"
      : !remote.checked
        ? "blocked"
        : !remote.exists
          ? "create"
          : remoteMatchesTemplate
            ? "noop"
            : "update";
  const writeRequired = targetOperation === "create" || targetOperation === "update";
  return {
    key: entry.key,
    name: entry.name,
    template: entry.template,
    path: entry.path,
    defaultBranch,
    templateExists: template.exists,
    templateSha256: template.sha256,
    templateBytes: template.bytes,
    missingTerms: template.missingTerms,
    remoteChecked: remote.checked,
    remoteExists: remote.exists,
    remoteSha256,
    remoteMatchesTemplate,
    githubBlobSha: remote.githubBlobSha,
    remoteError: remote.error,
    operation: targetOperation,
    writeRequired,
    writeBlocked: writeRequired && workflowScope.available !== true,
    command: remote.command,
    putCommand: `gh api --method PUT repos/${repoEvidenceReady ? repo : "OWNER/REPO"}/contents/${entry.path} -f message=${shellQuote(`${commitMessage}: ${entry.name}`)} -f content=<base64> -f branch=${shellQuote(defaultBranch)}${remote.githubBlobSha ? " -f sha=<remote sha>" : ""}`,
    templateText: template.text,
    blockers: [
      !template.exists ? `${entry.key}: missing local template ${entry.template}` : "",
      template.missingTerms.length > 0 ? `${entry.key}: local template missing required terms` : "",
      !repoEvidenceReady ? `${entry.key}: replace OWNER/REPO before remote install` : "",
      remote.checked && remote.error && remote.error !== "not found on default branch" ? `${entry.key}: remote check failed: ${remote.error}` : "",
      writeRequired && workflowScope.available !== true ? `${entry.key}: workflow scope required before remote ${targetOperation}` : "",
    ].filter(Boolean),
  };
}

function execNode(argsList, options = {}) {
  try {
    return {
      ok: true,
      stdout: execFileSync(process.execPath, argsList, {
        cwd: root,
        encoding: "utf-8",
        stdio: ["ignore", "pipe", "pipe"],
        timeout: options.timeout || 15000,
      }),
      stderr: "",
      error: "",
    };
  } catch (error) {
    return {
      ok: false,
      stdout: error.stdout || "",
      stderr: error.stderr || "",
      error: String(error?.message || error),
    };
  }
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function runVerificationCommands() {
  if (!repoEvidenceReady) {
    return {
      status: "skipped",
      reason: "repo placeholder OWNER/REPO must be replaced before verification",
      commands: [remoteFileCheckCommand, dispatchPlanCommand],
    };
  }
  const commands = [
    {
      id: "remote_file_check",
      command: remoteFileCheckCommand,
      args: ["scripts/check-remote-workflow-files.mjs", "--repo", repo, "--write"],
    },
    {
      id: "publish_dispatch_plan",
      command: dispatchPlanCommand,
      args: ["scripts/plan-publish-dispatch.mjs", "--live", "--repo", repo, "--write"],
    },
  ].map((entry) => {
    const result = execNode(entry.args, { timeout: 20000 });
    const payload = parseJson(result.stdout);
    return {
      id: entry.id,
      command: entry.command,
      status: result.ok ? "pass" : "fail",
      result: payload || {
        stdout: result.stdout.trim(),
        stderr: result.stderr.trim(),
        error: result.error,
      },
    };
  });
  return {
    status: commands.every((entry) => entry.status === "pass") ? "pass" : "fail",
    commands,
  };
}

function publicOperation(operation) {
  const { templateText, ...rest } = operation;
  return rest;
}

function markdownSummary(payload) {
  const lines = [
    "# JooPark Remote Workflow Installer",
    "",
    `- status: ${payload.status}`,
    `- mode: ${payload.mode}`,
    `- repo: ${payload.repo}`,
    `- defaultBranch: ${payload.defaultBranch}`,
    `- workflowScopeAvailable: ${payload.workflowScopeAvailable}`,
    `- workflowScopeInstallBlocked: ${payload.workflowScopeInstallBlocked}`,
    `- remoteWorkflowFilesReady: ${payload.remoteWorkflowFilesReady}`,
    "",
    "## Workflow Scope Approval",
    `- status: ${payload.workflowScopeApprovalHandoff?.status || "not_available"}`,
    `- command: ${payload.workflowScopeApprovalHandoff?.command || workflowScopeRefreshCommand}`,
    `- clipboardCommand: ${payload.workflowScopeApprovalHandoff?.clipboardCommand || workflowScopeRefreshClipboardCommand}`,
    `- approvalUrl: ${payload.workflowScopeApprovalHandoff?.approvalUrl || "https://github.com/login/device"}`,
    `- interactiveApprovalRequired: ${payload.workflowScopeApprovalHandoff?.interactiveApprovalRequired ? "true" : "false"}`,
    `- terminalWaitRequired: ${payload.workflowScopeApprovalHandoff?.terminalWaitRequired ? "true" : "false"}`,
    `- postApprovalAuthStatusCommand: ${payload.workflowScopeApprovalHandoff?.postApprovalAuthStatusCommand || "gh auth status -h github.com"}`,
    `- incompleteApprovalSignal: ${payload.workflowScopeApprovalHandoff?.incompleteApprovalSignal || "Token scopes still omit workflow after the refresh attempt."}`,
    `- recheck: ${payload.workflowScopeApprovalHandoff?.recheckCommand || workflowScopeRecheckCommand}`,
    `- fallback: ${payload.workflowScopeApprovalHandoff?.fallback || "Use the GitHub UI fallback if browser approval cannot be completed."}`,
    `- stopCondition: ${payload.workflowScopeApprovalHandoff?.stopCondition || "Do not run gh workflow run until installation proof is ready."}`,
    "",
    "## Operations",
  ];
  payload.operations.forEach((operation) => {
    lines.push(`- ${operation.key}: ${operation.operation} (${operation.path})`);
    lines.push(`  - remoteExists: ${operation.remoteExists}`);
    lines.push(`  - remoteMatchesTemplate: ${operation.remoteMatchesTemplate}`);
    if (operation.blockers.length > 0) lines.push(`  - blockers: ${operation.blockers.join("; ")}`);
  });
  lines.push("", "## Commands");
  payload.nextActions.forEach((action) => lines.push(`- ${action}`));
  return `${lines.join("\n")}\n`;
}

const operations = workflows.map(operationFor);
const writesRequired = operations.filter((operation) => operation.writeRequired);
const operationBlockers = operations.flatMap((operation) => operation.blockers);
const workflowScopeInstallBlocked = writesRequired.length > 0 && workflowScope.available !== true;
const approvalHandoff = workflowScopeApprovalHandoff({ workflowScopeInstallBlocked, operations });
const remoteWorkflowFilesReady = operations.length > 0 && operations.every((operation) => operation.remoteMatchesTemplate);
const remoteWriteReady = write && repoEvidenceReady && workflowScope.available === true && writesRequired.length > 0 && operationBlockers.length === 0;
const writeResults = [];

function blockedPayload(blockers, nextActions) {
  return {
    status: "blocked",
    mode: write ? "write" : "dry-run",
    generatedAt: new Date().toISOString(),
    repo,
    suggestedRepo,
    repoEvidenceReady,
    defaultBranch,
    force,
    source: "GitHub REST repository contents API",
    sourceUrl: repositoryContentsApiUrl,
    workflowScopeChecked: workflowScope.checked,
    workflowScopeAvailable: workflowScope.available,
    workflowScopeInstallBlocked,
    workflowScope,
    workflowScopeRefreshCommand,
    workflowScopeRecheckCommand,
    workflowScopeApprovalHandoff: approvalHandoff,
    remoteWriteReady: false,
    remoteWorkflowFilesReady,
    writesRequired: writesRequired.length,
    operations: operations.map(publicOperation),
    blockers,
    postInstallVerificationCommands: [remoteFileCheckCommand, dispatchPlanCommand],
    nextActions,
  };
}

if (write && workflowScopeInstallBlocked) {
  const payload = blockedPayload(
    [...operationBlockers, "workflow scope: run gh auth refresh -h github.com -s workflow before remote workflow installation"],
    [
      workflowScopeRefreshCommand,
      workflowScopeRecheckCommand,
      workflowUiFallbackText(operations),
      "Do not run dispatch until remoteWorkflowFilesReady: true and allDispatchReady: true.",
    ],
  );
  console.log(markdown ? markdownSummary(payload) : JSON.stringify(payload, null, 2));
  process.exit(1);
}

if (write && operationBlockers.length > 0) {
  const payload = blockedPayload(
    operationBlockers,
    [
      "Fix blocked operations before retrying remote workflow installation.",
      workflowScopeRecheckCommand,
      "Do not run dispatch until remoteWorkflowFilesReady: true and allDispatchReady: true.",
    ],
  );
  console.log(markdown ? markdownSummary(payload) : JSON.stringify(payload, null, 2));
  process.exit(1);
}

if (remoteWriteReady) {
  for (const operation of writesRequired) {
    writeResults.push({
      key: operation.key,
      operation: operation.operation,
      path: operation.path,
      result: installRemoteFile(operation),
    });
  }
}

const verification = verify && (!write || writeResults.every((entry) => entry.result.status === "pass"))
  ? runVerificationCommands()
  : {
      status: "skipped",
      reason: verify ? "remote write did not complete" : "pass --verify to run post-install verification commands",
      commands: [remoteFileCheckCommand, dispatchPlanCommand],
    };
const writeFailed = writeResults.some((entry) => entry.result.status !== "pass");

const payload = {
  status: writeFailed ? "fail" : "pass",
  mode: write ? "write" : "dry-run",
  generatedAt: new Date().toISOString(),
  repo,
  suggestedRepo,
  repoEvidenceReady,
  defaultBranch,
  force,
  source: "GitHub REST repository contents API",
  sourceUrl: repositoryContentsApiUrl,
  workflowScopeChecked: workflowScope.checked,
  workflowScopeAvailable: workflowScope.available,
  workflowScopeInstallBlocked,
  workflowScope,
  workflowScopeRefreshCommand,
  workflowScopeRecheckCommand,
  workflowScopeApprovalHandoff: approvalHandoff,
  remoteWriteReady,
  remoteWorkflowFilesReady,
  writesRequired: writesRequired.length,
  operations: operations.map(publicOperation),
  writeResults,
  verification,
  blockers: operationBlockers,
  postInstallVerificationCommands: [remoteFileCheckCommand, dispatchPlanCommand],
  nextActions: remoteWorkflowFilesReady
    ? [
        dispatchPlanCommand,
        "Run dispatch only after allDispatchReady: true.",
      ]
    : [
        workflowScope.available === true ? `node scripts/install-remote-workflow-files.mjs --repo ${repoEvidenceReady ? repo : "OWNER/REPO"} --write --verify` : workflowScopeRefreshCommand,
        workflowScopeRecheckCommand,
        "Do not run dispatch until remoteWorkflowFilesReady: true and allDispatchReady: true.",
      ],
};

console.log(markdown ? markdownSummary(payload) : JSON.stringify(payload, null, 2));
process.exit(payload.status === "pass" ? 0 : 1);
