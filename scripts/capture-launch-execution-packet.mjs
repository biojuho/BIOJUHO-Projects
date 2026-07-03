#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const write = rawArgs.includes("--write");
const markdown = rawArgs.includes("--markdown");
const outRel = argValue("--out") || "data/launch-execution-packet.json";
const POST_INSTALL_DISPATCH_GUARD = "Do not run gh workflow run until every post-install evidence field has been filled, remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, and verify-launch-handoff reports safeToDispatch=true.";
const POST_INSTALL_STOP_CONDITION = "Stop condition: do not run gh workflow run, archive proof, or claim launch until all six post-install evidence fields are filled and verify-launch-handoff reports safeToDispatch=true.";

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

function readJson(relPath, fallback = null) {
  try {
    return JSON.parse(readFileSync(resolve(root, relPath), "utf-8"));
  } catch {
    return fallback;
  }
}

function valueOrPending(value) {
  if (value === true) return "true";
  if (value === false) return "false";
  if (value === null || value === undefined || value === "") return "not available";
  return String(value);
}

function numberOr(value, fallback) {
  if (value === null || value === undefined || value === "") return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function yesNo(value) {
  return value ? "true" : "false";
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))];
}

function externalComparison() {
  return [
    {
      key: "manual_workflow_dispatch",
      label: "GitHub manual workflow dispatch",
      detail: "Manual workflow runs require workflow_dispatch and the workflow file on the default branch, so this packet makes workflow installation and visibility verification the first gate.",
      url: "https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui",
    },
    {
      key: "github_pages_custom_workflow",
      label: "GitHub Pages custom workflows",
      detail: "GitHub Pages custom workflows deploy an uploaded artifact through actions/deploy-pages with pages: write and id-token: write permissions, so this packet verifies the prepared Pages workflow before dispatch.",
      url: "https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages",
    },
  ];
}

function installSteps(workflowUiInstallPlan, publishDispatchPlan) {
  const plans = Array.isArray(workflowUiInstallPlan?.plans) && workflowUiInstallPlan.plans.length
    ? workflowUiInstallPlan.plans
    : Array.isArray(publishDispatchPlan?.workflowUiInstallPlans) ? publishDispatchPlan.workflowUiInstallPlans : [];
  return plans.map((plan) => {
    const key = plan.key || plan.workflowFile || "";
    const cliInstallCommand = plan.cliInstallCommand ||
      (key === "pages" ? "node scripts/prepare-github-pages-workflow.mjs --write" : "") ||
      (key === "drift-watch" ? "node scripts/prepare-github-drift-watch-workflow.mjs --write" : "");
    return {
      key,
      label: plan.name || plan.workflowName || plan.targetRepositoryPath || "workflow",
      target: plan.targetRepositoryPath || plan.target || "",
      template: plan.template || "",
      templateSha256: plan.templateSha256 || plan.sha256 || "",
      targetSha256: plan.targetSha256 || "",
      targetMatchesTemplate: !!plan.targetMatchesTemplate,
      copyCommand: plan.templateCopyCommand || "",
      openNewFileCommand: plan.githubNewFileOpenCommand || "",
      openEditFileCommand: plan.githubEditFileOpenCommand || "",
      workflowUrl: plan.githubWorkflowUrl || "",
      openWorkflowCommand: plan.githubWorkflowOpenCommand || "",
      cliInstallCommand,
      manualDispatchRequirement: plan.manualDispatchRequirement || "workflow_dispatch must exist on the default branch before manual dispatch.",
    };
  });
}

function remoteWorkflowCheckForPlan(plan, remoteWorkflowFileCheck) {
  const checks = Array.isArray(remoteWorkflowFileCheck?.checks) ? remoteWorkflowFileCheck.checks : [];
  return checks.find((check) =>
    check.key === plan.key ||
    check.path === plan.target ||
    check.path === plan.targetRepositoryPath
  ) || {};
}

function workflowUiInstallCommands({ install, remoteWorkflowFileCheck }) {
  return install.flatMap((plan) => {
    const check = remoteWorkflowCheckForPlan(plan, remoteWorkflowFileCheck);
    const remediation = check.remediation || {};
    const installAction = check.installAction || remediation.installAction || "";
    if (installAction === "verified_remote_matches_template" || (check.remoteExists && check.remoteMatchesTemplate)) return [];
    const copyCommand = check.templateCopyCommand || remediation.templateCopyCommand || plan.copyCommand || "";
    const editCommand = check.githubEditFileOpenCommand || remediation.githubEditFileOpenCommand || "";
    if (installAction === "replace_existing_remote_file" && copyCommand && editCommand) {
      return [`${copyCommand} && ${editCommand}`];
    }
    const newFileCommand = check.githubNewFileOpenCommand || remediation.githubNewFileOpenCommand || plan.openNewFileCommand || "";
    return [copyCommand, newFileCommand].filter(Boolean);
  });
}

function workflowUiInstallPathCommands({ install, remoteWorkflowFileCheck }) {
  return install.flatMap((plan) => {
    const check = remoteWorkflowCheckForPlan(plan, remoteWorkflowFileCheck);
    const remediation = check.remediation || {};
    const installAction = check.installAction || remediation.installAction || "";
    const copyCommand = check.templateCopyCommand || remediation.templateCopyCommand || plan.copyCommand || "";
    const editCommand = check.githubEditFileOpenCommand || remediation.githubEditFileOpenCommand || plan.openEditFileCommand || "";
    const newFileCommand = check.githubNewFileOpenCommand || remediation.githubNewFileOpenCommand || plan.openNewFileCommand || "";
    if (installAction === "replace_existing_remote_file" || installAction === "verified_remote_matches_template" || (check.remoteExists && check.remoteMatchesTemplate)) {
      return copyCommand && editCommand ? [`${copyCommand} && ${editCommand}`] : [copyCommand, editCommand].filter(Boolean);
    }
    return copyCommand && newFileCommand ? [`${copyCommand} && ${newFileCommand}`] : [copyCommand, newFileCommand].filter(Boolean);
  });
}

function workflowInstallActionRows(remoteWorkflowFileCheck) {
  const checks = Array.isArray(remoteWorkflowFileCheck?.checks) ? remoteWorkflowFileCheck.checks : [];
  return checks.map((check) => {
    const remediation = check.remediation || {};
    const installAction = check.installAction || remediation.installAction ||
      (check.remoteExists && check.remoteMatchesTemplate
        ? "verified_remote_matches_template"
        : check.remoteExists
          ? "replace_existing_remote_file"
          : "create_missing_remote_file");
    return {
      key: check.key || check.path || "workflow",
      path: check.path || check.workflowFile || "",
      installAction,
    };
  });
}

function workflowInstallActionSummary(remoteWorkflowFileCheck) {
  const rows = workflowInstallActionRows(remoteWorkflowFileCheck);
  if (!rows.length) {
    return "Apply each workflow row's installAction on the default branch: replace existing mismatched files, create only missing files, and leave already verified files unchanged.";
  }
  const rowSummary = rows
    .map((row) => `${row.key}=${row.installAction}`)
    .join("; ");
  return `Apply each workflow row's installAction on the default branch: replace_existing_remote_file for existing SHA mismatches, create_missing_remote_file only for missing files, and no-op verified_remote_matches_template rows. Current rows: ${rowSummary}.`;
}

function remoteWorkflowFileOpenCommand(options) {
  const { installAction, githubNewFileOpenCommand, githubEditFileOpenCommand } = options || {};
  if (installAction === "verified_remote_matches_template") return "";
  if (installAction === "replace_existing_remote_file") {
    return githubEditFileOpenCommand || githubNewFileOpenCommand || "";
  }
  return githubNewFileOpenCommand || githubEditFileOpenCommand || "";
}

function installPathOptions({ install, publishDispatchPlan, remoteWorkflowFileCheck, remoteFileCommand, remoteInstallerCommand, workflowScopeInstallBlocked, workflowScopeRefreshCommand, workflowScopeRecheckCommand }) {
  const handoff = publishDispatchPlan?.workflowDefaultBranchHandoff || {};
  const githubUiCommands = workflowUiInstallCommands({ install, remoteWorkflowFileCheck });
  const githubUiPathCommands = workflowUiInstallPathCommands({ install, remoteWorkflowFileCheck });
  return [
    {
      key: "cli_workflow_scope",
      label: "CLI path after workflow scope",
      when: workflowScopeInstallBlocked
        ? "Use only after `gh auth refresh -h github.com -s workflow` succeeds and the token shows workflow scope."
        : "Use when the GitHub CLI token already has workflow scope.",
      commands: uniq([
        workflowScopeInstallBlocked ? workflowScopeRefreshCommand : "",
        remoteInstallerCommand,
        workflowScopeRecheckCommand,
        ...install.map((plan) => plan.cliInstallCommand),
        handoff.gitAddCommand,
        handoff.gitCommitCommand,
        remoteFileCommand,
        publishDispatchPlan?.nextVerificationCommand,
      ]),
      success: "The workflow files are committed to the default branch, remoteWorkflowFilesReady=true, and GitHub Actions lists both workflows.",
      guard: "Do not run dispatch commands just because the local .github/workflows files exist.",
    },
    {
      key: "github_ui",
      label: "GitHub UI path",
      when: "Use when the CLI token still lacks workflow scope or the operator prefers browser-based default-branch workflow repair.",
      commands: uniq([
        ...githubUiPathCommands,
        ...githubUiCommands,
        remoteFileCommand,
        publishDispatchPlan?.nextVerificationCommand,
      ]),
      success: "Required create_missing_remote_file rows are created, replace_existing_remote_file rows are replaced on main, verified_remote_matches_template rows are skipped, remoteWorkflowFilesReady=true, and workflow visibility is confirmed.",
      guard: "Use each file's create or edit URL according to installAction before any dispatch attempt.",
    },
  ].filter((path) => path.commands.length > 0);
}

function workflowInstallVerificationMatrix({ repo, defaultBranch, stages, currentAction, authPreflight, postAuthCheckpoint, publishDispatchPlan, remoteWorkflowFileCheck }) {
  const installStage = stages.find((stage) => stage.key === "install_workflows") || {};
  const visibilityStage = stages.find((stage) => stage.key === "verify_visibility") || {};
  const acceptance = Array.isArray(currentAction?.acceptanceChecklist) ? currentAction.acceptanceChecklist : [];
  const installPaths = Array.isArray(currentAction?.installPaths) ? currentAction.installPaths : [];
  const withheldCommands = Array.isArray(currentAction?.withheldCommands) ? currentAction.withheldCommands : [];
  const remoteFileCommand = postAuthCheckpoint?.remoteFileCommand || remoteWorkflowFileCheck?.nextVerificationCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`;
  const workflowListCommand = publishDispatchPlan?.workflowListCommand
    ? publishDispatchPlan.workflowListCommand.replace("OWNER/REPO", repo)
    : `gh workflow list --repo ${repo} --all --json name,path,state,id`;
  const dispatchPlanCommand = postAuthCheckpoint?.dispatchPlanCommand || publishDispatchPlan?.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`;
  const handoffCommand = postAuthCheckpoint?.verifyCommand || `node scripts/verify-launch-handoff.mjs --repo ${repo} --write --markdown`;
  const verificationCommands = uniq([remoteFileCommand, workflowListCommand, dispatchPlanCommand, handoffCommand]);
  const readyToDispatch = workflowDispatchReady({ publishDispatchPlan, remoteWorkflowFileCheck });
  const acceptanceSignal = (key, fallback) => {
    const item = acceptance.find((candidate) => candidate.key === key) || {};
    return {
      key,
      label: item.label || fallback.label,
      status: item.status || fallback.status,
      required: item.required || fallback.required,
      evidence: item.evidence || fallback.evidence,
      command: fallback.command || "",
    };
  };
  const signalChecks = [
    acceptanceSignal("operator_auth_path", {
      label: "Operator auth path",
      status: authPreflight?.workflowScopeAvailable && !authPreflight?.workflowScopeInstallBlocked ? "pass" : "action_required",
      required: "workflowScopeAvailable=true and workflowScopeInstallBlocked=false before CLI installation.",
      evidence: `workflowScopeAvailable=${yesNo(authPreflight?.workflowScopeAvailable)}; workflowScopeInstallBlocked=${yesNo(authPreflight?.workflowScopeInstallBlocked)}; scopes=${valueOrPending(authPreflight?.scopeList)}`,
      command: authPreflight?.refreshCommand || "gh auth refresh -h github.com -s workflow",
    }),
    acceptanceSignal("local_template_parity", {
      label: "Local template parity",
      status: publishDispatchPlan?.localTargetParityReady ? "pass" : "action_required",
      required: "Local workflow templates exist and match generated targets.",
      evidence: `localTargetParityReady=${yesNo(publishDispatchPlan?.localTargetParityReady)}`,
    }),
    acceptanceSignal("remote_workflow_file_parity", {
      label: "Remote workflow file parity",
      status: remoteWorkflowFileCheck?.remoteWorkflowFilesReady ? "pass" : "action_required",
      required: "Remote default-branch workflow files match local template SHA-256 values.",
      evidence: `remoteWorkflowFilesReady=${yesNo(remoteWorkflowFileCheck?.remoteWorkflowFilesReady)}`,
      command: remoteFileCommand,
    }),
    acceptanceSignal("workflow_visibility", {
      label: "Workflow visibility",
      status: publishDispatchPlan?.remoteWorkflowVisibilityReady ? "pass" : "action_required",
      required: "GitHub Actions lists both workflows before dispatch.",
      evidence: `remoteWorkflowVisibilityReady=${yesNo(publishDispatchPlan?.remoteWorkflowVisibilityReady)}`,
      command: workflowListCommand,
    }),
    acceptanceSignal("dispatch_guard", {
      label: "Dispatch guard",
      status: publishDispatchPlan?.allDispatchReady ? "ready" : "pass",
      required: "Dispatch commands stay withheld until allDispatchReady=true.",
      evidence: `allDispatchReady=${yesNo(publishDispatchPlan?.allDispatchReady)}; withheldCommands=${withheldCommands.length}`,
      command: handoffCommand,
    }),
  ];
  const requiredSignals = [
    "workflowScopeAvailable=true",
    "workflowScopeInstallBlocked=false",
    "remoteWorkflowFilesReady=true",
    "remoteWorkflowVisibilityReady=true",
    "allDispatchReady=true",
    "safeToDispatch=true before gh workflow run",
  ];
  const matrixRows = installPaths.map((path) => {
    const commands = Array.isArray(path.commands) ? path.commands : [];
    const cliBlocked = path.key === "cli_workflow_scope" && authPreflight?.workflowScopeInstallBlocked;
    return {
      key: path.key || "",
      label: path.label || "Install path",
      status: cliBlocked ? "blocked_by_workflow_scope" : "ready_to_install",
      firstCommand: commands[0] || "",
      commandCount: commands.length,
      verificationCommands,
      successSignals: requiredSignals,
      blockedSignals: Array.isArray(postAuthCheckpoint?.blockedSignals) ? postAuthCheckpoint.blockedSignals : [],
      guard: path.guard || "Do not run gh workflow run until allDispatchReady=true and verify-launch-handoff reports safeToDispatch=true.",
    };
  });
  return {
    source: "generated_from_launch_execution_packet",
    status: readyToDispatch ? "ready_to_dispatch" : "install_verification_required",
    repo,
    defaultBranch,
    currentStageKey: installStage.key || "install_workflows",
    nextStageKey: visibilityStage.key || "verify_visibility",
    readyToVerifyVisibility: !!remoteWorkflowFileCheck?.remoteWorkflowFilesReady,
    readyToDispatch,
    installPathCount: matrixRows.length,
    requiredSignalCount: requiredSignals.length,
    verificationCommandCount: verificationCommands.length,
    remoteFileCommand,
    workflowListCommand,
    dispatchPlanCommand,
    handoffCommand,
    dispatchGuard: postAuthCheckpoint?.guard || "Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true.",
    requiredSignals,
    matrixRows,
    signalChecks,
  };
}

