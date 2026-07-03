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
const directionLogRel = argValue("--direction-log") || "docs/product-direction.md";
const githubDiscoveryRel = argValue("--github-discovery") || "data/github-project-discovery.json";
const experimentId = "product-loop-summary-gate-parity";
const summaryExperimentIds = new Set([experimentId]);
const githubDiscoveryExperimentId = "github-project-discovery-artifact";

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

function readText(relPath, fallback = "") {
  try {
    return readFileSync(resolve(root, relPath), "utf-8");
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

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
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

function nextCandidatesForStatus(status, publishPatch) {
  if (status === "ready-for-external-claim" || publishPatch.readyForExternalClaim) {
    return [
      "Share the proof-ready launch packet with `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown`.",
      "Archive the release-readiness, launch-readiness, output-quality, publish-evidence, and verify-workspace receipts together with activeDispatchCommandCount=0.",
      "Capture signed GitHub artifact attestation proof only after attestation-url, attestation-id, and gh attestation verify results are available from the remote Pages workflow.",
      "Prepare the main-branch PR bridge under apps/joopark-workspace because the release branch still has no common history with main.",
      "Continue extracting low-state navigation/runtime helpers only after proof-ready launch receipts remain green.",
    ];
  }
  return [
    "Land .github/workflows/joopark-pages.yml and .github/workflows/joopark-drift-watch.yml on the default branch with workflow scope or GitHub UI.",
    "Fill the six post-install evidence intake fields from commit, parity, Actions visibility, dispatch readiness, and verify-launch-handoff proof before any dispatch.",
    "Fill the six launch proof evidence receipt fields from live Pages site, Pages workflow, Drift Watch workflow, evidence freshness, release receipt, and public claim guard proof before external launch copy.",
    "Fill the Pages attestation proof intake with attestation-url, attestation-id, and gh attestation verify results after the remote Pages workflow run.",
    "Rerun node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects until allDispatchReady is true, then dispatch Pages and Drift Watch and capture live publish evidence.",
    "Continue extracting low-state navigation/runtime helpers only where accessibility ownership and state mutation stay clear.",
  ];
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
  const summary = {
    id: experiment.id || "",
    primaryMetric: experiment.primaryMetric || "",
    baseline: experiment.baseline ?? null,
    candidate: experiment.candidate ?? null,
    decision: experiment.decision || "",
    generatedAt: experiment.generatedAt || "",
  };
  if (Array.isArray(experiment.topProjects)) {
    summary.topProjects = experiment.topProjects
      .slice(0, 4)
      .map((project) => {
        if (typeof project === "string") return { nameWithOwner: project };
        const nextAction = String(project?.nextAction || "").replace(/\s+/g, " ").trim();
        return {
          nameWithOwner: String(project?.nameWithOwner || ""),
          relation: String(project?.relation || ""),
          localCheckout: project?.localCheckout === true,
          nextAction: nextAction.length <= 180 ? nextAction : `${nextAction.slice(0, 177).trim()}...`,
        };
      })
      .filter((project) => project.nameWithOwner);
  }
  if (Object.hasOwn(experiment, "topProjectCount")) {
    summary.topProjectCount = Number(experiment.topProjectCount || 0);
  }
  if (Object.hasOwn(experiment, "releaseTargetIncluded")) {
    summary.releaseTargetIncluded = experiment.releaseTargetIncluded === true;
  }
  return summary;
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

function compactText(value, maxLength = 320) {
  const compact = String(value || "").replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) return compact;
  return `${compact.slice(0, maxLength - 3).trim()}...`;
}

function githubDiscoveryMetric(githubDiscovery) {
  const ab = githubDiscovery?.abComparison || {};
  const launchSummary = githubDiscovery?.launchCandidateSummary || {};
  const primaryMetric = ab.primaryMetric || launchSummary.metric || "githubProjectDiscoveryArtifactCount";
  if (primaryMetric === "githubDiscoveryActionableProjectCoverage") {
    return {
      primaryMetric,
      baseline: Number(ab.baselineActionableProjectCoverage || 0),
      candidate: Number(ab.candidateActionableProjectCoverage ?? launchSummary.candidateActionableProjectCoverage ?? 0),
      required: Number(ab.requiredActionableProjectCoverage ?? launchSummary.requiredActionableProjectCoverage ?? 0),
    };
  }
  return {
    primaryMetric,
    baseline: Number(ab.baselineArtifactCount || 0),
    candidate: Number(ab.candidateArtifactCount || 0),
    required: Number(ab.candidateArtifactCount || 0),
  };
}

function slugify(value, fallback = "experiment") {
  const slug = String(value || "")
    .toLowerCase()
    .replace(/`[^`]+`/g, " ")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64)
    .replace(/-+$/g, "");
  return slug || fallback;
}

function normalizedReferenceUrl(rawUrl) {
  const cleaned = String(rawUrl || "")
    .trim()
    .replace(/[`'".,;:]+$/g, "");
  if (!cleaned) return "";
  try {
    return new URL(cleaned).toString();
  } catch {
    return cleaned;
  }
}

function isOperationalGithubUrl(rawUrl) {
  try {
    const url = new URL(rawUrl);
    if (url.hostname !== "github.com") return false;
    return /\/(edit|new)\//.test(url.pathname);
  } catch {
    return false;
  }
}

function directionReferencesFromSection(section) {
  const rawReferences = Array.from(section.matchAll(/https?:\/\/[^\s)|]+/g))
    .map((match) => normalizedReferenceUrl(match[0]))
    .filter(Boolean);
  const operationalReferences = [...new Set(rawReferences.filter(isOperationalGithubUrl))];
  const references = [...new Set(rawReferences.filter((url) => !isOperationalGithubUrl(url)))];
  const operationalReferenceLeaks = references.filter(isOperationalGithubUrl);
  return {
    references,
    rawReferenceCount: rawReferences.length,
    operationalReferenceExcludedCount: operationalReferences.length,
    operationalReferenceLeakCount: operationalReferenceLeaks.length,
    excludedOperationalReferences: operationalReferences,
    referenceQualityReady: operationalReferenceLeaks.length === 0,
  };
}

function latestDirectionLoopFromMarkdown(markdownText, source) {
  const matches = Array.from(markdownText.matchAll(/^## Loop (\d+) Decision\s*$/gm));
  if (!matches.length) return null;
  const latest = matches.reduce((best, match) => {
    if (!best) return match;
    return Number(match[1]) >= Number(best[1]) ? match : best;
  }, null);
  const loopNumber = Number(latest[1]);
  const sectionStart = latest.index + latest[0].length;
  const nextHeading = matches.find((match) => match.index > latest.index);
  const section = markdownText.slice(sectionStart, nextHeading?.index ?? markdownText.length).trim();
  const paragraphs = section.split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean);
  const summaryParagraph = paragraphs.find((part) => !part.startsWith("|") && !part.startsWith("Loop ")) || "";
  const changedParagraph = paragraphs.find((part) => part.startsWith(`Loop ${loopNumber} changed`)) || "";
  const referenceQuality = directionReferencesFromSection(section);
  return {
    id: `loop-${loopNumber}`,
    number: loopNumber,
    heading: `Loop ${loopNumber} Decision`,
    source,
    summary: compactText(summaryParagraph),
    verification: compactText(changedParagraph, 420),
    referenceCount: referenceQuality.references.length,
    references: referenceQuality.references.slice(0, 8),
    rawReferenceCount: referenceQuality.rawReferenceCount,
    operationalReferenceExcludedCount: referenceQuality.operationalReferenceExcludedCount,
    operationalReferenceLeakCount: referenceQuality.operationalReferenceLeakCount,
    referenceQualityReady: referenceQuality.referenceQualityReady,
  };
}

function githubDiscoveryExperiment(githubDiscovery, source) {
  if (githubDiscovery?.schemaVersion !== "joopark-github-project-discovery/v1" || !githubDiscovery.abComparison) {
    return null;
  }
  const ab = githubDiscovery.abComparison;
  const metric = githubDiscoveryMetric(githubDiscovery);
  const launchSummary = githubDiscovery.launchCandidateSummary || {};
  const topProjects = arrayValue(launchSummary.topProjects)
    .map((project) => ({
      nameWithOwner: String(project?.nameWithOwner || ""),
      relation: String(project?.relation || ""),
      localCheckout: project?.localCheckout === true,
      nextAction: compactText(project?.nextAction || "", 180),
    }))
    .filter((project) => project.nameWithOwner)
    .slice(0, 4);
  const topProjectNames = topProjects.map((project) => project.nameWithOwner);
  return {
    id: githubDiscoveryExperimentId,
    primaryMetric: metric.primaryMetric,
    baseline: metric.baseline,
    candidate: metric.candidate,
    decision: ab.decision === "keep_b" ? "keep" : ab.decision || "review",
    generatedAt: githubDiscovery.generatedAt || new Date().toISOString(),
    topProjects,
    topProjectCount: topProjects.length,
    releaseTargetIncluded: launchSummary.releaseTargetIncluded === true,
    hypothesis: "GitHub-related project discovery should be reproducible and ranked instead of relying on one-off terminal searches before product launch decisions.",
    evidence: [
      `Captured ${Number(githubDiscovery.counts?.localGitRepos || 0)} local Git checkouts from ${githubDiscovery.localRoot || "local workspace"}.`,
      `Captured ${Number(githubDiscovery.counts?.githubRepos || 0)} GitHub repositories for owner ${githubDiscovery.owner || "unknown"}.`,
      `Ranked ${Number(githubDiscovery.counts?.rankedProjects || 0)} related local and remote projects, including local-only and external-owner remotes.`,
      `Actionable public project coverage ${metric.candidate}/${metric.required || "unknown"} from rankedProjects; release target included=${yesNo(launchSummary.releaseTargetIncluded)}.`,
      topProjectNames.length ? `Top reusable projects: ${topProjectNames.join(", ")}.` : "Top reusable projects: none.",
      `Release target ready=${yesNo(githubDiscovery.releaseTargetReady)}; guard=${githubDiscovery.guard || "read-only discovery"}.`,
      `Artifacts: ${source} and data/github-project-discovery.md; artifactCount=${Number(ab.candidateArtifactCount || 0)}.`,
    ],
    externalComparison: {
      label: "Launch work that references multiple GitHub projects needs a reusable inventory artifact with explicit guardrails before any cross-repository edits or external actions.",
      urls: [
        "https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages",
        "https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations",
      ],
    },
  };
}

function directionLoopExperiment(latestDirectionLoop, outputQuality) {
  if (!latestDirectionLoop?.id) return null;
  const metric = "latestDirectionLoopExperimentTraceCoverage";
  const summarySubject = String(latestDirectionLoop.summary || latestDirectionLoop.heading || "")
    .replace(/^The next product gap is\s+/i, "")
    .split(".")[0];
  const summarySlug = slugify(summarySubject, "direction-loop");
  const generatedAt = outputQuality?.generatedAt || new Date().toISOString();
  return {
    id: `${latestDirectionLoop.id}-${summarySlug}`,
    primaryMetric: metric,
    baseline: 0,
    candidate: 1,
    decision: "keep",
    generatedAt,
    hypothesis: "The product-loop headline experiment should point to the latest adopted direction loop so operators can trace current release evidence back to the concrete A/B improvement that just landed.",
    evidence: [
      `Latest direction loop is ${latestDirectionLoop.id} from ${latestDirectionLoop.source}.`,
      `Reference quality: ${latestDirectionLoop.referenceCount || 0} source references, ${latestDirectionLoop.operationalReferenceExcludedCount || 0} operational repair URLs excluded, ${latestDirectionLoop.operationalReferenceLeakCount || 0} leaked.`,
      `Direction summary: ${latestDirectionLoop.summary || "not available"}`,
      `Verification summary: ${latestDirectionLoop.verification || "not available"}`,
      `Output-quality audit generatedAt=${outputQuality?.generatedAt || "not available"}; readyForExternalClaim=${yesNo(outputQuality?.readyForExternalClaim)}.`,
    ],
    externalComparison: {
      label: "Operator-facing release summaries should keep the newest adopted improvement close to the evidence receipt, while manual dispatch and public release claims remain separately guarded.",
      urls: [
        "https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary",
        "https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow",
        "https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases",
      ],
    },
  };
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
const githubDiscovery = readJson(githubDiscoveryRel, {});
const latestDirectionLoop = latestDirectionLoopFromMarkdown(readText(directionLogRel), directionLogRel);
const latestGate = outputQuality?.latestGate || null;

if (!latestGate) {
  console.error(`Missing latestGate in ${outputQualityRel}`);
  process.exit(1);
}

const generatedAt = new Date().toISOString();
const publishPatch = publishPatchFromOutputQuality(outputQuality);
const status = statusFromOutputQuality(outputQuality);
const nextCandidates = nextCandidatesForStatus(status, publishPatch);
const baseline = parityScore({ productLoop, latestGate, publishPatch });
const beforeGateChecks = productLoop?.latestGate?.checks || {};
const changedPublish = changedPublishKeys(productLoop?.publish || {}, publishPatch);
const latestGateUpdated = !sameJson(productLoop?.latestGate, latestGate);
const gateChanged = !sameJson(latestGateForParity(productLoop?.latestGate), latestGateForParity(latestGate));
const statusChanged = productLoop?.status !== status;
const nextCandidatesChanged = !sameJson(productLoop?.nextCandidates, nextCandidates);
const summarySyncOutputQualityStale = productLoop.summarySync?.outputQualityGeneratedAt !== (outputQuality?.generatedAt || "");
const summarySyncParityMissing = productLoop.summarySync?.gateParityReady !== true || productLoop.summarySync?.publishParityReady !== true;
const summarySyncNextCandidatesMissing = productLoop.summarySync?.nextCandidatesReady !== true ||
  productLoop.summarySync?.nextCandidateCount !== nextCandidates.length;
const directionLoopChanged = !sameJson(productLoop.latestDirectionLoop, latestDirectionLoop);
const discoveryExperiment = githubDiscoveryExperiment(githubDiscovery, githubDiscoveryRel);
const directionExperiment = directionLoopExperiment(latestDirectionLoop, outputQuality);
const existingDiscoveryExperiment = Array.isArray(productLoop?.experiments)
  ? productLoop.experiments.find((item) => item?.id === githubDiscoveryExperimentId)
  : null;
const discoveryExperimentChanged = !!discoveryExperiment && !sameJson(existingDiscoveryExperiment, discoveryExperiment);
const discoveryExperimentSummary = discoveryExperiment ? experimentSummary(discoveryExperiment) : null;
const discoveryExperimentMetadataMissing = !!discoveryExperimentSummary &&
  (
    productLoop.summarySync?.latestDiscoveryExperimentReady !== true ||
    productLoop.summarySync?.latestDiscoveryExperimentId !== discoveryExperimentSummary.id ||
    !sameJson(productLoop.latestDiscoveryExperiment, discoveryExperimentSummary)
  );
const existingDirectionExperiment = Array.isArray(productLoop?.experiments)
  ? productLoop.experiments.find((item) => item?.id === directionExperiment?.id)
  : null;
const directionExperimentChanged = !!directionExperiment && !sameJson(existingDirectionExperiment, directionExperiment);
const metadataMissing = !productLoop?.summarySync ||
  productLoop.summarySync.source !== "scripts/sync-product-loop-summary.mjs" ||
  productLoop.summarySync.productLoopPath !== productLoopRel ||
  productLoop.summarySync.outputQualityPath !== outputQualityRel ||
  productLoop.summarySync.directionLogPath !== directionLogRel ||
  (!!discoveryExperiment && productLoop.summarySync.githubDiscoveryPath !== githubDiscoveryRel) ||
  discoveryExperimentMetadataMissing ||
  (!!directionExperiment && productLoop.summarySync.latestDirectionExperimentId !== directionExperiment.id);
const semanticSyncNeeded = baseline < 2 || latestGateUpdated || gateChanged || changedPublish.length > 0 || statusChanged || nextCandidatesChanged || metadataMissing || summarySyncOutputQualityStale || summarySyncParityMissing || summarySyncNextCandidatesMissing || directionLoopChanged || discoveryExperimentChanged || directionExperimentChanged;
const existingSyncExperiment = Array.isArray(productLoop?.experiments)
  ? productLoop.experiments.find((item) => item?.id === experimentId)
  : null;
const syncExperimentShouldRefresh = !existingSyncExperiment || baseline < 2 || latestGateUpdated || gateChanged || changedPublish.length > 0 || nextCandidatesChanged || summarySyncOutputQualityStale || summarySyncParityMissing || summarySyncNextCandidatesMissing;
const candidateLoop = semanticSyncNeeded
  ? {
      ...productLoop,
      generatedAt,
      status,
      nextCandidates,
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
        directionLogPath: directionLogRel,
        githubDiscoveryPath: discoveryExperiment ? githubDiscoveryRel : "",
        githubDiscoveryGeneratedAt: githubDiscovery?.generatedAt || "",
        githubDiscoveryExperimentReady: !!discoveryExperiment,
        latestDiscoveryExperimentReady: !!discoveryExperimentSummary,
        latestDiscoveryExperimentId: discoveryExperimentSummary?.id || "",
        outputQualityGeneratedAt: outputQuality?.generatedAt || "",
        gateParityReady: true,
        publishParityReady: true,
        directionLoopReady: !!latestDirectionLoop,
        latestDirectionLoopNumber: latestDirectionLoop?.number || 0,
        latestDirectionExperimentReady: !!directionExperiment,
        latestDirectionExperimentId: directionExperiment?.id || "",
        gateChanged,
        latestGateUpdated,
        directionLoopChanged,
        directionExperimentChanged,
        discoveryExperimentMetadataMissing,
        discoveryExperimentChanged,
        nextCandidatesChanged,
        changedPublishKeys: changedPublish,
        baselineParityCoverage: baseline,
        candidateParityCoverage: 2,
        syncExperimentUpdated: syncExperimentShouldRefresh,
        nextCandidatesReady: true,
        nextCandidateCount: nextCandidates.length,
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
    `Next candidates are synchronized to proof-ready state: nextCandidateCount=${nextCandidates.length}, readyForExternalClaim=${yesNo(publishPatch.readyForExternalClaim)}.`,
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
if (discoveryExperiment) {
  candidateLoop.experiments = upsertExperiment(candidateLoop.experiments, discoveryExperiment, {
    refresh: true,
  });
}
if (directionExperiment) {
  candidateLoop.experiments = upsertExperiment(candidateLoop.experiments, directionExperiment, {
    refresh: true,
  });
}
const syncNowMs = Date.parse(generatedAt);
const futureExperiments = futureExperimentSummaries(candidateLoop.experiments, syncNowMs);
candidateLoop.latestExperiment = latestExperimentSummary(candidateLoop.experiments, syncNowMs, {
  excludeIds: [...summaryExperimentIds],
});
candidateLoop.latestDirectionLoop = latestDirectionLoop;
candidateLoop.latestDiscoveryExperiment = experimentSummary(
  candidateLoop.experiments.find((item) => item?.id === githubDiscoveryExperimentId),
);
candidateLoop.latestSyncExperiment = experimentSummary(
  candidateLoop.experiments.find((item) => item?.id === experimentId),
);
candidateLoop.summarySync.latestDiscoveryExperimentReady = !!candidateLoop.latestDiscoveryExperiment;
candidateLoop.summarySync.latestDiscoveryExperimentId = candidateLoop.latestDiscoveryExperiment?.id || "";
candidateLoop.summarySync.futureDatedExperimentCount = futureExperiments.length;
candidateLoop.summarySync.futureDatedExperimentIds = futureExperiments.map((item) => item.id);

const after = {
  gateParityReady: sameJson(latestGateForParity(candidateLoop.latestGate), latestGateForParity(latestGate)),
  publishParityReady: trackedPublishParity(candidateLoop.publish, publishPatch),
  directionLoopReady: !!latestDirectionLoop && sameJson(candidateLoop.latestDirectionLoop, latestDirectionLoop),
  nextCandidatesReady: sameJson(candidateLoop.nextCandidates, nextCandidates),
  parityCoverage: parityScore({ productLoop: candidateLoop, latestGate, publishPatch }),
};
const writeApplied = write && semanticSyncNeeded;

const payload = {
  status: after.gateParityReady && after.publishParityReady && after.directionLoopReady && after.nextCandidatesReady ? "pass" : "fail",
  generatedAt,
  write,
  writeApplied,
  productLoopPath: productLoopRel,
  outputQualityPath: outputQualityRel,
  directionLogPath: directionLogRel,
  outputQualityGeneratedAt: outputQuality?.generatedAt || "",
  baselineParityCoverage: baseline,
  candidateParityCoverage: after.parityCoverage,
  gateChanged,
  latestGateUpdated,
  directionLoopChanged,
  discoveryExperimentChanged,
  discoveryExperimentMetadataMissing,
  directionExperimentChanged,
  nextCandidatesChanged,
  latestDirectionLoop,
  githubDiscoveryGeneratedAt: githubDiscovery?.generatedAt || "",
  summarySyncOutputQualityStale,
  summarySyncParityMissing,
  semanticSyncNeeded,
  changedPublishKeys: changedPublish,
  nextCandidateCount: nextCandidates.length,
  syncExperimentUpdated: syncExperimentShouldRefresh,
  latestExperiment: candidateLoop.latestExperiment,
  latestSyncExperiment: candidateLoop.latestSyncExperiment,
  latestDirectionExperiment: directionExperiment ? experimentSummary(directionExperiment) : null,
  latestDiscoveryExperiment: candidateLoop.latestDiscoveryExperiment,
  futureDatedExperimentCount: futureExperiments.length,
  futureDatedExperimentIds: futureExperiments.map((item) => item.id),
  before: {
    latestGateChecks: beforeGateChecks,
    publish: productLoop?.publish || {},
    nextCandidates: Array.isArray(productLoop?.nextCandidates) ? productLoop.nextCandidates : [],
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
    `- directionLoopChanged: ${yesNo(payload.directionLoopChanged)}`,
    `- discoveryExperimentChanged: ${yesNo(payload.discoveryExperimentChanged)}`,
    `- directionExperimentChanged: ${yesNo(payload.directionExperimentChanged)}`,
    `- nextCandidatesChanged: ${yesNo(payload.nextCandidatesChanged)}`,
    `- latestDirectionLoop: ${payload.latestDirectionLoop?.id || "none"}`,
    `- githubDiscoveryGeneratedAt: ${payload.githubDiscoveryGeneratedAt || "none"}`,
    `- summarySyncOutputQualityStale: ${yesNo(payload.summarySyncOutputQualityStale)}`,
    `- summarySyncParityMissing: ${yesNo(payload.summarySyncParityMissing)}`,
    `- semanticSyncNeeded: ${yesNo(payload.semanticSyncNeeded)}`,
    `- writeApplied: ${yesNo(payload.writeApplied)}`,
    `- changedPublishKeys: ${payload.changedPublishKeys.length ? payload.changedPublishKeys.join(", ") : "none"}`,
    `- nextCandidateCount: ${payload.nextCandidateCount}`,
    `- syncExperimentUpdated: ${yesNo(payload.syncExperimentUpdated)}`,
    `- latestExperiment: ${payload.latestExperiment?.id || "none"}`,
    `- latestDirectionExperiment: ${payload.latestDirectionExperiment?.id || "none"}`,
    `- latestDiscoveryExperiment: ${payload.latestDiscoveryExperiment?.id || "none"}`,
    `- futureDatedExperiments: ${payload.futureDatedExperimentCount}`,
  ].join("\n"));
} else {
  console.log(JSON.stringify(payload, null, 2));
}
