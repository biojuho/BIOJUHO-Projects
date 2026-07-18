#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const live = rawArgs.includes("--live");
const write = rawArgs.includes("--write");
const markdown = rawArgs.includes("--markdown");
const suggestedRepo = suggestedRepoFromRemote();
const repo = argValue("--repo") || (live ? currentRepo() || suggestedRepo : "OWNER/REPO");
const outRel = argValue("--out") || "data/publish-evidence.json";
const workflowRunJsonFields = "databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle";
const evidenceMaxAgeHours = 24;
const workflowDispatchPrefix = "gh workflow run --repo";
const publishDispatchPlan = readJson("data/publish-dispatch-plan.json");
const launchExecutionPacket = readJson("data/launch-execution-packet.json");
const launchReadinessRefresh = readJson("data/launch-readiness-refresh.json");
const pagesWorkflowDispatchRef = pagesWorkflowRefFromTemplate();

function isPlaceholderRepo(value) {
  return !value || value === "OWNER/REPO";
}

function repoDisplayContext(evidence) {
  const evidenceRepo = String(evidence?.repo || "").trim() || "not available";
  const suggested = String(evidence?.suggestedRepo || suggestedRepo || "").trim();
  const displayRepo = isPlaceholderRepo(evidenceRepo) && suggested ? suggested : evidenceRepo || suggested;
  const placeholderResolved = isPlaceholderRepo(evidenceRepo) && !!suggested;
  return {
    displayRepo,
    evidenceRepo,
    repoResolution: placeholderResolved ? "resolved_from_suggested_repo" : displayRepo ? "source_repo" : "missing_repo",
    repoPlaceholderResolved: placeholderResolved,
  };
}

function workflowDispatchCommand(workflowFile, targetRepo = "OWNER/REPO", fields = []) {
  return [workflowDispatchPrefix, targetRepo || "OWNER/REPO", workflowFile, ...fields].join(" ");
}

function workflowEvidenceCommand(workflowFile, targetRepo = "OWNER/REPO") {
  return `gh run list --repo ${targetRepo || "OWNER/REPO"} --workflow ${workflowFile} --limit 1 --json ${workflowRunJsonFields}`;
}

function workflowProofSelectionCommand(workflowFile, targetRepo = "OWNER/REPO") {
  return `gh run list --repo ${targetRepo || "OWNER/REPO"} --workflow ${workflowFile} --limit 10 --json ${workflowRunJsonFields}`;
}

function readJson(relPath) {
  try {
    return JSON.parse(readFileSync(resolve(root, relPath), "utf-8"));
  } catch {
    return null;
  }
}

