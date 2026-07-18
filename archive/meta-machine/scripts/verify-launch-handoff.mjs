#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const args = new Set(rawArgs);
const write = args.has("--write");
const markdown = args.has("--markdown");
const repo = argValue("--repo") || readRepo() || "OWNER/REPO";
const repoEvidenceReady = repo && repo !== "OWNER/REPO";
const outJsonRel = argValue("--out-json") || "data/launch-handoff-verification.json";
const outMarkdownRel = argValue("--out-markdown") || "data/launch-handoff-verification.md";
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

function readJson(path, fallback = {}) {
  try {
    return JSON.parse(readFileSync(resolve(root, path), "utf-8"));
  } catch {
    return fallback;
  }
}

function writeText(path, text) {
  const target = resolve(root, path);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, text, "utf-8");
}

function readRepo() {
  const publishDispatchPlan = readJson("data/publish-dispatch-plan.json", {});
  const publishEvidence = readJson("data/publish-evidence.json", {});
  return publishDispatchPlan.repo || publishEvidence.suggestedRepo || publishEvidence.displayRepo || "";
}

function runNode(script, scriptArgs) {
  const command = ["node", script, ...scriptArgs].join(" ");
  try {
    const stdout = execFileSync("node", [script, ...scriptArgs], {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    return {
      command,
      status: "pass",
      stdout,
      json: JSON.parse(stdout || "{}"),
    };
  } catch (error) {
    return {
      command,
      status: "fail",
      stdout: String(error?.stdout || ""),
      stderr: String(error?.stderr || error?.message || error).slice(0, 1000),
      json: null,
    };
  }
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

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function numberOr(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function blockerResolutionSummary(checklist) {
  const source = checklist && typeof checklist === "object" ? checklist : {};
  const items = Array.isArray(source.items) ? source.items : [];
  return {
    source: source.source || "not_available",
    status: source.status || "not_available",
    activeItemKey: source.activeItemKey || "",
    itemCount: numberOr(source.itemCount, items.length),
    passCount: numberOr(source.passCount, items.filter((item) => item.status === "pass" || item.status === "ready").length),
    actionRequiredCount: numberOr(source.actionRequiredCount, items.filter((item) => item.status === "action_required").length),
    deferredCount: numberOr(source.deferredCount, items.filter((item) => String(item.status || "").includes("deferred")).length),
    proofCommandCount: numberOr(source.proofCommandCount, items.filter((item) => item.proofCommand).length),
    dispatchGuard: source.dispatchGuard || "Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.",
    items,
  };
}

function postInstallEvidenceIntakeSummary(intake) {
  const source = intake && typeof intake === "object" ? intake : {};
  const fields = Array.isArray(source.fields)
    ? source.fields
    : Array.isArray(source.fieldItems) ? source.fieldItems : [];
  const defaultFieldKeys = [
    "pages_workflow_commit",
    "drift_workflow_commit",
    "remote_parity_proof",
    "actions_visibility_proof",
    "dispatch_readiness_proof",
    "handoff_verifier_proof",
  ];
  const fieldKeys = fields.length ? fields.map((field) => field.key).filter(Boolean) : defaultFieldKeys;
  const commands = Array.isArray(source.commands) ? source.commands : [];
  const expectedSignals = Array.isArray(source.expectedSignals) ? source.expectedSignals : [];
  const checklist = Array.isArray(source.checklist) ? source.checklist : [];
  const fallbackCommand = (needle, fallback) => commands.find((command) => String(command).includes(needle)) || fallback;
  const verificationSequence = Array.isArray(source.verificationSequence) && source.verificationSequence.length
    ? source.verificationSequence
    : [
        {
          key: "remote_file_parity",
          label: "Remote workflow file check",
          command: fallbackCommand("check-remote-workflow-files", "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"),
          expected: "remoteWorkflowFilesReady=true",
          guard: "Confirm both default-branch workflow files exist and match local templates before checking Actions visibility.",
        },
        {
          key: "actions_visibility",
          label: "Actions visibility check",
          command: fallbackCommand("gh workflow list", "gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id"),
          expected: "remoteWorkflowVisibilityReady=true",
          guard: "Confirm GitHub Actions lists both workflow files before planning dispatch.",
        },
        {
          key: "dispatch_readiness",
          label: "Dispatch readiness plan",
          command: fallbackCommand("plan-publish-dispatch", "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects"),
          expected: "allDispatchReady=true",
          guard: "Confirm pages and drift dispatch readiness are both true before final handoff verification.",
        },
        {
          key: "handoff_verifier",
          label: "Launch handoff verifier",
          command: fallbackCommand("verify-launch-handoff", "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"),
          expected: "safeToDispatch=true before gh workflow run",
          guard: source.stopCondition || POST_INSTALL_STOP_CONDITION,
        },
      ];
  const verificationSequenceCount = numberOr(source.verificationSequenceCount, verificationSequence.length);
  const verificationSequenceReady = source.verificationSequenceReady === true ||
    (verificationSequenceCount === 4 && verificationSequence.every((step) => step.command && step.expected));
  const quickProofSteps = Array.isArray(source.quickProofSteps) && source.quickProofSteps.length
    ? source.quickProofSteps
    : verificationSequence.map((step) => ({
        key: step.key,
        label: step.label,
        command: step.command,
        expected: step.expected,
        evidenceFieldKey: step.evidenceFieldKey || `${step.key}_proof`,
        status: "evidence_required",
        guard: step.guard || source.stopCondition || "",
      }));
  const quickProofStepCount = numberOr(source.quickProofStepCount, quickProofSteps.length);
  const quickProofCoverage = numberOr(
    source.quickProofCoverage,
    quickProofStepCount === 4 && quickProofSteps.every((step) => step.command && step.expected && step.evidenceFieldKey) ? 1 : 0,
  );
  const quickProofFieldMappings = Array.isArray(source.quickProofFieldMappings) && source.quickProofFieldMappings.length
    ? source.quickProofFieldMappings
    : quickProofSteps.map((step) => {
        const mappedField = fields.find((field) => field.key === step.evidenceFieldKey) || {};
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
          stopCondition: mappedField.stopCondition || step.guard || source.stopCondition || "",
        };
      });
  const quickProofMappedFieldCount = numberOr(source.quickProofMappedFieldCount, quickProofFieldMappings.length);
  const quickProofCompletedMappedFieldCount = numberOr(
    source.quickProofCompletedMappedFieldCount,
    quickProofFieldMappings.filter((item) => item.fieldCompleted).length,
  );
  const quickProofPendingMappedFieldCount = numberOr(
    source.quickProofPendingMappedFieldCount,
    Math.max(quickProofMappedFieldCount - quickProofCompletedMappedFieldCount, 0),
  );
  const quickProofFieldMappingCoverage = numberOr(
    source.quickProofFieldMappingCoverage,
    quickProofMappedFieldCount === 4 && quickProofFieldMappings.every((item) => item.stepKey && item.fieldKey && item.fieldLabel && item.proofCommand && item.expectedValue) ? 1 : 0,
  );
  const completedFallback = fields.filter((field) => field.completed || field.status === "proof_ready" || field.status === "ready").length;
  const fieldCount = numberOr(source.fieldCount, fields.length);
  const completedFieldCount = numberOr(source.completedFieldCount, completedFallback);
  const pendingFieldCount = numberOr(source.pendingFieldCount, Math.max(fieldCount - completedFieldCount, 0));
  const commandCount = numberOr(source.commandCount, commands.length);
  const signalCount = numberOr(source.signalCount, expectedSignals.length);
  const checklistCount = numberOr(source.checklistCount, checklist.length);
  const fieldCoverage = numberOr(
    source.fieldCoverage,
    fieldCount >= 6 && commandCount >= 4 && signalCount >= 8 ? 1 : 0,
  );
  const proofComplete = source.proofComplete === true || (fieldCount > 0 && completedFieldCount >= fieldCount);
  return {
    source: source.source || "not_available",
    status: source.status || "not_available",
    ready: source.ready === true || fieldCoverage === 1,
    proofComplete,
    allProofFieldsReady: source.allProofFieldsReady === true || proofComplete,
    repo: source.repo || "",
    defaultBranch: source.defaultBranch || "",
    fieldCount,
    completedFieldCount,
    pendingFieldCount,
    fieldCoverage,
    commandCount,
    signalCount,
    checklistCount,
    verificationSequenceCount,
    verificationSequenceReady,
    finalVerificationCommand: source.finalVerificationCommand || verificationSequence[verificationSequence.length - 1]?.command || "",
    quickProofReady: source.quickProofReady === true || quickProofCoverage === 1,
    quickProofStepCount,
    quickProofCoverage,
    quickProofStatus: source.quickProofStatus || source.status || "not_available",
    quickProofFinalCommand: source.quickProofFinalCommand || source.finalVerificationCommand || verificationSequence[verificationSequence.length - 1]?.command || "",
    quickProofReceipt: source.quickProofReceipt || "",
    quickProofSteps,
    quickProofFieldMappingReady: source.quickProofFieldMappingReady === true || quickProofFieldMappingCoverage === 1,
    quickProofFieldMappingCoverage,
    quickProofMappedFieldCount,
    quickProofCompletedMappedFieldCount,
    quickProofPendingMappedFieldCount,
    quickProofFieldMappings,
    fieldKeys,
    dispatchGuard: source.dispatchGuard || POST_INSTALL_DISPATCH_GUARD,
    stopCondition: source.stopCondition || POST_INSTALL_STOP_CONDITION,
    commands,
    expectedSignals,
    checklist,
    verificationSequence,
    fields,
  };
}

function blockerResolutionMarkdownLines(summary) {
  const items = Array.isArray(summary?.items) ? summary.items : [];
  return [
    "## Blocker Resolution Checklist",
    `- source: ${valueOrPending(summary?.source)}`,
    `- status: ${valueOrPending(summary?.status)}`,
    `- activeItemKey: ${valueOrPending(summary?.activeItemKey)}`,
    `- items: ${valueOrPending(summary?.passCount)}/${valueOrPending(summary?.itemCount)} pass; actionRequired=${valueOrPending(summary?.actionRequiredCount)}; deferred=${valueOrPending(summary?.deferredCount)}; proofCommands=${valueOrPending(summary?.proofCommandCount)}`,
    `- guard: ${valueOrPending(summary?.dispatchGuard)}`,
    ...(items.length
      ? items.map((item) => `- ${valueOrPending(item.key)}: ${valueOrPending(item.status)} - action=${valueOrPending(item.action)}; proofCommand=${valueOrPending(item.proofCommand)}; expectedValue=${valueOrPending(item.expectedValue)}; stopCondition=${valueOrPending(item.stopCondition)}`)
      : ["- not available; run with --write after launch packet generation"]),
  ];
}

function postInstallEvidenceIntakeMarkdownLines(summary) {
  const fields = Array.isArray(summary?.fields) ? summary.fields : [];
  const commands = Array.isArray(summary?.commands) ? summary.commands : [];
  const expectedSignals = Array.isArray(summary?.expectedSignals) ? summary.expectedSignals : [];
  const verificationSequence = Array.isArray(summary?.verificationSequence) ? summary.verificationSequence : [];
  const quickProofSteps = Array.isArray(summary?.quickProofSteps) ? summary.quickProofSteps : [];
  const quickProofFieldMappings = Array.isArray(summary?.quickProofFieldMappings) ? summary.quickProofFieldMappings : [];
  return [
    "## Post-install Evidence Intake",
    `- source: ${valueOrPending(summary?.source)}`,
    `- status: ${valueOrPending(summary?.status)}`,
    `- ready: ${yesNo(summary?.ready)}`,
    `- proofComplete: ${yesNo(summary?.proofComplete)}`,
    `- fields: ${valueOrPending(summary?.completedFieldCount)}/${valueOrPending(summary?.fieldCount)} complete; pending=${valueOrPending(summary?.pendingFieldCount)}; coverage=${valueOrPending(summary?.fieldCoverage)}`,
    `- fieldKeys: ${Array.isArray(summary?.fieldKeys) && summary.fieldKeys.length ? summary.fieldKeys.join(", ") : "not available"}`,
    `- commands: ${valueOrPending(summary?.commandCount)}; signals=${valueOrPending(summary?.signalCount)}; checklist=${valueOrPending(summary?.checklistCount)}; sequence=${valueOrPending(summary?.verificationSequenceCount)}`,
    `- verificationSequenceReady: ${yesNo(summary?.verificationSequenceReady)}`,
    `- finalVerificationCommand: ${valueOrPending(summary?.finalVerificationCommand)}`,
    `- quickProofReady: ${yesNo(summary?.quickProofReady)}; steps=${valueOrPending(summary?.quickProofStepCount)}; coverage=${valueOrPending(summary?.quickProofCoverage)}; final=${valueOrPending(summary?.quickProofFinalCommand)}`,
    `- quickProofFieldMappingReady: ${yesNo(summary?.quickProofFieldMappingReady)}; mapped=${valueOrPending(summary?.quickProofMappedFieldCount)}; completed=${valueOrPending(summary?.quickProofCompletedMappedFieldCount)}/${valueOrPending(summary?.quickProofMappedFieldCount)}; coverage=${valueOrPending(summary?.quickProofFieldMappingCoverage)}`,
    `- guard: ${valueOrPending(summary?.dispatchGuard)}`,
    `- ${valueOrPending(summary?.stopCondition)}`,
    "",
    "## Post-install Quick Proof",
    ...(quickProofSteps.length ? quickProofSteps.map((step, index) => `- ${index + 1}. ${valueOrPending(step.key)}: command=${valueOrPending(step.command)}; expected=${valueOrPending(step.expected)}; evidenceField=${valueOrPending(step.evidenceFieldKey)}; status=${valueOrPending(step.status)}`) : ["- quick proof not available"]),
    ...(quickProofFieldMappings.length ? quickProofFieldMappings.map((item, index) => `- mapped field ${index + 1} ${valueOrPending(item.stepKey)} -> ${valueOrPending(item.fieldKey)}: ${valueOrPending(item.fieldStatus)}; completed=${yesNo(item.fieldCompleted)}; currentValue=${valueOrPending(item.currentValue)}; expectedValue=${valueOrPending(item.expectedValue)}; proofCommand=${valueOrPending(item.proofCommand)}`) : ["- mapped field: not available"]),
    ...(commands.length ? commands.map((command) => `- command: ${command}`) : ["- command: not available"]),
    ...(verificationSequence.length ? verificationSequence.map((step, index) => `- sequence ${index + 1} ${valueOrPending(step.key)}: ${valueOrPending(step.label)}; command=${valueOrPending(step.command)}; expected=${valueOrPending(step.expected)}; guard=${valueOrPending(step.guard)}`) : ["- sequence: not available"]),
    ...(expectedSignals.length ? expectedSignals.map((signal) => `- expected signal: ${signal}`) : ["- expected signal: not available"]),
    ...(fields.length
      ? fields.map((field) => `- field ${valueOrPending(field.key)}: ${valueOrPending(field.status)}; completed=${yesNo(field.completed)}; currentValue=${valueOrPending(field.currentValue)}; expectedValue=${valueOrPending(field.expectedValue)}; proofCommand=${valueOrPending(field.proofCommand)}; stopCondition=${valueOrPending(field.stopCondition)}`)
      : ["- field evidence not available; run with --write after launch packet generation"]),
  ];
}

function payloadMarkdownLines(payload) {
  return [
    "# JooPark Launch Handoff Verification",
    "",
    `- status: ${payload.status}`,
    `- repo: ${payload.repo}`,
    `- verificationOnly: ${yesNo(payload.verificationOnly)}`,
    `- dispatchExecuted: ${yesNo(payload.dispatchExecuted)}`,
    `- launchProofCaptured: ${yesNo(payload.launchProofCaptured)}`,
    `- remoteWorkflowFilesReady: ${yesNo(payload.remoteWorkflowFilesReady)}`,
    `- remoteWorkflowVisibilityReady: ${yesNo(payload.remoteWorkflowVisibilityReady)}`,
    `- workflowScopeAvailable: ${yesNo(payload.workflowScopeAvailable)}`,
    `- workflowScopeInstallBlocked: ${yesNo(payload.workflowScopeInstallBlocked)}`,
    `- allDispatchReady: ${yesNo(payload.allDispatchReady)}`,
    `- safeToDispatch: ${yesNo(payload.safeToDispatch)}`,
    `- acceptance: ${valueOrPending(payload.acceptancePassCount)}/${valueOrPending(payload.acceptanceChecklist.length)} pass; pending=${valueOrPending(payload.acceptancePendingCount)}`,
    "",
    "## Verification Artifacts",
    `- artifactCoverage: ${valueOrPending(payload.verificationArtifact.artifactCoverage)}`,
    `- json: ${valueOrPending(payload.verificationArtifact.jsonPath)}`,
    `- markdown: ${valueOrPending(payload.verificationArtifact.markdownPath)}`,
    `- write: ${yesNo(payload.verificationArtifact.write)}`,
    "",
    "## Auth Preflight",
    `- checked: ${yesNo(payload.authPreflight.checked)}`,
    `- source: ${valueOrPending(payload.authPreflight.source)}`,
    `- workflowScopeAvailable: ${yesNo(payload.authPreflight.workflowScopeAvailable)}`,
    `- workflowScopeInstallBlocked: ${yesNo(payload.authPreflight.workflowScopeInstallBlocked)}`,
    `- scopes: ${payload.authPreflight.scopes.length ? payload.authPreflight.scopes.join(", ") : "none"}`,
    `- refresh: ${payload.authPreflight.refreshCommand}`,
    `- refreshWithClipboard: ${payload.authPreflight.refreshClipboardCommand}`,
    `- recheck: ${payload.authPreflight.recheckCommand}`,
    `- approval: ${payload.authPreflight.approvalHandoff?.status || "not_required"}`,
    `- interactiveApprovalRequired: ${payload.authPreflight.approvalHandoff?.interactiveApprovalRequired ? "true" : "false"}`,
    `- terminalWaitRequired: ${payload.authPreflight.approvalHandoff?.terminalWaitRequired ? "true" : "false"}`,
    `- incompleteApprovalSignal: ${payload.authPreflight.approvalHandoff?.incompleteApprovalSignal || "not available"}`,
    "",
    "## Commands Run",
    ...payload.commandRuns.map((run) => `- ${run.status}: \`${run.command}\``),
    "",
    "## Acceptance Checklist",
    ...(payload.acceptanceChecklist.length
      ? payload.acceptanceChecklist.map((item) => `- ${item.label}: ${item.status} - ${item.evidence || item.required || ""}`)
      : ["- not available; run with --write after launch packet generation"]),
    "",
    ...blockerResolutionMarkdownLines(payload.blockerResolutionChecklist),
    "",
    ...postInstallEvidenceIntakeMarkdownLines(payload.postInstallEvidenceIntake),
    "",
    "## Withheld Dispatch Commands",
    ...(payload.withheldDispatchCommands.length ? payload.withheldDispatchCommands.map((command) => `- ${command}`) : ["- none"]),
    "",
    "## Suggested Dispatch Commands",
    ...(payload.suggestedDispatchCommands.length ? payload.suggestedDispatchCommands.map((command) => `- ${command}`) : ["- none until every post-install evidence field has been filled and verify-launch-handoff reports safeToDispatch=true"]),
    "",
    "## Blockers",
    ...(payload.blockers.length ? payload.blockers.map((blocker) => `- ${blocker}`) : ["- none"]),
    "",
    "## Next Actions",
    ...payload.nextActions.map((action) => `- ${action}`),
  ];
}

const commandRuns = [];
const remoteArgs = ["scripts/check-remote-workflow-files.mjs", "--repo", repo];
if (write) remoteArgs.push("--write");
commandRuns.push(runNode(remoteArgs[0], remoteArgs.slice(1)));

const dispatchArgs = ["scripts/plan-publish-dispatch.mjs", "--live", "--repo", repo];
if (write) dispatchArgs.push("--write");
commandRuns.push(runNode(dispatchArgs[0], dispatchArgs.slice(1)));

if (write) {
  commandRuns.push(runNode("scripts/capture-launch-execution-packet.mjs", ["--write"]));
  commandRuns.push(runNode("scripts/capture-output-quality-audit.mjs", ["--write"]));
}

const remoteWorkflowFileCheck = commandRuns[0]?.json || readJson("data/remote-workflow-file-check.json", {});
const publishDispatchPlan = commandRuns[1]?.json || readJson("data/publish-dispatch-plan.json", {});
const launchExecutionPacket = write
  ? commandRuns[2]?.json || readJson("data/launch-execution-packet.json", {})
  : readJson("data/launch-execution-packet.json", {});
const outputQualityAudit = write
  ? commandRuns[3]?.json || readJson("data/output-quality-audit.json", {})
  : readJson("data/output-quality-audit.json", {});
const currentAction = launchExecutionPacket?.currentAction || {};
const acceptanceChecklist = Array.isArray(currentAction.acceptanceChecklist) ? currentAction.acceptanceChecklist : [];
const blockerResolutionChecklist = blockerResolutionSummary(launchExecutionPacket?.blockerResolutionChecklist);
const postInstallEvidenceIntake = postInstallEvidenceIntakeSummary(launchExecutionPacket?.postInstallEvidenceIntake);
const allDispatchReady = !!publishDispatchPlan.allDispatchReady;
const remoteWorkflowFilesReady = !!remoteWorkflowFileCheck.remoteWorkflowFilesReady;
const remoteWorkflowVisibilityReady = !!publishDispatchPlan.remoteWorkflowVisibilityReady;
const workflowScope = publishDispatchPlan.workflowScope || {};
const workflowScopeScopes = Array.isArray(workflowScope.scopes) ? workflowScope.scopes : [];
const workflowScopeAvailable = !!(publishDispatchPlan.workflowScopeAvailable ?? workflowScope.available);
const workflowScopeInstallBlocked = !!publishDispatchPlan.workflowScopeInstallBlocked;
const workflowScopeRefreshCommand = publishDispatchPlan.workflowScopeRefreshCommand || "gh auth refresh -h github.com -s workflow";
const workflowScopeRefreshClipboardCommand = publishDispatchPlan.workflowScopeRefreshClipboardCommand || publishDispatchPlan.workflowScopeRefreshHandoff?.clipboardCommand || `${workflowScopeRefreshCommand} --clipboard`;
const workflowScopeRecheckCommand = publishDispatchPlan.workflowScopeRecheckCommand || publishDispatchPlan.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${repo}`;
const authPreflight = {
  checked: workflowScope.checked !== false,
  source: workflowScope.source || "publish-dispatch-plan",
  workflowScopeAvailable,
  workflowScopeInstallBlocked,
  scopes: workflowScopeScopes,
  refreshCommand: workflowScopeRefreshCommand,
  refreshClipboardCommand: workflowScopeRefreshClipboardCommand,
  recheckCommand: workflowScopeRecheckCommand,
  approvalHandoff: publishDispatchPlan.workflowScopeApprovalHandoff || publishDispatchPlan.workflowScopeRefreshHandoff?.approval || {},
};
const safeToDispatch = repoEvidenceReady && remoteWorkflowFilesReady && remoteWorkflowVisibilityReady && allDispatchReady;
const suggestedDispatchCommands = safeToDispatch && Array.isArray(publishDispatchPlan.suggestedDispatchCommands)
  ? publishDispatchPlan.suggestedDispatchCommands
  : [];
const withheldDispatchCommands = safeToDispatch
  ? []
  : unique([
      publishDispatchPlan.dispatchCommand,
      publishDispatchPlan.driftDispatchCommand,
    ]);
const blockers = unique([
  ...commandRuns.filter((run) => run.status !== "pass").map((run) => `${run.command}: ${run.stderr || "failed"}`),
  ...(Array.isArray(remoteWorkflowFileCheck.blockers) ? remoteWorkflowFileCheck.blockers.map((item) => `Remote workflow file check: ${item}`) : []),
  ...(Array.isArray(publishDispatchPlan.blockers) ? publishDispatchPlan.blockers.map((item) => `Publish dispatch: ${item}`) : []),
  !repoEvidenceReady ? "Repo must be provided before live launch handoff verification" : "",
  workflowScopeInstallBlocked ? `workflowScopeInstallBlocked=true; run ${workflowScopeRefreshCommand} and rerun ${workflowScopeRecheckCommand}` : "",
  !remoteWorkflowFilesReady ? "remoteWorkflowFilesReady=false" : "",
  !remoteWorkflowVisibilityReady ? "remoteWorkflowVisibilityReady=false" : "",
  !allDispatchReady ? "allDispatchReady=false" : "",
]);
const installActionRows = (Array.isArray(publishDispatchPlan.workflowPlans) ? publishDispatchPlan.workflowPlans : [])
  .map((plan) => `${plan.key || plan.workflowFile || "workflow"}=${plan.installAction || plan.checks?.installAction || "unknown"}`);
const installActionNextAction = installActionRows.length
  ? `Apply each workflow row's installAction on the default branch (${installActionRows.join("; ")}), then rerun this verifier.`
  : "Apply the workflow installAction rows on the default branch, then rerun this verifier.";
const nextActions = safeToDispatch
  ? [
      "Run the suggested dispatch commands only after confirming the repo and workflow names.",
      `Capture launch proof with node scripts/capture-publish-evidence.mjs --live --repo ${repo} --write after workflow runs finish.`,
    ]
  : [
      "Do not run gh workflow run yet.",
      installActionNextAction,
      `If workflow scope is missing, run ${workflowScopeRefreshCommand} first.`,
    ];

const payload = {
  status: commandRuns.every((run) => run.status === "pass") ? "pass" : "fail",
  mode: write ? "write" : "check",
  generatedAt: new Date().toISOString(),
  repo,
  repoEvidenceReady,
  verificationOnly: true,
  dispatchExecuted: false,
  launchProofCaptured: false,
  write,
  commandRuns: commandRuns.map((run) => ({ command: run.command, status: run.status, error: run.stderr || "" })),
  remoteWorkflowFilesReady,
  remoteWorkflowVisibilityReady,
  authPreflight,
  workflowScopeAvailable,
  workflowScopeInstallBlocked,
  workflowScopeRefreshCommand,
  workflowScopeRecheckCommand,
  allDispatchReady,
  safeToDispatch,
  readyForExternalClaim: !!outputQualityAudit.readyForExternalClaim,
  currentStage: currentAction.stageKey || "",
  acceptanceChecklist,
  acceptancePassCount: Number(currentAction.acceptancePassCount ?? acceptanceChecklist.filter((item) => item.status === "pass").length),
  acceptancePendingCount: Number(currentAction.acceptancePendingCount ?? acceptanceChecklist.filter((item) => item.status !== "pass").length),
  blockerResolutionChecklist,
  postInstallEvidenceIntake,
  verificationArtifact: {
    write,
    jsonPath: write ? outJsonRel : "",
    markdownPath: write ? outMarkdownRel : "",
    artifactCoverage: write ? 2 : 0,
    dispatchGuard: "Saved verifier artifacts are verification-only and never authorize gh workflow run while safeToDispatch=false.",
  },
  suggestedDispatchCommands,
  withheldDispatchCommands,
  blockers,
  nextActions,
};

const markdownText = payloadMarkdownLines(payload).join("\n");
if (write) {
  writeText(outJsonRel, `${JSON.stringify(payload, null, 2)}\n`);
  writeText(outMarkdownRel, `${markdownText}\n`);
}

if (markdown) {
  console.log(markdownText);
} else {
  console.log(JSON.stringify(payload, null, 2));
}

if (payload.status !== "pass") process.exit(1);
