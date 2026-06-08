#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const write = rawArgs.includes("--write");
const markdown = rawArgs.includes("--markdown");
const productLoopRel = argValue("--product-loop") || "autoresearch-results/joopark-product-loop.json";
const outputQualityRel = argValue("--output-quality") || "data/output-quality-audit.json";
const experimentId = "product-loop-summary-gate-parity";
const summaryExperimentIds = new Set([experimentId]);

function argValue(name) {
  const inline = rawArgs.find((arg) => arg.startsWith(`${name}=`));
  if (inline) return inline.slice(name.length + 1);
  const index = rawArgs.indexOf(name);
  return index >= 0 ? rawArgs[index + 1] || "" : "";
}

function readJson(relPath, fallback = null) {
  try {
    return JSON.parse(readFileSync(resolve(root, relPath), "utf-8"));
  } catch {
    return fallback;
  }
}

function sameJson(left, right) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

function yesNo(value) {
  return value ? "true" : "false";
}

function statusFromOutputQuality(outputQuality) {
  if (!outputQuality?.releaseQualityReady) return "release-quality-blocked";
  if (outputQuality.readyForExternalClaim) return "ready-for-external-claim";
  if (outputQuality.publicLaunchProofReady) return "release-quality-ready-public-launch-proof-ready";
  return "release-quality-ready-public-launch-blocked";
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

function parityScore({ productLoop, latestGate, publishPatch }) {
  return Number(sameJson(latestGateForParity(productLoop?.latestGate), latestGateForParity(latestGate))) +
    Number(trackedPublishParity(productLoop?.publish || {}, publishPatch));
}

function changedPublishKeys(beforePublish, patch) {
  return Object.entries(patch)
    .filter(([key, value]) => beforePublish?.[key] !== value)
    .map(([key]) => key);
}

function experimentTime(experiment) {
  const time = Date.parse(experiment?.generatedAt || "");
  return Number.isFinite(time) ? time : 0;
}

function experimentSummary(experiment) {
  if (!experiment || typeof experiment !== "object") return null;
  return {
    id: experiment.id || "",
    primaryMetric: experiment.primaryMetric || "",
    baseline: experiment.baseline ?? null,
    candidate: experiment.candidate ?? null,
    decision: experiment.decision || "",
    generatedAt: experiment.generatedAt || "",
  };
}

function futureExperimentSummaries(experiments, nowMs) {
  const source = Array.isArray(experiments) ? experiments : [];
  return source
    .filter((item) => experimentTime(item) > nowMs + 60000)
    .map(experimentSummary)
    .filter(Boolean);
}

function latestExperimentSummary(experiments, nowMs, { excludeIds = [] } = {}) {
  const source = Array.isArray(experiments) ? experiments : [];
  const excluded = new Set(excludeIds);
  const eligible = source.filter((item) => !excluded.has(item?.id));
  const currentOrPast = eligible.filter((item) => experimentTime(item) <= nowMs + 60000);
  const candidates = currentOrPast.length ? currentOrPast : eligible;
  const latest = candidates
    .filter((item) => item && typeof item === "object")
    .reduce((best, item) => {
      if (!best) return item;
      return experimentTime(item) >= experimentTime(best) ? item : best;
    }, null);
  return experimentSummary(latest);
}

function upsertExperiment(experiments, experiment, { refresh = true } = {}) {
  const source = Array.isArray(experiments) ? experiments : [];
  const existingIndex = source.findIndex((item) => item?.id === experiment.id);
  if (existingIndex < 0) return [...source, experiment];
  if (!refresh) return source;
  return source.map((item, index) => index === existingIndex ? experiment : item);
}

const productLoop = readJson(productLoopRel, {});
const outputQuality = readJson(outputQualityRel, {});
const latestGate = outputQuality?.latestGate || null;

if (!latestGate) {
  console.error(`Missing latestGate in ${outputQualityRel}`);
  process.exit(1);
}

const generatedAt = new Date().toISOString();
const publishPatch = publishPatchFromOutputQuality(outputQuality);
const status = statusFromOutputQuality(outputQuality);
const baseline = parityScore({ productLoop, latestGate, publishPatch });
const beforeGateChecks = productLoop?.latestGate?.checks || {};
const changedPublish = changedPublishKeys(productLoop?.publish || {}, publishPatch);
const latestGateUpdated = !sameJson(productLoop?.latestGate, latestGate);
const gateChanged = !sameJson(latestGateForParity(productLoop?.latestGate), latestGateForParity(latestGate));
const statusChanged = productLoop?.status !== status;
const summarySyncOutputQualityStale = productLoop.summarySync?.outputQualityGeneratedAt !== (outputQuality?.generatedAt || "");
const summarySyncParityMissing = productLoop.summarySync?.gateParityReady !== true || productLoop.summarySync?.publishParityReady !== true;
const metadataMissing = !productLoop?.summarySync ||
  productLoop.summarySync.source !== "scripts/sync-product-loop-summary.mjs" ||
  productLoop.summarySync.productLoopPath !== productLoopRel ||
  productLoop.summarySync.outputQualityPath !== outputQualityRel;
const semanticSyncNeeded = baseline < 2 || latestGateUpdated || gateChanged || changedPublish.length > 0 || statusChanged || metadataMissing || summarySyncOutputQualityStale || summarySyncParityMissing;
const existingSyncExperiment = Array.isArray(productLoop?.experiments)
  ? productLoop.experiments.find((item) => item?.id === experimentId)
  : null;
const syncExperimentShouldRefresh = !existingSyncExperiment || baseline < 2 || latestGateUpdated || gateChanged || changedPublish.length > 0 || summarySyncOutputQualityStale || summarySyncParityMissing;
const candidateLoop = semanticSyncNeeded
  ? {
      ...productLoop,
      generatedAt,
      status,
      latestGate,
      publish: {
        ...(productLoop?.publish || {}),
        ...publishPatch,
      },
      summarySync: {
        generatedAt,
        source: "scripts/sync-product-loop-summary.mjs",
        productLoopPath: productLoopRel,
        outputQualityPath: outputQualityRel,
        outputQualityGeneratedAt: outputQuality?.generatedAt || "",
        gateParityReady: true,
        publishParityReady: true,
        gateChanged,
        latestGateUpdated,
        changedPublishKeys: changedPublish,
        baselineParityCoverage: baseline,
        candidateParityCoverage: 2,
        syncExperimentUpdated: syncExperimentShouldRefresh,
      },
    }
  : {
      ...productLoop,
    };

const experiment = {
  id: experimentId,
  primaryMetric: "productLoopSummaryParityCoverage",
  baseline,
  candidate: 2,
  decision: "keep",
  generatedAt,
  hypothesis: "The AutoResearch product-loop summary should carry the same latest gate and launch publish blockers as the final output-quality audit so operators do not see stale pass counts or stale external-claim state.",
  evidence: [
    `Baseline product-loop latestGate reported ${Number(beforeGateChecks.pass || 0)} pass/${Number(beforeGateChecks.total || 0)} total while ${outputQualityRel} reported ${Number(latestGate.checks?.pass || 0)} pass/${Number(latestGate.checks?.total || 0)} total.`,
    `scripts/sync-product-loop-summary.mjs now updates ${productLoopRel} from ${outputQualityRel} and records gateParityReady=true plus publishParityReady=true.`,
    `Tracked publish blockers are synchronized: remoteWorkflowFilesReady=${yesNo(publishPatch.remoteWorkflowFilesReady)}, remoteWorkflowVisibilityReady=${yesNo(publishPatch.remoteWorkflowVisibilityReady)}, workflowScopeInstallBlocked=${yesNo(publishPatch.workflowScopeInstallBlocked)}, postPublishEvidenceReady=${yesNo(publishPatch.postPublishEvidenceReady)}, readyForExternalClaim=${yesNo(publishPatch.readyForExternalClaim)}.`,
  ],
  externalComparison: {
    label: "Operational release summaries are only useful when their headline status matches the underlying audit receipt; the sync keeps the product-loop summary aligned with the evidence source before handoff.",
    urls: [],
  },
};

candidateLoop.experiments = semanticSyncNeeded
  ? upsertExperiment(productLoop?.experiments, experiment, {
      refresh: syncExperimentShouldRefresh,
    })
  : Array.isArray(productLoop?.experiments) ? productLoop.experiments : [];
const syncNowMs = Date.parse(generatedAt);
const futureExperiments = futureExperimentSummaries(candidateLoop.experiments, syncNowMs);
candidateLoop.latestExperiment = latestExperimentSummary(candidateLoop.experiments, syncNowMs, {
  excludeIds: [...summaryExperimentIds],
});
candidateLoop.latestSyncExperiment = experimentSummary(
  candidateLoop.experiments.find((item) => item?.id === experimentId),
);
candidateLoop.summarySync.futureDatedExperimentCount = futureExperiments.length;
candidateLoop.summarySync.futureDatedExperimentIds = futureExperiments.map((item) => item.id);

const after = {
  gateParityReady: sameJson(latestGateForParity(candidateLoop.latestGate), latestGateForParity(latestGate)),
  publishParityReady: trackedPublishParity(candidateLoop.publish, publishPatch),
  parityCoverage: parityScore({ productLoop: candidateLoop, latestGate, publishPatch }),
};
const writeApplied = write && semanticSyncNeeded;

const payload = {
  status: after.gateParityReady && after.publishParityReady ? "pass" : "fail",
  generatedAt,
  write,
  writeApplied,
  productLoopPath: productLoopRel,
  outputQualityPath: outputQualityRel,
  outputQualityGeneratedAt: outputQuality?.generatedAt || "",
  baselineParityCoverage: baseline,
  candidateParityCoverage: after.parityCoverage,
  gateChanged,
  latestGateUpdated,
  summarySyncOutputQualityStale,
  summarySyncParityMissing,
  semanticSyncNeeded,
  changedPublishKeys: changedPublish,
  syncExperimentUpdated: syncExperimentShouldRefresh,
  latestExperiment: candidateLoop.latestExperiment,
  latestSyncExperiment: candidateLoop.latestSyncExperiment,
  futureDatedExperimentCount: futureExperiments.length,
  futureDatedExperimentIds: futureExperiments.map((item) => item.id),
  before: {
    latestGateChecks: beforeGateChecks,
    publish: productLoop?.publish || {},
  },
  after,
  experiment,
};

if (writeApplied) {
  const target = resolve(root, productLoopRel);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, `${JSON.stringify(candidateLoop, null, 2)}\n`, "utf-8");
}