function remoteWorkflowFileAcceptanceLedger({ repo, defaultBranch, workflowUiInstallPlan, remoteWorkflowFileCheck, postAuthCheckpoint }) {
  const checks = Array.isArray(remoteWorkflowFileCheck?.checks) ? remoteWorkflowFileCheck.checks : [];
  const plans = Array.isArray(workflowUiInstallPlan?.plans) ? workflowUiInstallPlan.plans : [];
  const merged = (checks.length ? checks : plans).map((item) => {
    const plan = plans.find((candidate) => candidate.key === item.key || candidate.targetRepositoryPath === item.path) || {};
    const remediation = item.remediation || {};
    const remoteExists = !!item.remoteExists;
    const remoteMatchesTemplate = !!item.remoteMatchesTemplate;
    const remoteChecked = item.remoteChecked !== false && (item.remoteChecked || remoteWorkflowFileCheck?.remoteWorkflowFilesChecked);
    const templateSha256 = item.templateSha256 || plan.templateSha256 || "";
    const localTargetSha256 = plan.targetSha256 || "";
    const status = remoteExists && remoteMatchesTemplate
      ? "ready"
      : !remoteChecked
        ? "not_checked"
        : !remoteExists
          ? "missing_on_default_branch"
          : "sha_mismatch";
    const installAction = item.installAction || remediation.installAction ||
      (status === "ready"
        ? "verified_remote_matches_template"
        : status === "sha_mismatch"
          ? "replace_existing_remote_file"
          : status === "missing_on_default_branch"
            ? "create_missing_remote_file"
            : "replace_repo_placeholder");
    const githubNewFileOpenCommand = item.githubNewFileOpenCommand || remediation.githubNewFileOpenCommand || plan.githubNewFileOpenCommand || "";
    const githubEditFileOpenCommand = item.githubEditFileOpenCommand || remediation.githubEditFileOpenCommand || "";
    const openCommand = remoteWorkflowFileOpenCommand({ installAction, githubNewFileOpenCommand, githubEditFileOpenCommand });
    return {
      key: item.key || plan.key || "",
      name: item.name || plan.name || plan.workflowName || "workflow",
      path: item.path || plan.targetRepositoryPath || "",
      template: item.template || plan.template || "",
      defaultBranch: item.defaultBranch || defaultBranch,
      status,
      installAction,
      localTemplateExists: item.templateExists !== false && (item.templateExists || !!templateSha256),
      localTargetMatchesTemplate: plan.targetMatchesTemplate !== false && (plan.targetMatchesTemplate || localTargetSha256 === templateSha256),
      templateSha256,
      localTargetSha256,
      remoteChecked,
      remoteExists,
      remoteSha256: item.remoteSha256 || "",
      remoteMatchesTemplate,
      githubBlobSha: item.githubBlobSha || "",
      htmlUrl: item.htmlUrl || "",
      workflowUrl: item.workflowUrl || plan.githubWorkflowUrl || "",
      githubNewFileUrl: item.githubNewFileUrl || plan.githubNewFileUrl || "",
      githubEditFileUrl: item.githubEditFileUrl || remediation.githubEditFileUrl || "",
      templateCopyCommand: item.templateCopyCommand || plan.templateCopyCommand || "",
      githubNewFileOpenCommand,
      githubEditFileOpenCommand,
      openCommand,
      verifyCommand: item.command || `gh api --method GET repos/${repo}/contents/${item.path || plan.targetRepositoryPath || ".github/workflows/<file>.yml"} -f ref=${defaultBranch}`,
      evidence: `remoteChecked=${yesNo(remoteChecked)}; remoteExists=${yesNo(remoteExists)}; remoteMatchesTemplate=${yesNo(remoteMatchesTemplate)}; templateSha256=${valueOrPending(templateSha256)}; remoteSha256=${valueOrPending(item.remoteSha256)}`,
      blockers: Array.isArray(item.blockers) ? item.blockers : [],
    };
  });
  const readyCount = merged.filter((item) => item.status === "ready").length;
  const missingCount = merged.filter((item) => item.status === "missing_on_default_branch").length;
  const mismatchCount = merged.filter((item) => item.status === "sha_mismatch").length;
  const notCheckedCount = merged.filter((item) => item.status === "not_checked").length;
  const commandCount = merged.reduce((sum, item) => sum + [item.templateCopyCommand, item.openCommand, item.verifyCommand].filter(Boolean).length, 0);
  return {
    source: "generated_from_remote_workflow_file_check",
    status: readyCount === merged.length && merged.length > 0 ? "remote_files_ready" : "remote_file_install_required",
    repo,
    defaultBranch,
    remoteWorkflowFilesChecked: !!remoteWorkflowFileCheck?.remoteWorkflowFilesChecked,
    remoteWorkflowFilesReady: !!remoteWorkflowFileCheck?.remoteWorkflowFilesReady,
    fileCount: merged.length,
    readyCount,
    missingCount,
    mismatchCount,
    notCheckedCount,
    commandCount,
    verifyCommand: remoteWorkflowFileCheck?.nextVerificationCommand || postAuthCheckpoint?.remoteFileCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`,
    installCommand: remoteWorkflowFileCheck?.remoteInstallerCommand || postAuthCheckpoint?.installCommand || `node scripts/install-remote-workflow-files.mjs --repo ${repo} --write --verify`,
    dispatchPlanCommand: remoteWorkflowFileCheck?.dispatchPlanCommand || postAuthCheckpoint?.dispatchPlanCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo} --write`,
    requiredSignals: [
      "remoteWorkflowFilesChecked=true",
      "remoteWorkflowFilesReady=true",
      "each remoteExists=true",
      "each remoteMatchesTemplate=true",
      "remoteWorkflowVisibilityReady=true after recheck",
    ],
    files: merged,
  };
}

function publishEvidenceCaptureMarkdownCommand(publishEvidence, repo) {
  const candidates = [
    publishEvidence?.deferredNextAction?.command,
    publishEvidence?.nextAction?.command,
  ].map((command) => String(command || "").trim()).filter(Boolean);
  const captureCommand = candidates.find((command) => command.includes("capture-publish-evidence.mjs"));
  if (!captureCommand) return `node scripts/capture-publish-evidence.mjs --live --repo ${repo} --markdown`;
  if (captureCommand.includes("--markdown")) return captureCommand.replace("OWNER/REPO", repo);
  if (captureCommand.includes("--write")) return captureCommand.replace("--write", "--markdown").replace("OWNER/REPO", repo);
  return `${captureCommand.replace("OWNER/REPO", repo)} --markdown`;
}

function publishEvidenceCaptureWriteCommand(markdownCommand) {
  if (markdownCommand.includes("--markdown")) return markdownCommand.replace("--markdown", "--write");
  if (markdownCommand.includes("--write")) return markdownCommand;
  return `${markdownCommand} --write`;
}

function releaseQualityReadyFromAudit(outputQualityAudit) {
  const latestChecks = outputQualityAudit?.latestGate?.checks || {};
  const latestGatePass = outputQualityAudit?.latestGate?.status === "pass" &&
    Number(latestChecks.fail || 0) === 0 &&
    Number(latestChecks.notRun || 0) === 0 &&
    Number(latestChecks.blocked || 0) === 0;
  return !!(outputQualityAudit?.releaseQualityReady || latestGatePass);
}

function publicLaunchProofReadyFromEvidence(publishEvidence, outputQualityAudit) {
  return !!(
    outputQualityAudit?.publicLaunchProofReady ||
    (publishEvidence?.postPublishEvidenceReady && publishEvidence?.evidenceFresh)
  );
}

function workflowDispatchReady({ publishDispatchPlan, remoteWorkflowFileCheck }) {
  return !!(
    remoteWorkflowFileCheck?.remoteWorkflowFilesReady &&
    publishDispatchPlan?.remoteWorkflowVisibilityReady &&
    publishDispatchPlan?.allDispatchReady &&
    !publishDispatchPlan?.workflowScopeInstallBlocked
  );
}

function launchPacketReadyForExternalClaim({ publishEvidence, outputQualityAudit, publishDispatchPlan, remoteWorkflowFileCheck }) {
  const liveProofReady = !!(publishEvidence?.postPublishEvidenceReady && publishEvidence?.evidenceFresh);
  return !!(
    releaseQualityReadyFromAudit(outputQualityAudit) &&
    publicLaunchProofReadyFromEvidence(publishEvidence, outputQualityAudit) &&
    liveProofReady &&
    workflowDispatchReady({ publishDispatchPlan, remoteWorkflowFileCheck })
  );
}

function launchProofAcceptanceLedger({ repo, stages, publishEvidence, publishDispatchPlan, remoteWorkflowFileCheck, outputQualityAudit }) {
  const captureStage = Array.isArray(stages) ? stages.find((stage) => stage.key === "capture_launch_proof") || {} : {};
  const captureMarkdownCommand = publishEvidenceCaptureMarkdownCommand(publishEvidence, repo);
  const captureWriteCommand = publishEvidenceCaptureWriteCommand(captureMarkdownCommand);
  const pagesSite = publishEvidence?.pagesSite && typeof publishEvidence.pagesSite === "object" ? publishEvidence.pagesSite : {};
  const workflowRuns = Array.isArray(publishEvidence?.workflowRuns) ? publishEvidence.workflowRuns : [];
  const workflowRun = (key) => workflowRuns.find((run) => run.key === key || run.workflowFile === key) || {};
  const pagesRun = workflowRun("pages");
  const driftRun = workflowRun("drift-watch");
  const workflowRunReady = (run) => !!(run?.ready && run?.latestRun?.url && run?.latestRun?.status && run?.latestRun?.conclusion);
  const workflowRunEvidence = (run) => {
    if (!run || typeof run !== "object") return "workflow run not checked";
    const latest = run.latestRun || {};
    return [
      `checked=${yesNo(run.checked)}`,
      `ready=${yesNo(run.ready)}`,
      `status=${valueOrPending(latest.status)}`,
      `conclusion=${valueOrPending(latest.conclusion)}`,
      `url=${valueOrPending(latest.url)}`,
      `headSha=${valueOrPending(latest.headSha)}`,
    ].join("; ");
  };
  const commandForRepo = (command, fallback) => (command || fallback || "").replace("OWNER/REPO", repo);
  const allDispatchReady = workflowDispatchReady({ publishDispatchPlan, remoteWorkflowFileCheck });
  const postPublishEvidenceReady = !!publishEvidence?.postPublishEvidenceReady;
  const evidenceFresh = !!publishEvidence?.evidenceFresh;
  const readyForExternalClaim = launchPacketReadyForExternalClaim({ publishEvidence, outputQualityAudit, publishDispatchPlan, remoteWorkflowFileCheck });
  const publicLaunchProofReady = publicLaunchProofReadyFromEvidence(publishEvidence, outputQualityAudit);
  const proofBlockedStatus = allDispatchReady ? "pending_capture" : "blocked_until_dispatch";
  const requiredProofs = [
    {
      key: "pages_site_url",
      label: "Pages site URL/status",
      status: pagesSite.ready ? "ready" : proofBlockedStatus,
      required: "Capture GitHub Pages html_url, status, and https_enforced from the live repository.",
      evidence: `pages.checked=${yesNo(pagesSite.checked)}; pages.ready=${yesNo(pagesSite.ready)}; site=${valueOrPending(pagesSite.site?.html_url || pagesSite.site?.url)}`,
      command: commandForRepo(pagesSite.command, `gh api repos/${repo}/pages`),
    },
    {
      key: "pages_workflow_run",
      label: "Pages workflow run",
      status: workflowRunReady(pagesRun) ? "ready" : proofBlockedStatus,
      required: "Capture latest joopark-pages.yml run status, conclusion, URL, and headSha after dispatch.",
      evidence: workflowRunEvidence(pagesRun),
      command: commandForRepo(pagesRun.evidenceCommand, `gh run list --repo ${repo} --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle`),
    },
    {
      key: "drift_workflow_run",
      label: "Drift Watch workflow run",
      status: workflowRunReady(driftRun) ? "ready" : proofBlockedStatus,
      required: "Capture latest joopark-drift-watch.yml run status, conclusion, URL, and headSha after dispatch.",
      evidence: workflowRunEvidence(driftRun),
      command: commandForRepo(driftRun.evidenceCommand, `gh run list --repo ${repo} --workflow joopark-drift-watch.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle`),
    },
    {
      key: "evidence_freshness",
      label: "Evidence freshness",
      status: postPublishEvidenceReady && evidenceFresh ? "ready" : proofBlockedStatus,
      required: "Saved publish evidence must be generated after dispatch and still be inside the freshness window.",
      evidence: `postPublishEvidenceReady=${yesNo(postPublishEvidenceReady)}; evidenceFresh=${yesNo(evidenceFresh)}; evidenceExpiresAt=${valueOrPending(publishEvidence?.evidenceExpiresAt)}`,
      command: captureWriteCommand,
    },
    {
      key: "release_receipt",
      label: "Release receipt",
      status: postPublishEvidenceReady && publishEvidence?.postLaunchVerificationReceipt ? "ready" : "blocked_until_proof",
      required: "Archive the post-launch verification receipt only after live Pages and workflow evidence is ready.",
      evidence: `postLaunchVerificationReceipt=${yesNo(publishEvidence?.postLaunchVerificationReceipt)}; postPublishEvidenceReady=${yesNo(postPublishEvidenceReady)}`,
      command: captureMarkdownCommand,
    },
    {
      key: "public_claim_guard",
      label: "Public claim guard",
      status: readyForExternalClaim ? "ready" : "guarded",
      required: "Keep public launch copy blocked until release quality, public launch proof, and launch packet claim guard are all true.",
      evidence: `publicLaunchProofReady=${yesNo(publicLaunchProofReady)}; readyForExternalClaim=${yesNo(readyForExternalClaim)}`,
      command: "copy System Status quality receipt after readyForExternalClaim=true",
    },
  ];
  const readyProofCount = requiredProofs.filter((proof) => proof.status === "ready").length;
  const pendingProofCount = requiredProofs.length - readyProofCount;
  return {
    source: "generated_from_launch_execution_packet",
    status: readyProofCount === requiredProofs.length ? "proof_ready" : allDispatchReady ? "proof_capture_required" : "proof_blocked_until_dispatch",
    repo,
    currentGate: captureStage.key || "capture_launch_proof",
    currentGateStatus: captureStage.status || "action_required_after_dispatch",
    deferredUntil: allDispatchReady ? "workflow dispatch complete and live evidence saved" : "safeToDispatch=true",
    safeToDispatch: allDispatchReady,
    postPublishEvidenceReady,
    evidenceFresh,
    publicLaunchProofReady,
    readyForExternalClaim,
    requiredProofCount: requiredProofs.length,
    readyProofCount,
    pendingProofCount,
    captureMarkdownCommand,
    captureWriteCommand,
    requiredProofs,
    externalProofBaseline: [
      {
        key: "github_pages_site",
        label: "GitHub Pages site evidence",
        requiredFields: ["html_url", "status", "https_enforced"],
        command: commandForRepo(pagesSite.command, `gh api repos/${repo}/pages`),
      },
      {
        key: "github_actions_runs",
        label: "GitHub Actions workflow run evidence",
        requiredFields: ["status", "conclusion", "url", "headSha"],
        command: `gh run list --repo ${repo} --workflow <workflow-file> --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle`,
      },
      {
        key: "github_actions_job_summary",
        label: "GitHub Actions job summaries",
        requiredFields: ["operator-readable status summary", "linked run evidence"],
        command: "review workflow summary after the run completes",
      },
    ],
  };
}

