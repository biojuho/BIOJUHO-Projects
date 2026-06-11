#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = gitRoot();
const args = new Set(process.argv.slice(2));
const markdown = args.has("--markdown");
const write = args.has("--write");
const outputRelativePath = "data/workflow-ui-install-plan.json";
const outputPath = join(root, outputRelativePath);
const workflows = [
  {
    key: "pages",
    name: "Publish JooPark Pages",
    template: "docs/github-pages-workflow.yml",
    target: ".github/workflows/joopark-pages.yml",
    commitMessage: "Add JooPark Pages publish workflow",
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
      "operations-copy-actions.js",
      "dialog-shell.js",
      "project-picker.js",
      "global-search.js",
      "command-palette.js",
      "review-result-view.js",
      "review-execution-checklist.js",
      "review-issue-payload.js",
      "review-result-state.js",
      "review-result-draft-state.js",
      "review-creation-actions.js",
      "review-package-view.js",
      "review-artifact-view.js",
      "review-artifact-state.js",
      "review-copy-actions.js",
      "review-submission-copy.js",
      "review-recommendation-export.js",
    ],
  },
  {
    key: "drift-watch",
    name: "Watch JooPark Candidate Drift",
    template: "docs/github-drift-watch-workflow.yml",
    target: ".github/workflows/joopark-drift-watch.yml",
    commitMessage: "Add JooPark candidate drift watch workflow",
    requiredTerms: [
      "workflow_dispatch:",
      "schedule:",
      "contents: read",
      "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
      "node scripts/check-candidate-freshness-drift.mjs --live",
      "fail-on-drift",
    ],
  },
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

function readJson(path, fallback = null) {
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return fallback;
  }
}

