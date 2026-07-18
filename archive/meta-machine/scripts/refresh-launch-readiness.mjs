#!/usr/bin/env node

import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const write = rawArgs.includes("--write");
const markdown = rawArgs.includes("--markdown");
const repo = argValue("--repo") || currentRepo() || suggestedRepoFromRemote() || "OWNER/REPO";
const outJsonRel = argValue("--out-json") || "data/launch-readiness-refresh.json";
const outMarkdownRel = argValue("--out-markdown") || "data/launch-readiness-refresh.md";
const evidenceMaxAgeHours = positiveNumber(process.env.LAUNCH_READINESS_MAX_AGE_HOURS, 24);

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

function currentRepo() {
  try {
    const output = execFileSync("gh", ["repo", "view", "--json", "nameWithOwner"], {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    const payload = JSON.parse(output || "{}");
    return payload?.nameWithOwner || "";
  } catch {
    return "";
  }
}

function readJson(relPath, fallback = {}) {
  try {
    return JSON.parse(readFileSync(resolve(root, relPath), "utf-8"));
  } catch {
    return fallback;
  }
}

function writeText(relPath, text) {
  const target = resolve(root, relPath);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, text, "utf-8");
}

function runNode(script, scriptArgs) {
  const command = ["node", script, ...scriptArgs].join(" ");
  const result = spawnSync(process.execPath, [script, ...scriptArgs], {
    cwd: root,
    encoding: "utf-8",
    maxBuffer: 40 * 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let json = null;
  try {
    json = result.stdout ? JSON.parse(result.stdout) : null;
  } catch {
    json = null;
  }
  return {
    command,
    status: result.status === 0 ? "pass" : "fail",
    code: result.status,
    json,
    stdout: String(result.stdout || "").slice(0, 1200),
    stderr: String(result.stderr || "").slice(0, 1200),
  };
}

function yesNo(value) {
  return value ? "true" : "false";
}

function valueOrPending(value) {
  if (value === true) return "true";
  if (value === false) return "false";
  if (value === null || value === undefined || value === "") return "not available";
  return String(value);
}

function gateSummary(gate) {
  const checks = gate?.checks || {};
  return `${Number(checks.pass || 0)} pass, ${Number(checks.fail || 0)} fail, ${Number(checks.notRun || 0)} not_run, ${Number(checks.blocked || 0)} blocked`;
}

function positiveNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function finiteNumberOr(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function checklistItem(key, label, ready, evidence, command = "") {
  return {
    key,
    label,
    status: ready ? "pass" : "action_required",
    evidence,
    command,
  };
}

function remoteWorkflowRepairAction(remoteWorkflowFileCheck) {
  const checks = Array.isArray(remoteWorkflowFileCheck?.checks) ? remoteWorkflowFileCheck.checks : [];
  const target = checks.find((check) => check?.remediation?.status === "action_required") ||
    checks.find((check) => check?.installAction && check.installAction !== "verified_remote_matches_template") ||
    checks.find((check) => check?.remoteMatchesTemplate === false);
  if (!target) return null;
  const remediation = target.remediation || {};
  const installAction = target.installAction || remediation.installAction || "repair_remote_workflow_file";
  const copyCommand = target.templateCopyCommand || remediation.templateCopyCommand || "";
  const editCommand = target.githubEditFileOpenCommand || remediation.githubEditFileOpenCommand || "";
  const newFileCommand = target.githubNewFileOpenCommand || remediation.githubNewFileOpenCommand || "";
  const openCommand = installAction === "replace_existing_remote_file" ? editCommand || newFileCommand : newFileCommand || editCommand;
  const command = copyCommand && openCommand
    ? `${copyCommand} && ${openCommand}`
    : openCommand || copyCommand || remoteWorkflowFileCheck?.nextVerificationCommand || "";
  return {
    key: target.key || "",
    label: target.name || target.path || "Remote workflow repair",
    installAction,
    command,
    copyCommand,
    openCommand,
    templatePath: target.template || remediation.templatePath || "",
    targetPath: target.path || remediation.targetPath || "",
    remoteBlobSha: target.remoteBlobSha || remediation.remoteBlobSha || target.githubBlobSha || "",
    githubEditFileUrl: target.githubEditFileUrl || remediation.githubEditFileUrl || "",
    githubNewFileUrl: target.githubNewFileUrl || remediation.githubNewFileUrl || "",
    nextStep: remediation.nextStep || "Repair the remote workflow file, then rerun the remote workflow file check.",
  };
}

const commandRuns = [
  runNode("scripts/plan-workflow-ui-install.mjs", ["--dry-run", "--write"]),
  runNode("scripts/check-remote-workflow-files.mjs", ["--repo", repo, "--write"]),
  runNode("scripts/plan-publish-dispatch.mjs", ["--live", "--repo", repo, "--write"]),
  runNode("scripts/capture-launch-execution-packet.mjs", ["--write"]),
  runNode("scripts/verify-launch-handoff.mjs", ["--repo", repo, "--write"]),
  runNode("scripts/capture-output-quality-audit.mjs", ["--write"]),
];

const workflowUiInstallPlan = commandRuns[0].json || readJson("data/workflow-ui-install-plan.json", {});
const remoteWorkflowFileCheck = commandRuns[1].json || readJson("data/remote-workflow-file-check.json", {});
const publishDispatchPlan = commandRuns[2].json || readJson("data/publish-dispatch-plan.json", {});
const launchExecutionPacket = commandRuns[3].json || readJson("data/launch-execution-packet.json", {});
const launchHandoffVerification = commandRuns[4].json || readJson("data/launch-handoff-verification.json", {});
const outputQualityAudit = commandRuns[5].json || readJson("data/output-quality-audit.json", {});

const remoteWorkflowFilesReady = remoteWorkflowFileCheck.remoteWorkflowFilesReady === true;
const remoteWorkflowVisibilityReady = publishDispatchPlan.remoteWorkflowVisibilityReady === true;
const allDispatchReady = publishDispatchPlan.allDispatchReady === true;
const safeToDispatch = launchHandoffVerification.safeToDispatch === true;
const workflowScopeAvailable = publishDispatchPlan.workflowScopeAvailable === true || publishDispatchPlan.workflowScope?.available === true;
const workflowScopeInstallBlocked = publishDispatchPlan.workflowScopeInstallBlocked === true;
const releaseQualityReady = outputQualityAudit.releaseQualityReady === true;
const publicLaunchProofReady = outputQualityAudit.publicLaunchProofReady === true;
const readyForExternalClaim = outputQualityAudit.readyForExternalClaim === true;
const outputQualityLatestGate = outputQualityAudit.latestGate && typeof outputQualityAudit.latestGate === "object"
  ? {
      command: outputQualityAudit.latestGate.command || "npm run verify",
      status: outputQualityAudit.latestGate.status || "unknown",
      checks: outputQualityAudit.latestGate.checks || { pass: 0, fail: 0, notRun: 0, blocked: 0, total: 0 },
      generatedAt: outputQualityAudit.generatedAt || "",
      source: "data/output-quality-audit.json",
      sourceInputCount: Number(outputQualityAudit.sourceInputCount || 0),
    }
  : null;
const outputQualityGateTraceabilityReady = !!(
  outputQualityLatestGate &&
  outputQualityLatestGate.status === "pass" &&
  Number(outputQualityLatestGate.checks.fail || 0) === 0 &&
  Number(outputQualityLatestGate.checks.notRun || 0) === 0 &&
  Number(outputQualityLatestGate.checks.blocked || 0) === 0 &&
  outputQualityLatestGate.sourceInputCount > 0
);
const generatedAt = new Date().toISOString();
const refreshDispatchGuard = "Do not run gh workflow run until every action_required refresh checklist item has passed and verify-launch-handoff reports safeToDispatch=true.";
const refreshExternalClaimGuard = "Do not run gh workflow run, archive proof, or claim readyForExternalClaim until every action_required refresh checklist item has passed, verify-launch-handoff reports safeToDispatch=true, postPublishEvidenceReady=true, and readyForExternalClaim=true.";
const evidenceExpiresAt = new Date(Date.parse(generatedAt) + evidenceMaxAgeHours * 60 * 60 * 1000).toISOString();
const withheldDispatchCommands = Array.isArray(launchHandoffVerification.withheldDispatchCommands)
  ? launchHandoffVerification.withheldDispatchCommands
  : Array.isArray(publishDispatchPlan.withheldDispatchCommands) ? publishDispatchPlan.withheldDispatchCommands : [];
const publishSuggestedDispatchCommands = Array.isArray(publishDispatchPlan.suggestedDispatchCommands)
  ? publishDispatchPlan.suggestedDispatchCommands
  : [];
const suggestedDispatchCommands = safeToDispatch ? publishSuggestedDispatchCommands : [];
const dispatchCommandDisposition = readyForExternalClaim
  ? "not_applicable_after_launch_proof"
  : safeToDispatch ? "active" : "withheld";
const activeDispatchCommands = dispatchCommandDisposition === "active" ? suggestedDispatchCommands : [];
const dispatchCommandReferenceCount = dispatchCommandDisposition === "withheld"
  ? withheldDispatchCommands.length
  : publishSuggestedDispatchCommands.length;
const remoteWorkflowRepair = remoteWorkflowRepairAction(remoteWorkflowFileCheck);
const blockers = unique([
  ...commandRuns.filter((run) => run.status !== "pass").map((run) => `${run.command}: ${run.stderr || "failed"}`),
  ...(Array.isArray(launchHandoffVerification.blockers) ? launchHandoffVerification.blockers : []),
  workflowScopeInstallBlocked ? `workflowScopeInstallBlocked=true; run ${publishDispatchPlan.workflowScopeRefreshCommand || "gh auth refresh -h github.com -s workflow"}` : "",
  !remoteWorkflowFilesReady ? "remoteWorkflowFilesReady=false" : "",
  !remoteWorkflowVisibilityReady ? "remoteWorkflowVisibilityReady=false" : "",
  !allDispatchReady ? "allDispatchReady=false" : "",
  !publicLaunchProofReady ? "postPublishEvidenceReady=false" : "",
  !readyForExternalClaim ? "readyForExternalClaim=false" : "",
]);
const refreshChecklist = [
  checklistItem(
    "workflow_ui_install_plan",
    "Workflow UI install plan",
    workflowUiInstallPlan.status === "pass" && workflowUiInstallPlan.workflowUiInstallReady === true,
    `workflowUiInstallReady=${yesNo(workflowUiInstallPlan.workflowUiInstallReady)}; localTargetParityReady=${yesNo(workflowUiInstallPlan.localTargetParityReady)}`,
    "node scripts/plan-workflow-ui-install.mjs --dry-run --write",
  ),
  checklistItem(
    "remote_workflow_files",
    "Remote workflow files",
    remoteWorkflowFilesReady,
    `remoteWorkflowFilesReady=${yesNo(remoteWorkflowFilesReady)}`,
    `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`,
  ),
  checklistItem(
    "workflow_visibility",
    "Workflow visibility and dispatch plan",
    remoteWorkflowVisibilityReady && allDispatchReady,
    `remoteWorkflowVisibilityReady=${yesNo(remoteWorkflowVisibilityReady)}; allDispatchReady=${yesNo(allDispatchReady)}`,
    `node scripts/plan-publish-dispatch.mjs --live --repo ${repo} --write`,
  ),
  checklistItem(
    "handoff_verifier",
    "Launch handoff verifier",
    launchHandoffVerification.status === "pass",
    `safeToDispatch=${yesNo(safeToDispatch)}; artifactCoverage=${valueOrPending(launchHandoffVerification.verificationArtifact?.artifactCoverage)}`,
    `node scripts/verify-launch-handoff.mjs --repo ${repo} --write`,
  ),
  checklistItem(
    "output_quality",
    "Output quality audit",
    releaseQualityReady,
    `releaseQualityReady=${yesNo(releaseQualityReady)}; publicLaunchProofReady=${yesNo(publicLaunchProofReady)}`,
    "node scripts/capture-output-quality-audit.mjs --write",
  ),
  checklistItem(
    "external_claim",
    "External completion claim",
    readyForExternalClaim,
    `readyForExternalClaim=${yesNo(readyForExternalClaim)}`,
    `node scripts/capture-publish-evidence.mjs --live --repo ${repo} --write`,
  ),
];

const nextAction = readyForExternalClaim
  ? {
      key: "share_launch_proof",
      status: "ready",
      command: `node scripts/capture-publish-evidence.mjs --live --repo ${repo} --markdown`,
      detail: "Live launch proof is fresh, workflows succeeded, and readyForExternalClaim=true.",
    }
  : safeToDispatch
  ? {
      key: "dispatch_workflows",
      status: "ready",
      command: suggestedDispatchCommands[0] || "",
      detail: "Run only suggested dispatch commands, then capture live publish evidence.",
    }
  : {
      key: workflowScopeInstallBlocked ? "refresh_workflow_scope_or_use_github_ui" : "install_workflows",
      status: "action_required",
      command: workflowScopeInstallBlocked
        ? publishDispatchPlan.workflowScopeRefreshCommand || "gh auth refresh -h github.com -s workflow"
        : remoteWorkflowRepair?.command || remoteWorkflowFileCheck.nextVerificationCommand || `node scripts/check-remote-workflow-files.mjs --repo ${repo} --write`,
      detail: remoteWorkflowRepair
        ? `${remoteWorkflowRepair.installAction}: ${remoteWorkflowRepair.nextStep} ${refreshDispatchGuard}`
        : refreshDispatchGuard,
    };
const sourceArtifacts = [
  ["workflow_ui_install_plan", "data/workflow-ui-install-plan.json", commandRuns[0]],
  ["remote_workflow_file_check", "data/remote-workflow-file-check.json", commandRuns[1]],
  ["publish_dispatch_plan", "data/publish-dispatch-plan.json", commandRuns[2]],
  ["launch_execution_packet", "data/launch-execution-packet.json", commandRuns[3]],
  ["launch_handoff_verification", "data/launch-handoff-verification.json", commandRuns[4]],
  ["output_quality_audit", "data/output-quality-audit.json", commandRuns[5]],
].map(([key, path, run]) => ({
  key,
  path,
  command: run?.command || "",
  status: run?.status || "missing",
  refreshedAt: generatedAt,
}));
const evidenceFreshness = {
  status: "fresh",
  generatedAt,
  expiresAt: evidenceExpiresAt,
  maxAgeHours: evidenceMaxAgeHours,
  refreshRequired: false,
  sourceArtifactCount: sourceArtifacts.length,
  sourceArtifacts,
  policy: "Rerun npm run refresh:launch-readiness before workflow dispatch, live publish proof capture, or external completion claim when this artifact is stale.",
};
const sourceArtifactSync = {
  status: outputQualityAudit.generatedAt ? "pass" : "fail",
  primaryMetric: "launchReadinessSourceArtifactSyncCoverage",
  baseline: 0,
  candidate: outputQualityAudit.generatedAt ? 1 : 0,
  decision: outputQualityAudit.generatedAt ? "keep" : "reject",
  outputQualityGeneratedAt: outputQualityAudit.generatedAt || "",
  latestGateGeneratedAt: outputQualityLatestGate?.generatedAt || "",
  source: "data/output-quality-audit.json",
  evidence: outputQualityAudit.generatedAt
    ? `launch readiness embedded outputQualityGeneratedAt=${outputQualityAudit.generatedAt}`
    : "output quality generatedAt missing",
};

const payload = {
  status: commandRuns.every((run) => run.status === "pass") ? "pass" : "fail",
  mode: write ? "write" : "check",
  generatedAt,
  decision: "keep_b",
  sourceArtifactCount: sourceArtifacts.length,
  evidenceFreshnessStatus: evidenceFreshness.status,
  evidenceMaxAgeHours,
  evidenceExpiresAt,
  evidenceFreshness,
  sourceArtifactSync,
  repo,
  source: outJsonRel,
  write,
  dispatchExecuted: false,
  launchProofCaptured: false,
  commandCoverage: commandRuns.length,
  commandRuns: commandRuns.map((run) => ({ command: run.command, status: run.status, code: run.code, error: run.stderr || "" })),
  outputQualityGeneratedAt: outputQualityAudit.generatedAt || "",
  outputQualitySourceInputCount: Number(outputQualityAudit.sourceInputCount || 0),
  latestGate: outputQualityLatestGate,
  latestGateSummary: outputQualityLatestGate ? gateSummary(outputQualityLatestGate) : "not available",
  outputQualityGateTraceability: {
    ready: outputQualityGateTraceabilityReady,
    status: outputQualityGateTraceabilityReady ? "pass" : "fail",
    primaryMetric: "launchReadinessOutputQualityGateTraceability",
    baseline: 0,
    candidate: outputQualityGateTraceabilityReady ? 1 : 0,
    decision: outputQualityGateTraceabilityReady ? "keep" : "reject",
    source: "data/output-quality-audit.json",
    evidence: outputQualityLatestGate
      ? `${outputQualityLatestGate.command} -> ${gateSummary(outputQualityLatestGate)}; sourceInputCount=${outputQualityLatestGate.sourceInputCount}; generatedAt=${outputQualityLatestGate.generatedAt || "not available"}`
      : "output quality latest gate missing",
    externalComparison: "GitHub Actions job summaries surface important run results on the workflow summary page so readers do not need to inspect raw logs; this receipt mirrors that pattern by carrying the latest gate summary in the operator handoff.",
  },
  abComparison: {
    status: "pass",
    baseline: "manual_multi_command_refresh",
    candidate: "single_launch_readiness_refresh_runner",
    decision: "keep_b",
    primaryMetric: "operator_refresh_command_count",
    baselineCommandCount: 6,
    candidateCommandCount: 1,
  },
  workflowScopeAvailable,
  workflowScopeInstallBlocked,
  remoteWorkflowFilesReady,
  remoteWorkflowVisibilityReady,
  allDispatchReady,
  safeToDispatch,
  releaseQualityReady,
  publicLaunchProofReady,
  readyForExternalClaim,
  withheldDispatchCommandCount: withheldDispatchCommands.length,
  suggestedDispatchCommandCount: suggestedDispatchCommands.length,
  dispatchCommandReferenceCount,
  activeDispatchCommandCount: activeDispatchCommands.length,
  activeDispatchCommands,
  dispatchCommandDisposition,
  suggestedDispatchCommands,
  withheldDispatchCommands,
  remoteWorkflowRepairAction: remoteWorkflowRepair,
  nextAction,
  refreshChecklist,
  blockers,
  guard: refreshExternalClaimGuard,
  artifacts: {
    workflowUiInstallPlan: "data/workflow-ui-install-plan.json",
    remoteWorkflowFileCheck: "data/remote-workflow-file-check.json",
    publishDispatchPlan: "data/publish-dispatch-plan.json",
    launchExecutionPacket: "data/launch-execution-packet.json",
    launchHandoffVerification: "data/launch-handoff-verification.json",
    launchHandoffMarkdown: "data/launch-handoff-verification.md",
    outputQualityAudit: "data/output-quality-audit.json",
    refreshJson: write ? outJsonRel : "",
    refreshMarkdown: write ? outMarkdownRel : "",
  },
};

function markdownLines(data) {
  return [
    "# JooPark Launch Readiness Refresh",
    "",
    `- status: ${data.status}`,
    `- repo: ${data.repo}`,
    `- generatedAt: ${data.generatedAt}`,
    `- evidenceFreshness: ${data.evidenceFreshnessStatus}`,
    `- evidenceExpiresAt: ${data.evidenceExpiresAt}`,
    `- refreshRequired: ${yesNo(data.evidenceFreshness?.refreshRequired)}`,
    `- commandCoverage: ${data.commandCoverage}`,
    `- decision: ${data.decision || data.abComparison?.decision || "not checked"}`,
    `- sourceArtifactCount: ${data.sourceArtifactCount || data.evidenceFreshness?.sourceArtifactCount || 0}`,
    `- sourceArtifactSync: ${data.sourceArtifactSync?.status || "missing"}`,
    `- outputQualityGeneratedAt: ${data.outputQualityGeneratedAt || "not available"}`,
    `- outputQualitySourceInputCount: ${data.outputQualitySourceInputCount || 0}`,
    `- latestGate: ${data.latestGate?.command || "not available"} -> ${data.latestGateSummary || "not available"}`,
    `- workflowScopeAvailable: ${yesNo(data.workflowScopeAvailable)}`,
    `- workflowScopeInstallBlocked: ${yesNo(data.workflowScopeInstallBlocked)}`,
    `- remoteWorkflowFilesReady: ${yesNo(data.remoteWorkflowFilesReady)}`,
    `- remoteWorkflowVisibilityReady: ${yesNo(data.remoteWorkflowVisibilityReady)}`,
    `- allDispatchReady: ${yesNo(data.allDispatchReady)}`,
    `- safeToDispatch: ${yesNo(data.safeToDispatch)}`,
    `- readyForExternalClaim: ${yesNo(data.readyForExternalClaim)}`,
    `- dispatchCommandDisposition: ${data.dispatchCommandDisposition || "withheld"}`,
    `- activeDispatchCommandCount: ${finiteNumberOr(data.activeDispatchCommandCount, 0)}`,
    `- dispatchCommandReferenceCount: ${finiteNumberOr(data.dispatchCommandReferenceCount, finiteNumberOr(data.suggestedDispatchCommandCount, 0))}`,
    `- guard: ${data.guard}`,
    "",
    "## A/B Decision",
    `- baseline: ${data.abComparison.baseline} (${data.abComparison.baselineCommandCount} commands)`,
    `- candidate: ${data.abComparison.candidate} (${data.abComparison.candidateCommandCount} command)`,
    `- decision: ${data.abComparison.decision}`,
    "",
    "## Output Quality Gate Traceability",
    `- status: ${data.outputQualityGateTraceability?.status || "missing"}`,
    `- primaryMetric: ${data.outputQualityGateTraceability?.primaryMetric || "not available"}`,
    `- candidate: ${data.outputQualityGateTraceability?.candidate ?? "not available"}`,
    `- evidence: ${data.outputQualityGateTraceability?.evidence || "not available"}`,
    "",
    "## Evidence Freshness",
    `- freshness: ${data.evidenceFreshness?.status || "missing"}`,
    `- maxAgeHours: ${data.evidenceMaxAgeHours}`,
    `- expiresAt: ${data.evidenceExpiresAt}`,
    `- refreshRequired: ${yesNo(data.evidenceFreshness?.refreshRequired)}`,
    `- sourceArtifactCount: ${data.evidenceFreshness?.sourceArtifactCount || 0}`,
    `- sourceArtifactSync: ${data.sourceArtifactSync?.status || "missing"}`,
    `- sourceArtifactSyncOutputQualityGeneratedAt: ${data.sourceArtifactSync?.outputQualityGeneratedAt || "not available"}`,
    `- policy: ${data.evidenceFreshness?.policy || "Rerun before dispatch or external claim."}`,
    ...(Array.isArray(data.evidenceFreshness?.sourceArtifacts) ? data.evidenceFreshness.sourceArtifacts.map((item) => `- ${item.key}: ${item.status} - ${item.path}`) : []),
    "",
    "## Refresh Checklist",
    ...data.refreshChecklist.map((item) => `- ${item.label}: ${item.status} - ${item.evidence}; command=${item.command}`),
    "",
    "## Remote Workflow Repair Action",
    `- installAction: ${data.remoteWorkflowRepairAction?.installAction || "not required"}`,
    `- target: ${data.remoteWorkflowRepairAction?.targetPath || "not available"}`,
    `- command: ${data.remoteWorkflowRepairAction?.command || "not available"}`,
    `- remoteBlobSha: ${data.remoteWorkflowRepairAction?.remoteBlobSha || "not available"}`,
    `- githubEditFileUrl: ${data.remoteWorkflowRepairAction?.githubEditFileUrl || "not available"}`,
    "",
    "## Commands Run",
    ...data.commandRuns.map((run) => `- ${run.status}: \`${run.command}\``),
    "",
    "## Next Action",
    `- ${data.nextAction.key}: ${data.nextAction.status} - ${data.nextAction.detail}`,
    `- command: ${data.nextAction.command || "not available"}`,
    "",
    "## Blockers",
    ...(data.blockers.length ? data.blockers.map((blocker) => `- ${blocker}`) : ["- none"]),
  ];
}

const markdownText = markdownLines(payload).join("\n");
if (write) {
  writeText(outJsonRel, `${JSON.stringify(payload, null, 2)}\n`);
  writeText(outMarkdownRel, `${markdownText}\n`);
}

if (markdown) console.log(markdownText);
else console.log(JSON.stringify(payload, null, 2));

if (payload.status !== "pass") process.exit(1);