function postInstallEvidenceIntake({ repo, defaultBranch, remoteWorkflowFileLedger, publishDispatchPlan, postAuthCheckpoint, blockerResolution }) {
  const files = Array.isArray(remoteWorkflowFileLedger?.files) ? remoteWorkflowFileLedger.files : [];
  const fileByKey = (key) => files.find((file) => file.key === key) || {};
  const pagesFile = fileByKey("pages");
  const driftFile = fileByKey("drift-watch");
  const workflowListCommand = publishDispatchPlan?.workflowListCommand
    ? publishDispatchPlan.workflowListCommand.replace("OWNER/REPO", repo)
    : `gh workflow list --repo ${repo} --all --json name,path,state,id`;
  const remoteFileCommand = remoteWorkflowFileLedger?.verifyCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`;
  const dispatchPlanCommand = publishDispatchPlan?.nextVerificationCommand || remoteWorkflowFileLedger?.dispatchPlanCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`;
  const handoffCommand = postAuthCheckpoint?.verifyCommand || `node scripts/verify-launch-handoff.mjs --repo ${repo} --write --markdown`;
  const commands = uniq([
    remoteFileCommand,
    workflowListCommand,
    dispatchPlanCommand,
    handoffCommand,
  ]);
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
    "Paste the two default-branch workflow commit URLs or SHA values.",
    "Paste the remote workflow file check output with remoteWorkflowFilesReady=true.",
    "Paste the gh workflow list output showing both workflow paths visible in Actions.",
    "Paste the publish dispatch plan output showing dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true.",
    "Paste the launch handoff verifier output showing safeToDispatch=true before any gh workflow run.",
  ];
  const guard = POST_INSTALL_DISPATCH_GUARD;
  const verificationSequence = [
    {
      key: "remote_file_parity",
      label: "Remote workflow file check",
      command: remoteFileCommand,
      expected: "remoteWorkflowFilesReady=true",
      guard: "Confirm both default-branch workflow files exist and match local templates before checking Actions visibility.",
      evidenceFieldKey: "remote_parity_proof",
    },
    {
      key: "actions_visibility",
      label: "Actions visibility check",
      command: workflowListCommand,
      expected: "remoteWorkflowVisibilityReady=true",
      guard: "Confirm GitHub Actions lists both workflow files before planning dispatch.",
      evidenceFieldKey: "actions_visibility_proof",
    },
    {
      key: "dispatch_readiness",
      label: "Dispatch readiness plan",
      command: dispatchPlanCommand,
      expected: "allDispatchReady=true",
      guard: "Confirm pages and drift dispatch readiness are both true before final handoff verification.",
      evidenceFieldKey: "dispatch_readiness_proof",
    },
    {
      key: "handoff_verifier",
      label: "Launch handoff verifier",
      command: handoffCommand,
      expected: "safeToDispatch=true before gh workflow run",
      guard,
      evidenceFieldKey: "handoff_verifier_proof",
    },
  ];
  const verificationSequenceReady = verificationSequence.length === 4 && verificationSequence.every((step) => step.command && step.expected);
  const remoteFilesReady = remoteWorkflowFileLedger?.remoteWorkflowFilesReady === true ||
    remoteWorkflowFileLedger?.status === "remote_files_ready";
  const safeToDispatch = !!(
    remoteFilesReady &&
    publishDispatchPlan?.remoteWorkflowVisibilityReady &&
    publishDispatchPlan?.allDispatchReady &&
    !publishDispatchPlan?.workflowScopeInstallBlocked
  );
  const itemByKey = (key) => Array.isArray(blockerResolution?.items)
    ? blockerResolution.items.find((item) => item.key === key) || {}
    : {};
  const field = ({ key, label, completed, currentValue, expectedValue, proofCommand, stopCondition, placeholder, sourceKey }) => ({
    key,
    label,
    status: completed ? "proof_ready" : "evidence_required",
    completed: !!completed,
    currentValue: currentValue || "not available",
    expectedValue,
    proofCommand,
    stopCondition,
    placeholder,
    sourceKey,
  });
  const fields = [
    field({
      key: "pages_workflow_commit",
      label: "Pages workflow commit",
      completed: pagesFile.status === "ready" || (pagesFile.remoteExists && pagesFile.remoteMatchesTemplate),
      currentValue: `${valueOrPending(pagesFile.path || ".github/workflows/joopark-pages.yml")}; status=${valueOrPending(pagesFile.status || "missing_on_default_branch")}; remoteSha256=${valueOrPending(pagesFile.remoteSha256)}`,
      expectedValue: `.github/workflows/joopark-pages.yml exists on ${defaultBranch || "main"} and remoteMatchesTemplate=true.`,
      proofCommand: remoteFileCommand,
      stopCondition: "If pages remoteExists=false or remoteMatchesTemplate=false, do not run dispatch.",
      placeholder: "[paste commit URL or SHA for .github/workflows/joopark-pages.yml on the default branch]",
      sourceKey: "remote_workflow_file_parity",
    }),
    field({
      key: "drift_workflow_commit",
      label: "Drift Watch workflow commit",
      completed: driftFile.status === "ready" || (driftFile.remoteExists && driftFile.remoteMatchesTemplate),
      currentValue: `${valueOrPending(driftFile.path || ".github/workflows/joopark-drift-watch.yml")}; status=${valueOrPending(driftFile.status || "missing_on_default_branch")}; remoteSha256=${valueOrPending(driftFile.remoteSha256)}`,
      expectedValue: `.github/workflows/joopark-drift-watch.yml exists on ${defaultBranch || "main"} and remoteMatchesTemplate=true.`,
      proofCommand: remoteFileCommand,
      stopCondition: "If drift-watch remoteExists=false or remoteMatchesTemplate=false, do not run dispatch.",
      placeholder: "[paste commit URL or SHA for .github/workflows/joopark-drift-watch.yml on the default branch]",
      sourceKey: "remote_workflow_file_parity",
    }),
    field({
      key: "remote_parity_proof",
      label: "Remote parity proof",
      completed: remoteFilesReady,
      currentValue: `remoteWorkflowFilesReady=${yesNo(remoteFilesReady)}; filesReady=${valueOrPending(remoteWorkflowFileLedger?.readyCount)}/${valueOrPending(remoteWorkflowFileLedger?.fileCount)}; missing=${valueOrPending(remoteWorkflowFileLedger?.missingCount)}; mismatch=${valueOrPending(remoteWorkflowFileLedger?.mismatchCount)}`,
      expectedValue: "remoteWorkflowFilesReady=true and every workflow file has remoteExists=true and remoteMatchesTemplate=true.",
      proofCommand: remoteFileCommand,
      stopCondition: itemByKey("remote_workflow_file_parity").stopCondition || "If any workflow file is missing or mismatched, do not run dispatch.",
      placeholder: "[paste generatedAt plus remoteWorkflowFilesReady=true from data/remote-workflow-file-check.json]",
      sourceKey: "remote_workflow_file_parity",
    }),
    field({
      key: "actions_visibility_proof",
      label: "Actions visibility proof",
      completed: !!publishDispatchPlan?.remoteWorkflowVisibilityReady,
      currentValue: `remoteWorkflowVisibilityReady=${yesNo(publishDispatchPlan?.remoteWorkflowVisibilityReady)}`,
      expectedValue: "remoteWorkflowVisibilityReady=true and GitHub Actions lists both workflow files.",
      proofCommand: workflowListCommand,
      stopCondition: itemByKey("workflow_visibility").stopCondition || "If GitHub Actions does not list both workflows, keep dispatch withheld.",
      placeholder: "[paste gh workflow list output showing both workflow paths visible]",
      sourceKey: "workflow_visibility",
    }),
    field({
      key: "dispatch_readiness_proof",
      label: "Dispatch readiness proof",
      completed: !!(publishDispatchPlan?.dispatchReady && publishDispatchPlan?.driftDispatchReady && publishDispatchPlan?.allDispatchReady),
      currentValue: `dispatchReady=${yesNo(publishDispatchPlan?.dispatchReady)}; driftDispatchReady=${yesNo(publishDispatchPlan?.driftDispatchReady)}; allDispatchReady=${yesNo(publishDispatchPlan?.allDispatchReady)}`,
      expectedValue: "dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true.",
      proofCommand: dispatchPlanCommand,
      stopCondition: "If allDispatchReady=false, suggestedDispatchCommands must remain empty.",
      placeholder: "[paste generatedAt plus dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true]",
      sourceKey: "dispatch_guard",
    }),
    field({
      key: "handoff_verifier_proof",
      label: "Handoff verifier proof",
      completed: safeToDispatch,
      currentValue: `safeToDispatch=${yesNo(safeToDispatch)}; allDispatchReady=${yesNo(publishDispatchPlan?.allDispatchReady)}`,
      expectedValue: "verify-launch-handoff reports safeToDispatch=true before gh workflow run.",
      proofCommand: handoffCommand,
      stopCondition: itemByKey("dispatch_guard").stopCondition || "If safeToDispatch=false, gh workflow run commands must stay withheld.",
      placeholder: "[paste verify-launch-handoff status plus safeToDispatch=true before gh workflow run]",
      sourceKey: "dispatch_guard",
    }),
  ];
  const completedFieldCount = fields.filter((item) => item.completed).length;
  const fieldCoverage = fields.length >= 6 && commands.length >= 4 && expectedSignals.length >= 8 ? 1 : 0;
  const proofComplete = completedFieldCount === fields.length && fields.length >= 6;
  const quickProofSteps = verificationSequence.map((step) => ({
    key: step.key,
    label: step.label,
    command: step.command,
    expected: step.expected,
    evidenceFieldKey: step.evidenceFieldKey || "",
    status: proofComplete ? "proof_ready" : "evidence_required",
    guard: step.guard || guard,
  }));
  const quickProofCoverage = quickProofSteps.length === 4 && quickProofSteps.every((step) => step.command && step.expected && step.evidenceFieldKey) ? 1 : 0;
  const fieldByKey = new Map(fields.map((item) => [item.key, item]));
  const quickProofFieldMappings = quickProofSteps.map((step) => {
    const mappedField = fieldByKey.get(step.evidenceFieldKey) || {};
    return {
      stepKey: step.key,
      stepLabel: step.label,
      fieldKey: step.evidenceFieldKey || "",
      fieldLabel: mappedField.label || "",
      fieldStatus: mappedField.status || "missing",
      fieldCompleted: !!mappedField.completed,
      currentValue: mappedField.currentValue || "not available",
      expectedValue: mappedField.expectedValue || step.expected || "not available",
      proofCommand: mappedField.proofCommand || step.command || "not available",
      stopCondition: mappedField.stopCondition || step.guard || guard,
    };
  });
  const quickProofFieldMappingCoverage = quickProofFieldMappings.length === 4 &&
    quickProofFieldMappings.every((item) => item.stepKey && item.fieldKey && item.fieldLabel && item.proofCommand && item.expectedValue) ? 1 : 0;
  const quickProofMappedFieldCount = quickProofFieldMappings.length;
  const quickProofCompletedMappedFieldCount = quickProofFieldMappings.filter((item) => item.fieldCompleted).length;
  const quickProofPendingMappedFieldCount = Math.max(quickProofMappedFieldCount - quickProofCompletedMappedFieldCount, 0);
  const quickProofFieldMappingReady = quickProofFieldMappingCoverage === 1;
  const quickProofReady = fieldCoverage === 1 && quickProofCoverage === 1 && quickProofFieldMappingReady;
  const quickProofReceipt = [
    "JooPark Post-Install Quick Proof Receipt",
    `Status: ${proofComplete ? "proof_complete" : "collect_post_install_proof"}`,
    `Repo: ${repo}`,
    `Default branch: ${defaultBranch || "main"}`,
    `Proof complete: ${proofComplete}`,
    `Fields complete: ${completedFieldCount}/${fields.length}`,
    `Quick proof steps: ${quickProofSteps.length}`,
    "",
    "4-step proof checklist:",
    ...quickProofSteps.map((step, index) => `${index + 1}. ${step.key}: run ${step.command}; expect ${step.expected}; paste into ${step.evidenceFieldKey}`),
    "",
    "Mapped proof fields:",
    ...quickProofFieldMappings.map((item, index) => `${index + 1}. ${item.stepKey} -> ${item.fieldKey}: ${item.fieldStatus}; completed=${yesNo(item.fieldCompleted)}; current=${item.currentValue}; expected=${item.expectedValue}`),
    "",
    "Six evidence fields remain required:",
    ...fields.map((item) => `- ${item.label}: ${item.placeholder || item.expectedValue}`),
    "",
    POST_INSTALL_STOP_CONDITION,
  ].join("\n");
  return {
    source: "generated_from_launch_execution_packet",
    status: proofComplete ? "proof_complete" : "collect_post_install_proof",
    ready: quickProofReady,
    proofComplete,
    allProofFieldsReady: proofComplete,
    repo,
    defaultBranch,
    fieldCount: fields.length,
    completedFieldCount,
    pendingFieldCount: Math.max(fields.length - completedFieldCount, 0),
    fieldCoverage,
    commandCount: commands.length,
    signalCount: expectedSignals.length,
    checklistCount: checklist.length,
    verificationSequenceCount: verificationSequence.length,
    verificationSequenceReady,
    finalVerificationCommand: handoffCommand,
    quickProofReady,
    quickProofStepCount: quickProofSteps.length,
    quickProofCoverage,
    quickProofStatus: proofComplete ? "proof_complete" : "collect_post_install_proof",
    quickProofFinalCommand: handoffCommand,
    quickProofReceipt,
    quickProofSteps,
    quickProofFieldMappingReady,
    quickProofFieldMappingCoverage,
    quickProofMappedFieldCount,
    quickProofCompletedMappedFieldCount,
    quickProofPendingMappedFieldCount,
    quickProofFieldMappings,
    dispatchGuard: guard,
    stopCondition: POST_INSTALL_STOP_CONDITION,
    commands,
    expectedSignals,
    checklist,
    verificationSequence,
    fields,
  };
}

