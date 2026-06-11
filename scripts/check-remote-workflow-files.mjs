#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const write = args.has("--write");
const markdown = args.has("--markdown");
const outputRelativePath = "data/remote-workflow-file-check.json";
const outputPath = join(root, outputRelativePath);
const manualDispatchDocsUrl = "https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui";
const editFileDocsUrl = "https://docs.github.com/en/repositories/working-with-files/managing-files/editing-files";
const updateFileContentsDocsUrl = "https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents";
const suggestedRepo = suggestedRepoFromRemote();
const repo = argValue("--repo") || suggestedRepo || "OWNER/REPO";
const defaultBranch = argValue("--branch") || defaultBranchCandidate().branch;
const repoEvidenceReady = !!repo && repo !== "OWNER/REPO";
const workflowScopeRefreshCommand = "gh auth refresh -h github.com -s workflow";
const workflowScopeRefreshClipboardCommand = `${workflowScopeRefreshCommand} --clipboard`;
const workflowScopeInteractiveApprovalNote = "This is an interactive OAuth device flow; keep the terminal session open until gh reports success. If the browser approval is not completed, gh auth status will still omit workflow.";
const workflowScopeRecheckCommand = `node scripts/check-remote-workflow-files.mjs --repo ${repoEvidenceReady ? repo : suggestedRepo || "OWNER/REPO"} --write`;
const workflows = [
  {
    key: "pages",
    name: "Publish JooPark Pages",
    template: "docs/github-pages-workflow.yml",
    path: ".github/workflows/joopark-pages.yml",
  },
  {
    key: "drift-watch",
    name: "Watch JooPark Candidate Drift",
    template: "docs/github-drift-watch-workflow.yml",
    path: ".github/workflows/joopark-drift-watch.yml",
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

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function githubWorkflowUrl(targetRepo, path) {
  return targetRepo && targetRepo !== "OWNER/REPO"
    ? `https://github.com/${targetRepo}/actions/workflows/${path.split("/").pop()}`
    : "";
}

function githubNewFileUrl(targetRepo, branch, path) {
  return targetRepo && targetRepo !== "OWNER/REPO"
    ? `https://github.com/${targetRepo}/new/${encodeURIComponent(branch)}?filename=${encodeURIComponent(path)}`
    : "";
}

function githubEditFileUrl(targetRepo, branch, path) {
  return targetRepo && targetRepo !== "OWNER/REPO"
    ? `https://github.com/${targetRepo}/edit/${encodeURIComponent(branch)}/${path}`
    : "";
}

function githubBlobUrl(targetRepo, branch, path) {
  return targetRepo && targetRepo !== "OWNER/REPO"
    ? `https://github.com/${targetRepo}/blob/${encodeURIComponent(branch)}/${path}`
    : "";
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

function decodeContent(payload) {
  if (!payload || payload.type !== "file" || payload.encoding !== "base64" || typeof payload.content !== "string") {
    return null;
  }
  return Buffer.from(payload.content.replace(/\s/g, ""), "base64").toString("utf-8");
}

function fetchRemoteFile(targetRepo, path, branch) {
  if (!repoEvidenceReady) {
    return {
      checked: false,
      exists: false,
      command: "gh api --method GET repos/OWNER/REPO/contents/PATH -f ref=BRANCH",
      error: "repo placeholder OWNER/REPO must be replaced before remote file check",
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
      githubBlobSha: payload?.sha || "",
      size: Number(payload?.size || 0),
      htmlUrl: payload?.html_url || githubBlobUrl(targetRepo, branch, path),
      text: text || "",
      error: text ? "" : "GitHub contents response did not contain base64 file content",
    };
  } catch (error) {
    const message = String(error?.stderr || error?.message || error).slice(0, 360);
    return {
      checked: true,
      exists: false,
      command,
      githubBlobSha: "",
      size: 0,
      htmlUrl: githubBlobUrl(targetRepo, branch, path),
      text: "",
      error: message.includes("Not Found") || message.includes("404") ? "not found on default branch" : message,
    };
  }
}

function workflowCheck(entry) {
  const templatePath = join(root, entry.template);
  const templateExists = existsSync(templatePath);
  const templateText = templateExists ? readFileSync(templatePath, "utf-8") : "";
  const templateSha256 = templateExists ? sha256(templateText) : null;
  const remote = fetchRemoteFile(repo, entry.path, defaultBranch);
  const remoteSha256 = remote.exists ? sha256(remote.text) : null;
  const remoteMatchesTemplate = !!(templateSha256 && remoteSha256 && templateSha256 === remoteSha256);
  const editUrl = githubEditFileUrl(repo, defaultBranch, entry.path);
  const newFileUrl = githubNewFileUrl(repo, defaultBranch, entry.path);
  const installAction = !remote.checked
    ? "replace_repo_placeholder"
    : !remote.exists
      ? "create_missing_remote_file"
      : remoteMatchesTemplate
        ? "verified_remote_matches_template"
        : "replace_existing_remote_file";
  const remediation = {
    status: remoteMatchesTemplate ? "pass" : "action_required",
    installAction,
    targetPath: entry.path,
    defaultBranch,
    templatePath: entry.template,
    templateSha256,
    remoteSha256,
    remoteBlobSha: remote.githubBlobSha || "",
    githubNewFileUrl: newFileUrl,
    githubEditFileUrl: editUrl,
    templateCopyCommand: `pbcopy < ${shellQuote(entry.template)}`,
    githubEditFileOpenCommand: editUrl ? `open ${shellQuote(editUrl)}` : "",
    githubNewFileOpenCommand: newFileUrl ? `open ${shellQuote(newFileUrl)}` : "",
    docs: {
      editFile: editFileDocsUrl,
      updateFileContents: updateFileContentsDocsUrl,
      manualDispatch: manualDispatchDocsUrl,
    },
    nextStep: installAction === "replace_existing_remote_file"
      ? "Open the existing workflow file editor, replace the entire file with the local template contents, commit to the default branch, then rerun the remote workflow file check."
      : installAction === "create_missing_remote_file"
        ? "Open the GitHub new-file page, paste the local template contents, commit to the default branch, then rerun the remote workflow file check."
        : installAction === "replace_repo_placeholder"
          ? "Replace OWNER/REPO with the real repository before checking or editing the remote workflow file."
          : "No edit required; remote workflow file already matches the local template.",
  };
  return {
    key: entry.key,
    name: entry.name,
    template: entry.template,
    path: entry.path,
    defaultBranch,
    repo,
    templateExists,
    templateSha256,
    remoteChecked: remote.checked,
    remoteExists: remote.exists,
    remoteSha256,
    remoteMatchesTemplate,
    githubBlobSha: remote.githubBlobSha,
    remoteBlobSha: remote.githubBlobSha,
    size: remote.size,
    htmlUrl: remote.htmlUrl,
    workflowUrl: githubWorkflowUrl(repo, entry.path),
    githubNewFileUrl: newFileUrl,
    githubEditFileUrl: editUrl,
    installAction,
    remediation,
    templateCopyCommand: `pbcopy < ${shellQuote(entry.template)}`,
    githubNewFileOpenCommand: remediation.githubNewFileOpenCommand,
    githubEditFileOpenCommand: remediation.githubEditFileOpenCommand,
    command: remote.command,
    error: remote.error,
    blockers: [
      !templateExists ? `${entry.key}: missing local template ${entry.template}` : "",
      remote.checked && !remote.exists ? `${entry.key}: remote workflow file is not installed on ${defaultBranch}` : "",
      remote.exists && !remoteMatchesTemplate ? `${entry.key}: remote workflow file differs from local template` : "",
    ].filter(Boolean),
  };
}

function workflowUiFallbackText(checks) {
  const list = Array.isArray(checks) ? checks : [];
  const editCount = list.filter((check) => check.installAction === "replace_existing_remote_file").length;
  const createCount = list.filter((check) => check.installAction === "create_missing_remote_file").length;
  const readyCount = list.filter((check) => check.installAction === "verified_remote_matches_template").length;
  if (editCount > 0 && createCount > 0) {
    return "If browser approval cannot be completed, use each workflow row's installAction: open GitHub edit-file pages for existing mismatched files and new-file pages only for missing files.";
  }
  if (editCount > 0) {
    return "If browser approval cannot be completed, use each workflow row's installAction: open GitHub edit-file pages for existing mismatched files; do not use new-file links for replace_existing_remote_file rows.";
  }
  if (createCount > 0) {
    return "If browser approval cannot be completed, use the GitHub new-file links only for workflow files that are missing on the default branch.";
  }
  if (readyCount > 0) {
    return "No GitHub UI file change is required for workflow files that already match the local templates.";
  }
  return "If browser approval cannot be completed, use each workflow row's installAction to choose the GitHub create or edit page before rerunning verification.";
}

function workflowScopeApprovalHandoff({ workflowScopeInstallBlocked, dispatchPlanCommand, checks }) {
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
    dispatchPlanCommand,
    authStatusCommand: "gh auth status -h github.com",
    postApprovalAuthStatusCommand: "gh auth status -h github.com",
    incompleteApprovalSignal: "Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.",
    fallback: workflowUiFallbackText(checks),
    successSignals: [
      "Token scopes include workflow",
      "workflowScopeAvailable=true",
      "workflowScopeInstallBlocked=false",
      "remoteWorkflowFilesReady=true",
    ],
    stopCondition: "Do not run install-remote-workflow-files.mjs, gh workflow run, publish copy, or archive proof until workflowScopeAvailable=true or GitHub UI installation makes remoteWorkflowFilesReady=true.",
  };
}

function workflowInstallPacket({ generatedAt, checks, blockers, remoteWorkflowFilesReady, remoteInstallerCommand, nextVerificationCommand, dispatchPlanCommand, workflowScope, workflowScopeInstallBlocked, approvalHandoff }) {
  const scopeList = Array.isArray(workflowScope?.scopes) && workflowScope.scopes.length ? workflowScope.scopes.join(", ") : "none";
  const lines = [
    "JooPark Remote Workflow Install Packet",
    `Status: ${remoteWorkflowFilesReady ? "remote workflow files ready" : "action required - install workflow files on the default branch"}`,
    `Generated: ${generatedAt}`,
    `Repo: ${repo}`,
    `Default branch: ${defaultBranch}`,
    `workflowScopeAvailable: ${workflowScope?.available === true}`,
    `workflowScopeInstallBlocked: ${workflowScopeInstallBlocked}`,
    "",
    "Why this is required:",
    `- GitHub repository contents API check source: ${payloadSourceUrl}`,
    `- Existing workflow file edits use GitHub's file editor: ${editFileDocsUrl}`,
    `- API replacement of an existing workflow file requires the current blob SHA: ${updateFileContentsDocsUrl}`,
    `- Manual workflow dispatch requires workflow_dispatch and the workflow file on the default branch: ${manualDispatchDocsUrl}`,
    "",
    "Workflow scope preflight:",
    `- workflowScopeAvailable: ${workflowScope?.available === true}`,
    `- workflowScopeInstallBlocked: ${workflowScopeInstallBlocked}`,
    `- workflowScope.scopes: ${scopeList}`,
    `- refresh: ${workflowScopeRefreshCommand}`,
    `- refresh with clipboard: ${approvalHandoff.clipboardCommand}`,
    `- recheck: ${workflowScopeRecheckCommand}`,
    `- approvalUrl: ${approvalHandoff.approvalUrl}`,
    `- interactive approval required: ${approvalHandoff.interactiveApprovalRequired ? "true" : "false"}`,
    `- terminal wait required: ${approvalHandoff.terminalWaitRequired ? "true" : "false"}`,
    `- post-approval auth status: ${approvalHandoff.postApprovalAuthStatusCommand}`,
    `- incomplete approval signal: ${approvalHandoff.incompleteApprovalSignal}`,
    `- one-time device code policy: ${approvalHandoff.sensitiveValuePolicy}`,
    `- GitHub UI fallback: ${approvalHandoff.fallback}`,
    "",
    "Install or repair steps:",
  ];
  checks.forEach((check, index) => {
    lines.push(`${index + 1}. ${check.name}`);
    lines.push(`   Target: ${check.path}`);
    lines.push(`   Action: ${check.installAction}`);
    lines.push(`   Template: ${check.template}`);
    lines.push(`   Template SHA-256: ${check.templateSha256 || "missing"}`);
    lines.push(`   Remote SHA-256: ${check.remoteSha256 || "missing"}`);
    lines.push(`   Remote blob SHA: ${check.remoteBlobSha || "missing"}`);
    lines.push(`   Copy template: ${check.templateCopyCommand}`);
    lines.push(`   Open GitHub new-file page: ${check.githubNewFileOpenCommand || "replace OWNER/REPO first"}`);
    lines.push(`   Open GitHub edit page: ${check.githubEditFileOpenCommand || "replace OWNER/REPO first"}`);
    lines.push(`   Next: ${check.remediation?.nextStep || "Paste the template exactly, commit it to the default branch, then rerun verification."}`);
  });
  lines.push("");
  lines.push("Verification:");
  lines.push(`- ${remoteInstallerCommand}`);
  lines.push(`- ${nextVerificationCommand}`);
  lines.push(`- ${dispatchPlanCommand}`);
  lines.push("");
  lines.push("Post-install verification checklist:");
  lines.push("- If workflowScopeInstallBlocked: true, approve workflow scope with the refresh command or use the GitHub UI fallback before CLI remote install.");
  lines.push("- Re-run remote file check and confirm remoteWorkflowFilesChecked: true.");
  lines.push("- Confirm remoteWorkflowFilesReady: true.");
  checks.forEach((check) => {
    lines.push(`- Confirm ${check.key} remoteExists: true and remoteMatchesTemplate: true (${check.path}).`);
  });
  lines.push("- Re-run publish dispatch plan and confirm remoteWorkflowVisibilityReady: true.");
  lines.push("- Run dispatch only after allDispatchReady: true.");
  lines.push("");
  lines.push("Current blockers:");
  (blockers.length ? blockers : ["none"]).forEach((blocker) => lines.push(`- ${blocker}`));
  lines.push("");
  lines.push("Guard:");
  lines.push(`- ${approvalHandoff.stopCondition}`);
  lines.push("- Do not run gh workflow run until remoteWorkflowFilesReady: true and allDispatchReady: true.");
  return lines.join("\n");
}

const workflowScope = inspectWorkflowScope();
const checks = workflows.map(workflowCheck);
const blockers = checks.flatMap((check) => check.blockers);
const remoteWorkflowFilesReady = checks.length > 0 && checks.every((check) => check.remoteExists && check.remoteMatchesTemplate);
const remoteInstallerCommand = `node scripts/install-remote-workflow-files.mjs --repo ${repoEvidenceReady ? repo : suggestedRepo || "OWNER/REPO"} --write --verify`;
const nextVerificationCommand = `node scripts/check-remote-workflow-files.mjs --repo ${repoEvidenceReady ? repo : "OWNER/REPO"} --write`;
const dispatchPlanCommand = `node scripts/plan-publish-dispatch.mjs --live --repo ${repoEvidenceReady ? repo : suggestedRepo || "OWNER/REPO"} --write`;
const generatedAt = new Date().toISOString();
const payloadSourceUrl = "https://docs.github.com/en/rest/repos/contents#get-repository-content";
const workflowScopeInstallBlocked = !remoteWorkflowFilesReady && workflowScope.available !== true;
const approvalHandoff = workflowScopeApprovalHandoff({ workflowScopeInstallBlocked, dispatchPlanCommand, checks });
const payload = {
  status: "pass",
  mode: repoEvidenceReady ? "live" : "dry-run",
  generatedAt,
  repo,
  suggestedRepo,
  repoEvidenceReady,
  defaultBranch,
  source: "GitHub REST repository contents API",
  sourceUrl: payloadSourceUrl,
  manualDispatchDocsUrl,
  editFileDocsUrl,
  updateFileContentsDocsUrl,
  workflowScopeChecked: workflowScope.checked,
  workflowScopeAvailable: workflowScope.available,
  workflowScopeInstallBlocked,
  workflowScope,
  workflowScopeRefreshCommand,
  workflowScopeRecheckCommand,
  workflowScopeApprovalHandoff: approvalHandoff,
  remoteWorkflowFilesChecked: repoEvidenceReady,
  remoteWorkflowFilesReady,
  checks,
  blockers,
  remediationSummary: {
    status: remoteWorkflowFilesReady ? "pass" : "action_required",
    createCount: checks.filter((check) => check.installAction === "create_missing_remote_file").length,
    editCount: checks.filter((check) => check.installAction === "replace_existing_remote_file").length,
    readyCount: checks.filter((check) => check.installAction === "verified_remote_matches_template").length,
    placeholderCount: checks.filter((check) => check.installAction === "replace_repo_placeholder").length,
    currentAction: checks.some((check) => check.installAction === "replace_existing_remote_file")
      ? "replace_existing_remote_file"
      : checks.some((check) => check.installAction === "create_missing_remote_file")
        ? "create_missing_remote_file"
        : remoteWorkflowFilesReady
          ? "verified_remote_matches_template"
          : "replace_repo_placeholder",
  },
  remoteInstallerCommand,
  nextVerificationCommand,
  dispatchPlanCommand,
  nextActions: remoteWorkflowFilesReady
    ? [
        `Run ${dispatchPlanCommand} until remoteWorkflowVisibilityReady and allDispatchReady are true.`,
        "Dispatch Pages and Drift Watch only after workflow visibility and dispatch gates pass.",
      ]
    : [
        workflowScopeInstallBlocked
          ? `Current CLI token lacks workflow scope; run ${workflowScopeRefreshCommand}, then rerun ${workflowScopeRecheckCommand}, or use the GitHub UI fallback.`
          : "CLI workflow scope is available; remote installer can create or update workflow files.",
        "Create or update both workflow files on the repository default branch with the exact local template contents.",
        `Run ${nextVerificationCommand} until remoteWorkflowFilesReady is true.`,
        `Then run ${dispatchPlanCommand} to confirm GitHub Actions visibility.`,
      ],
};
payload.installPacket = workflowInstallPacket({ generatedAt, checks, blockers, remoteWorkflowFilesReady, remoteInstallerCommand, nextVerificationCommand, dispatchPlanCommand, workflowScope, workflowScopeInstallBlocked, approvalHandoff });

if (write) {
  payload.writtenTo = outputRelativePath;
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

if (markdown) {
  const lines = [
    "# JooPark Remote Workflow File Check",
    "",
    `- status: ${payload.status}`,
    `- repo: ${payload.repo}`,
    `- defaultBranch: ${payload.defaultBranch}`,
    `- remoteWorkflowFilesReady: ${payload.remoteWorkflowFilesReady}`,
    `- source: ${payload.sourceUrl}`,
    `- editFileDocs: ${payload.editFileDocsUrl}`,
    `- remediationStatus: ${payload.remediationSummary.status}`,
    `- remediationAction: ${payload.remediationSummary.currentAction}`,
    "",
  ];
  for (const check of checks) {
    lines.push(`## ${check.name}`);
    lines.push(`- path: \`${check.path}\``);
    lines.push(`- templateSha256: \`${check.templateSha256 || "missing"}\``);
    lines.push(`- remoteSha256: \`${check.remoteSha256 || "missing"}\``);
    lines.push(`- remoteBlobSha: \`${check.remoteBlobSha || "missing"}\``);
    lines.push(`- remoteExists: ${check.remoteExists}`);
    lines.push(`- remoteMatchesTemplate: ${check.remoteMatchesTemplate}`);
    lines.push(`- installAction: ${check.installAction}`);
    lines.push(`- githubEditFileUrl: ${check.githubEditFileUrl || "replace OWNER/REPO first"}`);
    lines.push(`- githubEditFileOpenCommand: \`${check.githubEditFileOpenCommand || "replace OWNER/REPO first"}\``);
    lines.push(`- command: \`${check.command}\``);
    if (check.error) lines.push(`- error: ${check.error}`);
    lines.push("");
  }
  lines.push("## Next Actions");
  payload.nextActions.forEach((action) => lines.push(`- ${action}`));
  console.log(lines.join("\n"));
} else {
  console.log(JSON.stringify(payload, null, 2));
}