if (markdown) {
  console.log([
    "# JooPark Product Loop Summary Sync",
    "",
    `- status: ${payload.status}`,
    `- outputQualityGeneratedAt: ${payload.outputQualityGeneratedAt}`,
    `- baselineParityCoverage: ${payload.baselineParityCoverage}/2`,
    `- candidateParityCoverage: ${payload.candidateParityCoverage}/2`,
    `- gateChanged: ${yesNo(payload.gateChanged)}`,
    `- latestGateUpdated: ${yesNo(payload.latestGateUpdated)}`,
    `- summarySyncOutputQualityStale: ${yesNo(payload.summarySyncOutputQualityStale)}`,
    `- summarySyncParityMissing: ${yesNo(payload.summarySyncParityMissing)}`,
    `- semanticSyncNeeded: ${yesNo(payload.semanticSyncNeeded)}`,
    `- writeApplied: ${yesNo(payload.writeApplied)}`,
    `- changedPublishKeys: ${payload.changedPublishKeys.length ? payload.changedPublishKeys.join(", ") : "none"}`,
    `- syncExperimentUpdated: ${yesNo(payload.syncExperimentUpdated)}`,
    `- latestExperiment: ${payload.latestExperiment?.id || "none"}`,
    `- futureDatedExperiments: ${payload.futureDatedExperimentCount}`,
  ].join("\n"));
} else {
  console.log(JSON.stringify(payload, null, 2));
}
