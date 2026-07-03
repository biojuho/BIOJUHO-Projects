/* ================================================================
 * JooPark Workspace — dashboard evidence receipts.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkDashboardEvidenceReceipts(global) {
  "use strict";

  const VERSION = "joopark-dashboard-evidence-receipts/v1";

  function listOf(value) {
    return Array.isArray(value) ? value : [];
  }

  function clean(value) {
    return String(value == null ? "" : value).replace(/\s+/g, " ").trim();
  }

  function confidenceText(value) {
    const number = Number(value);
    const bounded = Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : 0;
    return bounded.toFixed(2);
  }

  function receiptMarkdown(receipt) {
    const sourceRefs = listOf(receipt.sourceRefs);
    const riskFlags = listOf(receipt.riskFlags);
    const action = receipt.nextAction || {};
    return [
      "# JooPark Dashboard Decision Receipt",
      "",
      `- id: ${clean(receipt.id)}`,
      `- createdAt: ${clean(receipt.createdAt)}`,
      `- verificationStatus: ${clean(receipt.verificationStatus)}`,
      `- confidence: ${confidenceText(receipt.confidence)}`,
      `- receiptHash: ${clean(receipt.receiptHash)}`,
      `- summary: ${clean(receipt.summary)}`,
      "",
      "## Source refs",
      ...(sourceRefs.length ? sourceRefs.map((item) => `- ${clean(item)}`) : ["- none"]),
      "",
      "## Risk flags",
      ...(riskFlags.length ? riskFlags.map((item) => `- ${clean(item)}`) : ["- none"]),
      "",
      "## Next action",
      `- label: ${clean(action.label)}`,
      `- command: ${clean(action.command) || "none"}`,
      `- view: ${clean(action.view) || "home"}`,
      `- status: ${clean(action.status) || "proposed"}`,
    ].join("\n");
  }

  function createReceipt(input = {}, storage) {
    const normalizer = storage && typeof storage.normalizeDashboardRecord === "function"
      ? storage.normalizeDashboardRecord
      : (value) => value;
    const receipt = normalizer({
      ...input,
      verificationStatus: input.verificationStatus || "local_receipt_ready",
    });
    return {
      ...receipt,
      markdown: receiptMarkdown(receipt),
    };
  }

  function createDashboardEvidenceReceipts(deps = {}) {
    const storage = deps.storage || null;
    return Object.freeze({
      version: VERSION,
      createReceipt: (input) => createReceipt(input, storage),
      receiptMarkdown,
      confidenceText,
    });
  }

  global.JooParkDashboardEvidenceReceipts = Object.freeze({
    version: VERSION,
    create: createDashboardEvidenceReceipts,
  });
})(typeof window !== "undefined" ? window : globalThis);
