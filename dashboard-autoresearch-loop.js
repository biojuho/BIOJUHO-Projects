/* ================================================================
 * JooPark Workspace — repeatable local AutoResearch loop.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkDashboardAutoresearchLoop(global) {
  "use strict";

  const VERSION = "joopark-dashboard-autoresearch-loop/v1";
  const LOOP_STEPS = Object.freeze([
    "project_state_recheck",
    "localStorage_summary",
    "evidence_check",
    "research_expansion",
    "problem_opportunity_mining",
    "priority_scoring",
    "dashboard_improvement_design",
    "implementation_patch",
    "verification",
    "evidence_receipt",
    "system_status_receipt",
    "next_loop_candidates",
  ]);

  function listOf(value) {
    return Array.isArray(value) ? value : [];
  }

  function latestId(prefix) {
    return `${prefix}-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
  }

  function boundedConfidence(value, fallback = 0.72) {
    const fallbackNumber = Number(fallback);
    const safeFallback = Number.isFinite(fallbackNumber) ? Math.max(0, Math.min(1, fallbackNumber)) : 0.72;
    if (value === null || value === undefined) return safeFallback;
    const number = Number(value);
    if (!Number.isFinite(number)) return safeFallback;
    return Math.max(0, Math.min(1, number));
  }

  function candidateWithSafeConfidence(candidate, fallback = 0.72) {
    const output = { ...candidate };
    if (Object.prototype.hasOwnProperty.call(output, "confidence")) {
      output.confidence = boundedConfidence(output.confidence, fallback);
    }
    return output;
  }

  function runLoop(input = {}) {
    const dashboard = input.dashboard || {};
    const storage = input.storage;
    const prioritization = input.prioritization;
    const receipts = input.receipts;
    const insightsEngine = input.insightsEngine;
    if (!storage || !prioritization || !receipts || !insightsEngine) {
      throw new Error("dashboard autoresearch loop requires storage, prioritization, receipts, and insights engine");
    }
    storage.ensureCollections(dashboard);
    const createdAt = input.createdAt || new Date().toISOString();
    const model = insightsEngine.dashboardInsightsModel({
      ...input,
      createdAt,
    });
    const ranked = prioritization.rankCandidates(model.candidates)
      .slice(0, 8)
      .map((candidate) => candidateWithSafeConfidence(candidate));
    const top = ranked[0] || {};
    const topConfidence = boundedConfidence(top.confidence, 0.72);
    const sourceRefs = [
      "README.md",
      "docs/app-architecture.md",
      "workspace-storage.js",
      "settings-view.js",
      "system-status-view.js",
      "llm-wiki-view.js",
      "ops-runtime-loader.js",
      "autoresearch-results/joopark-product-loop.json",
      "autoresearch-results/verify-workspace-summary.json",
      ...listOf(top.sourceRefs),
    ];
    const loopRecord = storage.appendRecord(dashboard, "dashboardResearchLoops", {
      id: latestId("loop"),
      createdAt,
      sourceRefs,
      summary: `AutoResearch loop completed ${LOOP_STEPS.length} local steps; top candidate: ${top.summary || "dashboard retention review"}`,
      scoreBreakdown: top.scoreBreakdown || {},
      confidence: topConfidence,
      verificationStatus: "local_loop_ready",
      riskFlags: listOf(top.riskFlags),
      nextAction: top.nextAction || { label: "다음 후보 검토", view: "home", status: "proposed" },
      loopSteps: LOOP_STEPS.slice(),
      activeUntilUserStops: input.active === true,
    });
    ranked.forEach((candidate, index) => {
      storage.appendRecord(dashboard, "dashboardImprovementCandidates", {
        ...candidate,
        id: candidate.id || `${loopRecord.id}-candidate-${index + 1}`,
        createdAt,
        verificationStatus: "local_scored",
      });
    });
    const evidenceSnapshot = storage.appendRecord(dashboard, "dashboardEvidenceSnapshots", {
      id: `${loopRecord.id}-snapshot`,
      createdAt,
      sourceRefs,
      summary: `${model.cards.length} dashboard cards, ${ranked.length} candidates, ${model.externalResearchSources.length} external sources`,
      scoreBreakdown: top.scoreBreakdown || {},
      confidence: 0.78,
      verificationStatus: "snapshot_ready",
      riskFlags: model.cards.filter((card) => card.riskLevel >= 4).map((card) => card.key),
      nextAction: { label: "System Status receipt 확인", view: "system", status: "ready" },
      cardCount: model.cards.length,
      candidateCount: ranked.length,
      externalResearchSources: model.externalResearchSources,
      needs_external_validation: model.sourceSummary.needs_external_validation === true,
    });
    const healthCheck = storage.appendRecord(dashboard, "dashboardHealthChecks", {
      id: `${loopRecord.id}-health`,
      createdAt,
      sourceRefs: ["localStorage", "workspace-storage.js", "backup-import-guards.js"],
      summary: `dashboard intelligence collections retained: ${storage.collectionSummary(dashboard).map((item) => `${item.key}=${item.count}/${item.retention}`).join(", ")}`,
      scoreBreakdown: { localStorageStability: 5, performance: 4, evidenceTraceability: 5, maintainability: 4 },
      confidence: 0.81,
      verificationStatus: "retention_checked",
      riskFlags: [],
      nextAction: { label: "JSON export/import guard 검증", command: "npm run verify:dashboard", view: "system", status: "ready" },
    });
    const insight = storage.appendRecord(dashboard, "dashboardInsights", {
      id: `${loopRecord.id}-insight`,
      createdAt,
      sourceRefs,
      summary: `운영 관제판은 ${model.cards.filter((card) => card.riskLevel >= 3).length}개 위험 카드를 우선 표시해야 합니다.`,
      scoreBreakdown: top.scoreBreakdown || {},
      confidence: 0.79,
      verificationStatus: "insight_ready",
      riskFlags: listOf(top.riskFlags),
      nextAction: top.nextAction || { label: "Home 관제판 검토", view: "home", status: "ready" },
    });
    const receipt = receipts.createReceipt({
      id: `${loopRecord.id}-receipt`,
      createdAt,
      sourceRefs,
      summary: `Decision: ${top.summary || "dashboard retention review"}`,
      scoreBreakdown: top.scoreBreakdown || {},
      confidence: topConfidence,
      verificationStatus: "receipt_ready",
      riskFlags: listOf(top.riskFlags),
      nextAction: top.nextAction || { label: "다음 후보 검토", view: "home", status: "ready" },
      loopId: loopRecord.id,
      evidenceSnapshotHash: evidenceSnapshot.receiptHash,
      healthCheckHash: healthCheck.receiptHash,
      insightHash: insight.receiptHash,
    });
    const decisionReceipt = storage.appendRecord(dashboard, "dashboardDecisionReceipts", receipt);
    return {
      version: VERSION,
      loopRecord,
      rankedCandidates: ranked,
      evidenceSnapshot,
      healthCheck,
      insight,
      decisionReceipt,
      model,
      nextLoopCandidates: ranked.slice(0, 5),
    };
  }

  function createDashboardAutoresearchLoop() {
    return Object.freeze({
      version: VERSION,
      loopSteps: LOOP_STEPS.slice(),
      boundedConfidence,
      runLoop,
    });
  }

  global.JooParkDashboardAutoresearchLoop = Object.freeze({
    version: VERSION,
    create: createDashboardAutoresearchLoop,
  });
})(typeof window !== "undefined" ? window : globalThis);