function workflowAuthPreflight(publishDispatchPlan, repo) {
  const workflowScope = publishDispatchPlan?.workflowScope || {};
  const scopes = Array.isArray(workflowScope.scopes)
    ? workflowScope.scopes.map((scope) => String(scope)).filter(Boolean)
    : [];
  const checked = workflowScope.checked !== false && (workflowScope.checked || publishDispatchPlan?.workflowScopeChecked || scopes.length > 0);
  const workflowScopeAvailable = !!(publishDispatchPlan?.workflowScopeAvailable ?? workflowScope.available);
  const workflowScopeInstallBlocked = !!publishDispatchPlan?.workflowScopeInstallBlocked;
  const missingScopes = checked && !scopes.includes("workflow") ? ["workflow"] : [];
  const refreshCommand = publishDispatchPlan?.workflowScopeRefreshCommand || "gh auth refresh -h github.com -s workflow";
  const refreshClipboardCommand = publishDispatchPlan?.workflowScopeRefreshClipboardCommand || publishDispatchPlan?.workflowScopeRefreshHandoff?.clipboardCommand || `${refreshCommand} --clipboard`;
  const recheckCommand = publishDispatchPlan?.workflowScopeRecheckCommand || publishDispatchPlan?.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`;
  const approvalHandoff = publishDispatchPlan?.workflowScopeApprovalHandoff && typeof publishDispatchPlan.workflowScopeApprovalHandoff === "object"
    ? publishDispatchPlan.workflowScopeApprovalHandoff
    : publishDispatchPlan?.workflowScopeRefreshHandoff?.approval && typeof publishDispatchPlan.workflowScopeRefreshHandoff.approval === "object"
      ? publishDispatchPlan.workflowScopeRefreshHandoff.approval
      : {};
  const status = !checked ? "not_checked" : workflowScopeAvailable ? "pass" : "action_required";
  return {
    checked: !!checked,
    status,
    source: workflowScope.source || (checked ? "publish-dispatch-plan" : "not checked"),
    workflowScopeAvailable,
    workflowScopeInstallBlocked,
    scopes,
    scopeList: scopes.length ? scopes.join(", ") : checked ? "none reported" : "not checked",
    missingScopes,
    missingScopeList: missingScopes.length ? missingScopes.join(", ") : "none",
    refreshCommand,
    refreshClipboardCommand,
    recheckCommand,
    approvalHandoff,
    approvalRequired: !!approvalHandoff.requiredWhenInstallBlocked || !!(workflowScopeInstallBlocked && missingScopes.includes("workflow")),
    approvalStatus: approvalHandoff.status || (workflowScopeInstallBlocked ? "approval_required" : "not_required"),
    approvalUrl: approvalHandoff.approvalUrl || "https://github.com/login/device",
    approvalExpectedPrompt: approvalHandoff.expectedPrompt || "First copy your one-time code, then open https://github.com/login/device to approve the workflow scope; keep the terminal session open until gh reports success.",
    approvalInteractiveRequired: approvalHandoff.interactiveApprovalRequired ?? !!workflowScopeInstallBlocked,
    approvalTerminalWaitRequired: approvalHandoff.terminalWaitRequired ?? !!workflowScopeInstallBlocked,
    approvalInteractiveNote: approvalHandoff.interactiveApprovalNote || "This is an interactive OAuth device flow; keep the terminal session open until gh reports success. If the browser approval is not completed, gh auth status will still omit workflow.",
    approvalSensitiveValuePolicy: approvalHandoff.sensitiveValuePolicy || "Do not store, log, or paste the one-time device code into project files.",
    approvalPostAuthStatusCommand: approvalHandoff.postApprovalAuthStatusCommand || approvalHandoff.authStatusCommand || "gh auth status -h github.com",
    approvalIncompleteSignal: approvalHandoff.incompleteApprovalSignal || "Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.",
    approvalStopCondition: approvalHandoff.stopCondition || "Do not run install, dispatch, publish copy, or archive proof until workflow scope or GitHub UI installation is verified.",
  };
}

function buildPostAuthCheckpoint({ repo, authPreflight, publishDispatchPlan, remoteWorkflowFileCheck }) {
  const verifyCommand = `node scripts/verify-launch-handoff.mjs --repo ${repo} --write --markdown`;
  const installCommand = remoteWorkflowFileCheck?.remoteInstallerCommand || `node scripts/install-remote-workflow-files.mjs --repo ${repo} --write --verify`;
  const remoteFileCommand = remoteWorkflowFileCheck?.nextVerificationCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`;
  const dispatchPlanCommand = publishDispatchPlan?.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`;
  const authStatusCommand = "gh auth status -h github.com";
  const status = authPreflight?.workflowScopeAvailable ? "pass" : "action_required";
  const guard = "Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true.";
  const expectedSignals = [
    "Token scopes include workflow",
    "workflowScopeAvailable=true",
    "workflowScopeInstallBlocked=false",
    "remoteWorkflowFilesReady=true after installer or GitHub UI commit",
    "remoteWorkflowVisibilityReady=true before dispatch",
    "safeToDispatch=true before gh workflow run",
  ];
  const blockedSignals = [
    "workflowScopeInstallBlocked=true",
    "remoteWorkflowFilesReady=false",
    "remoteWorkflowVisibilityReady=false",
    "allDispatchReady=false",
  ];
  const recheckSequence = [
    {
      key: "confirm_scope",
      label: "Confirm workflow scope",
      command: authStatusCommand,
      expected: "Token scopes include workflow; workflowScopeAvailable=true; workflowScopeInstallBlocked=false",
      sourceArtifact: "gh auth status -h github.com",
      stopCondition: "Stop if workflow scope is still missing; use GitHub UI fallback or rerun the scope refresh.",
    },
    {
      key: "install_workflows",
      label: "Install workflow files",
      command: installCommand,
      expected: workflowInstallActionSummary(remoteWorkflowFileCheck),
      sourceArtifact: "data/remote-workflow-file-check.json",
      stopCondition: "Stop if remote workflow files are not installed on the default branch.",
    },
    {
      key: "verify_remote_parity",
      label: "Verify remote file parity",
      command: remoteFileCommand,
      expected: "remoteWorkflowFilesReady=true; remoteExists=true; remoteMatchesTemplate=true for both workflows",
      sourceArtifact: "data/remote-workflow-file-check.json",
      stopCondition: "Stop if any remote SHA differs from the local template SHA-256.",
    },
    {
      key: "verify_actions_visibility",
      label: "Verify Actions visibility",
      command: dispatchPlanCommand,
      expected: "remoteWorkflowVisibilityReady=true; dispatchReady=true; driftDispatchReady=true; allDispatchReady=true",
      sourceArtifact: "data/publish-dispatch-plan.json",
      stopCondition: "Stop if GitHub Actions does not list both workflows or dispatch commands remain withheld.",
    },
    {
      key: "verify_handoff_guard",
      label: "Verify handoff guard",
      command: verifyCommand,
      expected: "safeToDispatch=true before gh workflow run; every post-install proof field has been filled",
      sourceArtifact: "data/launch-handoff-verification.json",
      stopCondition: "Stop if safeToDispatch=false or post-install proof is incomplete.",
    },
  ];
  const sourceArtifacts = uniq(recheckSequence.map((step) => step.sourceArtifact));
  return {
    key: "post_auth_checkpoint",
    label: "Post-auth checkpoint",
    status,
    verificationOnly: true,
    dispatchApproval: false,
    triggerCommand: authPreflight?.refreshCommand || "gh auth refresh -h github.com -s workflow",
    authStatusCommand,
    recheckCommand: authPreflight?.recheckCommand || dispatchPlanCommand,
    verifyCommand,
    installCommand,
    remoteFileCommand,
    dispatchPlanCommand,
    commandCount: recheckSequence.length,
    recheckSequence,
    recheckSequenceCount: recheckSequence.length,
    sourceArtifacts,
    sourceArtifactCount: sourceArtifacts.length,
    expectedSignals,
    expectedSignalCount: expectedSignals.length,
    blockedSignals,
    blockedSignalCount: blockedSignals.length,
    guard,
  };
}

function stageList({ workflowUiInstallPlan, publishDispatchPlan, remoteWorkflowFileCheck, publishEvidence, outputQualityAudit }) {
  const install = installSteps(workflowUiInstallPlan, publishDispatchPlan);
  const repo = publishDispatchPlan?.repo || publishEvidence?.suggestedRepo || workflowUiInstallPlan?.suggestedRepo || "OWNER/REPO";
  const authPreflight = workflowAuthPreflight(publishDispatchPlan, repo);
  const remoteFileCommand = remoteWorkflowFileCheck?.nextVerificationCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`;
  const remoteWorkflowFilesReady = !!remoteWorkflowFileCheck?.remoteWorkflowFilesReady;
  const dispatchReady = workflowDispatchReady({ publishDispatchPlan, remoteWorkflowFileCheck });
  const proofReady = !!publishEvidence?.postPublishEvidenceReady;
  const externalClaimReady = launchPacketReadyForExternalClaim({ publishEvidence, outputQualityAudit, publishDispatchPlan, remoteWorkflowFileCheck });
  const suggestedDispatchCommands = Array.isArray(publishDispatchPlan?.suggestedDispatchCommands)
    ? publishDispatchPlan.suggestedDispatchCommands
    : [];
  const dispatchCommands = uniq([
    publishDispatchPlan?.dispatchCommand && publishDispatchPlan.dispatchCommand.replace("OWNER/REPO", repo),
    publishDispatchPlan?.driftDispatchCommand && publishDispatchPlan.driftDispatchCommand.replace("OWNER/REPO", repo),
  ]);
  const captureMarkdown = publishEvidenceCaptureMarkdownCommand(publishEvidence, repo);
  const captureWrite = publishEvidenceCaptureWriteCommand(captureMarkdown);
  const workflowScopeInstallBlocked = !!publishDispatchPlan?.workflowScopeInstallBlocked;
  const workflowScopeRefreshCommand = publishDispatchPlan?.workflowScopeRefreshCommand || "gh auth refresh -h github.com -s workflow";
  const workflowScopeRecheckCommand = publishDispatchPlan?.workflowScopeRecheckCommand || publishDispatchPlan?.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`;
  const remoteInstallerCommand = remoteWorkflowFileCheck?.remoteInstallerCommand || `node scripts/install-remote-workflow-files.mjs --repo ${repo} --write --verify`;
  const installPaths = installPathOptions({
    install,
    publishDispatchPlan,
    remoteWorkflowFileCheck,
    remoteFileCommand,
    remoteInstallerCommand,
    workflowScopeInstallBlocked,
    workflowScopeRefreshCommand,
    workflowScopeRecheckCommand,
  });
  const githubUiInstallCommands = workflowUiInstallCommands({ install, remoteWorkflowFileCheck });
  const installActionSummary = workflowInstallActionSummary(remoteWorkflowFileCheck);
  return [
    {
      key: "install_workflows",
      label: "Install workflows on the default branch",
      status: remoteWorkflowFilesReady ? "pass" : "action_required",
      detail: workflowScopeInstallBlocked
        ? `Refresh the GitHub CLI token with workflow scope or use GitHub UI, then ${installActionSummary}; the current CLI token cannot install workflow files.`
        : installActionSummary,
      commands: [
        workflowScopeInstallBlocked ? workflowScopeRefreshCommand : "",
        workflowScopeInstallBlocked ? workflowScopeRecheckCommand : "",
        ...githubUiInstallCommands,
        remoteFileCommand,
      ].filter(Boolean),
      installPaths,
      evidence: [
        `workflowScopeAvailable=${yesNo(publishDispatchPlan?.workflowScopeAvailable)}`,
        `workflowScopeInstallBlocked=${yesNo(publishDispatchPlan?.workflowScopeInstallBlocked)}`,
        `workflowScope.scopes=${authPreflight.scopeList}`,
        `workflowScopeMissing=${authPreflight.missingScopeList}`,
        `workflowScopeRefreshCommand=${workflowScopeRefreshCommand}`,
        `workflowScopeRecheckCommand=${workflowScopeRecheckCommand}`,
        `localTargetParityReady=${yesNo(publishDispatchPlan?.localTargetParityReady ?? workflowUiInstallPlan?.localTargetParityReady)}`,
        `remoteWorkflowFilesReady=${yesNo(remoteWorkflowFileCheck?.remoteWorkflowFilesReady)}`,
        ...install.map((plan) => `${plan.target} templateSha256=${valueOrPending(plan.templateSha256)} targetSha256=${valueOrPending(plan.targetSha256)} targetMatchesTemplate=${yesNo(plan.targetMatchesTemplate)}`),
      ],
    },
    {
      key: "verify_visibility",
      label: "Verify workflow visibility",
      status: remoteWorkflowFilesReady && publishDispatchPlan?.remoteWorkflowVisibilityReady ? "pass" : "action_required",
      detail: "Confirm GitHub Actions can see the workflow files before attempting dispatch.",
      commands: uniq([
        publishDispatchPlan?.nextVerificationCommand,
        publishDispatchPlan?.workflowListCommand && publishDispatchPlan.workflowListCommand.replace("OWNER/REPO", repo),
      ]),
      evidence: [`remoteWorkflowVisibilityReady=${yesNo(publishDispatchPlan?.remoteWorkflowVisibilityReady)}`],
    },
    {
      key: "dispatch_gate",
      label: "Dispatch only after allDispatchReady",
      status: dispatchReady ? "ready" : "withheld",
      detail: "Do not run gh workflow run until repoEvidenceReady, dispatchReady, driftDispatchReady, and allDispatchReady are all true.",
      commands: dispatchReady ? suggestedDispatchCommands : dispatchCommands,
      evidence: [
        `repoEvidenceReady=${yesNo(publishDispatchPlan?.repoEvidenceReady)}`,
        `remoteWorkflowFilesReady=${yesNo(remoteWorkflowFilesReady)}`,
        `remoteWorkflowVisibilityReady=${yesNo(publishDispatchPlan?.remoteWorkflowVisibilityReady)}`,
        `dispatchReady=${yesNo(publishDispatchPlan?.dispatchReady)}`,
        `driftDispatchReady=${yesNo(publishDispatchPlan?.driftDispatchReady)}`,
        `allDispatchReady=${yesNo(publishDispatchPlan?.allDispatchReady)}`,
        `dispatchSuggestionStatus=${valueOrPending(publishDispatchPlan?.dispatchSuggestionStatus)}`,
      ],
    },
    {
      key: "capture_launch_proof",
      label: "Capture launch proof",
      status: proofReady ? "pass" : "action_required_after_dispatch",
      detail: "After both workflow runs complete, capture Pages URL/status and the latest Pages/Drift workflow run status/conclusion.",
      commands: uniq([captureMarkdown, captureWrite]),
      evidence: [
        `postPublishEvidenceReady=${yesNo(publishEvidence?.postPublishEvidenceReady)}`,
        `evidenceFresh=${yesNo(publishEvidence?.evidenceFresh)}`,
      ],
    },
    {
      key: "share_or_archive",
      label: "Share or archive only after proof",
      status: externalClaimReady ? "ready" : "blocked",
      detail: "Use the public launch announcement or archive receipt only after live launch proof is present.",
      commands: ["copy System Status quality receipt", "copy publish evidence share update", "copy post-launch verification receipt"],
      evidence: [
        `readyForExternalClaim=${yesNo(externalClaimReady)}`,
        `publicLaunchProofReady=${yesNo(publicLaunchProofReadyFromEvidence(publishEvidence, outputQualityAudit))}`,
      ],
    },
  ];
}

function blockerLines({ publishDispatchPlan, remoteWorkflowFileCheck, publishEvidence, stages }) {
  const blockers = [];
  stages.filter((stage) => !["pass", "ready"].includes(stage.status)).forEach((stage) => {
    blockers.push(`${stage.label}: ${stage.status} - ${stage.detail}`);
  });
  if (Array.isArray(remoteWorkflowFileCheck?.blockers)) remoteWorkflowFileCheck.blockers.forEach((item) => blockers.push(`Remote workflow file check: ${item}`));
  if (Array.isArray(publishDispatchPlan?.blockers)) publishDispatchPlan.blockers.forEach((item) => blockers.push(`Publish dispatch: ${item}`));
  if (Array.isArray(publishEvidence?.blockers)) publishEvidence.blockers.forEach((item) => blockers.push(`Publish evidence: ${item}`));
  return uniq(blockers);
}

function currentActionAcceptanceChecklist({ stages, remoteWorkflowFileCheck, publishDispatchPlan, authPreflight }) {
  const dispatchStage = stages.find((stage) => stage.key === "dispatch_gate") || {};
  const withheldCommandCount = Array.isArray(dispatchStage.commands) ? dispatchStage.commands.length : 0;
  const workflowScopeAvailable = !!publishDispatchPlan?.workflowScopeAvailable;
  const workflowScopeInstallBlocked = !!publishDispatchPlan?.workflowScopeInstallBlocked;
  const localTargetParityReady = !!publishDispatchPlan?.localTargetParityReady;
  const remoteWorkflowFilesReady = !!remoteWorkflowFileCheck?.remoteWorkflowFilesReady;
  const remoteWorkflowVisibilityReady = !!publishDispatchPlan?.remoteWorkflowVisibilityReady;
  const allDispatchReady = workflowDispatchReady({ publishDispatchPlan, remoteWorkflowFileCheck });
  const dispatchWithheld = !allDispatchReady && withheldCommandCount >= 2;
  return [
    {
      key: "operator_auth_path",
      label: "Operator auth path",
      status: workflowScopeInstallBlocked ? "action_required" : "pass",
      required: "Use a workflow-scope GitHub CLI token or a workflow-capable GitHub UI session before writing workflow files to the default branch.",
      evidence: `workflowScopeAvailable=${yesNo(workflowScopeAvailable)}; workflowScopeInstallBlocked=${yesNo(workflowScopeInstallBlocked)}; workflowScope.scopes=${valueOrPending(authPreflight?.scopeList)}; workflowScopeMissing=${valueOrPending(authPreflight?.missingScopeList)}; workflowScopeRefreshCommand=${valueOrPending(publishDispatchPlan?.workflowScopeRefreshCommand)}`,
    },
    {
      key: "local_template_parity",
      label: "Local template parity",
      status: localTargetParityReady ? "pass" : "action_required",
      required: "Local repository workflow targets must exist and match the prepared workflow templates before remote installation.",
      evidence: `localTargetParityReady=${yesNo(localTargetParityReady)}`,
    },
    {
      key: "remote_workflow_file_parity",
      label: "Remote workflow file parity",
      status: remoteWorkflowFilesReady ? "pass" : "action_required",
      required: "Remote default-branch workflow files must exist and match the local template SHA-256 values.",
      evidence: `remoteWorkflowFilesReady=${yesNo(remoteWorkflowFilesReady)}; nextVerificationCommand=${valueOrPending(remoteWorkflowFileCheck?.nextVerificationCommand)}`,
    },
    {
      key: "workflow_visibility",
      label: "Workflow visibility",
      status: remoteWorkflowVisibilityReady ? "pass" : "action_required",
      required: "GitHub Actions must list both workflows before any dispatch command is suggested.",
      evidence: `remoteWorkflowVisibilityReady=${yesNo(remoteWorkflowVisibilityReady)}; workflowListCommand=${valueOrPending(publishDispatchPlan?.workflowListCommand)}`,
    },
    {
      key: "dispatch_guard",
      label: "Dispatch guard",
      status: dispatchWithheld || allDispatchReady ? "pass" : "blocked",
      required: "Keep gh workflow run commands withheld until remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, and allDispatchReady=true.",
      evidence: `allDispatchReady=${yesNo(allDispatchReady)}; withheldCommands=${valueOrPending(withheldCommandCount)}`,
    },
  ];
}

function authPreflightLines(authPreflight) {
  return [
    "Auth preflight:",
    `- status: ${valueOrPending(authPreflight?.status)}`,
    `- checked: ${yesNo(authPreflight?.checked)}`,
    `- source: ${valueOrPending(authPreflight?.source)}`,
    `- workflowScopeAvailable: ${yesNo(authPreflight?.workflowScopeAvailable)}`,
    `- workflowScopeInstallBlocked: ${yesNo(authPreflight?.workflowScopeInstallBlocked)}`,
    `- scopes: ${valueOrPending(authPreflight?.scopeList)}`,
    `- missingScopes: ${valueOrPending(authPreflight?.missingScopeList)}`,
    `- refresh: ${valueOrPending(authPreflight?.refreshCommand)}`,
    `- refreshWithClipboard: ${valueOrPending(authPreflight?.refreshClipboardCommand)}`,
    `- recheck: ${valueOrPending(authPreflight?.recheckCommand)}`,
    `- approval: ${valueOrPending(authPreflight?.approvalStatus)}`,
    `- approvalUrl: ${valueOrPending(authPreflight?.approvalUrl)}`,
    `- approvalPrompt: ${valueOrPending(authPreflight?.approvalExpectedPrompt)}`,
    `- interactiveApprovalRequired: ${yesNo(authPreflight?.approvalInteractiveRequired)}`,
    `- terminalWaitRequired: ${yesNo(authPreflight?.approvalTerminalWaitRequired)}`,
    `- interactiveApprovalNote: ${valueOrPending(authPreflight?.approvalInteractiveNote)}`,
    `- postApprovalAuthStatus: ${valueOrPending(authPreflight?.approvalPostAuthStatusCommand)}`,
    `- incompleteApprovalSignal: ${valueOrPending(authPreflight?.approvalIncompleteSignal)}`,
    `- sensitiveValuePolicy: ${valueOrPending(authPreflight?.approvalSensitiveValuePolicy)}`,
    `- approvalStopCondition: ${valueOrPending(authPreflight?.approvalStopCondition)}`,
  ];
}

function postAuthCheckpointLines(checkpoint) {
  const recheckSequence = Array.isArray(checkpoint?.recheckSequence) ? checkpoint.recheckSequence : [];
  const sourceArtifacts = Array.isArray(checkpoint?.sourceArtifacts) ? checkpoint.sourceArtifacts : [];
  const recheckSequenceCount = numberOr(checkpoint?.recheckSequenceCount, recheckSequence.length);
  return [
    "Post-auth checkpoint:",
    `- status: ${valueOrPending(checkpoint?.status)}`,
    `- verificationOnly: ${yesNo(checkpoint?.verificationOnly)}`,
    `- dispatchApproval: ${yesNo(checkpoint?.dispatchApproval)}`,
    `- trigger: ${valueOrPending(checkpoint?.triggerCommand)}`,
    `- confirm scope: ${valueOrPending(checkpoint?.authStatusCommand)}`,
    `- recheck dispatch plan: ${valueOrPending(checkpoint?.recheckCommand)}`,
    `- verify handoff: ${valueOrPending(checkpoint?.verifyCommand)}`,
    `- install after pass: ${valueOrPending(checkpoint?.installCommand)}`,
    `- recheck sequence: ${valueOrPending(recheckSequenceCount)}`,
    `- source artifacts: ${sourceArtifacts.length ? sourceArtifacts.join("; ") : "not available"}`,
    `- expected: ${Array.isArray(checkpoint?.expectedSignals) ? checkpoint.expectedSignals.join("; ") : "not available"}`,
    `- still blocked if: ${Array.isArray(checkpoint?.blockedSignals) ? checkpoint.blockedSignals.join("; ") : "not available"}`,
    `- guard: ${valueOrPending(checkpoint?.guard)}`,
    "Recheck sequence:",
    ...recheckSequence.map((step, index) => `${index + 1}. ${valueOrPending(step.key)}: command=${valueOrPending(step.command)}; expected=${valueOrPending(step.expected)}; source=${valueOrPending(step.sourceArtifact)}; stop=${valueOrPending(step.stopCondition)}`),
  ];
}

function defaultBranchRequirementProof({ repo, defaultBranch, remoteWorkflowFileCheck, publishDispatchPlan }) {
  const checks = Array.isArray(remoteWorkflowFileCheck?.checks) ? remoteWorkflowFileCheck.checks : [];
  const workflowFiles = checks
    .map((check) => check.path || check.workflowFile || "")
    .filter(Boolean);
  const workflowListCommand = publishDispatchPlan?.workflowListCommand
    ? publishDispatchPlan.workflowListCommand.replace("OWNER/REPO", repo)
    : `gh workflow list --repo ${repo} --all --json name,path,state,id`;
  const installActionSummary = workflowInstallActionSummary(remoteWorkflowFileCheck);
  return {
    ready: true,
    source: "GitHub manual workflow dispatch docs + GitHub REST repository contents API",
    defaultBranch: defaultBranch || "main",
    workflowFileCount: workflowFiles.length,
    workflowFiles,
    manualDispatchDocsUrl: remoteWorkflowFileCheck?.manualDispatchDocsUrl || "https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui",
    repositoryContentsDocsUrl: remoteWorkflowFileCheck?.sourceUrl || "https://docs.github.com/en/rest/repos/contents#get-repository-content",
    workflowListCommand,
    requirements: [
      `${installActionSummary} Target workflow YAML files live under .github/workflows on the ${defaultBranch || "main"} default branch.`,
      "Manual workflow dispatch is available only after workflow_dispatch exists on the default branch.",
      "Remote workflow file check must read the default-branch contents and match each local template SHA-256.",
      "GitHub Actions visibility must be confirmed before gh workflow run commands are suggested.",
    ],
  };
}

function defaultBranchRequirementProofLines(proof) {
  const workflowFiles = Array.isArray(proof?.workflowFiles) ? proof.workflowFiles : [];
  const requirements = Array.isArray(proof?.requirements) ? proof.requirements : [];
  return [
    "Default-branch requirement proof:",
    `- source: ${valueOrPending(proof?.source)}`,
    `- defaultBranch: ${valueOrPending(proof?.defaultBranch)}`,
    `- workflowFiles: ${workflowFiles.length ? workflowFiles.join(", ") : "not available"}`,
    `- manual dispatch docs: ${valueOrPending(proof?.manualDispatchDocsUrl)}`,
    `- repository contents verification: ${valueOrPending(proof?.repositoryContentsDocsUrl)}`,
    `- visibility recheck: ${valueOrPending(proof?.workflowListCommand)}`,
    ...requirements.map((requirement) => `- requirement: ${requirement}`),
  ];
}

function currentActionPacket({ repo, defaultBranch, stages, remoteWorkflowFileCheck, publishDispatchPlan, authPreflight, postAuthCheckpoint }) {
  const currentStage = stages.find((stage) => !["pass", "ready"].includes(stage.status)) || stages[0] || null;
  const blockedDispatchCommands = stages
    .find((stage) => stage.key === "dispatch_gate")
    ?.commands || [];
  const firstCommands = Array.isArray(currentStage?.commands) ? currentStage.commands : [];
  const installPaths = currentStage?.key === "install_workflows" && Array.isArray(currentStage?.installPaths)
    ? currentStage.installPaths
    : [];
  const launchHandoffVerificationCommand = `node scripts/verify-launch-handoff.mjs --repo ${repo} --write`;
  const remoteInstallerCommand = remoteWorkflowFileCheck?.remoteInstallerCommand || `node scripts/install-remote-workflow-files.mjs --repo ${repo} --write --verify`;
  const acceptanceChecklist = currentActionAcceptanceChecklist({ stages, remoteWorkflowFileCheck, publishDispatchPlan, authPreflight });
  const acceptancePassCount = acceptanceChecklist.filter((item) => item.status === "pass").length;
  const acceptancePendingCount = acceptanceChecklist.length - acceptancePassCount;
  const defaultBranchProof = defaultBranchRequirementProof({ repo, defaultBranch, remoteWorkflowFileCheck, publishDispatchPlan });
  const successCondition = currentStage?.key === "install_workflows"
    ? "remoteWorkflowFilesReady=true and each remote workflow file matches the local template SHA-256."
    : currentStage?.key === "verify_visibility"
      ? "remoteWorkflowVisibilityReady=true and allDispatchReady=true before dispatch commands appear."
      : currentStage?.key === "dispatch_gate"
        ? "Pages and Drift Watch workflow_dispatch runs are started only after allDispatchReady=true."
        : currentStage?.key === "capture_launch_proof"
          ? "postPublishEvidenceReady=true and evidenceFresh=true after live workflow runs complete."
          : "readyForExternalClaim=true before public launch copy or archive receipt is used.";
  const handoff = [
    "JooPark Launch Current Action Packet",
    `Repo: ${repo}`,
    `Default branch: ${valueOrPending(defaultBranch)}`,
    `Current stage: ${valueOrPending(currentStage?.label)} [${valueOrPending(currentStage?.status)}]`,
    `Why now: ${valueOrPending(currentStage?.detail)}`,
    `Success condition: ${successCondition}`,
    "",
    ...authPreflightLines(authPreflight),
    "",
    ...postAuthCheckpointLines(postAuthCheckpoint),
    "",
    ...defaultBranchRequirementProofLines(defaultBranchProof),
    "",
    `Acceptance checklist: ${acceptancePassCount}/${acceptanceChecklist.length} pass; pending=${acceptancePendingCount}`,
    ...acceptanceChecklist.map((item) => `- ${item.label}: ${item.status} - ${item.required} Evidence: ${item.evidence}`),
    "",
    installPaths.length ? "Choose one install path:" : "Run now:",
    ...(installPaths.length ? installPaths.flatMap((path) => [
      `${path.label}:`,
      `- When: ${path.when}`,
      ...path.commands.map((command) => `- ${command}`),
      `- Success: ${path.success}`,
      `- Guard: ${path.guard}`,
    ]) : firstCommands.length ? firstCommands.map((command) => `- ${command}`) : ["- no immediate command available"]),
    "",
    "Verify after running:",
    `- ${launchHandoffVerificationCommand}`,
    `- ${remoteInstallerCommand}`,
    `- ${remoteWorkflowFileCheck?.nextVerificationCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`}`,
    `- ${publishDispatchPlan?.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`}`,
    "",
    "Do not run yet:",
    ...(blockedDispatchCommands.length ? blockedDispatchCommands.map((command) => `- ${command}`) : ["- gh workflow run commands remain withheld until allDispatchReady=true"]),
    "",
    "Guard: do not publish or archive launch proof until postPublishEvidenceReady=true and readyForExternalClaim=true.",
  ];
  return {
    status: currentStage ? currentStage.status : "ready",
    stageKey: currentStage?.key || "",
    label: currentStage?.label || "",
    successCondition,
    commandCount: firstCommands.length,
    withheldCommandCount: blockedDispatchCommands.length,
    authPreflight,
    postAuthCheckpoint,
    defaultBranchRequirementProof: defaultBranchProof,
    acceptanceChecklist,
    acceptancePassCount,
    acceptancePendingCount,
    commands: firstCommands,
    installPaths,
    verifyCommands: uniq([
      launchHandoffVerificationCommand,
      remoteInstallerCommand,
      remoteWorkflowFileCheck?.nextVerificationCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`,
      publishDispatchPlan?.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`,
    ]),
    withheldCommands: blockedDispatchCommands,
    packet: handoff.join("\n"),
  };
}

function operatorOnePageHandoff({ generatedAt, repo, defaultBranch, currentAction, blockerResolution, postInstallIntake, workflowInstallMatrix, remoteWorkflowFileLedger, launchProofLedger, authPreflight, postAuthCheckpoint }) {
  const installPaths = Array.isArray(currentAction?.installPaths) ? currentAction.installPaths : [];
  const uiPath = installPaths.find((path) => path.key === "github_ui") || {};
  const activeItem = Array.isArray(blockerResolution?.items)
    ? blockerResolution.items.find((item) => item.key === blockerResolution.activeItemKey) || blockerResolution.items.find((item) => item.status === "action_required") || {}
    : {};
  const immediateCommands = uniq([
    authPreflight?.workflowScopeAvailable ? "" : authPreflight?.refreshCommand || "gh auth refresh -h github.com -s workflow",
    authPreflight?.recheckCommand || workflowInstallMatrix?.dispatchPlanCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`,
  ]);
  const fallbackCommands = Array.isArray(uiPath.commands) ? uiPath.commands : [];
  const proofCommands = uniq([
    remoteWorkflowFileLedger?.verifyCommand || workflowInstallMatrix?.remoteFileCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`,
    workflowInstallMatrix?.workflowListCommand || `gh workflow list --repo ${repo} --all --json name,path,state,id`,
    workflowInstallMatrix?.dispatchPlanCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`,
    postAuthCheckpoint?.verifyCommand || workflowInstallMatrix?.handoffCommand || `node scripts/verify-launch-handoff.mjs --repo ${repo} --write --markdown`,
  ]);
  const quickProofSteps = Array.isArray(postInstallIntake?.quickProofSteps) ? postInstallIntake.quickProofSteps : [];
  const successSignals = uniq([
    "workflowScopeAvailable=true or GitHub UI installAction rows applied on the default branch",
    "remoteWorkflowFilesReady=true",
    "remoteWorkflowVisibilityReady=true",
    "dispatchReady=true",
    "driftDispatchReady=true",
    "allDispatchReady=true",
    "all six post-install evidence fields are filled",
    "safeToDispatch=true before gh workflow run",
  ]);
  const evidenceFields = Array.isArray(postInstallIntake?.fields)
    ? postInstallIntake.fields.map((field) => `${field.label || field.key}: ${field.placeholder || field.expectedValue || "paste proof"}`)
    : [];
  const forbiddenCommands = uniq([
    ...(Array.isArray(currentAction?.withheldCommands) ? currentAction.withheldCommands : []),
    "Do not post public launch copy.",
    "Do not archive post-launch proof.",
    "Do not claim readyForExternalClaim=true.",
  ]);
  const stopCondition = postInstallIntake?.stopCondition || launchProofLedger?.deferredUntil || "Do not dispatch or claim launch until every post-install evidence field has been filled, verify-launch-handoff reports safeToDispatch=true, and postPublishEvidenceReady=true.";
  const stopConditionLine = String(stopCondition).startsWith("Stop condition:")
    ? stopCondition
    : `Stop condition: ${stopCondition}`;
  const sectionCount = 8;
  const commandCount = immediateCommands.length + fallbackCommands.length + proofCommands.length + forbiddenCommands.filter((item) => item.startsWith("gh ")).length;
  const text = [
    "JooPark Launch Operator One-Page Handoff",
    `Status: ${valueOrPending(currentAction?.status || "action_required")}`,
    `Generated: ${generatedAt}`,
    `Repo: ${repo}`,
    `Default branch: ${valueOrPending(defaultBranch)}`,
    "",
    "Goal for this pass:",
    `- ${valueOrPending(currentAction?.label || "Install workflows on the default branch")}`,
    `- Success: ${valueOrPending(currentAction?.successCondition || "remoteWorkflowFilesReady=true and remote workflow files match local templates.")}`,
    `- Active blocker: ${valueOrPending(blockerResolution?.activeItemKey || activeItem.key || "operator_auth_path")} (${valueOrPending(activeItem.status || currentAction?.status || "action_required")})`,
    "",
    "Do first:",
    ...immediateCommands.map((command, index) => `${index + 1}. ${command}`),
    "",
    "If CLI workflow scope is still blocked, use GitHub UI fallback:",
    ...(fallbackCommands.length ? fallbackCommands.map((command, index) => `${index + 1}. ${command}`) : ["1. Use the GitHub UI workflow install plan and commit only required create/edit workflow rows on the default branch."]),
    "",
    "Prove after install:",
    ...proofCommands.map((command, index) => `${index + 1}. ${command}`),
    "",
    "Post-install quick proof:",
    ...(quickProofSteps.length ? quickProofSteps.map((step, index) => `${index + 1}. ${step.key}: expect ${step.expected}; paste into ${step.evidenceFieldKey}`) : ["1. Run the four post-install verification commands and paste their expected signals."]),
    "",
    "Success signals:",
    ...successSignals.map((signal) => `- ${signal}`),
    "",
    "Evidence fields to fill:",
    ...(evidenceFields.length ? evidenceFields.map((field) => `- ${field}`) : ["- Remote parity proof", "- Actions visibility proof", "- Dispatch readiness proof", "- Handoff verifier proof"]),
    "",
    "Do not run or claim yet:",
    ...forbiddenCommands.map((command) => `- ${command}`),
    "",
    "External baseline:",
    "- GitHub workflow_dispatch must exist on the default branch before manual dispatch.",
    "- GitHub Pages proof must include live Pages status and workflow run status/conclusion evidence.",
    "",
    stopConditionLine,
  ].join("\n");
  return {
    source: "generated_from_launch_execution_packet",
    status: currentAction?.status || "action_required",
    ready: !!(text && sectionCount >= 8 && proofCommands.length >= 4 && successSignals.length >= 8 && forbiddenCommands.length >= 3),
    repo,
    defaultBranch,
    activeItemKey: blockerResolution?.activeItemKey || activeItem.key || "",
    stageKey: currentAction?.stageKey || "",
    sectionCount,
    commandCount,
    immediateCommandCount: immediateCommands.length,
    fallbackCommandCount: fallbackCommands.length,
    proofCommandCount: proofCommands.length,
    quickProofStepCount: quickProofSteps.length,
    quickProofCoverage: Number(postInstallIntake?.quickProofCoverage || 0),
    successSignalCount: successSignals.length,
    evidenceFieldCount: evidenceFields.length,
    forbiddenCommandCount: forbiddenCommands.length,
    immediateCommands,
    fallbackCommands,
    proofCommands,
    quickProofSteps,
    successSignals,
    evidenceFields,
    forbiddenCommands,
    stopCondition: stopConditionLine,
    text,
  };
}