function gitOutput(args) {
  try {
    return execFileSync("git", args, {
      cwd: repositoryRoot,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function preferredRemoteName() {
  const remotes = gitOutput(["remote"]).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (remotes.includes("biojuho-projects")) return "biojuho-projects";
  if (remotes.includes("origin")) return "origin";
  return remotes[0] || "";
}

function normalizeGithubRepoUrl(remoteUrl) {
  const trimmed = String(remoteUrl || "").trim();
  if (!trimmed) return "";
  const httpsMatch = trimmed.match(/^https:\/\/github\.com\/([^/]+)\/(.+?)(?:\.git)?$/i);
  if (httpsMatch) return `https://github.com/${httpsMatch[1]}/${httpsMatch[2].replace(/\.git$/i, "")}`;
  const sshMatch = trimmed.match(/^(?:git@github\.com:|ssh:\/\/git@github\.com\/)([^/]+)\/(.+?)(?:\.git)?$/i);
  if (sshMatch) return `https://github.com/${sshMatch[1]}/${sshMatch[2].replace(/\.git$/i, "")}`;
  return "";
}

function defaultBranchCandidate(remoteName) {
  const candidates = ["main", "master"];
  const branch = candidates.find((candidate) => {
    return !!gitOutput(["show-ref", "--verify", `refs/remotes/${remoteName}/${candidate}`]);
  });
  return {
    branch: branch || "main",
    source: branch ? `local refs/remotes/${remoteName}/${branch}` : "fallback-main",
  };
}

function githubFileUrls(repoUrl, branch, target) {
  if (!repoUrl) {
    return {
      githubNewFileUrl: null,
      githubEditFileUrl: null,
      githubBlobUrl: null,
      githubWorkflowUrl: null,
    };
  }
  const encodedBranch = encodeURIComponent(branch);
  return {
    githubNewFileUrl: `${repoUrl}/new/${encodedBranch}?filename=${encodeURIComponent(target)}`,
    githubEditFileUrl: `${repoUrl}/edit/${encodedBranch}/${target}`,
    githubBlobUrl: `${repoUrl}/blob/${encodedBranch}/${target}`,
    githubWorkflowUrl: `${repoUrl}/actions/workflows/${target.split("/").pop()}`,
  };
}

function githubRepoSlug(repoUrl) {
  const match = String(repoUrl || "").match(/^https:\/\/github\.com\/([^/]+\/[^/]+)$/i);
  return match ? match[1].replace(/\.git$/i, "") : "";
}

function shellQuote(value) {
  return `'${String(value || "").replace(/'/g, "'\\''")}'`;
}

const remoteName = preferredRemoteName();
const remoteUrl = remoteName ? gitOutput(["config", "--get", `remote.${remoteName}.url`]) : "";
const repositoryUrl = normalizeGithubRepoUrl(remoteUrl);
const suggestedRepo = githubRepoSlug(repositoryUrl);
const repoReplacementHint = suggestedRepo
  ? `Replace OWNER/REPO with ${suggestedRepo}`
  : "Replace OWNER/REPO with the exact GitHub owner/name repo";
const placeholderVerificationCommand = "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO";
const nextVerificationCommand = `node scripts/plan-publish-dispatch.mjs --live --repo ${suggestedRepo || "OWNER/REPO"}`;
const defaultBranch = defaultBranchCandidate(remoteName);
const actionsUrl = repositoryUrl ? `${repositoryUrl}/actions` : null;
const remoteWorkflowFileCheckPath = "data/remote-workflow-file-check.json";
const remoteWorkflowFileCheck = readJson(join(root, remoteWorkflowFileCheckPath), null);

function remoteWorkflowCheckFor(entry) {
  const checks = Array.isArray(remoteWorkflowFileCheck?.checks) ? remoteWorkflowFileCheck.checks : [];
  return checks.find((check) => {
    const remediation = check?.remediation && typeof check.remediation === "object" ? check.remediation : {};
    return check?.key === entry.key ||
      check?.path === entry.target ||
      check?.targetPath === entry.target ||
      remediation.targetPath === entry.target;
  }) || null;
}

function workflowUiInstallAction(remoteFileCheck) {
  const remediation = remoteFileCheck?.remediation && typeof remoteFileCheck.remediation === "object" ? remoteFileCheck.remediation : {};
  const action = remoteFileCheck?.installAction || remediation.installAction || "";
  if (["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(action)) {
    return action;
  }
  if (remoteFileCheck?.remoteExists === true && remoteFileCheck?.remoteMatchesTemplate === true) {
    return "verified_remote_matches_template";
  }
  if (remoteFileCheck?.remoteExists === true) {
    return "replace_existing_remote_file";
  }
  return "create_missing_remote_file";
}

function workflowUiInstallLabel(action) {
  if (action === "replace_existing_remote_file") return "Replace existing remote file";
  if (action === "verified_remote_matches_template") return "No GitHub UI file change required";
  return "Create missing remote file";
}

function workflowUiInstallInstruction(plan) {
  if (plan.installAction === "replace_existing_remote_file") {
    return `Open the existing GitHub edit-file page for ${plan.targetRepositoryPath}, replace the entire file with the copied template, and commit to ${plan.defaultBranch}.`;
  }
  if (plan.installAction === "verified_remote_matches_template") {
    return `No GitHub UI edit is required for ${plan.targetRepositoryPath}; the remote file already matches the local template.`;
  }
  return `Open the GitHub new-file page, set the file name to ${plan.githubFileNameFieldValue}, paste the copied template, and commit to ${plan.defaultBranch}.`;
}

function workflowPlan(entry) {
  const templatePath = join(root, entry.template);
  const targetPath = join(repositoryRoot, entry.target);
  const templateDigest = fileDigest(templatePath);
  const targetDigest = fileDigest(targetPath);
  const templateText = templateDigest.text;
  const missingTerms = entry.requiredTerms.filter((term) => !templateText.includes(term));
  const urls = githubFileUrls(repositoryUrl, defaultBranch.branch, entry.target);
  const remoteFileCheck = remoteWorkflowCheckFor(entry);
  const remediation = remoteFileCheck?.remediation && typeof remoteFileCheck.remediation === "object" ? remoteFileCheck.remediation : {};
  const installAction = workflowUiInstallAction(remoteFileCheck);
  const githubNewFileUrl = remediation.githubNewFileUrl || remoteFileCheck?.githubNewFileUrl || urls.githubNewFileUrl;
  const githubEditFileUrl = remediation.githubEditFileUrl || remoteFileCheck?.githubEditFileUrl || urls.githubEditFileUrl;
  const templateCopyCommand = `pbcopy < ${shellQuote(entry.template)}`;
  const localTemplateHashCommand = `shasum -a 256 ${shellQuote(entry.template)}`;
  const githubNewFileOpenCommand = remediation.githubNewFileOpenCommand || remoteFileCheck?.githubNewFileOpenCommand || (githubNewFileUrl ? `open ${shellQuote(githubNewFileUrl)}` : "");
  const githubEditFileOpenCommand = remediation.githubEditFileOpenCommand || remoteFileCheck?.githubEditFileOpenCommand || (githubEditFileUrl ? `open ${shellQuote(githubEditFileUrl)}` : "");
  const githubWorkflowOpenCommand = urls.githubWorkflowUrl ? `open ${shellQuote(urls.githubWorkflowUrl)}` : "";
  const githubFileNameFieldValue = entry.target;
  const suggestedCommitMessage = entry.commitMessage || `Add ${entry.name} workflow`;
  const targetMatchesTemplate = templateDigest.exists && targetDigest.exists && templateDigest.sha256 === targetDigest.sha256;
  const uiInstallOpenCommand = installAction === "replace_existing_remote_file"
    ? githubEditFileOpenCommand
    : installAction === "create_missing_remote_file"
      ? githubNewFileOpenCommand
      : "";
  const uiInstallRequired = installAction !== "verified_remote_matches_template";
  const remoteCheckGeneratedAt = remoteWorkflowFileCheck?.generatedAt || "";
  return {
    key: entry.key,
    name: entry.name,
    template: entry.template,
    target: relative(root, targetPath).replaceAll("\\", "/") || entry.target,
    targetRepositoryPath: entry.target,
    defaultBranchRequired: true,
    defaultBranch: defaultBranch.branch,
    defaultBranchSource: defaultBranch.source,
    repositoryUrl,
    suggestedRepo,
    repoReplacementHint,
    actionsUrl,
    githubNewFileUrl,
    githubEditFileUrl,
    githubBlobUrl: urls.githubBlobUrl,
    githubWorkflowUrl: urls.githubWorkflowUrl,
    templateCopyCommand,
    localTemplateHashCommand,
    githubNewFileOpenCommand,
    githubEditFileOpenCommand,
    githubWorkflowOpenCommand,
    uiInstallOpenCommand,
    uiInstallCommand: uiInstallOpenCommand,
    uiInstallRequired,
    uiInstallActionLabel: workflowUiInstallLabel(installAction),
    uiInstallInstruction: "",
    githubFileNameFieldValue,
    suggestedCommitMessage,
    githubNewFileFormCheck: `GitHub file name field must equal ${githubFileNameFieldValue}; suggested commit message: ${suggestedCommitMessage}`,
    templateExists: templateDigest.exists,
    targetExists: targetDigest.exists,
    bytes: templateDigest.bytes,
    sha256: templateDigest.sha256,
    templateSha256: templateDigest.sha256,
    targetSha256: targetDigest.sha256,
    targetMatchesTemplate,
    localTargetParityReady: targetMatchesTemplate,
    remoteWorkflowFileCheckSource: remoteWorkflowFileCheck ? remoteWorkflowFileCheckPath : "",
    remoteWorkflowFileCheckGeneratedAt: remoteCheckGeneratedAt,
    remoteWorkflowFilesReadySnapshot: remoteWorkflowFileCheck?.remoteWorkflowFilesReady === true,
    installAction,
    remoteExists: remoteFileCheck?.remoteExists === true,
    remoteMatchesTemplate: remoteFileCheck?.remoteMatchesTemplate === true,
    remoteSha256: remoteFileCheck?.remoteSha256 || remediation.remoteSha256 || "",
    remoteBlobSha: remoteFileCheck?.remoteBlobSha || remediation.remoteBlobSha || "",
    remediationStatus: remediation.status || "",
    remediationNextStep: remediation.nextStep || "",
    requiredTerms: entry.requiredTerms,
    missingTerms,
    uiInstallReady: templateDigest.exists && missingTerms.length === 0,
    nextVerificationCommand,
    placeholderVerificationCommand,
    uiSteps: [
      uiInstallRequired ? `Run ${templateCopyCommand} to copy ${entry.template}` : `No copy is required for ${entry.target} while installAction=${installAction}`,
      `installAction=${installAction}: ${workflowUiInstallInstruction({
        installAction,
        targetRepositoryPath: entry.target,
        defaultBranch: defaultBranch.branch,
        githubFileNameFieldValue,
      })}`,
      uiInstallRequired ? `Run ${uiInstallOpenCommand || "open the GitHub repository default branch create/edit page"} before committing ${entry.target}` : `Skip GitHub create/edit pages for ${entry.target}`,
      uiInstallRequired ? `Commit to default branch ${defaultBranch.branch} with a workflow-scope capable GitHub UI session` : `Keep the verified remote file unchanged on ${defaultBranch.branch}`,
      `Run ${githubWorkflowOpenCommand || "open the GitHub Actions workflow page"} and confirm the workflow appears`,
      `Run ${nextVerificationCommand} after the workflow appears in Actions`,
      `Treat ${placeholderVerificationCommand} as a template only if the suggested repo is unavailable or wrong`,
    ],
    manualDispatchRequirement: "workflow_dispatch must be present on the repository default branch before GitHub UI, CLI, or REST dispatch can run it",
  };
}

const plans = workflows.map(workflowPlan);
const blockers = plans.flatMap((plan) => {
  const items = [];
  if (!plan.templateExists) items.push(`${plan.key}: missing template ${plan.template}`);
  if (plan.missingTerms.length) items.push(`${plan.key}: template missing required terms`);
  if (plan.targetExists && !plan.targetMatchesTemplate) items.push(`${plan.key}: local workflow target differs from template`);
  return items;
});
const localTargetParityReady = plans.every((plan) => plan.targetMatchesTemplate);

function workflowUiInstallReceipt(plans) {
  const repo = suggestedRepo || "OWNER/REPO";
  const remoteFileCommand = `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`;
  const dispatchPlanCommand = `node scripts/plan-publish-dispatch.mjs --live --repo ${repo} --write`;
  const workflowListCommand = `gh workflow list --repo ${repo} --all --json name,path,state,id`;
  const handoffVerifyCommand = `node scripts/verify-launch-handoff.mjs --repo ${repo} --write --markdown`;
  const postInstallStopCondition = "Stop condition: do not run gh workflow run, archive proof, or claim launch until all six post-install evidence fields are filled and verify-launch-handoff reports safeToDispatch=true.";
  const dispatchGuard = "Do not run gh workflow run until every post-install evidence field has been filled, remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, and verify-launch-handoff reports safeToDispatch=true.";
  const installRows = plans.map((plan) => ({
    key: plan.key,
    target: plan.targetRepositoryPath,
    installAction: plan.installAction || "create_missing_remote_file",
    required: plan.uiInstallRequired !== false,
    templateCopyCommand: plan.templateCopyCommand,
    openCommand: plan.uiInstallOpenCommand || "",
    githubNewFileUrl: plan.githubNewFileUrl || "",
    githubEditFileUrl: plan.githubEditFileUrl || "",
    instruction: workflowUiInstallInstruction(plan),
  }));
  const installCommands = installRows.flatMap((row) => row.required ? [row.templateCopyCommand, row.openCommand] : []).filter(Boolean);
  const verificationCommands = [
    remoteFileCommand,
    workflowListCommand,
    dispatchPlanCommand,
    handoffVerifyCommand,
  ];
  const expectedSignals = [
    "remoteWorkflowFilesReady=true",
    "pages remoteExists=true and remoteMatchesTemplate=true",
    "drift-watch remoteExists=true and remoteMatchesTemplate=true",
    "remoteWorkflowVisibilityReady=true",
    "dispatchReady=true",
    "driftDispatchReady=true",
    "allDispatchReady=true",
    "safeToDispatch=true before gh workflow run",
  ];
  const checklist = [
    "Use each workflow row's installAction and commit only changed workflow files to the repository default branch using the matching GitHub UI edit-file or new-file page.",
    "Confirm each committed file matches the local template SHA-256.",
    "Run the remote workflow file check until remoteWorkflowFilesReady=true.",
    "Open GitHub Actions and confirm both workflow files are visible.",
    "Run the publish dispatch plan until remoteWorkflowVisibilityReady=true and allDispatchReady=true.",
    "Run verify-launch-handoff and keep dispatch withheld until every post-install evidence field is filled and verify-launch-handoff reports safeToDispatch=true.",
  ];
  const evidenceFields = [
    ["Pages workflow commit", "[paste commit URL or SHA for .github/workflows/joopark-pages.yml on the default branch]"],
    ["Drift Watch workflow commit", "[paste commit URL or SHA for .github/workflows/joopark-drift-watch.yml on the default branch]"],
    ["Remote parity proof", "[paste generatedAt plus remoteWorkflowFilesReady=true from data/remote-workflow-file-check.json]"],
    ["Actions visibility proof", "[paste gh workflow list output showing both workflow paths visible]"],
    ["Dispatch readiness proof", "[paste generatedAt plus dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true]"],
    ["Handoff verifier proof", "[paste verify-launch-handoff status plus safeToDispatch=true before gh workflow run]"],
  ];
  const parserReadyProofFields = [
    ["pages_workflow_commit", "[paste actual commit URL or SHA for .github/workflows/joopark-pages.yml on the default branch]"],
    ["drift_workflow_commit", "[paste actual commit URL or SHA for .github/workflows/joopark-drift-watch.yml on the default branch]"],
    ["remote_parity_proof", "[paste actual generatedAt plus remoteWorkflowFilesReady=true, remoteExists=true, and remoteMatchesTemplate=true]"],
    ["actions_visibility_proof", "[paste actual gh workflow list proof or remoteWorkflowVisibilityReady=true]"],
    ["dispatch_readiness_proof", "[paste actual dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true proof]"],
    ["handoff_verifier_proof", "[paste actual verify-launch-handoff output showing safeToDispatch=true before gh workflow run]"],
  ];
  const parserReadyProofTemplate = [
    "Parser-ready proof block:",
    ...parserReadyProofFields.map(([key, placeholder]) => `${key}: ${placeholder}`),
    "",
    "Parser guard:",
    "The parser ignores bracketed [paste ...] placeholders and does not turn this template into dispatch approval.",
  ].join("\n");
  const parserReadyProofFieldCoverage = parserReadyProofFields.length >= 6 &&
    parserReadyProofFields.every(([key, placeholder]) => key.includes("_proof") || key.includes("_commit") && placeholder.includes(".github/workflows/")) ? 1 : 0;
  const formFieldChecks = plans.map((plan) => ({
    key: plan.key,
    target: plan.targetRepositoryPath,
    githubFileNameFieldValue: plan.githubFileNameFieldValue,
    suggestedCommitMessage: plan.suggestedCommitMessage,
    githubNewFileUrl: plan.githubNewFileUrl,
    githubEditFileUrl: plan.githubEditFileUrl,
    githubEditFileOpenCommand: plan.githubEditFileOpenCommand,
    installAction: plan.installAction,
    uiInstallOpenCommand: plan.uiInstallOpenCommand,
  }));
  const formFieldCoverage = formFieldChecks.length >= 2 &&
    formFieldChecks.every((item) => item.githubFileNameFieldValue && item.suggestedCommitMessage) ? 1 : 0;
  const templateIntegrityRows = plans.map((plan) => ({
    key: plan.key,
    template: plan.template,
    target: plan.targetRepositoryPath,
    expectedSha256: plan.templateSha256 || "",
    localTemplateHashCommand: plan.localTemplateHashCommand,
    postCommitRemoteCheck: remoteFileCommand,
    expectedRemoteSignals: [
      `${plan.key} remoteExists=true`,
      `${plan.key} remoteMatchesTemplate=true`,
      `remoteSha256 equals templateSha256 ${plan.templateSha256 || "missing"}`,
    ],
  }));
  const templateIntegrityCoverage = templateIntegrityRows.length >= 2 &&
    templateIntegrityRows.every((row) => row.expectedSha256 && row.localTemplateHashCommand.includes("shasum -a 256") && row.postCommitRemoteCheck.includes("check-remote-workflow-files.mjs")) ? 1 : 0;
  const lines = [
    "# JooPark GitHub UI Workflow Install Receipt",
    "JooPark GitHub UI Workflow Paste Packet",
    "",
    "Status: ready for GitHub UI install; not remote installation proof",
    `Generated: ${generatedAt}`,
    `Repo: ${repo}`,
    `Default branch: ${defaultBranch.branch}`,
    `Workflow UI install ready: ${blockers.length === 0 ? "true" : "false"}`,
    `workflowUiInstallReady=${blockers.length === 0 ? "true" : "false"}`,
    `Local target parity ready: ${localTargetParityReady ? "true" : "false"}`,
    `localTargetParityReady=${localTargetParityReady ? "true" : "false"}`,
    `Plan count: ${plans.length}`,
    `Suggested repo: ${suggestedRepo || "unknown"}`,
    `Repo replacement hint: ${repoReplacementHint}`,
    "",
    "Paste packet:",
    "Paste exact template content into each required GitHub create/edit page according to installAction, skip verified_remote_matches_template rows, commit changed files to the default branch, then rerun the verification sequence before dispatch.",
    "",
    "Install commands:",
    ...(installCommands.length ? installCommands.map((command, index) => `${index + 1}. ${command}`) : ["- No GitHub UI file change is required; all remote workflow files already match local templates."]),
    "",
    "Install action ledger:",
    ...installRows.map((row) => `- ${row.key}: installAction=${row.installAction}; required=${row.required}; openCommand=${row.openCommand || "none"}; instruction=${row.instruction}`),
    "",
    "Targets:",
    ...plans.map((plan) => `- ${plan.key}: ${plan.targetRepositoryPath} from ${plan.template}; installAction=${plan.installAction}; remoteExists=${plan.remoteExists}; remoteMatchesTemplate=${plan.remoteMatchesTemplate}; templateSha256=${plan.templateSha256}; targetMatchesTemplate=${plan.targetMatchesTemplate}; newFile=${plan.githubNewFileUrl || "unknown"}; editFile=${plan.githubEditFileUrl || "unknown"}; openCommand=${plan.uiInstallOpenCommand || "none"}`),
    "",
    "Template integrity ledger:",
    ...templateIntegrityRows.map((row) => `- ${row.key}: template=${row.template}; target=${row.target}; expectedSha256=${row.expectedSha256}; localTemplateHashCommand=${row.localTemplateHashCommand}; postCommitRemoteCheck=${row.postCommitRemoteCheck}; expectedRemoteSignals=${row.expectedRemoteSignals.join(" | ")}`),
    "",
    "Checksum guard:",
    "Run each localTemplateHashCommand before paste and compare the first shasum field with expectedSha256; after commit, run postCommitRemoteCheck and require remoteExists=true, remoteMatchesTemplate=true, and remoteSha256 equals templateSha256 before dispatch.",
    "",
    "GitHub new-file form values:",
    "(For create_missing_remote_file rows only; replace_existing_remote_file rows use githubEditFileOpenCommand and verified_remote_matches_template rows require no edit.)",
    ...formFieldChecks.map((item) => `- ${item.key}: installAction=${item.installAction}; githubFileNameFieldValue=${item.githubFileNameFieldValue}; suggestedCommitMessage=${item.suggestedCommitMessage}; newFile=${item.githubNewFileUrl || "unknown"}; editFile=${item.githubEditFileUrl || "unknown"}; uiInstallOpenCommand=${item.uiInstallOpenCommand || "none"}`),
    "",
    "Post-install verification commands:",
    ...verificationCommands.map((command, index) => `${index + 1}. ${command}`),
    "",
    "Post-install proof checklist:",
    ...checklist.map((item) => `- ${item}`),
    "",
    "Post-install evidence fields to fill:",
    ...evidenceFields.map(([label, placeholder]) => `- ${label}: ${placeholder}`),
    "",
    parserReadyProofTemplate,
    "",
    "Expected success signals:",
    ...expectedSignals.map((signal) => `- ${signal}`),
    "",
    "Dispatch guard:",
    postInstallStopCondition,
    dispatchGuard,
    "Do not run gh workflow run until remoteWorkflowFilesReady: true, remoteWorkflowVisibilityReady: true, dispatchReady: true, driftDispatchReady: true, and allDispatchReady: true.",
    "External benchmark: GitHub UI file creation or editing still requires committing the workflow file to the default branch, and GitHub manual workflow dispatch only appears after a workflow_dispatch workflow exists on the default branch.",
  ];
  return {
    key: "github_ui_workflow_install_receipt",
    label: "GitHub UI workflow paste packet",
    status: blockers.length === 0 ? "ready_to_use" : "blocked",
    ready: blockers.length === 0 && localTargetParityReady && plans.length >= 2,
    repo,
    defaultBranch: defaultBranch.branch,
    commandCount: installCommands.length + verificationCommands.length,
    checklistCount: checklist.length,
    evidenceFieldCount: evidenceFields.length,
    evidenceFieldCoverage: evidenceFields.length >= 6 ? 1 : 0,
    templateIntegrityRows,
    templateIntegrityCoverage,
    templateIntegrityReady: templateIntegrityCoverage === 1,
    installRows,
    installActionCoverage: installRows.length >= 2 &&
      installRows.every((row) => ["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(row.installAction)) ? 1 : 0,
    parserReadyProofFields: parserReadyProofFields.map(([key, placeholder]) => ({ key, placeholder })),
    parserReadyProofFieldCount: parserReadyProofFields.length,
    parserReadyProofFieldCoverage,
    parserReadyProofTemplate,
    parserReadyProofBlockReady: parserReadyProofFieldCoverage === 1,
    expectedSignalCount: expectedSignals.length,
    formFieldCoverage,
    formFieldChecks,
    installCommands,
    verificationCommands,
    evidenceFields: evidenceFields.map(([label, placeholder]) => ({ label, placeholder })),
    expectedSignals,
    checklist,
    remoteFileCommand,
    dispatchPlanCommand,
    workflowListCommand,
    handoffVerifyCommand,
    dispatchGuard,
    postInstallStopCondition,
    text: lines.join("\n"),
  };
}

const generatedAt = new Date().toISOString();
const installReceipt = workflowUiInstallReceipt(plans);
const workflowUiInstallPastePacket = installReceipt.text;
const workflowUiInstallPastePacketReady = !!(
  installReceipt.ready &&
  workflowUiInstallPastePacket.includes("JooPark GitHub UI Workflow Paste Packet") &&
  workflowUiInstallPastePacket.includes("Paste exact template content") &&
  workflowUiInstallPastePacket.includes("Template integrity ledger:") &&
  workflowUiInstallPastePacket.includes("localTemplateHashCommand=shasum -a 256") &&
  workflowUiInstallPastePacket.includes("expectedSha256=") &&
  workflowUiInstallPastePacket.includes("postCommitRemoteCheck=node scripts/check-remote-workflow-files.mjs --repo") &&
  workflowUiInstallPastePacket.includes("Checksum guard:") &&
  workflowUiInstallPastePacket.includes("GitHub new-file form values:") &&
  workflowUiInstallPastePacket.includes("githubFileNameFieldValue=.github/workflows/joopark-pages.yml") &&
  workflowUiInstallPastePacket.includes("suggestedCommitMessage=Add JooPark Pages publish workflow") &&
  workflowUiInstallPastePacket.includes("Post-install evidence fields to fill:") &&
  workflowUiInstallPastePacket.includes("Parser-ready proof block:") &&
  workflowUiInstallPastePacket.includes("pages_workflow_commit:") &&
  workflowUiInstallPastePacket.includes("The parser ignores bracketed [paste ...] placeholders") &&
  workflowUiInstallPastePacket.includes("Handoff verifier proof") &&
  workflowUiInstallPastePacket.includes("dispatchReady=true") &&
  workflowUiInstallPastePacket.includes("driftDispatchReady=true") &&
  workflowUiInstallPastePacket.includes("every post-install evidence field has been filled") &&
  workflowUiInstallPastePacket.includes("verify-launch-handoff reports safeToDispatch=true") &&
  workflowUiInstallPastePacket.includes("Do not run gh workflow run until remoteWorkflowFilesReady: true")
);
const payload = {
  status: blockers.length === 0 ? "pass" : "fail",
  mode: "dry-run",
  generatedAt,
  repositoryRoot,
  remoteName,
  repositoryUrl,
  suggestedRepo,
  repoReplacementHint,
  defaultBranch: defaultBranch.branch,
  defaultBranchSource: defaultBranch.source,
  actionsUrl,
  workflowScopeRequired: true,
  workflowUiInstallReady: blockers.length === 0,
  localTargetParityReady,
  installReceipt,
  installReceiptReady: installReceipt.ready,
  installReceiptCommandCount: installReceipt.commandCount,
  installReceiptChecklistCount: installReceipt.checklistCount,
  workflowUiTemplateIntegrityCoverage: installReceipt.templateIntegrityCoverage,
  workflowUiTemplateIntegrityReady: installReceipt.templateIntegrityReady,
  workflowUiInstallFormFieldCoverage: installReceipt.formFieldCoverage,
  workflowUiInstallPastePacket,
  uiPastePacket: workflowUiInstallPastePacket,
  packet: workflowUiInstallPastePacket,
  workflowUiInstallPastePacketReady,
  uiPastePacketReady: workflowUiInstallPastePacketReady,
  packetReady: workflowUiInstallPastePacketReady,
  workflowUiInstallPastePacketCoverage: workflowUiInstallPastePacketReady ? 1 : 0,
  plans,
  blockers,
  nextVerificationCommand,
  placeholderVerificationCommand,
  nextCommands: [
    "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope",
    "node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope",
    "node scripts/plan-workflow-ui-install.mjs --dry-run",
    "node scripts/plan-workflow-ui-install.mjs --dry-run --markdown",
    nextVerificationCommand,
  ],
  placeholderTemplateCommands: [
    placeholderVerificationCommand,
  ],
};

if (write) {
  payload.writtenTo = outputRelativePath;
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

if (markdown) {
  const lines = [
    "# JooPark Workflow UI Install Plan",
    "",
    `- status: ${payload.status}`,
    `- workflowUiInstallReady: ${payload.workflowUiInstallReady}`,
    `- repositoryRoot: ${payload.repositoryRoot}`,
    `- remoteName: ${payload.remoteName || "unknown"}`,
    `- repositoryUrl: ${payload.repositoryUrl || "unknown"}`,
    `- suggestedRepo: ${payload.suggestedRepo || "unknown"}`,
    `- repoReplacementHint: ${payload.repoReplacementHint}`,
    `- defaultBranch: ${payload.defaultBranch}`,
    `- actionsUrl: ${payload.actionsUrl || "unknown"}`,
    `- localTargetParityReady: ${payload.localTargetParityReady}`,
    `- installReceiptReady: ${payload.installReceiptReady}`,
    `- installReceiptCommandCount: ${payload.installReceiptCommandCount}`,
    `- installReceiptChecklistCount: ${payload.installReceiptChecklistCount}`,
    `- workflowUiTemplateIntegrityCoverage: ${payload.workflowUiTemplateIntegrityCoverage}`,
    `- workflowUiInstallFormFieldCoverage: ${payload.workflowUiInstallFormFieldCoverage}`,
    `- nextVerificationCommand: \`${payload.nextVerificationCommand}\``,
    `- placeholderVerificationCommand: \`${payload.placeholderVerificationCommand}\``,
    "",
    "## GitHub UI workflow install receipt",
    "",
    payload.installReceipt.text,
    "",
  ];
  for (const plan of plans) {
    lines.push(`## ${plan.name}`);
    lines.push(`- template: \`${plan.template}\``);
    lines.push(`- target: \`${plan.targetRepositoryPath}\``);
    lines.push(`- defaultBranchRequired: ${plan.defaultBranchRequired}`);
    lines.push(`- githubNewFileUrl: ${plan.githubNewFileUrl || "unknown"}`);
    lines.push(`- githubWorkflowUrl: ${plan.githubWorkflowUrl || "unknown"}`);
    lines.push(`- templateCopyCommand: \`${plan.templateCopyCommand}\``);
    lines.push(`- localTemplateHashCommand: \`${plan.localTemplateHashCommand}\``);
    lines.push(`- githubNewFileOpenCommand: \`${plan.githubNewFileOpenCommand || "open GitHub new-file page"}\``);
    lines.push(`- githubWorkflowOpenCommand: \`${plan.githubWorkflowOpenCommand || "open GitHub workflow page"}\``);
    lines.push(`- githubFileNameFieldValue: \`${plan.githubFileNameFieldValue || plan.targetRepositoryPath}\``);
    lines.push(`- suggestedCommitMessage: \`${plan.suggestedCommitMessage || "Add workflow"}\``);
    lines.push(`- sha256: \`${plan.sha256 || "missing"}\``);
    lines.push(`- templateSha256: \`${plan.templateSha256 || "missing"}\``);
    lines.push(`- targetSha256: \`${plan.targetSha256 || "missing"}\``);
    lines.push(`- targetMatchesTemplate: ${plan.targetMatchesTemplate}`);
    lines.push(`- uiInstallReady: ${plan.uiInstallReady}`);
    lines.push(`- manualDispatchRequirement: ${plan.manualDispatchRequirement}`);
    lines.push("- steps:");
    plan.uiSteps.forEach((step, index) => lines.push(`  ${index + 1}. ${step}`));
    lines.push("");
  }
  console.log(lines.join("\n"));
} else {
  console.log(JSON.stringify(payload, null, 2));
}
