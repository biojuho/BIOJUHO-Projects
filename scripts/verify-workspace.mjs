#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const summaryRel = "autoresearch-results/verify-workspace-summary.json";
const directionLogRel = "docs/product-direction.md";

const syncArtifacts = process.argv.includes("--sync-artifacts");
const releaseReadinessCommand = syncArtifacts
  ? "node scripts/audit-release-readiness.mjs --run-gates --format=summary"
  : "node scripts/audit-release-readiness.mjs --format=summary";
const releaseReadinessArgs = syncArtifacts
  ? ["scripts/audit-release-readiness.mjs", "--run-gates", "--format=summary"]
  : ["scripts/audit-release-readiness.mjs", "--format=summary"];
const gateSteps = [
  {
    id: "release_readiness_gates",
    command: releaseReadinessCommand,
    args: releaseReadinessArgs,
    timeoutMs: 12 * 60 * 1000,
  },
];
const artifactSyncSteps = [
  {
    id: "launch_readiness_refresh",
    command: "node scripts/refresh-launch-readiness.mjs --repo biojuho/BIOJUHO-Projects --write",
    args: ["scripts/refresh-launch-readiness.mjs", "--repo", "biojuho/BIOJUHO-Projects", "--write"],
    timeoutMs: 3 * 60 * 1000,
  },
  {
    id: "product_loop_summary_sync",
    command: "node scripts/sync-product-loop-summary.mjs --write --markdown",
    args: ["scripts/sync-product-loop-summary.mjs", "--write", "--markdown"],
    timeoutMs: 60 * 1000,
  },
];
const steps = syncArtifacts ? [...gateSteps, ...artifactSyncSteps] : gateSteps;

function readJson(relPath, fallback = null) {
  try {
    return JSON.parse(readFileSync(resolve(root, relPath), "utf-8"));
  } catch {
    return fallback;
  }
}

function readText(relPath, fallback = "") {
  try {
    return readFileSync(resolve(root, relPath), "utf-8");
  } catch {
    return fallback;
  }
}