function stageTransitionPreview({ stages, currentAction, postAuthCheckpoint, readyToDispatch }) {
  const currentStage = stages.find((stage) => stage.key === currentAction?.stageKey) || stages.find((stage) => !["pass", "ready"].includes(stage.status)) || stages[0] || {};
  const visibilityStage = stages.find((stage) => stage.key === "verify_visibility") || {};
  const dispatchGateStage = stages.find((stage) => stage.key === "dispatch_gate") || {};
  const captureStage = stages.find((stage) => stage.key === "capture_launch_proof") || {};
  const nextStage = readyToDispatch
    ? captureStage
    : currentStage.key === "verify_visibility"
      ? dispatchGateStage
      : visibilityStage;
  const pendingAcceptanceCount = Number.isFinite(currentAction?.acceptancePendingCount)
    ? currentAction.acceptancePendingCount
    : Array.isArray(currentAction?.acceptanceChecklist) ? currentAction.acceptanceChecklist.filter((item) => item.status !== "pass").length : 0;
  const passAcceptanceCount = Number.isFinite(currentAction?.acceptancePassCount)
    ? currentAction.acceptancePassCount
    : Array.isArray(currentAction?.acceptanceChecklist) ? currentAction.acceptanceChecklist.filter((item) => item.status === "pass").length : 0;
  const withheldDispatchCommandCount = Number.isFinite(currentAction?.withheldCommandCount) ? currentAction.withheldCommandCount : 0;
  const gateCommand = postAuthCheckpoint?.verifyCommand ||
    (Array.isArray(currentAction?.verifyCommands) ? currentAction.verifyCommands.find((command) => command.includes("verify-launch-handoff")) : "") ||
    "node scripts/verify-launch-handoff.mjs --repo OWNER/REPO --write --markdown";
  const status = readyToDispatch ? "ready_after_guard" : "conditional";
  return {
    source: "generated_from_launch_execution_packet",
    status,
    currentStageKey: currentStage.key || currentAction?.stageKey || "",
    currentStageLabel: currentStage.label || currentAction?.label || "Current stage",
    currentStageStatus: currentStage.status || currentAction?.status || "action_required",
    nextStageKey: nextStage.key || (readyToDispatch ? "capture_launch_proof" : "verify_visibility"),
    nextStageLabel: nextStage.label || (readyToDispatch ? "Capture launch proof" : "Verify workflow visibility"),
    readyToAdvance: !!readyToDispatch,
    pendingAcceptanceCount,
    passAcceptanceCount,
    withheldDispatchCommandCount,
    gateCommand,
    requiredSignals: readyToDispatch ? [
      "safeToDispatch=true",
      "postPublishEvidenceReady=true after workflow runs",
    ] : [
      "remoteWorkflowFilesReady=true",
      "remoteWorkflowVisibilityReady=true",
      "allDispatchReady=true",
      "safeToDispatch=true before gh workflow run",
    ],
    dispatchGuard: readyToDispatch
      ? "Run only suggested dispatch commands, then capture launch proof."
      : "Keep gh workflow run commands withheld until allDispatchReady=true and safeToDispatch=true.",
    steps: [
      {
        key: "complete-current-stage",
        label: currentStage.label || currentAction?.label || "Complete current stage",
        status: currentStage.status || currentAction?.status || "action_required",
        condition: currentAction?.successCondition || "Complete the current launch stage and rerun verification.",
      },
      {
        key: "unlock-next-stage",
        label: nextStage.label || (readyToDispatch ? "Capture launch proof" : "Verify workflow visibility"),
        status,
        condition: readyToDispatch ? "safeToDispatch=true; capture live publish evidence next." : "remoteWorkflowFilesReady=true and remoteWorkflowVisibilityReady=true before dispatch.",
      },
      {
        key: "keep-dispatch-withheld",
        label: dispatchGateStage.label || "Dispatch only after allDispatchReady",
        status: readyToDispatch ? "ready" : "withheld",
        condition: readyToDispatch ? "Run only suggestedDispatchCommands, then capture launch proof." : "Keep gh workflow run withheld until allDispatchReady=true and safeToDispatch=true.",
      },
    ],
  };
}

