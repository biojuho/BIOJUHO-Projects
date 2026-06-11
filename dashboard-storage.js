/* ================================================================
 * JooPark Workspace — dashboard intelligence localStorage helpers.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkDashboardStorage(global) {
  "use strict";

  const VERSION = "joopark-dashboard-storage/v1";
  const COLLECTION_KEYS = Object.freeze([
    "dashboardInsights",
    "dashboardResearchLoops",
    "dashboardImprovementCandidates",
    "dashboardDecisionReceipts",
    "dashboardEvidenceSnapshots",
    "dashboardHealthChecks",
  ]);
  const RETENTION_LIMITS = Object.freeze({
    dashboardInsights: 80,
    dashboardResearchLoops: 40,
    dashboardImprovementCandidates: 120,
    dashboardDecisionReceipts: 80,
    dashboardEvidenceSnapshots: 60,
    dashboardHealthChecks: 120,
  });
  const SCORE_KEYS = Object.freeze([
    "userValue",
    "urgency",
    "difficulty",
    "regressionRisk",
    "performance",
    "accessibility",
    "security",
    "maintainability",
    "releaseReadiness",
    "localStorageStability",
    "mobileUX",
    "evidenceTraceability",
  ]);

  function listOf(value) {
    return Array.isArray(value) ? value : [];
  }

  function isObject(value) {
    return Boolean(value && typeof value === "object" && !Array.isArray(value));
  }

  function cleanString(value, max) {
    return String(value == null ? "" : value).replace(/\s+/g, " ").trim().slice(0, max || 240);
  }

  function cleanStringArray(value, maxItems, maxLength) {
    return listOf(value)
      .map((item) => cleanString(item, maxLength || 160))
      .filter(Boolean)
      .slice(0, maxItems || 12);
  }

  function boundedScore(value, fallback) {
    const number = Number(value);
    if (!Number.isFinite(number)) return fallback;
    return Math.max(1, Math.min(5, Math.round(number)));
  }

  function boundedConfidence(value, fallback = 0.65) {
    const fallbackNumber = Number(fallback);
    const safeFallback = Number.isFinite(fallbackNumber) ? Math.max(0, Math.min(1, fallbackNumber)) : 0.65;
    if (value === null || value === undefined) return safeFallback;
    const number = Number(value);
    if (!Number.isFinite(number)) return safeFallback;
    return Math.max(0, Math.min(1, number));
  }

  function normalizeScoreBreakdown(value) {
    const input = isObject(value) ? value : {};
    const out = {};
    SCORE_KEYS.forEach((key) => {
      out[key] = boundedScore(input[key], 3);
    });
    if (Number.isFinite(Number(input.total))) out.total = Number(input.total);
    if (Number.isFinite(Number(input.weighted))) out.weighted = Number(input.weighted);
    return out;
  }

  function normalizeNextAction(value) {
    if (typeof value === "string") {
      return { label: cleanString(value, 160), command: "", view: "", status: "proposed" };
    }
    const input = isObject(value) ? value : {};
    return {
      label: cleanString(input.label || input.summary || "다음 액션 확인", 160),
      command: cleanString(input.command || "", 220),
      view: cleanString(input.view || input.viewName || "", 40),
      status: cleanString(input.status || "proposed", 40),
    };
  }

  function stableValue(value) {
    if (Array.isArray(value)) return value.map(stableValue);
    if (isObject(value)) {
      return Object.keys(value).sort().reduce((out, key) => {
        out[key] = stableValue(value[key]);
        return out;
      }, {});
    }
    return value;
  }

  function stableStringify(value) {
    try { return JSON.stringify(stableValue(value)); } catch (_) { return ""; }
  }

  function hashString(value) {
    const text = String(value || "");
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return `dash-${(hash >>> 0).toString(16).padStart(8, "0")}`;
  }

  function normalizeDashboardRecord(record, fallback = {}) {
    const input = isObject(record) ? record : {};
    const createdAt = cleanString(input.createdAt || fallback.createdAt || new Date().toISOString(), 80);
    const normalized = {
      id: cleanString(input.id || fallback.id || `dash-${createdAt.replace(/[^0-9]/g, "").slice(0, 14)}`, 80),
      createdAt,
      sourceRefs: cleanStringArray(input.sourceRefs || fallback.sourceRefs, 20, 180),
      summary: cleanString(input.summary || fallback.summary, 360),
      scoreBreakdown: normalizeScoreBreakdown(input.scoreBreakdown || fallback.scoreBreakdown),
      confidence: boundedConfidence(input.confidence, fallback.confidence ?? 0.65),
      verificationStatus: cleanString(input.verificationStatus || fallback.verificationStatus || "needs_review", 60),
      riskFlags: cleanStringArray(input.riskFlags || fallback.riskFlags, 16, 120),
      nextAction: normalizeNextAction(input.nextAction || fallback.nextAction),
      receiptHash: cleanString(input.receiptHash || "", 80),
    };
    Object.keys(input).forEach((key) => {
      if (normalized[key] !== undefined) return;
      const value = input[key];
      if (typeof value === "string") normalized[key] = cleanString(value, 360);
      else if (typeof value === "number" || typeof value === "boolean") normalized[key] = value;
      else if (Array.isArray(value)) normalized[key] = cleanStringArray(value, 20, 180);
      else if (isObject(value)) normalized[key] = stableValue(value);
    });
    const hashPayload = { ...normalized, receiptHash: "" };
    normalized.receiptHash = normalized.receiptHash || hashString(stableStringify(hashPayload));
    return normalized;
  }

  function ensureCollections(dashboard) {
    COLLECTION_KEYS.forEach((key) => {
      if (!Array.isArray(dashboard[key])) dashboard[key] = [];
      dashboard[key] = dashboard[key]
        .map((record, index) => normalizeDashboardRecord(record, { id: `${key}-${index + 1}` }))
        .slice(0, RETENTION_LIMITS[key] || 80);
    });
    return dashboard;
  }

  function appendRecord(dashboard, key, record) {
    if (!COLLECTION_KEYS.includes(key)) throw new Error(`Unknown dashboard collection: ${key}`);
    ensureCollections(dashboard);
    const normalized = normalizeDashboardRecord(record);
    const existing = dashboard[key].filter((item) => item.id !== normalized.id && item.receiptHash !== normalized.receiptHash);
    dashboard[key] = [normalized, ...existing].slice(0, RETENTION_LIMITS[key] || 80);
    return normalized;
  }

  function collectionSummary(dashboard) {
    ensureCollections(dashboard);
    return COLLECTION_KEYS.map((key) => ({
      key,
      count: dashboard[key].length,
      retention: RETENTION_LIMITS[key] || 80,
      latestHash: dashboard[key][0] ? dashboard[key][0].receiptHash : "",
    }));
  }

  function createDashboardStorage() {
    return Object.freeze({
      version: VERSION,
      collectionKeys: COLLECTION_KEYS.slice(),
      scoreKeys: SCORE_KEYS.slice(),
      retentionLimits: { ...RETENTION_LIMITS },
      boundedConfidence,
      normalizeDashboardRecord,
      ensureCollections,
      appendRecord,
      collectionSummary,
      stableStringify,
      receiptHash: (value) => hashString(stableStringify(value)),
    });
  }

  global.JooParkDashboardStorage = Object.freeze({
    version: VERSION,
    create: createDashboardStorage,
  });
})(typeof window !== "undefined" ? window : globalThis);