function writeJson(relPath, payload) {
  const target = resolve(root, relPath);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

function redactLocalPaths(value) {
  return String(value || "")
    .replaceAll(root, "project-root")
    .replace(/\/Users\/[^\s"']+/g, "<local-path>");
}

function auditLockSnapshot() {
  const relPath = "dist/.release-readiness-audit.lock";
  const path = resolve(root, relPath);
  const ownerPath = resolve(path, "owner.json");
  const owner = existsSync(ownerPath) ? readJson(ownerPath, null) : null;
  return {
    path: relPath,
    exists: existsSync(path),
    ownerExists: existsSync(ownerPath),
    ownerPid: Number.isInteger(Number(owner?.pid)) ? Number(owner.pid) : null,
    ownerCommand: redactLocalPaths(owner?.command || ""),
    ownerStartedAt: owner?.startedAt || "",
  };
}

function runStep(step) {
  const startedAt = new Date().toISOString();
  const startedMs = Date.now();
  console.error(`[verify-workspace] start ${step.id}: ${step.command}`);
  const result = spawnSync(process.execPath, step.args, {
    cwd: root,
    env: {
      ...process.env,
      JOOPARK_VERIFY_WORKSPACE_RUNNER: "1",
    },
    stdio: "inherit",
    timeout: step.timeoutMs,
    killSignal: "SIGTERM",
  });
  const durationMs = Date.now() - startedMs;
  const releaseReadiness = step.id === "release_readiness_gates"
    ? readJson("autoresearch-results/release-readiness-summary.json", {})
    : {};
  const status = result.status === 0 && !result.error && !result.signal
    ? "pass"
    : releaseReadiness.status === "blocked" && !result.error && !result.signal
      ? "blocked"
      : "fail";
  console.error(`[verify-workspace] ${status} ${step.id} (${Math.round(durationMs / 1000)}s)`);
  return {
    id: step.id,
    command: step.command,
    status,
    code: result.status,
    signal: result.signal || "",
    error: result.error ? result.error.message : "",
    startedAt,
    finishedAt: new Date().toISOString(),
    durationMs,
    timeoutMs: step.timeoutMs,
  };
}

function gateSummary(checks = {}) {
  return `${Number(checks.pass || 0)} pass, ${Number(checks.fail || 0)} fail, ${Number(checks.notRun || 0)} not_run, ${Number(checks.blocked || 0)} blocked`;
}

function finiteNumberOr(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function sameJson(left, right) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

function latestGateForParity(gate) {
  const evidenceDowngradeGuard = gate?.evidenceDowngradeGuard && typeof gate.evidenceDowngradeGuard === "object"
    ? {
        ...gate.evidenceDowngradeGuard,
        previousGeneratedAt: "",
        previousAgeHours: null,
      }
    : undefined;
  return {
    ...(gate || {}),
    evidenceDowngradeGuard,
  };
}

function publishPatchFromOutputQuality(outputQuality) {
  const publishState = outputQuality?.publishState || {};
  const dispatchState = outputQuality?.dispatchState || {};
  return {
    repoEvidenceReady: !!dispatchState.repoEvidenceReady,
    remoteWorkflowVisibilityReady: !!dispatchState.remoteWorkflowVisibilityReady,
    allDispatchReady: !!dispatchState.allDispatchReady,
    postPublishEvidenceReady: !!publishState.postPublishEvidenceReady,
    remoteWorkflowFilesReady: !!dispatchState.remoteWorkflowFilesReady,
    workflowScopeInstallBlocked: !!dispatchState.workflowScopeInstallBlocked,
    readyForExternalClaim: !!outputQuality.readyForExternalClaim,
  };
}

function trackedPublishParity(publish, patch) {
  return Object.entries(patch).every(([key, value]) => publish?.[key] === value);
}

function latestDirectionLoopNumber(markdownText) {
  const matches = Array.from(markdownText.matchAll(/^## Loop (\d+) Decision\s*$/gm));
  if (!matches.length) return 0;
  return Math.max(...matches.map((match) => Number(match[1] || 0)).filter(Number.isFinite));
}

function artifactSnapshot() {
  const releaseSummary = readJson("autoresearch-results/release-readiness-summary.json", {});
  const launchReadiness = readJson("data/launch-readiness-refresh.json", {});
  const outputQuality = readJson("data/output-quality-audit.json", {});
  const productLoop = readJson("autoresearch-results/joopark-product-loop.json", {});
  const directionLoopNumber = latestDirectionLoopNumber(readText(directionLogRel));
  const releaseChecks = releaseSummary.checks || {};
  const launchGateChecks = launchReadiness.latestGate?.checks || outputQuality.latestGate?.checks || {};
  const productGateChecks = productLoop.latestGate?.checks || {};
  const outputLatestGate = outputQuality.latestGate || null;
  const publishPatch = publishPatchFromOutputQuality(outputQuality);
  const nextCandidates = Array.isArray(productLoop.nextCandidates)
    ? productLoop.nextCandidates.filter((item) => typeof item === "string" && item.trim()).map((item) => item.trim())
    : [];
  const nextCandidateListReady = productLoop.summarySync?.nextCandidatesReady === true &&
    nextCandidates.length > 0 &&
    nextCandidates.length === Number(productLoop.summarySync?.nextCandidateCount || 0);
  const productLoopGateParityReady = !!outputLatestGate &&
    sameJson(latestGateForParity(productLoop.latestGate), latestGateForParity(outputLatestGate));
  const productLoopPublishParityReady = trackedPublishParity(productLoop.publish || {}, publishPatch);
  const summarySyncReady = productLoop.summarySync?.source === "scripts/sync-product-loop-summary.mjs" &&
    productLoop.summarySync?.productLoopPath === "autoresearch-results/joopark-product-loop.json" &&
    productLoop.summarySync?.outputQualityPath === "data/output-quality-audit.json" &&
    productLoop.summarySync?.directionLogPath === directionLogRel &&
    productLoop.summarySync?.outputQualityGeneratedAt === (outputQuality.generatedAt || "") &&
    productLoop.summarySync?.gateParityReady === true &&
    productLoop.summarySync?.publishParityReady === true &&
    productLoop.summarySync?.nextCandidatesReady === true &&
    nextCandidateListReady;
  const directionLoopSyncReady = directionLoopNumber > 0 &&
    productLoop.latestDirectionLoop?.number === directionLoopNumber &&
    productLoop.summarySync?.latestDirectionLoopNumber === directionLoopNumber &&
    productLoop.summarySync?.directionLoopReady === true;
  const latestDirectionExperimentReady = productLoop.summarySync?.latestDirectionExperimentReady === true &&
    typeof productLoop.summarySync?.latestDirectionExperimentId === "string" &&
    productLoop.summarySync.latestDirectionExperimentId.length > 0 &&
    productLoop.latestExperiment?.id === productLoop.summarySync.latestDirectionExperimentId &&
    productLoop.latestExperiment.id.startsWith(`loop-${directionLoopNumber}-`);
  const latestDiscoveryExperimentReady = productLoop.summarySync?.latestDiscoveryExperimentReady === true &&
    typeof productLoop.summarySync?.latestDiscoveryExperimentId === "string" &&
    productLoop.summarySync.latestDiscoveryExperimentId.length > 0 &&
    productLoop.latestDiscoveryExperiment?.id === productLoop.summarySync.latestDiscoveryExperimentId &&
    productLoop.latestDiscoveryExperiment.id === "github-project-discovery-artifact";
  const evidenceSyncReady = productLoopGateParityReady && productLoopPublishParityReady && summarySyncReady && directionLoopSyncReady && latestDirectionExperimentReady && latestDiscoveryExperimentReady && nextCandidateListReady;
  return {
    releaseReadiness: {
      path: "autoresearch-results/release-readiness-summary.json",
      status: releaseSummary.status || "missing",
      generatedAt: releaseSummary.generatedAt || "",
      summary: gateSummary(releaseChecks),
      checks: releaseChecks,
    },
    launchReadiness: {
      path: "data/launch-readiness-refresh.json",
      status: launchReadiness.status || "missing",
      generatedAt: launchReadiness.generatedAt || "",
      latestGateSummary: launchReadiness.latestGateSummary || gateSummary(launchGateChecks),
      safeToDispatch: launchReadiness.safeToDispatch === true,
      readyForExternalClaim: launchReadiness.readyForExternalClaim === true,
      workflowScopeInstallBlocked: launchReadiness.workflowScopeInstallBlocked === true,
      dispatchCommandDisposition: launchReadiness.dispatchCommandDisposition || (launchReadiness.readyForExternalClaim === true ? "not_applicable_after_launch_proof" : launchReadiness.safeToDispatch === true ? "active" : "withheld"),
      activeDispatchCommandCount: finiteNumberOr(launchReadiness.activeDispatchCommandCount, 0),
      dispatchCommandReferenceCount: finiteNumberOr(
        launchReadiness.dispatchCommandReferenceCount,
        finiteNumberOr(launchReadiness.suggestedDispatchCommandCount, 0),
      ),
    },
    outputQuality: {
      path: "data/output-quality-audit.json",
      status: outputQuality.status || "missing",
      generatedAt: outputQuality.generatedAt || "",
      releaseQualityReady: outputQuality.releaseQualityReady === true,
      publicLaunchProofReady: outputQuality.publicLaunchProofReady === true,
      readyForExternalClaim: outputQuality.readyForExternalClaim === true,
      latestGateSummary: gateSummary(outputQuality.latestGate?.checks || {}),
    },
    productLoop: {
      path: "autoresearch-results/joopark-product-loop.json",
      status: productLoop.status || "missing",
      generatedAt: productLoop.generatedAt || "",
      latestGateSummary: gateSummary(productGateChecks),
      latestExperiment: productLoop.latestExperiment?.id || "",
      latestDirectionLoop: productLoop.latestDirectionLoop?.id || "",
      latestDirectionLoopNumber: productLoop.latestDirectionLoop?.number || 0,
      latestDirectionExperiment: productLoop.summarySync?.latestDirectionExperimentId || "",
      latestDiscoveryExperiment: productLoop.summarySync?.latestDiscoveryExperimentId || "",
      nextCandidateCount: nextCandidates.length,
      nextCandidates,
    },
    evidenceSync: {
      status: evidenceSyncReady ? "pass" : "fail",
      productLoopGateParityReady,
      productLoopPublishParityReady,
      summarySyncReady,
      nextCandidatesReady: productLoop.summarySync?.nextCandidatesReady === true,
      nextCandidateListReady,
      directionLoopSyncReady,
      latestDirectionExperimentReady,
      latestDiscoveryExperimentReady,
      latestDirectionLoopNumber: directionLoopNumber,
      productLoopLatestDirectionLoopNumber: productLoop.latestDirectionLoop?.number || 0,
      outputQualityGeneratedAt: outputQuality.generatedAt || "",
      productLoopSummarySyncOutputQualityGeneratedAt: productLoop.summarySync?.outputQualityGeneratedAt || "",
      source: "scripts/sync-product-loop-summary.mjs",
      directionLogPath: directionLogRel,
      fullVerifyCommand: "npm run verify:full",
    },
  };
}

function printSummary(payload) {
  const lines = [
    "# JooPark Verify Workspace Summary",
    "",
    `- status: ${payload.status}`,
    `- generatedAt: ${payload.generatedAt}`,
    `- durationSeconds: ${Math.round(payload.durationMs / 1000)}`,
    `- syncArtifacts: ${payload.syncArtifacts}`,
    `- steps: ${payload.stepResults.map((step) => `${step.id}=${step.status}`).join(", ")}`,
    `- releaseReadiness: ${payload.artifacts.releaseReadiness.status} (${payload.artifacts.releaseReadiness.summary})`,
    `- launchReadiness: ${payload.artifacts.launchReadiness.status} (${payload.artifacts.launchReadiness.latestGateSummary})`,
    `- outputQuality: ${payload.artifacts.outputQuality.status} (${payload.artifacts.outputQuality.latestGateSummary})`,
    `- productLoop: ${payload.artifacts.productLoop.status} (${payload.artifacts.productLoop.latestGateSummary})`,
    `- evidenceSync: ${payload.artifacts.evidenceSync.status} (gateParity=${payload.artifacts.evidenceSync.productLoopGateParityReady}, publishParity=${payload.artifacts.evidenceSync.productLoopPublishParityReady}, summarySync=${payload.artifacts.evidenceSync.summarySyncReady}, nextCandidates=${payload.artifacts.evidenceSync.nextCandidatesReady}, nextCandidateList=${payload.artifacts.evidenceSync.nextCandidateListReady}, directionLoop=${payload.artifacts.evidenceSync.directionLoopSyncReady}, discoveryExperiment=${payload.artifacts.evidenceSync.latestDiscoveryExperimentReady})`,
    `- safeToDispatch: ${payload.artifacts.launchReadiness.safeToDispatch}`,
    `- readyForExternalClaim: ${payload.artifacts.outputQuality.readyForExternalClaim}`,
    `- fullVerifyCommand: npm run verify:full`,
    `- summaryArtifact: ${summaryRel}`,
  ];
  console.log(lines.join("\n"));
}

const startedMs = Date.now();
const startedAt = new Date().toISOString();
const auditLockBefore = auditLockSnapshot();
const stepResults = [];
for (const step of steps) {
  const result = runStep(step);
  stepResults.push(result);
  if (result.status !== "pass" && !syncArtifacts) break;
}

const artifacts = artifactSnapshot();
const evidenceSyncRequired = syncArtifacts;
const evidenceSyncPass = !evidenceSyncRequired || artifacts.evidenceSync.status === "pass";
const ranAllSteps = stepResults.length === steps.length;
const hasFailedStep = stepResults.some((step) => step.status === "fail");
const hasBlockedStep = stepResults.some((step) => step.status === "blocked");
const status = ranAllSteps && !hasFailedStep && evidenceSyncPass
  ? hasBlockedStep ? "blocked" : "pass"
  : "fail";
const payload = {
  schemaVersion: "joopark-verify-workspace/v1",
  status,
  generatedAt: new Date().toISOString(),
  startedAt,
  durationMs: Date.now() - startedMs,
  command: syncArtifacts ? "npm run verify:full" : "npm run verify",
  runner: "scripts/verify-workspace.mjs",
  syncArtifacts,
  evidenceSyncRequired,
  evidenceSyncPass,
  stepResults,
  auditLockBefore,
  auditLockAfter: auditLockSnapshot(),
  artifacts,
  externalClaimGuard: "Do not claim readyForExternalClaim until release quality, public launch proof, and external completion claim proof all pass.",
};

writeJson(summaryRel, payload);
printSummary(payload);

if (payload.status !== "pass") process.exit(1);