function blockerResolutionChecklist({ repo, currentAction, workflowInstallMatrix, remoteWorkflowFileLedger, launchProofLedger, authPreflight, postAuthCheckpoint, publishDispatchPlan, remoteWorkflowFileCheck }) {
  const acceptance = Array.isArray(currentAction?.acceptanceChecklist) ? currentAction.acceptanceChecklist : [];
  const signalChecks = Array.isArray(workflowInstallMatrix?.signalChecks) ? workflowInstallMatrix.signalChecks : [];
  const acceptanceByKey = (key) => acceptance.find((item) => item.key === key) || signalChecks.find((item) => item.key === key) || {};
  const workflowListCommand = workflowInstallMatrix?.workflowListCommand ||
    (publishDispatchPlan?.workflowListCommand ? publishDispatchPlan.workflowListCommand.replace("OWNER/REPO", repo) : `gh workflow list --repo ${repo} --all --json name,path,state,id`);
  const remoteFileCommand = remoteWorkflowFileCheck?.nextVerificationCommand || workflowInstallMatrix?.remoteFileCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`;
  const dispatchPlanCommand = publishDispatchPlan?.nextVerificationCommand || workflowInstallMatrix?.dispatchPlanCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`;
  const handoffCommand = postAuthCheckpoint?.verifyCommand || workflowInstallMatrix?.handoffCommand || `node scripts/verify-launch-handoff.mjs --repo ${repo} --write --markdown`;
  const captureWriteCommand = launchProofLedger?.captureWriteCommand || `node scripts/capture-publish-evidence.mjs --live --repo ${repo} --write`;
  const authSignal = acceptanceByKey("operator_auth_path");
  const localSignal = acceptanceByKey("local_template_parity");
  const remoteSignal = acceptanceByKey("remote_workflow_file_parity");
  const visibilitySignal = acceptanceByKey("workflow_visibility");
  const dispatchSignal = acceptanceByKey("dispatch_guard");
  const remoteFileCount = Number(remoteWorkflowFileLedger?.fileCount || 0);
  const remoteReadyCount = Number(remoteWorkflowFileLedger?.readyCount || 0);
  const remoteMissingCount = Number(remoteWorkflowFileLedger?.missingCount || 0);
  const remoteMismatchCount = Number(remoteWorkflowFileLedger?.mismatchCount || 0);
  const proofReadyCount = Number(launchProofLedger?.readyProofCount || 0);
  const proofRequiredCount = Number(launchProofLedger?.requiredProofCount || 0);
  const proofPendingCount = Number(launchProofLedger?.pendingProofCount ?? Math.max(proofRequiredCount - proofReadyCount, 0));
  const items = [
    {
      key: "operator_auth_path",
      label: "Resolve workflow auth path",
      status: authSignal.status || (authPreflight?.workflowScopeInstallBlocked ? "action_required" : "pass"),
      blockedSignal: `workflowScopeAvailable=${yesNo(authPreflight?.workflowScopeAvailable)}; workflowScopeInstallBlocked=${yesNo(authPreflight?.workflowScopeInstallBlocked)}; missingScopes=${valueOrPending(authPreflight?.missingScopeList)}`,
      action: "Refresh GitHub CLI with workflow scope, or choose the GitHub UI path with a workflow-capable browser session.",
      proofCommand: authPreflight?.workflowScopeAvailable ? authPreflight?.recheckCommand || dispatchPlanCommand : authPreflight?.refreshCommand || "gh auth refresh -h github.com -s workflow",
      expectedValue: "workflowScopeAvailable=true; workflowScopeInstallBlocked=false, or GitHub UI path chosen to apply each workflow row's installAction on the default branch.",
      stopCondition: "If workflowScopeInstallBlocked=true remains after recheck, do not run the CLI installer; use the GitHub UI path and keep dispatch withheld.",
      evidence: authSignal.evidence || "",
    },
    {
      key: "local_template_parity",
      label: "Confirm local workflow templates",
      status: localSignal.status || (publishDispatchPlan?.localTargetParityReady ? "pass" : "action_required"),
      blockedSignal: `localTargetParityReady=${yesNo(publishDispatchPlan?.localTargetParityReady)}`,
      action: "Regenerate or restage local workflow targets if template parity fails before copying anything to GitHub.",
      proofCommand: publishDispatchPlan?.nextVerificationCommand || dispatchPlanCommand,
      expectedValue: "localTargetParityReady=true; each local target SHA-256 matches its template SHA-256.",
      stopCondition: "Do not create remote workflow files from stale or mismatched local targets.",
      evidence: localSignal.evidence || "",
    },
    {
      key: "remote_workflow_file_parity",
      label: "Prove remote workflow file parity",
      status: remoteSignal.status || (remoteWorkflowFileCheck?.remoteWorkflowFilesReady ? "pass" : "action_required"),
      blockedSignal: `remoteWorkflowFilesReady=${yesNo(remoteWorkflowFileCheck?.remoteWorkflowFilesReady)}; filesReady=${remoteReadyCount}/${remoteFileCount}; missing=${remoteMissingCount}; mismatch=${remoteMismatchCount}`,
      action: "Apply each workflow row's installAction on the default branch, then compare remote SHA-256 values against local templates.",
      proofCommand: remoteFileCommand,
      expectedValue: "remoteWorkflowFilesReady=true; every workflow file has remoteExists=true and remoteMatchesTemplate=true.",
      stopCondition: "If any workflow file is missing_on_default_branch or sha_mismatch, do not run dispatch.",
      evidence: remoteSignal.evidence || "",
    },
    {
      key: "workflow_visibility",
      label: "Prove GitHub Actions visibility",
      status: visibilitySignal.status || (publishDispatchPlan?.remoteWorkflowVisibilityReady ? "pass" : "action_required"),
      blockedSignal: `remoteWorkflowVisibilityReady=${yesNo(publishDispatchPlan?.remoteWorkflowVisibilityReady)}`,
      action: "List repository workflows and rerun the dispatch plan after remote file parity passes.",
      proofCommand: workflowListCommand,
      expectedValue: "remoteWorkflowVisibilityReady=true; Publish JooPark Pages and Watch JooPark Candidate Drift are visible.",
      stopCondition: "If GitHub Actions does not list both workflows, keep suggestedDispatchCommands empty.",
      evidence: visibilitySignal.evidence || "",
    },
    {
      key: "dispatch_guard",
      label: "Keep dispatch guarded",
      status: dispatchSignal.status || (publishDispatchPlan?.allDispatchReady ? "ready" : "pass"),
      blockedSignal: `allDispatchReady=${yesNo(publishDispatchPlan?.allDispatchReady)}; safeToDispatch=${yesNo(publishDispatchPlan?.allDispatchReady)}; dispatchSuggestionStatus=${valueOrPending(publishDispatchPlan?.dispatchSuggestionStatus)}`,
      action: "Rerun launch handoff verification and use only suggestedDispatchCommands after the guard reports safeToDispatch=true.",
      proofCommand: handoffCommand,
      expectedValue: "allDispatchReady=true; safeToDispatch=true before gh workflow run.",
      stopCondition: "If safeToDispatch=false, gh workflow run commands must stay withheld.",
      evidence: dispatchSignal.evidence || "",
    },
    {
      key: "launch_proof_capture",
      label: "Capture live launch proof after dispatch",
      status: proofPendingCount === 0 && proofRequiredCount > 0 ? "pass" : "deferred_until_dispatch",
      blockedSignal: `postPublishEvidenceReady=${yesNo(launchProofLedger?.postPublishEvidenceReady)}; proofReady=${proofReadyCount}/${proofRequiredCount}; pending=${proofPendingCount}`,
      action: "After guarded dispatch completes, capture Pages site proof, workflow run proof, freshness, release receipt, and public-claim guard evidence.",
      proofCommand: captureWriteCommand,
      expectedValue: "postPublishEvidenceReady=true; evidenceFresh=true; readyForExternalClaim=true only after live proof is saved.",
      stopCondition: "Do not post public launch copy, archive proof, or claim readyForExternalClaim until all launch proof fields are live and successful.",
      evidence: `deferredUntil=${valueOrPending(launchProofLedger?.deferredUntil || "safeToDispatch=true")}`,
    },
  ];
  const passCount = items.filter((item) => item.status === "pass" || item.status === "ready").length;
  const actionRequiredCount = items.filter((item) => item.status === "action_required").length;
  const deferredCount = items.filter((item) => item.status === "deferred_until_dispatch").length;
  const activeItem = items.find((item) => item.status === "action_required") || items.find((item) => item.status !== "pass" && item.status !== "ready") || null;
  const dispatchGuard = "Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.";
  return {
    source: "generated_from_launch_execution_packet",
    status: actionRequiredCount > 0 ? "action_required" : deferredCount > 0 ? "deferred_until_dispatch" : "pass",
    repo,
    currentStageKey: currentAction?.stageKey || "",
    activeItemKey: activeItem?.key || "",
    itemCount: items.length,
    passCount,
    actionRequiredCount,
    deferredCount,
    proofCommandCount: items.filter((item) => item.proofCommand).length,
    guard: dispatchGuard,
    dispatchGuard,
    items,
  };
}