function pagesWorkflowRefFromTemplate() {
  try {
    const template = readFileSync(resolve(root, "docs/github-pages-workflow.yml"), "utf-8");
    return template.match(/default:\s*([^\s#]+)/)?.[1] || "codex/joopark-workspace-release";
  } catch {
    return "codex/joopark-workspace-release";
  }
}

function publishDispatchSuggestionContext(plan) {
  const allDispatchReady = !!plan?.allDispatchReady;
  return {
    publishDispatchPlanSource: plan ? "data/publish-dispatch-plan.json" : "not available",
    publishDispatchReady: allDispatchReady,
    dispatchSuggestionStatus: typeof plan?.dispatchSuggestionStatus === "string"
      ? plan.dispatchSuggestionStatus
      : allDispatchReady
        ? "ready"
        : "withheld-until-all-dispatch-ready",
  };
}

function publishEvidenceCommandSet(targetRepo = "OWNER/REPO") {
  const commandRepo = targetRepo || "OWNER/REPO";
  const verificationCommands = [
    `node scripts/plan-publish-dispatch.mjs --live --repo ${commandRepo}`,
    `node scripts/capture-publish-evidence.mjs --live --repo ${commandRepo}`,
    `node scripts/capture-publish-evidence.mjs --live --repo ${commandRepo} --markdown`,
    `node scripts/capture-publish-evidence.mjs --live --repo ${commandRepo} --write`,
    `gh api repos/${commandRepo}/pages`,
    workflowEvidenceCommand("joopark-pages.yml", commandRepo),
    workflowEvidenceCommand("joopark-drift-watch.yml", commandRepo),
  ];
  const dispatchCommands = [
    workflowDispatchCommand("joopark-pages.yml", commandRepo, ["-f", `ref=${pagesWorkflowDispatchRef}`]),
    workflowDispatchCommand("joopark-drift-watch.yml", commandRepo, ["-f", "mode=advisory"]),
  ];
  return {
    verificationCommands,
    dispatchCommands,
  };
}

const workflowEvidencePlans = [
  {
    key: "pages",
    workflowName: "Publish JooPark Pages",
    workflowFile: "joopark-pages.yml",
    dispatchFields: ["-f", `ref=${pagesWorkflowDispatchRef}`],
  },
  {
    key: "drift-watch",
    workflowName: "Watch JooPark Candidate Drift",
    workflowFile: "joopark-drift-watch.yml",
    dispatchFields: ["-f", "mode=advisory"],
  },
].map((workflow) => ({
  ...workflow,
  dispatchCommand: workflowDispatchCommand(workflow.workflowFile, repo, workflow.dispatchFields),
  evidenceCommand: workflowEvidenceCommand(workflow.workflowFile, repo),
}));

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

function runJson(command, args) {
  try {
    const output = execFileSync(command, args, {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    return {
      ok: true,
      data: JSON.parse(output || "{}"),
      stderr: "",
    };
  } catch (error) {
    return {
      ok: false,
      data: null,
      stderr: String(error?.stderr || error?.message || error).slice(0, 400),
    };
  }
}

function runText(command, args) {
  try {
    const output = execFileSync(command, args, {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    return {
      ok: true,
      output: String(output || "").trim(),
      stderr: "",
    };
  } catch (error) {
    return {
      ok: false,
      output: String(error?.stdout || "").trim(),
      stderr: String(error?.stderr || error?.message || error).slice(0, 400),
    };
  }
}

function currentRepo() {
  const result = runJson("gh", ["repo", "view", "--json", "nameWithOwner"]);
  return result.ok && result.data?.nameWithOwner ? result.data.nameWithOwner : "";
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

function pageSiteEvidence(targetRepo) {
  const commandRepo = !targetRepo || targetRepo === "OWNER/REPO" ? "OWNER/REPO" : targetRepo;
  if (!live || !targetRepo || targetRepo === "OWNER/REPO") {
    return {
      checked: false,
      command: `gh api repos/${commandRepo}/pages`,
      ready: false,
      site: null,
      liveUrl: null,
      error: "",
    };
  }
  const result = runJson("gh", ["api", `repos/${targetRepo}/pages`]);
  const site = result.data || null;
  const liveUrl = site?.html_url ? liveUrlEvidence(site.html_url) : null;
  const apiStatusReady = site?.status === "built";
  const liveUrlReady = !!liveUrl?.ready;
  const statusSource = apiStatusReady ? "pages_api_status" : liveUrlReady ? "live_url_http" : "";
  const ready = !!(result.ok && site?.html_url && (apiStatusReady || liveUrlReady) && site?.https_enforced !== false);
  return {
    checked: true,
    command: `gh api repos/${targetRepo}/pages`,
    ready,
    site: site ? {
      html_url: site.html_url || "",
      status: site.status || "",
      statusSource,
      https_enforced: !!site.https_enforced,
      public: typeof site.public === "boolean" ? site.public : null,
    } : null,
    liveUrl,
    error: result.ok ? "" : result.stderr,
  };
}

function liveUrlEvidence(url) {
  const command = `curl -L --max-time 20 -sS -o /dev/null -w "%{http_code} %{url_effective} %{content_type}" ${url}`;
  const result = runText("curl", [
    "-L",
    "--max-time",
    "20",
    "-sS",
    "-o",
    "/dev/null",
    "-w",
    "%{http_code} %{url_effective} %{content_type}",
    url,
  ]);
  const [httpStatus = "", effectiveUrl = "", ...contentTypeParts] = result.output.split(/\s+/).filter(Boolean);
  const statusCode = Number(httpStatus);
  const ready = !!(result.ok && statusCode >= 200 && statusCode < 400 && effectiveUrl.startsWith("https://"));
  return {
    checked: true,
    command,
    ready,
    httpStatus,
    effectiveUrl,
    contentType: contentTypeParts.join(" "),
    error: result.ok ? "" : result.stderr,
  };
}

function latestWorkflowRun(workflow, targetRepo) {
  const evidenceCommand = workflowEvidenceCommand(workflow.workflowFile, targetRepo);
  const proofSelectionCommand = workflowProofSelectionCommand(workflow.workflowFile, targetRepo);
  if (!live || isPlaceholderRepo(targetRepo)) {
    return {
      ...workflow,
      evidenceCommand,
      proofSelectionCommand,
      checked: false,
      ready: false,
      latestRun: null,
      error: "",
    };
  }
  const result = runJson("gh", [
    "run",
    "list",
    "--repo",
    targetRepo,
    "--workflow",
    workflow.workflowFile,
    "--limit",
    "10",
    "--json",
    workflowRunJsonFields,
  ]);
  const runs = Array.isArray(result.data) ? result.data : [];
  const latestRun = runs.find((run) => run.event === "workflow_dispatch" && run.status === "completed" && run.conclusion === "success") ||
    runs.find((run) => run.status === "completed" && run.conclusion === "success") ||
    runs[0] ||
    null;
  const ready = !!(latestRun && latestRun.status === "completed" && latestRun.conclusion === "success");
  return {
    ...workflow,
    evidenceCommand,
    proofSelectionCommand,
    checked: true,
    ready,
    latestRun,
    actualLatestRun: runs[0] || null,
    recentRunCount: runs.length,
    proofSelectionPolicy: "Prefer the most recent successful workflow_dispatch proof run; preserve actualLatestRun when push-triggered deploys are rejected by environment protection.",
    error: result.ok ? "" : result.stderr,
  };
}

function valueOrPending(value) {
  if (value === true) return "true";
  if (value === false) return "false";
  if (value === null || value === undefined || value === "") return "not available";
  return String(value);
}

function pageSiteProofSource(pagesSite) {
  return pagesSite?.site?.statusSource || (pagesSite?.ready ? "pages_evidence_ready" : "");
}

function pageSiteStatusSummary(pagesSite) {
  const site = pagesSite?.site || {};
  const liveUrl = pagesSite?.liveUrl || {};
  const liveSuffix = liveUrl.checked
    ? `; live_http=${valueOrPending(liveUrl.httpStatus)}; live_url_ready=${valueOrPending(liveUrl.ready)}`
    : "";
  return `${valueOrPending(site.status)}; proof_source=${valueOrPending(pageSiteProofSource(pagesSite))}${liveSuffix}`;
}

function publishEvidenceDispatchGuardLines(evidence, { includeCommands = true } = {}) {
  const suggestedCommands = Array.isArray(evidence.suggestedCommands) ? evidence.suggestedCommands : [];
  const suggestedDispatchCommands = Array.isArray(evidence.suggestedDispatchCommands) ? evidence.suggestedDispatchCommands : [];
  const withheldDispatchCommands = Array.isArray(evidence.withheldDispatchCommands) ? evidence.withheldDispatchCommands : [];
  const suggestedCommandsSafe = !suggestedCommands.some((command) => command.includes("gh workflow run --repo"));
  const dispatchState = publishEvidenceDispatchCommandState(evidence);
  const dispatchGuardLines = [
    `Dispatch guard: ${evidence.publishDispatchReady ? "ready" : "withheld"} (${valueOrPending(evidence.dispatchSuggestionStatus)})`,
    `Suggested commands safe: ${suggestedCommandsSafe}; suggested dispatch: ${suggestedDispatchCommands.length}; withheld dispatch: ${withheldDispatchCommands.length}`,
    `dispatchCommandDisposition: ${dispatchState.dispatchCommandDisposition}`,
    `activeDispatchCommandCount: ${dispatchState.activeDispatchCommandCount}`,
    `dispatchCommandReferenceCount: ${dispatchState.dispatchCommandReferenceCount}`,
  ];
  if (includeCommands && withheldDispatchCommands.length) {
    dispatchGuardLines.push(
      "Do not run dispatch until allDispatchReady: true.",
      "Withheld dispatch commands:",
      ...withheldDispatchCommands.map((command) => `- ${command}`),
    );
  }
  return dispatchGuardLines;
}

function publishEvidenceDispatchCommandState(evidence) {
  const suggestedDispatchCommands = Array.isArray(evidence?.suggestedDispatchCommands) ? evidence.suggestedDispatchCommands : [];
  const withheldDispatchCommands = Array.isArray(evidence?.withheldDispatchCommands) ? evidence.withheldDispatchCommands : [];
  const proofReady = !!(evidence?.postPublishEvidenceReady && evidence?.evidenceFresh);
  if (!evidence?.publishDispatchReady) {
    return {
      dispatchCommandDisposition: "withheld_until_all_dispatch_ready",
      activeDispatchCommands: [],
      activeDispatchCommandCount: 0,
      dispatchCommandReferenceCount: withheldDispatchCommands.length,
    };
  }
  if (proofReady) {
    return {
      dispatchCommandDisposition: "not_applicable_after_launch_proof",
      activeDispatchCommands: [],
      activeDispatchCommandCount: 0,
      dispatchCommandReferenceCount: suggestedDispatchCommands.length,
    };
  }
  if (evidence?.publishDispatchReady) {
    return {
      dispatchCommandDisposition: "active_until_launch_proof",
      activeDispatchCommands: suggestedDispatchCommands,
      activeDispatchCommandCount: suggestedDispatchCommands.length,
      dispatchCommandReferenceCount: suggestedDispatchCommands.length,
    };
  }
  return {
    dispatchCommandDisposition: "withheld_until_all_dispatch_ready",
    activeDispatchCommands: [],
    activeDispatchCommandCount: 0,
    dispatchCommandReferenceCount: withheldDispatchCommands.length,
  };
}

function publishEvidenceExternalClaimGuard(evidence) {
  const publicLaunchProofReady = !!(evidence?.postPublishEvidenceReady && evidence?.evidenceFresh);
  const allDispatchReady = evidence?.publishDispatchReady === true || publishDispatchPlan?.allDispatchReady === true;
  const launchPacketReadyForExternalClaim = evidence?.launchPacketReadyForExternalClaim === true || launchExecutionPacket?.readyForExternalClaim === true;
  const readyForExternalClaim = !!(publicLaunchProofReady && allDispatchReady && launchPacketReadyForExternalClaim);
  const blockers = [];
  if (!publicLaunchProofReady) {
    blockers.push(`publicLaunchProofReady=false (postPublishEvidenceReady=${valueOrPending(evidence?.postPublishEvidenceReady)}; evidenceFresh=${valueOrPending(evidence?.evidenceFresh)})`);
  }
  if (!allDispatchReady) blockers.push("allDispatchReady=false");
  if (!launchPacketReadyForExternalClaim) blockers.push("launchPacketReadyForExternalClaim=false");
  if (!readyForExternalClaim) blockers.push("readyForExternalClaim=false");
  return {
    status: readyForExternalClaim ? "ready_for_external_claim" : "blocked_external_claim",
    publicLaunchProofReady,
    allDispatchReady,
    launchPacketReadyForExternalClaim,
    readyForExternalClaim,
    blockers,
  };
}

function publishEvidenceExternalClaimBlockerLines(evidence, guard = publishEvidenceExternalClaimGuard(evidence)) {
  const sourceBlockers = Array.isArray(evidence?.blockers) ? evidence.blockers : [];
  const blockers = [...sourceBlockers, ...guard.blockers].filter((blocker, index, lines) => blocker && lines.indexOf(blocker) === index);
  return blockers.length ? blockers.map((blocker) => `- ${blocker}`) : ["- none"];
}

function publishEvidenceExternalClaimGuardLines(evidence, guard = publishEvidenceExternalClaimGuard(evidence)) {
  return [
    "External claim guard:",
    `Status: ${guard.status}`,
    `Public launch proof ready: ${valueOrPending(guard.publicLaunchProofReady)}`,
    `allDispatchReady: ${valueOrPending(guard.allDispatchReady)}`,
    `Launch packet readyForExternalClaim: ${valueOrPending(guard.launchPacketReadyForExternalClaim)}`,
    `readyForExternalClaim: ${valueOrPending(guard.readyForExternalClaim)}`,
    "External claim blockers:",
    ...publishEvidenceExternalClaimBlockerLines(evidence, guard),
  ];
}

function publishEvidenceActionStatus(action) {
  return action?.status || action?.key || "action_required";
}

function publishEvidenceActionCommand(action) {
  if (!action) return "";
  if (action.command) return action.command;
  if (Array.isArray(action.commands) && action.commands.length) return action.commands[0];
  if (Array.isArray(action.verifyCommands) && action.verifyCommands.length) return action.verifyCommands[0];
  return "";
}

function launchReadinessMatchesRepo(launchReadiness, commandRepo, suggestedRepo) {
  const launchRepo = String(launchReadiness?.repo || "").trim();
  if (!launchRepo) return false;
  return launchRepo === commandRepo || launchRepo === suggestedRepo || (commandRepo === "OWNER/REPO" && launchRepo === suggestedRepo);
}

function publishEvidenceRepairFirstCommand({ current, launchReadinessRefresh, nextAction, commandRepo, suggestedRepo }) {
  if (!current || current.stageKey !== "install_workflows") return "";
  if (!launchReadinessMatchesRepo(launchReadinessRefresh, commandRepo, suggestedRepo)) return "";
  const repairAction = launchReadinessRefresh?.remoteWorkflowRepairAction || {};
  const candidate = repairAction.command || launchReadinessRefresh?.nextAction?.command || nextAction?.command || "";
  return String(candidate || "").includes("github-pages-workflow.yml") ? candidate : "";
}

function publishEvidenceImmediateNextAction({ launchExecutionPacket, launchReadinessRefresh, nextAction, commandRepo, suggestedRepo }) {
  const current = launchExecutionPacket?.currentAction;
  if (current && launchExecutionPacket?.readyForExternalClaim !== true) {
    const commands = Array.isArray(current.commands) ? current.commands : [];
    const verifyCommands = Array.isArray(current.verifyCommands) ? current.verifyCommands : [];
    const withheldCommands = Array.isArray(current.withheldCommands) ? current.withheldCommands : [];
    const launchInstallPaths = launchInstallPathSnapshot(launchExecutionPacket);
    const repairFirstCommand = publishEvidenceRepairFirstCommand({ current, launchReadinessRefresh, nextAction, commandRepo, suggestedRepo });
    return {
      key: current.stageKey || "install_workflows",
      label: current.label || "Current launch action",
      status: current.status || "action_required",
      detail: current.detail || "",
      successCondition: current.successCondition || "",
      command: repairFirstCommand || commands[0] || verifyCommands[0] || nextAction?.command || "",
      commandCount: Number.isFinite(Number(current.commandCount)) ? Number(current.commandCount) : commands.length,
      withheldCommandCount: Number.isFinite(Number(current.withheldCommandCount)) ? Number(current.withheldCommandCount) : withheldCommands.length,
      launchInstallPaths,
      source: "data/launch-execution-packet.json",
    };
  }
  return {
    ...(nextAction || {}),
    status: nextAction?.status || (nextAction?.key === "share-launch-proof" ? "ready" : "action_required"),
    source: "publish-evidence-next-action",
  };
}

function launchInstallPathSnapshot(launchExecutionPacket) {
  const installPaths = Array.isArray(launchExecutionPacket?.currentAction?.installPaths)
    ? launchExecutionPacket.currentAction.installPaths
    : [];
  const paths = installPaths.map((path) => {
    const commands = Array.isArray(path.commands)
      ? path.commands.map((command) => String(command || "").trim()).filter(Boolean)
      : [];
    return {
      key: path.key || "",
      label: path.label || "",
      when: path.when || "",
      commands,
      commandCount: commands.length,
      success: path.success || "",
      guard: path.guard || "",
    };
  });
  const labels = paths.map((path) => path.label).filter(Boolean);
  const allCommands = paths.flatMap((path) => path.commands);
  const installerCommand = allCommands.find((command) => command.includes("install-remote-workflow-files.mjs")) || "";
  const cliPath = paths.find((path) => path.key === "cli_workflow_scope" || path.label === "CLI path after workflow scope") || null;
  const uiPath = paths.find((path) => path.key === "github_ui" || path.label === "GitHub UI path") || null;
  return {
    ready: paths.length >= 2 && !!cliPath && !!uiPath && !!installerCommand,
    count: paths.length,
    commandCount: allCommands.length,
    labels,
    installerCommand,
    paths,
  };
}

function publishEvidenceInstallPathLines(evidence, immediate) {
  const launchInstallPaths = evidence.launchInstallPaths || immediate?.launchInstallPaths || {};
  const paths = Array.isArray(launchInstallPaths.paths) ? launchInstallPaths.paths : [];
  if (!paths.length) return [];
  return [
    "Choose one install path:",
    `Launch install path options: ${launchInstallPaths.ready ? "pass" : "blocked"} (${valueOrPending(launchInstallPaths.count)} paths, ${valueOrPending(launchInstallPaths.commandCount)} commands; ${launchInstallPaths.labels?.length ? launchInstallPaths.labels.join(" | ") : "labels unavailable"})`,
    ...paths.flatMap((path) => [
      `- ${valueOrPending(path.label)}: ${valueOrPending(path.commandCount)} commands; success: ${valueOrPending(path.success)}; guard: ${valueOrPending(path.guard)}`,
      ...path.commands.map((command) => `  - ${command}`),
    ]),
  ];
}

function publishEvidenceActionLines(evidence, { includeImmediateCommand = true, includeDeferred = true } = {}) {
  const immediate = evidence.immediateNextAction || evidence.nextAction || {};
  const deferred = evidence.deferredNextAction || null;
  const immediateCommand = publishEvidenceActionCommand(immediate);
  const lines = [
    `Immediate action: ${valueOrPending(immediate.label)} [${valueOrPending(publishEvidenceActionStatus(immediate))}]`,
  ];
  if (immediate.source) lines.push(`Immediate source: ${immediate.source}`);
  if (immediate.detail) lines.push(`Immediate detail: ${immediate.detail}`);
  if (immediate.successCondition) lines.push(`Immediate success condition: ${immediate.successCondition}`);
  if (includeImmediateCommand && immediateCommand) lines.push(`Immediate command: ${immediateCommand}`);
  if (Number.isFinite(Number(immediate.commandCount))) lines.push(`Immediate command count: ${Number(immediate.commandCount)}`);
  if (Number.isFinite(Number(immediate.withheldCommandCount))) lines.push(`Immediate withheld dispatch count: ${Number(immediate.withheldCommandCount)}`);
  lines.push(...publishEvidenceInstallPathLines(evidence, immediate));
  if (includeDeferred && deferred) {
    lines.push(
      `Deferred evidence capture: ${valueOrPending(deferred.label)} - ${valueOrPending(deferred.detail)}`,
      `Deferred command: ${valueOrPending(deferred.command)}`,
    );
  }
  return lines;
}

function publishEvidenceShareUpdate(evidence) {
  const site = evidence.pagesSite?.site || {};
  const ready = publishEvidenceExternalClaimGuard(evidence).readyForExternalClaim;
  const repo = repoDisplayContext(evidence);
  const workflowLines = (Array.isArray(evidence.workflowRuns) ? evidence.workflowRuns : []).map((run) => {
    const latest = run.latestRun || {};
    return `- ${run.workflowFile}: ready=${run.ready}; status=${valueOrPending(latest.status)}; conclusion=${valueOrPending(latest.conclusion)}; url=${valueOrPending(latest.url)}`;
  });
  const blockerLines = Array.isArray(evidence.blockers) && evidence.blockers.length
    ? evidence.blockers.map((blocker) => `- ${blocker}`)
    : ["- none"];
  return [
    "JooPark Publish Evidence Update",
    `Status: ${ready ? "launch proof ready" : "action required"}`,
    `Repo: ${valueOrPending(repo.displayRepo)}`,
    `Evidence repo: ${valueOrPending(repo.evidenceRepo)}${repo.repoPlaceholderResolved ? " (placeholder resolved from suggestedRepo)" : ""}`,
    `Suggested repo: ${valueOrPending(evidence.suggestedRepo)}`,
    `Repo resolution: ${valueOrPending(repo.repoResolution)}`,
    `Pages URL: ${valueOrPending(site.html_url)}`,
    `Pages status: ${pageSiteStatusSummary(evidence.pagesSite)}`,
    `Evidence freshness: ${evidence.evidenceFresh ? "fresh" : "stale"} until ${valueOrPending(evidence.evidenceExpiresAt)}`,
    `postPublishEvidenceReady: ${evidence.postPublishEvidenceReady}`,
    ...publishEvidenceDispatchGuardLines(evidence),
    "Workflow runs:",
    ...workflowLines,
    "Blockers:",
    ...blockerLines,
    ...publishEvidenceActionLines(evidence),
  ].join("\n");
}

function publishLaunchAnnouncement(evidence) {
  const site = evidence.pagesSite?.site || {};
  const claimGuard = publishEvidenceExternalClaimGuard(evidence);
  const ready = claimGuard.readyForExternalClaim;
  const proofReady = claimGuard.publicLaunchProofReady;
  const repo = repoDisplayContext(evidence);
  const workflowRuns = Array.isArray(evidence.workflowRuns) ? evidence.workflowRuns : [];
  const runProof = workflowRuns
    .map((run) => {
      const latest = run.latestRun || {};
      return `- ${run.workflowFile}: ${run.ready ? "success" : "not ready"} (${valueOrPending(latest.url)})`;
    });
  if (!ready) {
    return [
      "JooPark Public Launch Announcement",
      "Status: not ready for public posting",
      `Repo: ${valueOrPending(repo.displayRepo)}`,
      `Evidence repo: ${valueOrPending(repo.evidenceRepo)}${repo.repoPlaceholderResolved ? " (placeholder resolved from suggestedRepo)" : ""}`,
      `Suggested repo: ${valueOrPending(evidence.suggestedRepo)}`,
      `Repo resolution: ${valueOrPending(repo.repoResolution)}`,
      "Reason:",
      ...publishEvidenceExternalClaimBlockerLines(evidence, claimGuard),
      ...(proofReady ? [
        `Live proof available: ${valueOrPending(site.html_url)}`,
        `Verification: GitHub Pages proof ${pageSiteStatusSummary(evidence.pagesSite)}; publish and drift-watch workflows completed successfully.`,
        `Evidence fresh until: ${valueOrPending(evidence.evidenceExpiresAt)}`,
        "Workflow proof:",
        ...runProof,
      ] : []),
      ...publishEvidenceExternalClaimGuardLines(evidence, claimGuard),
      "Dispatch gate:",
      ...publishEvidenceDispatchGuardLines(evidence, { includeCommands: false }),
      "Do not post or dispatch until allDispatchReady: true, postPublishEvidenceReady: true, and readyForExternalClaim: true.",
      ...publishEvidenceActionLines(evidence),
      "Do not post a public launch announcement until repoEvidenceReady, evidenceFresh, postPublishEvidenceReady, launchPacketReadyForExternalClaim, allDispatchReady, and readyForExternalClaim are all true.",
    ].join("\n");
  }
  return [
    "JooPark Public Launch Announcement",
    "Status: ready to post",
    `JooPark Workspace is live: ${valueOrPending(site.html_url)}`,
    `Verification: GitHub Pages proof ${pageSiteStatusSummary(evidence.pagesSite)}; publish and drift-watch workflows completed successfully.`,
    `Evidence fresh until: ${valueOrPending(evidence.evidenceExpiresAt)}`,
    `Repo: ${valueOrPending(repo.displayRepo)}`,
    `Evidence repo: ${valueOrPending(repo.evidenceRepo)}${repo.repoPlaceholderResolved ? " (placeholder resolved from suggestedRepo)" : ""}`,
    `Repo resolution: ${valueOrPending(repo.repoResolution)}`,
    "Workflow proof:",
    ...runProof,
    "Use this announcement only while evidenceFresh and postPublishEvidenceReady remain true.",
  ].join("\n");
}

function publishPostLaunchVerificationReceipt(evidence) {
  const site = evidence.pagesSite?.site || {};
  const claimGuard = publishEvidenceExternalClaimGuard(evidence);
  const ready = claimGuard.readyForExternalClaim;
  const proofReady = claimGuard.publicLaunchProofReady;
  const status = ready ? "verified for archive" : "not verified for archive";
  const repo = repoDisplayContext(evidence);
  const workflowLines = (Array.isArray(evidence.workflowRuns) ? evidence.workflowRuns : []).map((run) => {
    const latest = run.latestRun || {};
    return `- ${run.workflowFile}: ready=${run.ready}; status=${valueOrPending(latest.status)}; conclusion=${valueOrPending(latest.conclusion)}; url=${valueOrPending(latest.url)}; headSha=${valueOrPending(latest.headSha)}`;
  });
  const blockerLines = publishEvidenceExternalClaimBlockerLines(evidence, claimGuard);
  const checklistLines = [
    `- repoEvidenceReady: ${evidence.repoEvidenceReady}`,
    `- pagesEvidenceReady: ${evidence.pagesEvidenceReady}`,
    `- workflowEvidenceReady: ${evidence.workflowEvidenceReady}`,
    `- evidenceFresh: ${evidence.evidenceFresh}`,
    `- postPublishEvidenceReady: ${evidence.postPublishEvidenceReady}`,
    `- publishDispatchReady: ${evidence.publishDispatchReady}`,
    `- allDispatchReady: ${claimGuard.allDispatchReady}`,
    `- launchPacketReadyForExternalClaim: ${claimGuard.launchPacketReadyForExternalClaim}`,
    `- readyForExternalClaim: ${claimGuard.readyForExternalClaim}`,
    `- dispatchSuggestionStatus: ${valueOrPending(evidence.dispatchSuggestionStatus)}`,
  ];
  const receipt = [
    "JooPark Post-Launch Verification Receipt",
    `Status: ${status}`,
    `Repo: ${valueOrPending(repo.displayRepo)}`,
    `Evidence repo: ${valueOrPending(repo.evidenceRepo)}${repo.repoPlaceholderResolved ? " (placeholder resolved from suggestedRepo)" : ""}`,
    `Suggested repo: ${valueOrPending(evidence.suggestedRepo)}`,
    `Repo resolution: ${valueOrPending(repo.repoResolution)}`,
    `Pages URL: ${valueOrPending(site.html_url)}`,
    `Pages status: ${pageSiteStatusSummary(evidence.pagesSite)}`,
    `HTTPS enforced: ${valueOrPending(site.https_enforced)}`,
    `Evidence generated: ${valueOrPending(evidence.generatedAt)}`,
    `Evidence fresh until: ${valueOrPending(evidence.evidenceExpiresAt)}`,
    "Verification checklist:",
    ...checklistLines,
    ...publishEvidenceExternalClaimGuardLines(evidence, claimGuard),
    "Dispatch gate:",
    ...publishEvidenceDispatchGuardLines(evidence),
    "Workflow evidence:",
    ...workflowLines,
    "Blockers:",
    ...blockerLines,
  ];
  if (!ready) {
    receipt.push(
      ...publishEvidenceActionLines(evidence),
      proofReady
        ? "Do not archive this as post-launch verification until readyForExternalClaim=true with allDispatchReady=true and launchPacketReadyForExternalClaim=true."
        : "Do not archive this as post-launch verification until repoEvidenceReady, pagesEvidenceReady, workflowEvidenceReady, evidenceFresh, and postPublishEvidenceReady are all true.",
    );
    return receipt.join("\n");
  }
  receipt.push(
    "Follow-up:",
    "- Save this receipt with the launch notes while the evidence window is fresh.",
    `- Re-run before expiry: node scripts/capture-publish-evidence.mjs --live --repo ${valueOrPending(repo.displayRepo)} --markdown`,
  );
  return receipt.join("\n");
}

function publishLaunchProofEvidenceFields(evidence) {
  const pagesSite = evidence.pagesSite || {};
  const site = evidence.pagesSite?.site || {};
  const workflowRuns = Array.isArray(evidence.workflowRuns) ? evidence.workflowRuns : [];
  const pagesRun = workflowRuns.find((run) => run.workflowFile === "joopark-pages.yml") || {};
  const driftRun = workflowRuns.find((run) => run.workflowFile === "joopark-drift-watch.yml") || {};
  const pagesLatest = pagesRun.latestRun || {};
  const driftLatest = driftRun.latestRun || {};
  const claimGuard = publishEvidenceExternalClaimGuard(evidence);
  const ready = claimGuard.readyForExternalClaim;
  const proofReady = claimGuard.publicLaunchProofReady;
  const releaseReceiptStatus = ready ? "verified for archive" : "not verified for archive";
  const displayRepo = repoDisplayContext(evidence).displayRepo;
  return [
    {
      label: "Pages site proof",
      value: `html_url=${valueOrPending(site.html_url)}; status=${pageSiteStatusSummary(pagesSite)}; https_enforced=${valueOrPending(site.https_enforced)}`,
      required: "GitHub Pages proof must provide html_url, HTTPS enforcement, and either API status=built or live URL HTTP 2xx.",
      command: evidence.pagesSite?.command || `gh api repos/${displayRepo}/pages`,
      nextAction: `Run gh api repos/${displayRepo}/pages and the live URL check after the Pages workflow succeeds, then paste html_url, status or live_http=2xx, and https_enforced=true.`,
    },
    {
      label: "Pages workflow run proof",
      value: `status=${valueOrPending(pagesLatest.status)}; conclusion=${valueOrPending(pagesLatest.conclusion)}; url=${valueOrPending(pagesLatest.url)}; headSha=${valueOrPending(pagesLatest.headSha)}`,
      required: "Selected joopark-pages.yml proof run must be completed successfully and linked; actualLatestRun is retained separately when push-triggered deploys are rejected.",
      command: pagesRun.proofSelectionCommand || pagesRun.evidenceCommand || workflowEvidenceCommand("joopark-pages.yml", displayRepo),
      nextAction: `Run ${pagesRun.proofSelectionCommand || pagesRun.evidenceCommand || workflowEvidenceCommand("joopark-pages.yml", displayRepo)} and paste the selected proof run plus any actualLatestRun context.`,
    },
    {
      label: "Drift Watch workflow run proof",
      value: `status=${valueOrPending(driftLatest.status)}; conclusion=${valueOrPending(driftLatest.conclusion)}; url=${valueOrPending(driftLatest.url)}; headSha=${valueOrPending(driftLatest.headSha)}`,
      required: "Selected joopark-drift-watch.yml proof run must be completed successfully and linked.",
      command: driftRun.proofSelectionCommand || driftRun.evidenceCommand || workflowEvidenceCommand("joopark-drift-watch.yml", displayRepo),
      nextAction: `Run ${driftRun.proofSelectionCommand || driftRun.evidenceCommand || workflowEvidenceCommand("joopark-drift-watch.yml", displayRepo)} and paste status=completed, conclusion=success, url, and headSha.`,
    },
    {
      label: "Evidence freshness proof",
      value: `generatedAt=${valueOrPending(evidence.generatedAt)}; evidenceFresh=${valueOrPending(evidence.evidenceFresh)}; evidenceExpiresAt=${valueOrPending(evidence.evidenceExpiresAt)}; postPublishEvidenceReady=${valueOrPending(evidence.postPublishEvidenceReady)}`,
      required: "Saved evidence must be generated after dispatch and remain inside the freshness window.",
      command: `node scripts/capture-publish-evidence.mjs --live --repo ${displayRepo} --write`,
      nextAction: `Run node scripts/capture-publish-evidence.mjs --live --repo ${displayRepo} --write after both workflow runs succeed, then paste generatedAt, evidenceFresh=true, evidenceExpiresAt, and postPublishEvidenceReady=true.`,
    },
    {
      label: "Release receipt proof",
      value: `postLaunchVerificationReceipt=${evidence.postLaunchVerificationReceipt ? "available" : "missing"}; status=${releaseReceiptStatus}`,
      required: "Post-launch verification receipt must be archive-ready only after live Pages, workflow evidence, and the external claim guard are ready.",
      command: `node scripts/capture-publish-evidence.mjs --live --repo ${displayRepo} --markdown`,
      nextAction: `Run node scripts/capture-publish-evidence.mjs --live --repo ${displayRepo} --markdown and paste the archive-ready post-launch verification receipt only after readyForExternalClaim=true.`,
    },
    {
      label: "Public claim guard proof",
      value: `repoEvidenceReady=${valueOrPending(evidence.repoEvidenceReady)}; pagesEvidenceReady=${valueOrPending(evidence.pagesEvidenceReady)}; workflowEvidenceReady=${valueOrPending(evidence.workflowEvidenceReady)}; allDispatchReady=${valueOrPending(claimGuard.allDispatchReady)}; launchPacketReadyForExternalClaim=${valueOrPending(claimGuard.launchPacketReadyForExternalClaim)}; readyForExternalClaim=${valueOrPending(claimGuard.readyForExternalClaim)}`,
      required: "Public claim remains blocked until release quality, live proof, and launch-packet external-claim guard are all true.",
      command: "copy System Status quality receipt after readyForExternalClaim=true",
      nextAction: "Run node scripts/capture-output-quality-audit.mjs --write after live proof is ready, then paste readyForExternalClaim=true and the external claim guard receipt.",
    },
  ];
}

function publishLaunchProofEvidenceReceipt(evidence) {
  const claimGuard = publishEvidenceExternalClaimGuard(evidence);
  const ready = claimGuard.readyForExternalClaim;
  const status = ready ? "ready for public proof review" : "guarded until external claim ready";
  const repo = repoDisplayContext(evidence);
  const fields = publishLaunchProofEvidenceFields(evidence);
  const blockerLines = publishEvidenceExternalClaimBlockerLines(evidence, claimGuard);
  return [
    "JooPark Launch Proof Evidence Receipt",
    `Status: ${status}`,
    `Repo: ${valueOrPending(repo.displayRepo)}`,
    `Evidence repo: ${valueOrPending(repo.evidenceRepo)}${repo.repoPlaceholderResolved ? " (placeholder resolved from suggestedRepo)" : ""}`,
    `Repo resolution: ${valueOrPending(repo.repoResolution)}`,
    "",
    "Evidence fields to fill:",
    ...fields.map((field) => `- ${field.label}: ${field.value}`),
    "",
    "Required proof commands:",
    ...fields.map((field, index) => `${index + 1}. ${field.command}`),
    "",
    "Next proof actions:",
    ...fields.map((field, index) => `${index + 1}. ${field.label}: nextAction=${field.nextAction}`),
    "",
    "Acceptance criteria:",
    ...fields.map((field) => `- ${field.label}: ${field.required}`),
    "",
    ...publishEvidenceExternalClaimGuardLines(evidence, claimGuard),
    "",
    "Blockers:",
    ...blockerLines,
    "",
    "Stop condition: do not post public launch copy, archive proof, or claim readyForExternalClaim until all six evidence fields are live, fresh, linked, successful, and readyForExternalClaim=true.",
  ].join("\n");
}

function formatPublishEvidenceMarkdown(evidence) {
  const site = evidence.pagesSite?.site || {};
  const nextAction = evidence.nextAction || {};
  const immediateNextAction = evidence.immediateNextAction || nextAction;
  const deferredNextAction = evidence.deferredNextAction || null;
  const repo = repoDisplayContext(evidence);
  const shareUpdate = evidence.shareUpdate || publishEvidenceShareUpdate(evidence);
  const launchAnnouncement = evidence.launchAnnouncement || publishLaunchAnnouncement(evidence);
  const postLaunchVerificationReceipt = evidence.postLaunchVerificationReceipt || publishPostLaunchVerificationReceipt(evidence);
  const launchProofEvidenceReceipt = evidence.launchProofEvidenceReceipt || publishLaunchProofEvidenceReceipt(evidence);
  const lines = [
    "# JooPark Publish Evidence",
    "",
    `- mode: ${evidence.mode}`,
    `- repo: ${valueOrPending(repo.displayRepo)}`,
    `- displayRepo: ${valueOrPending(repo.displayRepo)}`,
    `- evidenceRepo: ${valueOrPending(repo.evidenceRepo)}${repo.repoPlaceholderResolved ? " (placeholder resolved from suggestedRepo)" : ""}`,
    `- suggestedRepo: ${valueOrPending(evidence.suggestedRepo)}`,
    `- repoResolution: ${valueOrPending(repo.repoResolution)}`,
    `- repoPlaceholderResolved: ${repo.repoPlaceholderResolved}`,
    `- repoReplacementHint: ${valueOrPending(evidence.repoReplacementHint)}`,
    `- repoEvidenceReady: ${evidence.repoEvidenceReady}`,
    `- generatedAt: ${evidence.generatedAt}`,
    `- evidenceFresh: ${evidence.evidenceFresh}`,
    `- evidenceExpiresAt: ${evidence.evidenceExpiresAt}`,
    `- evidenceMaxAgeHours: ${evidence.evidenceMaxAgeHours}`,
    `- postPublishEvidenceReady: ${evidence.postPublishEvidenceReady}`,
    `- publishDispatchReady: ${evidence.publishDispatchReady}`,
    `- dispatchSuggestionStatus: ${valueOrPending(evidence.dispatchSuggestionStatus)}`,
    `- immediateNextAction: ${valueOrPending(immediateNextAction.key)}`,
    `- deferredNextAction: ${valueOrPending(deferredNextAction?.key)}`,
    `- suggestedDispatchCommands: ${Array.isArray(evidence.suggestedDispatchCommands) ? evidence.suggestedDispatchCommands.length : 0}`,
    `- withheldDispatchCommands: ${Array.isArray(evidence.withheldDispatchCommands) ? evidence.withheldDispatchCommands.length : 0}`,
    "",
    "## Launch proof gate",
    "- Treat this report as launch proof only when `repoEvidenceReady: true`, `evidenceFresh: true`, and `postPublishEvidenceReady: true` are all present.",
    `- Current repoEvidenceReady: ${evidence.repoEvidenceReady}`,
    `- Current evidenceFresh: ${evidence.evidenceFresh}`,
    `- Current postPublishEvidenceReady: ${evidence.postPublishEvidenceReady}`,
    "",
    "## Next action",
    `- nextAction: ${valueOrPending(immediateNextAction.key || nextAction.key)}`,
    "### Immediate action",
    `- key: ${valueOrPending(immediateNextAction.key)}`,
    `- label: ${valueOrPending(immediateNextAction.label)}`,
    `- status: ${valueOrPending(publishEvidenceActionStatus(immediateNextAction))}`,
    `- source: ${valueOrPending(immediateNextAction.source)}`,
    `- detail: ${valueOrPending(immediateNextAction.detail)}`,
    `- successCondition: ${valueOrPending(immediateNextAction.successCondition)}`,
    `- command: ${publishEvidenceActionCommand(immediateNextAction) ? `\`${publishEvidenceActionCommand(immediateNextAction)}\`` : "not available"}`,
    `- commandCount: ${valueOrPending(immediateNextAction.commandCount)}`,
    `- withheldCommandCount: ${valueOrPending(immediateNextAction.withheldCommandCount)}`,
    "",
    "### Install path options",
    ...publishEvidenceInstallPathLines(evidence, immediateNextAction),
    "",
    "### Deferred evidence capture",
    `- key: ${valueOrPending(deferredNextAction?.key)}`,
    `- label: ${valueOrPending(deferredNextAction?.label)}`,
    `- detail: ${valueOrPending(deferredNextAction?.detail)}`,
    `- command: ${publishEvidenceActionCommand(deferredNextAction) ? `\`${publishEvidenceActionCommand(deferredNextAction)}\`` : "not available"}`,
    "",
    "## Share update",
    "```text",
    shareUpdate,
    "```",
    "",
    "## Launch announcement",
    "```text",
    launchAnnouncement,
    "```",
    "",
    "## Post-launch verification receipt",
    "```text",
    postLaunchVerificationReceipt,
    "```",
    "",
    "## Launch proof evidence receipt",
    "```text",
    launchProofEvidenceReceipt,
    "```",
    "",
    "## Pages site",
    `- checked: ${evidence.pagesSite.checked}`,
    `- ready: ${evidence.pagesSite.ready}`,
    `- html_url: ${valueOrPending(site.html_url)}`,
    `- status: ${valueOrPending(site.status)}`,
    `- proof_source: ${valueOrPending(pageSiteProofSource(evidence.pagesSite))}`,
    `- https_enforced: ${valueOrPending(site.https_enforced)}`,
  ];
  if (evidence.pagesSite.liveUrl) {
    lines.push(
      `- live_url_checked: ${evidence.pagesSite.liveUrl.checked}`,
      `- live_url_ready: ${evidence.pagesSite.liveUrl.ready}`,
      `- live_http_status: ${valueOrPending(evidence.pagesSite.liveUrl.httpStatus)}`,
      `- live_effective_url: ${valueOrPending(evidence.pagesSite.liveUrl.effectiveUrl)}`,
      `- live_content_type: ${valueOrPending(evidence.pagesSite.liveUrl.contentType)}`,
    );
  }
  if (evidence.pagesSite.error) lines.push(`- error: ${evidence.pagesSite.error}`);

  lines.push("", "## Workflow runs");
  for (const run of evidence.workflowRuns) {
    const latest = run.latestRun || {};
    lines.push(
      `- ${run.workflowFile}: checked=${run.checked}; ready=${run.ready}; status=${valueOrPending(latest.status)}; conclusion=${valueOrPending(latest.conclusion)}; url=${valueOrPending(latest.url)}; headSha=${valueOrPending(latest.headSha)}`,
    );
    if (run.error) lines.push(`  error: ${run.error}`);
  }

  lines.push("", "## Blockers");
  if (evidence.blockers.length) {
    for (const blocker of evidence.blockers) lines.push(`- ${blocker}`);
  } else {
    lines.push("- none");
  }

  lines.push("", "## Repo replacement guard");
  lines.push(`- ${evidence.repoReplacementHint}`);
  lines.push("- Treat the OWNER/REPO commands below as templates until repoEvidenceReady is true.");
  lines.push("- Dispatch commands stay withheld until `allDispatchReady: true` in `data/publish-dispatch-plan.json`.");
  if (Array.isArray(evidence.suggestedCommands) && evidence.suggestedCommands.length) {
    lines.push("", "## Suggested repo commands");
    lines.push("- Safe verification and evidence-capture commands only; this section must not include workflow dispatch commands before readiness.");
    for (const command of evidence.suggestedCommands) lines.push(`- \`${command}\``);
  }
  lines.push("", "## Suggested dispatch commands");
  lines.push(`- dispatchSuggestionStatus: ${valueOrPending(evidence.dispatchSuggestionStatus)}`);
  if (Array.isArray(evidence.suggestedDispatchCommands) && evidence.suggestedDispatchCommands.length) {
    for (const command of evidence.suggestedDispatchCommands) lines.push(`- \`${command}\``);
  } else {
    lines.push("- none until allDispatchReady: true.");
  }
  if (Array.isArray(evidence.withheldDispatchCommands) && evidence.withheldDispatchCommands.length) {
    lines.push("", "## Withheld dispatch commands");
    lines.push("- Do not run until allDispatchReady: true.");
    lines.push(`- dispatchSuggestionStatus: ${valueOrPending(evidence.dispatchSuggestionStatus)}`);
    for (const command of evidence.withheldDispatchCommands) lines.push(`- \`${command}\``);
  }
  if (Array.isArray(evidence.templateDispatchCommands) && evidence.templateDispatchCommands.length) {
    lines.push("", "## Template withheld dispatch commands");
    lines.push("- Replace OWNER/REPO and do not run until allDispatchReady: true.");
    for (const command of evidence.templateDispatchCommands) lines.push(`- \`${command}\``);
  }
  lines.push("", "## Next commands");
  lines.push("- Template verification and evidence-capture commands only; dispatch commands are listed separately.");
  for (const command of evidence.commands) lines.push(`- \`${command}\``);
  return `${lines.join("\n")}\n`;
}

function publishEvidenceNextAction({ live, repo, repoEvidenceReady, pagesSite, workflowRuns, blockers, commandRepo, suggestedRepo, publishDispatchReady }) {
  const suggestedCommandRepo = suggestedRepo || commandRepo || "OWNER/REPO";
  if (!live) {
    return {
      key: "capture-live-evidence",
      label: "Capture live publish evidence",
      detail: "Dry-run evidence is not launch proof; run live capture after workflow installation and dispatch.",
      command: `node scripts/capture-publish-evidence.mjs --live --repo ${suggestedCommandRepo} --markdown`,
    };
  }
  if (isPlaceholderRepo(repo)) {
    return {
      key: "replace-repo-placeholder",
      label: "Replace OWNER/REPO",
      detail: "Use the exact GitHub owner/name repo before dispatch, live capture, or launch proof sharing.",
      command: `node scripts/plan-publish-dispatch.mjs --live --repo ${suggestedCommandRepo}`,
    };
  }
  if (!repoEvidenceReady) {
    return {
      key: "resolve-repo-evidence",
      label: "Resolve repo evidence",
      detail: "The target repository could not be confirmed; verify gh authentication and repo access.",
      command: `gh repo view ${commandRepo}`,
    };
  }
  if (!publishDispatchReady) {
    return {
      key: "capture-live-evidence",
      label: "Capture live publish evidence",
      detail: "Run live capture after workflow installation, guarded dispatch, and completed workflow runs; proof-only API checks are expected to fail before dispatch.",
      command: `node scripts/capture-publish-evidence.mjs --live --repo ${suggestedCommandRepo} --markdown`,
    };
  }
  if (!pagesSite.ready) {
    return {
      key: "verify-pages-site",
      label: "Verify GitHub Pages site",
      detail: "GitHub Pages must expose html_url plus API status=built or live URL HTTP 2xx before launch proof is ready.",
      command: `gh api repos/${commandRepo}/pages`,
    };
  }
  const missingRun = workflowRuns.find((run) => !run.latestRun);
  if (missingRun) {
    return {
      key: `dispatch-${missingRun.key}`,
      label: `Dispatch ${missingRun.workflowFile}`,
      detail: "The workflow has no latest run evidence yet; dispatch it before capturing launch proof.",
      command: missingRun.dispatchCommand || workflowDispatchCommand(missingRun.workflowFile, commandRepo, missingRun.dispatchFields || []),
    };
  }
  const incompleteRun = workflowRuns.find((run) => run.latestRun && !run.ready);
  if (incompleteRun) {
    return {
      key: `inspect-${incompleteRun.key}-run`,
      label: `Inspect ${incompleteRun.workflowFile}`,
    detail: "A selected recent workflow proof run must be completed with a success conclusion before launch proof is ready.",
      command: incompleteRun.evidenceCommand || workflowEvidenceCommand(incompleteRun.workflowFile, commandRepo),
    };
  }
  if (blockers.length) {
    return {
      key: "resolve-publish-blockers",
      label: "Resolve publish blockers",
      detail: blockers[0],
      command: `node scripts/capture-publish-evidence.mjs --live --repo ${commandRepo} --markdown`,
    };
  }
  return {
    key: "share-launch-proof",
    label: "Share launch proof",
    status: "ready",
    detail: "Pages and workflow run evidence are fresh and complete.",
    command: `node scripts/capture-publish-evidence.mjs --live --repo ${commandRepo} --markdown`,
  };
}

const pagesSite = pageSiteEvidence(repo);
const repoEvidenceReady = !isPlaceholderRepo(repo);
const workflowRuns = workflowEvidencePlans.map((workflow) => latestWorkflowRun(workflow, repo));
const blockers = [];

if (!live) blockers.push("live evidence was not checked; pass --live after dispatch");
if (live && !repo) blockers.push("repo was not provided and gh repo view did not resolve nameWithOwner");
if (live && repo === "OWNER/REPO") blockers.push("repo placeholder OWNER/REPO must be replaced before live evidence capture");
if (live && repoEvidenceReady && !pagesSite.ready) blockers.push("GitHub Pages site html_url/status or live URL evidence is not ready");
for (const run of workflowRuns) {
  if (live && repoEvidenceReady && !run.latestRun) blockers.push(`${run.key}: selected workflow proof run was not found`);
  if (live && repoEvidenceReady && run.latestRun && !run.ready) blockers.push(`${run.key}: selected workflow proof run is not completed with success conclusion`);
}

const workflowEvidenceReady = workflowRuns.every((run) => run.ready);
const postPublishEvidenceReady = live && repoEvidenceReady && pagesSite.ready && workflowEvidenceReady && blockers.length === 0;
const generatedAt = new Date();
const evidenceExpiresAt = new Date(generatedAt.getTime() + evidenceMaxAgeHours * 60 * 60 * 1000).toISOString();
const commandRepo = repo || "OWNER/REPO";
const displayRepoContext = repoDisplayContext({ repo, suggestedRepo });
const dispatchContext = publishDispatchSuggestionContext(publishDispatchPlan);
const templateCommands = publishEvidenceCommandSet(commandRepo);
const suggestedCommandRepo = suggestedRepo || displayRepoContext.displayRepo || commandRepo;
const suggestedCommandSet = suggestedRepo ? publishEvidenceCommandSet(suggestedCommandRepo) : { verificationCommands: [], dispatchCommands: [] };
const suggestedDispatchCommands = dispatchContext.publishDispatchReady ? suggestedCommandSet.dispatchCommands : [];
const withheldDispatchCommands = dispatchContext.publishDispatchReady ? [] : publishEvidenceCommandSet(suggestedCommandRepo || commandRepo).dispatchCommands;
const proofNextAction = publishEvidenceNextAction({
  live,
  repo,
  repoEvidenceReady,
  pagesSite,
  workflowRuns,
  blockers,
  commandRepo,
  suggestedRepo,
  publishDispatchReady: dispatchContext.publishDispatchReady,
});
const immediateNextAction = publishEvidenceImmediateNextAction({
  launchExecutionPacket,
  launchReadinessRefresh,
  nextAction: proofNextAction,
  commandRepo,
  suggestedRepo,
});
const deferredNextAction = immediateNextAction?.key && immediateNextAction.key !== proofNextAction.key ? proofNextAction : null;
const nextAction = immediateNextAction?.key ? immediateNextAction : proofNextAction;
const launchInstallPaths = immediateNextAction?.launchInstallPaths || launchInstallPathSnapshot(launchExecutionPacket);
const payload = {
  status: "pass",
  mode: live ? "live" : "dry-run",
  generatedAt: generatedAt.toISOString(),
  evidenceFresh: true,
  evidenceExpiresAt,
  evidenceMaxAgeHours,
  suggestedRepo,
  repoReplacementHint: suggestedRepo ? `Replace OWNER/REPO with ${suggestedRepo}` : "Replace OWNER/REPO with the exact GitHub owner/name repo",
  repo,
  displayRepo: displayRepoContext.displayRepo,
  evidenceRepo: displayRepoContext.evidenceRepo,
  repoResolution: displayRepoContext.repoResolution,
  repoPlaceholderResolved: displayRepoContext.repoPlaceholderResolved,
  suggestedRepoEvidenceRepo: suggestedRepo || "",
  suggestedRepoResolution: suggestedRepo ? "source_repo" : "",
  suggestedRepoEvidenceLine: suggestedRepo ? `Evidence repo: ${suggestedRepo}` : "",
  suggestedRepoResolutionLine: suggestedRepo ? "Repo resolution: source_repo" : "",
  repoEvidenceReady,
  pagesSite,
  workflowEvidencePlans,
  workflowRuns,
  pagesEvidenceReady: pagesSite.ready,
  workflowEvidenceReady,
  postPublishEvidenceReady,
  blockers,
  publishDispatchPlanSource: dispatchContext.publishDispatchPlanSource,
  publishDispatchReady: dispatchContext.publishDispatchReady,
  allDispatchReady: dispatchContext.publishDispatchReady,
  launchPacketReadyForExternalClaim: launchExecutionPacket?.readyForExternalClaim === true,
  dispatchSuggestionStatus: dispatchContext.dispatchSuggestionStatus,
  nextAction,
  immediateNextAction,
  immediateNextActionSource: immediateNextAction?.source || "",
  immediateActionCommandCount: Number(immediateNextAction?.commandCount || 0),
  immediateActionWithheldCommandCount: Number(immediateNextAction?.withheldCommandCount || 0),
  launchInstallPaths,
  deferredNextAction,
  commands: templateCommands.verificationCommands,
  templateVerificationCommands: templateCommands.verificationCommands,
  templateDispatchCommands: templateCommands.dispatchCommands,
  suggestedCommands: suggestedCommandSet.verificationCommands,
  suggestedVerificationCommands: suggestedCommandSet.verificationCommands,
  suggestedDispatchCommands,
  withheldDispatchCommands,
  safeSuggestedCommandCount: suggestedCommandSet.verificationCommands.length,
  withheldDispatchCommandCount: withheldDispatchCommands.length,
  suggestedDispatchCommandCount: suggestedDispatchCommands.length,
  documentationSignals: [
    "GitHub REST: Get a GitHub Pages site returns html_url and may include status.",
    "Workflow-based GitHub Pages proof can use the live html_url HTTP 2xx check when API status is empty.",
    "GitHub REST/CLI workflow run evidence uses status and conclusion.",
  ],
};

Object.assign(payload, publishEvidenceDispatchCommandState(payload));
{
  const externalClaimGuard = publishEvidenceExternalClaimGuard(payload);
  Object.assign(payload, {
    publicLaunchProofReady: externalClaimGuard.publicLaunchProofReady,
    readyForExternalClaim: externalClaimGuard.readyForExternalClaim,
    externalClaimGuardStatus: externalClaimGuard.status,
    externalClaimBlockers: externalClaimGuard.blockers,
    externalClaimGuard,
  });
}

payload.shareUpdate = publishEvidenceShareUpdate(payload);
payload.launchAnnouncement = publishLaunchAnnouncement(payload);
payload.postLaunchVerificationReceipt = publishPostLaunchVerificationReceipt(payload);
payload.launchProofEvidenceFields = publishLaunchProofEvidenceFields(payload);
payload.launchProofEvidenceFieldCount = payload.launchProofEvidenceFields.length;
payload.launchProofEvidenceFieldCoverage = payload.launchProofEvidenceFieldCount >= 6 ? 1 : 0;
payload.launchProofEvidenceReceipt = publishLaunchProofEvidenceReceipt(payload);

if (write) {
  const outPath = resolve(root, outRel);
  payload.writtenTo = relative(root, outPath).replaceAll("\\", "/");
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

console.log(markdown ? formatPublishEvidenceMarkdown(payload) : JSON.stringify(payload, null, 2));