function blockerResolutionChecklistLines(checklist) {
  const items = Array.isArray(checklist?.items) ? checklist.items : [];
  return [
    "Blocker resolution checklist:",
    `- source: ${valueOrPending(checklist?.source)}`,
    `- status: ${valueOrPending(checklist?.status)}`,
    `- active item: ${valueOrPending(checklist?.activeItemKey)}`,
    `- items: ${valueOrPending(checklist?.passCount)}/${valueOrPending(checklist?.itemCount)} pass; action_required=${valueOrPending(checklist?.actionRequiredCount)}; deferred=${valueOrPending(checklist?.deferredCount)}`,
    `- guard: ${valueOrPending(checklist?.dispatchGuard)}`,
    ...items.map((item) => `- ${valueOrPending(item.key)}: ${valueOrPending(item.status)}; action=${valueOrPending(item.action)}; proof command: ${valueOrPending(item.proofCommand)}; expectedValue=${valueOrPending(item.expectedValue)}; stopCondition=${valueOrPending(item.stopCondition)}; evidence=${valueOrPending(item.evidence || item.blockedSignal)}`),
  ];
}

function postInstallEvidenceIntakeLines(intake) {
  const fields = Array.isArray(intake?.fields) ? intake.fields : [];
  const commands = Array.isArray(intake?.commands) ? intake.commands : [];
  const signals = Array.isArray(intake?.expectedSignals) ? intake.expectedSignals : [];
  const sequence = Array.isArray(intake?.verificationSequence) ? intake.verificationSequence : [];
  const quickProofSteps = Array.isArray(intake?.quickProofSteps) ? intake.quickProofSteps : [];
  const quickProofFieldMappings = Array.isArray(intake?.quickProofFieldMappings) ? intake.quickProofFieldMappings : [];
  const verificationSequenceCount = numberOr(intake?.verificationSequenceCount, sequence.length);
  const quickProofStepCount = numberOr(intake?.quickProofStepCount, quickProofSteps.length);
  const quickProofMappedFieldCount = numberOr(intake?.quickProofMappedFieldCount, quickProofFieldMappings.length);
  return [
    "Post-install evidence intake:",
    `- source: ${valueOrPending(intake?.source)}`,
    `- status: ${valueOrPending(intake?.status)}`,
    `- proofComplete: ${yesNo(intake?.proofComplete)}; fields=${valueOrPending(intake?.completedFieldCount)}/${valueOrPending(intake?.fieldCount)} complete; coverage=${valueOrPending(intake?.fieldCoverage)}`,
    `- commands: ${valueOrPending(intake?.commandCount)}; signals=${valueOrPending(intake?.signalCount)}; checklist=${valueOrPending(intake?.checklistCount)}; sequence=${valueOrPending(verificationSequenceCount)}`,
    `- quick proof: ready=${yesNo(intake?.quickProofReady)}; steps=${valueOrPending(quickProofStepCount)}; coverage=${valueOrPending(intake?.quickProofCoverage)}`,
    `- quick proof field mapping: ready=${yesNo(intake?.quickProofFieldMappingReady)}; mapped=${valueOrPending(quickProofMappedFieldCount)}; completed=${valueOrPending(intake?.quickProofCompletedMappedFieldCount)}/${valueOrPending(quickProofMappedFieldCount)}; coverage=${valueOrPending(intake?.quickProofFieldMappingCoverage)}`,
    `- guard: ${valueOrPending(intake?.dispatchGuard)}`,
    `- ${valueOrPending(intake?.stopCondition)}`,
    ...(quickProofSteps.length ? quickProofSteps.map((step, index) => `- quick proof ${index + 1} ${valueOrPending(step.key)}: command=${valueOrPending(step.command)}; expected=${valueOrPending(step.expected)}; evidenceField=${valueOrPending(step.evidenceFieldKey)}`) : []),
    ...(quickProofFieldMappings.length ? quickProofFieldMappings.map((item, index) => `- quick proof field ${index + 1} ${valueOrPending(item.stepKey)} -> ${valueOrPending(item.fieldKey)}: ${valueOrPending(item.fieldStatus)}; completed=${yesNo(item.fieldCompleted)}; currentValue=${valueOrPending(item.currentValue)}; expectedValue=${valueOrPending(item.expectedValue)}; proofCommand=${valueOrPending(item.proofCommand)}; stopCondition=${valueOrPending(item.stopCondition)}`) : []),
    ...commands.map((command) => `- command: ${command}`),
    ...sequence.map((step, index) => `- sequence ${index + 1} ${valueOrPending(step.key)}: ${valueOrPending(step.label)}; command=${valueOrPending(step.command)}; expected=${valueOrPending(step.expected)}; guard=${valueOrPending(step.guard)}`),
    ...signals.map((signal) => `- expected signal: ${signal}`),
    ...fields.map((field) => `- field ${valueOrPending(field.key)}: ${valueOrPending(field.status)}; completed=${yesNo(field.completed)}; currentValue=${valueOrPending(field.currentValue)}; expectedValue=${valueOrPending(field.expectedValue)}; proofCommand=${valueOrPending(field.proofCommand)}; stopCondition=${valueOrPending(field.stopCondition)}`),
  ];
}

function stageTransitionLines(transition) {
  return [
    "Stage transition preview:",
    `- source: ${valueOrPending(transition?.source)}`,
    `- current: ${valueOrPending(transition?.currentStageKey)} (${valueOrPending(transition?.currentStageLabel)}) [${valueOrPending(transition?.currentStageStatus)}]`,
    `- next: ${valueOrPending(transition?.nextStageKey)} (${valueOrPending(transition?.nextStageLabel)}) [${valueOrPending(transition?.status)}]`,
    `- acceptance: ${valueOrPending(transition?.passAcceptanceCount)} pass; pending=${valueOrPending(transition?.pendingAcceptanceCount)}`,
    `- withheld dispatch commands: ${valueOrPending(transition?.withheldDispatchCommandCount)}`,
    `- gate command: ${valueOrPending(transition?.gateCommand)}`,
    `- required signals: ${Array.isArray(transition?.requiredSignals) ? transition.requiredSignals.join("; ") : "not available"}`,
    `- guard: ${valueOrPending(transition?.dispatchGuard)}`,
  ];
}

function workflowInstallVerificationMatrixLines(matrix) {
  return [
    "Workflow install verification matrix:",
    `- source: ${valueOrPending(matrix?.source)}`,
    `- status: ${valueOrPending(matrix?.status)}`,
    `- gate: ${valueOrPending(matrix?.currentStageKey)} -> ${valueOrPending(matrix?.nextStageKey)}`,
    `- install paths: ${valueOrPending(matrix?.installPathCount)}`,
    `- verification commands: ${valueOrPending(matrix?.verificationCommandCount)}`,
    `- required signals: ${Array.isArray(matrix?.requiredSignals) ? matrix.requiredSignals.join("; ") : "not available"}`,
    ...(Array.isArray(matrix?.matrixRows) ? matrix.matrixRows.map((row) => `- path ${valueOrPending(row.key)}: ${valueOrPending(row.status)}; first=${valueOrPending(row.firstCommand)}; verify=${Array.isArray(row.verificationCommands) ? row.verificationCommands.join(" | ") : "not available"}`) : []),
    ...(Array.isArray(matrix?.signalChecks) ? matrix.signalChecks.map((signal) => `- signal ${valueOrPending(signal.key)}: ${valueOrPending(signal.status)}; ${valueOrPending(signal.evidence)}`) : []),
    `- guard: ${valueOrPending(matrix?.dispatchGuard)}`,
  ];
}

function remoteWorkflowFileAcceptanceLedgerLines(ledger) {
  return [
    "Remote workflow file acceptance ledger:",
    `- source: ${valueOrPending(ledger?.source)}`,
    `- status: ${valueOrPending(ledger?.status)}`,
    `- files: ${valueOrPending(ledger?.readyCount)}/${valueOrPending(ledger?.fileCount)} ready; missing=${valueOrPending(ledger?.missingCount)}; mismatch=${valueOrPending(ledger?.mismatchCount)}; notChecked=${valueOrPending(ledger?.notCheckedCount)}`,
    `- verify: ${valueOrPending(ledger?.verifyCommand)}`,
    `- install: ${valueOrPending(ledger?.installCommand)}`,
    `- required signals: ${Array.isArray(ledger?.requiredSignals) ? ledger.requiredSignals.join("; ") : "not available"}`,
    ...(Array.isArray(ledger?.files) ? ledger.files.map((file) => `- file ${valueOrPending(file.key)}: ${valueOrPending(file.status)}; installAction=${valueOrPending(file.installAction)}; path=${valueOrPending(file.path)}; templateSha256=${valueOrPending(file.templateSha256)}; remoteSha256=${valueOrPending(file.remoteSha256)}; evidence=${valueOrPending(file.evidence)}; copy=${valueOrPending(file.templateCopyCommand)}; open=${valueOrPending(file.openCommand || (file.installAction === "verified_remote_matches_template" ? "No GitHub file edit required" : file.githubNewFileOpenCommand))}`) : []),
  ];
}

function launchProofAcceptanceLedgerLines(ledger) {
  return [
    "Launch proof acceptance ledger:",
    `- source: ${valueOrPending(ledger?.source)}`,
    `- status: ${valueOrPending(ledger?.status)}`,
    `- current gate: ${valueOrPending(ledger?.currentGate)} [${valueOrPending(ledger?.currentGateStatus)}]`,
    `- deferred until: ${valueOrPending(ledger?.deferredUntil)}`,
    `- proof readiness: ${valueOrPending(ledger?.readyProofCount)}/${valueOrPending(ledger?.requiredProofCount)} ready; pending=${valueOrPending(ledger?.pendingProofCount)}`,
    `- capture markdown: ${valueOrPending(ledger?.captureMarkdownCommand)}`,
    `- capture write: ${valueOrPending(ledger?.captureWriteCommand)}`,
    ...(Array.isArray(ledger?.requiredProofs) ? ledger.requiredProofs.map((proof) => `- proof ${valueOrPending(proof.key)}: ${valueOrPending(proof.status)}; required=${valueOrPending(proof.required)} Evidence: ${valueOrPending(proof.evidence)} Command: ${valueOrPending(proof.command)}`) : []),
    ...(Array.isArray(ledger?.externalProofBaseline) ? ledger.externalProofBaseline.map((item) => `- external baseline ${valueOrPending(item.key)}: ${valueOrPending(item.label)}; fields=${Array.isArray(item.requiredFields) ? item.requiredFields.join(", ") : "not available"}; command=${valueOrPending(item.command)}`) : []),
  ];
}

function packetText({ generatedAt, repo, defaultBranch, stages, currentAction, operatorOnePage, stageTransition, blockerResolution, postInstallIntake, workflowInstallMatrix, remoteWorkflowFileLedger, launchProofLedger, authPreflight, postAuthCheckpoint, blockers, comparisons }) {
  const lines = [
    "JooPark Launch Execution Packet",
    `Status: ${blockers.length ? "action required - launch proof not complete" : "ready"}`,
    `Generated: ${generatedAt}`,
    `Repo: ${repo}`,
    `Default branch: ${valueOrPending(defaultBranch)}`,
    "",
    "Guard:",
    "- Do not run dispatch commands until allDispatchReady: true.",
    "- Do not publish a public launch claim until postPublishEvidenceReady: true and readyForExternalClaim: true.",
    "",
    "Operator one-page handoff:",
    operatorOnePage?.text || "not available",
    "",
    ...authPreflightLines(authPreflight),
    "",
    ...postAuthCheckpointLines(postAuthCheckpoint),
    "",
    "Current action packet:",
    currentAction.packet,
    "",
    ...stageTransitionLines(stageTransition),
    "",
    ...blockerResolutionChecklistLines(blockerResolution),
    "",
    ...postInstallEvidenceIntakeLines(postInstallIntake),
    "",
    ...workflowInstallVerificationMatrixLines(workflowInstallMatrix),
    "",
    ...remoteWorkflowFileAcceptanceLedgerLines(remoteWorkflowFileLedger),
    "",
    ...launchProofAcceptanceLedgerLines(launchProofLedger),
    "",
    "Execution stages:",
  ];
  stages.forEach((stage, index) => {
    lines.push(`${index + 1}. ${stage.label} [${stage.status}]`);
    lines.push(`   Detail: ${stage.detail}`);
    if (stage.commands.length) {
      lines.push("   Commands:");
      stage.commands.forEach((command) => lines.push(`   - ${command}`));
    }
    if (stage.evidence.length) {
      lines.push("   Evidence:");
      stage.evidence.forEach((item) => lines.push(`   - ${item}`));
    }
  });
  lines.push("");
  lines.push("External comparison:");
  comparisons.forEach((item) => lines.push(`- ${item.label}: ${item.detail} Source: ${item.url}`));
  lines.push("");
  lines.push("Blockers:");
  (blockers.length ? blockers : ["none"]).forEach((blocker) => lines.push(`- ${blocker}`));
  return lines.join("\n");
}

const workflowUiInstallPlan = readJson("data/workflow-ui-install-plan.json", {}) || {};
const publishDispatchPlan = readJson("data/publish-dispatch-plan.json", {}) || {};
const remoteWorkflowFileCheck = readJson("data/remote-workflow-file-check.json", {}) || {};
const publishEvidence = readJson("data/publish-evidence.json", {}) || {};
const outputQualityAudit = readJson("data/output-quality-audit.json", {}) || {};
const generatedAt = new Date().toISOString();
const repo = publishDispatchPlan?.repo || publishEvidence?.suggestedRepo || workflowUiInstallPlan?.suggestedRepo || "OWNER/REPO";
const defaultBranch = publishDispatchPlan?.defaultBranch || workflowUiInstallPlan?.defaultBranch || "main";
const authPreflight = workflowAuthPreflight(publishDispatchPlan, repo);
const postAuthCheckpoint = buildPostAuthCheckpoint({ repo, authPreflight, publishDispatchPlan, remoteWorkflowFileCheck });
const stages = stageList({ workflowUiInstallPlan, publishDispatchPlan, remoteWorkflowFileCheck, publishEvidence, outputQualityAudit });
const blockers = blockerLines({ publishDispatchPlan, remoteWorkflowFileCheck, publishEvidence, stages });
const comparisons = externalComparison();
const currentAction = currentActionPacket({ repo, defaultBranch, stages, remoteWorkflowFileCheck, publishDispatchPlan, authPreflight, postAuthCheckpoint });
const commandCount = stages.reduce((sum, stage) => sum + stage.commands.length, 0);
const readyToDispatch = workflowDispatchReady({ publishDispatchPlan, remoteWorkflowFileCheck });
const readyForExternalClaim = launchPacketReadyForExternalClaim({ publishEvidence, outputQualityAudit, publishDispatchPlan, remoteWorkflowFileCheck });
const stageTransition = stageTransitionPreview({ stages, currentAction, postAuthCheckpoint, readyToDispatch });
const workflowInstallMatrix = workflowInstallVerificationMatrix({ repo, defaultBranch, stages, currentAction, authPreflight, postAuthCheckpoint, publishDispatchPlan, remoteWorkflowFileCheck });
const remoteWorkflowFileLedger = remoteWorkflowFileAcceptanceLedger({ repo, defaultBranch, workflowUiInstallPlan, remoteWorkflowFileCheck, postAuthCheckpoint });
const launchProofLedger = launchProofAcceptanceLedger({ repo, stages, publishEvidence, publishDispatchPlan, remoteWorkflowFileCheck, outputQualityAudit });
const blockerResolution = blockerResolutionChecklist({ repo, currentAction, workflowInstallMatrix, remoteWorkflowFileLedger, launchProofLedger, authPreflight, postAuthCheckpoint, publishDispatchPlan, remoteWorkflowFileCheck });
const postInstallIntake = postInstallEvidenceIntake({ repo, defaultBranch, remoteWorkflowFileLedger, publishDispatchPlan, postAuthCheckpoint, blockerResolution });
const operatorOnePage = operatorOnePageHandoff({ generatedAt, repo, defaultBranch, currentAction, blockerResolution, postInstallIntake, workflowInstallMatrix, remoteWorkflowFileLedger, launchProofLedger, authPreflight, postAuthCheckpoint });
const payload = {
  status: "pass",
  generatedAt,
  source: "data/workflow-ui-install-plan.json + data/publish-dispatch-plan.json + data/remote-workflow-file-check.json + data/publish-evidence.json + data/output-quality-audit.json",
  repo,
  suggestedRepo: publishEvidence?.suggestedRepo || workflowUiInstallPlan?.suggestedRepo || "",
  defaultBranch,
  readyToDispatch,
  remoteWorkflowFilesReady: !!remoteWorkflowFileCheck?.remoteWorkflowFilesReady,
  authPreflight,
  postAuthCheckpoint,
  launchProofReady: !!publishEvidence?.postPublishEvidenceReady,
  readyForExternalClaim,
  stageCount: stages.length,
  commandCount,
  currentAction,
  operatorOnePageHandoff: operatorOnePage,
  stageTransitionPreview: stageTransition,
  blockerResolutionChecklist: blockerResolution,
  postInstallEvidenceIntake: postInstallIntake,
  workflowInstallVerificationMatrix: workflowInstallMatrix,
  remoteWorkflowFileAcceptanceLedger: remoteWorkflowFileLedger,
  launchProofAcceptanceLedger: launchProofLedger,
  stages,
  externalComparison: comparisons,
  blockers,
};
payload.packet = packetText({ generatedAt, repo, defaultBranch, stages, currentAction, operatorOnePage, stageTransition, blockerResolution, postInstallIntake, workflowInstallMatrix, remoteWorkflowFileLedger, launchProofLedger, authPreflight, postAuthCheckpoint, blockers, comparisons });

if (write) {
  const outPath = resolve(root, outRel);
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

if (markdown) {
  console.log(["# JooPark Launch Execution Packet", "", "```text", payload.packet, "```"].join("\n"));
} else {
  console.log(JSON.stringify(payload, null, 2));
}
